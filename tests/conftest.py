import pytest
import os
import sys
from unittest.mock import MagicMock, patch


@pytest.fixture(autouse=True)
def mock_otel_exporters():
    """Mock OpenTelemetry exporters to prevent real network calls during testing."""
    from unittest.mock import MagicMock

    with patch(
        "opentelemetry.exporter.otlp.proto.grpc.trace_exporter.OTLPSpanExporter"
    ) as mock_span_exporter, patch(
        "opentelemetry.exporter.otlp.proto.grpc.metric_exporter.OTLPMetricExporter"
    ) as mock_metric_exporter, patch(
        "opentelemetry.exporter.otlp.proto.grpc._log_exporter.OTLPLogExporter"
    ) as mock_log_exporter, patch(
        "shared.otel.get_tracer"
    ) as mock_get_tracer, patch(
        "shared.otel.get_logger"
    ) as mock_get_logger, patch(
        "shared.otel.get_meter"
    ) as mock_get_meter, patch(
        "new_relic_exporter.processors.pipeline_processor.get_tracer"
    ) as mock_pipeline_tracer, patch(
        "new_relic_exporter.processors.job_processor.get_tracer"
    ) as mock_job_tracer, patch(
        "new_relic_exporter.processors.job_processor.get_logger"
    ) as mock_job_logger, patch(
        "new_relic_exporter.processors.bridge_processor.get_tracer"
    ) as mock_bridge_tracer:

        # Use mock exporters that don't make network calls
        mock_span_exporter.return_value = MagicMock()
        mock_metric_exporter.return_value = MagicMock()
        mock_log_exporter.return_value = MagicMock()

        # Mock the otel helper functions to return mock objects
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_span.return_value = mock_span

        mock_logger = MagicMock()
        mock_meter = MagicMock()

        # Configure all tracer mocks to return the same mock tracer
        mock_get_tracer.return_value = mock_tracer
        mock_pipeline_tracer.return_value = mock_tracer
        mock_job_tracer.return_value = mock_tracer
        mock_bridge_tracer.return_value = mock_tracer

        # Configure all logger mocks to return the same mock logger
        mock_get_logger.return_value = mock_logger
        mock_job_logger.return_value = mock_logger

        # Configure meter mock
        mock_get_meter.return_value = mock_meter

        yield


@pytest.fixture(autouse=True)
def clean_imports():
    """Automatically clean up imports before each test."""
    modules_to_clean = [
        "new_relic_exporter.main",
        "shared.global_variables",
        "shared.custom_parsers",
    ]

    for module in modules_to_clean:
        if module in sys.modules:
            del sys.modules[module]

    yield

    # Clean up after test as well
    for module in modules_to_clean:
        if module in sys.modules:
            del sys.modules[module]


@pytest.fixture(scope="session")
def test_environment():
    """Session-wide test environment setup."""
    return {
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


@pytest.fixture
def clean_environment():
    """Fixture to provide a clean environment for each test."""
    original_env = os.environ.copy()
    os.environ.clear()
    yield
    os.environ.clear()
    os.environ.update(original_env)


@pytest.fixture
def mock_gitlab_client():
    """Fixture providing a fully configured mock GitLab client."""
    mock_gl = MagicMock()

    # Configure project mock
    mock_project = MagicMock()
    mock_project.id = 123
    mock_project.name = "test-project"
    mock_project.attributes = {
        "id": 123,
        "name": "test-project",
        "namespace": {"name": "test-namespace"},
        "web_url": "https://gitlab.com/test-namespace/test-project",
    }

    # Configure pipeline mock
    mock_pipeline = MagicMock()
    mock_pipeline.id = 789
    mock_pipeline.status = "success"
    mock_pipeline.started_at = "2024-01-01T00:00:00.000Z"
    mock_pipeline.finished_at = "2024-01-01T01:00:00.000Z"
    mock_pipeline.duration = 3600
    mock_pipeline.ref = "main"
    mock_pipeline.sha = "abc123def456"
    mock_pipeline.web_url = (
        "https://gitlab.com/test-namespace/test-project/-/pipelines/789"
    )
    mock_pipeline.bridges.list.return_value = []
    mock_pipeline.jobs.list.return_value = []
    mock_pipeline.to_json.return_value = '{"id": 789, "status": "success"}'

    # Wire up the mocks
    mock_project.pipelines.get.return_value = mock_pipeline
    mock_gl.projects.get.return_value = mock_project

    return mock_gl


@pytest.fixture
def mock_successful_environment():
    """Fixture providing a complete successful test environment."""
    return {
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


@pytest.fixture
def sample_pipeline_data():
    """Fixture providing sample pipeline data for testing."""
    return {
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


@pytest.fixture
def sample_job_data():
    """Fixture providing sample job data for testing."""
    return {
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
