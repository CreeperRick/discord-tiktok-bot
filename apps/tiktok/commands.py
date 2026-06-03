# bot.py
"""
Entry point for the TikTok Discord bot.

Extension auto-discovery: every package under apps/ that contains any of
  commands.py | monitor.py | automod.py
is loaded as a discord.py cog, provided it exports `async def setup(bot)`.
"""
from __future__ import annotations

import asyncio
import logging
import pkgutil
from pathlib import Path

import discord
from discord.ext import commands

from config import settings
from utils.database import init_db
from utils.logging_conf import setup_logging

logger = setup_logging()

APPS_DIR = Path(__file__).parent / "apps"

# Sub-module filenames we look for inside each app package
DISCOVERABLE_SUBMODULES = ("commands", "monitor", "automod")


class TikTokBot(commands.Bot):
    def __init__(self) -> None:
        # Grant only the privileges this bot actually needs.
        # Intents.all() was the original — that's a security/privacy risk.
        intents = discord.Intents.none()
        intents.guilds = True           # channel access, guild events
        intents.guild_messages = True   # read messages in guilds
        intents.message_content = True  # read message body (privileged)
        intents.members = True          # needed by automod for member events

        super().__init__(
            command_prefix=commands.when_mentioned,  # slash-commands only bot
            intents=intents,
            help_command=None,          # we provide /help via slash commands
        )

    # ── Lifecycle ─────────────────────────────────────────────────────────

    async def setup_hook(self) -> None:
        """
        Runs exactly once before the bot connects.
        All one-time init (DB, extensions, slash sync) belongs here — NOT in
        on_ready, which fires on every reconnect.
        """
        await init_db()
        logger.info("Database initialised")

        await self._load_all_extensions()

        # Sync to your guild instantly (guild syncs are immediate).
        # Switch to `await self.tree.sync()` for global rollout when ready.
        TEST_GUILD = discord.Object(id=1495372441860571187)
        self.tree.copy_global_to(guild=TEST_GUILD)
        synced = await self.tree.sync(guild=TEST_GUILD)
        logger.info("Slash commands synced (%d registered)", len(synced))

    async def close(self) -> None:
        """Graceful shutdown — lets cog background tasks clean up properly."""
        logger.info("Shutting down…")
        await super().close()

    async def on_ready(self) -> None:
        """Fires on every successful (re)connection — keep lightweight."""
        assert self.user is not None
        logger.info("✅  Logged in as %s (ID: %s)", self.user, self.user.id)
        await self.change_presence(
            activity=discord.Game(name="TikTok Lives | /help")
        )

    async def on_error(
        self, event_method: str, /, *args: object, **kwargs: object
    ) -> None:
        """Surface unhandled exceptions from event listeners — never silently swallow."""
        logger.exception("Unhandled error in event '%s'", event_method)

    # ── Extension loading ─────────────────────────────────────────────────

    async def _load_all_extensions(self) -> None:
        """
        Walk every sub-package under apps/ and attempt to load the standard
        sub-modules. Only real packages (with __init__.py) are scanned.
        """
        if not APPS_DIR.is_dir():
            logger.warning("apps/ directory not found — no extensions loaded")
            return

        for pkg in pkgutil.iter_modules([str(APPS_DIR)]):
            if not pkg.ispkg:
                continue  # skip loose .py files at the top of apps/
            for submodule in DISCOVERABLE_SUBMODULES:
                await self._try_load(f"apps.{pkg.name}.{submodule}")

    async def _try_load(self, ext_path: str) -> None:
        """
        Load a single extension, distinguishing between:
          - File doesn't exist   → silently skip (expected)
          - No setup() function  → warn (developer mistake)
          - Any other error      → log full traceback (bug — must be visible)
        """
        try:
            await self.load_extension(ext_path)
            logger.info("Loaded: %s", ext_path)
        except commands.ExtensionNotFound:
            pass  # sub-module simply doesn't exist for this app — fine
        except commands.NoEntryPointError:
            logger.warning("'%s' has no setup() — skipping", ext_path)
        except Exception:
            # Syntax errors, import failures, runtime crashes — always loud
            logger.exception("Failed to load '%s'", ext_path)


# ── Entry point ───────────────────────────────────────────────────────────────

async def main() -> None:
    async with TikTokBot() as bot:
        await bot.start(settings.discord_token)


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Stopped by user (KeyboardInterrupt)")
