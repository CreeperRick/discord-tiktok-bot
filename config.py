# config.py
"""
Central configuration loaded from environment variables / .env file.
All settings are validated by Pydantic on startup — bad config = immediate,
readable error instead of a mysterious crash 30 seconds later.
"""
from __future__ import annotations

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",          # ignore unknown keys in .env
    )

    # ── Discord ───────────────────────────────────────────────────────────
    discord_token: str = Field(..., description="Bot token from Discord Developer Portal")

    # ── Database ──────────────────────────────────────────────────────────
    # SQLite for local dev; swap to postgresql+asyncpg://... for production
    database_url: str = Field(
        default="sqlite+aiosqlite:///./data.db",
        description="SQLAlchemy async-compatible database URL",
    )

    # ── TikTok monitor ────────────────────────────────────────────────────
    tiktok_check_interval: int = Field(
        default=60,
        ge=5,           # never poll faster than every 5 s — avoid IP bans
        description="Seconds between TikTok live/post polling cycles",
    )

    # ── Moderation ────────────────────────────────────────────────────────
    moderation_log_channel_id: int | None = Field(
        default=None,
        description="Discord channel ID for moderation audit logs (optional)",
    )


def _load_settings() -> Settings:
    """
    Load and validate settings, converting Pydantic's ValidationError into a
    human-readable message so operators know exactly which env var is missing.
    """
    try:
        return Settings()
    except Exception as exc:
        raise SystemExit(
            f"\n❌  Configuration error — check your .env file:\n\n{exc}\n"
        ) from exc


settings = _load_settings()
