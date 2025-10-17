"""Tests for metrics collection functionality."""

import asyncio
import json
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from mcp_atlassian.utils.metrics import (
    ErrorMetrics,
    HealthChecker,
    record_error,
    track_errors,
)


class TestErrorMetrics:
    """Tests for the ErrorMetrics class."""

    def test_error_metrics_initialization(self):
        """Test that ErrorMetrics initializes correctly."""
        metrics = ErrorMetrics()
        summary = metrics.get_error_summary()
        assert summary["total_errors"] == 0

    def test_record_basic_error(self):
        """Test recording a basic error."""
        metrics = ErrorMetrics()
        metrics.record_error("validation", "TestService", "test_tool", "abc123")

        summary = metrics.get_error_summary()
        assert summary["total_errors"] == 1
        assert summary["error_types"]["validation"] == 1
        assert summary["service_errors"]["TestService"] == 1
        assert "recent_errors" in summary

    def test_record_multiple_errors(self):
        """Test recording multiple errors."""
        metrics = ErrorMetrics()

        metrics.record_error("validation", "TestService", "tool1", "cor1")
        metrics.record_error("authentication", "TestService", "tool2", "cor2")
        metrics.record_error("rate_limit", "AnotherService", "tool3", "cor3")

        summary = metrics.get_error_summary()
        assert summary["total_errors"] == 3
        assert summary["error_types"]["validation"] == 1
        assert summary["error_types"]["authentication"] == 1
        assert summary["error_types"]["rate_limit"] == 1

    def test_get_health_status_healthy(self):
        """Test health status when system is healthy."""
        metrics = ErrorMetrics()

        health_status = metrics.get_health_status()
        assert health_status["status"] == "healthy"
        assert health_status["status_code"] == 200

    def test_get_health_status_with_errors(self):
        """Test health status when there are errors."""
        metrics = ErrorMetrics()

        # Add some errors
        for _ in range(10):
            metrics.record_error("validation", "TestService", "test_tool", "abc123")

        health_status = metrics.get_health_status()
        # Should still be healthy with low error rate
        assert health_status["status"] in ["healthy", "degraded"]

    def test_get_health_status_critical_auth_errors(self):
        """Test health status with many authentication errors."""
        metrics = ErrorMetrics()

        # Add many authentication errors
        for _ in range(15):
            metrics.record_error("authentication", "TestService", "test_tool", "abc123")

        health_status = metrics.get_health_status()
        # Should be critical with many auth errors
        assert health_status["status"] == "critical"
        assert health_status["status_code"] == 503


class TestHealthChecker:
    """Tests for the HealthChecker class."""

    def test_health_checker_initialization(self):
        """Test that HealthChecker initializes correctly."""
        checker = HealthChecker()
        assert isinstance(checker.metrics, ErrorMetrics)
        assert len(checker._health_checks) == 0

    def test_register_health_check(self):
        """Test registering a health check function."""
        checker = HealthChecker()

        def test_check():
            return {"status": "ok"}

        checker.register_health_check("test", test_check)
        assert "test" in checker._health_checks
        assert checker._health_checks["test"] == test_check

    @pytest.mark.asyncio
    async def test_run_health_checks_all_healthy(self):
        """Test running health checks when all are healthy."""
        checker = HealthChecker()

        def check1():
            return {"status": "ok"}

        def check2():
            return {"data": "test"}

        checker.register_health_check("check1", check1)
        checker.register_health_check("check2", check2)

        result = await checker.run_health_checks()

        assert result["overall_status"] == "healthy"
        assert "checks" in result
        assert "error_metrics" in result
        assert result["checks"]["check1"]["status"] == "healthy"
        assert result["checks"]["check2"]["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_run_health_checks_with_failure(self):
        """Test running health checks when one fails."""
        checker = HealthChecker()

        def check1():
            return {"status": "ok"}

        def check2():
            raise Exception("Health check failed")

        checker.register_health_check("check1", check1)
        checker.register_health_check("check2", check2)

        result = await checker.run_health_checks()

        assert result["overall_status"] == "unhealthy"
        assert result["checks"]["check1"]["status"] == "healthy"
        assert result["checks"]["check2"]["status"] == "unhealthy"
        assert "error" in result["checks"]["check2"]

    @pytest.mark.asyncio
    async def test_run_async_health_check(self):
        """Test running an async health check function."""
        checker = HealthChecker()

        async def async_check():
            await asyncio.sleep(0.001)  # Simulate async operation
            return {"status": "ok", "async": True}

        checker.register_health_check("async_check", async_check)

        result = await checker.run_health_checks()

        assert result["overall_status"] == "healthy"
        assert result["checks"]["async_check"]["status"] == "healthy"
        assert result["checks"]["async_check"]["result"]["async"] is True


class TestGlobalFunctions:
    """Tests for global utility functions."""

    def test_record_error_function(self):
        """Test the global record_error function."""
        with patch('mcp_atlassian.utils.metrics.health_checker') as mock_checker:
            record_error("validation", "TestService", "test_tool", "abc123")
            mock_checker.metrics.record_error.assert_called_once_with(
                error_type="validation",
                service="TestService",
                tool="test_tool",
                correlation_id="abc123",
                status_code=None,
                message=None
            )

    def test_track_errors_decorator(self):
        """Test the track_errors decorator."""
        @track_errors("TestService")
        def test_function():
            return "success"

        # Test successful execution
        result = test_function()
        assert result == "success"

    def test_track_errors_decorator_with_exception(self):
        """Test the track_errors decorator with exception."""
        @track_errors("TestService")
        def failing_function():
            raise ValueError("Test error")

        with patch('mcp_atlassian.utils.metrics.record_error') as mock_record:
            with pytest.raises(ValueError, match="Test error"):
                failing_function()

            # Verify error was recorded
            mock_record.assert_called_once()
            call_args = mock_record.call_args[1]
            assert call_args["error_type"] == "internal"
            assert call_args["service"] == "TestService"
            assert call_args["tool"] == "failing_function"
            assert call_args["message"] == "Test error"

    def test_track_errors_decorator_with_http_error(self):
        """Test the track_errors decorator with HTTP error."""
        from requests.exceptions import HTTPError

        @track_errors("TestService")
        def http_error_function():
            response = MagicMock()
            response.status_code = 401
            raise HTTPError("Unauthorized", response=response)

        with patch('mcp_atlassian.utils.metrics.record_error') as mock_record:
            with pytest.raises(HTTPError):
                http_error_function()

            # Verify error was recorded with correct type
            mock_record.assert_called_once()
            call_args = mock_record.call_args[1]
            assert call_args["error_type"] == "authentication"
            assert call_args["status_code"] == 401


class TestErrorMetricsIntegration:
    """Integration tests for error metrics."""

    def test_error_metrics_with_real_timestamps(self):
        """Test that error metrics work with real timestamps."""
        metrics = ErrorMetrics()

        # Record errors at different times
        start_time = datetime.now()
        metrics.record_error("validation", "Service1", "tool1", "cor1")

        # Wait a bit and record another error
        import time
        time.sleep(0.01)
        metrics.record_error("authentication", "Service1", "tool2", "cor2")

        summary = metrics.get_error_summary()
        assert summary["total_errors"] == 2
        assert len(summary["recent_errors"]) == 2

        # Verify timestamps are valid ISO format
        for error in summary["recent_errors"]:
            assert "timestamp" in error
            # Should be able to parse the timestamp
            parsed_time = datetime.fromisoformat(error["timestamp"])
            assert start_time <= parsed_time <= datetime.now()

    def test_error_metrics_uptime_calculation(self):
        """Test uptime calculation in error metrics."""
        metrics = ErrorMetrics()

        summary = metrics.get_error_summary()
        assert "uptime_hours" in summary
        assert summary["uptime_hours"] >= 0

        # Uptime should increase over time
        import time
        time.sleep(0.01)

        summary2 = metrics.get_error_summary()
        assert summary2["uptime_hours"] >= summary["uptime_hours"]

    def test_error_summary_structure(self):
        """Test that error summary has the expected structure."""
        metrics = ErrorMetrics()
        metrics.record_error("validation", "TestService", "test_tool", "abc123")

        summary = metrics.get_error_summary()

        # Check required fields
        required_fields = [
            "total_errors",
            "error_rate_per_hour",
            "uptime_hours",
            "error_types",
            "service_errors",
            "tool_errors",
            "recent_errors"
        ]

        for field in required_fields:
            assert field in summary, f"Missing field: {field}"

        # Check types
        assert isinstance(summary["total_errors"], int)
        assert isinstance(summary["error_rate_per_hour"], (int, float))
        assert isinstance(summary["uptime_hours"], (int, float))
        assert isinstance(summary["error_types"], dict)
        assert isinstance(summary["service_errors"], dict)
        assert isinstance(summary["tool_errors"], dict)
        assert isinstance(summary["recent_errors"], list)