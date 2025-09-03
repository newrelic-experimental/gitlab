"""
Tests for OpenTelemetry helper functions.
"""

import pytest
import logging
from unittest.mock import MagicMock, patch, Mock
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from shared.otel import (
    create_resource_attributes,
    get_logger,
    get_meter,
    get_tracer,
)


class TestCreateResourceAttributes:
    """Test create_resource_attributes function."""

    def test_basic_resource_attributes(self):
        """Test basic resource attributes creation."""
        atts = {
            "key1": "value1",
            "key2": "value2",
        }
        service_name = "test-service"

        result = create_resource_attributes(atts, service_name)

        expected = {
            SERVICE_NAME: "test-service",
            "key1": "value1",
            "key2": "value2",
        }

        assert result == expected

    def test_resource_attributes_with_name_key(self):
        """Test resource attributes with 'name' key gets converted to 'resource.name'."""
        atts = {
            "name": "my-resource",
            "other_key": "other_value",
        }
        service_name = "test-service"

        result = create_resource_attributes(atts, service_name)

        expected = {
            SERVICE_NAME: "test-service",
            "resource.name": "my-resource",
            "other_key": "other_value",
        }

        assert result == expected
        assert "name" not in result  # Original 'name' key should not be present

    def test_resource_attributes_filters_none_values(self):
        """Test that None values are filtered out."""
        atts = {
            "valid_key": "valid_value",
            "none_key": None,
            "empty_string": "",
            "none_string": "None",
            "zero_value": 0,
            "false_value": False,
        }
        service_name = "test-service"

        result = create_resource_attributes(atts, service_name)

        expected = {
            SERVICE_NAME: "test-service",
            "valid_key": "valid_value",  # This should be included as it's a valid non-empty string
            "zero_value": 0,
            "false_value": False,
        }

        assert result == expected
        assert "none_key" not in result
        assert "empty_string" not in result
        assert "none_string" not in result

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
        """Test create_resource_attributes with realistic data."""
        atts = {
            "name": "gitlab-pipeline-123",
            "pipeline_id": "123",
            "project_id": "456",
            "status": "success",
            "ref": "main",
            "empty_field": "",
            "null_field": None,
            "none_string": "None",
        }
        service_name = "gitlab-exporter"

        result = create_resource_attributes(atts, service_name)

        expected = {
            SERVICE_NAME: "gitlab-exporter",
            "resource.name": "gitlab-pipeline-123",
            "pipeline_id": "123",
            "project_id": "456",
            "status": "success",
            "ref": "main",
        }

        assert result == expected
        # Ensure filtered fields are not present
        assert "empty_field" not in result
        assert "null_field" not in result
        assert "none_string" not in result
        assert "name" not in result  # Should be converted to resource.name

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
