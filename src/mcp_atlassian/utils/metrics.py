"""Metrics and health check utilities for MCP Atlassian.

This module provides error tracking, metrics collection, and health monitoring
capabilities for the MCP server.
"""

import asyncio
import json
import logging
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from fastmcp import Context
from starlette.responses import JSONResponse

logger = logging.getLogger(__name__)


class ErrorMetrics:
    """Error metrics collector and aggregator."""

    def __init__(self, max_history: int = 1000, max_age_hours: int = 24):
        self.max_history = max_history
        self.max_age = timedelta(hours=max_age_hours)
        self._errors: deque = deque(maxlen=max_history)
        self._error_counts: Dict[str, int] = defaultdict(int)
        self._service_errors: Dict[str, int] = defaultdict(int)
        self._tool_errors: Dict[str, int] = defaultdict(int)
        self._start_time = datetime.now()

    def record_error(
        self,
        error_type: str,
        service: str,
        tool: str | None = None,
        correlation_id: str | None = None,
        status_code: int | None = None,
        message: str | None = None,
    ):
        """Record an error occurrence."""
        error_record = {
            "timestamp": datetime.now().isoformat(),
            "error_type": error_type,
            "service": service,
            "tool": tool,
            "correlation_id": correlation_id,
            "status_code": status_code,
            "message": message,
        }

        self._errors.append(error_record)
        self._error_counts[error_type] += 1
        self._service_errors[service] += 1
        if tool:
            self._tool_errors[tool] += 1

        logger.debug(
            f"Recorded error: {error_type} in {service}" + (f" tool {tool}" if tool else "")
        )

    def get_error_summary(self) -> Dict[str, Any]:
        """Get a summary of error metrics."""
        now = datetime.now()
        recent_errors = [
            error for error in self._errors
            if now - datetime.fromisoformat(error["timestamp"]) < self.max_age
        ]

        # Calculate error rates
        total_errors = len(recent_errors)
        uptime_hours = (now - self._start_time).total_seconds() / 3600
        error_rate = total_errors / uptime_hours if uptime_hours > 0 else 0

        return {
            "total_errors": total_errors,
            "error_rate_per_hour": round(error_rate, 2),
            "uptime_hours": round(uptime_hours, 2),
            "error_types": dict(self._error_counts),
            "service_errors": dict(self._service_errors),
            "tool_errors": dict(self._tool_errors),
            "recent_errors": list(recent_errors)[-10:],  # Last 10 errors
        }

    def get_health_status(self) -> Dict[str, Any]:
        """Get overall health status based on error metrics."""
        summary = self.get_error_summary()
        total_errors = summary["total_errors"]
        error_rate = summary["error_rate_per_hour"]

        # Determine health status
        if error_rate == 0:
            status = "healthy"
            status_code = 200
        elif error_rate < 5:
            status = "degraded"
            status_code = 200
        elif error_rate < 20:
            status = "unhealthy"
            status_code = 503
        else:
            status = "critical"
            status_code = 503

        # Check for critical error types
        critical_errors = summary["error_types"].get("authentication", 0)
        if critical_errors > 10:  # High auth errors indicate configuration issues
            status = "critical"
            status_code = 503

        return {
            "status": status,
            "status_code": status_code,
            "error_summary": summary,
            "timestamp": datetime.now().isoformat(),
        }


class HealthChecker:
    """Health check manager for the MCP server."""

    def __init__(self):
        self.metrics = ErrorMetrics()
        self._health_checks: Dict[str, callable] = {}

    def register_health_check(self, name: str, check_func: callable):
        """Register a health check function."""
        self._health_checks[name] = check_func

    async def run_health_checks(self) -> Dict[str, Any]:
        """Run all registered health checks."""
        results = {}
        overall_healthy = True

        for name, check_func in self._health_checks.items():
            try:
                if asyncio.iscoroutinefunction(check_func):
                    result = await check_func()
                else:
                    result = check_func()
                results[name] = {"status": "healthy", "result": result}
            except Exception as e:
                results[name] = {
                    "status": "unhealthy",
                    "error": str(e),
                    "timestamp": datetime.now().isoformat(),
                }
                overall_healthy = False

        # Include error metrics in health check
        error_health = self.metrics.get_health_status()
        if error_health["status"] != "healthy":
            overall_healthy = False

        return {
            "overall_status": "healthy" if overall_healthy else "unhealthy",
            "timestamp": datetime.now().isoformat(),
            "checks": results,
            "error_metrics": error_health["error_summary"],
        }


# Global health checker instance
health_checker = HealthChecker()


def record_error(
    error_type: str,
    service: str,
    tool: str | None = None,
    correlation_id: str | None = None,
    status_code: int | None = None,
    message: str | None = None,
):
    """Record an error in the global metrics collector."""
    health_checker.metrics.record_error(
        error_type=error_type,
        service=service,
        tool=tool,
        correlation_id=correlation_id,
        status_code=status_code,
        message=message,
    )


async def health_check_endpoint() -> JSONResponse:
    """Health check endpoint for monitoring."""
    try:
        health_status = await health_checker.run_health_checks()
        status_code = 200 if health_status["overall_status"] == "healthy" else 503
        return JSONResponse(health_status, status_code=status_code)
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return JSONResponse(
            {
                "overall_status": "critical",
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
            },
            status_code=503,
        )


async def metrics_endpoint() -> JSONResponse:
    """Metrics endpoint for monitoring."""
    try:
        metrics = health_checker.metrics.get_error_summary()
        return JSONResponse(metrics, status_code=200)
    except Exception as e:
        logger.error(f"Metrics endpoint failed: {e}")
        return JSONResponse(
            {
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            },
            status_code=500,
        )


def create_jira_health_check(jira_config) -> callable:
    """Create a health check function for Jira connectivity."""
    async def check_jira_health():
        if not jira_config:
            raise Exception("Jira configuration not available")

        # Basic connectivity check
        try:
            from mcp_atlassian.jira import JiraFetcher
            jira = JiraFetcher(jira_config)
            # Try to get a simple project list to verify connectivity
            projects = jira.get_all_projects(include_archived=False)
            return {"projects_count": len(projects), "connected": True}
        except Exception as e:
            raise Exception(f"Jira connectivity failed: {str(e)}")

    return check_jira_health


def create_confluence_health_check(confluence_config) -> callable:
    """Create a health check function for Confluence connectivity."""
    async def check_confluence_health():
        if not confluence_config:
            raise Exception("Confluence configuration not available")

        try:
            from mcp_atlassian.confluence import ConfluenceFetcher
            confluence = ConfluenceFetcher(confluence_config)
            # Try to get a simple space list to verify connectivity
            spaces = confluence.get_spaces(limit=1)
            return {"spaces_count": len(spaces), "connected": True}
        except Exception as e:
            raise Exception(f"Confluence connectivity failed: {str(e)}")

    return check_confluence_health


def setup_health_checks(jira_config=None, confluence_config=None):
    """Set up default health checks for the MCP server."""
    if jira_config:
        health_checker.register_health_check("jira", create_jira_health_check(jira_config))

    if confluence_config:
        health_checker.register_health_check(
            "confluence", create_confluence_health_check(confluence_config)
        )

    # Add system health checks
    def check_memory():
        import psutil
        memory = psutil.virtual_memory()
        return {
            "total_gb": round(memory.total / (1024**3), 2),
            "available_gb": round(memory.available / (1024**3), 2),
            "percent_used": memory.percent,
        }

    health_checker.register_health_check("memory", check_memory)

    def check_disk():
        import psutil
        disk = psutil.disk_usage('/')
        return {
            "total_gb": round(disk.total / (1024**3), 2),
            "free_gb": round(disk.free / (1024**3), 2),
            "percent_used": round((disk.used / disk.total) * 100, 2),
        }

    health_checker.register_health_check("disk", check_disk)


# Decorator for automatic error recording
def track_errors(service_name: str):
    """Decorator to automatically track errors in functions."""
    def decorator(func):
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                # Extract correlation ID if available
                correlation_id = None
                if args and hasattr(args[0], 'request_context'):
                    correlation_id = getattr(args[0].request_context, 'correlation_id', None)

                # Determine error type
                error_type = "internal"
                if hasattr(e, 'response') and hasattr(e.response, 'status_code'):
                    if e.response.status_code == 401:
                        error_type = "authentication"
                    elif e.response.status_code == 403:
                        error_type = "authorization"
                    elif e.response.status_code == 429:
                        error_type = "rate_limit"
                    elif e.response.status_code >= 500:
                        error_type = "server_error"

                record_error(
                    error_type=error_type,
                    service=service_name,
                    tool=func.__name__,
                    correlation_id=correlation_id,
                    status_code=getattr(e.response, 'status_code', None) if hasattr(e, 'response') else None,
                    message=str(e),
                )
                raise
        return wrapper
    return decorator