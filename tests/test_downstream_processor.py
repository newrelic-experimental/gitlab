"""
Tests for downstream processor functionality.
"""

import pytest
import json
from unittest.mock import MagicMock, patch, Mock
from opentelemetry import trace
from shared.config.settings import GitLabConfig
from new_relic_exporter.processors.downstream_processor import DownstreamProcessor


class TestDownstreamProcessor:
    """Test DownstreamProcessor class."""

    @pytest.fixture
    def mock_config(self):
        """Create a mock GitLab config."""
        config = MagicMock(spec=GitLabConfig)
        config.low_data_mode = False
        return config

    @pytest.fixture
    def mock_gitlab_client(self):
        """Create a mock GitLab client."""
        return MagicMock()

    @pytest.fixture
    def downstream_processor(self, mock_config, mock_gitlab_client):
        """Create a DownstreamProcessor instance."""
        with patch("new_relic_exporter.processors.downstream_processor.get_logger"):
            return DownstreamProcessor(mock_config, mock_gitlab_client)

    @pytest.fixture
    def sample_bridge_data(self):
        """Sample bridge data with downstream pipeline info."""
        return {
            "id": 1001,
            "name": "trigger-downstream",
            "status": "success",
            "started_at": "2024-01-01T00:00:00.000Z",
            "finished_at": "2024-01-01T00:30:00.000Z",
            "downstream_pipeline": {
                "id": 2001,
                "project_id": 456,
                "status": "success",
                "web_url": "https://gitlab.com/downstream/project/-/pipelines/2001",
            },
        }

    @pytest.fixture
    def sample_downstream_jobs(self):
        """Sample downstream jobs data."""
        return [
            {
                "id": 3001,
                "name": "downstream-job-1",
                "status": "success",
                "stage": "build",
                "started_at": "2024-01-01T00:01:00.000Z",
                "finished_at": "2024-01-01T00:03:00.000Z",
            },
            {
                "id": 3002,
                "name": "downstream-job-2",
                "status": "success",
                "stage": "test",
                "started_at": "2024-01-01T00:03:00.000Z",
                "finished_at": "2024-01-01T00:04:00.000Z",
            },
        ]

    def test_init(self, mock_config, mock_gitlab_client):
        """Test DownstreamProcessor initialization."""
        with patch(
            "new_relic_exporter.processors.downstream_processor.get_logger"
        ) as mock_logger:
            processor = DownstreamProcessor(mock_config, mock_gitlab_client)

            assert processor.config == mock_config
            assert processor.gitlab_client == mock_gitlab_client
            assert len(processor.processed_pipelines) == 0
            mock_logger.assert_called_once_with(
                "gitlab-exporter", "downstream-processor"
            )

    def test_get_downstream_pipeline_data_success(
        self, downstream_processor, mock_gitlab_client
    ):
        """Test successful downstream pipeline data retrieval."""
        # Setup mocks
        mock_project = MagicMock()
        mock_pipeline = MagicMock()
        mock_pipeline.to_json.return_value = json.dumps(
            {"id": 2001, "status": "success"}
        )

        mock_gitlab_client.projects.get.return_value = mock_project
        mock_project.pipelines.get.return_value = mock_pipeline

        result = downstream_processor.get_downstream_pipeline_data(456, 2001)

        assert result is not None
        assert result["project"] == mock_project
        assert result["pipeline"] == mock_pipeline
        assert result["pipeline_json"]["id"] == 2001
        mock_gitlab_client.projects.get.assert_called_once_with(456)
        mock_project.pipelines.get.assert_called_once_with(2001)

    def test_get_downstream_pipeline_data_failure(
        self, downstream_processor, mock_gitlab_client
    ):
        """Test downstream pipeline data retrieval failure."""
        mock_gitlab_client.projects.get.side_effect = Exception("Access denied")

        result = downstream_processor.get_downstream_pipeline_data(456, 2001)

        assert result is None

    def test_get_downstream_jobs_and_bridges(
        self, downstream_processor, sample_downstream_jobs
    ):
        """Test getting downstream jobs and bridges."""
        # Setup mocks
        mock_project = MagicMock()
        mock_pipeline = MagicMock()

        # Mock jobs
        mock_jobs = []
        for job_data in sample_downstream_jobs:
            mock_job = MagicMock()
            mock_job.to_json.return_value = json.dumps(job_data)
            mock_jobs.append(mock_job)

        mock_pipeline.jobs.list.return_value = mock_jobs
        mock_pipeline.bridges.list.return_value = []

        jobs, bridges = downstream_processor.get_downstream_jobs_and_bridges(
            mock_project, mock_pipeline, []
        )

        assert len(jobs) == 2
        assert len(bridges) == 0
        assert jobs[0]["name"] == "downstream-job-1"
        assert jobs[1]["name"] == "downstream-job-2"

    def test_get_downstream_jobs_and_bridges_with_exclusions(
        self, downstream_processor, sample_downstream_jobs
    ):
        """Test getting downstream jobs with exclusions."""
        # Setup mocks
        mock_project = MagicMock()
        mock_pipeline = MagicMock()

        # Mock jobs
        mock_jobs = []
        for job_data in sample_downstream_jobs:
            mock_job = MagicMock()
            mock_job.to_json.return_value = json.dumps(job_data)
            mock_jobs.append(mock_job)

        mock_pipeline.jobs.list.return_value = mock_jobs
        mock_pipeline.bridges.list.return_value = []

        # Exclude one job by name
        jobs, bridges = downstream_processor.get_downstream_jobs_and_bridges(
            mock_project, mock_pipeline, ["downstream-job-1"]
        )

        assert len(jobs) == 1
        assert jobs[0]["name"] == "downstream-job-2"

    @patch("new_relic_exporter.processors.downstream_processor.JobProcessor")
    @patch("new_relic_exporter.processors.downstream_processor.BridgeProcessor")
    def test_process_downstream_pipeline(
        self,
        mock_bridge_processor_class,
        mock_job_processor_class,
        downstream_processor,
        sample_downstream_jobs,
    ):
        """Test processing a downstream pipeline."""
        # Setup mocks
        mock_project = MagicMock()
        mock_pipeline = MagicMock()
        mock_pipeline.to_json.return_value = json.dumps(
            {"id": 2001, "status": "success"}
        )

        # Mock jobs
        mock_jobs = []
        for job_data in sample_downstream_jobs:
            mock_job = MagicMock()
            mock_job.to_json.return_value = json.dumps(job_data)
            mock_jobs.append(mock_job)

        mock_pipeline.jobs.list.return_value = mock_jobs
        mock_pipeline.bridges.list.return_value = []

        downstream_processor.gitlab_client.projects.get.return_value = mock_project
        mock_project.pipelines.get.return_value = mock_pipeline

        # Mock processors
        mock_job_processor = MagicMock()
        mock_bridge_processor = MagicMock()
        mock_job_processor_class.return_value = mock_job_processor
        mock_bridge_processor_class.return_value = mock_bridge_processor

        downstream_info = {
            "downstream_project_id": 456,
            "downstream_pipeline_id": 2001,
            "downstream_status": "success",
        }

        mock_context = MagicMock()

        downstream_processor.process_downstream_pipeline(
            downstream_info,
            mock_context,
            "http://otel-endpoint",
            "headers",
            "test-service",
            [],
        )

        # Verify job processor was called
        mock_job_processor_class.assert_called_once_with(
            downstream_processor.config, mock_project
        )
        mock_job_processor.process.assert_called_once()

        # Verify the jobs passed to processor
        call_args = mock_job_processor.process.call_args
        processed_jobs = call_args[0][0]
        assert len(processed_jobs) == 2
        assert processed_jobs[0]["name"] == "downstream-job-1"

    def test_process_downstream_pipeline_max_depth(self, downstream_processor):
        """Test that max depth is respected."""
        downstream_info = {
            "downstream_project_id": 456,
            "downstream_pipeline_id": 2001,
        }

        mock_context = MagicMock()

        # Should return early due to max depth
        downstream_processor.process_downstream_pipeline(
            downstream_info,
            mock_context,
            "http://otel-endpoint",
            "headers",
            "test-service",
            [],
            max_depth=2,
            current_depth=2,
        )

        # Should not have made any GitLab API calls
        downstream_processor.gitlab_client.projects.get.assert_not_called()

    def test_process_downstream_pipeline_cycle_detection(self, downstream_processor):
        """Test cycle detection prevents infinite loops."""
        downstream_info = {
            "downstream_project_id": 456,
            "downstream_pipeline_id": 2001,
        }

        # Add pipeline to processed set
        downstream_processor.processed_pipelines.add("456:2001")

        mock_context = MagicMock()

        downstream_processor.process_downstream_pipeline(
            downstream_info,
            mock_context,
            "http://otel-endpoint",
            "headers",
            "test-service",
            [],
        )

        # Should not have made any GitLab API calls due to cycle detection
        downstream_processor.gitlab_client.projects.get.assert_not_called()

    @patch("new_relic_exporter.processors.downstream_processor.BridgeProcessor")
    def test_process_bridges_with_downstream(
        self, mock_bridge_processor_class, downstream_processor, sample_bridge_data
    ):
        """Test processing bridges with downstream pipelines."""
        mock_bridge_processor = MagicMock()
        mock_bridge_processor_class.return_value = mock_bridge_processor
        mock_bridge_processor.get_bridge_downstream_info.return_value = {
            "downstream_project_id": 456,
            "downstream_pipeline_id": 2001,
            "downstream_status": "success",
        }

        # Mock the downstream pipeline processing
        with patch.object(
            downstream_processor, "process_downstream_pipeline"
        ) as mock_process_downstream:
            bridge_list = [sample_bridge_data]
            mock_context = MagicMock()

            downstream_processor.process_bridges_with_downstream(
                bridge_list,
                mock_context,
                "http://otel-endpoint",
                "headers",
                "test-service",
                [],
            )

            # Verify bridge processor was called
            mock_bridge_processor.process.assert_called_once()

            # Verify downstream processing was called
            mock_process_downstream.assert_called_once()

    def test_process_bridges_with_downstream_empty_list(self, downstream_processor):
        """Test processing empty bridge list."""
        mock_context = MagicMock()

        # Should not raise any exceptions
        downstream_processor.process_bridges_with_downstream(
            [], mock_context, "http://otel-endpoint", "headers", "test-service", []
        )

    def test_process_method_compatibility(self, downstream_processor):
        """Test the abstract process method implementation."""
        # Test with sufficient arguments
        with patch.object(
            downstream_processor, "process_bridges_with_downstream"
        ) as mock_process_bridges:
            args = [[], MagicMock(), "endpoint", "headers", "service", []]
            downstream_processor.process(*args)
            mock_process_bridges.assert_called_once_with(*args)

        # Test with insufficient arguments
        with pytest.raises(ValueError, match="Invalid arguments"):
            downstream_processor.process("not", "enough", "args")

    def test_get_downstream_jobs_and_bridges_exception_handling(
        self, downstream_processor
    ):
        """Test exception handling in get_downstream_jobs_and_bridges."""
        mock_project = MagicMock()
        mock_pipeline = MagicMock()
        mock_pipeline.jobs.list.side_effect = Exception("API Error")

        jobs, bridges = downstream_processor.get_downstream_jobs_and_bridges(
            mock_project, mock_pipeline, []
        )

        assert jobs == []
        assert bridges == []
