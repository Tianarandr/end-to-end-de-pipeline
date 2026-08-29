"""Structured, greppable logging. See docs/architecture/06-observability.md.

Every ingestion log line is `event=<name> key=value ...` instead of free
text, so a log-based alert or dashboard can parse it later without any
change in this module.
"""
from __future__ import annotations

import logging
import sys


def get_logger(name: str) -> logging.Logger:
    logger = logging.getLogger(name)
    if not logger.handlers:
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s %(message)s"))
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)
    return logger


def log_event(logger: logging.Logger, event: str, level: int = logging.INFO, **fields: object) -> None:
    kv = " ".join(f"{k}={v}" for k, v in fields.items())
    logger.log(level, "event=%s %s", event, kv)
