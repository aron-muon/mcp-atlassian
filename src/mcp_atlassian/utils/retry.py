"""Retry utilities for MCP Atlassian.

This module provides retry mechanisms for handling transient failures
in API calls, with exponential backoff and rate limit awareness.
"""

import asyncio
import logging
import random
import time
from collections.abc import Callable
from functools import wraps
from typing import Any, TypeVar

import requests
from requests.exceptions import HTTPError, RequestException

logger = logging.getLogger(__name__)

F = TypeVar("F", bound=Callable[..., Any])


class RetryConfig:
    """Configuration for retry behavior."""

    def __init__(
        self,
        max_attempts: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        exponential_base: float = 2.0,
        jitter: bool = True,
        retryable_status_codes: set[int] | None = None,
        retryable_exceptions: tuple[type[Exception], ...] | None = None,
    ):
        self.max_attempts = max_attempts
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.exponential_base = exponential_base
        self.jitter = jitter

        # Default retryable status codes
        if retryable_status_codes is None:
            retryable_status_codes = {
                408,  # Request Timeout
                429,  # Too Many Requests (Rate Limited)
                500,  # Internal Server Error
                502,  # Bad Gateway
                503,  # Service Unavailable
                504,  # Gateway Timeout
                507,  # Insufficient Storage
                509,  # Bandwidth Limit Exceeded
                520,  # Unknown Error (Cloudflare)
                521,  # Web Server Is Down (Cloudflare)
                522,  # Connection Timed Out (Cloudflare)
                523,  # Origin Is Unreachable (Cloudflare)
                524,  # A Timeout Occurred (Cloudflare)
            }
        self.retryable_status_codes = retryable_status_codes

        # Default retryable exceptions
        if retryable_exceptions is None:
            retryable_exceptions = (
                RequestException,
                ConnectionError,
                TimeoutError,
            )
        self.retryable_exceptions = retryable_exceptions


def is_retryable_error(
    error: Exception, config: RetryConfig, correlation_id: str | None = None
) -> bool:
    """
    Determine if an error is retryable based on the configuration.

    Args:
        error: The exception that occurred
        config: Retry configuration
        correlation_id: Optional correlation ID for logging

    Returns:
        True if the error is retryable, False otherwise
    """
    # Check for retryable exceptions
    if isinstance(error, config.retryable_exceptions):
        logger.debug(
            f"[{correlation_id}] Retryable exception detected: {type(error).__name__}: {error}"
        )
        return True

    # Check for HTTP errors with retryable status codes
    if isinstance(error, HTTPError) and hasattr(error, 'response') and error.response is not None:
        status_code = error.response.status_code
        if status_code in config.retryable_status_codes:
            logger.debug(
                f"[{correlation_id}] Retryable HTTP status code: {status_code}"
            )
            return True

        # Check for rate limit headers
        if hasattr(error.response, 'headers'):
            rate_limit_remaining = error.response.headers.get('X-RateLimit-Remaining')
            if rate_limit_remaining == '0':
                logger.debug(
                    f"[{correlation_id}] Rate limit exhausted (X-RateLimit-Remaining: 0)"
                )
                return True

    return False


def calculate_delay(attempt: int, config: RetryConfig, correlation_id: str | None = None) -> float:
    """
    Calculate delay before next retry attempt.

    Args:
        attempt: Current attempt number (0-based)
        config: Retry configuration
        correlation_id: Optional correlation ID for logging

    Returns:
        Delay in seconds
    """
    delay = config.base_delay * (config.exponential_base ** attempt)
    delay = min(delay, config.max_delay)

    if config.jitter:
        # Add random jitter to avoid thundering herd
        jitter_range = delay * 0.1
        delay += random.uniform(-jitter_range, jitter_range)

    delay = max(0, delay)  # Ensure non-negative

    logger.debug(
        f"[{correlation_id}] Calculated delay for attempt {attempt + 1}: {delay:.2f}s"
    )
    return delay


async def async_retry_with_backoff(
    func: Callable,
    config: RetryConfig,
    *args: Any,
    correlation_id: str | None = None,
    **kwargs: Any,
) -> Any:
    """
    Execute an async function with retry logic and exponential backoff.

    Args:
        func: The async function to execute
        config: Retry configuration
        correlation_id: Optional correlation ID for logging
        *args: Function arguments
        **kwargs: Function keyword arguments

    Returns:
        The result of the function call

    Raises:
        The last exception if all retries are exhausted
    """
    last_exception = None

    for attempt in range(config.max_attempts):
        try:
            if attempt > 0:
                delay = calculate_delay(attempt, config, correlation_id)
                logger.info(
                    f"[{correlation_id}] Retrying after {delay:.2f}s (attempt {attempt + 1}/{config.max_attempts})"
                )
                await asyncio.sleep(delay)

            result = await func(*args, **kwargs)

            if attempt > 0:
                logger.info(
                    f"[{correlation_id}] Retry successful on attempt {attempt + 1}"
                )

            return result

        except Exception as e:
            last_exception = e

            if attempt == config.max_attempts - 1:
                logger.error(
                    f"[{correlation_id}] All {config.max_attempts} retry attempts exhausted"
                )
                break

            if not is_retryable_error(e, config, correlation_id):
                logger.warning(
                    f"[{correlation_id}] Non-retryable error encountered: {type(e).__name__}: {e}"
                )
                break

            logger.warning(
                f"[{correlation_id}] Attempt {attempt + 1} failed with retryable error: {type(e).__name__}: {e}"
            )

    # Re-raise the last exception
    if last_exception is not None:
        raise last_exception


def retry_with_backoff(
    config: RetryConfig | None = None,
) -> Callable:
    """
    Decorator for retrying functions with exponential backoff.

    Args:
        config: Retry configuration (uses default if None)

    Returns:
        Decorated function with retry logic

    Example:
        @retry_with_backoff(max_attempts=3, base_delay=1.0)
        async def api_call():
            return await some_api_request()
    """
    if config is None:
        config = RetryConfig()

    def decorator(func: F) -> F:
        @wraps(func)
        async def async_wrapper(*args: Any, **kwargs: Any) -> Any:
            # Extract correlation ID from first argument if it's a context object
            correlation_id = None
            if args and hasattr(args[0], 'request_context'):
                correlation_id = getattr(args[0].request_context, 'correlation_id', None)

            return await async_retry_with_backoff(
                func, config, *args, correlation_id=correlation_id, **kwargs
            )

        @wraps(func)
        def sync_wrapper(*args: Any, **kwargs: Any) -> Any:
            # For synchronous functions (not commonly used in this codebase)
            last_exception = None

            for attempt in range(config.max_attempts):
                try:
                    if attempt > 0:
                        delay = calculate_delay(attempt, config)
                        time.sleep(delay)

                    return func(*args, **kwargs)

                except Exception as e:
                    last_exception = e

                    if attempt == config.max_attempts - 1:
                        break

                    if not is_retryable_error(e, config):
                        break

                    logger.warning(
                        f"Attempt {attempt + 1} failed with retryable error: {type(e).__name__}: {e}"
                    )

            if last_exception is not None:
                raise last_exception

        # Return appropriate wrapper based on function type
        if asyncio.iscoroutinefunction(func):
            return async_wrapper  # type: ignore
        else:
            return sync_wrapper  # type: ignore

    return decorator


# Predefined retry configurations
DEFAULT_RETRY_CONFIG = RetryConfig(
    max_attempts=3,
    base_delay=1.0,
    max_delay=30.0,
)

AGGRESSIVE_RETRY_CONFIG = RetryConfig(
    max_attempts=5,
    base_delay=0.5,
    max_delay=60.0,
)

CONSERVATIVE_RETRY_CONFIG = RetryConfig(
    max_attempts=2,
    base_delay=2.0,
    max_delay=10.0,
)

RATE_LIMIT_RETRY_CONFIG = RetryConfig(
    max_attempts=4,
    base_delay=2.0,
    max_delay=120.0,
    retryable_status_codes={429, 500, 502, 503, 504},
)