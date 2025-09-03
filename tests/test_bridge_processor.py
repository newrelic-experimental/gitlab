"""
Tests for bridge processor functionality.
"""

import pytest
import os
from unittest.mock import MagicMock, patch, Mock
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.trace import Status, StatusCode
from shared.config.settings import GitLabConfig
from new_relic_exporter.processors.bridge_processor import BridgeProcessor


class TestBridgeProcessor:
    """Test BridgeProcessor class."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock GitLab config."""
        config = MagicMock(spec=GitLabConfig)
        config.low_data_mode = False
        return config

    @pytest.fixture
    def mock_project(self):
        """Create a mock GitLab project."""
        project = MagicMock()
        project.id = 123
        project.name = "test-project"
        return project

    @pytest.fixture
    def bridge_processor(self, mock_config, mock_project):
        """Create a BridgeProcessor instance."""
        with patch("new_relic_exporter.processors.bridge_processor.get_logger"):
            return BridgeProcessor(mock_config, mock_project)

    @pytest.fixture
    def sample_bridge_data(self):
        """Sample bridge data for testing."""
        return {
            "id": 1001,
            "name": "trigger-downstream",
            "status": "success",
            "started_at": "2024-01-01T00:00:00.000Z",
            "finished_at": "2024-01-01T00:30:00.000Z",
            "stage": "deploy",
            "web_url": "https://gitlab.com/test/project/-/jobs/1001",
            "downstream_pipeline": {
                "id": 2001,
                "project_id": 456,
                "status": "success",
                "web_url": "https://gitlab.com/downstream/project/-/pipelines/2001",
            },
        }

    def test_init(self, mock_config, mock_project):
        """Test BridgeProcessor initialization."""
        with patch(
            "new_relic_exporter.processors.bridge_processor.get_logger"
        ) as mock_logger:
            processor = BridgeProcessor(mock_config, mock_project)

            assert processor.config == mock_config
            assert processor.project == mock_project
            mock_logger.assert_called_once_with("gitlab-exporter", "bridge-processor")

    def test_create_bridge_resource_basic(self, bridge_processor, sample_bridge_data):
        """Test basic bridge resource creation."""
        service_name = "test-service"

        with patch.dict(
            os.environ, {"CI_PARENT_PIPELINE": "456", "CI_PROJECT_ID": "123"}
        ), patch(
            "new_relic_exporter.processors.bridge_processor.parse_attributes"
        ) as mock_parse:
            mock_parse.return_value = {"parsed_attr": "value"}

            result = bridge_processor.create_bridge_resource(
                sample_bridge_data, service_name
            )

            assert isinstance(result, Resource)
            attributes = result.attributes
            assert attributes["service.name"] == service_name
            assert attributes["bridge_id"] == "1001"
            assert attributes["pipeline_id"] == "456"
            assert attributes["project_id"] == "123"
            assert attributes["instrumentation.name"] == "gitlab-integration"
            assert attributes["gitlab.source"] == "gitlab-exporter"
            assert attributes["gitlab.resource.type"] == "span"

    def test_create_bridge_resource_low_data_mode(
        self, bridge_processor, sample_bridge_data
    ):
        """Test bridge resource creation in low data mode."""
        bridge_processor.config.low_data_mode = True
        service_name = "test-service"

        with patch.dict(
            os.environ, {"CI_PARENT_PIPELINE": "456", "CI_PROJECT_ID": "123"}
        ), patch(
            "new_relic_exporter.processors.bridge_processor.parse_attributes"
        ) as mock_parse:

            result = bridge_processor.create_bridge_resource(
                sample_bridge_data, service_name
            )

            # In low data mode, parse_attributes should not be called
            mock_parse.assert_not_called()

            attributes = result.attributes
            assert attributes["service.name"] == service_name
            assert attributes["bridge_id"] == "1001"

    def test_create_bridge_resource_filters_none_values(self, bridge_processor):
        """Test that None values are filtered from resource attributes."""
        bridge_data = {
            "id": 1001,
            "name": None,
            "status": "",
        }
        service_name = "test-service"

        with patch.dict(
            os.environ, {"CI_PARENT_PIPELINE": "456", "CI_PROJECT_ID": "123"}
        ), patch(
            "new_relic_exporter.processors.bridge_processor.parse_attributes"
        ) as mock_parse:
            mock_parse.return_value = {
                "name": None,
                "status": "",
                "valid_attr": "value",
            }

            result = bridge_processor.create_bridge_resource(bridge_data, service_name)

            attributes = result.attributes
            assert "name" not in attributes
            assert "status" not in attributes
            assert "valid_attr" in attributes

    def test_get_bridge_downstream_info_with_pipeline(
        self, bridge_processor, sample_bridge_data
    ):
        """Test extracting downstream pipeline info when available."""
        result = bridge_processor.get_bridge_downstream_info(sample_bridge_data)

        expected = {
            "downstream_project_id": 456,
            "downstream_pipeline_id": 2001,
            "downstream_status": "success",
            "downstream_web_url": "https://gitlab.com/downstream/project/-/pipelines/2001",
        }

        assert result == expected

    def test_get_bridge_downstream_info_without_pipeline(self, bridge_processor):
        """Test extracting downstream pipeline info when not available."""
        bridge_data = {"id": 1001, "name": "test-bridge"}

        result = bridge_processor.get_bridge_downstream_info(bridge_data)

        assert result is None

    def test_get_bridge_downstream_info_partial_data(self, bridge_processor):
        """Test extracting downstream pipeline info with partial data."""
        bridge_data = {
            "id": 1001,
            "downstream_pipeline": {
                "id": 2001,
                "status": "running",
                # Missing project_id and web_url
            },
        }

        result = bridge_processor.get_bridge_downstream_info(bridge_data)

        expected = {
            "downstream_project_id": None,
            "downstream_pipeline_id": 2001,
            "downstream_status": "running",
            "downstream_web_url": None,
        }

        assert result == expected

    @patch("new_relic_exporter.processors.bridge_processor.get_tracer")
    @patch("new_relic_exporter.processors.bridge_processor.do_time")
    def test_process_bridge_skipped(
        self, mock_do_time, mock_get_tracer, bridge_processor
    ):
        """Test processing a skipped bridge."""
        bridge_data = {
            "id": 1001,
            "name": "skipped-bridge",
            "status": "skipped",
        }

        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_span.return_value = mock_span
        mock_get_tracer.return_value = mock_tracer

        pipeline_context = MagicMock()

        bridge_processor.process_bridge(
            bridge_data, pipeline_context, "endpoint", "headers", "service"
        )

        # Verify span was created for skipped bridge
        expected_span_name = "Bridge: skipped-bridge - bridge_id: 1001 - SKIPPED"
        mock_tracer.start_span.assert_called_once_with(
            name=expected_span_name,
            context=pipeline_context,
            kind=trace.SpanKind.CLIENT,
        )
        mock_span.end.assert_called_once()

    @patch("new_relic_exporter.processors.bridge_processor.get_tracer")
    @patch("new_relic_exporter.processors.bridge_processor.do_time")
    @patch("new_relic_exporter.processors.bridge_processor.parse_attributes")
    def test_process_bridge_success(
        self,
        mock_parse,
        mock_do_time,
        mock_get_tracer,
        bridge_processor,
        sample_bridge_data,
    ):
        """Test processing a successful bridge."""
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_span.return_value = mock_span
        mock_get_tracer.return_value = mock_tracer
        mock_do_time.side_effect = lambda x: f"parsed_{x}"
        mock_parse.return_value = {"attr1": "value1", "attr2": "value2"}

        pipeline_context = MagicMock()

        with patch(
            "new_relic_exporter.processors.bridge_processor.trace.use_span"
        ) as mock_use_span:
            bridge_processor.process_bridge(
                sample_bridge_data, pipeline_context, "endpoint", "headers", "service"
            )

        # Verify span creation
        expected_span_name = "Bridge: trigger-downstream - bridge_id: 1001"
        mock_tracer.start_span.assert_called_once_with(
            name=expected_span_name,
            start_time="parsed_2024-01-01T00:00:00.000Z",
            context=pipeline_context,
            kind=trace.SpanKind.CLIENT,
        )

        # Verify span attributes were set
        mock_span.set_attributes.assert_called()

        # Verify span was ended with finish time
        mock_span.end.assert_called_with(end_time="parsed_2024-01-01T00:30:00.000Z")

    @patch("new_relic_exporter.processors.bridge_processor.get_tracer")
    @patch("new_relic_exporter.processors.bridge_processor.do_time")
    @patch("new_relic_exporter.processors.bridge_processor.parse_attributes")
    def test_process_bridge_failed(
        self, mock_parse, mock_do_time, mock_get_tracer, bridge_processor
    ):
        """Test processing a failed bridge."""
        bridge_data = {
            "id": 1001,
            "name": "failed-bridge",
            "status": "failed",
            "failure_reason": "Script failure",
            "started_at": "2024-01-01T00:00:00.000Z",
            "finished_at": "2024-01-01T00:30:00.000Z",
        }

        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_span.return_value = mock_span
        mock_get_tracer.return_value = mock_tracer
        mock_do_time.side_effect = lambda x: f"parsed_{x}"
        mock_parse.return_value = {}

        pipeline_context = MagicMock()

        with patch(
            "new_relic_exporter.processors.bridge_processor.trace.use_span"
        ) as mock_use_span:
            bridge_processor.process_bridge(
                bridge_data, pipeline_context, "endpoint", "headers", "service"
            )

        # Verify error status was set
        mock_span.set_status.assert_called_once()
        call_args = mock_span.set_status.call_args[0][0]
        assert call_args.status_code == StatusCode.ERROR
        assert call_args.description == "Script failure"

    @patch("new_relic_exporter.processors.bridge_processor.get_tracer")
    @patch("new_relic_exporter.processors.bridge_processor.do_time")
    @patch("new_relic_exporter.processors.bridge_processor.parse_attributes")
    def test_process_bridge_success_with_failed_downstream(
        self, mock_parse, mock_do_time, mock_get_tracer, bridge_processor
    ):
        """Test processing a successful bridge with failed downstream pipeline."""
        bridge_data = {
            "id": 1001,
            "name": "bridge-with-failed-downstream",
            "status": "success",
            "started_at": "2024-01-01T00:00:00.000Z",
            "finished_at": "2024-01-01T00:30:00.000Z",
            "downstream_pipeline": {
                "id": 2001,
                "status": "failed",
            },
        }

        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_span.return_value = mock_span
        mock_get_tracer.return_value = mock_tracer
        mock_do_time.side_effect = lambda x: f"parsed_{x}"
        mock_parse.return_value = {}

        pipeline_context = MagicMock()

        with patch(
            "new_relic_exporter.processors.bridge_processor.trace.use_span"
        ) as mock_use_span:
            bridge_processor.process_bridge(
                bridge_data, pipeline_context, "endpoint", "headers", "service"
            )

        # Verify error status was set due to downstream failure
        mock_span.set_status.assert_called_once()
        call_args = mock_span.set_status.call_args[0][0]
        assert call_args.status_code == StatusCode.ERROR
        assert call_args.description == "Downstream pipeline failed"

    @patch("new_relic_exporter.processors.bridge_processor.get_tracer")
    @patch("new_relic_exporter.processors.bridge_processor.do_time")
    @patch("new_relic_exporter.processors.bridge_processor.parse_attributes")
    def test_process_bridge_success_with_successful_downstream(
        self, mock_parse, mock_do_time, mock_get_tracer, bridge_processor
    ):
        """Test processing a successful bridge with successful downstream pipeline."""
        bridge_data = {
            "id": 1001,
            "name": "bridge-with-success-downstream",
            "status": "success",
            "started_at": "2024-01-01T00:00:00.000Z",
            "finished_at": "2024-01-01T00:30:00.000Z",
            "downstream_pipeline": {
                "id": 2001,
                "status": "success",
            },
        }

        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_span.return_value = mock_span
        mock_get_tracer.return_value = mock_tracer
        mock_do_time.side_effect = lambda x: f"parsed_{x}"
        mock_parse.return_value = {}

        pipeline_context = MagicMock()

        with patch(
            "new_relic_exporter.processors.bridge_processor.trace.use_span"
        ) as mock_use_span:
            bridge_processor.process_bridge(
                bridge_data, pipeline_context, "endpoint", "headers", "service"
            )

        # Verify OK status was set
        mock_span.set_status.assert_called_once()
        call_args = mock_span.set_status.call_args[0][0]
        assert call_args.status_code == StatusCode.OK

    @patch("new_relic_exporter.processors.bridge_processor.get_tracer")
    def test_process_bridge_exception_handling(self, mock_get_tracer, bridge_processor):
        """Test exception handling in process_bridge."""
        mock_get_tracer.side_effect = Exception("Tracer creation failed")

        bridge_data = {"id": 1001, "name": "test-bridge", "status": "success"}
        pipeline_context = MagicMock()

        with pytest.raises(Exception, match="Tracer creation failed"):
            bridge_processor.process_bridge(
                bridge_data, pipeline_context, "endpoint", "headers", "service"
            )

    def test_process_empty_bridge_list(self, bridge_processor):
        """Test processing empty bridge list."""
        pipeline_context = MagicMock()

        # Should not raise any exceptions
        bridge_processor.process([], pipeline_context, "endpoint", "headers", "service")

    @patch("new_relic_exporter.processors.bridge_processor.get_tracer")
    @patch("new_relic_exporter.processors.bridge_processor.do_time")
    @patch("new_relic_exporter.processors.bridge_processor.parse_attributes")
    def test_process_multiple_bridges(
        self, mock_parse, mock_do_time, mock_get_tracer, bridge_processor
    ):
        """Test processing multiple bridges."""
        bridge_list = [
            {"id": 1001, "name": "bridge1", "status": "success"},
            {"id": 1002, "name": "bridge2", "status": "skipped"},
            {"id": 1003, "name": "bridge3", "status": "failed"},
        ]

        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_span.return_value = mock_span
        mock_get_tracer.return_value = mock_tracer
        mock_parse.return_value = {}

        pipeline_context = MagicMock()

        with patch("new_relic_exporter.processors.bridge_processor.trace.use_span"):
            bridge_processor.process(
                bridge_list, pipeline_context, "endpoint", "headers", "service"
            )

        # Verify all bridges were processed
        assert mock_tracer.start_span.call_count == 3

    @patch("new_relic_exporter.processors.bridge_processor.get_tracer")
    def test_process_continues_on_individual_bridge_failure(
        self, mock_get_tracer, bridge_processor
    ):
        """Test that processing continues even if individual bridge fails."""
        bridge_list = [
            {"id": 1001, "name": "bridge1", "status": "success"},
            {"id": 1002, "name": "bridge2", "status": "success"},  # This will fail
            {"id": 1003, "name": "bridge3", "status": "success"},
        ]

        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_span.return_value = mock_span

        # Make the second bridge fail
        call_count = 0

        def side_effect(*args, **kwargs):
            nonlocal call_count
            call_count += 1
            if call_count == 2:  # Second call fails
                raise Exception("Bridge processing failed")
            return mock_tracer

        mock_get_tracer.side_effect = side_effect

        pipeline_context = MagicMock()

        # Should not raise exception, should continue processing
        bridge_processor.process(
            bridge_list, pipeline_context, "endpoint", "headers", "service"
        )

        # Verify all bridges were attempted
        assert mock_get_tracer.call_count == 3

    def test_process_bridge_low_data_mode_no_attributes(
        self, bridge_processor, sample_bridge_data
    ):
        """Test that attributes are not set in low data mode."""
        bridge_processor.config.low_data_mode = True

        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_span.return_value = mock_span

        pipeline_context = MagicMock()

        with patch(
            "new_relic_exporter.processors.bridge_processor.get_tracer",
            return_value=mock_tracer,
        ), patch(
            "new_relic_exporter.processors.bridge_processor.do_time",
            side_effect=lambda x: f"parsed_{x}",
        ), patch(
            "new_relic_exporter.processors.bridge_processor.parse_attributes"
        ) as mock_parse, patch(
            "new_relic_exporter.processors.bridge_processor.trace.use_span"
        ):

            bridge_processor.process_bridge(
                sample_bridge_data, pipeline_context, "endpoint", "headers", "service"
            )

        # In low data mode, parse_attributes should not be called
        mock_parse.assert_not_called()

        # Span attributes should still be set for downstream info, but not bridge attributes
        # The span.set_attributes should be called only for downstream info
        assert (
            mock_span.set_attributes.call_count <= 1
        )  # Only for downstream info if present

    def test_process_bridge_filters_none_attributes(self, bridge_processor):
        """Test that None values are filtered from span attributes."""
        bridge_data = {
            "id": 1001,
            "name": "test-bridge",
            "status": "success",
            "started_at": "2024-01-01T00:00:00.000Z",
            "finished_at": "2024-01-01T00:30:00.000Z",
            "downstream_pipeline": {
                "id": None,
                "project_id": 456,
                "status": "",
                "web_url": "https://example.com",
            },
        }

        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_span.return_value = mock_span

        pipeline_context = MagicMock()

        with patch(
            "new_relic_exporter.processors.bridge_processor.get_tracer",
            return_value=mock_tracer,
        ), patch(
            "new_relic_exporter.processors.bridge_processor.do_time",
            side_effect=lambda x: f"parsed_{x}",
        ), patch(
            "new_relic_exporter.processors.bridge_processor.parse_attributes",
            return_value={"attr": None, "valid": "value"},
        ), patch(
            "new_relic_exporter.processors.bridge_processor.trace.use_span"
        ):

            bridge_processor.process_bridge(
                bridge_data, pipeline_context, "endpoint", "headers", "service"
            )

        # Verify set_attributes was called (for both bridge attributes and downstream info)
        assert mock_span.set_attributes.call_count >= 1

        # Check that None values were filtered in the calls
        for call in mock_span.set_attributes.call_args_list:
            attributes = call[0][0]
            for key, value in attributes.items():
                assert value is not None
                assert value != ""
