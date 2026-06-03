# apps/moderation/automod.py
"""
Moderation event listener cog.

Listens for Discord audit events (member joins/leaves, message deletions,
bans/unbans) and logs them to a configurable mod-log channel.

The log channel is set via:
  - Global:    MODERATION_LOG_CHANNEL_ID in .env
  - Per-guild: GuildSettings.mod_log_channel_id in the database (takes priority)
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone

import discord
from discord.ext import commands
from sqlalchemy import select

from config import settings
from utils.database import GuildSettings, get_session

logger = logging.getLogger(__name__)


class ModerationLog(commands.Cog, name="ModerationLog"):
    """Logs moderation events to a designated channel."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ── Helpers ───────────────────────────────────────────────────────────

    async def _get_log_channel(
        self, guild: discord.Guild
    ) -> discord.TextChannel | None:
        """
        Resolve the mod-log channel for a guild.
        Checks DB guild_settings first; falls back to global config.
        """
        channel_id: int | None = None

        async with get_session() as session:
            row = await session.get(GuildSettings, guild.id)
            if row and row.mod_log_channel_id:
                channel_id = row.mod_log_channel_id

        if channel_id is None:
            channel_id = settings.moderation_log_channel_id

        if channel_id is None:
            return None

        channel = self.bot.get_channel(channel_id)
        return channel if isinstance(channel, discord.TextChannel) else None

    async def _send_log(
        self, guild: discord.Guild, embed: discord.Embed
    ) -> None:
        """Send a log embed to the guild's mod-log channel, if configured."""
        channel = await self._get_log_channel(guild)
        if channel is None:
            return
        embed.timestamp = datetime.now(timezone.utc)
        try:
            await channel.send(embed=embed)
        except discord.Forbidden:
            logger.warning(
                "No permission to send mod log in channel %s (guild %s)",
                channel.id,
                guild.id,
            )
        except discord.HTTPException:
            logger.exception("Failed to send mod log for guild %s", guild.id)

    # ── Event listeners ───────────────────────────────────────────────────

    @commands.Cog.listener()
    async def on_member_join(self, member: discord.Member) -> None:
        embed = discord.Embed(
            title="Member Joined",
            description=f"{member.mention} ({member})",
            colour=discord.Colour.green(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.add_field(name="Account created", value=discord.utils.format_dt(member.created_at, "R"))
        embed.set_footer(text=f"ID: {member.id}")
        await self._send_log(member.guild, embed)

    @commands.Cog.listener()
    async def on_member_remove(self, member: discord.Member) -> None:
        embed = discord.Embed(
            title="Member Left",
            description=f"{member.mention} ({member})",
            colour=discord.Colour.red(),
        )
        embed.set_thumbnail(url=member.display_avatar.url)
        embed.set_footer(text=f"ID: {member.id}")
        await self._send_log(member.guild, embed)

    @commands.Cog.listener()
    async def on_member_ban(self, guild: discord.Guild, user: discord.User) -> None:
        embed = discord.Embed(
            title="Member Banned",
            description=f"{user.mention} ({user})",
            colour=discord.Colour.dark_red(),
        )
        embed.set_thumbnail(url=user.display_avatar.url)
        embed.set_footer(text=f"ID: {user.id}")
        await self._send_log(guild, embed)

    @commands.Cog.listener()
    async def on_member_unban(self, guild: discord.Guild, user: discord.User) -> None:
        embed = discord.Embed(
            title="Member Unbanned",
            description=f"{user.mention} ({user})",
            colour=discord.Colour.blue(),
        )
        embed.set_footer(text=f"ID: {user.id}")
        await self._send_log(guild, embed)

    @commands.Cog.listener()
    async def on_message_delete(self, message: discord.Message) -> None:
        # Ignore DMs and bot messages
        if not message.guild or message.author.bot:
            return

        embed = discord.Embed(
            title="Message Deleted",
            description=f"In {message.channel.mention} by {message.author.mention}",
            colour=discord.Colour.orange(),
        )
        if message.content:
            embed.add_field(
                name="Content",
                value=message.content[:1024],
                inline=False,
            )
        embed.set_footer(text=f"Author ID: {message.author.id} | Msg ID: {message.id}")
        await self._send_log(message.guild, embed)

    @commands.Cog.listener()
    async def on_message_edit(
        self, before: discord.Message, after: discord.Message
    ) -> None:
        if not before.guild or before.author.bot:
            return
        if before.content == after.content:
            return  # embed unfurling or pin — not a real edit

        embed = discord.Embed(
            title="Message Edited",
            description=f"In {before.channel.mention} by {before.author.mention}",
            colour=discord.Colour.gold(),
        )
        embed.add_field(name="Before", value=before.content[:512] or "*empty*", inline=False)
        embed.add_field(name="After", value=after.content[:512] or "*empty*", inline=False)
        embed.add_field(name="Jump", value=f"[Go to message]({after.jump_url})", inline=False)
        embed.set_footer(text=f"Author ID: {before.author.id}")
        await self._send_log(before.guild, embed)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(ModerationLog(bot))
