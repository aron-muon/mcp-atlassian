"""Tests for enhanced error handling functionality."""

import json
import logging
from unittest.mock import AsyncMock, MagicMock, patch
from fastmcp import Context

import pytest
from requests.exceptions import HTTPError

from mcp_atlassian.exceptions import MCPAtlassianAuthenticationError
from mcp_atlassian.utils.decorators import handle_tool_errors


class TestHandleToolErrorsDecorator:
    """Tests for the enhanced handle_tool_errors decorator."""

    @pytest.fixture
    def mock_context(self):
        """Create a mock FastMCP context for testing."""
        ctx = MagicMock(spec=Context)
        ctx.request_context = MagicMock()
        ctx.request_context.correlation_id = None
        return ctx

    @pytest.mark.asyncio
    async def test_successful_function_execution(self, mock_context):
        """Test that successful function execution returns normally."""

        @handle_tool_errors(default_return_key="test", service_name="TestService")
        async def test_function(ctx: Context):
            return {"data": "success"}

        result = await test_function(mock_context)
        # Successful execution returns the result directly, not JSON
        assert result == {"data": "success"}

    @pytest.mark.asyncio
    async def test_authentication_error_handling(self, mock_context):
        """Test that authentication errors are properly formatted."""

        @handle_tool_errors(default_return_key="test", service_name="TestService")
        async def test_function(ctx: Context):
            raise MCPAtlassianAuthenticationError("Auth failed")

        result = json.loads(await test_function(mock_context))

        assert result["success"] is False
        assert result["error"] == "Authentication Failed"
        assert result["error_type"] == "authentication"
        assert result["message"] == "Auth failed"
        assert result["service"] == "TestService"
        assert result["tool"] == "test_function"
        assert "correlation_id" in result
        assert result["test"] == {}

    @pytest.mark.asyncio
    async def test_http_error_401_handling(self, mock_context):
        """Test that HTTP 401 errors are properly formatted."""

        @handle_tool_errors(default_return_key="test", service_name="TestService")
        async def test_function(ctx: Context):
            response = MagicMock()
            response.status_code = 401
            http_error = HTTPError("401 Client Error", response=response)
            raise http_error

        result = json.loads(await test_function(mock_context))

        assert result["success"] is False
        assert result["error"] == "HTTP_401"
        assert result["error_type"] == "http_error"
        assert "Authentication failed" in result["message"]
        assert result["status_code"] == 401
        assert result["service"] == "TestService"

    @pytest.mark.asyncio
    async def test_http_error_403_handling(self, mock_context):
        """Test that HTTP 403 errors are properly formatted."""

        @handle_tool_errors(default_return_key="test", service_name="TestService")
        async def test_function(ctx: Context):
            response = MagicMock()
            response.status_code = 403
            http_error = HTTPError("403 Client Error", response=response)
            raise http_error

        result = json.loads(await test_function(mock_context))

        assert result["success"] is False
        assert result["error"] == "HTTP_403"
        assert "Access denied" in result["message"]
        assert result["status_code"] == 403

    @pytest.mark.asyncio
    async def test_http_error_404_handling(self, mock_context):
        """Test that HTTP 404 errors are properly formatted."""

        @handle_tool_errors(default_return_key="test", service_name="TestService")
        async def test_function(ctx: Context):
            response = MagicMock()
            response.status_code = 404
            http_error = HTTPError("404 Client Error", response=response)
            raise http_error

        result = json.loads(await test_function(mock_context))

        assert result["success"] is False
        assert result["error"] == "HTTP_404"
        assert "Resource not found" in result["message"]
        assert result["status_code"] == 404

    @pytest.mark.asyncio
    async def test_rate_limit_error_handling_with_retry_after(self, mock_context):
        """Test that rate limit errors include retry information."""

        @handle_tool_errors(default_return_key="test", service_name="TestService")
        async def test_function(ctx: Context):
            response = MagicMock()
            response.status_code = 429
            response.headers = {"Retry-After": "60", "X-RateLimit-Remaining": "0"}
            http_error = HTTPError("429 Too Many Requests", response=response)
            raise http_error

        result = json.loads(await test_function(mock_context))

        assert result["success"] is False
        assert result["error"] == "HTTP_429"
        assert result["error_type"] == "rate_limit"
        assert "Rate limit exceeded" in result["message"]
        assert result["retry_after"] == "60"
        assert result["rate_limit_remaining"] == "0"
        assert result["status_code"] == 429

    @pytest.mark.asyncio
    async def test_rate_limit_error_handling_without_retry_after(self, mock_context):
        """Test that rate limit errors work without retry-after header."""

        @handle_tool_errors(default_return_key="test", service_name="TestService")
        async def test_function(ctx: Context):
            response = MagicMock()
            response.status_code = 429
            response.headers = {"X-RateLimit-Remaining": "0"}
            http_error = HTTPError("429 Too Many Requests", response=response)
            raise http_error

        result = json.loads(await test_function(mock_context))

        assert result["success"] is False
        assert result["error_type"] == "rate_limit"
        assert "Rate limit exceeded" in result["message"]
        assert "after 60 seconds" not in result["message"]  # No retry-after

    @pytest.mark.asyncio
    async def test_server_error_handling(self, mock_context):
        """Test that 5xx server errors are properly formatted."""

        @handle_tool_errors(default_return_key="test", service_name="TestService")
        async def test_function(ctx: Context):
            response = MagicMock()
            response.status_code = 500
            http_error = HTTPError("500 Server Error", response=response)
            raise http_error

        result = json.loads(await test_function(mock_context))

        assert result["success"] is False
        assert result["error"] == "HTTP_500"
        assert "server error" in result["message"].lower()
        assert result["status_code"] == 500

    @pytest.mark.asyncio
    async def test_validation_error_handling(self, mock_context):
        """Test that validation errors are properly formatted."""

        @handle_tool_errors(default_return_key="test", service_name="TestService")
        async def test_function(ctx: Context):
            raise ValueError("Invalid input")

        result = json.loads(await test_function(mock_context))

        assert result["success"] is False
        assert result["error"] == "Validation Error"
        assert result["error_type"] == "validation"
        assert result["message"] == "Invalid input"
        assert result["service"] == "TestService"

    @pytest.mark.asyncio
    async def test_unexpected_error_handling(self, mock_context):
        """Test that unexpected errors are properly formatted."""

        @handle_tool_errors(default_return_key="test", service_name="TestService")
        async def test_function(ctx: Context):
            raise RuntimeError("Unexpected error")

        result = json.loads(await test_function(mock_context))

        assert result["success"] is False
        assert result["error"] == "Internal Error"
        assert result["error_type"] == "internal"
        assert "unexpected error occurred" in result["message"].lower()
        assert "TestService" in result["message"]
        assert result["service"] == "TestService"

    @pytest.mark.asyncio
    async def test_correlation_id_inclusion(self, mock_context):
        """Test that correlation IDs are included in error responses."""

        @handle_tool_errors(default_return_key="test", service_name="TestService")
        async def test_function(ctx: Context):
            raise ValueError("Test error")

        result = json.loads(await test_function(mock_context))

        assert "correlation_id" in result
        assert len(result["correlation_id"]) == 8  # Should be 8 characters
        assert result["correlation_id"].isalnum()

    @pytest.mark.asyncio
    async def test_custom_return_key(self, mock_context):
        """Test that custom return key is used in error responses."""

        @handle_tool_errors(default_return_key="custom_data", service_name="TestService")
        async def test_function(ctx: Context):
            raise ValueError("Test error")

        result = json.loads(await test_function(mock_context))

        assert result["success"] is False
        assert "custom_data" in result
        assert result["custom_data"] == {}

    @pytest.mark.asyncio
    async def test_service_name_inclusion(self, mock_context):
        """Test that service name is included in error responses."""

        @handle_tool_errors(default_return_key="test", service_name="CustomService")
        async def test_function(ctx: Context):
            raise ValueError("Test error")

        result = json.loads(await test_function(mock_context))

        assert result["service"] == "CustomService"

    @pytest.mark.asyncio
    async def test_tool_name_inclusion(self, mock_context):
        """Test that tool name is included in error responses."""

        @handle_tool_errors(default_return_key="test", service_name="TestService")
        async def custom_function_name(ctx: Context):
            raise ValueError("Test error")

        result = json.loads(await custom_function_name(mock_context))

        assert result["tool"] == "custom_function_name"

    @pytest.mark.asyncio
    @patch('mcp_atlassian.utils.decorators.logger')
    async def test_logging_with_correlation_id(self, mock_logger, mock_context):
        """Test that errors are logged with correlation ID."""

        @handle_tool_errors(default_return_key="test", service_name="TestService")
        async def test_function(ctx: Context):
            raise ValueError("Test error")

        await test_function(mock_context)

        # Verify logger.error was called with correlation ID
        mock_logger.error.assert_called_once()
        call_args = mock_logger.error.call_args
        # call_args[0] is the message, call_args[1] is the extra dict
        assert call_args[1]["extra"]["correlation_id"] is not None
        assert call_args[1]["extra"]["tool"] == "test_function"
        assert call_args[1]["extra"]["service"] == "TestService"

    @pytest.mark.asyncio
    async def test_http_error_detection_with_rate_limit_headers(self, mock_context):
        """Test that rate limiting is detected via headers even without 429 status."""

        @handle_tool_errors(default_return_key="test", service_name="TestService")
        async def test_function(ctx: Context):
            response = MagicMock()
            response.status_code = 200
            response.headers = {"X-RateLimit-Remaining": "0"}
            http_error = HTTPError("200 OK", response=response)
            raise http_error

        result = json.loads(await test_function(mock_context))

        assert result["error_type"] == "rate_limit"
        assert result["rate_limit_remaining"] == "0"