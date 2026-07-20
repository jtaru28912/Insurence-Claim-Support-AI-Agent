"""Centralized logging configuration.

Kept separate from settings.py so logging concerns (formatters, handlers)
don't clutter the configuration model, while still deriving the log level
from Settings — a single call site (api/app_factory.py) wires the two
together at startup.
"""

from __future__ import annotations

import logging
import sys

_VALID_LOG_LEVELS = {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}


def configure_logging(log_level: str = "INFO") -> None:
    """Configure root logging once, at application startup.

    Idempotent: safe to call multiple times (e.g. in tests) without
    duplicating log handlers.
    """
    root_logger = logging.getLogger()
    if root_logger.handlers:
        # Already configured (e.g. during test collection) — just update level.
        root_logger.setLevel(log_level.upper())
        return

    handler = logging.StreamHandler(stream=sys.stdout)
    formatter = logging.Formatter(
        fmt="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )
    handler.setFormatter(formatter)

    root_logger.addHandler(handler)
    root_logger.setLevel(log_level.upper())

    # Quiet down noisy third-party loggers by default.
    for noisy_logger in ("httpx", "httpcore", "urllib3"):
        logging.getLogger(noisy_logger).setLevel(logging.WARNING)


def set_log_level(log_level: str) -> str:
    """Update the root log level at runtime and return the applied level."""
    normalized = log_level.strip().upper()
    if normalized not in _VALID_LOG_LEVELS:
        raise ValueError(
            f"Unsupported log level: {log_level}. Expected one of {sorted(_VALID_LOG_LEVELS)}"
        )
    logging.getLogger().setLevel(normalized)
    return normalized


def get_log_level() -> str:
    """Return the current effective root log level."""
    return logging.getLevelName(logging.getLogger().getEffectiveLevel())
