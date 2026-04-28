"""Centralised logging configuration.

A single ``get_logger`` factory returns module-scoped loggers that share
a rotating file handler plus a console handler. Importing this module
configures the root logger exactly once.
"""

from __future__ import annotations

import logging
from logging.handlers import RotatingFileHandler

from app.core.config import settings


_LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(name)s | %(message)s"
_DATE_FORMAT = "%Y-%m-%d %H:%M:%S"
_CONFIGURED = False


def _configure_root() -> None:
    """Attach handlers to the root logger; idempotent."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    settings.ensure_dirs()
    formatter = logging.Formatter(_LOG_FORMAT, _DATE_FORMAT)

    console = logging.StreamHandler()
    console.setFormatter(formatter)

    file_handler = RotatingFileHandler(
        settings.log_dir / "automation.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    file_handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(logging.INFO)
    # Replace existing handlers so reloads don't multiply log lines.
    root.handlers = [console, file_handler]

    _CONFIGURED = True


def get_logger(name: str) -> logging.Logger:
    """Return a configured logger for the given module name."""
    _configure_root()
    return logging.getLogger(name)
