"""
Tests for new_relic_exporter.processors.job_processor module.

Comprehensive tests for JobProcessor class and job processing functionality.
"""

import pytest
import os
import tempfile
from unittest.mock import patch, MagicMock, mock_open, call
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from new_relic_exporter.processors.job_processor import JobProcessor


class TestJobProcessorInitialization:
    """Test suite for JobProcessor initialization."""

    def test_job_processor_init(self, mock_successful_environment):
        """Test JobProcessor initialization."""
        mock_config = MagicMock()
        mock_project = MagicMock()

        processor = JobProcessor(mock_config, mock_project)

        assert processor.config == mock_config
        assert processor.project == mock_project
        assert processor.ansi_escape is not None
        assert processor.logger is not None

    def test_job_processor_ansi_escape_pattern(self, mock_successful_environment):
        """Test ANSI escape pattern compilation."""
        mock_config = MagicMock()
        mock_project = MagicMock()

        processor = JobProcessor(mock_config, mock_project)

        # Test ANSI escape sequence removal
        test_string = "\x1b[31mRed text\x1b[0m"
        cleaned = processor.ansi_escape.sub(" ", test_string)
        assert "\x1b" not in cleaned
        assert "Red text" in cleaned


class TestJobResourceCreation:
    """Test suite for job resource creation."""

    def test_create_job_resource_basic(self, mock_successful_environment):
        """Test basic job resource creation."""
        mock_config = MagicMock()
        mock_config.low_data_mode = False
        mock_project = MagicMock()

        processor = JobProcessor(mock_config, mock_project)

        job_data = {"id": 12345, "name": "test-job", "status": "success"}
        service_name = "test-service"

        with patch.dict(
            os.environ, {"CI_PARENT_PIPELINE": "456", "CI_PROJECT_ID": "123"}
        ):
            with patch(
                "new_relic_exporter.processors.job_processor.parse_attributes"
            ) as mock_parse:
                with patch(
                    "new_relic_exporter.processors.job_processor.create_resource_attributes"
                ) as mock_create_attrs:
                    mock_parse.return_value = {"parsed": "attributes"}
                    mock_create_attrs.return_value = {"created": "attributes"}

                    resource = processor.create_job_resource(job_data, service_name)

                    assert isinstance(resource, Resource)
                    mock_parse.assert_called_once_with(job_data)
                    mock_create_attrs.assert_called_once()

    def test_create_job_resource_low_data_mode(self, mock_successful_environment):
        """Test job resource creation in low data mode."""
        mock_config = MagicMock()
        mock_config.low_data_mode = True
        mock_project = MagicMock()

        processor = JobProcessor(mock_config, mock_project)

        job_data = {"id": 12345, "name": "test-job", "status": "success"}
        service_name = "test-service"

        with patch.dict(
            os.environ, {"CI_PARENT_PIPELINE": "456", "CI_PROJECT_ID": "123"}
        ):
            with patch(
                "new_relic_exporter.processors.job_processor.parse_attributes"
            ) as mock_parse:
                resource = processor.create_job_resource(job_data, service_name)

                assert isinstance(resource, Resource)
                # Should not parse attributes in low data mode
                mock_parse.assert_not_called()

    def test_create_job_resource_filters_none_values(self, mock_successful_environment):
        """Test job resource creation filters out None values."""
        mock_config = MagicMock()
        mock_config.low_data_mode = False
        mock_project = MagicMock()

        processor = JobProcessor(mock_config, mock_project)

        job_data = {"id": 12345, "name": "test-job", "status": "success"}
        service_name = "test-service"

        with patch.dict(
            os.environ, {"CI_PARENT_PIPELINE": "456", "CI_PROJECT_ID": "123"}
        ):
            with patch(
                "new_relic_exporter.processors.job_processor.parse_attributes"
            ) as mock_parse:
                with patch(
                    "new_relic_exporter.processors.job_processor.create_resource_attributes"
                ) as mock_create_attrs:
                    mock_parse.return_value = {
                        "valid": "value",
                        "none_field": None,
                        "empty_field": "",
                    }
                    mock_create_attrs.return_value = {"created": "attributes"}

                    resource = processor.create_job_resource(job_data, service_name)

                    # Verify None and empty values are filtered
                    assert isinstance(resource, Resource)


class TestJobLogHandling:
    """Test suite for job log handling."""

    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data=b"Log line 1\nLog line 2\nLog line 3\n",
    )
    def test_handle_job_logs_success(self, mock_file, mock_successful_environment):
        """Test successful job log handling."""
        mock_config = MagicMock()
        mock_project = MagicMock()

        # Setup mock job
        mock_job = MagicMock()
        mock_job.trace = MagicMock()
        mock_project.jobs.get.return_value = mock_job

        processor = JobProcessor(mock_config, mock_project)

        job_data = {"id": 12345}
        endpoint = "https://otlp.nr-data.net"
        headers = "api-key=test"
        resource_attributes = {"job_id": "12345"}
        service_name = "test-service"
        error_status = False

        # Should not raise exception
        processor.handle_job_logs(
            job_data, endpoint, headers, resource_attributes, service_name, error_status
        )

        mock_project.jobs.get.assert_called_once_with(12345, lazy=True)
        mock_job.trace.assert_called_once()

    @patch("builtins.open", side_effect=Exception("File error"))
    def test_handle_job_logs_exception(self, mock_file, mock_successful_environment):
        """Test job log handling with exception."""
        mock_config = MagicMock()
        mock_project = MagicMock()

        # Setup mock job
        mock_job = MagicMock()
        mock_project.jobs.get.return_value = mock_job

        processor = JobProcessor(mock_config, mock_project)

        job_data = {"id": 12345}
        endpoint = "https://otlp.nr-data.net"
        headers = "api-key=test"
        resource_attributes = {"job_id": "12345"}
        service_name = "test-service"
        error_status = False

        # Should handle exception gracefully
        processor.handle_job_logs(
            job_data, endpoint, headers, resource_attributes, service_name, error_status
        )

        # Should still attempt to get job
        mock_project.jobs.get.assert_called_once_with(12345, lazy=True)

    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data=b"Line with \x1b[31mANSI\x1b[0m codes\n",
    )
    def test_handle_job_logs_ansi_removal(self, mock_file, mock_successful_environment):
        """Test ANSI escape sequence removal in job logs."""
        mock_config = MagicMock()
        mock_project = MagicMock()

        # Setup mock job
        mock_job = MagicMock()
        mock_project.jobs.get.return_value = mock_job

        processor = JobProcessor(mock_config, mock_project)

        job_data = {"id": 12345}
        endpoint = "https://otlp.nr-data.net"
        headers = "api-key=test"
        resource_attributes = {"job_id": "12345"}
        service_name = "test-service"
        error_status = False

        processor.handle_job_logs(
            job_data, endpoint, headers, resource_attributes, service_name, error_status
        )

        # Verify ANSI codes are processed
        mock_project.jobs.get.assert_called_once()


class TestErrorMessageExtraction:
    """Test suite for error message extraction."""

    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data=b"Some logs\nERROR: Job failed: Script execution failed\nMore logs\n",
    )
    def test_extract_error_message_from_logs(
        self, mock_file, mock_successful_environment
    ):
        """Test error message extraction from job logs."""
        mock_config = MagicMock()
        mock_project = MagicMock()

        # Setup mock job
        mock_job = MagicMock()
        mock_project.jobs.get.return_value = mock_job

        processor = JobProcessor(mock_config, mock_project)

        job_data = {"id": 12345, "failure_reason": "script_failure"}

        with patch("shared.custom_parsers.do_parse", return_value=True):
            error_message = processor.extract_error_message(job_data)

            assert "Script execution failed" in error_message
            mock_project.jobs.get.assert_called_once_with(12345, lazy=True)

    @patch(
        "builtins.open",
        new_callable=mock_open,
        read_data=b"Some logs without error message\n",
    )
    def test_extract_error_message_fallback(
        self, mock_file, mock_successful_environment
    ):
        """Test error message extraction fallback to failure_reason."""
        mock_config = MagicMock()
        mock_project = MagicMock()

        # Setup mock job
        mock_job = MagicMock()
        mock_project.jobs.get.return_value = mock_job

        processor = JobProcessor(mock_config, mock_project)

        job_data = {"id": 12345, "failure_reason": "runner_system_failure"}

        with patch("shared.custom_parsers.do_parse", return_value=False):
            error_message = processor.extract_error_message(job_data)

            assert error_message == "runner_system_failure"

    @patch("builtins.open", side_effect=Exception("File error"))
    def test_extract_error_message_exception(
        self, mock_file, mock_successful_environment
    ):
        """Test error message extraction with exception."""
        mock_config = MagicMock()
        mock_project = MagicMock()

        # Setup mock job
        mock_job = MagicMock()
        mock_project.jobs.get.return_value = mock_job

        processor = JobProcessor(mock_config, mock_project)

        job_data = {"id": 12345, "failure_reason": "script_failure"}

        error_message = processor.extract_error_message(job_data)

        # Should fallback to failure_reason on exception
        assert error_message == "script_failure"

    def test_extract_error_message_no_failure_reason(self, mock_successful_environment):
        """Test error message extraction with no failure_reason."""
        mock_config = MagicMock()
        mock_project = MagicMock()

        processor = JobProcessor(mock_config, mock_project)

        job_data = {"id": 12345}

        with patch("builtins.open", side_effect=Exception("File error")):
            error_message = processor.extract_error_message(job_data)

            assert error_message == "Unknown error"


class TestJobProcessing:
    """Test suite for individual job processing."""

    def test_process_job_skipped_status(self, mock_successful_environment):
        """Test processing of skipped jobs."""
        mock_config = MagicMock()
        mock_config.low_data_mode = False
        mock_config.export_logs = False
        mock_project = MagicMock()

        processor = JobProcessor(mock_config, mock_project)

        job_data = {
            "id": 12345,
            "name": "test-job",
            "status": "skipped",
            "started_at": "2024-01-01T10:00:00Z",
            "finished_at": "2024-01-01T10:05:00Z",
        }

        mock_context = MagicMock()
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_span.return_value = mock_span

        with patch(
            "new_relic_exporter.processors.job_processor.get_tracer",
            return_value=mock_tracer,
        ):
            processor.process_job(
                job_data,
                mock_context,
                "https://otlp.nr-data.net",
                "api-key=test",
                "test-service",
            )

            # Verify skipped job span creation
            mock_tracer.start_span.assert_called_once()
            call_args = mock_tracer.start_span.call_args
            assert "SKIPPED" in call_args[1]["name"]
            mock_span.end.assert_called_once()

    def test_process_job_success_status(self, mock_successful_environment):
        """Test processing of successful jobs."""
        mock_config = MagicMock()
        mock_config.low_data_mode = False
        mock_config.export_logs = False
        mock_project = MagicMock()

        processor = JobProcessor(mock_config, mock_project)

        job_data = {
            "id": 12345,
            "name": "test-job",
            "status": "success",
            "started_at": "2024-01-01T10:00:00Z",
            "finished_at": "2024-01-01T10:05:00Z",
        }

        mock_context = MagicMock()
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_span.return_value = mock_span

        with patch(
            "new_relic_exporter.processors.job_processor.get_tracer",
            return_value=mock_tracer,
        ):
            with patch(
                "new_relic_exporter.processors.job_processor.do_time",
                return_value=1000000000,
            ):
                with patch(
                    "new_relic_exporter.processors.job_processor.parse_attributes",
                    return_value={"parsed": "attrs"},
                ):
                    with patch(
                        "new_relic_exporter.processors.job_processor.trace.use_span"
                    ):
                        processor.process_job(
                            job_data,
                            mock_context,
                            "https://otlp.nr-data.net",
                            "api-key=test",
                            "test-service",
                        )

                        # Verify successful job processing
                        mock_tracer.start_span.assert_called_once()
                        mock_span.set_attributes.assert_called_once_with(
                            {"parsed": "attrs"}
                        )
                        mock_span.end.assert_called_once()

    def test_process_job_failed_status(self, mock_successful_environment):
        """Test processing of failed jobs."""
        mock_config = MagicMock()
        mock_config.low_data_mode = False
        mock_config.export_logs = False
        mock_project = MagicMock()

        processor = JobProcessor(mock_config, mock_project)

        job_data = {
            "id": 12345,
            "name": "test-job",
            "status": "failed",
            "started_at": "2024-01-01T10:00:00Z",
            "finished_at": "2024-01-01T10:05:00Z",
            "failure_reason": "script_failure",
        }

        mock_context = MagicMock()
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_span.return_value = mock_span

        with patch(
            "new_relic_exporter.processors.job_processor.get_tracer",
            return_value=mock_tracer,
        ):
            with patch(
                "new_relic_exporter.processors.job_processor.do_time",
                return_value=1000000000,
            ):
                with patch(
                    "new_relic_exporter.processors.job_processor.parse_attributes",
                    return_value={"parsed": "attrs"},
                ):
                    with patch(
                        "new_relic_exporter.processors.job_processor.trace.use_span"
                    ):
                        with patch.object(
                            processor,
                            "extract_error_message",
                            return_value="Test error",
                        ):
                            processor.process_job(
                                job_data,
                                mock_context,
                                "https://otlp.nr-data.net",
                                "api-key=test",
                                "test-service",
                            )

                            # Verify failed job processing
                            mock_span.set_status.assert_called_once()
                            processor.extract_error_message.assert_called_once_with(
                                job_data
                            )

    def test_process_job_with_logs_enabled(self, mock_successful_environment):
        """Test job processing with log export enabled."""
        mock_config = MagicMock()
        mock_config.low_data_mode = False
        mock_config.export_logs = True
        mock_project = MagicMock()

        processor = JobProcessor(mock_config, mock_project)

        job_data = {
            "id": 12345,
            "name": "test-job",
            "status": "success",
            "started_at": "2024-01-01T10:00:00Z",
            "finished_at": "2024-01-01T10:05:00Z",
        }

        mock_context = MagicMock()
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_span.return_value = mock_span

        with patch(
            "new_relic_exporter.processors.job_processor.get_tracer",
            return_value=mock_tracer,
        ):
            with patch(
                "new_relic_exporter.processors.job_processor.do_time",
                return_value=1000000000,
            ):
                with patch(
                    "new_relic_exporter.processors.job_processor.parse_attributes",
                    return_value={"parsed": "attrs"},
                ):
                    with patch(
                        "new_relic_exporter.processors.job_processor.trace.use_span"
                    ):
                        with patch.object(
                            processor, "handle_job_logs"
                        ) as mock_handle_logs:
                            processor.process_job(
                                job_data,
                                mock_context,
                                "https://otlp.nr-data.net",
                                "api-key=test",
                                "test-service",
                            )

                            # Verify log handling was called
                            mock_handle_logs.assert_called_once()

    def test_process_job_low_data_mode(self, mock_successful_environment):
        """Test job processing in low data mode."""
        mock_config = MagicMock()
        mock_config.low_data_mode = True
        mock_config.export_logs = False
        mock_project = MagicMock()

        processor = JobProcessor(mock_config, mock_project)

        job_data = {
            "id": 12345,
            "name": "test-job",
            "status": "success",
            "started_at": "2024-01-01T10:00:00Z",
            "finished_at": "2024-01-01T10:05:00Z",
        }

        mock_context = MagicMock()
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_span.return_value = mock_span

        with patch(
            "new_relic_exporter.processors.job_processor.get_tracer",
            return_value=mock_tracer,
        ):
            with patch(
                "new_relic_exporter.processors.job_processor.do_time",
                return_value=1000000000,
            ):
                with patch(
                    "new_relic_exporter.processors.job_processor.parse_attributes"
                ) as mock_parse:
                    with patch(
                        "new_relic_exporter.processors.job_processor.trace.use_span"
                    ):
                        processor.process_job(
                            job_data,
                            mock_context,
                            "https://otlp.nr-data.net",
                            "api-key=test",
                            "test-service",
                        )

                        # Should not set attributes in low data mode
                        mock_span.set_attributes.assert_not_called()

    def test_process_job_exception_handling(self, mock_successful_environment):
        """Test job processing exception handling."""
        mock_config = MagicMock()
        mock_project = MagicMock()

        processor = JobProcessor(mock_config, mock_project)

        job_data = {"id": 12345, "name": "test-job", "status": "success"}

        mock_context = MagicMock()

        with patch(
            "new_relic_exporter.processors.job_processor.get_tracer",
            side_effect=Exception("Tracer error"),
        ):
            # Should handle exception gracefully
            processor.process_job(
                job_data,
                mock_context,
                "https://otlp.nr-data.net",
                "api-key=test",
                "test-service",
            )


class TestBatchJobProcessing:
    """Test suite for batch job processing."""

    def test_process_multiple_jobs(self, mock_successful_environment):
        """Test processing multiple jobs in batch."""
        mock_config = MagicMock()
        mock_project = MagicMock()

        processor = JobProcessor(mock_config, mock_project)

        jobs = [
            {"id": 1, "name": "job1", "status": "success"},
            {"id": 2, "name": "job2", "status": "failed"},
            {"id": 3, "name": "job3", "status": "skipped"},
        ]

        mock_context = MagicMock()

        with patch.object(processor, "process_job") as mock_process_job:
            processor.process(
                jobs,
                mock_context,
                "https://otlp.nr-data.net",
                "api-key=test",
                "test-service",
            )

            # Verify all jobs were processed
            assert mock_process_job.call_count == 3

            # Verify each job was called with correct parameters
            for i, job in enumerate(jobs):
                call_args = mock_process_job.call_args_list[i]
                assert call_args[0][0] == job
                assert call_args[0][1] == mock_context

    def test_process_empty_job_list(self, mock_successful_environment):
        """Test processing empty job list."""
        mock_config = MagicMock()
        mock_project = MagicMock()

        processor = JobProcessor(mock_config, mock_project)

        jobs = []
        mock_context = MagicMock()

        with patch.object(processor, "process_job") as mock_process_job:
            processor.process(
                jobs,
                mock_context,
                "https://otlp.nr-data.net",
                "api-key=test",
                "test-service",
            )

            # Should not process any jobs
            mock_process_job.assert_not_called()

    def test_process_last_job_debug_logging(self, mock_successful_environment):
        """Test debug logging for last job in batch."""
        mock_config = MagicMock()
        mock_project = MagicMock()

        processor = JobProcessor(mock_config, mock_project)

        jobs = [
            {"id": 1, "name": "job1", "status": "success"},
            {"id": 2, "name": "job2", "status": "success"},
        ]

        mock_context = MagicMock()

        with patch.object(processor, "process_job"):
            with patch.object(processor.logger, "debug") as mock_debug:
                processor.process(
                    jobs,
                    mock_context,
                    "https://otlp.nr-data.net",
                    "api-key=test",
                    "test-service",
                )

                # Should log debug message for last job
                mock_debug.assert_called_once()
                call_args = mock_debug.call_args
                assert "Processing last job in batch" in call_args[0][0]


class TestIntegrationScenarios:
    """Test suite for integration scenarios."""

    def test_complete_job_processing_workflow(self, mock_successful_environment):
        """Test complete job processing workflow."""
        mock_config = MagicMock()
        mock_config.low_data_mode = False
        mock_config.export_logs = True
        mock_project = MagicMock()

        # Setup mock job for log retrieval
        mock_job = MagicMock()
        mock_project.jobs.get.return_value = mock_job

        processor = JobProcessor(mock_config, mock_project)

        job_data = {
            "id": 12345,
            "name": "build:docker",
            "status": "success",
            "stage": "build",
            "started_at": "2024-01-01T10:00:00Z",
            "finished_at": "2024-01-01T10:05:00Z",
            "duration": 300.0,
            "runner": {"id": 1, "description": "docker-runner"},
        }

        mock_context = MagicMock()
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_span.return_value = mock_span

        with patch(
            "new_relic_exporter.processors.job_processor.get_tracer",
            return_value=mock_tracer,
        ):
            with patch(
                "new_relic_exporter.processors.job_processor.do_time",
                return_value=1000000000,
            ):
                with patch(
                    "new_relic_exporter.processors.job_processor.parse_attributes",
                    return_value={"parsed": "attrs"},
                ):
                    with patch(
                        "new_relic_exporter.processors.job_processor.trace.use_span"
                    ):
                        with patch(
                            "builtins.open", mock_open(read_data=b"Build successful\n")
                        ):
                            processor.process_job(
                                job_data,
                                mock_context,
                                "https://otlp.nr-data.net",
                                "api-key=test",
                                "test-service",
                            )

                            # Verify complete workflow
                            mock_tracer.start_span.assert_called_once()
                            mock_span.set_attributes.assert_called_once()
                            mock_span.end.assert_called_once()
                            mock_project.jobs.get.assert_called_once()

    def test_failed_job_with_error_extraction(self, mock_successful_environment):
        """Test failed job processing with error message extraction."""
        mock_config = MagicMock()
        mock_config.low_data_mode = False
        mock_config.export_logs = False
        mock_project = MagicMock()

        # Setup mock job for error extraction
        mock_job = MagicMock()
        mock_project.jobs.get.return_value = mock_job

        processor = JobProcessor(mock_config, mock_project)

        job_data = {
            "id": 12345,
            "name": "test:unit",
            "status": "failed",
            "started_at": "2024-01-01T10:00:00Z",
            "finished_at": "2024-01-01T10:05:00Z",
            "failure_reason": "script_failure",
        }

        mock_context = MagicMock()
        mock_tracer = MagicMock()
        mock_span = MagicMock()
        mock_tracer.start_span.return_value = mock_span

        log_content = b"Running tests...\nERROR: Job failed: Test suite failed with 3 errors\nExiting with code 1\n"

        with patch(
            "new_relic_exporter.processors.job_processor.get_tracer",
            return_value=mock_tracer,
        ):
            with patch(
                "new_relic_exporter.processors.job_processor.do_time",
                return_value=1000000000,
            ):
                with patch(
                    "new_relic_exporter.processors.job_processor.parse_attributes",
                    return_value={"parsed": "attrs"},
                ):
                    with patch(
                        "new_relic_exporter.processors.job_processor.trace.use_span"
                    ):
                        with patch("builtins.open", mock_open(read_data=log_content)):
                            with patch(
                                "shared.custom_parsers.do_parse", return_value=True
                            ):
                                processor.process_job(
                                    job_data,
                                    mock_context,
                                    "https://otlp.nr-data.net",
                                    "api-key=test",
                                    "test-service",
                                )

                                # Verify error status was set
                                mock_span.set_status.assert_called_once()
                                status_call = mock_span.set_status.call_args[0][0]
                                assert "Test suite failed with 3 errors" in str(
                                    status_call.description
                                )
