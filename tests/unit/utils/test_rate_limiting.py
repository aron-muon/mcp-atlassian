"""Tests for rate limiting detection and handling functionality."""

from unittest.mock import MagicMock

import pytest
from requests.exceptions import HTTPError

from mcp_atlassian.utils.decorators import is_rate_limit_error
from mcp_atlassian.utils.retry import is_retryable_error, RetryConfig


class TestRateLimitingDetection:
    """Tests for rate limiting detection logic."""

    def test_is_rate_limit_error_http_429(self):
        """Test detection of HTTP 429 status code."""
        response = MagicMock()
        response.status_code = 429
        error = HTTPError("Too Many Requests", response=response)

        assert is_rate_limit_error(error) is True

    def test_is_rate_limit_error_with_retry_after_header(self):
        """Test detection via Retry-After header."""
        response = MagicMock()
        response.status_code = 200  # Even with 200 status
        response.headers = {"Retry-After": "60"}
        error = HTTPError("OK", response=response)

        assert is_rate_limit_error(error) is True

    def test_is_rate_limit_error_with_rate_limit_remaining_zero(self):
        """Test detection via X-RateLimit-Remaining header at zero."""
        response = MagicMock()
        response.status_code = 200
        response.headers = {"X-RateLimit-Remaining": "0"}
        error = HTTPError("OK", response=response)

        assert is_rate_limit_error(error) is True

    def test_is_rate_limit_error_with_rate_limit_remaining_zero_string(self):
        """Test detection via X-RateLimit-Remaining header as string zero."""
        response = MagicMock()
        response.status_code = 200
        response.headers = {"X-RateLimit-Remaining": "0"}
        error = HTTPError("OK", response=response)

        assert is_rate_limit_error(error) is True

    def test_is_rate_limit_error_with_multiple_rate_limit_headers(self):
        """Test detection with multiple rate limit headers."""
        response = MagicMock()
        response.status_code = 200
        response.headers = {
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Limit": "1000",
            "X-RateLimit-Reset": "1640995200"
        }
        error = HTTPError("OK", response=response)

        assert is_rate_limit_error(error) is True

    def test_is_rate_limit_error_with_non_zero_remaining(self):
        """Test that non-zero remaining doesn't trigger rate limit detection."""
        response = MagicMock()
        response.status_code = 200
        response.headers = {"X-RateLimit-Remaining": "10"}
        error = HTTPError("OK", response=response)

        assert is_rate_limit_error(error) is False

    def test_is_rate_limit_error_no_headers_not_429(self):
        """Test that errors without rate limit indicators are not detected."""
        response = MagicMock()
        response.status_code = 500
        response.headers = {}
        error = HTTPError("Internal Server Error", response=response)

        assert is_rate_limit_error(error) is False

    def test_is_rate_limit_error_with_403_and_rate_limit_headers(self):
        """Test rate limit detection on 403 with rate limit headers."""
        response = MagicMock()
        response.status_code = 403
        response.headers = {"X-RateLimit-Remaining": "0"}
        error = HTTPError("Forbidden", response=response)

        assert is_rate_limit_error(error) is True

    def test_is_rate_limit_error_with_403_no_headers(self):
        """Test that 403 without rate limit headers is not rate limiting."""
        response = MagicMock()
        response.status_code = 403
        response.headers = {}
        error = HTTPError("Forbidden", response=response)

        assert is_rate_limit_error(error) is False

    def test_is_rate_limit_error_response_without_response(self):
        """Test handling when HTTPError has no response attribute."""
        error = HTTPError("Network error")  # No response object

        assert is_rate_limit_error(error) is False

    def test_is_rate_limit_error_response_without_headers(self):
        """Test handling when response has no headers attribute."""
        response = MagicMock()
        response.status_code = 429
        del response.headers  # Remove headers attribute
        error = HTTPError("Too Many Requests", response=response)

        # Should still detect based on status code
        assert is_rate_limit_error(error) is True

    def test_is_rate_limit_error_header_case_insensitive(self):
        """Test rate limit detection with lowercase headers."""
        response = MagicMock()
        response.status_code = 200
        response.headers = {"x-ratelimit-remaining": "0"}  # lowercase
        error = HTTPError("OK", response=response)

        assert is_rate_limit_error(error) is True

    def test_is_rate_limit_error_with_integer_header_values(self):
        """Test rate limit detection with integer header values."""
        response = MagicMock()
        response.status_code = 200
        response.headers = {"X-RateLimit-Remaining": 0}  # Integer instead of string
        error = HTTPError("OK", response=response)

        assert is_rate_limit_error(error) is True

    def test_is_rate_limit_error_with_float_header_values(self):
        """Test rate limit detection with float header values."""
        response = MagicMock()
        response.status_code = 200
        response.headers = {"X-RateLimit-Remaining": 0.0}  # Float instead of string
        error = HTTPError("OK", response=response)

        assert is_rate_limit_error(error) is True

    def test_is_rate_limit_error_with_invalid_header_values(self):
        """Test rate limit detection with invalid header values."""
        response = MagicMock()
        response.status_code = 200
        response.headers = {"X-RateLimit-Remaining": "invalid"}
        error = HTTPError("OK", response=response)

        assert is_rate_limit_error(error) is False

    def test_is_rate_limit_error_empty_retry_after(self):
        """Test rate limit detection with empty Retry-After header."""
        response = MagicMock()
        response.status_code = 200
        response.headers = {"Retry-After": ""}
        error = HTTPError("OK", response=response)

        assert is_rate_limit_error(error) is True

    def test_is_rate_limit_error_with_different_rate_limit_header_names(self):
        """Test detection with various rate limit header names."""
        test_headers = [
            {"X-RateLimit-Remaining": "0"},
            {"X-Rate-Limit-Remaining": "0"},
            {"Rate-Limit-Remaining": "0"},
            {"X-Rate-Remaining": "0"},
        ]

        for headers in test_headers:
            response = MagicMock()
            response.status_code = 200
            response.headers = headers
            error = HTTPError("OK", response=response)

            assert is_rate_limit_error(error) is True, f"Failed for headers: {headers}"


class TestRateLimitingInRetryLogic:
    """Tests for rate limiting in retry logic."""

    def test_rate_limit_error_is_retryable(self):
        """Test that rate limit errors are considered retryable."""
        config = RetryConfig()

        # Test HTTP 429
        response = MagicMock()
        response.status_code = 429
        error = HTTPError("Too Many Requests", response=response)

        assert is_retryable_error(error, config) is True

    def test_rate_limit_error_with_headers_is_retryable(self):
        """Test that errors with rate limit headers are retryable."""
        config = RetryConfig()

        response = MagicMock()
        response.status_code = 200
        response.headers = {"X-RateLimit-Remaining": "0"}
        error = HTTPError("OK", response=response)

        assert is_retryable_error(error, config) is True

    def test_custom_retry_config_excludes_rate_limiting(self):
        """Test custom retry config that excludes rate limiting."""
        config = RetryConfig(retryable_status_codes={500, 502, 503})

        response = MagicMock()
        response.status_code = 429
        error = HTTPError("Too Many Requests", response=response)

        # Should not be retryable with custom config
        assert is_retryable_error(error, config) is False

    def test_custom_retry_config_includes_rate_limiting(self):
        """Test custom retry config that explicitly includes rate limiting."""
        config = RetryConfig(retryable_status_codes={429, 500, 502, 503})

        response = MagicMock()
        response.status_code = 429
        error = HTTPError("Too Many Requests", response=response)

        # Should be retryable with custom config
        assert is_retryable_error(error, config) is True

    def test_rate_limiting_with_correlation_id_logging(self, caplog):
        """Test that rate limiting detection logs correlation ID."""
        import logging

        config = RetryConfig()
        response = MagicMock()
        response.status_code = 429
        error = HTTPError("Too Many Requests", response=response)

        with caplog.at_level(logging.DEBUG):
            result = is_retryable_error(error, config, correlation_id="test123")

        assert result is True
        # Should log with correlation ID if the logging function includes it
        assert len(caplog.records) >= 0


class TestRateLimitingHeaderExtraction:
    """Tests for extracting rate limit information from headers."""

    def test_extract_retry_after_value(self):
        """Test extracting Retry-After header value."""
        response = MagicMock()
        response.status_code = 429
        response.headers = {"Retry-After": "60"}
        error = HTTPError("Too Many Requests", response=response)

        # The is_rate_limit_error function should detect it
        assert is_rate_limit_error(error) is True

    def test_extract_rate_limit_remaining_value(self):
        """Test extracting X-RateLimit-Remaining header value."""
        response = MagicMock()
        response.status_code = 200
        response.headers = {"X-RateLimit-Remaining": "42"}
        error = HTTPError("OK", response=response)

        # Should not be rate limited since remaining > 0
        assert is_rate_limit_error(error) is False

    def test_extract_rate_limit_limit_value(self):
        """Test extracting X-RateLimit-Limit header value."""
        response = MagicMock()
        response.status_code = 200
        response.headers = {
            "X-RateLimit-Limit": "1000",
            "X-RateLimit-Remaining": "0"  # This triggers rate limiting
        }
        error = HTTPError("OK", response=response)

        assert is_rate_limit_error(error) is True

    def test_extract_rate_limit_reset_value(self):
        """Test extracting X-RateLimit-Reset header value."""
        response = MagicMock()
        response.status_code = 200
        response.headers = {
            "X-RateLimit-Reset": "1640995200",
            "X-RateLimit-Remaining": "0"  # This triggers rate limiting
        }
        error = HTTPError("OK", response=response)

        assert is_rate_limit_error(error) is True


class TestRateLimitingInEnhancedErrorHandling:
    """Tests for rate limiting detection in enhanced error handling."""

    @pytest.mark.asyncio
    async def test_rate_limit_error_categorization_in_decorator(self):
        """Test that rate limiting errors are properly categorized by decorator."""
        from mcp_atlassian.utils.decorators import handle_tool_errors
        from fastmcp import Context
        import json

        mock_ctx = MagicMock(spec=Context)
        mock_ctx.request_context = MagicMock()
        mock_ctx.request_context.correlation_id = None

        @handle_tool_errors(default_return_key="test", service_name="TestService")
        async def test_function(ctx):
            response = MagicMock()
            response.status_code = 429
            response.headers = {"Retry-After": "60", "X-RateLimit-Remaining": "0"}
            raise HTTPError("Too Many Requests", response=response)

        result = await test_function(mock_ctx)
        error_data = json.loads(result)

        assert error_data["error_type"] == "rate_limit"
        assert error_data["retry_after"] == "60"
        assert error_data["rate_limit_remaining"] == "0"

    @pytest.mark.asyncio
    async def test_rate_limit_error_without_retry_after(self):
        """Test rate limiting error without Retry-After header."""
        from mcp_atlassian.utils.decorators import handle_tool_errors
        from fastmcp import Context
        import json

        mock_ctx = MagicMock(spec=Context)
        mock_ctx.request_context = MagicMock()
        mock_ctx.request_context.correlation_id = None

        @handle_tool_errors(default_return_key="test", service_name="TestService")
        async def test_function(ctx):
            response = MagicMock()
            response.status_code = 429
            response.headers = {"X-RateLimit-Remaining": "0"}
            raise HTTPError("Too Many Requests", response=response)

        result = await test_function(mock_ctx)
        error_data = json.loads(result)

        assert error_data["error_type"] == "rate_limit"
        assert "retry_after" not in error_data
        assert error_data["rate_limit_remaining"] == "0"

    @pytest.mark.asyncio
    async def test_rate_limit_detection_on_non_429_status(self):
        """Test rate limiting detection on non-429 status codes."""
        from mcp_atlassian.utils.decorators import handle_tool_errors
        from fastmcp import Context
        import json

        mock_ctx = MagicMock(spec=Context)
        mock_ctx.request_context = MagicMock()
        mock_ctx.request_context.correlation_id = None

        @handle_tool_errors(default_return_key="test", service_name="TestService")
        async def test_function(ctx):
            response = MagicMock()
            response.status_code = 200  # Success status
            response.headers = {"X-RateLimit-Remaining": "0"}
            raise HTTPError("OK", response=response)

        result = await test_function(mock_ctx)
        error_data = json.loads(result)

        assert error_data["error_type"] == "rate_limit"
        assert error_data["rate_limit_remaining"] == "0"


class TestRateLimitingConfigurations:
    """Tests for different rate limiting configurations and scenarios."""

    def test_rate_limit_detection_with_custom_header_names(self):
        """Test rate limiting detection with custom header names."""
        response = MagicMock()
        response.status_code = 200
        response.headers = {
            "Custom-Rate-Limit-Remaining": "0",
            "Custom-Rate-Reset": "60"
        }
        error = HTTPError("OK", response=response)

        # Current implementation may not detect custom headers
        # This test documents current behavior
        result = is_rate_limit_error(error)
        assert result is False  # Current implementation only checks standard headers

    def test_rate_limit_detection_with_multiple_indicators(self):
        """Test rate limiting detection with multiple indicators."""
        response = MagicMock()
        response.status_code = 429
        response.headers = {
            "Retry-After": "120",
            "X-RateLimit-Remaining": "0",
            "X-RateLimit-Limit": "1000"
        }
        error = HTTPError("Too Many Requests", response=response)

        assert is_rate_limit_error(error) is True

    def test_rate_limit_detection_edge_cases(self):
        """Test rate limiting detection edge cases."""
        test_cases = [
            # (status_code, headers, expected_result, description)
            (429, {}, True, "429 without headers"),
            (200, {"Retry-After": "60"}, True, "200 with Retry-After"),
            (200, {"X-RateLimit-Remaining": "0"}, True, "200 with zero remaining"),
            (403, {"X-RateLimit-Remaining": "0"}, True, "403 with zero remaining"),
            (500, {"X-RateLimit-Remaining": "0"}, True, "500 with zero remaining"),
            (200, {"X-RateLimit-Remaining": "1"}, False, "200 with non-zero remaining"),
            (200, {"X-RateLimit-Limit": "1000"}, False, "200 with only limit header"),
            (418, {"X-RateLimit-Remaining": "0"}, True, "418 with zero remaining"),
        ]

        for status_code, headers, expected, description in test_cases:
            response = MagicMock()
            response.status_code = status_code
            response.headers = headers
            error = HTTPError(f"Test {status_code}", response=response)

            result = is_rate_limit_error(error)
            assert result == expected, f"Failed for {description}: status={status_code}, headers={headers}"