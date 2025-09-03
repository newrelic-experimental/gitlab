"""
Downstream processor for GitLab CI/CD bridge jobs.

Handles processing of downstream pipelines triggered by bridges.
"""

import json
from typing import List, Dict, Any, Optional, Set
from opentelemetry import trace
from shared.config.settings import GitLabConfig
from shared.logging.structured_logger import get_logger, LogContext
from .base_processor import BaseProcessor
from .job_processor import JobProcessor
from .bridge_processor import BridgeProcessor


class DownstreamProcessor(BaseProcessor):
    """
    Processor for handling downstream pipelines triggered by bridges.

    This processor recursively processes downstream pipelines and their jobs,
    ensuring that all jobs triggered by bridges are properly traced.
    """

    def __init__(self, config: GitLabConfig, gitlab_client):
        """
        Initialize the downstream processor.

        Args:
            config: GitLab configuration object
            gitlab_client: GitLab client instance
        """
        super().__init__(config)
        self.gitlab_client = gitlab_client
        self.logger = get_logger("gitlab-exporter", "downstream-processor")
        self.processed_pipelines: Set[str] = (
            set()
        )  # Track processed pipelines to avoid cycles

    def get_downstream_pipeline_data(
        self, downstream_project_id: int, downstream_pipeline_id: int
    ) -> Optional[Dict[str, Any]]:
        """
        Fetch downstream pipeline data from GitLab API.

        Args:
            downstream_project_id: ID of the downstream project
            downstream_pipeline_id: ID of the downstream pipeline

        Returns:
            Dictionary with downstream pipeline data or None if not accessible
        """
        try:
            downstream_project = self.gitlab_client.projects.get(downstream_project_id)
            downstream_pipeline = downstream_project.pipelines.get(
                downstream_pipeline_id
            )

            return {
                "project": downstream_project,
                "pipeline": downstream_pipeline,
                "pipeline_json": json.loads(downstream_pipeline.to_json()),
            }
        except Exception as e:
            context = LogContext(
                service_name="gitlab-exporter",
                component="downstream-processor",
                operation="get_downstream_pipeline_data",
                project_id=str(downstream_project_id),
                pipeline_id=str(downstream_pipeline_id),
            )
            self.logger.warning(
                f"Could not access downstream pipeline: {e}",
                context,
                extra={
                    "downstream_project_id": downstream_project_id,
                    "downstream_pipeline_id": downstream_pipeline_id,
                    "error": str(e),
                },
            )
            return None

    def get_downstream_jobs_and_bridges(
        self, downstream_project, downstream_pipeline, exclude_jobs: List[str]
    ) -> tuple[List[Dict[str, Any]], List[Dict[str, Any]]]:
        """
        Get jobs and bridges from downstream pipeline.

        Args:
            downstream_project: GitLab project object
            downstream_pipeline: GitLab pipeline object
            exclude_jobs: List of job/bridge names to exclude

        Returns:
            Tuple of (job_list, bridge_list)
        """
        try:
            jobs = downstream_pipeline.jobs.list(get_all=True)
            bridges = downstream_pipeline.bridges.list(get_all=True)

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

                if not self.should_exclude_item(
                    bridge_name, bridge_stage, exclude_jobs
                ):
                    bridge_lst.append(bridge_json)

            return job_lst, bridge_lst

        except Exception as e:
            context = LogContext(
                service_name="gitlab-exporter",
                component="downstream-processor",
                operation="get_downstream_jobs_and_bridges",
                project_id=str(downstream_project.id),
                pipeline_id=str(downstream_pipeline.id),
            )
            self.logger.error(
                f"Error fetching downstream jobs and bridges: {e}", context, exception=e
            )
            return [], []

    def process_downstream_pipeline(
        self,
        downstream_info: Dict[str, Any],
        parent_context: trace.Context,
        otel_endpoint: str,
        headers: str,
        service_name: str,
        exclude_jobs: List[str],
        max_depth: int = 3,
        current_depth: int = 0,
    ) -> None:
        """
        Process a downstream pipeline and its jobs/bridges.

        Args:
            downstream_info: Dictionary with downstream pipeline information
            parent_context: Parent span context
            otel_endpoint: OpenTelemetry endpoint
            headers: Headers for OTEL exporter
            service_name: Service name for tracing
            exclude_jobs: List of jobs to exclude
            max_depth: Maximum recursion depth for nested bridges
            current_depth: Current recursion depth
        """
        if current_depth >= max_depth:
            context = LogContext(
                service_name="gitlab-exporter",
                component="downstream-processor",
                operation="process_downstream_pipeline",
            )
            self.logger.warning(
                f"Maximum recursion depth ({max_depth}) reached, skipping further downstream processing",
                context,
                extra={"current_depth": current_depth},
            )
            return

        downstream_project_id = downstream_info.get("downstream_project_id")
        downstream_pipeline_id = downstream_info.get("downstream_pipeline_id")

        if not downstream_project_id or not downstream_pipeline_id:
            return

        # Create unique identifier for this pipeline to avoid cycles
        pipeline_key = f"{downstream_project_id}:{downstream_pipeline_id}"
        if pipeline_key in self.processed_pipelines:
            context = LogContext(
                service_name="gitlab-exporter",
                component="downstream-processor",
                operation="process_downstream_pipeline",
                project_id=str(downstream_project_id),
                pipeline_id=str(downstream_pipeline_id),
            )
            self.logger.debug(
                "Pipeline already processed, skipping to avoid cycles", context
            )
            return

        self.processed_pipelines.add(pipeline_key)

        context = LogContext(
            service_name="gitlab-exporter",
            component="downstream-processor",
            operation="process_downstream_pipeline",
            project_id=str(downstream_project_id),
            pipeline_id=str(downstream_pipeline_id),
        )

        self.logger.info(
            "Processing downstream pipeline",
            context,
            extra={
                "downstream_project_id": downstream_project_id,
                "downstream_pipeline_id": downstream_pipeline_id,
                "depth": current_depth,
            },
        )

        # Fetch downstream pipeline data
        downstream_data = self.get_downstream_pipeline_data(
            downstream_project_id, downstream_pipeline_id
        )

        if not downstream_data:
            self.logger.warning("Could not fetch downstream pipeline data", context)
            return

        downstream_project = downstream_data["project"]
        downstream_pipeline = downstream_data["pipeline"]

        # Get jobs and bridges from downstream pipeline
        downstream_jobs, downstream_bridges = self.get_downstream_jobs_and_bridges(
            downstream_project, downstream_pipeline, exclude_jobs
        )

        if not downstream_jobs and not downstream_bridges:
            self.logger.debug(
                "No jobs or bridges found in downstream pipeline", context
            )
            return

        self.logger.info(
            "Found downstream pipeline content",
            context,
            extra={
                "job_count": len(downstream_jobs),
                "bridge_count": len(downstream_bridges),
                "job_names": [job.get("name") for job in downstream_jobs],
                "bridge_names": [bridge.get("name") for bridge in downstream_bridges],
            },
        )

        # Process downstream jobs
        if downstream_jobs:
            job_processor = JobProcessor(self.config, downstream_project)
            job_processor.process(
                downstream_jobs,
                parent_context,
                otel_endpoint,
                headers,
                service_name,
            )

        # Process downstream bridges and their downstream pipelines recursively
        if downstream_bridges:
            bridge_processor = BridgeProcessor(self.config, downstream_project)
            bridge_processor.process(
                downstream_bridges,
                parent_context,
                otel_endpoint,
                headers,
                service_name,
            )

            # Recursively process any further downstream pipelines
            for bridge_data in downstream_bridges:
                bridge_downstream_info = bridge_processor.get_bridge_downstream_info(
                    bridge_data
                )
                if bridge_downstream_info:
                    self.process_downstream_pipeline(
                        bridge_downstream_info,
                        parent_context,
                        otel_endpoint,
                        headers,
                        service_name,
                        exclude_jobs,
                        max_depth,
                        current_depth + 1,
                    )

        self.logger.info(
            "Completed processing downstream pipeline",
            context,
            extra={
                "jobs_processed": len(downstream_jobs),
                "bridges_processed": len(downstream_bridges),
            },
        )

    def process_bridges_with_downstream(
        self,
        bridge_list: List[Dict[str, Any]],
        parent_context: trace.Context,
        otel_endpoint: str,
        headers: str,
        service_name: str,
        exclude_jobs: List[str],
        max_depth: int = 3,
    ) -> None:
        """
        Process bridges and their downstream pipelines.

        Args:
            bridge_list: List of bridge data from GitLab API
            parent_context: Parent pipeline context
            otel_endpoint: OpenTelemetry endpoint
            headers: Headers for OTEL exporter
            service_name: Service name for tracing
            exclude_jobs: List of jobs to exclude
            max_depth: Maximum recursion depth for nested bridges
        """
        context = LogContext(
            service_name="gitlab-exporter",
            component="downstream-processor",
            operation="process_bridges_with_downstream",
        )

        if not bridge_list:
            self.logger.debug("No bridges to process", context)
            return

        self.logger.info(
            "Processing bridges with downstream pipelines",
            context,
            extra={"bridge_count": len(bridge_list)},
        )

        # First process the bridges themselves
        bridge_processor = BridgeProcessor(
            self.config, None
        )  # Project will be set per bridge
        bridge_processor.process(
            bridge_list,
            parent_context,
            otel_endpoint,
            headers,
            service_name,
        )

        # Then process their downstream pipelines
        for bridge_data in bridge_list:
            downstream_info = bridge_processor.get_bridge_downstream_info(bridge_data)
            if downstream_info:
                self.process_downstream_pipeline(
                    downstream_info,
                    parent_context,
                    otel_endpoint,
                    headers,
                    service_name,
                    exclude_jobs,
                    max_depth,
                )

        self.logger.info(
            "Completed processing bridges with downstream pipelines",
            context,
            extra={"bridge_count": len(bridge_list)},
        )

    def process(self, *args, **kwargs):
        """
        Implementation of abstract process method from BaseProcessor.

        This method delegates to process_bridges_with_downstream for compatibility
        with the BaseProcessor interface.
        """
        # This is a compatibility method - the main functionality is in
        # process_bridges_with_downstream and process_downstream_pipeline
        if len(args) >= 6:
            return self.process_bridges_with_downstream(*args, **kwargs)
        else:
            raise ValueError("Invalid arguments for DownstreamProcessor.process()")
