# Dockerfile
# ── Build stage: install Python deps ─────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build dependencies for asyncpg (C extension)
RUN apt-get update && apt-get install -y --no-install-recommends \
        gcc \
        libpq-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Runtime stage ─────────────────────────────────────────────────────────────
FROM python:3.12-slim

WORKDIR /app

# ffmpeg is required by yt-dlp to process TikTok video streams
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg \
        libpq5 \
    && rm -rf /var/lib/apt/lists/*

# Copy installed packages from the builder stage
COPY --from=builder /install /usr/local

# Run as a non-root user — reduces blast radius if the bot is ever compromised
RUN useradd --system --no-create-home botuser
USER botuser

# Copy application code
COPY --chown=botuser:botuser . .

# Create logs dir (writable by botuser)
RUN mkdir -p logs

# The bot is a long-running process — no HTTP port to expose
CMD ["python", "-u", "bot.py"]
