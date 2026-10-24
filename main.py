"""
main.py — FastAPI application, routes, HTMX endpoints, startup events.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from typing import Optional

from fastapi import Depends, FastAPI, HTTPException, Query, Request
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.templating import Jinja2Templates
from sqlalchemy import or_, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from config import get_settings
from database import get_session, init_db
from models import Article
from seed import seed_database

logger = logging.getLogger(__name__)
settings = get_settings()

# ─────────────────────────────────────────────────────────────────────────────
# App Initialization
# ─────────────────────────────────────────────────────────────────────────────

app = FastAPI(
    title="DevPulse",
    description="High-Signal Tech Intelligence & News Aggregator for Software Engineers",
    version="1.0.0",
)

templates = Jinja2Templates(directory="templates")

# ─────────────────────────────────────────────────────────────────────────────
# Jinja2 Template Filters & Globals
# ─────────────────────────────────────────────────────────────────────────────

def _from_json(value: Optional[str]) -> list:
    if not value:
        return []
    try:
        return json.loads(value)
    except (json.JSONDecodeError, TypeError):
        return []


def _category_label(cat: Optional[str]) -> str:
    labels = {
        "rea": "Reverse Engineering",
        "bugs_cves": "Bugs & CVEs",
        "applied_ai": "Applied AI",
        "dev_qol": "Dev QoL",
        "architecture": "Architecture",
        "daily_briefing": "Daily Briefing",
    }
    return labels.get(cat or "", cat or "General")


def _category_color(cat: Optional[str]) -> str:
    colors = {
        "rea": "red",
        "bugs_cves": "orange",
        "applied_ai": "violet",
        "dev_qol": "teal",
        "architecture": "blue",
        "daily_briefing": "yellow",
    }
    return colors.get(cat or "", "slate")


def _time_ago(dt: Optional[datetime]) -> str:
    if not dt:
        return "recently"
    now = datetime.utcnow()
    diff = now - dt.replace(tzinfo=None)
    seconds = int(diff.total_seconds())
    if seconds < 60:
        return "just now"
    elif seconds < 3600:
        mins = seconds // 60
        return f"{mins}m ago"
    elif seconds < 86400:
        hrs = seconds // 3600
        return f"{hrs}h ago"
    else:
        days = seconds // 86400
        return f"{days}d ago"


def _read_time_crux(article: Article) -> str:
    text = " ".join(filter(None, [
        article.crux_what_it_is,
        article.crux_why_important,
        article.crux_impact_dev,
        article.crux_impact_world,
    ]))
    words = len(text.split()) if text else 80
    mins = max(1, round(words / 300))
    return f"{mins}m Crux"


def _read_time_full(article: Article) -> str:
    if not article.full_text:
        return "~5m Full"
    words = len(article.full_text.split())
    mins = max(1, round(words / 250))
    return f"{mins}m Full Read"


def _display_title(article: Article) -> str:
    return article.clean_title or article.original_title or "Untitled"


def _render_markdown(text: Optional[str]) -> str:
    """
    Render markdown text to HTML for the full article reader.
    Handles code blocks, headers, lists, tables, bold/italic, and links.
    Pure Python implementation — no extra dependency needed.
    """
    if not text:
        return ""
    import re as _re

    lines = text.split("\n")
    html_parts: list[str] = []
    in_code_block = False
    in_list = False
    code_lang = ""
    buffer: list[str] = []

    def flush_paragraph():
        nonlocal in_list
        if buffer:
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            para = " ".join(buffer).strip()
            if para:
                html_parts.append(f"<p>{_inline(para)}</p>")
            buffer.clear()

    def _inline(s: str) -> str:
        # Code spans
        s = _re.sub(r"`([^`]+)`", r'<code>\1</code>', s)
        # Bold
        s = _re.sub(r"\*\*([^*]+)\*\*", r'<strong>\1</strong>', s)
        s = _re.sub(r"__([^_]+)__", r'<strong>\1</strong>', s)
        # Italic
        s = _re.sub(r"\*([^*]+)\*", r'<em>\1</em>', s)
        s = _re.sub(r"_([^_]+)_", r'<em>\1</em>', s)
        # Links
        s = _re.sub(r"\[([^\]]+)\]\(([^)]+)\)", r'<a href="\2" target="_blank" rel="noopener">\1</a>', s)
        return s

    for line in lines:
        # Code block toggle
        if line.startswith("```"):
            if in_code_block:
                html_parts.append("</code></pre>")
                in_code_block = False
                code_lang = ""
            else:
                flush_paragraph()
                code_lang = line[3:].strip() or ""
                lang_class = f' class="language-{code_lang}"' if code_lang else ""
                html_parts.append(f"<pre><code{lang_class}>")
                in_code_block = True
            continue

        if in_code_block:
            # Escape HTML in code blocks
            escaped = line.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
            html_parts.append(escaped + "\n")
            continue

        # Headers
        if line.startswith("#### "):
            flush_paragraph()
            html_parts.append(f"<h3>{_inline(line[5:])}</h3>")
        elif line.startswith("### "):
            flush_paragraph()
            html_parts.append(f"<h3>{_inline(line[4:])}</h3>")
        elif line.startswith("## "):
            flush_paragraph()
            html_parts.append(f"<h2>{_inline(line[3:])}</h2>")
        elif line.startswith("# "):
            flush_paragraph()
            html_parts.append(f"<h1>{_inline(line[2:])}</h1>")
        # Horizontal rule
        elif line.strip() in ("---", "***", "___"):
            flush_paragraph()
            html_parts.append("<hr/>")
        # Unordered list item
        elif _re.match(r"^[\-\*\+]\s", line):
            if buffer:
                para = " ".join(buffer).strip()
                if para:
                    html_parts.append(f"<p>{_inline(para)}</p>")
                buffer.clear()
            if not in_list:
                html_parts.append("<ul>")
                in_list = True
            html_parts.append(f"<li>{_inline(line[2:].strip())}</li>")
        # Numbered list item
        elif _re.match(r"^\d+\.\s", line):
            if buffer:
                para = " ".join(buffer).strip()
                if para:
                    html_parts.append(f"<p>{_inline(para)}</p>")
                buffer.clear()
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            html_parts.append(f"<li>{_inline(_re.sub(r'^\d+\.\s', '', line))}</li>")
        # Blockquote
        elif line.startswith("> "):
            flush_paragraph()
            html_parts.append(f"<blockquote><p>{_inline(line[2:])}</p></blockquote>")
        # Table header separator — skip
        elif _re.match(r"^\|[-:\s|]+\|$", line.strip()):
            pass
        # Table row
        elif line.strip().startswith("|") and line.strip().endswith("|"):
            flush_paragraph()
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            row_html = "".join(f"<td>{_inline(c)}</td>" for c in cells)
            # Check if next is separator → this is header
            html_parts.append(f"<tr>{row_html}</tr>")
        # Empty line → paragraph break
        elif not line.strip():
            flush_paragraph()
        else:
            if in_list:
                html_parts.append("</ul>")
                in_list = False
            buffer.append(line.strip())

    flush_paragraph()
    if in_code_block:
        html_parts.append("</code></pre>")

    result = "\n".join(html_parts)
    # Wrap table rows in a table
    result = _re.sub(r"(<tr>.*?</tr>\n?)+", lambda m: f"<table>{m.group(0)}</table>", result, flags=_re.DOTALL)

    from markupsafe import Markup
    return Markup(result)


templates.env.filters["from_json"] = _from_json
templates.env.filters["category_label"] = _category_label
templates.env.filters["category_color"] = _category_color
templates.env.filters["time_ago"] = _time_ago
templates.env.filters["read_time_crux"] = _read_time_crux
templates.env.filters["read_time_full"] = _read_time_full
templates.env.filters["display_title"] = _display_title
templates.env.filters["render_markdown"] = _render_markdown

# ─────────────────────────────────────────────────────────────────────────────
# Scheduler
# ─────────────────────────────────────────────────────────────────────────────

_scheduler = None
_last_sync: Optional[datetime] = None
_sync_in_progress: bool = False


async def _run_ingestion_job():
    global _last_sync, _sync_in_progress
    if _sync_in_progress:
        logger.info("Ingestion already running, skipping.")
        return
    _sync_in_progress = True
    try:
        from database import AsyncSessionLocal
        from scraper import run_ingestion
        async with AsyncSessionLocal() as session:
            # Get existing URLs to avoid duplicates
            result = await session.execute(select(Article.source_url))
            existing_urls = set(result.scalars().all())
        async with AsyncSessionLocal() as session:
            count = await run_ingestion(session, existing_urls)
        _last_sync = datetime.utcnow()
        logger.info("Background ingestion completed: %d new articles", count)
    except Exception as exc:
        logger.error("Background ingestion failed: %s", exc)
    finally:
        _sync_in_progress = False


def _start_scheduler():
    global _scheduler
    from apscheduler.schedulers.asyncio import AsyncIOScheduler
    _scheduler = AsyncIOScheduler()
    _scheduler.add_job(
        _run_ingestion_job,
        trigger="interval",
        minutes=settings.scrape_interval_minutes,
        id="ingestion",
        replace_existing=True,
        max_instances=1,
    )
    _scheduler.start()
    logger.info("Scheduler started: ingestion every %d minutes", settings.scrape_interval_minutes)


# ─────────────────────────────────────────────────────────────────────────────
# Startup / Shutdown
# ─────────────────────────────────────────────────────────────────────────────

@app.on_event("startup")
async def startup():
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s [%(name)s] %(message)s",
    )
    logger.info("DevPulse starting up…")
    await init_db()
    seeded = await seed_database()
    if seeded:
        logger.info("DB seeded with %d articles.", seeded)
    _start_scheduler()


@app.on_event("shutdown")
async def shutdown():
    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
    logger.info("DevPulse shutting down.")


# ─────────────────────────────────────────────────────────────────────────────
# Query Helpers
# ─────────────────────────────────────────────────────────────────────────────

VALID_CATEGORIES = {"daily_briefing", "rea", "bugs_cves", "applied_ai", "dev_qol", "architecture"}


async def _get_articles(
    session: AsyncSession,
    category: str = "daily_briefing",
    search: Optional[str] = None,
    page: int = 1,
    per_page: int = 20,
) -> list[Article]:
    stmt = select(Article)

    if category == "daily_briefing":
        stmt = stmt.where(Article.is_daily_briefing == True)
    elif category in VALID_CATEGORIES:
        stmt = stmt.where(Article.category == category)

    if search and search.strip():
        q = f"%{search.strip()}%"
        stmt = stmt.where(
            or_(
                Article.clean_title.ilike(q),
                Article.original_title.ilike(q),
                Article.crux_what_it_is.ilike(q),
                Article.tags.ilike(q),
            )
        )

    stmt = (
        stmt.order_by(
            Article.importance_score.desc(),
            Article.published_at.desc().nulls_last(),
            Article.scraped_at.desc(),
        )
        .limit(per_page)
        .offset((page - 1) * per_page)
    )

    result = await session.execute(stmt)
    return result.scalars().all()


# ─────────────────────────────────────────────────────────────────────────────
# Routes
# ─────────────────────────────────────────────────────────────────────────────

@app.get("/", response_class=HTMLResponse)
async def home(
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Main page — renders the full shell with Daily Briefing active."""
    articles = await _get_articles(session, category="daily_briefing")
    return templates.TemplateResponse(
        "index.html",
        {
            "request": request,
            "articles": articles,
            "active_category": "daily_briefing",
            "search_query": "",
            "last_sync": _last_sync,
            "sync_in_progress": _sync_in_progress,
            "llm_enabled": settings.llm_enabled,
        },
    )


@app.get("/feed", response_class=HTMLResponse)
async def feed_partial(
    request: Request,
    category: str = Query("daily_briefing"),
    search: str = Query(""),
    page: int = Query(1, ge=1),
    session: AsyncSession = Depends(get_session),
):
    """
    HTMX partial: returns the feed card grid for a given category.
    Used by tab switches and search without full page reloads.
    """
    if category not in VALID_CATEGORIES:
        category = "daily_briefing"

    articles = await _get_articles(
        session,
        category=category,
        search=search or None,
        page=page,
    )

    return templates.TemplateResponse(
        "partials/feed_cards.html",
        {
            "request": request,
            "articles": articles,
            "active_category": category,
            "search_query": search,
            "page": page,
            "has_more": len(articles) == 20,
        },
    )


@app.get("/article/{article_id}/crux", response_class=HTMLResponse)
async def article_crux(
    article_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """
    HTMX partial: Stage 2 — The 4-Part Crux slide-over drawer.
    """
    result = await session.execute(select(Article).where(Article.id == article_id))
    article = result.scalars().first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    return templates.TemplateResponse(
        "partials/crux_drawer.html",
        {
            "request": request,
            "article": article,
        },
    )


@app.get("/article/{article_id}/full", response_class=HTMLResponse)
async def article_full(
    article_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """
    HTMX partial: Stage 3 — Full distraction-free article reader.
    """
    result = await session.execute(select(Article).where(Article.id == article_id))
    article = result.scalars().first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    return templates.TemplateResponse(
        "partials/full_reader.html",
        {
            "request": request,
            "article": article,
        },
    )


@app.post("/article/{article_id}/bookmark", response_class=HTMLResponse)
async def toggle_bookmark(
    article_id: int,
    request: Request,
    session: AsyncSession = Depends(get_session),
):
    """Toggle bookmark state, return updated bookmark button HTML."""
    result = await session.execute(select(Article).where(Article.id == article_id))
    article = result.scalars().first()
    if not article:
        raise HTTPException(status_code=404, detail="Article not found")

    new_state = not article.bookmarked
    await session.execute(
        update(Article).where(Article.id == article_id).values(bookmarked=new_state)
    )
    await session.commit()

    icon = "★" if new_state else "☆"
    label = "Saved" if new_state else "Bookmark"
    cls = "text-yellow-400" if new_state else "text-slate-400 hover:text-yellow-300"
    return HTMLResponse(
        f'<button hx-post="/article/{article_id}/bookmark" hx-swap="outerHTML" '
        f'class="flex items-center gap-1.5 text-sm {cls} transition-colors cursor-pointer">'
        f'<span>{icon}</span><span>{label}</span></button>'
    )


@app.post("/sync", response_class=HTMLResponse)
async def manual_sync(request: Request):
    """
    Trigger a manual ingestion run. Returns an HTMX-friendly status snippet.
    """
    global _sync_in_progress
    if _sync_in_progress:
        return HTMLResponse(
            '<span class="text-yellow-400 text-sm animate-pulse">⟳ Sync already running…</span>'
        )

    import asyncio
    asyncio.create_task(_run_ingestion_job())

    return HTMLResponse(
        '<span class="text-emerald-400 text-sm animate-pulse" '
        'hx-get="/sync/status" hx-trigger="every 3s" hx-swap="outerHTML">'
        '⟳ Syncing…</span>'
    )


@app.get("/sync/status", response_class=HTMLResponse)
async def sync_status():
    """Poll sync status for the "Syncing…" spinner."""
    if _sync_in_progress:
        return HTMLResponse(
            '<span class="text-emerald-400 text-sm animate-pulse" '
            'hx-get="/sync/status" hx-trigger="every 3s" hx-swap="outerHTML">'
            '⟳ Syncing…</span>'
        )
    sync_str = _last_sync.strftime("%H:%M") if _last_sync else "never"
    return HTMLResponse(
        f'<span class="text-slate-500 text-sm">Last sync: {sync_str}</span>'
    )


@app.get("/api/stats", response_class=JSONResponse)
async def api_stats(session: AsyncSession = Depends(get_session)):
    """Quick DB stats for health checking."""
    from sqlalchemy import func
    total_result = await session.execute(select(func.count(Article.id)))
    total = total_result.scalar_one()
    briefing_result = await session.execute(
        select(func.count(Article.id)).where(Article.is_daily_briefing == True)
    )
    briefing = briefing_result.scalar_one()
    return {
        "total_articles": total,
        "daily_briefing_count": briefing,
        "last_sync": _last_sync.isoformat() if _last_sync else None,
        "sync_in_progress": _sync_in_progress,
        "llm_enabled": settings.llm_enabled,
    }


# ─────────────────────────────────────────────────────────────────────────────
# Dev server entry point
# ─────────────────────────────────────────────────────────────────────────────

if __name__ == "__main__":
    import uvicorn
    import os
    port = int(os.environ.get("PORT", settings.app_port))
    uvicorn.run(
        "main:app",
        host=settings.app_host,
        port=port,
        reload=settings.app_debug,
        log_level="info",
    )
