"""
Tests for the GitLab exporter module.

This module tests the main GitLabExporter class that orchestrates
the processing of GitLab pipelines and jobs for export to New Relic.
"""

import os
import pytest
from unittest.mock import patch, MagicMock, Mock
import gitlab
from gitlab.exceptions import GitlabGetError

from new_relic_exporter.exporters.gitlab_exporter import GitLabExporter, main
from shared.error_handling import GitLabAPIError, ConfigurationError


class TestGitLabExporter:
    """Test suite for GitLabExporter class."""

    @patch("new_relic_exporter.exporters.gitlab_exporter.get_config")
    @patch("gitlab.Gitlab")
    def test_init_success_with_custom_endpoint(
        self, mock_gitlab_class, mock_get_config
    ):
        """Test successful initialization with custom GitLab endpoint."""
        # Setup mock config
        mock_config = MagicMock()
        mock_config.endpoint = "https://custom-gitlab.com/"
        mock_config.token = "test-token"
        mock_get_config.return_value = mock_config

        # Setup mock GitLab client
        mock_gitlab_instance = MagicMock()
        mock_gitlab_class.return_value = mock_gitlab_instance

        # Initialize exporter
        exporter = GitLabExporter()

        # Verify initialization
        assert exporter.config == mock_config
        assert exporter.gl == mock_gitlab_instance
        mock_gitlab_class.assert_called_once_with(
            "https://custom-gitlab.com/", private_token="test-token"
        )

    @patch("new_relic_exporter.exporters.gitlab_exporter.get_config")
    @patch("gitlab.Gitlab")
    def test_init_success_with_default_endpoint(
        self, mock_gitlab_class, mock_get_config
    ):
        """Test successful initialization with default GitLab endpoint."""
        # Setup mock config
        mock_config = MagicMock()
        mock_config.endpoint = "https://gitlab.com/"
        mock_config.token = "test-token"
        mock_get_config.return_value = mock_config

        # Setup mock GitLab client
        mock_gitlab_instance = MagicMock()
        mock_gitlab_class.return_value = mock_gitlab_instance

        # Initialize exporter
        exporter = GitLabExporter()

        # Verify initialization
        mock_gitlab_class.assert_called_once_with(private_token="test-token")

    @patch("new_relic_exporter.exporters.gitlab_exporter.get_config")
    @patch("gitlab.Gitlab")
    def test_init_success_with_none_endpoint(self, mock_gitlab_class, mock_get_config):
        """Test successful initialization with None endpoint."""
        # Setup mock config
        mock_config = MagicMock()
        mock_config.endpoint = None
        mock_config.token = "test-token"
        mock_get_config.return_value = mock_config

        # Setup mock GitLab client
        mock_gitlab_instance = MagicMock()
        mock_gitlab_class.return_value = mock_gitlab_instance

        # Initialize exporter
        exporter = GitLabExporter()

        # Verify initialization
        mock_gitlab_class.assert_called_once_with(private_token="test-token")

    @patch("new_relic_exporter.exporters.gitlab_exporter.get_config")
    def test_init_config_error(self, mock_get_config):
        """Test initialization failure due to config error."""
        mock_get_config.side_effect = Exception("Config load failed")

        with pytest.raises(ConfigurationError) as exc_info:
            GitLabExporter()

        assert "Failed to load configuration" in str(exc_info.value)

    @patch("new_relic_exporter.exporters.gitlab_exporter.get_config")
    @patch("gitlab.Gitlab")
    def test_init_gitlab_client_error(self, mock_gitlab_class, mock_get_config):
        """Test initialization failure due to GitLab client error."""
        # Setup mock config
        mock_config = MagicMock()
        mock_config.endpoint = "https://gitlab.com/"
        mock_config.token = "test-token"
        mock_get_config.return_value = mock_config

        # Make GitLab client initialization fail
        mock_gitlab_class.side_effect = Exception("GitLab client failed")

        with pytest.raises(GitLabAPIError) as exc_info:
            GitLabExporter()

        assert "Failed to initialize GitLab client" in str(exc_info.value)

    def test_get_exclude_jobs_list_empty(self):
        """Test get_exclude_jobs_list with no environment variable."""
        with patch.dict(os.environ, {}, clear=True):
            with patch(
                "new_relic_exporter.exporters.gitlab_exporter.get_config"
            ), patch("gitlab.Gitlab"):
                exporter = GitLabExporter()
                exclude_jobs = exporter.get_exclude_jobs_list()
                assert exclude_jobs == []

    def test_get_exclude_jobs_list_with_jobs(self):
        """Test get_exclude_jobs_list with jobs specified."""
        with patch.dict(os.environ, {"GLAB_EXCLUDE_JOBS": "Deploy,Test,Build"}):
            with patch(
                "new_relic_exporter.exporters.gitlab_exporter.get_config"
            ), patch("gitlab.Gitlab"):
                exporter = GitLabExporter()
                exclude_jobs = exporter.get_exclude_jobs_list()
                assert exclude_jobs == ["deploy", "test", "build"]

    def test_get_exclude_jobs_list_with_spaces_and_empty(self):
        """Test get_exclude_jobs_list with spaces and empty values."""
        with patch.dict(os.environ, {"GLAB_EXCLUDE_JOBS": " Deploy , , Test , Build "}):
            with patch(
                "new_relic_exporter.exporters.gitlab_exporter.get_config"
            ), patch("gitlab.Gitlab"):
                exporter = GitLabExporter()
                exclude_jobs = exporter.get_exclude_jobs_list()
                assert exclude_jobs == ["deploy", "test", "build"]

    @patch.dict(os.environ, {"CI_PROJECT_ID": "123", "CI_PARENT_PIPELINE": "456"})
    @patch("new_relic_exporter.exporters.gitlab_exporter.get_config")
    @patch("gitlab.Gitlab")
    @patch("new_relic_exporter.exporters.gitlab_exporter.PipelineProcessor")
    @patch("new_relic_exporter.exporters.gitlab_exporter.JobProcessor")
    @patch("new_relic_exporter.exporters.gitlab_exporter.DownstreamProcessor")
    def test_export_pipeline_data_success(
        self,
        mock_downstream_proc,
        mock_job_proc,
        mock_pipeline_proc,
        mock_gitlab_class,
        mock_get_config,
    ):
        """Test successful pipeline data export."""
        # Setup mocks
        mock_config = MagicMock()
        mock_config.otel_endpoint = "http://otel-endpoint"
        mock_config.gitlab_headers = {"Authorization": "Bearer token"}
        mock_get_config.return_value = mock_config

        mock_gl = MagicMock()
        mock_gitlab_class.return_value = mock_gl

        # Setup project and pipeline mocks
        mock_project = MagicMock()
        mock_project.name = "test-project"
        mock_pipeline = MagicMock()
        mock_pipeline.iid = 123
        mock_pipeline.status = "success"
        mock_pipeline.ref = "main"

        mock_gl.projects.get.return_value = mock_project
        mock_project.pipelines.get.return_value = mock_pipeline

        # Setup processor mocks
        mock_pipeline_span = MagicMock()
        mock_pipeline_context = MagicMock()
        mock_job_lst = [{"name": "test-job"}]
        mock_bridge_lst = [{"id": 1, "name": "test-bridge", "status": "success"}]

        mock_pipeline_processor_instance = MagicMock()
        mock_pipeline_processor_instance.process.return_value = (
            mock_pipeline_span,
            mock_pipeline_context,
            mock_job_lst,
            mock_bridge_lst,
        )
        mock_pipeline_processor_instance.service_name = "test-service"
        mock_pipeline_proc.return_value = mock_pipeline_processor_instance

        mock_job_processor_instance = MagicMock()
        mock_job_proc.return_value = mock_job_processor_instance

        mock_downstream_processor_instance = MagicMock()
        mock_downstream_proc.return_value = mock_downstream_processor_instance

        # Initialize and run exporter
        exporter = GitLabExporter()
        exporter.export_pipeline_data()

        # Verify calls
        mock_gl.projects.get.assert_called_once_with("123")
        mock_project.pipelines.get.assert_called_once_with("456")
        mock_pipeline_processor_instance.process.assert_called_once()
        mock_job_processor_instance.process.assert_called_once()
        mock_downstream_processor_instance.process_bridges_with_downstream.assert_called_once()
        mock_pipeline_processor_instance.finalize_pipeline.assert_called_once_with(
            mock_pipeline_span
        )

    @patch.dict(os.environ, {"CI_PROJECT_ID": "123", "CI_PARENT_PIPELINE": "456"})
    @patch("new_relic_exporter.exporters.gitlab_exporter.get_config")
    @patch("gitlab.Gitlab")
    @patch("new_relic_exporter.exporters.gitlab_exporter.PipelineProcessor")
    def test_export_pipeline_data_no_data_to_export(
        self, mock_pipeline_proc, mock_gitlab_class, mock_get_config
    ):
        """Test pipeline data export when no data to export."""
        # Setup mocks
        mock_config = MagicMock()
        mock_get_config.return_value = mock_config

        mock_gl = MagicMock()
        mock_gitlab_class.return_value = mock_gl

        # Setup project and pipeline mocks
        mock_project = MagicMock()
        mock_pipeline = MagicMock()
        mock_gl.projects.get.return_value = mock_project
        mock_project.pipelines.get.return_value = mock_pipeline

        # Setup processor to return None (no data)
        mock_pipeline_processor_instance = MagicMock()
        mock_pipeline_processor_instance.process.return_value = (None, None, None, None)
        mock_pipeline_proc.return_value = mock_pipeline_processor_instance

        # Initialize and run exporter
        exporter = GitLabExporter()
        exporter.export_pipeline_data()

        # Verify early return
        mock_pipeline_processor_instance.process.assert_called_once()
        mock_pipeline_processor_instance.finalize_pipeline.assert_not_called()

    def test_export_pipeline_data_missing_project_id(self):
        """Test export_pipeline_data with missing CI_PROJECT_ID."""
        with patch.dict(os.environ, {"CI_PARENT_PIPELINE": "456"}, clear=True):
            with patch(
                "new_relic_exporter.exporters.gitlab_exporter.get_config"
            ), patch("gitlab.Gitlab"):
                exporter = GitLabExporter()

                with pytest.raises(ConfigurationError) as exc_info:
                    exporter.export_pipeline_data()

                assert "Missing required environment variables" in str(exc_info.value)

    def test_export_pipeline_data_missing_pipeline_id(self):
        """Test export_pipeline_data with missing CI_PARENT_PIPELINE."""
        with patch.dict(os.environ, {"CI_PROJECT_ID": "123"}, clear=True):
            with patch(
                "new_relic_exporter.exporters.gitlab_exporter.get_config"
            ), patch("gitlab.Gitlab"):
                exporter = GitLabExporter()

                with pytest.raises(ConfigurationError) as exc_info:
                    exporter.export_pipeline_data()

                assert "Missing required environment variables" in str(exc_info.value)

    @patch.dict(os.environ, {"CI_PROJECT_ID": "123", "CI_PARENT_PIPELINE": "456"})
    @patch("new_relic_exporter.exporters.gitlab_exporter.get_config")
    @patch("gitlab.Gitlab")
    def test_export_pipeline_data_gitlab_get_error(
        self, mock_gitlab_class, mock_get_config
    ):
        """Test export_pipeline_data with GitLab API error."""
        # Setup mocks
        mock_config = MagicMock()
        mock_get_config.return_value = mock_config

        mock_gl = MagicMock()
        mock_gitlab_class.return_value = mock_gl

        # Make project.get raise GitlabGetError
        gitlab_error = GitlabGetError("Not found")
        gitlab_error.response_code = 404
        mock_gl.projects.get.side_effect = gitlab_error

        # Initialize and run exporter
        exporter = GitLabExporter()

        with pytest.raises(GitLabAPIError) as exc_info:
            exporter.export_pipeline_data()

        assert "Failed to retrieve project or pipeline" in str(exc_info.value)

    @patch.dict(os.environ, {"CI_PROJECT_ID": "123", "CI_PARENT_PIPELINE": "456"})
    @patch("new_relic_exporter.exporters.gitlab_exporter.get_config")
    @patch("gitlab.Gitlab")
    @patch("new_relic_exporter.exporters.gitlab_exporter.PipelineProcessor")
    def test_export_pipeline_data_unexpected_error(
        self, mock_pipeline_proc, mock_gitlab_class, mock_get_config
    ):
        """Test export_pipeline_data with unexpected error."""
        # Setup mocks
        mock_config = MagicMock()
        mock_get_config.return_value = mock_config

        mock_gl = MagicMock()
        mock_gitlab_class.return_value = mock_gl

        # Setup project and pipeline mocks
        mock_project = MagicMock()
        mock_pipeline = MagicMock()
        mock_gl.projects.get.return_value = mock_project
        mock_project.pipelines.get.return_value = mock_pipeline

        # Make processor raise unexpected error
        mock_pipeline_processor_instance = MagicMock()
        mock_pipeline_processor_instance.process.side_effect = RuntimeError(
            "Unexpected error"
        )
        mock_pipeline_proc.return_value = mock_pipeline_processor_instance

        # Initialize and run exporter
        exporter = GitLabExporter()

        with pytest.raises(RuntimeError):
            exporter.export_pipeline_data()

    @patch.dict(os.environ, {"CI_PROJECT_ID": "123", "CI_PARENT_PIPELINE": "456"})
    @patch("new_relic_exporter.exporters.gitlab_exporter.get_config")
    @patch("gitlab.Gitlab")
    @patch("new_relic_exporter.exporters.gitlab_exporter.PipelineProcessor")
    def test_export_pipeline_data_session_cleanup(
        self, mock_pipeline_proc, mock_gitlab_class, mock_get_config
    ):
        """Test that GitLab session is properly cleaned up."""
        # Setup mocks
        mock_config = MagicMock()
        mock_get_config.return_value = mock_config

        mock_gl = MagicMock()
        mock_session = MagicMock()
        mock_gl.session = mock_session
        mock_gitlab_class.return_value = mock_gl

        # Setup project and pipeline mocks
        mock_project = MagicMock()
        mock_pipeline = MagicMock()
        mock_gl.projects.get.return_value = mock_project
        mock_project.pipelines.get.return_value = mock_pipeline

        # Setup processor to return no data (early return)
        mock_pipeline_processor_instance = MagicMock()
        mock_pipeline_processor_instance.process.return_value = (None, None, None, None)
        mock_pipeline_proc.return_value = mock_pipeline_processor_instance

        # Initialize and run exporter
        exporter = GitLabExporter()
        exporter.export_pipeline_data()

        # Verify session cleanup
        mock_session.close.assert_called_once()

    @patch.dict(
        os.environ,
        {
            "CI_PROJECT_ID": "123",
            "CI_PARENT_PIPELINE": "456",
            "GLAB_EXCLUDE_JOBS": "deploy,test",
        },
    )
    @patch("new_relic_exporter.exporters.gitlab_exporter.get_config")
    @patch("gitlab.Gitlab")
    @patch("new_relic_exporter.exporters.gitlab_exporter.PipelineProcessor")
    @patch("new_relic_exporter.exporters.gitlab_exporter.JobProcessor")
    @patch("new_relic_exporter.exporters.gitlab_exporter.BridgeProcessor")
    def test_export_pipeline_data_with_exclude_jobs(
        self,
        mock_bridge_proc,
        mock_job_proc,
        mock_pipeline_proc,
        mock_gitlab_class,
        mock_get_config,
    ):
        """Test pipeline data export with job exclusions."""
        # Setup mocks
        mock_config = MagicMock()
        mock_config.otel_endpoint = "http://otel-endpoint"
        mock_config.gitlab_headers = {"Authorization": "Bearer token"}
        mock_get_config.return_value = mock_config

        mock_gl = MagicMock()
        mock_gitlab_class.return_value = mock_gl

        # Setup project and pipeline mocks
        mock_project = MagicMock()
        mock_project.name = "test-project"
        mock_pipeline = MagicMock()
        mock_pipeline.iid = 123
        mock_pipeline.status = "success"

        mock_gl.projects.get.return_value = mock_project
        mock_project.pipelines.get.return_value = mock_pipeline

        # Setup processor mocks
        mock_pipeline_span = MagicMock()
        mock_pipeline_context = MagicMock()
        mock_job_lst = [{"name": "build-job"}]
        mock_bridge_lst = []

        mock_pipeline_processor_instance = MagicMock()
        mock_pipeline_processor_instance.process.return_value = (
            mock_pipeline_span,
            mock_pipeline_context,
            mock_job_lst,
            mock_bridge_lst,
        )
        mock_pipeline_processor_instance.service_name = "test-service"
        mock_pipeline_proc.return_value = mock_pipeline_processor_instance

        mock_job_processor_instance = MagicMock()
        mock_job_proc.return_value = mock_job_processor_instance

        mock_bridge_processor_instance = MagicMock()
        mock_bridge_proc.return_value = mock_bridge_processor_instance

        # Initialize and run exporter
        exporter = GitLabExporter()
        exporter.export_pipeline_data()

        # Verify exclude jobs were passed to processor
        args, kwargs = mock_pipeline_processor_instance.process.call_args
        exclude_jobs_arg = args[2]  # Third argument should be exclude_jobs
        assert exclude_jobs_arg == ["deploy", "test"]


class TestMainFunction:
    """Test suite for main function."""

    @patch("new_relic_exporter.exporters.gitlab_exporter.GitLabExporter")
    def test_main_function(self, mock_exporter_class):
        """Test main function creates exporter and calls export_pipeline_data."""
        mock_exporter_instance = MagicMock()
        mock_exporter_class.return_value = mock_exporter_instance

        main()

        mock_exporter_class.assert_called_once()
        mock_exporter_instance.export_pipeline_data.assert_called_once()
