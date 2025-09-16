"""
Logging utilities optimized for AWS Lambda and CloudWatch integration.

This module provides structured logging with JSON formatting for Lambda environments
and human-readable formatting for development. Features include performance timing,
error context preservation, and CloudWatch optimization.
"""

import json
import logging
import os
import sys
import time
from contextlib import contextmanager
from typing import Any, Dict, Optional


class StructuredFormatter(logging.Formatter):
    """
    Formatter that outputs JSON for Lambda/CloudWatch or human-readable for development.
    """

    def __init__(self, include_extra: bool = True):
        super().__init__()
        self.include_extra = include_extra
        self.is_lambda = bool(os.environ.get("AWS_LAMBDA_FUNCTION_NAME"))

    def format(self, record: logging.LogRecord) -> str:
        if self.is_lambda:
            return self._format_json(record)
        else:
            return self._format_human(record)

    def _format_json(self, record: logging.LogRecord) -> str:
        """Format log record as JSON for CloudWatch."""
        log_data = {
            "timestamp": self.formatTime(record, self.datefmt),
            "level": record.levelname,
            "message": record.getMessage(),
            "logger": record.name,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add extra fields if available
        if self.include_extra and hasattr(record, "extra_data"):
            log_data.update(record.extra_data)

        # Add exception information
        if record.exc_info:
            log_data["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_data, default=str)

    def _format_human(self, record: logging.LogRecord) -> str:
        """Format log record for human readability in development."""
        timestamp = self.formatTime(record, "%Y-%m-%d %H:%M:%S")
        message = record.getMessage()

        # Add extra context if available
        if self.include_extra and hasattr(record, "extra_data"):
            extra_parts = [f"{k}={v}" for k, v in record.extra_data.items()]
            if extra_parts:
                message += f" [{', '.join(extra_parts)}]"

        formatted = f"{timestamp} - {record.levelname:8} - {message}"

        if record.exc_info:
            formatted += "\n" + self.formatException(record.exc_info)

        return formatted


class SSMLogger:
    """
    Enhanced logger for AWS SSM data fetching with performance tracking and context.
    """

    def __init__(self, name: str = "aws_ssm_fetcher", level: Optional[str] = None):
        self.logger = logging.getLogger(name)
        self._setup_logger(level)
        self._timers: Dict[str, float] = {}

    def _setup_logger(self, level: Optional[str] = None):
        """Configure logger with appropriate formatter and level."""
        if self.logger.handlers:
            return  # Already configured

        # Determine log level
        if level:
            log_level = getattr(logging, level.upper())
        elif os.environ.get("AWS_LAMBDA_FUNCTION_NAME"):
            log_level = logging.INFO
        else:
            log_level = logging.INFO

        self.logger.setLevel(log_level)

        # Create handler
        handler = logging.StreamHandler(sys.stdout)
        handler.setFormatter(StructuredFormatter())
        self.logger.addHandler(handler)

        # Prevent duplicate logs in Lambda
        self.logger.propagate = False

    def info(self, message: str, **extra):
        """Log info message with optional extra context."""
        self._log_with_extra(logging.INFO, message, extra)

    def debug(self, message: str, **extra):
        """Log debug message with optional extra context."""
        self._log_with_extra(logging.DEBUG, message, extra)

    def warning(self, message: str, **extra):
        """Log warning message with optional extra context."""
        self._log_with_extra(logging.WARNING, message, extra)

    def error(self, message: str, exc_info: bool = False, **extra):
        """Log error message with optional exception info and extra context."""
        self._log_with_extra(logging.ERROR, message, extra, exc_info=exc_info)

    def critical(self, message: str, exc_info: bool = False, **extra):
        """Log critical message with optional exception info and extra context."""
        self._log_with_extra(logging.CRITICAL, message, extra, exc_info=exc_info)

    def _log_with_extra(
        self, level: int, message: str, extra: Dict[str, Any], exc_info: bool = False
    ):
        """Internal method to log with extra context data."""
        if extra:
            # Create a custom LogRecord with extra data
            exc_info_tuple = sys.exc_info() if exc_info else None
            record = self.logger.makeRecord(
                self.logger.name, level, "", 0, message, (), exc_info_tuple
            )
            record.extra_data = extra
            self.logger.handle(record)
        else:
            self.logger.log(level, message, exc_info=exc_info)

    @contextmanager
    def timer(self, operation: str):
        """Context manager for timing operations."""
        start_time = time.time()
        self.info(f"Starting {operation}")

        try:
            yield
            duration = time.time() - start_time
            self.info(f"Completed {operation}", duration_seconds=f"{duration:.2f}")
        except Exception as e:
            duration = time.time() - start_time
            self.error(
                f"Failed {operation}",
                duration_seconds=f"{duration:.2f}",
                error=str(e),
                exc_info=True,
            )
            raise

    def start_timer(self, operation: str):
        """Start a named timer for an operation."""
        self._timers[operation] = time.time()
        self.info(f"Starting {operation}")

    def end_timer(self, operation: str, **extra):
        """End a named timer and log the duration."""
        if operation not in self._timers:
            self.warning(f"Timer '{operation}' was not started")
            return

        duration = time.time() - self._timers.pop(operation)
        self.info(f"Completed {operation}", duration_seconds=f"{duration:.2f}", **extra)
        return duration


def setup_logging(level: str = "INFO") -> SSMLogger:
    """
    Set up logging for the application.

    Args:
        level: Log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)

    Returns:
        Configured SSMLogger instance
    """
    return SSMLogger(level=level)


def get_logger(name: str = "aws_ssm_fetcher") -> SSMLogger:
    """
    Get a logger instance.

    Args:
        name: Logger name

    Returns:
        SSMLogger instance
    """
    return SSMLogger(name)


# Module-level convenience functions
_default_logger = None


def get_default_logger() -> SSMLogger:
    """Get the default logger instance."""
    global _default_logger
    if _default_logger is None:
        _default_logger = setup_logging()
    return _default_logger


# Convenience functions that use the default logger
def info(message: str, **extra):
    """Log info message using default logger."""
    get_default_logger().info(message, **extra)


def debug(message: str, **extra):
    """Log debug message using default logger."""
    get_default_logger().debug(message, **extra)


def warning(message: str, **extra):
    """Log warning message using default logger."""
    get_default_logger().warning(message, **extra)


def error(message: str, exc_info: bool = False, **extra):
    """Log error message using default logger."""
    get_default_logger().error(message, exc_info=exc_info, **extra)


def critical(message: str, exc_info: bool = False, **extra):
    """Log critical message using default logger."""
    get_default_logger().critical(message, exc_info=exc_info, **extra)
