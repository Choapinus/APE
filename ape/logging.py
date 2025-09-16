from __future__ import annotations

"""Centralised Loguru configuration.

Use setup_logger() at program start. Idempotent – repeated calls are no-ops.
"""
import sys
from pathlib import Path
from typing import Literal

from loguru import logger

from ape.settings import settings

_INITIALISED = False


def setup_logger(
    level: Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"] | None = None
) -> None:
    """Configure Loguru sinks once per process.

    If *level* is *None* the value of ``settings.LOG_LEVEL`` is used.  The
    function is idempotent – subsequent calls are ignored.
    """

    global _INITIALISED
    if _INITIALISED:
        return

    if level is None:
        level = settings.LOG_LEVEL.upper()  # type: ignore[assignment]

    Path("logs").mkdir(exist_ok=True)

    logger.remove()  # remove default stderr sink

    logger.add("logs/app.log", level="INFO", rotation="1 MB", retention="10 days")
    logger.add("logs/debug.log", level="DEBUG", rotation="1 MB", retention="10 days")

    # pretty-print to stderr at the chosen level
    logger.add(
        sys.stderr,
        level=level,
        format="<level>{message}</level>",
        colorize=True,
    )

    logger.level(level)
    logger.info("Logger initialised (level: {})", level)

    _INITIALISED = True 