"""
Tests for OpenTelemetry helper functions.
"""

import pytest
import logging
from unittest.mock import MagicMock, patch, Mock
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from shared.otel import (
    create_resource_attributes,
    get_otel_logger,
    get_meter,
    get_tracer,
)
# alias for test readability
get_logger = get_otel_logger


class TestCreateResourceAttributes:
    """Test create_resource_attributes function."""

    def test_basic_resource_attributes(self):
        """Test that service.name is always set and only required attributes are promoted."""
        atts = {
            "status": "success",   # in _DEFAULT_REQUIRED_ATTRS — should be included
            "non_required_key": "value",  # not required — should be excluded
        }
        service_name = "test-service"

        result = create_resource_attributes(atts, service_name)

        assert result[SERVICE_NAME] == "test-service"
        assert result["status"] == "success"
        assert "non_required_key" not in result

    def test_resource_attributes_with_name_key(self):
        """Test that 'name' is not a required attribute and is excluded from resource level."""
        atts = {
            "name": "my-resource",
            "status": "success",
        }
        service_name = "test-service"

        result = create_resource_attributes(atts, service_name)

        # 'name' is not a required resource attribute — it stays at log-record level
        assert "name" not in result
        assert "resource.name" not in result
        assert result["status"] == "success"
        assert result[SERVICE_NAME] == "test-service"

    def test_resource_attributes_filters_none_values(self):
        """Test that None, empty, and 'None' string values are filtered even for required attrs."""
        atts = {
            "status": "success",      # required, valid — included
            "stage": None,            # required, None — excluded
            "failure_reason": "",     # required, empty string — excluded
            "description": "None",   # required, string "None" — excluded
            "id": "42",               # required, valid — included
        }
        service_name = "test-service"

        result = create_resource_attributes(atts, service_name)

        assert result[SERVICE_NAME] == "test-service"
        assert result["status"] == "success"
        assert result["id"] == "42"
        assert "stage" not in result
        assert "failure_reason" not in result
        assert "description" not in result

    def test_resource_attributes_empty_input(self):
        """Test resource attributes with empty input."""
        atts = {}
        service_name = "test-service"

        result = create_resource_attributes(atts, service_name)

        expected = {SERVICE_NAME: "test-service"}

        assert result == expected

    def test_resource_attributes_all_filtered_values(self):
        """Test resource attributes when all values are filtered."""
        atts = {
            "none_key": None,
            "empty_key": "",
            "none_string": "None",
        }
        service_name = "test-service"

        result = create_resource_attributes(atts, service_name)

        expected = {SERVICE_NAME: "test-service"}

        assert result == expected


class TestGetLogger:
    """Test get_logger function."""

    @patch("shared.otel.OTLPLogExporter")
    @patch("shared.otel.LoggerProvider")
    @patch("shared.otel.BatchLogRecordProcessor")
    @patch("shared.otel.LoggingHandler")
    @patch("shared.otel.logging.getLogger")
    def test_get_logger_basic(
        self,
        mock_get_logger,
        mock_logging_handler,
        mock_batch_processor,
        mock_logger_provider,
        mock_exporter,
    ):
        """Test basic logger creation."""
        # Setup mocks
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        mock_exporter_instance = MagicMock()
        mock_exporter.return_value = mock_exporter_instance
        mock_provider_instance = MagicMock()
        mock_logger_provider.return_value = mock_provider_instance
        mock_processor_instance = MagicMock()
        mock_batch_processor.return_value = mock_processor_instance
        mock_handler_instance = MagicMock()
        mock_logging_handler.return_value = mock_handler_instance

        # Test data
        endpoint = "https://otlp.example.com:4317"
        headers = {"api-key": "test-key"}
        resource = Resource.create({"service.name": "test-service"})
        name = "test-logger"

        # Call function
        result = get_logger(endpoint, headers, resource, name)

        # Assertions
        mock_exporter.assert_called_once_with(endpoint=endpoint, headers=headers)
        mock_get_logger.assert_called_once_with(str(name))
        mock_logger.handlers.clear.assert_called_once()
        mock_logger_provider.assert_called_once_with(resource=resource)
        mock_batch_processor.assert_called_once_with(mock_exporter_instance)
        mock_provider_instance.add_log_record_processor.assert_called_once_with(
            mock_processor_instance
        )
        mock_logging_handler.assert_called_once_with(
            level=logging.NOTSET, logger_provider=mock_provider_instance
        )
        mock_logger.addHandler.assert_called_once_with(mock_handler_instance)

        assert result == mock_logger

    @patch("shared.otel.OTLPLogExporter")
    @patch("shared.otel.LoggerProvider")
    @patch("shared.otel.BatchLogRecordProcessor")
    @patch("shared.otel.LoggingHandler")
    @patch("shared.otel.logging.getLogger")
    def test_get_logger_with_different_types(
        self,
        mock_get_logger,
        mock_logging_handler,
        mock_batch_processor,
        mock_logger_provider,
        mock_exporter,
    ):
        """Test logger creation with different name types."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        mock_exporter.return_value = MagicMock()
        mock_logger_provider.return_value = MagicMock()
        mock_batch_processor.return_value = MagicMock()
        mock_logging_handler.return_value = MagicMock()

        # Test with integer name
        get_logger("endpoint", {}, MagicMock(), 123)
        mock_get_logger.assert_called_with("123")

        # Test with None name
        get_logger("endpoint", {}, MagicMock(), None)
        mock_get_logger.assert_called_with("None")


class TestGetMeter:
    """Test get_meter function."""

    @patch("shared.otel.PeriodicExportingMetricReader")
    @patch("shared.otel.OTLPMetricExporter")
    @patch("shared.otel.MeterProvider")
    @patch("shared.otel.metrics.get_meter")
    def test_get_meter_basic(
        self,
        mock_get_meter,
        mock_meter_provider,
        mock_metric_exporter,
        mock_metric_reader,
    ):
        """Test basic meter creation."""
        # Setup mocks
        mock_exporter_instance = MagicMock()
        mock_metric_exporter.return_value = mock_exporter_instance
        mock_reader_instance = MagicMock()
        mock_metric_reader.return_value = mock_reader_instance
        mock_provider_instance = MagicMock()
        mock_meter_provider.return_value = mock_provider_instance
        mock_meter_instance = MagicMock()
        mock_get_meter.return_value = mock_meter_instance

        # Test data
        endpoint = "https://otlp.example.com:4317"
        headers = {"api-key": "test-key"}
        resource = Resource.create({"service.name": "test-service"})
        meter = "test-meter"

        # Call function
        result = get_meter(endpoint, headers, resource, meter)

        # Assertions
        mock_metric_exporter.assert_called_once_with(endpoint=endpoint, headers=headers)
        mock_metric_reader.assert_called_once_with(mock_exporter_instance)
        mock_meter_provider.assert_called_once_with(
            resource=resource, metric_readers=[mock_reader_instance]
        )
        mock_get_meter.assert_called_once_with(
            "shared.otel", meter_provider=mock_provider_instance
        )

        assert result == mock_meter_instance

    @patch("shared.otel.PeriodicExportingMetricReader")
    @patch("shared.otel.OTLPMetricExporter")
    @patch("shared.otel.MeterProvider")
    @patch("shared.otel.metrics.get_meter")
    def test_get_meter_with_none_headers(
        self,
        mock_get_meter,
        mock_meter_provider,
        mock_metric_exporter,
        mock_metric_reader,
    ):
        """Test meter creation with None headers."""
        mock_metric_exporter.return_value = MagicMock()
        mock_metric_reader.return_value = MagicMock()
        mock_meter_provider.return_value = MagicMock()
        mock_get_meter.return_value = MagicMock()

        get_meter("endpoint", None, MagicMock(), "meter")

        mock_metric_exporter.assert_called_once_with(endpoint="endpoint", headers=None)


class TestGetTracer:
    """Test get_tracer function."""

    @patch("shared.otel.BatchSpanProcessor")
    @patch("shared.otel.OTLPSpanExporter")
    @patch("shared.otel.TracerProvider")
    @patch("shared.otel.trace.get_tracer")
    def test_get_tracer_basic(
        self,
        mock_get_tracer,
        mock_tracer_provider,
        mock_span_exporter,
        mock_span_processor,
    ):
        """Test basic tracer creation."""
        # Setup mocks
        mock_exporter_instance = MagicMock()
        mock_span_exporter.return_value = mock_exporter_instance
        mock_processor_instance = MagicMock()
        mock_span_processor.return_value = mock_processor_instance
        mock_provider_instance = MagicMock()
        mock_tracer_provider.return_value = mock_provider_instance
        mock_tracer_instance = MagicMock()
        mock_get_tracer.return_value = mock_tracer_instance

        # Test data
        endpoint = "https://otlp.example.com:4317"
        headers = {"api-key": "test-key"}
        resource = Resource.create({"service.name": "test-service"})
        tracer = "test-tracer"

        # Call function
        result = get_tracer(endpoint, headers, resource, tracer)

        # Assertions
        mock_span_exporter.assert_called_once_with(endpoint=endpoint, headers=headers)
        mock_span_processor.assert_called_once_with(mock_exporter_instance)
        mock_tracer_provider.assert_called_once_with(resource=resource)
        mock_provider_instance.add_span_processor.assert_called_once_with(
            mock_processor_instance
        )
        mock_get_tracer.assert_called_once_with(
            "shared.otel", tracer_provider=mock_provider_instance
        )

        assert result == mock_tracer_instance

    @patch("shared.otel.BatchSpanProcessor")
    @patch("shared.otel.OTLPSpanExporter")
    @patch("shared.otel.TracerProvider")
    @patch("shared.otel.trace.get_tracer")
    def test_get_tracer_with_empty_headers(
        self,
        mock_get_tracer,
        mock_tracer_provider,
        mock_span_exporter,
        mock_span_processor,
    ):
        """Test tracer creation with empty headers."""
        mock_span_exporter.return_value = MagicMock()
        mock_span_processor.return_value = MagicMock()
        mock_tracer_provider.return_value = MagicMock()
        mock_get_tracer.return_value = MagicMock()

        get_tracer("endpoint", {}, MagicMock(), "tracer")

        mock_span_exporter.assert_called_once_with(endpoint="endpoint", headers={})


class TestIntegration:
    """Integration tests for OTEL helper functions."""

    def test_create_resource_attributes_integration(self):
        """Test create_resource_attributes with realistic pipeline data."""
        atts = {
            "name": "gitlab-pipeline-123",  # not required — excluded
            "pipeline_id": "123",           # required — included
            "project_id": "456",            # required — included
            "status": "success",            # required — included
            "ref": "main",                  # not required — excluded
            "empty_field": "",              # filtered — excluded
            "null_field": None,             # filtered — excluded
            "none_string": "None",          # filtered — excluded
        }
        service_name = "gitlab-exporter"

        result = create_resource_attributes(atts, service_name)

        assert result[SERVICE_NAME] == "gitlab-exporter"
        assert result["pipeline_id"] == "123"
        assert result["project_id"] == "456"
        assert result["status"] == "success"
        # Non-required attributes stay at log-record level, not resource level
        assert "ref" not in result
        assert "name" not in result
        assert "resource.name" not in result
        # Filtered fields never appear
        assert "empty_field" not in result
        assert "null_field" not in result
        assert "none_string" not in result

    @patch("shared.otel.OTLPLogExporter")
    @patch("shared.otel.LoggerProvider")
    @patch("shared.otel.BatchLogRecordProcessor")
    @patch("shared.otel.LoggingHandler")
    @patch("shared.otel.logging.getLogger")
    def test_logger_setup_sequence(
        self,
        mock_get_logger,
        mock_logging_handler,
        mock_batch_processor,
        mock_logger_provider,
        mock_exporter,
    ):
        """Test that logger setup follows correct sequence."""
        mock_logger = MagicMock()
        mock_get_logger.return_value = mock_logger
        mock_exporter.return_value = MagicMock()
        mock_provider = MagicMock()
        mock_logger_provider.return_value = mock_provider
        mock_processor = MagicMock()
        mock_batch_processor.return_value = mock_processor
        mock_handler = MagicMock()
        mock_logging_handler.return_value = mock_handler

        get_logger("endpoint", {"key": "value"}, MagicMock(), "test")

        # Verify the sequence of calls
        assert mock_logger.handlers.clear.called
        assert mock_provider.add_log_record_processor.called
        assert mock_logger.addHandler.called

        # Verify handler was added after processor was added to provider
        mock_provider.add_log_record_processor.assert_called_with(mock_processor)
        mock_logger.addHandler.assert_called_with(mock_handler)
