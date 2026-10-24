"""
database.py — SQLAlchemy 2.0 async engine + session factory.
"""
from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase

from pathlib import Path

from config import get_settings

settings = get_settings()

BASE_DIR = Path(__file__).resolve().parent

# Ensure SQLite path is always absolute so it works in any working directory / production container
if "sqlite:///" in settings.database_url:
    db_name = settings.database_url.split("///")[-1].lstrip("./")
    db_file = BASE_DIR / db_name
    _db_url = f"sqlite+aiosqlite:///{db_file}"
else:
    _db_url = settings.database_url

engine = create_async_engine(
    _db_url,
    connect_args={"check_same_thread": False},
    echo=False,
)

AsyncSessionLocal = async_sessionmaker(
    bind=engine,
    class_=AsyncSession,
    expire_on_commit=False,
    autoflush=False,
    autocommit=False,
)


class Base(DeclarativeBase):
    pass


async def init_db() -> None:
    """Create all tables if they don't exist."""
    async with engine.begin() as conn:
        from models import Article  # noqa: F401 – imported for side-effects
        await conn.run_sync(Base.metadata.create_all)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    """FastAPI dependency that yields a database session."""
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
