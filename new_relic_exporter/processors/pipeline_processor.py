"""
Pipeline processor for GitLab New Relic Exporter.

Handles pipeline-level processing and tracing.
"""

import json
import os
from typing import Dict, Any, Tuple, List
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from opentelemetry.trace import Status, StatusCode
from shared.custom_parsers import do_time, grab_span_att_vars, parse_attributes
from shared.otel import get_tracer
from shared.logging.structured_logger import get_logger, LogContext
from .base_processor import BaseProcessor


class PipelineProcessor(BaseProcessor):
    """
    Processor for GitLab pipelines.

    Handles creation of pipeline spans and manages the overall pipeline context.
    """

    def __init__(self, config, project, pipeline):
        """
        Initialize the pipeline processor.

        Args:
            config: GitLab configuration instance
            project: GitLab project instance
            pipeline: GitLab pipeline instance
        """
        super().__init__(config)
        self.project = project
        self.pipeline = pipeline
        self.pipeline_json = json.loads(pipeline.to_json())
        self.logger = get_logger("gitlab-exporter", "pipeline-processor")

        # Set service name based on project
        self.service_name = (
            str(project.attributes.get("name_with_namespace")).lower().replace(" ", "")
        )

    def create_pipeline_resource(self) -> Resource:
        """
        Create OpenTelemetry resource for the pipeline.

        Returns:
            Resource instance for the pipeline
        """
        attributes = {
            SERVICE_NAME: self.service_name,
            "instrumentation.name": "gitlab-integration",
            "pipeline_id": str(os.getenv("CI_PARENT_PIPELINE")),
            "project_id": str(os.getenv("CI_PROJECT_ID")),
            "gitlab.source": "gitlab-exporter",
            "gitlab.resource.type": "span",
        }

        # Filter out None values and empty strings to prevent OpenTelemetry warnings
        filtered_attributes = {
            key: value
            for key, value in attributes.items()
            if value is not None and value != ""
        }

        return Resource(attributes=filtered_attributes)

    def get_filtered_jobs_and_bridges(
        self, exclude_jobs: List[str]
    ) -> Tuple[List[Dict], List[Dict]]:
        """
        Get filtered lists of jobs and bridges, excluding specified items.

        Args:
            exclude_jobs: List of job/bridge names or stages to exclude

        Returns:
            Tuple of (job_list, bridge_list)
        """
        jobs = self.pipeline.jobs.list(get_all=True)
        bridges = self.pipeline.bridges.list(get_all=True)

        job_lst = []
        bridge_lst = []

        # Process jobs
        for job in jobs:
            job_json = json.loads(job.to_json())
            job_name = str(job_json.get("name", "")).lower()
            job_stage = str(job_json.get("stage", "")).lower()

            if not self.should_exclude_item(job_name, job_stage, exclude_jobs):
                job_lst.append(job_json)

        # Process bridges
        for bridge in bridges:
            bridge_json = json.loads(bridge.to_json())
            bridge_name = str(bridge_json.get("name", "")).lower()
            bridge_stage = str(bridge_json.get("stage", "")).lower()

            if not self.should_exclude_item(bridge_name, bridge_stage, exclude_jobs):
                bridge_lst.append(bridge_json)

        return job_lst, bridge_lst

    def create_pipeline_span(self, tracer, exclude_jobs: List[str]) -> trace.Span:
        """
        Create the main pipeline span.

        Args:
            tracer: OpenTelemetry tracer instance
            exclude_jobs: List of jobs to exclude

        Returns:
            Pipeline span instance
        """
        # Get span attributes based on data mode
        if self.config.low_data_mode:
            atts = {}
        else:
            atts = grab_span_att_vars()

        # Create pipeline span
        span_name = f"{self.service_name} - pipeline: {os.getenv('CI_PARENT_PIPELINE')}"
        pipeline_span = tracer.start_span(
            name=span_name,
            attributes=atts,
            start_time=do_time(str(self.pipeline_json["started_at"])),
            kind=trace.SpanKind.SERVER,
        )

        # Set additional attributes if not in low data mode
        if not self.config.low_data_mode:
            pipeline_attributes = parse_attributes(self.pipeline_json)
            pipeline_attributes.update(atts)
            # Filter out None values and empty strings to prevent OpenTelemetry warnings
            filtered_attributes = {
                key: value
                for key, value in pipeline_attributes.items()
                if value is not None and value != ""
            }
            pipeline_span.set_attributes(filtered_attributes)

        # Set error status if pipeline failed
        if self.pipeline_json["status"] == "failed":
            pipeline_span.set_status(
                Status(StatusCode.ERROR, "Pipeline failed, check jobs for more details")
            )

        return pipeline_span

    def process(
        self, endpoint: str, headers: str, exclude_jobs: List[str]
    ) -> Tuple[trace.Span, trace.Context, List[Dict], List[Dict]]:
        """
        Process the pipeline and return span context and filtered jobs/bridges.

        Args:
            endpoint: New Relic OTLP endpoint
            headers: Authentication headers
            exclude_jobs: List of jobs to exclude

        Returns:
            Tuple of (pipeline_span, pipeline_context, job_list, bridge_list)
        """
        # Create pipeline resource and tracer
        pipeline_resource = self.create_pipeline_resource()
        tracer = get_tracer(endpoint, headers, pipeline_resource, "tracer")

        # Get filtered jobs and bridges
        job_lst, bridge_lst = self.get_filtered_jobs_and_bridges(exclude_jobs)

        # Check if we have any data to export
        if len(job_lst) == 0 and len(bridge_lst) == 0:
            context = LogContext(
                service_name="gitlab-exporter",
                component="pipeline-processor",
                operation="process",
                pipeline_id=str(self.pipeline_json["id"]),
            )
            self.logger.info(
                "No data to export, all jobs and bridges excluded or are exporters",
                context,
            )
            return None, None, [], []

        # Create pipeline span
        pipeline_span = self.create_pipeline_span(tracer, exclude_jobs)
        pipeline_context = trace.set_span_in_context(pipeline_span)

        return pipeline_span, pipeline_context, job_lst, bridge_lst

    def finalize_pipeline(self, pipeline_span: trace.Span):
        """
        Finalize the pipeline span with end time.

        Args:
            pipeline_span: The pipeline span to finalize
        """
        if pipeline_span:
            pipeline_span.end(end_time=do_time(str(self.pipeline_json["finished_at"])))
            context = LogContext(
                service_name="gitlab-exporter",
                component="pipeline-processor",
                operation="finalize_pipeline",
                pipeline_id=str(self.pipeline_json["id"]),
            )
            self.logger.debug(
                "All data sent to New Relic for pipeline",
                context,
                extra={"pipeline_id": self.pipeline_json["id"]},
            )
