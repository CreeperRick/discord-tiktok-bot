# utils/embeds.py
"""
Centralised Discord embed builders.
Keeping embed construction here means a single style change updates every cog.
"""
from __future__ import annotations

import discord

# Brand colour palette
COLOUR_SUCCESS = discord.Colour.green()
COLOUR_ERROR   = discord.Colour.red()
COLOUR_INFO    = discord.Colour(0xFE2C55)   # TikTok red
COLOUR_WARNING = discord.Colour.orange()


def success(title: str, description: str = "") -> discord.Embed:
    return discord.Embed(title=f"✅  {title}", description=description, colour=COLOUR_SUCCESS)


def error(title: str, description: str = "") -> discord.Embed:
    return discord.Embed(title=f"❌  {title}", description=description, colour=COLOUR_ERROR)


def info(title: str, description: str = "") -> discord.Embed:
    return discord.Embed(title=title, description=description, colour=COLOUR_INFO)


def warning(title: str, description: str = "") -> discord.Embed:
    return discord.Embed(title=f"⚠️  {title}", description=description, colour=COLOUR_WARNING)


def tiktok_live(username: str, avatar_url: str | None = None) -> discord.Embed:
    """Embed shown when a monitored TikTok user goes live."""
    embed = discord.Embed(
        title=f"🔴  {username} is LIVE on TikTok!",
        url=f"https://www.tiktok.com/@{username}/live",
        colour=COLOUR_INFO,
    )
    embed.set_footer(text="TikTok Live")
    if avatar_url:
        embed.set_thumbnail(url=avatar_url)
    return embed


def tiktok_post(
    username: str,
    post_url: str,
    description: str,
    thumbnail_url: str | None = None,
) -> discord.Embed:
    """Embed shown when a monitored TikTok user posts new content."""
    embed = discord.Embed(
        title=f"🎵  New post from @{username}",
        url=post_url,
        description=description[:200] + ("…" if len(description) > 200 else ""),
        colour=COLOUR_INFO,
    )
    embed.set_footer(text="TikTok")
    if thumbnail_url:
        embed.set_image(url=thumbnail_url)
    return embed
