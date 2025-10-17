"""Logging utilities for MCP Atlassian.

This module provides enhanced logging capabilities for MCP Atlassian,
including level-dependent stream handling to route logs to the appropriate
output stream based on their level, structured JSON logging, and correlation tracking.
"""

import json
import logging
import sys
import time
from datetime import datetime
from typing import Any, Dict, TextIO


def setup_logging(
    level: int = logging.WARNING, stream: TextIO = sys.stderr
) -> logging.Logger:
    """
    Configure MCP-Atlassian logging with level-based stream routing.

    Args:
        level: The minimum logging level to display (default: WARNING)
        stream: The stream to write logs to (default: sys.stderr)

    Returns:
        The configured logger instance
    """
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers to prevent duplication
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Add the level-dependent handler
    handler = logging.StreamHandler(stream)
    formatter = logging.Formatter("%(levelname)s - %(name)s - %(message)s")
    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    # Configure specific loggers
    loggers = ["mcp-atlassian", "mcp.server", "mcp.server.lowlevel.server", "mcp-jira"]

    for logger_name in loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(level)

    # Return the application logger
    return logging.getLogger("mcp-atlassian")


def mask_sensitive(value: str | None, keep_chars: int = 4) -> str:
    """Masks sensitive strings for logging.

    Args:
        value: The string to mask
        keep_chars: Number of characters to keep visible at start and end

    Returns:
        Masked string with most characters replaced by asterisks
    """
    if not value:
        return "Not Provided"
    if len(value) <= keep_chars * 2:
        return "*" * len(value)
    start = value[:keep_chars]
    end = value[-keep_chars:]
    middle = "*" * (len(value) - keep_chars * 2)
    return f"{start}{middle}{end}"


def get_masked_session_headers(headers: dict[str, str]) -> dict[str, str]:
    """Get session headers with sensitive values masked for safe logging.

    Args:
        headers: Dictionary of HTTP headers

    Returns:
        Dictionary with sensitive headers masked
    """
    sensitive_headers = {"Authorization", "Cookie", "Set-Cookie", "Proxy-Authorization"}
    masked_headers = {}

    for key, value in headers.items():
        if key in sensitive_headers:
            if key == "Authorization":
                # Preserve auth type but mask the credentials
                if value.startswith("Basic "):
                    masked_headers[key] = f"Basic {mask_sensitive(value[6:])}"
                elif value.startswith("Bearer "):
                    masked_headers[key] = f"Bearer {mask_sensitive(value[7:])}"
                else:
                    masked_headers[key] = mask_sensitive(value)
            else:
                masked_headers[key] = mask_sensitive(value)
        else:
            masked_headers[key] = str(value)

    return masked_headers


class StructuredFormatter(logging.Formatter):
    """Structured JSON log formatter with correlation ID support."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as structured JSON."""
        # Create base log entry
        log_entry = {
            "timestamp": datetime.fromtimestamp(record.created).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add correlation ID if available
        correlation_id = getattr(record, 'correlation_id', None)
        if correlation_id:
            log_entry["correlation_id"] = correlation_id

        # Add extra fields
        extra_fields = {
            'tool': getattr(record, 'tool', None),
            'service': getattr(record, 'service', None),
            'status_code': getattr(record, 'status_code', None),
            'error_type': getattr(record, 'error_type', None),
            'operation': getattr(record, 'operation', None),
        }

        # Only include non-None extra fields
        for key, value in extra_fields.items():
            if value is not None:
                log_entry[key] = value

        # Add exception info if present
        if record.exc_info:
            log_entry["exception"] = self.formatException(record.exc_info)

        return json.dumps(log_entry, default=str)


def setup_structured_logging(
    level: int = logging.INFO,
    stream: TextIO = sys.stderr,
    enable_json: bool = False
) -> logging.Logger:
    """
    Configure MCP-Atlassian logging with structured output.

    Args:
        level: The minimum logging level to display (default: INFO)
        stream: The stream to write logs to (default: sys.stderr)
        enable_json: Whether to use JSON formatting (default: False for compatibility)

    Returns:
        The configured logger instance
    """
    # Configure root logger
    root_logger = logging.getLogger()
    root_logger.setLevel(level)

    # Remove existing handlers to prevent duplication
    for handler in root_logger.handlers[:]:
        root_logger.removeHandler(handler)

    # Add the structured handler
    handler = logging.StreamHandler(stream)

    if enable_json:
        formatter = StructuredFormatter()
    else:
        # Fallback to regular formatter with optional correlation ID support
        formatter = logging.Formatter(
            "%(asctime)s - %(levelname)s - %(name)s - %(message)s"
        )

    handler.setFormatter(formatter)
    root_logger.addHandler(handler)

    # Configure specific loggers
    loggers = ["mcp-atlassian", "mcp.server", "mcp.server.lowlevel.server", "mcp-jira"]

    for logger_name in loggers:
        logger = logging.getLogger(logger_name)
        logger.setLevel(level)

    # Return the application logger
    return logging.getLogger("mcp-atlassian")


def setup_logging(
    level: int = logging.WARNING, stream: TextIO = sys.stderr
) -> logging.Logger:
    """
    Configure MCP-Atlassian logging with level-based stream routing.

    Args:
        level: The minimum logging level to display (default: WARNING)
        stream: The stream to write logs to (default: sys.stderr)

    Returns:
        The configured logger instance
    """
    # For backward compatibility, use structured logging without JSON
    return setup_structured_logging(level=level, stream=stream, enable_json=False)


def log_with_correlation(
    logger: logging.Logger,
    level: int,
    message: str,
    correlation_id: str | None = None,
    extra: Dict[str, Any] | None = None,
) -> None:
    """
    Log a message with correlation ID and extra context.

    Args:
        logger: The logger to use
        level: Log level (logging.INFO, logging.ERROR, etc.)
        message: The log message
        correlation_id: Optional correlation ID for request tracking
        extra: Additional context fields
    """
    log_extra = extra or {}
    if correlation_id:
        log_extra['correlation_id'] = correlation_id

    logger.log(level, message, extra=log_extra)


def log_config_param(
    logger: logging.Logger,
    service: str,
    param: str,
    value: str | None,
    sensitive: bool = False,
) -> None:
    """Logs a configuration parameter, masking if sensitive.

    Args:
        logger: The logger to use
        service: The service name (Jira or Confluence)
        param: The parameter name
        value: The parameter value
        sensitive: Whether the value should be masked
    """
    display_value = mask_sensitive(value) if sensitive else (value or "Not Provided")
    logger.info(f"{service} {param}: {display_value}")


def get_logger(name: str) -> logging.Logger:
    """
    Get a logger with structured logging capabilities.

    Args:
        name: Logger name

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)
