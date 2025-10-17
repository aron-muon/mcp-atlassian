"""Tests for structured logging functionality."""

import json
import logging
import sys
from io import StringIO
from datetime import datetime

import pytest

from mcp_atlassian.utils.logging import (
    StructuredFormatter,
    get_logger,
    log_config_param,
    log_with_correlation,
    mask_sensitive,
    setup_structured_logging,
    get_masked_session_headers,
)


class TestStructuredFormatter:
    """Tests for the StructuredFormatter class."""

    def test_structured_formatter_basic_format(self):
        """Test basic structured log record formatting."""
        formatter = StructuredFormatter()

        # Create a log record
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="/path/to/file.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None
        )

        result = json.loads(formatter.format(record))

        assert result["level"] == "INFO"
        assert result["logger"] == "test.logger"
        assert result["message"] == "Test message"
        assert result["module"] == "file"
        assert result["function"] == "<module>"
        assert result["line"] == 42
        assert "timestamp" in result
        assert "correlation_id" not in result  # Not set by default

    def test_structured_formatter_with_correlation_id(self):
        """Test structured formatter with correlation ID."""
        formatter = StructuredFormatter()

        # Create a log record with correlation ID
        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="/path/to/file.py",
            lineno=42,
            msg="Error message",
            args=(),
            exc_info=None
        )
        record.correlation_id = "abc12345"

        result = json.loads(formatter.format(record))

        assert result["correlation_id"] == "abc12345"
        assert result["level"] == "ERROR"

    def test_structured_formatter_with_extra_fields(self):
        """Test structured formatter with extra fields."""
        formatter = StructuredFormatter()

        # Create a log record with extra fields
        record = logging.LogRecord(
            name="test.logger",
            level=logging.WARNING,
            pathname="/path/to/file.py",
            lineno=42,
            msg="Warning message",
            args=(),
            exc_info=None
        )
        record.tool = "test_tool"
        record.service = "TestService"
        record.status_code = 500

        result = json.loads(formatter.format(record))

        assert result["tool"] == "test_tool"
        assert result["service"] == "TestService"
        assert result["status_code"] == 500

    def test_structured_formatter_with_exception(self):
        """Test structured formatter with exception info."""
        formatter = StructuredFormatter()

        # Create a log record with exception
        try:
            raise ValueError("Test exception")
        except ValueError:
            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test.logger",
            level=logging.ERROR,
            pathname="/path/to/file.py",
            lineno=42,
            msg="Error occurred",
            args=(),
            exc_info=exc_info
        )

        result = json.loads(formatter.format(record))

        assert result["level"] == "ERROR"
        assert "exception" in result
        assert "ValueError" in result["exception"]
        assert "Test exception" in result["exception"]

    def test_structured_formatter_timestamp_format(self):
        """Test that timestamp is properly formatted."""
        formatter = StructuredFormatter()

        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="/path/to/file.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None
        )

        result = json.loads(formatter.format(record))

        # Verify timestamp is ISO format
        timestamp_str = result["timestamp"]
        datetime.fromisoformat(timestamp_str)  # Should not raise exception


class TestSetupStructuredLogging:
    """Tests for the setup_structured_logging function."""

    def test_setup_structured_logging_json_format(self):
        """Test setup_structured_logging with JSON format enabled."""
        stream = StringIO()
        logger = setup_structured_logging(
            level=logging.DEBUG,
            stream=stream,
            enable_json=True
        )

        logger.info("Test message")
        output = stream.getvalue()

        # Should be valid JSON
        log_entry = json.loads(output.strip())
        assert log_entry["level"] == "INFO"
        assert log_entry["message"] == "Test message"
        assert "timestamp" in log_entry

    def test_setup_structured_logging_text_format(self):
        """Test setup_structured_logging with text format."""
        stream = StringIO()
        logger = setup_structured_logging(
            level=logging.INFO,
            stream=stream,
            enable_json=False
        )

        logger.info("Test message")
        output = stream.getvalue()

        # Should be plain text with timestamp
        assert "INFO" in output
        assert "Test message" in output
        assert "mcp-atlassian" in output

    def test_setup_structured_logging_removes_existing_handlers(self):
        """Test that setup_structured_logging removes existing handlers."""
        root_logger = logging.getLogger()

        # Add a test handler
        test_handler = logging.StreamHandler()
        root_logger.addHandler(test_handler)
        initial_count = len(root_logger.handlers)

        # Setup should remove existing handler
        stream = StringIO()
        setup_structured_logging(stream=stream, enable_json=False)

        # Should only have one handler
        assert len(root_logger.handlers) == 1
        assert test_handler not in root_logger.handlers

    def test_setup_structured_logging_configures_specific_loggers(self):
        """Test that specific loggers are configured."""
        stream = StringIO()
        logger = setup_structured_logging(
            level=logging.DEBUG,
            stream=stream,
            enable_json=False
        )

        # Check specific loggers are configured
        for logger_name in ["mcp-atlassian", "mcp.server", "mcp.server.lowlevel.server", "mcp-jira"]:
            configured_logger = logging.getLogger(logger_name)
            assert configured_logger.level == logging.DEBUG

    def test_setup_structured_logging_returns_application_logger(self):
        """Test that setup_structured_logging returns the application logger."""
        stream = StringIO()
        logger = setup_structured_logging(stream=stream, enable_json=False)

        assert logger.name == "mcp-atlassian"


class TestLoggingUtilities:
    """Tests for logging utility functions."""

    def test_log_with_correlation(self):
        """Test log_with_correlation function."""
        stream = StringIO()
        logger = logging.getLogger("test")
        handler = logging.StreamHandler(stream)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        log_with_correlation(
            logger, logging.INFO, "Test message", correlation_id="abc123"
        )

        output = stream.getvalue()
        assert "Test message" in output

    def test_get_logger(self):
        """Test get_logger function."""
        logger = get_logger("test.custom")

        assert logger.name == "test.custom"
        assert isinstance(logger, logging.Logger)

    def test_log_config_param_non_sensitive(self):
        """Test log_config_param with non-sensitive parameter."""
        stream = StringIO()
        logger = logging.getLogger("test")
        handler = logging.StreamHandler(stream)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        log_config_param(logger, "TestService", "url", "http://example.com", sensitive=False)

        output = stream.getvalue()
        assert "TestService url: http://example.com" in output

    def test_log_config_param_sensitive(self):
        """Test log_config_param with sensitive parameter."""
        stream = StringIO()
        logger = logging.getLogger("test")
        handler = logging.StreamHandler(stream)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        log_config_param(logger, "TestService", "token", "secret123", sensitive=True)

        output = stream.getvalue()
        assert "TestService token: secr*t123" in output  # Masked (first 4, last 4)

    def test_log_config_param_none_value(self):
        """Test log_config_param with None value."""
        stream = StringIO()
        logger = logging.getLogger("test")
        handler = logging.StreamHandler(stream)
        logger.addHandler(handler)
        logger.setLevel(logging.INFO)

        log_config_param(logger, "TestService", "url", None, sensitive=False)

        output = stream.getvalue()
        assert "TestService url: Not Provided" in output


class TestCredentialMasking:
    """Tests for credential masking functionality."""

    def test_mask_sensitive_none_value(self):
        """Test mask_sensitive with None value."""
        result = mask_sensitive(None)
        assert result == "Not Provided"

    def test_mask_sensitive_short_value(self):
        """Test mask_sensitive with short value."""
        result = mask_sensitive("ab")
        assert result == "**"  # Too short to show any characters

    def test_mask_sensitive_normal_value(self):
        """Test mask_sensitive with normal value."""
        result = mask_sensitive("secret-api-key-12345")
        assert result == "secr************2345"  # First 4 and last 4 characters

    def test_mask_sensitive_custom_keep_chars(self):
        """Test mask_sensitive with custom keep_chars parameter."""
        result = mask_sensitive("secret-api-key-12345", keep_chars=2)
        assert result == "se****************45"  # First 2 and last 2 characters

    def test_mask_sensitive_exact_boundary(self):
        """Test mask_sensitive with value exactly at boundary."""
        result = mask_sensitive("12345678", keep_chars=4)
        assert result == "********"  # Fully masked when length <= keep_chars * 2

    def test_get_masked_session_headers(self):
        """Test get_masked_session_headers function."""
        headers = {
            "Authorization": "Bearer secret-token-123",
            "Content-Type": "application/json",
            "X-Custom": "custom-value",
            "Cookie": "session=abc123"
        }

        masked = get_masked_session_headers(headers)

        # Check Authorization header is masked
        assert masked["Authorization"].startswith("Bearer ")
        assert "secret-token-123" not in masked["Authorization"]
        # Check that it follows the consistent mask_sensitive pattern
        assert "Bearer secr********-123" in masked["Authorization"]

        # Check non-sensitive headers are unchanged
        assert masked["Content-Type"] == "application/json"
        assert masked["X-Custom"] == "custom-value"

        # Check Cookie header is masked
        assert masked["Cookie"] == "*****"

    def test_get_masked_session_headers_basic_auth(self):
        """Test get_masked_session_headers with Basic auth."""
        headers = {
            "Authorization": "Basic dXNlcjpwYXNzd29yZA=="
        }

        masked = get_masked_session_headers(headers)

        assert masked["Authorization"].startswith("Basic ")
        assert "dXNlcjpwYXNzd29yZA==" not in masked["Authorization"]
        # Check that it follows the consistent mask_sensitive pattern
        assert "Basic dXNl************ZA==" in masked["Authorization"]

    def test_get_masked_session_headers_unknown_auth_type(self):
        """Test get_masked_session_headers with unknown auth type."""
        headers = {
            "Authorization": "Custom token123"
        }

        masked = get_masked_session_headers(headers)

        assert masked["Authorization"] == "*****"

    def test_get_masked_session_headers_no_auth_header(self):
        """Test get_masked_session_headers without Authorization header."""
        headers = {
            "Content-Type": "application/json",
            "Accept": "application/json"
        }

        masked = get_masked_session_headers(headers)

        assert masked["Content-Type"] == "application/json"
        assert masked["Accept"] == "application/json"
        assert "Authorization" not in masked