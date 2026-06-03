# TikTok Discord Bot

A Discord bot that monitors TikTok accounts and posts live/new-post alerts to your server. Built with **discord.py 2.x**, **SQLAlchemy async**, and **yt-dlp**.

---

## Features

- `/tiktok add <username>` — subscribe to any TikTok account
- `/tiktok remove <username>` — unsubscribe
- `/tiktok list` — view all subscriptions in the server
- Automatic moderation log (member joins/leaves, bans, message edits/deletes)
- Per-guild configuration stored in database
- Docker-ready with multi-stage build and non-root user

---

## Quick Start (local)

### 1. Prerequisites

- Python 3.12+
- ffmpeg installed (`apt install ffmpeg` / `brew install ffmpeg`)

### 2. Clone and install

```bash
git clone https://github.com/CreeperRick/discord-tiktok-bot.git
cd discord-tiktok-bot
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

### 3. Configure

```bash
cp .env.example .env
# Open .env and set DISCORD_TOKEN (and optionally DATABASE_URL)
```

### 4. Run

```bash
python bot.py
```

Expected output:
```
2025-01-01 12:00:00 [INFO    ] tiktokbot: Database initialised
2025-01-01 12:00:01 [INFO    ] tiktokbot: Loaded: apps.tiktok.commands
2025-01-01 12:00:01 [INFO    ] tiktokbot: Loaded: apps.tiktok.monitor
2025-01-01 12:00:01 [INFO    ] tiktokbot: Loaded: apps.moderation.automod
2025-01-01 12:00:02 [INFO    ] tiktokbot: Slash commands synced (4 registered)
2025-01-01 12:00:02 [INFO    ] tiktokbot: ✅  Logged in as TikTokBot#1234 (ID: ...)
```

---

## Docker

```bash
# Build and start
docker compose up -d --build

# Watch logs
docker compose logs -f bot

# Stop
docker compose down
```

The SQLite database is stored in a named Docker volume (`bot_data`) and survives container rebuilds.

---

## Switching to PostgreSQL (production)

1. Spin up a Postgres instance (or use a managed service)
2. Set in `.env`:
   ```
   DATABASE_URL=postgresql+asyncpg://user:password@host:5432/tiktokbot
   ```
3. That's it — the ORM handles schema creation on first boot.

For production, use [Alembic](https://alembic.sqlalchemy.org/) for schema migrations instead of relying on `create_all`.

---

## Project structure

```
discord-tiktok-bot/
├── bot.py                    # Entry point, bot class, extension loader
├── config.py                 # Pydantic settings (reads .env)
├── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env.example
│
├── apps/                     # Feature modules (each is a Python package)
│   ├── tiktok/
│   │   ├── commands.py       # /tiktok slash commands
│   │   └── monitor.py        # Background polling loop
│   └── moderation/
│       └── automod.py        # Mod-log event listeners
│
└── utils/
    ├── database.py           # SQLAlchemy models + session helper
    ├── embeds.py             # Reusable Discord embed builders
    └── logging_conf.py       # Logging setup (colour console + rotating file)
```

---

## Adding a new app

1. Create `apps/myapp/__init__.py` (empty)
2. Add `apps/myapp/commands.py` with `async def setup(bot)` — the bot loader picks it up automatically
3. Optionally add `apps/myapp/monitor.py` or `apps/myapp/automod.py`

---

## Debugging

```bash
# Check bot logs
tail -f logs/bot.log

# Enable SQLAlchemy query logging (edit utils/database.py)
_engine = create_async_engine(settings.database_url, echo=True)

# Run with Python debugger attached
python -m pdb bot.py
```

---

## Environment variables

| Variable | Required | Default | Description |
|---|---|---|---|
| `DISCORD_TOKEN` | ✅ | — | Bot token from Discord Developer Portal |
| `DATABASE_URL` | ❌ | `sqlite+aiosqlite:///./data.db` | SQLAlchemy async DB URL |
| `TIKTOK_CHECK_INTERVAL` | ❌ | `60` | Poll interval in seconds (min 5) |
| `MODERATION_LOG_CHANNEL_ID` | ❌ | `None` | Channel ID for global mod log |
