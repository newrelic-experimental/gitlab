"""
Job processor for GitLab New Relic Exporter.

Handles job-level processing, tracing, and log export.
"""

import json
import os
import re
from typing import Dict, Any
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.trace import Status, StatusCode
from shared.custom_parsers import do_time, parse_attributes, do_parse, log_attributes_debug
from shared.otel import create_resource_attributes, get_tracer, get_otel_logger
from shared.logging.structured_logger import (
    get_logger as get_structured_logger,
    LogContext,
)
from .base_processor import BaseProcessor


class JobProcessor(BaseProcessor):
    """
    Processor for GitLab jobs.

    Handles job span creation, log processing, and error handling.
    """

    def __init__(self, config, project):
        """
        Initialize the job processor.

        Args:
            config: GitLab configuration instance
            project: GitLab project instance
        """
        super().__init__(config)
        self.project = project
        self.ansi_escape = re.compile(r"\x1B(?:[@-Z\\-_]|\[[0-?]*[ -/]*[@-~])")
        self.logger = get_structured_logger("gitlab-exporter", "job-processor")

    def create_job_resource(self, job: Dict[str, Any], service_name: str) -> Resource:
        """
        Create OpenTelemetry resource for a job.

        Args:
            job: Job data dictionary
            service_name: Service name for the job

        Returns:
            Resource instance for the job
        """
        # Build resource attributes, being careful to skip missing env vars (don't convert None to "None")
        resource_attributes = {
            SERVICE_NAME: service_name,
            "job_id": str(job["id"]),
            "instrumentation.name": "gitlab-integration",
            "gitlab.source": "gitlab-exporter",
            "gitlab.resource.type": "span",
        }

        # Only add environment variables if they're set
        pipeline_id = os.getenv("CI_PARENT_PIPELINE")
        if pipeline_id:
            resource_attributes["pipeline_id"] = str(pipeline_id)

        project_id = os.getenv("CI_PROJECT_ID")
        if project_id:
            resource_attributes["project_id"] = str(project_id)

        if not self.config.low_data_mode:
            job_attributes = parse_attributes(job)
            resource_attributes.update(
                create_resource_attributes(job_attributes, service_name)
            )

        # Filter out None values, empty strings, and "None" strings to prevent OpenTelemetry warnings
        # This is a critical pass to ensure Resource attributes are clean
        filtered_resource_attributes = {
            key: value
            for key, value in resource_attributes.items()
            if value is not None and value != "" and value != "None"
        }

        # Log attributes debug information
        log_attributes_debug(filtered_resource_attributes, "JobProcessor.create_job_resource")

        return Resource(attributes=filtered_resource_attributes)

    def handle_job_logs(
        self,
        job: Dict[str, Any],
        endpoint: str,
        headers: str,
        resource_attributes: Dict[str, Any],
        service_name: str,
        error_status: bool,
    ):
        """
        Handle job log processing and export.

        Args:
            job: Job data dictionary
            endpoint: New Relic OTLP endpoint
            headers: Authentication headers
            resource_attributes: Resource attributes for the job
            service_name: Service name
            error_status: Whether the job has error status
        """
        debug_enabled = os.getenv("DEBUG", "").lower() in ("true", "1", "yes")

        # Debug: Check resource attributes for None values
        if debug_enabled:
            context_init = LogContext(
                service_name="gitlab-exporter",
                component="job-processor",
                operation="handle_job_logs_init",
                job_id=str(job.get("id", "unknown")),
            )
            none_attrs = [k for k, v in resource_attributes.items() if v is None]
            if none_attrs:
                self.logger.debug(
                    f"[INIT] Incoming resource_attributes has {len(none_attrs)} None values",
                    context_init,
                    extra={
                        "none_keys": none_attrs,
                        "total_attrs": len(resource_attributes),
                        "attr_names": list(resource_attributes.keys())[:10]
                    }
                )

        try:
            current_job = self.project.jobs.get(job["id"], lazy=True)

            # Download job logs
            with open("job.log", "wb") as f:
                current_job.trace(streamed=True, action=f.write)

            # Process logs line by line
            with open("job.log", "rb") as f:
                count = 1
                for string in f:
                    raw_string = string.decode("utf-8", "ignore")
                    txt = str(
                        self.ansi_escape.sub(" ", str(raw_string))
                    ).strip()

                    if debug_enabled and count <= 5:  # Log first 5 lines for debugging
                        context = LogContext(
                            service_name="gitlab-exporter",
                            component="job-processor",
                            operation="handle_job_logs_debug",
                            job_id=str(job.get("id", "unknown")),
                        )
                        self.logger.debug(
                            f"[RAW] Line {count}: {raw_string[:100]}",
                            context,
                            extra={"raw_length": len(raw_string), "line_num": count}
                        )

                    # Remove timestamp prefix (format: TIMESTAMP LOG_LEVEL MESSAGE)
                    # Example: "2026-02-09T16:24:37.2141912 010 CI_PROJECT_NAME=..."
                    txt_before = txt
                    if txt:
                        # Look for ISO timestamp pattern followed by whitespace and log level
                        # Pattern: ISO timestamp (with Z or decimals) + log level (digits or alphanumeric) + message
                        # Examples:
                        #   2026-02-09T18:27:22.690736Z 00O  Running with...
                        #   2026-02-09T16:24:37.2141912 010 CI_PROJECT_NAME=...
                        timestamp_pattern = r'^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}[.\d]*Z?\s+[\dA-Za-z]+\s+'
                        match = re.match(timestamp_pattern, txt)

                        if debug_enabled and count <= 5:
                            self.logger.debug(
                                f"[PARSE] Line {count} timestamp pattern match: {match is not None}",
                                context,
                                extra={"pattern_matched": match is not None, "txt_start": txt[:80]}
                            )

                        if match:
                            # Remove the matched timestamp and log level prefix
                            txt = txt[match.end():]
                        else:
                            # Fallback: try simple space-based splitting
                            parts = txt.split(' ', 2)
                            if len(parts) >= 3 and parts[1].isdigit():
                                txt = parts[2]
                            elif len(parts) >= 2 and parts[1].isdigit() and len(parts[1]) <= 3:
                                txt = ' '.join(parts[1:])

                    if debug_enabled and count <= 5 and txt != txt_before:
                        self.logger.debug(
                            f"[EXTRACT] Line {count} timestamp removed",
                            context,
                            extra={"before": txt_before[:80], "after": txt[:80]}
                        )

                    # Skip empty lines
                    if string.decode("utf-8") != "\n" and len(txt) > 2:
                        attrs = resource_attributes.copy()
                        attrs["log"] = txt

                        # Filter out None, empty strings, and invalid OTEL attribute types
                        # CRITICAL: Must completely eliminate None values to prevent OTEL warnings
                        filtered_attrs = {}
                        none_attrs_filtered = []
                        invalid_type_attrs = []

                        for key, value in attrs.items():
                            # CRITICAL: Skip None values - this is the main issue causing warnings
                            if value is None:
                                none_attrs_filtered.append(key)
                                continue
                            # Skip empty strings and string "None"
                            if value == "" or value == "None":
                                continue
                            # Only allow valid OTEL attribute types
                            if isinstance(value, (bool, str, bytes, int, float)):
                                filtered_attrs[key] = value
                            elif isinstance(value, list):
                                # For lists, skip if empty or if contains None values
                                if value and all(v is not None for v in value):
                                    filtered_attrs[key] = value
                                else:
                                    invalid_type_attrs.append(key)
                            elif isinstance(value, dict):
                                # For dicts, skip (can't be serialized reliably)
                                invalid_type_attrs.append(key)
                            else:
                                # Convert other types to string for safety
                                try:
                                    str_value = str(value)
                                    if str_value and str_value != "None":
                                        filtered_attrs[key] = str_value
                                except Exception:
                                    invalid_type_attrs.append(key)

                        if debug_enabled and count <= 5:
                            self.logger.debug(
                                f"[SEND] Line {count} to New Relic - attribute filtering details",
                                context,
                                extra={
                                    "message": txt[:100],
                                    "attr_count": len(filtered_attrs),
                                    "filtered_out_none": len(none_attrs_filtered),
                                    "filtered_out_invalid": len(invalid_type_attrs),
                                    "none_keys": none_attrs_filtered[:5],
                                    "invalid_keys": invalid_type_attrs[:5],
                                    "sent_attrs": list(filtered_attrs.keys())[:10]
                                }
                            )

                        # CRITICAL: Final pass to ensure absolutely NO None values reach OpenTelemetry
                        # This handles edge cases where Resource or logging frameworks add None attributes
                        final_attrs = {k: v for k, v in filtered_attrs.items() if v is not None and v != "None"}

                        # Send log to New Relic with all attributes
                        # The message field contains the JSON-formatted log with structured data
                        # Use final_attrs for both Resource and extra to ensure no None values
                        otel_logger = get_otel_logger(endpoint, headers, Resource(attributes=final_attrs), "job_logger")
                        otel_logger.info(txt, extra=final_attrs)

                        count += 1

        except Exception as e:
            context = LogContext(
                service_name="gitlab-exporter",
                component="job-processor",
                operation="handle_job_logs",
                job_id=str(job.get("id", "unknown")),
            )
            self.logger.error("Error processing job logs", context, exception=e)

    def extract_error_message(self, job: Dict[str, Any]) -> str:
        """
        Extract error message from failed job logs.

        Args:
            job: Job data dictionary

        Returns:
            Error message string
        """
        try:
            current_job = self.project.jobs.get(job["id"], lazy=True)

            with open("job.log", "wb") as f:
                current_job.trace(streamed=True, action=f.write)

            with open("job.log", "rb") as f:
                log_data = ""
                for string in f:
                    log_data += str(
                        self.ansi_escape.sub(
                            "",
                            str(string.decode("utf-8", "ignore")),
                        )
                    )

            # Look for error message
            match = log_data.split("ERROR: Job failed: ")
            if do_parse(match):
                return str(match[1]).strip()
            else:
                return str(job["failure_reason"])

        except Exception as e:
            context = LogContext(
                service_name="gitlab-exporter",
                component="job-processor",
                operation="extract_error_message",
                job_id=str(job.get("id", "unknown")),
            )
            self.logger.error("Error extracting error message", context, exception=e)
            return str(job.get("failure_reason", "Unknown error"))

    def process_job(
        self,
        job: Dict[str, Any],
        pipeline_context: trace.Context,
        endpoint: str,
        headers: str,
        service_name: str,
    ) -> None:
        """
        Process a single job and create its span.

        Args:
            job: Job data dictionary
            pipeline_context: Parent pipeline context
            endpoint: New Relic OTLP endpoint
            headers: Authentication headers
            service_name: Service name
        """
        try:
            # Create job resource and tracer
            job_resource = self.create_job_resource(job, service_name)
            job_tracer = get_tracer(endpoint, headers, job_resource, "job_tracer")

            # Handle skipped jobs
            if job["status"] == "skipped":
                span_name = f"Stage: {job['name']} - job_id: {job['id']} - SKIPPED"
                child = job_tracer.start_span(
                    name=span_name,
                    context=pipeline_context,
                    kind=trace.SpanKind.CONSUMER,
                )
                child.end()
                return

            # Create job span
            span_name = f"Stage: {job['name']} - job_id: {job['id']}"
            child = job_tracer.start_span(
                name=span_name,
                start_time=do_time(job["started_at"]),
                context=pipeline_context,
                kind=trace.SpanKind.CONSUMER,
            )

            with trace.use_span(child, end_on_exit=False):
                error_status = job["status"] == "failed"

                # Handle failed jobs
                if error_status:
                    error_message = self.extract_error_message(job)
                    child.set_status(Status(StatusCode.ERROR, error_message))

                # Set job attributes if not in low data mode
                if not self.config.low_data_mode:
                    job_attributes = parse_attributes(job)
                    # Log attributes debug information
                    log_attributes_debug(job_attributes, "JobProcessor.process_job.set_attributes")
                    child.set_attributes(job_attributes)

                # Handle job logs if enabled
                if self.config.export_logs:
                    self.handle_job_logs(
                        job,
                        endpoint,
                        headers,
                        job_resource.attributes,
                        service_name,
                        error_status,
                    )
                else:
                    context = LogContext(
                        service_name="gitlab-exporter",
                        component="job-processor",
                        operation="process_job",
                        job_id=str(job.get("id", "unknown")),
                    )
                    self.logger.info(
                        "Not configured to send logs to New Relic, skipping log export",
                        context,
                    )

                # End the job span
                child.end(end_time=do_time(job["finished_at"]))

        except Exception as e:
            context = LogContext(
                service_name="gitlab-exporter",
                component="job-processor",
                operation="process_job",
                job_id=str(job.get("id", "unknown")),
            )
            self.logger.error("Error processing job", context, exception=e)

    def process(
        self,
        jobs: list,
        pipeline_context: trace.Context,
        endpoint: str,
        headers: str,
        service_name: str,
    ) -> None:
        """
        Process all jobs in the list.

        Args:
            jobs: List of job dictionaries
            pipeline_context: Parent pipeline context
            endpoint: New Relic OTLP endpoint
            headers: Authentication headers
            service_name: Service name
        """
        for job in jobs:
            self.process_job(job, pipeline_context, endpoint, headers, service_name)

            # Debug output for last job
            if job == jobs[-1]:
                context = LogContext(
                    service_name="gitlab-exporter",
                    component="job-processor",
                    operation="process",
                    job_id=str(job.get("id", "unknown")),
                )
                self.logger.debug(
                    "Processing last job in batch", context, extra={"job_data": job}
                )
