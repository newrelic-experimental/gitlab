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
from shared.custom_parsers import do_time, parse_attributes, do_parse
from shared.otel import create_resource_attributes, get_tracer, get_logger
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

    def create_job_resource(self, job: Dict[str, Any], service_name: str) -> Resource:
        """
        Create OpenTelemetry resource for a job.

        Args:
            job: Job data dictionary
            service_name: Service name for the job

        Returns:
            Resource instance for the job
        """
        resource_attributes = {
            SERVICE_NAME: service_name,
            "pipeline_id": str(os.getenv("CI_PARENT_PIPELINE")),
            "project_id": str(os.getenv("CI_PROJECT_ID")),
            "job_id": str(job["id"]),
            "instrumentation.name": "gitlab-integration",
            "gitlab.source": "gitlab-exporter",
            "gitlab.resource.type": "span",
        }

        if not self.config.low_data_mode:
            job_attributes = parse_attributes(job)
            resource_attributes.update(
                create_resource_attributes(job_attributes, service_name)
            )

        # Filter out None values and empty strings to prevent OpenTelemetry warnings
        filtered_resource_attributes = {
            key: value
            for key, value in resource_attributes.items()
            if value is not None and value != ""
        }

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
        try:
            current_job = self.project.jobs.get(job["id"], lazy=True)

            # Download job logs
            with open("job.log", "wb") as f:
                current_job.trace(streamed=True, action=f.write)

            # Process logs line by line
            with open("job.log", "rb") as f:
                count = 1
                for string in f:
                    txt = str(
                        self.ansi_escape.sub(" ", str(string.decode("utf-8", "ignore")))
                    )

                    # Skip empty lines
                    if string.decode("utf-8") != "\n" and len(txt) > 2:
                        attrs = resource_attributes.copy()
                        attrs["log"] = txt
                        # Filter out None values and empty strings to prevent OpenTelemetry warnings
                        filtered_attrs = {
                            key: value
                            for key, value in attrs.items()
                            if value is not None and value != ""
                        }

                        # Debug: Print the attributes being passed to Resource
                        print(f"DEBUG: Resource attributes before filtering: {attrs}")
                        print(
                            f"DEBUG: Resource attributes after filtering: {filtered_attrs}"
                        )

                        resource_log = Resource(attributes=filtered_attrs)
                        job_logger = get_logger(
                            endpoint, headers, resource_log, "job_logger"
                        )

                        # Log as error or info based on status
                        if error_status:
                            job_logger.error("")
                        else:
                            job_logger.info("")
                        count += 1

        except Exception as e:
            print(f"Error processing job logs: {e}")

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
                return str(match[1])
            else:
                return str(job["failure_reason"])

        except Exception as e:
            print(f"Error extracting error message: {e}")
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
                    # Filter out None values to prevent OpenTelemetry warnings
                    filtered_attributes = {
                        key: value
                        for key, value in job_attributes.items()
                        if value is not None
                    }
                    child.set_attributes(filtered_attributes)

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
                    print("Not configured to send logs to New Relic, skip...")

                # End the job span
                child.end(end_time=do_time(job["finished_at"]))

        except Exception as e:
            print(f"Error processing job {job.get('id', 'unknown')}: {e}")

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
                print(job)
