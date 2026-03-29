"""Logging configuration using loguru."""

import sys
from loguru import logger
from config.settings import LOG_LEVEL, BASE_DIR

# Remove default handler
logger.remove()

# Console handler with color
logger.add(
    sys.stdout,
    level=LOG_LEVEL,
    format="<green>{time:HH:mm:ss}</green> | <level>{level:<8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan> | <level>{message}</level>",
    colorize=True,
)

# File handler for audit trail
logger.add(
    BASE_DIR / "logs" / "engine_{time:YYYY-MM-DD}.log",
    level="DEBUG",
    format="{time:YYYY-MM-DD HH:mm:ss} | {level:<8} | {name}:{function}:{line} | {message}",
    rotation="10 MB",
    retention="30 days",
)

def get_logger(name: str):
    """Get a named logger instance."""
    return logger.bind(name=name)
