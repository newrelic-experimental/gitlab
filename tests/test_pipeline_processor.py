"""
Tests for the pipeline processor module.

This module tests the PipelineProcessor class that handles
pipeline-level processing and tracing for GitLab CI/CD data.
"""

import json
import os
import pytest
from unittest.mock import patch, MagicMock, Mock
from opentelemetry import trace
from opentelemetry.trace import Status, StatusCode
from opentelemetry.sdk.resources import Resource

from new_relic_exporter.processors.pipeline_processor import PipelineProcessor


class TestPipelineProcessor:
    """Test suite for PipelineProcessor class."""

    def setup_method(self):
        """Set up test fixtures."""
        # Mock config
        self.mock_config = MagicMock()
        self.mock_config.low_data_mode = False

        # Mock project
        self.mock_project = MagicMock()
        self.mock_project.attributes = {
            "name_with_namespace": "Test Group/Test Project"
        }

        # Mock pipeline with comprehensive data
        self.mock_pipeline = MagicMock()
        self.pipeline_data = {
            "id": 12345,
            "iid": 123,
            "status": "success",
            "started_at": "2023-01-01T10:00:00Z",
            "finished_at": "2023-01-01T10:30:00Z",
            "ref": "main",
            "sha": "abc123def456",
            "web_url": "https://gitlab.com/test/project/-/pipelines/12345",
        }
        self.mock_pipeline.to_json.return_value = json.dumps(self.pipeline_data)

    @patch.dict(os.environ, {"CI_PARENT_PIPELINE": "12345", "CI_PROJECT_ID": "456"})
    def test_init_success(self):
        """Test successful initialization of PipelineProcessor."""
        processor = PipelineProcessor(
            self.mock_config, self.mock_project, self.mock_pipeline
        )

        assert processor.config == self.mock_config
        assert processor.project == self.mock_project
        assert processor.pipeline == self.mock_pipeline
        assert processor.pipeline_json == self.pipeline_data
        assert processor.service_name == "test-group/test-project"

    @patch.dict(os.environ, {"CI_PARENT_PIPELINE": "12345", "CI_PROJECT_ID": "456"})
    def test_create_pipeline_resource(self):
        """Test creation of pipeline resource."""
        processor = PipelineProcessor(
            self.mock_config, self.mock_project, self.mock_pipeline
        )

        resource = processor.create_pipeline_resource()

        assert isinstance(resource, Resource)
        attributes = resource.attributes
        assert attributes["service.name"] == "test-group/test-project"
        assert attributes["instrumentation.name"] == "gitlab-integration"
        assert attributes["pipeline_id"] == "12345"
        assert attributes["project_id"] == "456"
        assert attributes["gitlab.source"] == "gitlab-exporter"
        assert attributes["gitlab.resource.type"] == "span"

    @patch.dict(os.environ, {"CI_PARENT_PIPELINE": "", "CI_PROJECT_ID": ""})
    def test_create_pipeline_resource_with_empty_env_vars(self):
        """Test creation of pipeline resource with empty environment variables."""
        processor = PipelineProcessor(
            self.mock_config, self.mock_project, self.mock_pipeline
        )

        resource = processor.create_pipeline_resource()

        # Empty strings should be filtered out
        attributes = resource.attributes
        assert "pipeline_id" not in attributes
        assert "project_id" not in attributes

    def test_get_filtered_jobs_and_bridges_no_exclusions(self):
        """Test getting filtered jobs and bridges with no exclusions."""
        # Setup mock jobs
        mock_job1 = MagicMock()
        mock_job1.to_json.return_value = json.dumps({"name": "build", "stage": "build"})
        mock_job2 = MagicMock()
        mock_job2.to_json.return_value = json.dumps({"name": "test", "stage": "test"})

        # Setup mock bridges
        mock_bridge1 = MagicMock()
        mock_bridge1.to_json.return_value = json.dumps(
            {"name": "deploy", "stage": "deploy"}
        )

        self.mock_pipeline.jobs.list.return_value = [mock_job1, mock_job2]
        self.mock_pipeline.bridges.list.return_value = [mock_bridge1]

        processor = PipelineProcessor(
            self.mock_config, self.mock_project, self.mock_pipeline
        )

        job_lst, bridge_lst = processor.get_filtered_jobs_and_bridges([])

        assert len(job_lst) == 2
        assert len(bridge_lst) == 1
        assert job_lst[0]["name"] == "build"
        assert job_lst[1]["name"] == "test"
        assert bridge_lst[0]["name"] == "deploy"

    def test_get_filtered_jobs_and_bridges_with_exclusions(self):
        """Test getting filtered jobs and bridges with exclusions."""
        # Setup mock jobs
        mock_job1 = MagicMock()
        mock_job1.to_json.return_value = json.dumps({"name": "build", "stage": "build"})
        mock_job2 = MagicMock()
        mock_job2.to_json.return_value = json.dumps(
            {"name": "deploy", "stage": "deploy"}
        )

        # Setup mock bridges
        mock_bridge1 = MagicMock()
        mock_bridge1.to_json.return_value = json.dumps(
            {"name": "trigger", "stage": "trigger"}
        )

        self.mock_pipeline.jobs.list.return_value = [mock_job1, mock_job2]
        self.mock_pipeline.bridges.list.return_value = [mock_bridge1]

        processor = PipelineProcessor(
            self.mock_config, self.mock_project, self.mock_pipeline
        )

        # Exclude deploy job
        job_lst, bridge_lst = processor.get_filtered_jobs_and_bridges(["deploy"])

        assert len(job_lst) == 1
        assert len(bridge_lst) == 1
        assert job_lst[0]["name"] == "build"

    def test_get_filtered_jobs_and_bridges_exclude_by_stage(self):
        """Test getting filtered jobs and bridges excluding by stage."""
        # Setup mock jobs
        mock_job1 = MagicMock()
        mock_job1.to_json.return_value = json.dumps(
            {"name": "build-job", "stage": "build"}
        )
        mock_job2 = MagicMock()
        mock_job2.to_json.return_value = json.dumps(
            {"name": "test-job", "stage": "test"}
        )

        self.mock_pipeline.jobs.list.return_value = [mock_job1, mock_job2]
        self.mock_pipeline.bridges.list.return_value = []

        processor = PipelineProcessor(
            self.mock_config, self.mock_project, self.mock_pipeline
        )

        # Exclude test stage
        job_lst, bridge_lst = processor.get_filtered_jobs_and_bridges(["test"])

        assert len(job_lst) == 1
        assert job_lst[0]["name"] == "build-job"

    @patch.dict(os.environ, {"CI_PARENT_PIPELINE": "12345"})
    @patch("new_relic_exporter.processors.pipeline_processor.grab_span_att_vars")
    @patch("new_relic_exporter.processors.pipeline_processor.do_time")
    @patch("new_relic_exporter.processors.pipeline_processor.parse_attributes")
    def test_create_pipeline_span_normal_mode(
        self, mock_parse_attrs, mock_do_time, mock_grab_vars
    ):
        """Test creating pipeline span in normal mode (not low data mode)."""
        # Setup mocks
        mock_grab_vars.return_value = {"env.var1": "value1"}
        mock_do_time.return_value = 1672574400000000000  # Mock timestamp
        mock_parse_attrs.return_value = {"pipeline.attr": "value"}

        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_span.return_value = mock_span

        processor = PipelineProcessor(
            self.mock_config, self.mock_project, self.mock_pipeline
        )

        result_span = processor.create_pipeline_span(mock_tracer, [])

        # Verify span creation
        mock_tracer.start_span.assert_called_once()
        call_args = mock_tracer.start_span.call_args
        assert "test-group/test-project - pipeline: 12345" in call_args[1]["name"]
        assert call_args[1]["kind"] == trace.SpanKind.SERVER

        # Verify attributes were set
        mock_span.set_attributes.assert_called_once()

        assert result_span == mock_span

    @patch.dict(os.environ, {"CI_PARENT_PIPELINE": "12345"})
    @patch("new_relic_exporter.processors.pipeline_processor.do_time")
    def test_create_pipeline_span_low_data_mode(self, mock_do_time):
        """Test creating pipeline span in low data mode."""
        # Setup low data mode
        self.mock_config.low_data_mode = True
        mock_do_time.return_value = 1672574400000000000

        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_span.return_value = mock_span

        processor = PipelineProcessor(
            self.mock_config, self.mock_project, self.mock_pipeline
        )

        result_span = processor.create_pipeline_span(mock_tracer, [])

        # Verify span creation with empty attributes
        mock_tracer.start_span.assert_called_once()
        call_args = mock_tracer.start_span.call_args
        assert call_args[1]["attributes"] == {}

        # set_attributes should not be called in low data mode
        mock_span.set_attributes.assert_not_called()

    @patch.dict(os.environ, {"CI_PARENT_PIPELINE": "12345"})
    @patch("new_relic_exporter.processors.pipeline_processor.do_time")
    def test_create_pipeline_span_failed_status(self, mock_do_time):
        """Test creating pipeline span for failed pipeline."""
        # Setup failed pipeline
        failed_pipeline_data = self.pipeline_data.copy()
        failed_pipeline_data["status"] = "failed"
        self.mock_pipeline.to_json.return_value = json.dumps(failed_pipeline_data)

        mock_do_time.return_value = 1672574400000000000

        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_span.return_value = mock_span

        processor = PipelineProcessor(
            self.mock_config, self.mock_project, self.mock_pipeline
        )

        result_span = processor.create_pipeline_span(mock_tracer, [])

        # Verify error status was set
        mock_span.set_status.assert_called_once()
        call_args = mock_span.set_status.call_args[0][0]
        assert call_args.status_code == StatusCode.ERROR
        assert "Pipeline failed" in call_args.description

    @patch.dict(os.environ, {"CI_PARENT_PIPELINE": "12345", "CI_PROJECT_ID": "456"})
    @patch("new_relic_exporter.processors.pipeline_processor.get_tracer")
    def test_process_success_with_data(self, mock_get_tracer):
        """Test successful processing with jobs and bridges."""
        # Setup mocks
        mock_tracer = MagicMock()
        mock_get_tracer.return_value = mock_tracer

        mock_span = MagicMock()
        mock_tracer.start_span.return_value = mock_span

        mock_context = MagicMock()

        # Setup jobs and bridges
        mock_job = MagicMock()
        mock_job.to_json.return_value = json.dumps(
            {"name": "test-job", "stage": "test"}
        )
        mock_bridge = MagicMock()
        mock_bridge.to_json.return_value = json.dumps(
            {"name": "deploy-bridge", "stage": "deploy"}
        )

        self.mock_pipeline.jobs.list.return_value = [mock_job]
        self.mock_pipeline.bridges.list.return_value = [mock_bridge]

        processor = PipelineProcessor(
            self.mock_config, self.mock_project, self.mock_pipeline
        )

        with patch(
            "new_relic_exporter.processors.pipeline_processor.trace.set_span_in_context"
        ) as mock_set_context:
            mock_set_context.return_value = mock_context

            result = processor.process("http://endpoint", {"auth": "token"}, [])

        pipeline_span, pipeline_context, job_lst, bridge_lst = result

        assert pipeline_span == mock_span
        assert pipeline_context == mock_context
        assert len(job_lst) == 1
        assert len(bridge_lst) == 1
        assert job_lst[0]["name"] == "test-job"
        assert bridge_lst[0]["name"] == "deploy-bridge"

    @patch.dict(os.environ, {"CI_PARENT_PIPELINE": "12345", "CI_PROJECT_ID": "456"})
    @patch("new_relic_exporter.processors.pipeline_processor.get_tracer")
    def test_process_no_data_to_export(self, mock_get_tracer):
        """Test processing when no jobs or bridges to export."""
        # Setup mocks
        mock_tracer = MagicMock()
        mock_get_tracer.return_value = mock_tracer

        # No jobs or bridges
        self.mock_pipeline.jobs.list.return_value = []
        self.mock_pipeline.bridges.list.return_value = []

        processor = PipelineProcessor(
            self.mock_config, self.mock_project, self.mock_pipeline
        )

        result = processor.process("http://endpoint", {"auth": "token"}, [])

        pipeline_span, pipeline_context, job_lst, bridge_lst = result

        # Should return None values when no data to export
        assert pipeline_span is None
        assert pipeline_context is None
        assert job_lst == []
        assert bridge_lst == []

    @patch.dict(os.environ, {"CI_PARENT_PIPELINE": "12345", "CI_PROJECT_ID": "456"})
    @patch("new_relic_exporter.processors.pipeline_processor.get_tracer")
    def test_process_all_jobs_excluded(self, mock_get_tracer):
        """Test processing when all jobs are excluded."""
        # Setup mocks
        mock_tracer = MagicMock()
        mock_get_tracer.return_value = mock_tracer

        # Setup jobs that will be excluded
        mock_job = MagicMock()
        mock_job.to_json.return_value = json.dumps(
            {"name": "deploy", "stage": "deploy"}
        )

        self.mock_pipeline.jobs.list.return_value = [mock_job]
        self.mock_pipeline.bridges.list.return_value = []

        processor = PipelineProcessor(
            self.mock_config, self.mock_project, self.mock_pipeline
        )

        # Exclude all jobs
        result = processor.process("http://endpoint", {"auth": "token"}, ["deploy"])

        pipeline_span, pipeline_context, job_lst, bridge_lst = result

        # Should return None values when all jobs excluded
        assert pipeline_span is None
        assert pipeline_context is None
        assert job_lst == []
        assert bridge_lst == []

    @patch("new_relic_exporter.processors.pipeline_processor.do_time")
    def test_finalize_pipeline_with_span(self, mock_do_time):
        """Test finalizing pipeline with valid span."""
        mock_do_time.return_value = 1672577000000000000  # Mock end timestamp

        mock_span = MagicMock()

        processor = PipelineProcessor(
            self.mock_config, self.mock_project, self.mock_pipeline
        )

        processor.finalize_pipeline(mock_span)

        # Verify span was ended with correct timestamp
        mock_span.end.assert_called_once_with(end_time=1672577000000000000)

    def test_finalize_pipeline_with_none_span(self):
        """Test finalizing pipeline with None span."""
        processor = PipelineProcessor(
            self.mock_config, self.mock_project, self.mock_pipeline
        )

        # Should not raise exception with None span
        processor.finalize_pipeline(None)

    def test_service_name_formatting(self):
        """Test service name formatting with various project names."""
        test_cases = [
            ("Test Group/Test Project", "test-group/test-project"),
            ("My Org / My App", "my-org/my-app"),
            ("single-project", "single-project"),
            ("UPPER CASE / LOWER case", "upper-case/lower-case"),
        ]

        for project_name, expected_service_name in test_cases:
            mock_project = MagicMock()
            mock_project.attributes = {"name_with_namespace": project_name}

            processor = PipelineProcessor(
                self.mock_config, mock_project, self.mock_pipeline
            )

            assert processor.service_name == expected_service_name

    @patch("new_relic_exporter.processors.pipeline_processor.parse_attributes")
    def test_create_pipeline_span_filters_none_attributes(self, mock_parse_attrs):
        """Test that None and empty string attributes are filtered out."""
        # Setup attributes with None and empty values
        mock_parse_attrs.return_value = {
            "valid_attr": "value",
            "none_attr": None,
            "empty_attr": "",
            "zero_attr": 0,
            "false_attr": False,
        }

        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_span.return_value = mock_span

        processor = PipelineProcessor(
            self.mock_config, self.mock_project, self.mock_pipeline
        )

        with patch(
            "new_relic_exporter.processors.pipeline_processor.grab_span_att_vars",
            return_value={},
        ):
            processor.create_pipeline_span(mock_tracer, [])

        # Verify set_attributes was called with filtered attributes
        mock_span.set_attributes.assert_called_once()
        call_args = mock_span.set_attributes.call_args[0][0]

        # Should include valid values but exclude None and empty strings
        assert "valid_attr" in call_args
        assert "none_attr" not in call_args
        assert "empty_attr" not in call_args
        assert "zero_attr" in call_args  # 0 is valid
        assert "false_attr" in call_args  # False is valid
