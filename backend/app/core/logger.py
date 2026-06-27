"""
Logging configuration for Synapse backend.

Configures Loguru with:
- Console output with coloured formatting
- Daily rotating application log
- Separate error-only log with rotation
- Automatic log directory creation
"""

import sys
from pathlib import Path

from loguru import logger

from app.core.config import get_settings

_configured = False


def configure_logging() -> None:
    """
    Apply Loguru handlers once per process.

    Safe to call multiple times — subsequent calls are no-ops.
    """
    global _configured
    if _configured:
        return

    settings = get_settings()
    log_dir = Path("logs")
    log_dir.mkdir(parents=True, exist_ok=True)

    # Remove the default Loguru handler
    logger.remove()

    # --- Console handler ---------------------------------------------------
    logger.add(
        sys.stdout,
        level=settings.log_level,
        colorize=True,
        format=(
            "<green>{time:YYYY-MM-DD HH:mm:ss}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> | "
            "<level>{message}</level>"
        ),
        backtrace=True,
        diagnose=True,
    )

    # --- Daily rotating application log ------------------------------------
    logger.add(
        log_dir / "synapse_{time:YYYY-MM-DD}.log",
        level=settings.log_level,
        rotation="00:00",          # Rotate at midnight
        retention="30 days",       # Keep 30 days of logs
        compression="gz",
        format=(
            "{time:YYYY-MM-DD HH:mm:ss} | "
            "{level: <8} | "
            "{name}:{function}:{line} | "
            "{message}"
        ),
        backtrace=True,
        diagnose=False,            # Disable in file logs for safety
        encoding="utf-8",
    )

    # --- Error-only log ----------------------------------------------------
    logger.add(
        log_dir / "synapse_errors_{time:YYYY-MM-DD}.log",
        level="ERROR",
        rotation="00:00",
        retention="90 days",
        compression="gz",
        format=(
            "{time:YYYY-MM-DD HH:mm:ss} | "
            "{level: <8} | "
            "{name}:{function}:{line} | "
            "{message}\n{exception}"
        ),
        backtrace=True,
        diagnose=True,
        encoding="utf-8",
    )

    _configured = True
    logger.info("Logging configured — level={}", settings.log_level)


def get_logger(name: str):
    """
    Return a contextually bound Loguru logger.

    Args:
        name: Module or component name used as the logging context.

    Returns:
        A Loguru logger with the given name bound to it.
    """
    return logger.bind(name=name)