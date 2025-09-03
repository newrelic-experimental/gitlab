"""
Tests for error handling and custom exceptions.
"""

import pytest
from unittest.mock import MagicMock
from shared.error_handling.exceptions import (
    ErrorCategory,
    ErrorSeverity,
    GitLabExporterError,
    ConfigurationError,
    GitLabAPIError,
    NewRelicAPIError,
    NetworkError,
    DataProcessingError,
    AuthenticationError,
    ValidationError,
    SystemError,
    create_config_error,
    create_gitlab_api_error,
    create_newrelic_api_error,
    create_data_processing_error,
)


class TestErrorEnums:
    """Test error enumeration classes."""

    def test_error_category_values(self):
        """Test ErrorCategory enum values."""
        assert ErrorCategory.CONFIGURATION.value == "configuration"
        assert ErrorCategory.GITLAB_API.value == "gitlab_api"
        assert ErrorCategory.NEW_RELIC_API.value == "new_relic_api"
        assert ErrorCategory.NETWORK.value == "network"
        assert ErrorCategory.DATA_PROCESSING.value == "data_processing"
        assert ErrorCategory.AUTHENTICATION.value == "authentication"
        assert ErrorCategory.VALIDATION.value == "validation"
        assert ErrorCategory.SYSTEM.value == "system"

    def test_error_severity_values(self):
        """Test ErrorSeverity enum values."""
        assert ErrorSeverity.LOW.value == "low"
        assert ErrorSeverity.MEDIUM.value == "medium"
        assert ErrorSeverity.HIGH.value == "high"
        assert ErrorSeverity.CRITICAL.value == "critical"


class TestGitLabExporterError:
    """Test base GitLabExporterError class."""

    def test_basic_error_creation(self):
        """Test basic error creation with minimal parameters."""
        error = GitLabExporterError("Test error message", ErrorCategory.SYSTEM)

        assert str(error) == "Test error message"
        assert error.message == "Test error message"
        assert error.category == ErrorCategory.SYSTEM
        assert error.severity == ErrorSeverity.MEDIUM
        assert error.context == {}
        assert error.original_exception is None
        assert error.retry_after is None

    def test_full_error_creation(self):
        """Test error creation with all parameters."""
        original_exception = ValueError("Original error")
        context = {"key": "value", "number": 42}

        error = GitLabExporterError(
            "Test error message",
            ErrorCategory.GITLAB_API,
            ErrorSeverity.HIGH,
            context=context,
            original_exception=original_exception,
            retry_after=60,
        )

        assert error.message == "Test error message"
        assert error.category == ErrorCategory.GITLAB_API
        assert error.severity == ErrorSeverity.HIGH
        assert error.context == context
        assert error.original_exception == original_exception
        assert error.retry_after == 60

    def test_to_dict_basic(self):
        """Test to_dict method with basic error."""
        error = GitLabExporterError(
            "Test error", ErrorCategory.NETWORK, ErrorSeverity.LOW
        )

        result = error.to_dict()

        expected = {
            "error_type": "GitLabExporterError",
            "message": "Test error",
            "category": "network",
            "severity": "low",
            "context": {},
        }

        assert result == expected

    def test_to_dict_with_original_exception(self):
        """Test to_dict method with original exception."""
        original_exception = ValueError("Original error")
        error = GitLabExporterError(
            "Test error", ErrorCategory.SYSTEM, original_exception=original_exception
        )

        result = error.to_dict()

        assert result["original_exception"]["type"] == "ValueError"
        assert result["original_exception"]["message"] == "Original error"

    def test_to_dict_with_retry_after(self):
        """Test to_dict method with retry_after."""
        error = GitLabExporterError("Test error", ErrorCategory.NETWORK, retry_after=30)

        result = error.to_dict()

        assert result["retry_after"] == 30

    def test_is_retryable_true(self):
        """Test is_retryable returns True when retry_after is set."""
        error = GitLabExporterError("Test error", ErrorCategory.NETWORK, retry_after=60)

        assert error.is_retryable() is True

    def test_is_retryable_false(self):
        """Test is_retryable returns False when retry_after is None."""
        error = GitLabExporterError("Test error", ErrorCategory.SYSTEM)

        assert error.is_retryable() is False


class TestConfigurationError:
    """Test ConfigurationError class."""

    def test_basic_configuration_error(self):
        """Test basic configuration error creation."""
        error = ConfigurationError("Invalid config")

        assert error.message == "Invalid config"
        assert error.category == ErrorCategory.CONFIGURATION
        assert error.severity == ErrorSeverity.HIGH
        assert error.context == {}

    def test_configuration_error_with_config_key(self):
        """Test configuration error with config key."""
        error = ConfigurationError("Invalid config", config_key="api_key")

        assert error.context["config_key"] == "api_key"

    def test_configuration_error_with_context(self):
        """Test configuration error with additional context."""
        context = {"existing_key": "value"}
        error = ConfigurationError(
            "Invalid config", config_key="api_key", context=context
        )

        assert error.context["config_key"] == "api_key"
        assert error.context["existing_key"] == "value"


class TestGitLabAPIError:
    """Test GitLabAPIError class."""

    def test_basic_gitlab_api_error(self):
        """Test basic GitLab API error creation."""
        error = GitLabAPIError("API request failed")

        assert error.message == "API request failed"
        assert error.category == ErrorCategory.GITLAB_API
        assert error.severity == ErrorSeverity.MEDIUM
        assert error.retry_after is None

    def test_gitlab_api_error_with_status_code(self):
        """Test GitLab API error with status code."""
        error = GitLabAPIError(
            "API request failed", status_code=404, endpoint="/api/v4/projects"
        )

        assert error.context["status_code"] == 404
        assert error.context["endpoint"] == "/api/v4/projects"
        assert error.retry_after is None

    def test_gitlab_api_error_retryable_status_codes(self):
        """Test GitLab API error with retryable status codes."""
        retryable_codes = [429, 502, 503, 504]

        for code in retryable_codes:
            error = GitLabAPIError("API request failed", status_code=code)
            assert error.retry_after == 60
            assert error.is_retryable() is True

    def test_gitlab_api_error_custom_retry_after(self):
        """Test GitLab API error with custom retry_after."""
        error = GitLabAPIError("Rate limited", status_code=429, retry_after=120)

        assert error.retry_after == 120


class TestNewRelicAPIError:
    """Test NewRelicAPIError class."""

    def test_basic_newrelic_api_error(self):
        """Test basic New Relic API error creation."""
        error = NewRelicAPIError("API request failed")

        assert error.message == "API request failed"
        assert error.category == ErrorCategory.NEW_RELIC_API
        assert error.severity == ErrorSeverity.MEDIUM
        assert error.retry_after is None

    def test_newrelic_api_error_retryable_status_codes(self):
        """Test New Relic API error with retryable status codes."""
        retryable_codes = [429, 502, 503, 504]

        for code in retryable_codes:
            error = NewRelicAPIError("API request failed", status_code=code)
            assert error.retry_after == 30  # Different default than GitLab
            assert error.is_retryable() is True


class TestNetworkError:
    """Test NetworkError class."""

    def test_basic_network_error(self):
        """Test basic network error creation."""
        error = NetworkError("Connection failed")

        assert error.message == "Connection failed"
        assert error.category == ErrorCategory.NETWORK
        assert error.severity == ErrorSeverity.MEDIUM
        assert error.retry_after == 30
        assert error.is_retryable() is True

    def test_network_error_custom_retry_after(self):
        """Test network error with custom retry_after."""
        error = NetworkError("Connection failed", retry_after=60)

        assert error.retry_after == 60


class TestDataProcessingError:
    """Test DataProcessingError class."""

    def test_basic_data_processing_error(self):
        """Test basic data processing error creation."""
        error = DataProcessingError("Processing failed")

        assert error.message == "Processing failed"
        assert error.category == ErrorCategory.DATA_PROCESSING
        assert error.severity == ErrorSeverity.MEDIUM
        assert error.context == {}

    def test_data_processing_error_with_data_type(self):
        """Test data processing error with data type."""
        error = DataProcessingError("Processing failed", data_type="pipeline")

        assert error.context["data_type"] == "pipeline"


class TestAuthenticationError:
    """Test AuthenticationError class."""

    def test_basic_authentication_error(self):
        """Test basic authentication error creation."""
        error = AuthenticationError("Authentication failed")

        assert error.message == "Authentication failed"
        assert error.category == ErrorCategory.AUTHENTICATION
        assert error.severity == ErrorSeverity.HIGH


class TestValidationError:
    """Test ValidationError class."""

    def test_basic_validation_error(self):
        """Test basic validation error creation."""
        error = ValidationError("Validation failed")

        assert error.message == "Validation failed"
        assert error.category == ErrorCategory.VALIDATION
        assert error.severity == ErrorSeverity.MEDIUM
        assert error.context == {}

    def test_validation_error_with_field_name(self):
        """Test validation error with field name."""
        error = ValidationError("Invalid value", field_name="api_key")

        assert error.context["field_name"] == "api_key"


class TestSystemError:
    """Test SystemError class."""

    def test_basic_system_error(self):
        """Test basic system error creation."""
        error = SystemError("System failure")

        assert error.message == "System failure"
        assert error.category == ErrorCategory.SYSTEM
        assert error.severity == ErrorSeverity.HIGH


class TestConvenienceFunctions:
    """Test convenience functions for creating errors."""

    def test_create_config_error(self):
        """Test create_config_error convenience function."""
        error = create_config_error("Invalid API key", "api_key")

        assert isinstance(error, ConfigurationError)
        assert error.message == "Invalid API key"
        assert error.context["config_key"] == "api_key"

    def test_create_gitlab_api_error(self):
        """Test create_gitlab_api_error convenience function."""
        original_exception = ValueError("Original error")
        error = create_gitlab_api_error(
            "API failed", 404, "/api/v4/projects", original_exception
        )

        assert isinstance(error, GitLabAPIError)
        assert error.message == "API failed"
        assert error.context["status_code"] == 404
        assert error.context["endpoint"] == "/api/v4/projects"
        assert error.original_exception == original_exception

    def test_create_gitlab_api_error_without_exception(self):
        """Test create_gitlab_api_error without original exception."""
        error = create_gitlab_api_error("API failed", 500, "/api/v4/projects")

        assert isinstance(error, GitLabAPIError)
        assert error.original_exception is None

    def test_create_newrelic_api_error(self):
        """Test create_newrelic_api_error convenience function."""
        original_exception = ConnectionError("Connection failed")
        error = create_newrelic_api_error(
            "NR API failed", 429, "/v1/accounts/123/events", original_exception
        )

        assert isinstance(error, NewRelicAPIError)
        assert error.message == "NR API failed"
        assert error.context["status_code"] == 429
        assert error.context["endpoint"] == "/v1/accounts/123/events"
        assert error.original_exception == original_exception

    def test_create_newrelic_api_error_without_exception(self):
        """Test create_newrelic_api_error without original exception."""
        error = create_newrelic_api_error("NR API failed", 500, "/v1/events")

        assert isinstance(error, NewRelicAPIError)
        assert error.original_exception is None

    def test_create_data_processing_error(self):
        """Test create_data_processing_error convenience function."""
        original_exception = KeyError("Missing key")
        error = create_data_processing_error(
            "Processing failed", "pipeline", original_exception
        )

        assert isinstance(error, DataProcessingError)
        assert error.message == "Processing failed"
        assert error.context["data_type"] == "pipeline"
        assert error.original_exception == original_exception

    def test_create_data_processing_error_without_exception(self):
        """Test create_data_processing_error without original exception."""
        error = create_data_processing_error("Processing failed", "job")

        assert isinstance(error, DataProcessingError)
        assert error.original_exception is None
