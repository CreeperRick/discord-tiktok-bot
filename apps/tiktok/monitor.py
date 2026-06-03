# apps/tiktok/monitor.py
"""
Background cog that polls TikTok for new posts and live streams.

Design decisions:
- Uses yt-dlp (already a dependency) to fetch metadata without a TikTok API key.
- Runs one asyncio task per bot restart; gracefully cancels on shutdown.
- Each poll checks all subscriptions and announces only NEW content.
- Seen post IDs are stored in the DB to survive restarts.

Pitfall: yt-dlp network calls are blocking — we run them in an executor so
         the Discord event loop is never blocked.
"""
from __future__ import annotations

import asyncio
import logging
from concurrent.futures import ThreadPoolExecutor
from functools import partial

import discord
import yt_dlp
from discord.ext import commands, tasks
from sqlalchemy import select

from config import settings
from utils import embeds
from utils.database import TikTokSeenPost, TikTokSubscription, get_session

logger = logging.getLogger(__name__)

# Thread pool for yt-dlp blocking calls (1 worker to avoid hammering TikTok)
_EXECUTOR = ThreadPoolExecutor(max_workers=1, thread_name_prefix="yt-dlp")

# yt-dlp options: metadata only, no actual download
_YDL_OPTS = {
    "quiet": True,
    "no_warnings": True,
    "extract_flat": "in_playlist",     # fast — gets list without downloading
    "skip_download": True,
    "playlistend": 5,                   # only check the 5 most recent posts
}


def _fetch_user_info(username: str) -> dict | None:
    """
    Blocking: fetch recent post metadata for a TikTok user via yt-dlp.
    Returns the info_dict or None on any error.
    """
    url = f"https://www.tiktok.com/@{username}"
    try:
        with yt_dlp.YoutubeDL(_YDL_OPTS) as ydl:
            return ydl.extract_info(url, download=False)
    except yt_dlp.utils.DownloadError as exc:
        logger.warning("yt-dlp error for @%s: %s", username, exc)
        return None
    except Exception:
        logger.exception("Unexpected error fetching @%s", username)
        return None


class TikTokMonitor(commands.Cog, name="TikTokMonitor"):
    """Polls TikTok accounts and announces new content to configured channels."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot
        self._poll_loop.change_interval(seconds=settings.tiktok_check_interval)
        self._poll_loop.start()

    def cog_unload(self) -> None:
        """Called when the cog is unloaded — cancel the background task cleanly."""
        self._poll_loop.cancel()

    # ── Background task ───────────────────────────────────────────────────

    @tasks.loop(seconds=60)  # overridden in __init__ from settings
    async def _poll_loop(self) -> None:
        """Main polling loop — runs every `tiktok_check_interval` seconds."""
        async with get_session() as session:
            subscriptions = list(
                await session.scalars(select(TikTokSubscription))
            )

        if not subscriptions:
            return  # nothing to check

        logger.debug("Polling %d TikTok subscription(s)…", len(subscriptions))

        # Gather all usernames (unique) to avoid redundant network calls
        seen_usernames: dict[str, dict | None] = {}
        for sub in subscriptions:
            if sub.tiktok_username not in seen_usernames:
                info = await self._fetch_async(sub.tiktok_username)
                seen_usernames[sub.tiktok_username] = info

        for sub in subscriptions:
            info = seen_usernames.get(sub.tiktok_username)
            if not info:
                continue
            await self._process_subscription(sub, info)

    @_poll_loop.before_loop
    async def _before_poll(self) -> None:
        """Wait until the bot is fully connected before polling starts."""
        await self.bot.wait_until_ready()

    @_poll_loop.error
    async def _poll_error(self, error: BaseException) -> None:
        """Log poll errors but keep the loop running — one bad cycle ≠ crash."""
        logger.exception("Error in TikTok poll loop: %s", error)

    # ── Helpers ───────────────────────────────────────────────────────────

    async def _fetch_async(self, username: str) -> dict | None:
        """Run the blocking yt-dlp call in the thread pool executor."""
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(
            _EXECUTOR,
            partial(_fetch_user_info, username),
        )

    async def _process_subscription(
        self, sub: TikTokSubscription, info: dict
    ) -> None:
        """
        Compare fetched posts against the seen-posts table and announce new ones.
        """
        entries = info.get("entries") or []

        for entry in entries:
            post_id = str(entry.get("id", ""))
            if not post_id:
                continue

            # Check if we've already announced this post for this guild
            async with get_session() as session:
                already_seen = await session.scalar(
                    select(TikTokSeenPost).where(
                        TikTokSeenPost.guild_id == sub.guild_id,
                        TikTokSeenPost.tiktok_username == sub.tiktok_username,
                        TikTokSeenPost.post_id == post_id,
                    )
                )
                if already_seen:
                    continue

                # Mark as seen before announcing (prevents double-post on error)
                session.add(
                    TikTokSeenPost(
                        guild_id=sub.guild_id,
                        tiktok_username=sub.tiktok_username,
                        post_id=post_id,
                    )
                )

            if not sub.announce_posts:
                continue

            await self._announce_post(sub, entry)

    async def _announce_post(self, sub: TikTokSubscription, entry: dict) -> None:
        """Send a new-post embed to the subscription's notification channel."""
        channel = self.bot.get_channel(sub.notify_channel_id)
        if not isinstance(channel, discord.TextChannel):
            logger.warning(
                "Channel %s for guild %s not found or not a text channel",
                sub.notify_channel_id,
                sub.guild_id,
            )
            return

        post_url = entry.get("url") or f"https://www.tiktok.com/@{sub.tiktok_username}"
        description = entry.get("description") or entry.get("title") or ""
        thumbnail = entry.get("thumbnail")

        embed = embeds.tiktok_post(
            username=sub.tiktok_username,
            post_url=post_url,
            description=description,
            thumbnail_url=thumbnail,
        )

        try:
            await channel.send(embed=embed)
            logger.info(
                "Announced post %s from @%s in guild %s",
                entry.get("id"),
                sub.tiktok_username,
                sub.guild_id,
            )
        except discord.Forbidden:
            logger.error(
                "Missing permissions to send in channel %s (guild %s)",
                sub.notify_channel_id,
                sub.guild_id,
            )
        except discord.HTTPException:
            logger.exception(
                "HTTP error announcing post for guild %s", sub.guild_id
            )


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TikTokMonitor(bot))
