# utils/database.py
"""
Async database layer using SQLAlchemy 2.x with aiosqlite (dev) or asyncpg (prod).

Tables
------
tiktok_subscriptions  — guild → TikTok accounts to monitor
tiktok_seen_posts     — deduplication cache for posts already announced
guild_settings        — per-guild configuration (log channel, etc.)

Usage
-----
    from utils.database import get_session, TikTokSubscription

    async with get_session() as session:
        subs = await session.scalars(select(TikTokSubscription))
"""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from typing import AsyncIterator

from sqlalchemy import BigInteger, Boolean, DateTime, Integer, String, Text
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column

from config import settings

logger = logging.getLogger(__name__)

# ── Engine & session factory ──────────────────────────────────────────────────

# echo=False in production; set to True temporarily when debugging SQL
_engine = create_async_engine(
    settings.database_url,
    echo=False,
    # Pool settings only matter for PostgreSQL; SQLite ignores them
    pool_pre_ping=True,     # detect stale connections before using them
    pool_recycle=1800,      # recycle connections every 30 minutes
)

_AsyncSessionLocal = async_sessionmaker(
    _engine,
    class_=AsyncSession,
    expire_on_commit=False,  # keep attributes accessible after commit
)


# ── ORM base ─────────────────────────────────────────────────────────────────

class Base(DeclarativeBase):
    pass


# ── Models ────────────────────────────────────────────────────────────────────

class TikTokSubscription(Base):
    """
    One row per (guild, tiktok_username) pair.
    The bot monitors each username and posts alerts to notify_channel_id.
    """
    __tablename__ = "tiktok_subscriptions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    tiktok_username: Mapped[str] = mapped_column(String(64), nullable=False)
    notify_channel_id: Mapped[int] = mapped_column(BigInteger, nullable=False)
    # Whether to announce new posts (videos/photos) — distinct from live alerts
    announce_posts: Mapped[bool] = mapped_column(Boolean, default=True)
    # Whether to announce when the user goes live
    announce_live: Mapped[bool] = mapped_column(Boolean, default=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


class TikTokSeenPost(Base):
    """
    Tracks post IDs we have already announced so we never double-post.
    Should be periodically pruned (keep last N per username).
    """
    __tablename__ = "tiktok_seen_posts"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    guild_id: Mapped[int] = mapped_column(BigInteger, nullable=False, index=True)
    tiktok_username: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    post_id: Mapped[str] = mapped_column(String(128), nullable=False)
    seen_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
    )


class GuildSettings(Base):
    """Per-guild configuration overrides."""
    __tablename__ = "guild_settings"

    guild_id: Mapped[int] = mapped_column(BigInteger, primary_key=True)
    # Override global tiktok_check_interval for this guild (seconds)
    check_interval: Mapped[int | None] = mapped_column(Integer, nullable=True)
    # Channel to send moderation audit log messages
    mod_log_channel_id: Mapped[int | None] = mapped_column(BigInteger, nullable=True)
    # Arbitrary JSON config stored as text (future-proofing)
    extra_config: Mapped[str | None] = mapped_column(Text, nullable=True)


# ── Public helpers ────────────────────────────────────────────────────────────

async def init_db() -> None:
    """
    Create all tables that don't yet exist.
    Safe to call on every startup — uses CREATE TABLE IF NOT EXISTS internally.
    For production migrations, use Alembic instead of relying on this.
    """
    async with _engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    logger.debug("Database tables ensured")


@asynccontextmanager
async def get_session() -> AsyncIterator[AsyncSession]:
    """
    Async context manager that yields a SQLAlchemy session.

    Automatically commits on success, rolls back on exception.

    Usage:
        async with get_session() as session:
            session.add(my_object)
            # commit happens automatically on exit
    """
    async with _AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
