# apps/tiktok/commands.py
"""
Slash commands for managing TikTok subscriptions.

/tiktok add <username> [channel]   — subscribe to a TikTok account
/tiktok remove <username>          — unsubscribe
/tiktok list                       — show all subscriptions in this guild
/help                              — show bot help
"""
from __future__ import annotations

import logging

import discord
from discord import app_commands
from discord.ext import commands
from sqlalchemy import delete, select

from utils.database import TikTokSubscription, get_session
from utils import embeds

logger = logging.getLogger(__name__)


class TikTokCommands(commands.Cog, name="TikTok"):
    """Manage which TikTok accounts are monitored in this server."""

    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    # ── /tiktok group ─────────────────────────────────────────────────────

    tiktok_group = app_commands.Group(
        name="tiktok",
        description="Manage TikTok account monitoring",
        default_permissions=discord.Permissions(manage_guild=True),
    )

    @tiktok_group.command(name="add", description="Subscribe to a TikTok account")
    @app_commands.describe(
        username="TikTok username (without @)",
        channel="Channel to send notifications in (defaults to current channel)",
        announce_posts="Announce new posts?",
        announce_live="Announce when user goes live?",
    )
    async def tiktok_add(
        self,
        interaction: discord.Interaction,
        username: str,
        channel: discord.TextChannel | None = None,
        announce_posts: bool = True,
        announce_live: bool = True,
    ) -> None:
        await interaction.response.defer(ephemeral=True)

        notify_channel = channel or interaction.channel
        assert interaction.guild is not None
        assert isinstance(notify_channel, discord.TextChannel)

        username = username.lstrip("@").strip().lower()
        if not username:
            await interaction.followup.send(
                embed=embeds.error("Invalid username", "Username cannot be empty."),
                ephemeral=True,
            )
            return

        async with get_session() as session:
            # Check for duplicate
            existing = await session.scalar(
                select(TikTokSubscription).where(
                    TikTokSubscription.guild_id == interaction.guild.id,
                    TikTokSubscription.tiktok_username == username,
                )
            )
            if existing:
                await interaction.followup.send(
                    embed=embeds.warning(
                        "Already subscribed",
                        f"@{username} is already being monitored in <#{existing.notify_channel_id}>.",
                    ),
                    ephemeral=True,
                )
                return

            session.add(
                TikTokSubscription(
                    guild_id=interaction.guild.id,
                    tiktok_username=username,
                    notify_channel_id=notify_channel.id,
                    announce_posts=announce_posts,
                    announce_live=announce_live,
                )
            )

        logger.info(
            "Guild %s subscribed to @%s → #%s",
            interaction.guild.id,
            username,
            notify_channel.name,
        )
        await interaction.followup.send(
            embed=embeds.success(
                "Subscription added",
                f"Now monitoring **@{username}** and posting alerts in {notify_channel.mention}.",
            ),
            ephemeral=True,
        )

    @tiktok_group.command(name="remove", description="Stop monitoring a TikTok account")
    @app_commands.describe(username="TikTok username (without @)")
    async def tiktok_remove(
        self,
        interaction: discord.Interaction,
        username: str,
    ) -> None:
        await interaction.response.defer(ephemeral=True)
        assert interaction.guild is not None

        username = username.lstrip("@").strip().lower()

        async with get_session() as session:
            result = await session.execute(
                delete(TikTokSubscription).where(
                    TikTokSubscription.guild_id == interaction.guild.id,
                    TikTokSubscription.tiktok_username == username,
                )
            )

        if result.rowcount == 0:
            await interaction.followup.send(
                embed=embeds.error("Not found", f"No subscription for @{username} in this server."),
                ephemeral=True,
            )
            return

        logger.info("Guild %s unsubscribed from @%s", interaction.guild.id, username)
        await interaction.followup.send(
            embed=embeds.success("Unsubscribed", f"Stopped monitoring **@{username}**."),
            ephemeral=True,
        )

    @tiktok_group.command(name="list", description="List all monitored TikTok accounts")
    async def tiktok_list(self, interaction: discord.Interaction) -> None:
        await interaction.response.defer(ephemeral=True)
        assert interaction.guild is not None

        async with get_session() as session:
            rows = list(
                await session.scalars(
                    select(TikTokSubscription).where(
                        TikTokSubscription.guild_id == interaction.guild.id
                    )
                )
            )

        if not rows:
            await interaction.followup.send(
                embed=embeds.info("No subscriptions", "Use `/tiktok add` to start monitoring an account."),
                ephemeral=True,
            )
            return

        lines = [
            f"**@{row.tiktok_username}** → <#{row.notify_channel_id}> "
            f"(posts: {'✅' if row.announce_posts else '❌'}  live: {'✅' if row.announce_live else '❌'})"
            for row in rows
        ]
        embed = embeds.info(
            f"Monitored TikTok accounts ({len(rows)})",
            "\n".join(lines),
        )
        await interaction.followup.send(embed=embed, ephemeral=True)

    # ── /help ─────────────────────────────────────────────────────────────

    @app_commands.command(name="help", description="Show bot commands and usage")
    async def help_command(self, interaction: discord.Interaction) -> None:
        embed = embeds.info(
            "TikTok Bot — Help",
            "Monitor TikTok accounts and receive live/post alerts in your server.",
        )
        embed.add_field(
            name="/tiktok add <username> [channel]",
            value="Subscribe to a TikTok account. Requires **Manage Server**.",
            inline=False,
        )
        embed.add_field(
            name="/tiktok remove <username>",
            value="Stop monitoring an account. Requires **Manage Server**.",
            inline=False,
        )
        embed.add_field(
            name="/tiktok list",
            value="Show all monitored accounts in this server.",
            inline=False,
        )
        await interaction.response.send_message(embed=embed, ephemeral=True)


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(TikTokCommands(bot))
