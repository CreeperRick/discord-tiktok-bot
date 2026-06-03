# utils/logging_conf.py
"""
Logging configuration for the bot.

Features:
- Colour output in terminals (via a lightweight formatter — no extra deps)
- Log rotation: keeps 7 days of daily files in logs/
- Separate log levels for discord.py internals (WARNING) vs our code (INFO)
- Returns a named logger so every module gets consistent output
"""
from __future__ import annotations

import logging
import logging.handlers
from pathlib import Path

# ── Colour codes (ANSI) for terminal output ───────────────────────────────────

_COLOURS = {
    logging.DEBUG:    "\033[36m",   # cyan
    logging.INFO:     "\033[32m",   # green
    logging.WARNING:  "\033[33m",   # yellow
    logging.ERROR:    "\033[31m",   # red
    logging.CRITICAL: "\033[35m",   # magenta
}
_RESET = "\033[0m"


class _ColourFormatter(logging.Formatter):
    """Adds ANSI colour to levelname for console output."""

    BASE_FMT = "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s"
    DATEFMT = "%Y-%m-%d %H:%M:%S"

    def format(self, record: logging.LogRecord) -> str:
        colour = _COLOURS.get(record.levelno, "")
        record.levelname = f"{colour}{record.levelname}{_RESET}"
        formatter = logging.Formatter(self.BASE_FMT, datefmt=self.DATEFMT)
        return formatter.format(record)


def setup_logging(name: str = "tiktokbot") -> logging.Logger:
    """
    Configure root logging once and return a named child logger.

    Call this once in bot.py; every other module should do:
        import logging
        logger = logging.getLogger(__name__)
    """
    log_dir = Path("logs")
    log_dir.mkdir(exist_ok=True)

    root = logging.getLogger()
    # Avoid adding duplicate handlers if called more than once (e.g. in tests)
    if root.handlers:
        return logging.getLogger(name)

    root.setLevel(logging.DEBUG)

    # ── Console handler (coloured, INFO+) ─────────────────────────────────
    console = logging.StreamHandler()
    console.setLevel(logging.INFO)
    console.setFormatter(_ColourFormatter())
    root.addHandler(console)

    # ── Rotating file handler (plain text, DEBUG+, 7-day retention) ───────
    file_handler = logging.handlers.TimedRotatingFileHandler(
        filename=log_dir / "bot.log",
        when="midnight",
        backupCount=7,
        encoding="utf-8",
    )
    file_handler.setLevel(logging.DEBUG)
    file_handler.setFormatter(
        logging.Formatter(
            "%(asctime)s [%(levelname)-8s] %(name)s: %(message)s",
            datefmt="%Y-%m-%d %H:%M:%S",
        )
    )
    root.addHandler(file_handler)

    # ── Silence noisy third-party loggers ─────────────────────────────────
    logging.getLogger("discord").setLevel(logging.WARNING)
    logging.getLogger("discord.http").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)

    return logging.getLogger(name)
