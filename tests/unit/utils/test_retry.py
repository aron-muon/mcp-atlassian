"""Tests for retry mechanism functionality."""

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import requests
from requests.exceptions import HTTPError, ConnectionError

from mcp_atlassian.utils.retry import (
    RetryConfig,
    async_retry_with_backoff,
    is_retryable_error,
    calculate_delay,
    retry_with_backoff,
    DEFAULT_RETRY_CONFIG,
    AGGRESSIVE_RETRY_CONFIG,
    CONSERVATIVE_RETRY_CONFIG,
    RATE_LIMIT_RETRY_CONFIG,
)


class TestRetryConfig:
    """Tests for the RetryConfig class."""

    def test_default_retry_config(self):
        """Test default retry configuration."""
        config = RetryConfig()

        assert config.max_attempts == 3
        assert config.base_delay == 1.0
        assert config.max_delay == 60.0
        assert config.exponential_base == 2.0
        assert config.jitter is True
        assert 429 in config.retryable_status_codes
        assert 500 in config.retryable_status_codes
        assert HTTPError in config.retryable_exceptions

    def test_custom_retry_config(self):
        """Test custom retry configuration."""
        config = RetryConfig(
            max_attempts=5,
            base_delay=2.0,
            max_delay=120.0,
            exponential_base=3.0,
            jitter=False
        )

        assert config.max_attempts == 5
        assert config.base_delay == 2.0
        assert config.max_delay == 120.0
        assert config.exponential_base == 3.0
        assert config.jitter is False

    def test_retry_config_with_custom_retryable_status_codes(self):
        """Test retry config with custom retryable status codes."""
        custom_codes = {408, 429, 502}
        config = RetryConfig(retryable_status_codes=custom_codes)

        assert config.retryable_status_codes == custom_codes
        assert 408 in config.retryable_status_codes
        assert 429 in config.retryable_status_codes
        assert 502 in config.retryable_status_codes
        assert 500 not in config.retryable_status_codes  # Not in custom set

    def test_retry_config_with_custom_retryable_exceptions(self):
        """Test retry config with custom retryable exceptions."""
        custom_exceptions = (TimeoutError, OSError)
        config = RetryConfig(retryable_exceptions=custom_exceptions)

        assert config.retryable_exceptions == custom_exceptions
        assert TimeoutError in config.retryable_exceptions
        assert OSError in config.retryable_exceptions
        assert HTTPError not in config.retryable_exceptions  # Not in custom set


class TestIsRetryableError:
    """Tests for is_retryable_error function."""

    def test_retryable_request_exception(self):
        """Test that RequestException is retryable."""
        error = RequestException("Connection failed")
        assert is_retryable_error(error, RetryConfig()) is True

    def test_retryable_connection_error(self):
        """Test that ConnectionError is retryable."""
        error = ConnectionError("Connection refused")
        assert is_retryable_error(error, RetryConfig()) is True

    def test_retryable_timeout_error(self):
        """Test that TimeoutError is retryable."""
        error = TimeoutError("Request timed out")
        assert is_retryable_error(error, RetryConfig()) is True

    def test_non_retryable_value_error(self):
        """Test that ValueError is not retryable."""
        error = ValueError("Invalid input")
        assert is_retryable_error(error, RetryConfig()) is False

    def test_retryable_http_429_error(self):
        """Test that HTTP 429 errors are retryable."""
        response = MagicMock()
        response.status_code = 429
        error = HTTPError("Too Many Requests", response=response)
        assert is_retryable_error(error, RetryConfig()) is True

    def test_retryable_http_500_error(self):
        """Test that HTTP 500 errors are retryable."""
        response = MagicMock()
        response.status_code = 500
        error = HTTPError("Internal Server Error", response=response)
        assert is_retryable_error(error, RetryConfig()) is True

    def test_non_retryable_http_404_error(self):
        """Test that HTTP 404 errors are not retryable."""
        response = MagicMock()
        response.status_code = 404
        error = HTTPError("Not Found", response=response)
        assert is_retryable_error(error, RetryConfig()) is False

    def test_rate_limit_header_detection(self):
        """Test rate limit detection via headers."""
        response = MagicMock()
        response.status_code = 200
        response.headers = {"X-RateLimit-Remaining": "0"}
        error = HTTPError("OK", response=response)
        assert is_retryable_error(error, RetryConfig()) is True

    def test_custom_retryable_status_codes(self):
        """Test custom retryable status codes."""
        config = RetryConfig(retryable_status_codes={408})

        response = MagicMock()
        response.status_code = 408
        error = HTTPError("Request Timeout", response=response)
        assert is_retryable_error(error, config) is True

        response.status_code = 404
        error = HTTPError("Not Found", response=response)
        assert is_retryable_error(error, config) is False

    def test_correlation_id_logging(self, caplog):
        """Test that correlation ID is included in debug logs."""
        error = HTTPError("Test error")
        with caplog.at_level(logging.DEBUG):
            result = is_retryable_error(error, RetryConfig(), correlation_id="abc123")

        assert result is True
        assert any("abc123" in record.getMessage() for record in caplog.records)


class TestCalculateDelay:
    """Tests for calculate_delay function."""

    def test_calculate_delay_no_jitter(self):
        """Test delay calculation without jitter."""
        config = RetryConfig(jitter=False)

        # First attempt (attempt=0): base_delay * exponential_base^0
        delay = calculate_delay(0, config, "test123")
        assert delay == config.base_delay  # 1.0 * 2.0^0 = 1.0

        # Second attempt (attempt=1): base_delay * exponential_base^1
        delay = calculate_delay(1, config, "test123")
        assert delay == config.base_delay * config.exponential_base  # 1.0 * 2.0^1 = 2.0

        # Third attempt (attempt=2): base_delay * exponential_base^2
        delay = calculate_delay(2, config, "test123")
        assert delay == config.base_delay * (config.exponential_base ** 2)  # 1.0 * 2.0^2 = 4.0

    def test_calculate_delay_with_max_limit(self):
        """Test delay calculation respects max_delay limit."""
        config = RetryConfig(base_delay=10.0, max_delay=50.0, jitter=False, exponential_base=3.0)

        # Should hit max_delay: 10.0 * 3.0^2 = 90.0, capped at 50.0
        delay = calculate_delay(2, config, "test123")
        assert delay == 50.0

    def test_calculate_delay_with_jitter(self):
        """Test delay calculation with jitter enabled."""
        config = RetryConfig(jitter=True, base_delay=1.0)

        # Jitter should make delay vary, but stay within reasonable bounds
        delays = [calculate_delay(1, config, f"test{i}") for i in range(10)]

        # All delays should be close to expected (2.0s) but with some variation
        for delay in delays:
            assert 0.8 <= delay <= 2.2  # Allow 20% jitter

    def test_calculate_delay_negative_delay_handling(self):
        """Test that calculated delay is never negative."""
        config = RetryConfig(jitter=True)

        # Even with negative jitter, delay should not be negative
        for _ in range(100):
            delay = calculate_delay(1, config, "test")
            assert delay >= 0


class TestAsyncRetryWithBackoff:
    """Tests for async_retry_with_backoff function."""

    @pytest.mark.asyncio
    async def test_successful_execution_no_retry(self):
        """Test successful function execution doesn't retry."""
        mock_function = AsyncMock(return_value="success")

        result = await async_retry_with_backoff(
            mock_function, DEFAULT_RETRY_CONFIG, "test123"
        )

        assert result == "success"
        mock_function.assert_called_once()

    @pytest.mark.asyncio
    async def test_retry_on_retryable_error(self):
        """Test retry on retryable error."""
        call_count = 0

        async def failing_function():
            nonlocal call_count
            call_count += 1
            if call_count < 3:
                raise ConnectionError("Connection failed")
            return "success"

        result = await async_retry_with_backoff(
            failing_function, DEFAULT_RETRY_CONFIG, "test123"
        )

        assert result == "success"
        assert call_count == 3

    @pytest.mark.asyncio
    async def test_no_retry_on_non_retryable_error(self):
        """Test no retry on non-retryable error."""
        failing_function = AsyncMock(side_effect=ValueError("Invalid input"))

        with pytest.raises(ValueError, match="Invalid input"):
            await async_retry_with_backoff(
                failing_function, DEFAULT_RETRY_CONFIG, "test123"
            )

        failing_function.assert_called_once()

    @pytest.mark.asyncio
    async def test_retry_exhaustion(self):
        """Test behavior when retry attempts are exhausted."""
        call_count = 0

        async def always_failing_function():
            nonlocal call_count
            call_count += 1
            raise ConnectionError("Always fails")

        config = RetryConfig(max_attempts=2)

        with pytest.raises(ConnectionError, match="Always fails"):
            await async_retry_with_backoff(
                always_failing_function, config, "test123"
            )

        assert call_count == 2  # Should be called max_attempts times

    @pytest.mark.asyncio
    @patch('asyncio.sleep')
    async def test_retry_delay_timing(self, mock_sleep):
        """Test that retry delays are applied correctly."""
        call_count = 0

        async def failing_function():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Connection failed")
            return "success"

        config = RetryConfig(max_attempts=3, base_delay=0.1, jitter=False)

        result = await async_retry_with_backoff(
            failing_function, config, "test123"
        )

        assert result == "success"
        assert call_count == 2
        # Should have slept once before the second attempt
        assert mock_sleep.call_count == 1
        assert mock_sleep.call_args[0][0] == 0.2  # base_delay * exponential_base^1


class TestRetryWithBackoffDecorator:
    """Tests for retry_with_backoff decorator."""

    @pytest.mark.asyncio
    async def test_decorator_successful_execution(self):
        """Test decorator on successful function."""
        mock_function = AsyncMock(return_value="success")

        @retry_with_backoff()
        async def test_function():
            return await mock_function()

        result = await test_function()

        assert result == "success"
        mock_function.assert_called_once()

    @pytest.mark.asyncio
    async def test_decorator_with_custom_config(self):
        """Test decorator with custom retry configuration."""
        call_count = 0

        @retry_with_backoff(config=RetryConfig(max_attempts=2))
        async def test_function():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Connection failed")
            return "success"

        result = await test_function()

        assert result == "success"
        assert call_count == 2

    def test_decorator_sync_function(self):
        """Test decorator on synchronous function."""
        call_count = 0

        @retry_with_backoff()
        def test_function():
            nonlocal call_count
            call_count += 1
            if call_count < 2:
                raise ConnectionError("Connection failed")
            return "success"

        result = test_function()

        assert result == "success"
        assert call_count == 2

    @pytest.mark.asyncio
    async def test_predefined_configurations(self):
        """Test that predefined retry configurations work."""
        # Test conservative config
        conservative_config = CONSERVATIVE_RETRY_CONFIG
        assert conservative_config.max_attempts == 2
        assert conservative_config.base_delay == 2.0

        # Test aggressive config
        aggressive_config = AGGRESSIVE_RETRY_CONFIG
        assert aggressive_config.max_attempts == 5
        assert aggressive_config.base_delay == 0.5

        # Test rate limit config
        rate_limit_config = RATE_LIMIT_RETRY_CONFIG
        assert rate_limit_config.max_attempts == 4
        assert rate_limit_config.base_delay == 2.0
        assert 429 in rate_limit_config.retryable_status_codes