"""
models.py — SQLAlchemy ORM Models + Pydantic v2 Schemas
"""
from __future__ import annotations

import enum
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import Boolean, DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


# ─────────────────────────────────────────────────────────────────────────────
# Enums
# ─────────────────────────────────────────────────────────────────────────────

class Category(str, enum.Enum):
    DAILY_BRIEFING = "daily_briefing"
    REA = "rea"
    BUGS_CVES = "bugs_cves"
    APPLIED_AI = "applied_ai"
    DEV_QOL = "dev_qol"
    ARCHITECTURE = "architecture"


# ─────────────────────────────────────────────────────────────────────────────
# ORM Model
# ─────────────────────────────────────────────────────────────────────────────

class Article(Base):
    __tablename__ = "articles"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)

    # ── Source metadata ───────────────────────────────────────────────────────
    source_url: Mapped[str] = mapped_column(String(2048), unique=True, nullable=False)
    source_domain: Mapped[Optional[str]] = mapped_column(String(256), nullable=True)
    original_title: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    published_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), nullable=True)
    scraped_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )

    # ── LLM-enriched fields ──────────────────────────────────────────────────
    clean_title: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)
    simple_title: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)  # Plain English title for beginners
    category: Mapped[Optional[str]] = mapped_column(String(64), nullable=True)
    tags: Mapped[Optional[str]] = mapped_column(String(512), nullable=True)  # JSON list stored as string
    importance_badge: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)
    simple_badge: Mapped[Optional[str]] = mapped_column(String(128), nullable=True)  # Friendly badge (e.g. "⚠️ Security Risk")
    technical_depth_score: Mapped[int] = mapped_column(Integer, default=5)
    importance_score: Mapped[float] = mapped_column(Float, default=0.0)
    is_daily_briefing: Mapped[bool] = mapped_column(Boolean, default=False)

    # ── Plain English & Jargon Buster ────────────────────────────────────────
    plain_english_summary: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    jargon_buster: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON list of {"term": "...", "meaning": "..."}

    # ── Crux (Stage 2) ───────────────────────────────────────────────────────
    crux_what_it_is: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    crux_why_important: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    crux_technical_details: Mapped[Optional[str]] = mapped_column(Text, nullable=True)  # JSON list
    crux_impact_dev: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    crux_impact_world: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    # ── Full article body (Stage 3) ──────────────────────────────────────────
    full_text: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    full_text_available: Mapped[bool] = mapped_column(Boolean, default=False)

    # ── HN metadata ─────────────────────────────────────────────────────────
    hn_score: Mapped[int] = mapped_column(Integer, default=0)
    hn_comments: Mapped[int] = mapped_column(Integer, default=0)
    hn_item_id: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)

    # ── Bookmarked ───────────────────────────────────────────────────────────
    bookmarked: Mapped[bool] = mapped_column(Boolean, default=False)

    # ── Processing state ──────────────────────────────────────────────────────
    llm_processed: Mapped[bool] = mapped_column(Boolean, default=False)

    def tags_list(self) -> list[str]:
        import json
        if not self.tags:
            return []
        try:
            return json.loads(self.tags)
        except (json.JSONDecodeError, TypeError):
            return [t.strip() for t in self.tags.split(",") if t.strip()]

    def crux_technical_details_list(self) -> list[str]:
        import json
        if not self.crux_technical_details:
            return []
        try:
            return json.loads(self.crux_technical_details)
        except (json.JSONDecodeError, TypeError):
            return [self.crux_technical_details]

    def read_time_crux(self) -> str:
        """Estimated read time for crux view (~300 wpm)."""
        text = " ".join(filter(None, [
            self.crux_what_it_is,
            self.crux_why_important,
            self.crux_impact_dev,
            self.crux_impact_world,
        ]))
        words = len(text.split()) if text else 80
        mins = max(1, round(words / 300))
        return f"{mins}m Crux"

    def read_time_full(self) -> str:
        """Estimated read time for full article (~250 wpm)."""
        if not self.full_text:
            return "~5m Full"
        words = len(self.full_text.split())
        mins = max(1, round(words / 250))
        return f"{mins}m Full Read"

    def display_title(self) -> str:
        return self.clean_title or self.original_title or "Untitled"

    def display_simple_title(self) -> str:
        return self.simple_title or self.clean_title or self.original_title or "Untitled"

    def display_simple_badge(self) -> str:
        return self.simple_badge or self.importance_badge or "📰 Story"

    def jargon_list(self) -> list[dict]:
        import json
        if not self.jargon_buster:
            return []
        try:
            return json.loads(self.jargon_buster)
        except Exception:
            return []

    def category_label(self) -> str:
        labels = {
            "rea": "Reverse Engineering",
            "bugs_cves": "Bugs & CVEs",
            "applied_ai": "Applied AI",
            "dev_qol": "Dev QoL",
            "architecture": "Architecture",
            "daily_briefing": "Daily Briefing",
        }
        return labels.get(self.category or "", self.category or "General")

    def time_ago(self) -> str:
        if not self.published_at:
            return "recently"
        now = datetime.utcnow()
        diff = now - self.published_at.replace(tzinfo=None)
        seconds = int(diff.total_seconds())
        if seconds < 3600:
            mins = max(1, seconds // 60)
            return f"{mins}m ago"
        elif seconds < 86400:
            hrs = seconds // 3600
            return f"{hrs}h ago"
        else:
            days = seconds // 86400
            return f"{days}d ago"


# ─────────────────────────────────────────────────────────────────────────────
# Pydantic Schemas
# ─────────────────────────────────────────────────────────────────────────────

class ArticleBase(BaseModel):
    source_url: str
    original_title: Optional[str] = None
    source_domain: Optional[str] = None
    published_at: Optional[datetime] = None
    hn_score: int = 0
    hn_comments: int = 0
    hn_item_id: Optional[int] = None


class ArticleCreate(ArticleBase):
    pass


class LLMResult(BaseModel):
    """Structured output expected from the LLM processor."""
    clean_title: str = Field(..., description="De-clickbaited technical headline")
    simple_title: Optional[str] = Field(None, description="Plain English headline for beginners (avoid jargon)")
    category: str = Field(..., description="rea|bugs_cves|applied_ai|dev_qol|architecture")
    tags: list[str] = Field(default_factory=list, description="3-4 short tag strings")
    importance_badge: str = Field(..., description="e.g. '🚨 Critical PHP Bug'")
    simple_badge: Optional[str] = Field(None, description="Friendly badge e.g. '⚠️ Major Security Risk'")
    technical_depth_score: int = Field(..., ge=1, le=10)
    is_daily_briefing: bool = False
    plain_english_summary: Optional[str] = Field(None, description="1-2 sentence ELI5 explanation with simple analogy")
    jargon_buster: Optional[list[dict]] = Field(default_factory=list, description="List of {'term': '...', 'meaning': '...'}")
    crux_what_it_is: str = Field(..., description="2-3 sentence technical summary")
    crux_why_important: str = Field(..., description="Catalyst / why engineers care now")
    crux_technical_details: list[str] = Field(..., description="3-4 technical bullets")
    crux_impact_dev: str = Field(..., description="Actionable takeaway for the developer")
    crux_impact_world: str = Field(..., description="Broader industry / ecosystem effect")


class ArticleRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_url: str
    source_domain: Optional[str] = None
    original_title: Optional[str] = None
    clean_title: Optional[str] = None
    category: Optional[str] = None
    tags: Optional[str] = None
    importance_badge: Optional[str] = None
    technical_depth_score: int = 5
    importance_score: float = 0.0
    is_daily_briefing: bool = False
    crux_what_it_is: Optional[str] = None
    crux_why_important: Optional[str] = None
    crux_technical_details: Optional[str] = None
    crux_impact_dev: Optional[str] = None
    crux_impact_world: Optional[str] = None
    full_text: Optional[str] = None
    full_text_available: bool = False
    hn_score: int = 0
    hn_comments: int = 0
    bookmarked: bool = False
    llm_processed: bool = False
    published_at: Optional[datetime] = None
    scraped_at: Optional[datetime] = None
