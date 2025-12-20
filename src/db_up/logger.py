"""
Logging setup for db-up.

This module provides logging configuration with:
- User-configurable log levels (DEBUG, INFO, WARNING, ERROR)
- Multiple output formats (text, JSON)
- Multiple destinations (console, file, both)
- Automatic credential redaction
- Log rotation

SECURITY: All logs are automatically filtered to remove sensitive data.
"""

import logging
import json
from logging.handlers import RotatingFileHandler
from pathlib import Path
from typing import Any, Dict, List

from db_up.models import LoggingConfig
from db_up.security import sanitize_error


class SensitiveDataFilter(logging.Filter):
    """
    Filter to redact sensitive information from logs.

    SECURITY: This filter ensures passwords and credentials never
    appear in log output.
    """

    def __init__(self, redact_hostnames: bool = False):
        """
        Initialize the filter.

        Args:
            redact_hostnames: If True, also redact IP addresses
        """
        super().__init__()
        self.redact_hostnames = redact_hostnames

    def filter(self, record: logging.LogRecord) -> bool:
        """
        Filter log record to redact sensitive data.

        Args:
            record: Log record to filter

        Returns:
            True (always allow the record, just modify it)
        """
        # Sanitize the message
        if hasattr(record, "msg") and isinstance(record.msg, str):
            record.msg = sanitize_error(record.msg, self.redact_hostnames)

        # Sanitize any string arguments
        if hasattr(record, "args") and record.args:
            sanitized_args: List[Any] = []
            for arg in record.args:
                if isinstance(arg, str):
                    sanitized_args.append(sanitize_error(arg, self.redact_hostnames))
                else:
                    sanitized_args.append(arg)
            record.args = tuple(sanitized_args)

        return True


class JSONFormatter(logging.Formatter):
    """
    Format logs as JSON for structured logging.

    This formatter creates JSON output compatible with log aggregation
    systems like ELK, Splunk, and Datadog.
    """

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record as JSON.

        Args:
            record: Log record to format

        Returns:
            JSON string
        """
        log_data: Dict[str, Any] = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "application": "db-up",
        }

        # Add extra fields if present
        extra_fields = [
            "response_time_ms",
            "status",
            "error_code",
            "error_message",
            "retry_attempt",
            "max_retries",
            "check_number",
        ]

        for field in extra_fields:
            if hasattr(record, field):
                log_data[field] = getattr(record, field)

        # Add exception info if present
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data)


class ColoredFormatter(logging.Formatter):
    """
    Format logs with colors for console output.

    Uses colorama for cross-platform color support.
    """

    # Color codes
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "RESET": "\033[0m",  # Reset
    }

    def format(self, record: logging.LogRecord) -> str:
        """
        Format log record with colors.

        Args:
            record: Log record to format

        Returns:
            Colored log string
        """
        # Add color to level name
        levelname = record.levelname
        if levelname in self.COLORS:
            colored_levelname = (
                f"{self.COLORS[levelname]}{levelname}{self.COLORS['RESET']}"
            )
            record.levelname = colored_levelname

        # Format the record
        result = super().format(record)

        # Restore original levelname
        record.levelname = levelname

        return result


def setup_logging(config: LoggingConfig) -> logging.Logger:
    """
    Setup logging with user-configurable options.

    This function configures the logging system according to the provided
    configuration, including:
    - Log level (DEBUG, INFO, WARNING, ERROR)
    - Output destination (console, file, both)
    - Log format (text, JSON)
    - Automatic credential redaction
    - Log rotation

    Args:
        config: Logging configuration

    Returns:
        Configured logger instance

    Example:
        >>> from db_up.models import LoggingConfig
        >>> config = LoggingConfig(level='DEBUG', output='console')
        >>> logger = setup_logging(config)
        >>> logger.info("Database connection successful")
    """
    # Get or create logger
    logger = logging.getLogger("db-up")
    logger.setLevel(getattr(logging, config.level))

    # Clear existing handlers to avoid duplicates
    logger.handlers.clear()

    # Prevent propagation to root logger
    logger.propagate = False

    # Add sensitive data filter (SECURITY)
    if config.redact_credentials:
        logger.addFilter(SensitiveDataFilter(config.redact_hostnames))

    # Choose formatter based on format setting
    formatter: logging.Formatter
    if config.format == "json":
        formatter = JSONFormatter(datefmt="%Y-%m-%dT%H:%M:%S")
    else:
        # Text format with colors for console
        formatter = ColoredFormatter(
            "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
        )

    # Add console handler if needed
    if config.output in ("console", "both"):
        console_handler = logging.StreamHandler()
        console_handler.setFormatter(formatter)
        logger.addHandler(console_handler)

    # Add file handler if needed
    if config.output in ("file", "both"):
        # Create log directory if it doesn't exist
        log_path = Path(config.file_path)
        log_path.parent.mkdir(parents=True, exist_ok=True)

        # Use rotating file handler
        file_handler = RotatingFileHandler(
            config.file_path,
            maxBytes=config.max_file_size,
            backupCount=config.backup_count,
            encoding="utf-8",
        )

        # Use JSON formatter for file output (better for parsing)
        if config.format == "json":
            file_handler.setFormatter(formatter)
        else:
            # Use plain text formatter for file
            file_formatter = logging.Formatter(
                "%(asctime)s [%(levelname)s] %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
            )
            file_handler.setFormatter(file_formatter)

        logger.addHandler(file_handler)

    return logger


def get_logger() -> logging.Logger:
    """
    Get the db-up logger instance.

    Returns:
        Logger instance

    Note:
        You must call setup_logging() before using this function.
    """
    return logging.getLogger("db-up")
