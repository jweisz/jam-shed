"""
Logging configuration for jam-shed.
"""

import logging
import sys
from typing import Optional


# Color codes for terminal output
class LogColors:
    """ANSI color codes for terminal logging."""

    RESET = "\033[0m"
    RED = "\033[91m"
    GREEN = "\033[92m"
    YELLOW = "\033[93m"
    BLUE = "\033[94m"
    MAGENTA = "\033[95m"
    CYAN = "\033[96m"
    WHITE = "\033[97m"
    BOLD = "\033[1m"


class ColoredFormatter(logging.Formatter):
    """Custom formatter with colors for log levels."""

    COLORS = {
        logging.DEBUG: LogColors.CYAN,
        logging.INFO: LogColors.GREEN,
        logging.WARNING: LogColors.YELLOW,
        logging.ERROR: LogColors.RED,
        logging.CRITICAL: LogColors.RED + LogColors.BOLD,
    }

    def format(self, record):
        """Format log record with colors."""
        color = self.COLORS.get(record.levelno, LogColors.WHITE)
        record.levelname = f"{color}{record.levelname}{LogColors.RESET}"
        record.msg = f"{color}{record.msg}{LogColors.RESET}"
        return super().format(record)


def setup_logging(level: int = logging.INFO, log_file: Optional[str] = None, use_colors: bool = True) -> logging.Logger:
    """
    Setup logging configuration for jam-shed.

    Args:
        level: Logging level (default: INFO)
        log_file: Optional file path for file logging
        use_colors: Use colored output for console (default: True)

    Returns:
        Configured logger instance
    """
    logger = logging.getLogger("jam-shed")
    logger.setLevel(level)

    # Remove existing handlers
    logger.handlers.clear()

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)

    if use_colors:
        console_formatter = ColoredFormatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S")
    else:
        console_formatter = logging.Formatter(
            "%(asctime)s - %(name)s - %(levelname)s - %(message)s", datefmt="%H:%M:%S"
        )

    console_handler.setFormatter(console_formatter)
    logger.addHandler(console_handler)

    # File handler (if specified)
    if log_file:
        file_handler = logging.FileHandler(log_file)
        file_handler.setLevel(level)
        file_formatter = logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        file_handler.setFormatter(file_formatter)
        logger.addHandler(file_handler)

    return logger


def get_logger(name: Optional[str] = None) -> logging.Logger:
    """
    Get a logger instance.

    Args:
        name: Optional logger name (default: 'jam-shed')

    Returns:
        Logger instance
    """
    if name:
        return logging.getLogger(f"jam-shed.{name}")
    return logging.getLogger("jam-shed")


# Default logger instance
logger = get_logger()
