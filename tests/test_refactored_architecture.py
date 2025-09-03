"""
Tests for the refactored GitLab New Relic Exporter architecture.

Tests the new processor-based architecture with focused classes.
"""

import pytest
import os
from unittest.mock import Mock, patch, MagicMock
from new_relic_exporter.processors.base_processor import BaseProcessor
from new_relic_exporter.processors.pipeline_processor import PipelineProcessor
from new_relic_exporter.processors.job_processor import JobProcessor
from new_relic_exporter.processors.bridge_processor import BridgeProcessor
from new_relic_exporter.exporters.gitlab_exporter import GitLabExporter
from shared.config.settings import GitLabConfig, reset_config


class TestBaseProcessor:
    """Test the base processor functionality."""

    def test_base_processor_initialization(self):
        """Test base processor initialization."""
        config = GitLabConfig(
            token="test_token",
            new_relic_api_key="test_key",
            service_name="test-service",
        )

        # Create a concrete implementation for testing
        class TestProcessor(BaseProcessor):
            def process(self, *args, **kwargs):
                return "processed"

        processor = TestProcessor(config)
        assert processor.config == config
        assert processor.service_name == "test-service"

    def test_create_resource_attributes(self):
        """Test resource attributes creation."""
        config = GitLabConfig(
            token="test_token",
            new_relic_api_key="test_key",
            service_name="test-service",
        )

        class TestProcessor(BaseProcessor):
            def process(self, *args, **kwargs):
                return "processed"

        processor = TestProcessor(config)
        base_attrs = {"custom": "value"}

        result = processor.create_resource_attributes(base_attrs)

        assert result["instrumentation.name"] == "gitlab-integration"
        assert result["gitlab.source"] == "gitlab-exporter"
        assert result["service.name"] == "test-service"
        assert result["custom"] == "value"

    def test_should_exclude_item(self):
        """Test item exclusion logic."""
        config = GitLabConfig(token="test_token", new_relic_api_key="test_key")

        class TestProcessor(BaseProcessor):
            def process(self, *args, **kwargs):
                return "processed"

        processor = TestProcessor(config)
        exclude_list = ["test-job", "excluded-stage"]

        # Test exporter stage exclusion
        assert processor.should_exclude_item("job", "new-relic-exporter", exclude_list)
        assert processor.should_exclude_item(
            "job", "new-relic-metrics-exporter", exclude_list
        )

        # Test exclude list
        assert processor.should_exclude_item("test-job", "stage", exclude_list)
        assert processor.should_exclude_item("job", "excluded-stage", exclude_list)

        # Test non-excluded items
        assert not processor.should_exclude_item(
            "allowed-job", "allowed-stage", exclude_list
        )


class TestPipelineProcessor:
    """Test the pipeline processor."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration."""
        return GitLabConfig(
            token="test_token",
            new_relic_api_key="test_key",
            low_data_mode=False,
            export_logs=True,
        )

    @pytest.fixture
    def mock_project(self):
        """Create a mock GitLab project."""
        project = Mock()
        project.attributes = {"name_with_namespace": "Test Project"}
        return project

    @pytest.fixture
    def mock_pipeline(self):
        """Create a mock GitLab pipeline."""
        pipeline = Mock()
        pipeline_data = {
            "id": 123,
            "status": "success",
            "started_at": "2024-01-01T10:00:00Z",
            "finished_at": "2024-01-01T10:30:00Z",
        }
        pipeline.to_json.return_value = '{"id": 123, "status": "success", "started_at": "2024-01-01T10:00:00Z", "finished_at": "2024-01-01T10:30:00Z"}'

        # Mock jobs and bridges
        job_mock = Mock()
        job_mock.to_json.return_value = (
            '{"id": 1, "name": "test-job", "stage": "test", "status": "success"}'
        )
        pipeline.jobs.list.return_value = [job_mock]
        pipeline.bridges.list.return_value = []

        return pipeline

    def test_pipeline_processor_initialization(
        self, mock_config, mock_project, mock_pipeline
    ):
        """Test pipeline processor initialization."""
        processor = PipelineProcessor(mock_config, mock_project, mock_pipeline)

        assert processor.config == mock_config
        assert processor.project == mock_project
        assert processor.pipeline == mock_pipeline
        assert processor.service_name == "testproject"

    def test_create_pipeline_resource(self, mock_config, mock_project, mock_pipeline):
        """Test pipeline resource creation."""
        with patch.dict(
            os.environ, {"CI_PARENT_PIPELINE": "123", "CI_PROJECT_ID": "456"}
        ):
            processor = PipelineProcessor(mock_config, mock_project, mock_pipeline)
            resource = processor.create_pipeline_resource()

            attrs = resource.attributes
            assert attrs["service.name"] == "testproject"
            assert attrs["pipeline_id"] == "123"
            assert attrs["project_id"] == "456"
            assert attrs["instrumentation.name"] == "gitlab-integration"

    def test_get_filtered_jobs_and_bridges(
        self, mock_config, mock_project, mock_pipeline
    ):
        """Test job and bridge filtering."""
        processor = PipelineProcessor(mock_config, mock_project, mock_pipeline)
        exclude_jobs = ["excluded-job"]

        jobs, bridges = processor.get_filtered_jobs_and_bridges(exclude_jobs)

        assert len(jobs) == 1
        assert jobs[0]["name"] == "test-job"
        assert len(bridges) == 0


class TestJobProcessor:
    """Test the job processor."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration."""
        return GitLabConfig(
            token="test_token",
            new_relic_api_key="test_key",
            low_data_mode=False,
            export_logs=True,
        )

    @pytest.fixture
    def mock_project(self):
        """Create a mock GitLab project."""
        project = Mock()
        mock_job = Mock()
        mock_job.trace = Mock()
        project.jobs.get.return_value = mock_job
        return project

    def test_job_processor_initialization(self, mock_config, mock_project):
        """Test job processor initialization."""
        processor = JobProcessor(mock_config, mock_project)

        assert processor.config == mock_config
        assert processor.project == mock_project
        assert processor.ansi_escape is not None

    def test_create_job_resource(self, mock_config, mock_project):
        """Test job resource creation."""
        with patch.dict(
            os.environ, {"CI_PARENT_PIPELINE": "123", "CI_PROJECT_ID": "456"}
        ):
            processor = JobProcessor(mock_config, mock_project)
            job_data = {"id": 789, "name": "test-job"}

            resource = processor.create_job_resource(job_data, "test-service")

            attrs = resource.attributes
            assert attrs["service.name"] == "test-service"
            assert attrs["job_id"] == "789"
            assert attrs["pipeline_id"] == "123"
            assert attrs["project_id"] == "456"


class TestBridgeProcessor:
    """Test the bridge processor."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock configuration."""
        return GitLabConfig(
            token="test_token",
            new_relic_api_key="test_key",
            low_data_mode=False,
            export_logs=True,
        )

    @pytest.fixture
    def mock_project(self):
        """Create a mock GitLab project."""
        project = Mock()
        return project

    def test_bridge_processor_initialization(self, mock_config, mock_project):
        """Test bridge processor initialization."""
        processor = BridgeProcessor(mock_config, mock_project)

        assert processor.config == mock_config
        assert processor.project == mock_project

    def test_create_bridge_resource(self, mock_config, mock_project):
        """Test bridge resource creation."""
        with patch.dict(
            os.environ, {"CI_PARENT_PIPELINE": "123", "CI_PROJECT_ID": "456"}
        ):
            processor = BridgeProcessor(mock_config, mock_project)
            bridge_data = {"id": 999, "name": "trigger-downstream"}

            resource = processor.create_bridge_resource(bridge_data, "test-service")

            attrs = resource.attributes
            assert attrs["service.name"] == "test-service"
            assert attrs["bridge_id"] == "999"
            assert attrs["pipeline_id"] == "123"
            assert attrs["project_id"] == "456"

    def test_get_bridge_downstream_info(self, mock_config, mock_project):
        """Test downstream pipeline info extraction."""
        processor = BridgeProcessor(mock_config, mock_project)

        # Test with downstream pipeline info
        bridge_data_with_downstream = {
            "id": 999,
            "name": "trigger-downstream",
            "downstream_pipeline": {
                "project_id": 789,
                "id": 456,
                "status": "success",
                "web_url": "https://gitlab.com/project/pipelines/456",
            },
        }

        result = processor.get_bridge_downstream_info(bridge_data_with_downstream)
        assert result["downstream_project_id"] == 789
        assert result["downstream_pipeline_id"] == 456
        assert result["downstream_status"] == "success"

        # Test without downstream pipeline info
        bridge_data_without_downstream = {"id": 999, "name": "trigger-downstream"}
        result = processor.get_bridge_downstream_info(bridge_data_without_downstream)
        assert result is None

    @patch("new_relic_exporter.processors.bridge_processor.get_tracer")
    def test_process_bridge_skipped(self, mock_get_tracer, mock_config, mock_project):
        """Test processing a skipped bridge."""
        processor = BridgeProcessor(mock_config, mock_project)

        # Mock tracer
        mock_tracer = Mock()
        mock_span = Mock()
        mock_tracer.start_span.return_value = mock_span
        mock_get_tracer.return_value = mock_tracer

        bridge_data = {"id": 999, "name": "trigger-downstream", "status": "skipped"}
        mock_context = Mock()

        processor.process_bridge(
            bridge_data,
            mock_context,
            "https://test.endpoint",
            "api-key=test",
            "test-service",
        )

        # Verify span was created and ended for skipped bridge
        mock_tracer.start_span.assert_called_once()
        mock_span.end.assert_called_once()

    @patch("new_relic_exporter.processors.bridge_processor.get_tracer")
    @patch("new_relic_exporter.processors.bridge_processor.do_time")
    def test_process_bridge_success(
        self, mock_do_time, mock_get_tracer, mock_config, mock_project
    ):
        """Test processing a successful bridge."""
        processor = BridgeProcessor(mock_config, mock_project)

        # Mock tracer and time
        mock_tracer = Mock()
        mock_span = Mock()
        mock_tracer.start_span.return_value = mock_span
        mock_get_tracer.return_value = mock_tracer
        mock_do_time.return_value = 1234567890

        bridge_data = {
            "id": 999,
            "name": "trigger-downstream",
            "status": "success",
            "started_at": "2024-01-01T10:00:00Z",
            "finished_at": "2024-01-01T10:05:00Z",
            "downstream_pipeline": {
                "project_id": 789,
                "id": 456,
                "status": "success",
                "web_url": "https://gitlab.com/project/pipelines/456",
            },
        }
        mock_context = Mock()

        with patch("opentelemetry.trace.use_span"):
            processor.process_bridge(
                bridge_data,
                mock_context,
                "https://test.endpoint",
                "api-key=test",
                "test-service",
            )

        # Verify span was created with proper timing
        mock_tracer.start_span.assert_called_once()
        mock_span.end.assert_called_once()


class TestGitLabExporter:
    """Test the main GitLab exporter."""

    @patch("new_relic_exporter.exporters.gitlab_exporter.gitlab.Gitlab")
    @patch("new_relic_exporter.exporters.gitlab_exporter.get_config")
    def test_exporter_initialization(self, mock_get_config, mock_gitlab):
        """Test exporter initialization."""
        mock_config = GitLabConfig(token="test_token", new_relic_api_key="test_key")
        mock_get_config.return_value = mock_config
        mock_gitlab_instance = Mock()
        mock_gitlab.return_value = mock_gitlab_instance

        exporter = GitLabExporter()
        assert exporter.config == mock_config
        assert exporter.gl == mock_gitlab_instance

    @patch("new_relic_exporter.exporters.gitlab_exporter.gitlab.Gitlab")
    @patch("new_relic_exporter.exporters.gitlab_exporter.get_config")
    def test_get_exclude_jobs_list(self, mock_get_config, mock_gitlab):
        """Test exclude jobs list parsing."""
        mock_config = GitLabConfig(token="test_token", new_relic_api_key="test_key")
        mock_get_config.return_value = mock_config
        mock_gitlab.return_value = Mock()

        exporter = GitLabExporter()

        # Test with no environment variable
        with patch.dict(os.environ, {}, clear=True):
            result = exporter.get_exclude_jobs_list()
            assert result == []

        # Test with exclude jobs
        with patch.dict(os.environ, {"GLAB_EXCLUDE_JOBS": "job1, job2 , job3"}):
            result = exporter.get_exclude_jobs_list()
            assert result == ["job1", "job2", "job3"]

    @patch("new_relic_exporter.exporters.gitlab_exporter.gitlab.Gitlab")
    @patch("new_relic_exporter.exporters.gitlab_exporter.get_config")
    def test_export_pipeline_data_missing_env_vars(self, mock_get_config, mock_gitlab):
        """Test export with missing environment variables."""
        mock_config = GitLabConfig(token="test_token", new_relic_api_key="test_key")
        mock_get_config.return_value = mock_config
        mock_gitlab.return_value = Mock()

        exporter = GitLabExporter()

        # Test with missing environment variables - should raise ConfigurationError
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(Exception) as exc_info:
                exporter.export_pipeline_data()

            # Verify it's a ConfigurationError with the expected message
            assert (
                "Missing required environment variables: CI_PROJECT_ID or CI_PARENT_PIPELINE"
                in str(exc_info.value)
            )


class TestRefactoredArchitectureIntegration:
    """Integration tests for the refactored architecture."""

    @patch("new_relic_exporter.exporters.gitlab_exporter.gitlab.Gitlab")
    @patch("new_relic_exporter.exporters.gitlab_exporter.get_config")
    def test_full_pipeline_processing_flow(self, mock_get_config, mock_gitlab):
        """Test the complete pipeline processing flow."""
        # Setup mocks
        mock_config = GitLabConfig(
            token="test_token",
            new_relic_api_key="test_key",
            otel_endpoint="https://test.endpoint",
            low_data_mode=False,
            export_logs=True,
        )
        mock_get_config.return_value = mock_config

        # Mock GitLab objects
        mock_project = Mock()
        mock_project.attributes = {"name_with_namespace": "Test Project"}

        mock_pipeline = Mock()
        mock_pipeline.to_json.return_value = '{"id": 123, "status": "success", "started_at": "2024-01-01T10:00:00Z", "finished_at": "2024-01-01T10:30:00Z"}'

        mock_job = Mock()
        mock_job.to_json.return_value = '{"id": 1, "name": "test-job", "stage": "test", "status": "success", "started_at": "2024-01-01T10:05:00Z", "finished_at": "2024-01-01T10:10:00Z"}'
        mock_pipeline.jobs.list.return_value = [mock_job]
        mock_pipeline.bridges.list.return_value = []

        # Mock GitLab client instance
        mock_gl_instance = Mock()
        mock_gl_instance.projects.get.return_value = mock_project
        mock_project.pipelines.get.return_value = mock_pipeline
        mock_gitlab.return_value = mock_gl_instance

        # Mock tracer (handled by global fixture)
        mock_span = Mock()
        mock_tracer = Mock()
        mock_tracer.start_span.return_value = mock_span

        # Test the flow
        exporter = GitLabExporter()

        with patch.dict(
            os.environ, {"CI_PROJECT_ID": "456", "CI_PARENT_PIPELINE": "123"}
        ):
            with patch("shared.custom_parsers.do_time") as mock_do_time:
                with patch(
                    "opentelemetry.trace.set_span_in_context"
                ) as mock_set_context:
                    mock_do_time.return_value = 1234567890
                    mock_context = Mock()
                    mock_set_context.return_value = mock_context

                    # This should complete without errors
                    exporter.export_pipeline_data()

                    # Verify key interactions
                    mock_gl_instance.projects.get.assert_called_with("456")
                    mock_project.pipelines.get.assert_called_with("123")
                    mock_pipeline.jobs.list.assert_called_with(get_all=True)
