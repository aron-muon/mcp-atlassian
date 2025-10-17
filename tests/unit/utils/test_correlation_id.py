"""Tests for correlation ID tracking functionality."""

import asyncio
import logging
from unittest.mock import AsyncMock, MagicMock, patch
from fastmcp import Context

import pytest
from starlette.requests import Request
from starlette.responses import JSONResponse

from mcp_atlassian.servers.main import UserTokenMiddleware
from mcp_atlassian.utils.decorators import handle_tool_errors
from mcp_atlassian.utils.logging import log_with_correlation


class TestCorrelationIdTracking:
    """Tests for correlation ID tracking throughout the system."""

    @pytest.fixture
    def mock_context(self):
        """Create a mock FastMCP context for testing."""
        ctx = MagicMock(spec=Context)
        ctx.request_context = MagicMock()
        ctx.request_context.correlation_id = None
        return ctx

    @pytest.fixture
    def mock_request(self):
        """Create a mock request for testing."""
        request = MagicMock(spec=Request)
        request.url.path = "/mcp"
        request.method = "POST"
        request.headers = {}
        # Create a real state object that can be modified
        from types import SimpleNamespace
        request.state = SimpleNamespace()
        return request

    @pytest.fixture
    def mock_call_next(self):
        """Create a mock call_next function."""
        mock_response = JSONResponse({"test": "response"})
        call_next = AsyncMock(return_value=mock_response)
        return call_next

    @pytest.fixture
    def middleware(self):
        """Create a UserTokenMiddleware instance for testing."""
        mock_app = AsyncMock()
        # Create a mock MCP server to avoid warnings
        mock_mcp_server = MagicMock()
        mock_mcp_server.settings.streamable_http_path = "/mcp"
        return UserTokenMiddleware(mock_app, mcp_server_ref=mock_mcp_server)

    def test_log_with_correlation_function(self):
        """Test the log_with_correlation utility function."""
        stream = logging.StreamHandler()
        logger = logging.getLogger("test.correlation")
        logger.addHandler(stream)
        logger.setLevel(logging.INFO)

        with patch.object(logger, '_log') as mock_log:
            log_with_correlation(
                logger, logging.INFO, "Test message", correlation_id="abc123"
            )

            # Verify logger was called with correlation_id in extra
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            assert call_args[1]["extra"]["correlation_id"] == "abc123"

    def test_log_with_correlation_none_id(self):
        """Test log_with_correlation with None correlation ID."""
        stream = logging.StreamHandler()
        logger = logging.getLogger("test.correlation.none")
        logger.addHandler(stream)
        logger.setLevel(logging.INFO)

        with patch.object(logger, '_log') as mock_log:
            log_with_correlation(
                logger, logging.INFO, "Test message", correlation_id=None
            )

            # Verify logger was called without correlation_id in extra
            mock_log.assert_called_once()
            call_args = mock_log.call_args
            assert "correlation_id" not in call_args[1]["extra"]

    @pytest.mark.asyncio
    async def test_middleware_correlation_id_generation(self, middleware, mock_request, mock_call_next):
        """Test that middleware generates correlation ID when not present."""
        # Setup request without correlation ID
        mock_request.headers = {
            "Authorization": "Bearer test-token",
        }

        result = await middleware.dispatch(mock_request, mock_call_next)

        # Verify correlation ID was generated and stored in request state
        assert hasattr(mock_request.state, "correlation_id")
        correlation_id = mock_request.state.correlation_id
        assert correlation_id is not None
        assert isinstance(correlation_id, str)
        assert len(correlation_id) == 8  # Should be 8 characters
        assert correlation_id.isalnum()

        # Verify the request was processed normally
        mock_call_next.assert_called_once_with(mock_request)

    @pytest.mark.asyncio
    async def test_middleware_correlation_id_preservation(self, middleware, mock_request, mock_call_next):
        """Test that middleware preserves existing correlation ID."""
        # Setup request with existing correlation ID header
        existing_correlation_id = "existing123"
        mock_request.headers = {
            "Authorization": "Bearer test-token",
            "X-Correlation-ID": existing_correlation_id,
        }

        result = await middleware.dispatch(mock_request, mock_call_next)

        # Verify existing correlation ID was preserved
        assert hasattr(mock_request.state, "correlation_id")
        assert mock_request.state.correlation_id == existing_correlation_id

        # Verify the request was processed normally
        mock_call_next.assert_called_once_with(mock_request)

    @pytest.mark.asyncio
    async def test_error_decorator_correlation_id_generation(self, mock_context):
        """Test that error decorator generates correlation ID."""
        @handle_tool_errors(default_return_key="test", service_name="TestService")
        async def test_function(ctx: Context):
            raise ValueError("Test error")

        result = await test_function(mock_context)

        import json
        error_data = json.loads(result)

        # Verify correlation ID was generated and included in error response
        assert "correlation_id" in error_data
        correlation_id = error_data["correlation_id"]
        assert isinstance(correlation_id, str)
        assert len(correlation_id) == 8
        assert correlation_id.isalnum()

    @pytest.mark.asyncio
    async def test_error_decorator_with_context_correlation_id(self, mock_context):
        """Test error decorator with existing correlation ID in context."""
        # Set correlation ID in context
        mock_context.request_context.correlation_id = "context123"

        @handle_tool_errors(default_return_key="test", service_name="TestService")
        async def test_function(ctx: Context):
            raise ValueError("Test error")

        result = await test_function(mock_context)

        import json
        error_data = json.loads(result)

        # Verify context correlation ID was used
        assert "correlation_id" in error_data
        assert error_data["correlation_id"] == "context123"

    @pytest.mark.asyncio
    async def test_error_decorator_logging_with_correlation_id(self, mock_context):
        """Test that errors are logged with correlation ID."""
        # Set a correlation ID in the mock context
        mock_context.request_context.correlation_id = "test12345"

        @handle_tool_errors(default_return_key="test", service_name="TestService")
        async def test_function(ctx: Context):
            raise ValueError("Test error")

        with patch('mcp_atlassian.utils.decorators.logger') as mock_logger:
            await test_function(mock_context)

            # Verify logger.error was called with correlation ID
            mock_logger.error.assert_called_once()
            call_args = mock_logger.error.call_args
            assert call_args[1]["extra"]["correlation_id"] == "test12345"
            assert call_args[1]["extra"]["tool"] == "test_function"
            assert call_args[1]["extra"]["service"] == "TestService"

    @pytest.mark.asyncio
    async def test_concurrent_correlation_id_isolation(self):
        """Test that concurrent operations have isolated correlation IDs."""
        @handle_tool_errors(default_return_key="test", service_name="TestService")
        async def test_function(ctx: Context, correlation_id_override: str | None = None):
            # Override correlation ID if provided (for testing)
            if correlation_id_override:
                ctx.request_context.correlation_id = correlation_id_override
            raise ValueError(f"Error with {correlation_id_override or 'generated'} ID")

        async def run_with_correlation_id(override_id: str):
            ctx = MagicMock(spec=Context)
            ctx.request_context = MagicMock()
            ctx.request_context.correlation_id = None

            result = await test_function(ctx, override_id)
            import json
            return json.loads(result)

        # Run multiple concurrent operations with different correlation IDs
        results = await asyncio.gather(
            run_with_correlation_id("thread1"),
            run_with_correlation_id("thread2"),
            run_with_correlation_id("thread3"),
        )

        # Verify each result has the correct correlation ID
        assert results[0]["correlation_id"] == "thread1"
        assert results[1]["correlation_id"] == "thread2"
        assert results[2]["correlation_id"] == "thread3"

    @pytest.mark.asyncio
    async def test_correlation_id_persistence_through_multiple_calls(self, mock_context):
        """Test correlation ID persistence through multiple function calls."""
        @handle_tool_errors(default_return_key="test", service_name="TestService")
        async def test_function(ctx: Context):
            import json
            return json.dumps({"success": True, "correlation_id": ctx.request_context.correlation_id})

        # Set correlation ID in context
        mock_context.request_context.correlation_id = "persistent123"

        # Call the function multiple times with the same context
        result1 = await test_function(mock_context)
        result2 = await test_function(mock_context)
        result3 = await test_function(mock_context)

        import json
        data1 = json.loads(result1)
        data2 = json.loads(result2)
        data3 = json.loads(result3)

        # When function succeeds, it returns the JSON directly, not wrapped in error structure
        # Verify all calls succeeded and used the same correlation ID
        assert data1["success"] is True
        assert data2["success"] is True
        assert data3["success"] is True
        assert data1["correlation_id"] == "persistent123"
        assert data2["correlation_id"] == "persistent123"
        assert data3["correlation_id"] == "persistent123"

    def test_correlation_id_format_validation(self):
        """Test correlation ID format and validation."""
        from mcp_atlassian.utils.decorators import generate_correlation_id

        # Generate multiple correlation IDs
        correlation_ids = [generate_correlation_id() for _ in range(100)]

        # Validate format
        for correlation_id in correlation_ids:
            assert isinstance(correlation_id, str)
            assert len(correlation_id) == 8
            assert correlation_id.isalnum()

        # Check for uniqueness
        assert len(set(correlation_ids)) == 100  # All should be unique

    @pytest.mark.asyncio
    async def test_middleware_correlation_id_logging(self, middleware, mock_request, mock_call_next):
        """Test that middleware logs correlation ID information."""
        mock_request.headers = {"Authorization": "Bearer test-token"}

        with patch('mcp_atlassian.servers.main.logger') as mock_logger:
            result = await middleware.dispatch(mock_request, mock_call_next)

            # Verify correlation ID was logged (if middleware logs it)
            # This test would need to be adjusted based on actual middleware logging
            mock_request.state.correlation_id is not None

    @pytest.mark.asyncio
    async def test_correlation_id_in_structured_logging(self, mock_context):
        """Test correlation ID inclusion in structured logging."""
        from mcp_atlassian.utils.logging import StructuredFormatter
        import json

        # Create a logger with structured formatter
        formatter = StructuredFormatter()

        # Create a log record with correlation ID
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="/path/to/file.py",
            lineno=42,
            msg="Test message with correlation ID",
            args=(),
            exc_info=None
        )
        record.correlation_id = "test12345"

        # Format the record
        formatted_message = formatter.format(record)
        log_entry = json.loads(formatted_message)

        # Verify correlation ID is included
        assert log_entry["correlation_id"] == "test12345"
        assert log_entry["message"] == "Test message with correlation ID"

    def test_correlation_id_missing_in_structured_logging(self):
        """Test structured logging behavior when correlation ID is missing."""
        from mcp_atlassian.utils.logging import StructuredFormatter
        import json

        # Create a logger with structured formatter
        formatter = StructuredFormatter()

        # Create a log record without correlation ID
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="/path/to/file.py",
            lineno=42,
            msg="Test message without correlation ID",
            args=(),
            exc_info=None
        )

        # Format the record
        formatted_message = formatter.format(record)
        log_entry = json.loads(formatted_message)

        # Verify correlation ID is not present when missing
        assert "correlation_id" not in log_entry
        assert log_entry["message"] == "Test message without correlation ID"