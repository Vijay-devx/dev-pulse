"""
config.py — Environment & Settings Management
Loads from .env file with sensible defaults.
"""
from __future__ import annotations

import os
from functools import lru_cache
from pathlib import Path

from pydantic import field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=Path(__file__).parent / ".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # ── App ──────────────────────────────────────────────────
    app_name: str = "DevPulse"
    app_host: str = "0.0.0.0"
    app_port: int = 8000
    app_debug: bool = False

    # ── Database ─────────────────────────────────────────────
    database_url: str = "sqlite:///./devpulse.db"

    # ── LLM ──────────────────────────────────────────────────
    llm_provider: str = "openai"          # openai | anthropic | gemini | openai_compatible
    llm_api_key: str = ""
    llm_model: str = "gpt-4o-mini"
    llm_base_url: str = ""                # for openai_compatible endpoints

    # ── Scraper ───────────────────────────────────────────────
    scrape_interval_minutes: int = 60
    hn_min_score: int = 100
    max_articles_per_run: int = 50

    @field_validator("llm_provider")
    @classmethod
    def validate_provider(cls, v: str) -> str:
        allowed = {"openai", "anthropic", "gemini", "openai_compatible"}
        if v not in allowed:
            raise ValueError(f"llm_provider must be one of {allowed}, got '{v}'")
        return v

    @property
    def llm_enabled(self) -> bool:
        """Return True only if a real API key is configured."""
        return bool(self.llm_api_key and self.llm_api_key not in ("", "your_api_key_here"))


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    return Settings()
