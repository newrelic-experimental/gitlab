"""
Error handling utilities for GitLab New Relic Exporters.
"""

from .exceptions import (
    GitLabExporterError,
    ConfigurationError,
    GitLabAPIError,
    NewRelicAPIError,
    NetworkError,
    DataProcessingError,
    AuthenticationError,
    ValidationError,
    SystemError,
    ErrorCategory,
    ErrorSeverity,
    create_config_error,
    create_gitlab_api_error,
    create_newrelic_api_error,
    create_data_processing_error,
)

__all__ = [
    "GitLabExporterError",
    "ConfigurationError",
    "GitLabAPIError",
    "NewRelicAPIError",
    "NetworkError",
    "DataProcessingError",
    "AuthenticationError",
    "ValidationError",
    "SystemError",
    "ErrorCategory",
    "ErrorSeverity",
    "create_config_error",
    "create_gitlab_api_error",
    "create_newrelic_api_error",
    "create_data_processing_error",
]
