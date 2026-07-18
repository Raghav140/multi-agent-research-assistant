"""Centralized logging configuration for production-ready AI application.

This module provides a comprehensive logging system using Loguru with support for:
- Console logging with JSON/text formats
- Rotating file logs with compression
- Separate error log files
- Automatic directory creation
- Environment-specific log levels
- Standard logging interception
"""

import logging
import sys
from pathlib import Path
from typing import Literal, Optional

from loguru import logger


class InterceptHandler(logging.Handler):
    """Intercept standard logging and redirect to loguru.

    This handler captures all standard library logging calls and redirects
    them through Loguru for consistent formatting and handling.
    """

    def emit(self, record: logging.LogRecord) -> None:
        """Emit a log record to loguru.

        Args:
            record: The log record to emit
        """
        # Get corresponding Loguru level if it exists
        try:
            level = logger.level(record.levelname).name
        except ValueError:
            level = record.levelno

        # Find caller from where originated the logged message
        frame, depth = logging.currentframe(), 2
        while frame and frame.f_code.co_filename == logging.__file__:
            frame = frame.f_back
            depth += 1

        logger.opt(depth=depth, exception=record.exc_info).log(
            level, record.getMessage()
        )


def setup_logging(
    log_level: str = "INFO",
    log_format: Literal["json", "text"] = "json",
    log_dir: Optional[Path] = None,
    environment: Literal["development", "staging", "production"] = "development",
) -> None:
    """
    Set up application logging with loguru for production use.

    This function configures Loguru with multiple handlers:
    - Console handler for immediate output
    - General log file with rotation
    - Separate error log file for critical issues

    Args:
        log_level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_format: Log format ("json" or "text")
        log_dir: Directory for log files (defaults to ./logs)
        environment: Environment name for configuration tuning
    """
    # Set default log directory
    if log_dir is None:
        log_dir = Path("logs")

    # Create logs directory if it doesn't exist
    log_dir.mkdir(parents=True, exist_ok=True)

    # Remove default handler
    logger.remove()

    # Adjust log level based on environment
    if environment == "production":
        file_log_level = "WARNING"
        console_log_level = "INFO"
    elif environment == "staging":
        file_log_level = "INFO"
        console_log_level = "INFO"
    else:  # development
        file_log_level = "DEBUG"
        console_log_level = "DEBUG"

    # Add console handler
    if log_format == "json":
        logger.add(
            sys.stderr,
            format=lambda record: (
                f'{{"time": "{record["time"]}", '
                f'"level": "{record["level"].name}", '
                f'"message": "{record["message"]}", '
                f'"module": "{record["name"]}", '
                f'"function": "{record["function"]}", '
                f'"line": {record["line"]}}}'
            ),
            level=console_log_level,
            enqueue=True,
            colorize=False,
        )
    else:
        logger.add(
            sys.stderr,
            format="<green>{time:YYYY-MM-DD HH:mm:ss.SSS}</green> | "
            "<level>{level: <8}</level> | "
            "<cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - "
            "<level>{message}</level>",
            level=console_log_level,
            enqueue=True,
            colorize=True,
        )

    # Add general log file with rotation
    general_log_file = log_dir / "app.log"
    logger.add(
        general_log_file,
        rotation="10 MB",
        retention="30 days",
        compression="zip",
        level=file_log_level,
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
        encoding="utf-8",
    )

    # Add separate error log file
    error_log_file = log_dir / "error.log"
    logger.add(
        error_log_file,
        rotation="10 MB",
        retention="60 days",
        compression="zip",
        level="ERROR",
        format="{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} - {message}",
        encoding="utf-8",
        filter=lambda record: record["level"].name in ["ERROR", "CRITICAL"],
    )

    # Intercept standard logging
    logging.basicConfig(handlers=[InterceptHandler()], level=0, force=True)

    logger.info(f"Logging configured - Level: {log_level}, Format: {log_format}, Environment: {environment}")


def get_logger(name: str) -> "logger":
    """
    Get a logger instance bound to a specific module.

    This function provides a convenient way to get a logger that is
    automatically bound to the calling module's name.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Logger instance bound to the specified name

    Example:
        >>> from backend.utils.logging_config import get_logger
        >>> logger = get_logger(__name__)
        >>> logger.info("Application started")
    """
    return logger.bind(name=name)
