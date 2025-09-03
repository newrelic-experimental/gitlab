"""
Custom exceptions and error handling for GitLab New Relic Exporters.

Provides structured error handling with proper categorization,
retry logic, and error reporting capabilities.
"""

from typing import Optional, Dict, Any
from enum import Enum


class ErrorCategory(Enum):
    """Error category enumeration for better error classification."""

    CONFIGURATION = "configuration"
    GITLAB_API = "gitlab_api"
    NEW_RELIC_API = "new_relic_api"
    NETWORK = "network"
    DATA_PROCESSING = "data_processing"
    AUTHENTICATION = "authentication"
    VALIDATION = "validation"
    SYSTEM = "system"


class ErrorSeverity(Enum):
    """Error severity levels."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class GitLabExporterError(Exception):
    """
    Base exception class for GitLab exporter errors.

    Provides structured error information with categorization,
    severity levels, and context for better error handling.
    """

    def __init__(
        self,
        message: str,
        category: ErrorCategory,
        severity: ErrorSeverity = ErrorSeverity.MEDIUM,
        context: Optional[Dict[str, Any]] = None,
        original_exception: Optional[Exception] = None,
        retry_after: Optional[int] = None,
    ):
        """
        Initialize GitLab exporter error.

        Args:
            message: Human-readable error message
            category: Error category for classification
            severity: Error severity level
            context: Additional context information
            original_exception: Original exception that caused this error
            retry_after: Suggested retry delay in seconds (if applicable)
        """
        super().__init__(message)
        self.message = message
        self.category = category
        self.severity = severity
        self.context = context or {}
        self.original_exception = original_exception
        self.retry_after = retry_after

    def to_dict(self) -> Dict[str, Any]:
        """Convert error to dictionary for logging/reporting."""
        error_dict = {
            "error_type": self.__class__.__name__,
            "message": self.message,
            "category": self.category.value,
            "severity": self.severity.value,
            "context": self.context,
        }

        if self.original_exception:
            error_dict["original_exception"] = {
                "type": type(self.original_exception).__name__,
                "message": str(self.original_exception),
            }

        if self.retry_after:
            error_dict["retry_after"] = self.retry_after

        return error_dict

    def is_retryable(self) -> bool:
        """Check if this error is retryable."""
        return self.retry_after is not None


class ConfigurationError(GitLabExporterError):
    """Error related to configuration issues."""

    def __init__(self, message: str, config_key: Optional[str] = None, **kwargs):
        context = kwargs.get("context", {})
        if config_key:
            context["config_key"] = config_key

        super().__init__(
            message,
            ErrorCategory.CONFIGURATION,
            ErrorSeverity.HIGH,
            context=context,
            **{k: v for k, v in kwargs.items() if k != "context"}
        )


class GitLabAPIError(GitLabExporterError):
    """Error related to GitLab API interactions."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        endpoint: Optional[str] = None,
        **kwargs
    ):
        context = kwargs.get("context", {})
        if status_code:
            context["status_code"] = status_code
        if endpoint:
            context["endpoint"] = endpoint

        # Determine if retryable based on status code
        retry_after = None
        if status_code in [429, 502, 503, 504]:  # Rate limit or server errors
            retry_after = kwargs.get("retry_after", 60)

        super().__init__(
            message,
            ErrorCategory.GITLAB_API,
            ErrorSeverity.MEDIUM,
            context=context,
            retry_after=retry_after,
            **{k: v for k, v in kwargs.items() if k not in ["context", "retry_after"]}
        )


class NewRelicAPIError(GitLabExporterError):
    """Error related to New Relic API interactions."""

    def __init__(
        self,
        message: str,
        status_code: Optional[int] = None,
        endpoint: Optional[str] = None,
        **kwargs
    ):
        context = kwargs.get("context", {})
        if status_code:
            context["status_code"] = status_code
        if endpoint:
            context["endpoint"] = endpoint

        # Determine if retryable based on status code
        retry_after = None
        if status_code in [429, 502, 503, 504]:  # Rate limit or server errors
            retry_after = kwargs.get("retry_after", 30)

        super().__init__(
            message,
            ErrorCategory.NEW_RELIC_API,
            ErrorSeverity.MEDIUM,
            context=context,
            retry_after=retry_after,
            **{k: v for k, v in kwargs.items() if k not in ["context", "retry_after"]}
        )


class NetworkError(GitLabExporterError):
    """Error related to network connectivity."""

    def __init__(self, message: str, **kwargs):
        super().__init__(
            message,
            ErrorCategory.NETWORK,
            ErrorSeverity.MEDIUM,
            retry_after=kwargs.get("retry_after", 30),
            **{k: v for k, v in kwargs.items() if k != "retry_after"}
        )


class DataProcessingError(GitLabExporterError):
    """Error related to data processing and transformation."""

    def __init__(self, message: str, data_type: Optional[str] = None, **kwargs):
        context = kwargs.get("context", {})
        if data_type:
            context["data_type"] = data_type

        super().__init__(
            message,
            ErrorCategory.DATA_PROCESSING,
            ErrorSeverity.MEDIUM,
            context=context,
            **{k: v for k, v in kwargs.items() if k != "context"}
        )


class AuthenticationError(GitLabExporterError):
    """Error related to authentication issues."""

    def __init__(self, message: str, **kwargs):
        super().__init__(
            message, ErrorCategory.AUTHENTICATION, ErrorSeverity.HIGH, **kwargs
        )


class ValidationError(GitLabExporterError):
    """Error related to data validation."""

    def __init__(self, message: str, field_name: Optional[str] = None, **kwargs):
        context = kwargs.get("context", {})
        if field_name:
            context["field_name"] = field_name

        super().__init__(
            message,
            ErrorCategory.VALIDATION,
            ErrorSeverity.MEDIUM,
            context=context,
            **{k: v for k, v in kwargs.items() if k != "context"}
        )


class SystemError(GitLabExporterError):
    """Error related to system-level issues."""

    def __init__(self, message: str, **kwargs):
        super().__init__(message, ErrorCategory.SYSTEM, ErrorSeverity.HIGH, **kwargs)


# Convenience functions for creating common errors


def create_config_error(message: str, config_key: str) -> ConfigurationError:
    """Create a configuration error with proper context."""
    return ConfigurationError(
        message, config_key=config_key, context={"config_key": config_key}
    )


def create_gitlab_api_error(
    message: str,
    status_code: int,
    endpoint: str,
    original_exception: Optional[Exception] = None,
) -> GitLabAPIError:
    """Create a GitLab API error with proper context."""
    return GitLabAPIError(
        message,
        status_code=status_code,
        endpoint=endpoint,
        original_exception=original_exception,
    )


def create_newrelic_api_error(
    message: str,
    status_code: int,
    endpoint: str,
    original_exception: Optional[Exception] = None,
) -> NewRelicAPIError:
    """Create a New Relic API error with proper context."""
    return NewRelicAPIError(
        message,
        status_code=status_code,
        endpoint=endpoint,
        original_exception=original_exception,
    )


def create_data_processing_error(
    message: str, data_type: str, original_exception: Optional[Exception] = None
) -> DataProcessingError:
    """Create a data processing error with proper context."""
    return DataProcessingError(
        message, data_type=data_type, original_exception=original_exception
    )
