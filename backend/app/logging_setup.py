"""
One place that configures logging for the whole backend. Import
`get_logger(__name__)` in every module instead of calling `logging.getLogger`
directly, so every log line goes through the same console + rotating file
handlers set up here.
"""
from __future__ import annotations

import logging
import sys
from logging.handlers import RotatingFileHandler
from pathlib import Path

from app.config import BACKEND_DIR, Settings

_CONFIGURED = False


def configure_logging(settings: Settings) -> None:
    global _CONFIGURED
    if _CONFIGURED:
        return

    log_dir = BACKEND_DIR / settings.logging.log_dir
    log_dir.mkdir(parents=True, exist_ok=True)
    log_path = log_dir / settings.logging.log_file

    level = getattr(logging, settings.logging.level.upper(), logging.INFO)
    fmt = logging.Formatter(
        "%(asctime)s %(levelname)-8s %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setFormatter(fmt)

    file_handler = RotatingFileHandler(
        log_path,
        maxBytes=settings.logging.max_bytes,
        backupCount=settings.logging.backup_count,
        encoding="utf-8",
    )
    file_handler.setFormatter(fmt)

    root = logging.getLogger()
    root.setLevel(level)
    root.addHandler(console_handler)
    root.addHandler(file_handler)

    _CONFIGURED = True
    logging.getLogger(__name__).info("Logging configured (level=%s, file=%s)", settings.logging.level, log_path)


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
