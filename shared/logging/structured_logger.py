"""
Structured logging module for GitLab New Relic Exporters.

Provides centralized, structured logging with proper error handling,
context management, and performance monitoring.
"""

import logging
import structlog
import time
from typing import Dict, Any, Optional
from contextlib import contextmanager
from dataclasses import dataclass
from enum import Enum


class LogLevel(Enum):
    """Log level enumeration."""

    DEBUG = "debug"
    INFO = "info"
    WARNING = "warning"
    ERROR = "error"
    CRITICAL = "critical"


@dataclass
class LogContext:
    """Context information for structured logging."""

    service_name: str
    component: str
    operation: str
    project_id: Optional[str] = None
    pipeline_id: Optional[str] = None
    job_id: Optional[str] = None
    bridge_id: Optional[str] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert context to dictionary for logging."""
        context = {
            "service_name": self.service_name,
            "component": self.component,
            "operation": self.operation,
        }

        # Add optional fields if present
        if self.project_id:
            context["project_id"] = self.project_id
        if self.pipeline_id:
            context["pipeline_id"] = self.pipeline_id
        if self.job_id:
            context["job_id"] = self.job_id
        if self.bridge_id:
            context["bridge_id"] = self.bridge_id

        return context


class StructuredLogger:
    """
    Structured logger with context management and performance monitoring.

    Provides consistent logging across all GitLab exporter components
    with proper error handling and performance tracking.
    """

    def __init__(self, service_name: str, component: str):
        """
        Initialize structured logger.

        Args:
            service_name: Name of the service (e.g., "gitlab-exporter")
            component: Component name (e.g., "pipeline-processor")
        """
        self.service_name = service_name
        self.component = component

        # Configure structlog
        structlog.configure(
            processors=[
                structlog.stdlib.filter_by_level,
                structlog.stdlib.add_logger_name,
                structlog.stdlib.add_log_level,
                structlog.stdlib.PositionalArgumentsFormatter(),
                structlog.processors.TimeStamper(fmt="iso"),
                structlog.processors.StackInfoRenderer(),
                structlog.processors.format_exc_info,
                structlog.processors.UnicodeDecoder(),
                structlog.processors.JSONRenderer(),
            ],
            context_class=dict,
            logger_factory=structlog.stdlib.LoggerFactory(),
            wrapper_class=structlog.stdlib.BoundLogger,
            cache_logger_on_first_use=True,
        )

        self.logger = structlog.get_logger(service_name)

    def _log(
        self,
        level: LogLevel,
        message: str,
        context: Optional[LogContext] = None,
        extra: Optional[Dict[str, Any]] = None,
        exception: Optional[Exception] = None,
    ):
        """
        Internal logging method with context and exception handling.

        Args:
            level: Log level
            message: Log message
            context: Log context information
            extra: Additional fields to include
            exception: Exception to log (if any)
        """
        log_data = {
            "component": self.component,
            "message": message,
        }

        # Add context if provided
        if context:
            log_data.update(context.to_dict())

        # Add extra fields if provided
        if extra:
            log_data.update(extra)

        # Add exception information if provided
        if exception:
            log_data.update(
                {
                    "exception_type": type(exception).__name__,
                    "exception_message": str(exception),
                }
            )

        # Log at appropriate level
        getattr(self.logger, level.value)(**log_data)

    def debug(
        self,
        message: str,
        context: Optional[LogContext] = None,
        extra: Optional[Dict[str, Any]] = None,
    ):
        """Log debug message."""
        self._log(LogLevel.DEBUG, message, context, extra)

    def info(
        self,
        message: str,
        context: Optional[LogContext] = None,
        extra: Optional[Dict[str, Any]] = None,
    ):
        """Log info message."""
        self._log(LogLevel.INFO, message, context, extra)

    def warning(
        self,
        message: str,
        context: Optional[LogContext] = None,
        extra: Optional[Dict[str, Any]] = None,
        exception: Optional[Exception] = None,
    ):
        """Log warning message."""
        self._log(LogLevel.WARNING, message, context, extra, exception)

    def error(
        self,
        message: str,
        context: Optional[LogContext] = None,
        extra: Optional[Dict[str, Any]] = None,
        exception: Optional[Exception] = None,
    ):
        """Log error message."""
        self._log(LogLevel.ERROR, message, context, extra, exception)

    def critical(
        self,
        message: str,
        context: Optional[LogContext] = None,
        extra: Optional[Dict[str, Any]] = None,
        exception: Optional[Exception] = None,
    ):
        """Log critical message."""
        self._log(LogLevel.CRITICAL, message, context, extra, exception)

    @contextmanager
    def operation_timer(self, operation: str, context: Optional[LogContext] = None):
        """
        Context manager for timing operations.

        Args:
            operation: Name of the operation being timed
            context: Log context information

        Yields:
            Dictionary to store operation results
        """
        start_time = time.time()
        operation_context = context or LogContext(
            service_name=self.service_name,
            component=self.component,
            operation=operation,
        )

        self.info(f"Starting {operation}", operation_context)

        result = {"success": False, "error": None}

        try:
            yield result
            result["success"] = True

        except Exception as e:
            result["error"] = e
            self.error(f"Operation {operation} failed", operation_context, exception=e)
            raise

        finally:
            duration = time.time() - start_time

            if result["success"]:
                self.info(
                    f"Completed {operation}",
                    operation_context,
                    extra={"duration_seconds": duration},
                )
            else:
                self.error(
                    f"Failed {operation}",
                    operation_context,
                    extra={"duration_seconds": duration},
                    exception=result.get("error"),
                )

    def log_performance_metrics(
        self,
        operation: str,
        metrics: Dict[str, Any],
        context: Optional[LogContext] = None,
    ):
        """
        Log performance metrics for an operation.

        Args:
            operation: Name of the operation
            metrics: Performance metrics dictionary
            context: Log context information
        """
        perf_context = context or LogContext(
            service_name=self.service_name,
            component=self.component,
            operation=operation,
        )

        self.info(
            f"Performance metrics for {operation}",
            perf_context,
            extra={"metrics": metrics},
        )

    def log_api_call(
        self,
        method: str,
        url: str,
        status_code: int,
        duration: float,
        context: Optional[LogContext] = None,
    ):
        """
        Log API call information.

        Args:
            method: HTTP method
            url: API endpoint URL
            status_code: HTTP status code
            duration: Request duration in seconds
            context: Log context information
        """
        api_context = context or LogContext(
            service_name=self.service_name,
            component=self.component,
            operation="api_call",
        )

        level = LogLevel.INFO if 200 <= status_code < 400 else LogLevel.ERROR

        self._log(
            level,
            f"API call: {method} {url}",
            api_context,
            extra={
                "http_method": method,
                "url": url,
                "status_code": status_code,
                "duration_seconds": duration,
            },
        )


def get_logger(service_name: str, component: str) -> StructuredLogger:
    """
    Factory function to create a structured logger.

    Args:
        service_name: Name of the service
        component: Component name

    Returns:
        Configured StructuredLogger instance
    """
    return StructuredLogger(service_name, component)
