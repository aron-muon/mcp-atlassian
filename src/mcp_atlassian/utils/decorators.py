import json
import logging
import uuid
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import Any, TypeVar

import requests
from fastmcp import Context
from requests.exceptions import HTTPError

from mcp_atlassian.exceptions import MCPAtlassianAuthenticationError
from mcp_atlassian.utils.retry import async_retry_with_backoff, RetryConfig

logger = logging.getLogger(__name__)


F = TypeVar("F", bound=Callable[..., Awaitable[Any]])


def is_rate_limit_error(error: HTTPError) -> bool:
    """Detect if an error is due to rate limiting.

    Args:
        error: HTTPError to check

    Returns:
        True if the error indicates rate limiting
    """
    if not hasattr(error, 'response') or not error.response:
        return False

    status_code = getattr(error.response, 'status_code', None)
    headers = getattr(error.response, 'headers', {})

    # Check for 429 status code
    if status_code == 429:
        return True

    # Check for Retry-After header (even empty string indicates rate limiting)
    if 'Retry-After' in headers:
        return True

    # Check for rate limit remaining at zero (handle various header names and value types)
    rate_limit_headers = [
        'X-RateLimit-Remaining',
        'x-ratelimit-remaining',
        'X-Rate-Limit-Remaining',
        'Rate-Limit-Remaining',
        'X-Rate-Remaining',
        'RateLimit-Remaining',
    ]

    for header_name in rate_limit_headers:
        rate_limit_remaining = headers.get(header_name)
        if rate_limit_remaining is not None:
            try:
                # Convert to string for comparison, then to int for numeric check
                if str(rate_limit_remaining) == '0' or int(rate_limit_remaining) == 0:
                    return True
            except (ValueError, TypeError):
                # If we can't parse the value, continue with other checks
                pass

    return False


def check_write_access(service_name_or_func: str | F = "Service") -> Callable:
    """
    Decorator for FastMCP tools to check if the application is in read-only mode.
    If in read-only mode, it raises a ValueError.
    Assumes the decorated function is async and has `ctx: Context` as its first argument.

    Can be used in two ways:
    1. @check_write_access (uses default service name "Service")
    2. @check_write_access("Jira") (specifies service name)

    Args:
        service_name_or_func: Either the service name or the function being decorated
    """

    # Check if this is being called as @check_write_access (without parameters)
    if callable(service_name_or_func):
        # Direct decorator usage: @check_write_access
        func = service_name_or_func
        service_name = "Service"
    else:
        # Parameterized decorator usage: @check_write_access("Jira")
        service_name = service_name_or_func
        # Return the actual decorator that will be applied to the function
        def decorator(func: F) -> F:
            return _create_wrapper(func, service_name)
        return decorator

    # For direct usage, create and return the wrapped function
    return _create_wrapper(func, service_name)


def _create_wrapper(func: F, service_name: str) -> F:
    """Create the actual wrapper function for check_write_access."""
    @wraps(func)
    async def wrapper(ctx: Context, *args: Any, **kwargs: Any) -> Any:
        lifespan_ctx_dict = ctx.request_context.lifespan_context
        app_lifespan_ctx = (
            lifespan_ctx_dict.get("app_lifespan_context")
            if isinstance(lifespan_ctx_dict, dict)
            else None
        )  # type: ignore

        if app_lifespan_ctx is not None and app_lifespan_ctx.read_only:
            tool_name = func.__name__
            action_description = tool_name.replace(
                "_", " "
            )  # e.g., "create_issue" -> "create issue"
            logger.warning(f"Attempted to call tool '{tool_name}' in read-only mode.")
            raise ValueError(f"Cannot {action_description} in read-only mode for {service_name}.")

        return await func(ctx, *args, **kwargs)

    return wrapper  # type: ignore


def handle_atlassian_api_errors(service_name: str = "Atlassian API") -> Callable:
    """
    Decorator to handle common Atlassian API exceptions (Jira, Confluence, etc.).

    Args:
        service_name: Name of the service for error logging (e.g., "Jira API").
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        def wrapper(self: Any, *args: Any, **kwargs: Any) -> Any:
            # Generate correlation ID for this API call
            correlation_id = str(uuid.uuid4())[:8]
            operation_name = getattr(func, "__name__", "API operation")

            try:
                return func(self, *args, **kwargs)
            except HTTPError as http_err:
                if http_err.response is not None and http_err.response.status_code in [
                    401,
                    403,
                ]:
                    error_msg = (
                        f"Authentication failed for {service_name} "
                        f"({http_err.response.status_code}). "
                        "Token may be expired or invalid. Please verify credentials."
                    )
                    logger.error(
                        f"[{correlation_id}] Authentication error in {operation_name}: {error_msg}",
                        extra={"correlation_id": correlation_id, "operation": operation_name, "service": service_name}
                    )
                    raise MCPAtlassianAuthenticationError(error_msg) from http_err
                else:
                    status_code = getattr(http_err.response, 'status_code', 'Unknown') if http_err.response else 'Unknown'
                    logger.error(
                        f"[{correlation_id}] HTTP {status_code} error during {operation_name}: {http_err}",
                        extra={
                            "correlation_id": correlation_id,
                            "operation": operation_name,
                            "service": service_name,
                            "status_code": status_code
                        },
                        exc_info=False,
                    )
                    raise http_err
            except KeyError as e:
                logger.error(
                    f"[{correlation_id}] Missing key in {operation_name} results: {str(e)}",
                    extra={"correlation_id": correlation_id, "operation": operation_name, "service": service_name}
                )
                return []
            except requests.RequestException as e:
                logger.error(
                    f"[{correlation_id}] Network error during {operation_name}: {str(e)}",
                    extra={"correlation_id": correlation_id, "operation": operation_name, "service": service_name}
                )
                return []
            except (ValueError, TypeError) as e:
                logger.error(
                    f"[{correlation_id}] Error processing {operation_name} results: {str(e)}",
                    extra={"correlation_id": correlation_id, "operation": operation_name, "service": service_name}
                )
                return []
            except Exception as e:  # noqa: BLE001 - Intentional fallback with logging
                logger.error(
                    f"[{correlation_id}] Unexpected error during {operation_name}: {str(e)}",
                    extra={"correlation_id": correlation_id, "operation": operation_name, "service": service_name}
                )
                logger.debug(
                    f"[{correlation_id}] Full exception details for {operation_name}:",
                    extra={"correlation_id": correlation_id},
                    exc_info=True
                )
                return []

        return wrapper

    return decorator


def handle_tool_errors(
    default_return_key: str = "data", service_name: str = "Service"
) -> Callable:
    """
    Decorator to handle exceptions in MCP tools and return formatted JSON error.

    Args:
        default_return_key: Key name for empty data in error response (e.g., "issue", "page")
        service_name: Service name for error messages (e.g., "Jira", "Confluence")

    Returns:
        JSON string with error message and empty data

    Example:
        @handle_tool_errors(default_return_key="issue", service_name="Jira")
        async def get_issue(ctx: Context, issue_key: str) -> str:
            jira = await get_jira_fetcher(ctx)
            issue = jira.get_issue(issue_key)
            return issue.model_dump_json()
    """

    def decorator(func: F) -> F:
        @wraps(func)
        async def wrapper(*args: Any, **kwargs: Any) -> str:
            # Extract context if available (first arg is usually ctx for MCP tools)
            ctx = None
            correlation_id = None

            if args and hasattr(args[0], 'request_context'):
                ctx = args[0]

            try:
                # Check for correlation ID right before executing function
                if args and hasattr(args[0], 'request_context') and hasattr(args[0].request_context, 'correlation_id'):
                    context_correlation_id = args[0].request_context.correlation_id
                    if context_correlation_id:
                        correlation_id = context_correlation_id
                        # Store in context for logging if not already there
                        if ctx and hasattr(ctx, 'request_context') and not hasattr(ctx.request_context, 'correlation_id'):
                            ctx.request_context.correlation_id = correlation_id

                # Generate correlation ID if none exists
                if not correlation_id:
                    correlation_id = str(uuid.uuid4())[:8]
                    # Store correlation ID in context for logging
                    if ctx and hasattr(ctx, 'request_context'):
                        ctx.request_context.correlation_id = correlation_id

                return await func(*args, **kwargs)
            except MCPAtlassianAuthenticationError as auth_err:
                # Re-capture correlation ID from context in case it was updated during function execution
                if args and hasattr(args[0], 'request_context') and hasattr(args[0].request_context, 'correlation_id'):
                    current_correlation_id = args[0].request_context.correlation_id
                    if current_correlation_id:
                        correlation_id = current_correlation_id

                error_details = {
                    "success": False,
                    "error": "Authentication Failed",
                    "error_type": "authentication",
                    "message": str(auth_err),
                    "correlation_id": correlation_id,
                    "service": service_name,
                    "tool": func.__name__,
                    default_return_key: {},
                }
                logger.error(
                    f"[{correlation_id}] Authentication error in {func.__name__}: {auth_err}",
                    extra={"correlation_id": correlation_id, "tool": func.__name__, "service": service_name}
                )
                return json.dumps(error_details, indent=2, ensure_ascii=False)

            except HTTPError as http_err:
                # Re-capture correlation ID from context in case it was updated during function execution
                if args and hasattr(args[0], 'request_context') and hasattr(args[0].request_context, 'correlation_id'):
                    current_correlation_id = args[0].request_context.correlation_id
                    if current_correlation_id:
                        correlation_id = current_correlation_id

                status_code = http_err.response.status_code if http_err.response else "Unknown"
                # Detect rate limiting
                is_rate_limit = status_code == 429 or (
                    hasattr(http_err.response, 'headers') and
                    http_err.response.headers.get('X-RateLimit-Remaining') == '0'
                )

                error_type = "rate_limit" if is_rate_limit else "http_error"
                error_code = f"HTTP_{status_code}"

                # Handle specific HTTP errors with better messages
                if status_code == 401:
                    message = f"Authentication failed for {service_name}. Please check your credentials."
                elif status_code == 403:
                    message = f"Access denied for {service_name}. You may not have permission to perform this operation."
                elif status_code == 404:
                    message = f"Resource not found in {service_name}."
                elif status_code == 429:
                    retry_after = None
                    if hasattr(http_err.response, 'headers'):
                        retry_after = http_err.response.headers.get('Retry-After')
                    message = f"Rate limit exceeded for {service_name}. Please try again later{f' after {retry_after} seconds' if retry_after else ''}."
                elif status_code >= 500:
                    message = f"{service_name} server error. Please try again later."
                else:
                    message = f"{service_name} API error: {str(http_err)}"

                error_details = {
                    "success": False,
                    "error": error_code,
                    "error_type": error_type,
                    "message": message,
                    "correlation_id": correlation_id,
                    "service": service_name,
                    "tool": func.__name__,
                    "status_code": status_code,
                    default_return_key: {},
                }

                # Add retry information for rate limiting
                if is_rate_limit and hasattr(http_err.response, 'headers'):
                    retry_after = http_err.response.headers.get('Retry-After')
                    if retry_after:
                        error_details["retry_after"] = retry_after
                    # Include rate limit headers if present
                    rate_limit_header_mapping = {
                        'X-RateLimit-Remaining': 'rate_limit_remaining',
                        'X-RateLimit-Reset': 'rate_limit_reset'
                    }
                    for header_key, field_name in rate_limit_header_mapping.items():
                        if header_key in http_err.response.headers:
                            error_details[field_name] = http_err.response.headers[header_key]

                logger.error(
                    f"[{correlation_id}] HTTP {status_code} error in {func.__name__}: {message}",
                    extra={
                        "correlation_id": correlation_id,
                        "tool": func.__name__,
                        "service": service_name,
                        "status_code": status_code,
                        "error_type": error_type
                    }
                )
                return json.dumps(error_details, indent=2, ensure_ascii=False)

            except ValueError as val_err:
                # Re-capture correlation ID from context in case it was updated during function execution
                if args and hasattr(args[0], 'request_context') and hasattr(args[0].request_context, 'correlation_id'):
                    current_correlation_id = args[0].request_context.correlation_id
                    if current_correlation_id:
                        correlation_id = current_correlation_id

                error_details = {
                    "success": False,
                    "error": "Validation Error",
                    "error_type": "validation",
                    "message": str(val_err),
                    "correlation_id": correlation_id,
                    "service": service_name,
                    "tool": func.__name__,
                    default_return_key: {},
                }
                logger.error(
                    f"[{correlation_id}] Validation error in {func.__name__}: {val_err}",
                    extra={"correlation_id": correlation_id, "tool": func.__name__, "service": service_name}
                )
                return json.dumps(error_details, indent=2, ensure_ascii=False)

            except Exception as e:
                # Re-capture correlation ID from context in case it was updated during function execution
                if args and hasattr(args[0], 'request_context') and hasattr(args[0].request_context, 'correlation_id'):
                    current_correlation_id = args[0].request_context.correlation_id
                    if current_correlation_id:
                        correlation_id = current_correlation_id

                error_details = {
                    "success": False,
                    "error": "Internal Error",
                    "error_type": "internal",
                    "message": f"An unexpected error occurred in {service_name}: {str(e)}",
                    "correlation_id": correlation_id,
                    "service": service_name,
                    "tool": func.__name__,
                    default_return_key: {},
                }
                logger.error(
                    f"[{correlation_id}] Unexpected error in {func.__name__}: {e}",
                    extra={
                        "correlation_id": correlation_id,
                        "tool": func.__name__,
                        "service": service_name,
                        "error_type": "internal"
                    },
                    exc_info=True
                )
                return json.dumps(error_details, indent=2, ensure_ascii=False)

        return wrapper  # type: ignore

    return decorator


def generate_correlation_id() -> str:
    """Generate a unique correlation ID for request tracking.

    Returns:
        An 8-character alphanumeric string for correlation tracking
    """
    return str(uuid.uuid4())[:8]
