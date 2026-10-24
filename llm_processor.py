"""
llm_processor.py — LLM API client with structured JSON prompt & fallback parser.

Supports: openai | anthropic | gemini | openai_compatible
Falls back to heuristic classification when no API key is configured.
"""
from __future__ import annotations

import json
import logging
import re
from typing import Optional

import httpx

from config import get_settings
from models import LLMResult

logger = logging.getLogger(__name__)
settings = get_settings()

# ─────────────────────────────────────────────────────────────────────────────
# Prompt Construction
# ─────────────────────────────────────────────────────────────────────────────

SYSTEM_PROMPT = """You are a senior staff engineer and security researcher who curates
high-signal tech news for software engineers. You are rigorous, technical, and allergic
to marketing fluff. Your job is to analyze article content and return a structured JSON
analysis. Be precise, technical, and concise. Never fabricate details — if information
is not present, say so clearly."""

def build_user_prompt(title: str, url: str, source_domain: str, body: str) -> str:
    body_preview = body[:4000] if body else "(no content extracted)"
    return f"""Analyze this tech article and return ONLY a valid JSON object matching the schema below.

## Article Metadata
- Title: {title}
- URL: {url}
- Source: {source_domain}

## Article Body (first 4000 chars)
{body_preview}

## Required JSON Schema
Return exactly this structure, no markdown, no explanation, just raw JSON:
{{
  "clean_title": "De-clickbaited, factual technical headline (max 100 chars)",
  "simple_title": "Clear, friendly headline in plain English that any beginner can instantly understand",
  "category": "one of: rea | bugs_cves | applied_ai | dev_qol | architecture",
  "tags": ["tag1", "tag2", "tag3"],
  "importance_badge": "emoji + short badge e.g. '🚨 Critical CVE' or '🛠️ CLI Tool' or '🔥 HN 420 pts'",
  "simple_badge": "Friendly badge e.g. '⚠️ Major Security Risk' or '🛠️ Handy Tool' or '💡 AI Tool'",
  "technical_depth_score": 7,
  "is_daily_briefing": false,
  "plain_english_summary": "1-2 sentence simple explanation with a friendly real-world analogy for beginners",
  "jargon_buster": [
    {{"term": "Scary Term or Acronym", "meaning": "Simple, friendly explanation of what it actually means"}}
  ],
  "crux_what_it_is": "2-3 sentence technical summary of the core news, bug, or tool",
  "crux_why_important": "Why engineers are talking about this right now — the catalyst",
  "crux_technical_details": [
    "Technical detail bullet 1",
    "Technical detail bullet 2",
    "Technical detail bullet 3"
  ],
  "crux_impact_dev": "Direct, actionable takeaway: what to patch, adopt, or avoid",
  "crux_impact_world": "Broader effect on the tech ecosystem or industry"
}}

## Classification Guide
- rea: binary exploitation, firmware, malware analysis, decompilation, hardware hacking
- bugs_cves: language bugs, CVEs, memory bugs, cloud outage post-mortems
- applied_ai: coding agents, local LLMs, RAG pipelines, AI dev tools (NO hype pieces)
- dev_qol: CLI tools, dotfiles, IDE extensions, productivity open-source tools
- architecture: database scaling, compiler tech, engineering deep-dives, OS design

## Scoring Rules
- technical_depth_score: 1=marketing fluff, 5=basic overview, 10=deep technical analysis
- is_daily_briefing: true ONLY if technical_depth_score >= 8 AND the story is highly impactful"""


# ─────────────────────────────────────────────────────────────────────────────
# Provider Clients
# ─────────────────────────────────────────────────────────────────────────────

async def _call_openai(prompt: str, system: str, base_url: Optional[str] = None) -> str:
    """Call OpenAI or any OpenAI-compatible endpoint."""
    url = (base_url or "https://api.openai.com/v1").rstrip("/") + "/chat/completions"
    headers = {
        "Authorization": f"Bearer {settings.llm_api_key}",
        "Content-Type": "application/json",
    }
    payload = {
        "model": settings.llm_model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": prompt},
        ],
        "temperature": 0.2,
        "response_format": {"type": "json_object"},
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]


async def _call_anthropic(prompt: str, system: str) -> str:
    """Call Anthropic Claude API."""
    headers = {
        "x-api-key": settings.llm_api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json",
    }
    payload = {
        "model": settings.llm_model,
        "max_tokens": 1500,
        "system": system,
        "messages": [{"role": "user", "content": prompt}],
        "temperature": 0.2,
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(
            "https://api.anthropic.com/v1/messages",
            headers=headers,
            json=payload,
        )
        resp.raise_for_status()
        data = resp.json()
        return data["content"][0]["text"]


async def _call_gemini(prompt: str, system: str) -> str:
    """Call Google Gemini API."""
    model = settings.llm_model or "gemini-1.5-flash"
    url = (
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
        f"?key={settings.llm_api_key}"
    )
    payload = {
        "contents": [
            {"role": "user", "parts": [{"text": f"{system}\n\n{prompt}"}]}
        ],
        "generationConfig": {
            "temperature": 0.2,
            "responseMimeType": "application/json",
        },
    }
    async with httpx.AsyncClient(timeout=60.0) as client:
        resp = await client.post(url, json=payload)
        resp.raise_for_status()
        data = resp.json()
        return data["candidates"][0]["content"]["parts"][0]["text"]


# ─────────────────────────────────────────────────────────────────────────────
# JSON Parser with Fallback
# ─────────────────────────────────────────────────────────────────────────────

def _parse_json_response(raw: str) -> dict:
    """Parse LLM JSON response, stripping markdown fences if present."""
    # Strip ```json ... ``` wrappers
    cleaned = re.sub(r"^```(?:json)?\s*", "", raw.strip(), flags=re.MULTILINE)
    cleaned = re.sub(r"\s*```$", "", cleaned.strip(), flags=re.MULTILINE)
    return json.loads(cleaned.strip())


# ─────────────────────────────────────────────────────────────────────────────
# Heuristic Fallback (no API key)
# ─────────────────────────────────────────────────────────────────────────────

def _heuristic_classify(title: str, url: str, body: str) -> LLMResult:
    """
    Rule-based classifier used when no LLM API key is configured.
    Returns a plausible LLMResult based on keywords.
    """
    title_lower = (title or "").lower()
    body_lower = (body or "")[:2000].lower()
    combined = title_lower + " " + body_lower

    # Category detection
    rea_keywords = ["exploit", "reverse engineer", "firmware", "malware", "binary", "rop", "shellcode",
                    "decompil", "disassembl", "fuzzing", "heap spray", "buffer overflow", "asm", "ghidra"]
    bug_keywords = ["cve", "vulnerability", "rce", "zero-day", "patch", "bug", "memory leak",
                    "segfault", "injection", "xss", "sql injection", "post-mortem", "outage", "incident"]
    ai_keywords = ["llm", "gpt", "claude", "gemini", "copilot", "agent", "rag", "embedding",
                   "fine-tun", "inference", "vector", "prompt engineering", "local model"]
    qol_keywords = ["cli", "terminal", "dotfiles", "plugin", "extension", "zsh", "bash", "vim",
                    "neovim", "vscode", "tmux", "tool", "utility", "workflow", "productivity"]
    arch_keywords = ["architecture", "database", "scaling", "distributed", "compiler", "kernel",
                     "performance", "benchmark", "postgres", "redis", "kafka", "rust", "go ", "open source"]

    def score(kws: list[str]) -> int:
        return sum(1 for k in kws if k in combined)

    scores = {
        "rea": score(rea_keywords),
        "bugs_cves": score(bug_keywords),
        "applied_ai": score(ai_keywords),
        "dev_qol": score(qol_keywords),
        "architecture": score(arch_keywords),
    }
    category = max(scores, key=lambda k: scores[k]) if max(scores.values()) > 0 else "architecture"

    # Depth score heuristic
    depth = 5
    if any(k in combined for k in ["cvss", "cve-", "rce", "zero-day", "exploit"]):
        depth = 8
    elif any(k in combined for k in ["deep dive", "internals", "how it works", "under the hood"]):
        depth = 9
    elif any(k in combined for k in ["tutorial", "beginners", "intro to"]):
        depth = 3

    # Importance badge
    if "cve" in combined or "zero-day" in combined:
        badge = "🚨 Critical CVE"
    elif "exploit" in combined or "rce" in combined:
        badge = "💀 RCE / Exploit"
    elif "llm" in combined or "agent" in combined:
        badge = "🤖 AI Dev Tool"
    elif "cli" in combined or "tool" in combined:
        badge = "🛠️ Dev Tool"
    elif "performance" in combined or "benchmark" in combined:
        badge = "⚡ Perf Benchmark"
    else:
        badge = "📰 Tech Story"

    # Friendly simple badge
    if "cve" in combined or "zero-day" in combined or "rce" in combined:
        simple_badge = "🚨 Major Security Issue"
    elif "agent" in combined or "llm" in combined:
        simple_badge = "🤖 Helpful AI Tool"
    elif "cli" in combined or "tool" in combined:
        simple_badge = "🛠️ Useful Dev Tool"
    elif "performance" in combined or "database" in combined or "scaling" in combined:
        simple_badge = "⚡ Speed & Scale"
    else:
        simple_badge = "💡 Important Tech News"

    # Friendly simple title (de-jargonized)
    simple_t = title[:90]
    for scary, easy in [
        ("Remote Code Execution", "Hacking Risk"),
        ("Use-After-Free", "Memory Bug"),
        ("Privilege Escalation", "Security Bypass"),
        ("Sigreturn-Oriented Programming", "System Trick"),
        ("Bootkit", "Hardware Malware"),
        ("Soundness Hole", "Safety Bug"),
    ]:
        simple_t = simple_t.replace(scary, easy)

    is_briefing = depth >= 8

    # Generate basic crux from title / body snippet
    first_para = body[:500].strip() if body else title
    sentences = [s.strip() for s in re.split(r'[.!?]', first_para) if len(s.strip()) > 20][:3]
    what_it_is = ". ".join(sentences) + "." if sentences else f"{title}. This story covers a significant development in the {category.replace('_', ' ')} space."

    # Jargon Buster
    jargon = []
    if "cve" in combined:
        jargon.append({"term": "CVE", "meaning": "A unique catalog number assigned to a known security bug."})
    if "rce" in combined:
        jargon.append({"term": "RCE", "meaning": "Remote Code Execution: when an attacker can run commands on your machine over the internet."})
    if "llm" in combined or "agent" in combined:
        jargon.append({"term": "LLM / Agent", "meaning": "Artificial Intelligence software trained to understand instructions and write code."})
    if "cli" in combined:
        jargon.append({"term": "CLI", "meaning": "Command Line Interface: typing text commands in your terminal."})

    return LLMResult(
        clean_title=title[:100],
        simple_title=simple_t,
        category=category,
        tags=_extract_tags(combined),
        importance_badge=badge,
        simple_badge=simple_badge,
        technical_depth_score=depth,
        is_daily_briefing=is_briefing,
        plain_english_summary=f"In simple terms: this update affects how software operates in the {category.replace('_', ' ')} world. It matters because developers need to ensure their systems remain secure and fast.",
        jargon_buster=jargon,
        crux_what_it_is=what_it_is,
        crux_why_important=f"This topic is gaining attention among software engineers and security researchers due to its direct impact on widely-used systems and workflows.",
        crux_technical_details=[
            f"Affects systems and codebases in the {category.replace('_', ' ')} domain.",
            "Engineers should review the linked source for full technical context.",
            "Community discussion is active on Hacker News and related forums.",
        ],
        crux_impact_dev="Review the full article and linked resources to determine if immediate action is required for your stack.",
        crux_impact_world="This development is likely to influence tooling, security practices, or architectural decisions across the industry.",
    )


def _extract_tags(text: str) -> list[str]:
    """Extract likely tech tags from combined text."""
    tag_map = {
        "python": "#Python", "rust": "#Rust", "go ": "#Go", "javascript": "#JS",
        "typescript": "#TypeScript", "php": "#PHP", "linux": "#Linux", "docker": "#Docker",
        "kubernetes": "#Kubernetes", "wasm": "#WASM", "llm": "#LLM", "cve": "#CVE",
        "rce": "#RCE", "cli": "#CLI", "postgres": "#PostgreSQL", "redis": "#Redis",
        "sqlite": "#SQLite", "compiler": "#Compiler", "kernel": "#Kernel",
        "fuzzing": "#Fuzzing", "exploit": "#Exploit", "malware": "#Malware",
        "agent": "#Agent", "rag": "#RAG", "neovim": "#Neovim", "zsh": "#ZSH",
        "github": "#GitHub", "open source": "#OpenSource", "c++": "#CPP",
    }
    found = [v for k, v in tag_map.items() if k in text.lower()]
    return found[:4] if found else ["#Tech", "#Engineering"]


# ─────────────────────────────────────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────────────────────────────────────

async def process_article(
    title: str,
    url: str,
    source_domain: str,
    body: str,
) -> LLMResult:
    """
    Main entry point. Calls the configured LLM provider, or falls back to
    heuristic classification if no API key is available.
    """
    if not settings.llm_enabled:
        logger.info("LLM disabled (no API key) — using heuristic classifier for: %s", title[:60])
        return _heuristic_classify(title, url, body)

    prompt = build_user_prompt(title, url, source_domain, body)
    raw_response = ""

    try:
        provider = settings.llm_provider
        if provider == "openai":
            raw_response = await _call_openai(prompt, SYSTEM_PROMPT)
        elif provider == "openai_compatible":
            raw_response = await _call_openai(prompt, SYSTEM_PROMPT, base_url=settings.llm_base_url)
        elif provider == "anthropic":
            raw_response = await _call_anthropic(prompt, SYSTEM_PROMPT)
        elif provider == "gemini":
            raw_response = await _call_gemini(prompt, SYSTEM_PROMPT)
        else:
            raise ValueError(f"Unknown provider: {provider}")

        data = _parse_json_response(raw_response)

        # Validate & coerce tags + details lists
        if isinstance(data.get("tags"), str):
            data["tags"] = [t.strip() for t in data["tags"].split(",")]
        if isinstance(data.get("crux_technical_details"), str):
            data["crux_technical_details"] = [data["crux_technical_details"]]

        return LLMResult(**data)

    except Exception as exc:
        logger.warning("LLM call failed (%s): %s — falling back to heuristic", type(exc).__name__, exc)
        return _heuristic_classify(title, url, body)


def compute_importance_score(result: LLMResult, hn_score: int = 0) -> float:
    """
    Compute a numeric importance score (0–100) used to gate Daily Briefing inclusion.
    """
    score = 0.0

    # Technical depth (max 40 pts)
    score += result.technical_depth_score * 4.0

    # HN community signal (max 30 pts)
    if hn_score >= 500:
        score += 30
    elif hn_score >= 200:
        score += 20
    elif hn_score >= 100:
        score += 10
    elif hn_score >= 50:
        score += 5

    # Security signal (max 20 pts)
    badge_lower = result.importance_badge.lower()
    body_combined = " ".join([
        result.crux_what_it_is,
        result.crux_why_important,
        " ".join(result.crux_technical_details),
    ]).lower()

    if any(k in badge_lower or k in body_combined for k in ["zero-day", "rce", "critical cve", "cvss 9", "cvss 10"]):
        score += 20
    elif any(k in badge_lower or k in body_combined for k in ["cve", "exploit", "vulnerability", "critical"]):
        score += 12

    # Daily briefing LLM verdict (bonus 10 pts)
    if result.is_daily_briefing:
        score += 10

    return min(score, 100.0)
