"""
scraper.py — Async RSS + Hacker News + Trafilatura full-text extractor.

Sources:
  - Hacker News API (Top/Best stories, filtered by score > HN_MIN_SCORE)
  - RSS: r/ReverseEngineering, PHP internals, Simon Willison's blog,
         Lobste.rs, GitHub Blog, security feeds, Python dev feeds
"""
from __future__ import annotations

import asyncio
import json
import logging
import re
from datetime import datetime, timezone
from typing import Optional
from urllib.parse import urlparse

import feedparser
import httpx
import trafilatura

from config import get_settings
from models import ArticleCreate

logger = logging.getLogger(__name__)
settings = get_settings()

# ─────────────────────────────────────────────────────────────────────────────
# RSS Feed Registry
# ─────────────────────────────────────────────────────────────────────────────

RSS_FEEDS: list[dict] = [
    # Reverse Engineering & Low-Level
    {
        "url": "https://www.reddit.com/r/ReverseEngineering/.rss",
        "category_hint": "rea",
        "name": "r/ReverseEngineering",
    },
    {
        "url": "https://feeds.feedburner.com/eset/blog",
        "category_hint": "rea",
        "name": "ESET Security Blog",
    },
    # Security / CVEs
    {
        "url": "https://googleprojectzero.blogspot.com/feeds/posts/default",
        "category_hint": "bugs_cves",
        "name": "Project Zero",
    },
    {
        "url": "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json",
        "category_hint": "bugs_cves",
        "name": "CISA KEV",
        "is_json": True,
    },
    {
        "url": "https://feeds.feedburner.com/TheHackersNews",
        "category_hint": "bugs_cves",
        "name": "The Hacker News",
    },
    # Applied AI
    {
        "url": "https://simonwillison.net/atom/everything/",
        "category_hint": "applied_ai",
        "name": "Simon Willison",
    },
    {
        "url": "https://www.latent.space/feed",
        "category_hint": "applied_ai",
        "name": "Latent Space",
    },
    # Dev QoL
    {
        "url": "https://lobste.rs/rss",
        "category_hint": "dev_qol",
        "name": "Lobste.rs",
    },
    # Architecture / Engineering
    {
        "url": "https://github.blog/feed/",
        "category_hint": "architecture",
        "name": "GitHub Blog",
    },
    {
        "url": "https://engineering.fb.com/feed/",
        "category_hint": "architecture",
        "name": "Meta Engineering",
    },
    {
        "url": "https://planetpython.org/rss20.xml",
        "category_hint": "bugs_cves",
        "name": "Planet Python",
    },
    {
        "url": "https://www.php.net/releases/feed.php",
        "category_hint": "bugs_cves",
        "name": "PHP Releases",
    },
    {
        "url": "https://blog.rust-lang.org/feed.xml",
        "category_hint": "architecture",
        "name": "Rust Blog",
    },
]

# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _extract_domain(url: str) -> str:
    try:
        parsed = urlparse(url)
        domain = parsed.netloc.lstrip("www.")
        return domain or url
    except Exception:
        return url


def _parse_dt(value) -> Optional[datetime]:
    """Best-effort datetime parsing from feedparser's time structs or strings."""
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    try:
        import time as _time
        ts = _time.mktime(value)
        return datetime.fromtimestamp(ts, tz=timezone.utc)
    except (TypeError, ValueError, OverflowError):
        pass
    if isinstance(value, str):
        for fmt in ("%Y-%m-%dT%H:%M:%SZ", "%Y-%m-%d %H:%M:%S", "%a, %d %b %Y %H:%M:%S %z"):
            try:
                return datetime.strptime(value, fmt).replace(tzinfo=timezone.utc)
            except ValueError:
                continue
    return None


async def extract_full_text(url: str, client: httpx.AsyncClient) -> tuple[str, bool]:
    """
    Fetch URL and extract clean main-body text using trafilatura.
    Returns (text, success_flag).
    """
    try:
        resp = await client.get(
            url,
            headers={"User-Agent": "DevPulse/1.0 (tech news aggregator)"},
            follow_redirects=True,
            timeout=20.0,
        )
        resp.raise_for_status()
        html = resp.text
        text = trafilatura.extract(
            html,
            include_comments=False,
            include_tables=True,
            no_fallback=False,
            favor_recall=True,
        )
        if text and len(text.strip()) > 100:
            return text.strip(), True
        return "", False
    except Exception as exc:
        logger.debug("Full text extraction failed for %s: %s", url, exc)
        return "", False


# ─────────────────────────────────────────────────────────────────────────────
# Hacker News
# ─────────────────────────────────────────────────────────────────────────────

HN_API = "https://hacker-news.firebaseio.com/v0"


async def _hn_fetch_item(item_id: int, client: httpx.AsyncClient) -> Optional[dict]:
    try:
        resp = await client.get(f"{HN_API}/item/{item_id}.json", timeout=10.0)
        resp.raise_for_status()
        return resp.json()
    except Exception:
        return None


async def scrape_hacker_news(
    client: httpx.AsyncClient,
    min_score: int = 100,
    limit: int = 30,
) -> list[ArticleCreate]:
    """
    Fetch top Hacker News stories filtered by minimum score.
    Also includes Show HN posts above a lower threshold.
    """
    articles: list[ArticleCreate] = []
    try:
        # Fetch both top and best story lists
        ids_resp_top = await client.get(f"{HN_API}/topstories.json", timeout=15.0)
        ids_resp_best = await client.get(f"{HN_API}/beststories.json", timeout=15.0)
        ids_top: list[int] = ids_resp_top.json()[:80]
        ids_best: list[int] = ids_resp_best.json()[:80]

        # Deduplicate, prioritise top
        seen: set[int] = set()
        combined: list[int] = []
        for i in ids_top + ids_best:
            if i not in seen:
                seen.add(i)
                combined.append(i)
        combined = combined[:120]

        # Fetch items concurrently in batches of 20
        batch_size = 20
        for batch_start in range(0, len(combined), batch_size):
            batch = combined[batch_start : batch_start + batch_size]
            tasks = [_hn_fetch_item(i, client) for i in batch]
            items = await asyncio.gather(*tasks, return_exceptions=False)

            for item in items:
                if not item or item.get("type") != "story":
                    continue
                score = item.get("score", 0)
                url = item.get("url", "")
                title = item.get("title", "")

                # Show HN with lower threshold
                is_show_hn = title.lower().startswith("show hn")
                threshold = max(50, min_score // 2) if is_show_hn else min_score

                if score < threshold or not url:
                    continue

                # Skip pure HN-internal threads (Ask HN, etc.)
                if url.startswith("https://news.ycombinator.com"):
                    continue

                published = None
                ts = item.get("time")
                if ts:
                    published = datetime.fromtimestamp(ts, tz=timezone.utc)

                articles.append(
                    ArticleCreate(
                        source_url=url,
                        source_domain=_extract_domain(url),
                        original_title=title,
                        published_at=published,
                        hn_score=score,
                        hn_comments=item.get("descendants", 0),
                        hn_item_id=item.get("id"),
                    )
                )
                if len(articles) >= limit:
                    break

            if len(articles) >= limit:
                break

        logger.info("HN scraper collected %d articles", len(articles))
    except Exception as exc:
        logger.error("HN scraper failed: %s", exc)

    return articles


# ─────────────────────────────────────────────────────────────────────────────
# RSS Scraper
# ─────────────────────────────────────────────────────────────────────────────

async def _fetch_feed(
    feed_meta: dict, client: httpx.AsyncClient
) -> list[ArticleCreate]:
    articles: list[ArticleCreate] = []
    url = feed_meta["url"]
    is_json_feed = feed_meta.get("is_json", False)

    try:
        resp = await client.get(
            url,
            headers={"User-Agent": "DevPulse/1.0"},
            follow_redirects=True,
            timeout=20.0,
        )
        resp.raise_for_status()

        if is_json_feed:
            # Handle CISA JSON feed specially
            data = resp.json()
            vulnerabilities = data.get("vulnerabilities", [])
            for vuln in vulnerabilities[:5]:
                vuln_url = vuln.get("references", [{}])[0].get("url", "") if vuln.get("references") else ""
                if not vuln_url:
                    vuln_url = f"https://www.cisa.gov/known-exploited-vulnerabilities-catalog"
                title = f"CISA KEV: {vuln.get('vulnerabilityName', 'Unknown')} - {vuln.get('cveID', '')}"
                articles.append(
                    ArticleCreate(
                        source_url=vuln_url + f"#{vuln.get('cveID', '')}",
                        source_domain="cisa.gov",
                        original_title=title,
                        published_at=None,
                        hn_score=0,
                    )
                )
            return articles

        # Standard RSS/Atom via feedparser
        parsed = feedparser.parse(resp.text)
        for entry in parsed.entries[:15]:
            link = getattr(entry, "link", "") or ""
            title = getattr(entry, "title", "") or ""
            if not link or not title:
                continue

            published = _parse_dt(getattr(entry, "published_parsed", None))

            articles.append(
                ArticleCreate(
                    source_url=link,
                    source_domain=_extract_domain(link),
                    original_title=title.strip(),
                    published_at=published,
                    hn_score=0,
                )
            )
    except Exception as exc:
        logger.warning("RSS feed failed [%s]: %s", feed_meta.get("name", url), exc)

    return articles


async def scrape_rss_feeds(
    client: httpx.AsyncClient, limit_per_feed: int = 15
) -> list[ArticleCreate]:
    """Fetch all configured RSS feeds concurrently."""
    tasks = [_fetch_feed(feed, client) for feed in RSS_FEEDS]
    results = await asyncio.gather(*tasks, return_exceptions=True)

    all_articles: list[ArticleCreate] = []
    for result in results:
        if isinstance(result, Exception):
            logger.warning("Feed task exception: %s", result)
        elif isinstance(result, list):
            all_articles.extend(result)

    # Deduplicate by URL
    seen: set[str] = set()
    unique: list[ArticleCreate] = []
    for a in all_articles:
        if a.source_url not in seen:
            seen.add(a.source_url)
            unique.append(a)

    logger.info("RSS scraper collected %d unique articles", len(unique))
    return unique


# ─────────────────────────────────────────────────────────────────────────────
# Main Ingestion Orchestrator
# ─────────────────────────────────────────────────────────────────────────────

async def run_ingestion(db_session, skip_existing_urls: set[str]) -> int:
    """
    Full ingestion run:
    1. Scrape HN + RSS feeds
    2. De-duplicate against existing DB URLs
    3. Extract full text for each new article
    4. LLM-process each new article
    5. Persist to DB

    Returns count of newly inserted articles.
    """
    from llm_processor import compute_importance_score, process_article
    from models import Article

    inserted = 0
    connector_limits = httpx.Limits(max_connections=20, max_keepalive_connections=10)

    async with httpx.AsyncClient(limits=connector_limits) as client:
        # 1. Collect raw articles
        hn_articles = await scrape_hacker_news(
            client,
            min_score=settings.hn_min_score,
            limit=settings.max_articles_per_run // 2,
        )
        rss_articles = await scrape_rss_feeds(client)

        all_candidates = hn_articles + rss_articles

        # 2. Deduplicate
        new_articles = [a for a in all_candidates if a.source_url not in skip_existing_urls]
        logger.info("Ingestion: %d new articles to process (skipping %d existing)",
                    len(new_articles), len(all_candidates) - len(new_articles))

        # Limit to configured max
        new_articles = new_articles[: settings.max_articles_per_run]

        # 3 + 4 + 5. Process each article
        for article_data in new_articles:
            try:
                # Extract full text
                full_text, text_ok = await extract_full_text(article_data.source_url, client)

                # LLM processing
                llm_result = await process_article(
                    title=article_data.original_title or "",
                    url=article_data.source_url,
                    source_domain=article_data.source_domain or "",
                    body=full_text,
                )

                importance = compute_importance_score(llm_result, hn_score=article_data.hn_score)

                # Build ORM object
                article = Article(
                    source_url=article_data.source_url,
                    source_domain=article_data.source_domain,
                    original_title=article_data.original_title,
                    published_at=article_data.published_at,
                    hn_score=article_data.hn_score,
                    hn_comments=article_data.hn_comments,
                    hn_item_id=article_data.hn_item_id,
                    # LLM fields
                    clean_title=llm_result.clean_title,
                    simple_title=llm_result.simple_title or llm_result.clean_title,
                    category=llm_result.category,
                    tags=json.dumps(llm_result.tags),
                    importance_badge=llm_result.importance_badge,
                    simple_badge=llm_result.simple_badge or llm_result.importance_badge,
                    technical_depth_score=llm_result.technical_depth_score,
                    importance_score=importance,
                    is_daily_briefing=(importance >= 80),
                    plain_english_summary=llm_result.plain_english_summary,
                    jargon_buster=json.dumps(llm_result.jargon_buster) if llm_result.jargon_buster else None,
                    crux_what_it_is=llm_result.crux_what_it_is,
                    crux_why_important=llm_result.crux_why_important,
                    crux_technical_details=json.dumps(llm_result.crux_technical_details),
                    crux_impact_dev=llm_result.crux_impact_dev,
                    crux_impact_world=llm_result.crux_impact_world,
                    # Full text
                    full_text=full_text if text_ok else None,
                    full_text_available=text_ok,
                    llm_processed=True,
                )
                db_session.add(article)
                await db_session.commit()
                await db_session.refresh(article)
                inserted += 1
                logger.info("Inserted article #%d: %s", article.id, llm_result.clean_title[:60])

            except Exception as exc:
                await db_session.rollback()
                logger.error("Failed to process article %s: %s", article_data.source_url[:80], exc)
                continue

    return inserted
