"""
Bridge processor for GitLab CI/CD bridge jobs.

Handles bridge-level processing, tracing, and span management for multi-project pipelines.
Bridges are used to trigger downstream pipelines in GitLab CI/CD.
"""

import json
import os
from typing import List, Dict, Any, Optional, Tuple
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.trace import Status, StatusCode
from shared.config.settings import GitLabConfig
from shared.custom_parsers import do_time, parse_attributes
from shared.otel import get_tracer
from shared.logging.structured_logger import get_logger, LogContext
from .base_processor import BaseProcessor


class BridgeProcessor(BaseProcessor):
    """
    Processor for handling GitLab CI/CD bridge jobs.

    Bridge jobs are used to trigger downstream pipelines in multi-project setups.
    This processor creates spans for each bridge and handles their tracing.
    """

    def __init__(self, config: GitLabConfig, project):
        """
        Initialize the bridge processor.

        Args:
            config: GitLab configuration object
            project: GitLab project object
        """
        super().__init__(config)
        self.project = project
        self.logger = get_logger("gitlab-exporter", "bridge-processor")

    def create_bridge_resource(
        self, bridge_data: Dict[str, Any], service_name: str
    ) -> Resource:
        """
        Create OpenTelemetry resource for a bridge.

        Args:
            bridge_data: Bridge data from GitLab API
            service_name: Service name for the resource

        Returns:
            OpenTelemetry Resource object
        """
        base_attributes = {
            "service.name": service_name,
            "bridge_id": str(bridge_data["id"]),
            "pipeline_id": str(os.getenv("CI_PARENT_PIPELINE")),
            "project_id": str(os.getenv("CI_PROJECT_ID")),
            "instrumentation.name": "gitlab-integration",
            "gitlab.source": "gitlab-exporter",
            "gitlab.resource.type": "span",
        }

        # Add bridge-specific attributes if not in low data mode
        if not self.config.low_data_mode:
            bridge_attributes = parse_attributes(bridge_data)
            base_attributes.update(bridge_attributes)

        # Filter out None values and empty strings to prevent OpenTelemetry warnings
        filtered_base_attributes = {
            key: value
            for key, value in base_attributes.items()
            if value is not None and value != ""
        }

        resource_attributes = self.create_resource_attributes(filtered_base_attributes)
        return Resource(attributes=resource_attributes)

    def get_bridge_downstream_info(
        self, bridge_data: Dict[str, Any]
    ) -> Optional[Dict[str, Any]]:
        """
        Extract downstream pipeline information from bridge data.

        Args:
            bridge_data: Bridge data from GitLab API

        Returns:
            Dictionary with downstream pipeline info or None if not available
        """
        downstream_pipeline = bridge_data.get("downstream_pipeline")
        if downstream_pipeline:
            return {
                "downstream_project_id": downstream_pipeline.get("project_id"),
                "downstream_pipeline_id": downstream_pipeline.get("id"),
                "downstream_status": downstream_pipeline.get("status"),
                "downstream_web_url": downstream_pipeline.get("web_url"),
            }
        return None

    def process_bridge(
        self,
        bridge_data: Dict[str, Any],
        pipeline_context: trace.Context,
        otel_endpoint: str,
        headers: str,
        service_name: str,
    ) -> None:
        """
        Process a single bridge job.

        Args:
            bridge_data: Bridge data from GitLab API
            pipeline_context: Parent pipeline context
            otel_endpoint: OpenTelemetry endpoint
            headers: Headers for OTEL exporter
            service_name: Service name for tracing
        """
        try:
            # Create resource for this bridge
            resource = self.create_bridge_resource(bridge_data, service_name)
            bridge_tracer = get_tracer(
                otel_endpoint, headers, resource, "bridge_tracer"
            )

            # Handle skipped bridges
            if bridge_data["status"] == "skipped":
                span_name = f"Bridge: {bridge_data['name']} - bridge_id: {bridge_data['id']} - SKIPPED"
                child = bridge_tracer.start_span(
                    name=span_name,
                    context=pipeline_context,
                    kind=trace.SpanKind.CLIENT,  # Bridges trigger external pipelines
                )
                child.end()
                return

            # Create span for active bridge
            span_name = (
                f"Bridge: {bridge_data['name']} - bridge_id: {bridge_data['id']}"
            )

            # Use start time if available
            start_time = None
            if bridge_data.get("started_at"):
                start_time = do_time(bridge_data["started_at"])

            child = bridge_tracer.start_span(
                name=span_name,
                start_time=start_time,
                context=pipeline_context,
                kind=trace.SpanKind.CLIENT,  # Bridges are client spans (trigger external work)
            )

            with trace.use_span(child, end_on_exit=False):
                # Set bridge attributes if not in low data mode
                if not self.config.low_data_mode:
                    bridge_attributes = parse_attributes(bridge_data)
                    # Filter out None values and empty strings to prevent OpenTelemetry warnings
                    filtered_attributes = {
                        key: value
                        for key, value in bridge_attributes.items()
                        if value is not None and value != ""
                    }
                    child.set_attributes(filtered_attributes)

                # Add downstream pipeline information if available
                downstream_info = self.get_bridge_downstream_info(bridge_data)
                if downstream_info:
                    # Filter downstream info as well
                    filtered_downstream_info = {
                        key: value
                        for key, value in downstream_info.items()
                        if value is not None and value != ""
                    }
                    child.set_attributes(filtered_downstream_info)

                # Handle failed bridges
                if bridge_data["status"] == "failed":
                    failure_reason = bridge_data.get("failure_reason", "Bridge failed")
                    child.set_status(Status(StatusCode.ERROR, failure_reason))

                # Handle successful bridges with downstream pipeline info
                elif bridge_data["status"] == "success" and downstream_info:
                    # Add success status with downstream info
                    downstream_status = downstream_info.get(
                        "downstream_status", "unknown"
                    )
                    if downstream_status == "failed":
                        child.set_status(
                            Status(StatusCode.ERROR, "Downstream pipeline failed")
                        )
                    elif downstream_status in ["success", "passed"]:
                        child.set_status(Status(StatusCode.OK))

                # End the span with finish time if available
                end_time = None
                if bridge_data.get("finished_at"):
                    end_time = do_time(bridge_data["finished_at"])

                child.end(end_time=end_time)

            context = LogContext(
                service_name="gitlab-exporter",
                component="bridge-processor",
                operation="process_bridge",
                bridge_id=str(bridge_data["id"]),
            )
            self.logger.info(
                f"Processed bridge: {bridge_data['name']}",
                context,
                extra={
                    "bridge_id": bridge_data["id"],
                    "bridge_name": bridge_data["name"],
                },
            )

        except Exception as e:
            context = LogContext(
                service_name="gitlab-exporter",
                component="bridge-processor",
                operation="process_bridge",
                bridge_id=str(bridge_data.get("id", "unknown")),
            )
            self.logger.error("Error processing bridge", context, exception=e)
            raise

    def process(
        self,
        bridge_list: List[Dict[str, Any]],
        pipeline_context: trace.Context,
        otel_endpoint: str,
        headers: str,
        service_name: str,
    ) -> None:
        """
        Process all bridges in the list.

        Args:
            bridge_list: List of bridge data from GitLab API
            pipeline_context: Parent pipeline context
            otel_endpoint: OpenTelemetry endpoint
            headers: Headers for OTEL exporter
            service_name: Service name for tracing
        """
        context = LogContext(
            service_name="gitlab-exporter",
            component="bridge-processor",
            operation="process_bridges",
        )

        if not bridge_list:
            self.logger.info("No bridges to process", context)
            return

        self.logger.info(
            "Processing bridges", context, extra={"bridge_count": len(bridge_list)}
        )

        for bridge_data in bridge_list:
            try:
                self.process_bridge(
                    bridge_data,
                    pipeline_context,
                    otel_endpoint,
                    headers,
                    service_name,
                )
            except Exception as e:
                bridge_context = LogContext(
                    service_name="gitlab-exporter",
                    component="bridge-processor",
                    operation="process_bridges",
                    bridge_id=str(bridge_data.get("id", "unknown")),
                )
                self.logger.error(
                    "Failed to process bridge", bridge_context, exception=e
                )
                # Continue processing other bridges even if one fails
                continue

        self.logger.info(
            "Completed processing bridges",
            context,
            extra={"bridge_count": len(bridge_list)},
        )
