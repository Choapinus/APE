from __future__ import annotations

"""Centralised Loguru configuration.

Use setup_logger() at program start. Idempotent – repeated calls are no-ops.
"""

from pathlib import Path
from typing import Literal

from loguru import logger

_INITIALISED = False


def setup_logger(level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] = "DEBUG") -> None:
    """Configure Loguru sinks once per process."""

    global _INITIALISED
    if _INITIALISED:
        return

    Path("logs").mkdir(exist_ok=True)

    logger.remove()  # remove default stderr sink

    logger.add("logs/app.log", level="INFO", rotation="1 MB", retention="10 days")
    logger.add("logs/debug.log", level="DEBUG", rotation="1 MB", retention="10 days")

    # also pretty-print to stderr at requested level
    logger.add(lambda msg: print(msg, end=""), level=level)

    logger.level(level)
    logger.info("Logger initialised (level: {})", level)

    _INITIALISED = True 