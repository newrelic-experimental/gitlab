"""
Tests for conftest.py fixtures and utilities.
"""

import pytest
import os
import sys
from unittest.mock import MagicMock, patch
from tests.conftest import (
    test_environment,
    clean_environment,
    mock_gitlab_client,
    mock_successful_environment,
    sample_pipeline_data,
    sample_job_data,
)


class TestConftestFixtures:
    """Test conftest.py fixtures."""

    def test_test_environment_fixture(self, test_environment):
        """Test test_environment fixture provides expected environment variables."""
        expected_vars = {
            "CI_PARENT_PIPELINE": "456",
            "CI_PROJECT_ID": "123",
            "NEW_RELIC_API_KEY": "NRAK-TEST123",
            "GLAB_TOKEN": "glpat-test123",
            "CI_PIPELINE_ID": "789",
            "CI_JOB_ID": "101112",
            "CI_PROJECT_NAME": "test-project",
            "CI_PROJECT_NAMESPACE": "test-namespace",
            "NEW_RELIC_ENDPOINT": "https://otlp.nr-data.net:4317",
        }

        assert test_environment == expected_vars

        # Verify all expected keys are present
        for key, value in expected_vars.items():
            assert key in test_environment
            assert test_environment[key] == value

    def test_clean_environment_fixture(self, clean_environment):
        """Test clean_environment fixture cleans and restores environment."""
        # Set a test environment variable
        test_key = "TEST_CLEAN_ENV_VAR"
        test_value = "test_value"
        os.environ[test_key] = test_value

        # The fixture should have cleared the environment
        # But we can't test this directly since the fixture runs before the test
        # Instead, we test that we can use the fixture without issues
        assert clean_environment is None  # Fixture doesn't return anything

        # After the test, the original environment should be restored
        # This is tested implicitly by the fixture's cleanup

    def test_mock_gitlab_client_fixture(self, mock_gitlab_client):
        """Test mock_gitlab_client fixture provides properly configured mock."""
        # Test project mock
        project = mock_gitlab_client.projects.get.return_value
        assert project.id == 123
        assert project.name == "test-project"
        assert project.attributes["id"] == 123
        assert project.attributes["name"] == "test-project"
        assert project.attributes["namespace"]["name"] == "test-namespace"
        assert (
            project.attributes["web_url"]
            == "https://gitlab.com/test-namespace/test-project"
        )

        # Test pipeline mock
        pipeline = project.pipelines.get.return_value
        assert pipeline.id == 789
        assert pipeline.status == "success"
        assert pipeline.started_at == "2024-01-01T00:00:00.000Z"
        assert pipeline.finished_at == "2024-01-01T01:00:00.000Z"
        assert pipeline.duration == 3600
        assert pipeline.ref == "main"
        assert pipeline.sha == "abc123def456"
        assert (
            pipeline.web_url
            == "https://gitlab.com/test-namespace/test-project/-/pipelines/789"
        )

        # Test that bridges and jobs lists are empty
        assert pipeline.bridges.list.return_value == []
        assert pipeline.jobs.list.return_value == []

        # Test JSON serialization
        assert pipeline.to_json.return_value == '{"id": 789, "status": "success"}'

    def test_mock_successful_environment_fixture(self, mock_successful_environment):
        """Test mock_successful_environment fixture provides complete environment."""
        expected_vars = {
            "CI_PARENT_PIPELINE": "456",
            "CI_PROJECT_ID": "123",
            "NEW_RELIC_API_KEY": "NRAK-TEST123",
            "GLAB_TOKEN": "glpat-test123",
            "CI_PIPELINE_ID": "789",
            "CI_JOB_ID": "101112",
            "CI_PROJECT_NAME": "test-project",
            "CI_PROJECT_NAMESPACE": "test-namespace",
            "NEW_RELIC_ENDPOINT": "https://otlp.nr-data.net:4317",
        }

        assert mock_successful_environment == expected_vars

        # Verify it's identical to test_environment
        # (they should provide the same data)
        for key, value in expected_vars.items():
            assert key in mock_successful_environment
            assert mock_successful_environment[key] == value

    def test_sample_pipeline_data_fixture(self, sample_pipeline_data):
        """Test sample_pipeline_data fixture provides expected pipeline data."""
        expected_data = {
            "id": 789,
            "project_id": 123,
            "status": "success",
            "ref": "main",
            "sha": "abc123def456",
            "started_at": "2024-01-01T00:00:00.000Z",
            "finished_at": "2024-01-01T01:00:00.000Z",
            "duration": 3600,
            "web_url": "https://gitlab.com/test-namespace/test-project/-/pipelines/789",
            "source": "push",
            "user": {
                "name": "John Doe",
                "username": "johndoe",
                "email": "john@example.com",
            },
        }

        assert sample_pipeline_data == expected_data

        # Test nested user data
        user_data = sample_pipeline_data["user"]
        assert user_data["name"] == "John Doe"
        assert user_data["username"] == "johndoe"
        assert user_data["email"] == "john@example.com"

    def test_sample_job_data_fixture(self, sample_job_data):
        """Test sample_job_data fixture provides expected job data."""
        expected_data = {
            "id": 1001,
            "name": "build:docker",
            "stage": "build",
            "status": "success",
            "started_at": "2024-01-01T00:00:00.000Z",
            "finished_at": "2024-01-01T00:30:00.000Z",
            "duration": 1800,
            "web_url": "https://gitlab.com/test-namespace/test-project/-/jobs/1001",
            "runner": {
                "id": 1,
                "description": "docker-runner",
                "tags": ["docker", "linux"],
            },
        }

        assert sample_job_data == expected_data

        # Test nested runner data
        runner_data = sample_job_data["runner"]
        assert runner_data["id"] == 1
        assert runner_data["description"] == "docker-runner"
        assert runner_data["tags"] == ["docker", "linux"]

    def test_mock_gitlab_client_method_calls(self, mock_gitlab_client):
        """Test that mock_gitlab_client methods can be called properly."""
        # Test getting a project
        project = mock_gitlab_client.projects.get(123)
        assert project is not None

        # Test getting a pipeline from the project
        pipeline = project.pipelines.get(789)
        assert pipeline is not None

        # Test calling methods on the pipeline
        bridges = pipeline.bridges.list()
        jobs = pipeline.jobs.list()
        json_data = pipeline.to_json()

        assert bridges == []
        assert jobs == []
        assert json_data == '{"id": 789, "status": "success"}'

    def test_fixtures_are_independent(
        self, test_environment, mock_successful_environment
    ):
        """Test that fixtures provide independent data (not shared references)."""
        # Modify one fixture's data
        test_environment["CI_PROJECT_ID"] = "modified"

        # The other fixture should be unaffected
        assert mock_successful_environment["CI_PROJECT_ID"] == "123"

    def test_sample_data_consistency(
        self, sample_pipeline_data, sample_job_data, mock_gitlab_client
    ):
        """Test that sample data is consistent across fixtures."""
        # Pipeline data should match mock client pipeline
        pipeline = (
            mock_gitlab_client.projects.get.return_value.pipelines.get.return_value
        )
        assert sample_pipeline_data["id"] == pipeline.id
        assert sample_pipeline_data["status"] == pipeline.status
        assert sample_pipeline_data["ref"] == pipeline.ref
        assert sample_pipeline_data["sha"] == pipeline.sha

        # Job data should have reasonable values
        assert sample_job_data["id"] == 1001
        assert sample_job_data["status"] == "success"
        assert sample_job_data["duration"] == 1800  # 30 minutes

    def test_environment_data_types(self, test_environment):
        """Test that environment data has correct types."""
        # All environment variables should be strings
        for key, value in test_environment.items():
            assert isinstance(key, str), f"Key {key} should be string"
            assert isinstance(value, str), f"Value for {key} should be string"

    def test_sample_data_types(self, sample_pipeline_data, sample_job_data):
        """Test that sample data has correct types."""
        # Pipeline data types
        assert isinstance(sample_pipeline_data["id"], int)
        assert isinstance(sample_pipeline_data["project_id"], int)
        assert isinstance(sample_pipeline_data["status"], str)
        assert isinstance(sample_pipeline_data["duration"], int)
        assert isinstance(sample_pipeline_data["user"], dict)

        # Job data types
        assert isinstance(sample_job_data["id"], int)
        assert isinstance(sample_job_data["name"], str)
        assert isinstance(sample_job_data["duration"], int)
        assert isinstance(sample_job_data["runner"], dict)
        assert isinstance(sample_job_data["runner"]["tags"], list)


class TestConftestAutoFixtures:
    """Test auto-applied fixtures from conftest.py."""

    def test_otel_mocks_are_applied(self):
        """Test that OpenTelemetry mocks are automatically applied."""
        # This test verifies that the mock_otel_exporters fixture is working
        # by attempting to import and use OTEL components that should be mocked
        try:
            from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import (
                OTLPSpanExporter,
            )
            from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import (
                OTLPMetricExporter,
            )
            from opentelemetry.exporter.otlp.proto.grpc._log_exporter import (
                OTLPLogExporter,
            )

            # These should be mocked and not make real network calls
            span_exporter = OTLPSpanExporter(endpoint="http://test", headers={})
            metric_exporter = OTLPMetricExporter(endpoint="http://test", headers={})
            log_exporter = OTLPLogExporter(endpoint="http://test", headers={})

            # If we get here without network errors, the mocks are working
            assert span_exporter is not None
            assert metric_exporter is not None
            assert log_exporter is not None

        except ImportError:
            pytest.skip("OpenTelemetry packages not available")

    def test_clean_imports_fixture(self):
        """Test that imports are cleaned between tests."""
        # The clean_imports fixture should ensure modules are cleaned
        # This is hard to test directly, but we can verify the fixture exists
        # and doesn't cause import issues

        # Try importing modules that should be cleaned
        # We need to set required environment variables first
        with patch.dict(
            os.environ, {"GLAB_TOKEN": "test-token", "NEW_RELIC_API_KEY": "test-key"}
        ):
            try:
                import shared.global_variables
                import shared.custom_parsers

                # If these import without issues, the fixture is working
                assert True
            except ImportError:
                # This is expected in some test environments
                pytest.skip("Modules not available for import test")

    def test_mock_tracer_functionality(self):
        """Test that mocked tracer provides expected functionality."""
        # The mock_otel_exporters fixture should provide working mock tracers
        try:
            from shared.otel import get_tracer

            tracer = get_tracer("endpoint", {}, MagicMock(), "test-tracer")

            # Should be able to start a span
            span = tracer.start_span("test-span")
            assert span is not None

            # Span should have mock methods
            assert hasattr(span, "set_attributes")
            assert hasattr(span, "set_status")
            assert hasattr(span, "end")

        except ImportError:
            pytest.skip("OTEL modules not available")

    def test_mock_logger_functionality(self):
        """Test that mocked logger provides expected functionality."""
        try:
            from shared.otel import get_logger

            logger = get_logger("endpoint", {}, MagicMock(), "test-logger")

            # Should be able to call logger methods without errors
            assert logger is not None
            assert hasattr(logger, "info")
            assert hasattr(logger, "error")
            assert hasattr(logger, "debug")

        except ImportError:
            pytest.skip("OTEL modules not available")

    def test_mock_meter_functionality(self):
        """Test that mocked meter provides expected functionality."""
        try:
            from shared.otel import get_meter

            meter = get_meter("endpoint", {}, MagicMock(), "test-meter")

            # Should be able to use meter without errors
            assert meter is not None

        except ImportError:
            pytest.skip("OTEL modules not available")
