"""
Main GitLab exporter class.

Orchestrates the processing of GitLab pipelines and jobs for export to New Relic.
"""

import os
from typing import List
import gitlab
from shared.config.settings import get_config
from shared.logging import get_logger, LogContext
from shared.error_handling import (
    GitLabAPIError,
    ConfigurationError,
    create_gitlab_api_error,
    create_config_error,
)
from ..processors.pipeline_processor import PipelineProcessor
from ..processors.job_processor import JobProcessor
from ..processors.bridge_processor import BridgeProcessor


class GitLabExporter:
    """
    Main exporter class that orchestrates GitLab data processing.

    This class coordinates the pipeline and job processors to export
    GitLab CI/CD data to New Relic using OpenTelemetry.
    """

    def __init__(self):
        """Initialize the GitLab exporter with configuration."""
        self.logger = get_logger("gitlab-exporter", "main")

        try:
            self.config = get_config()
            self.logger.debug("Configuration loaded successfully")
        except Exception as e:
            raise create_config_error(
                "Failed to load configuration",
                "general",
            ) from e

        # Initialize GitLab client
        try:
            if self.config.endpoint and self.config.endpoint != "https://gitlab.com/":
                self.gl = gitlab.Gitlab(
                    self.config.endpoint, private_token=self.config.token
                )
            else:
                self.gl = gitlab.Gitlab(private_token=self.config.token)

            self.logger.debug(
                "GitLab client initialized",
                context=LogContext(
                    service_name="gitlab-exporter",
                    component="main",
                    operation="init",
                ),
                extra={"endpoint": self.config.endpoint or "https://gitlab.com"},
            )
        except Exception as e:
            raise create_gitlab_api_error(
                "Failed to initialize GitLab client",
                status_code=0,
                endpoint=self.config.endpoint or "https://gitlab.com",
                original_exception=e,
            ) from e

    def get_exclude_jobs_list(self) -> List[str]:
        """
        Get list of jobs to exclude from processing.

        Returns:
            List of job/stage names to exclude (lowercase)
        """
        exclude_jobs = []
        if "GLAB_EXCLUDE_JOBS" in os.environ:
            exclude_jobs = [
                j.strip().lower()
                for j in os.getenv("GLAB_EXCLUDE_JOBS", "").split(",")
                if j.strip()
            ]
        return exclude_jobs

    def export_pipeline_data(self) -> None:
        """
        Main method to export pipeline data to New Relic.

        This method:
        1. Gets the current pipeline from environment variables
        2. Processes the pipeline to create the main span
        3. Processes all jobs in the pipeline
        4. Finalizes the pipeline span
        """
        context = LogContext(
            service_name="gitlab-exporter",
            component="main",
            operation="export_pipeline_data",
        )

        with self.logger.operation_timer("export_pipeline_data", context) as timer:
            try:
                # Get pipeline information from environment
                project_id = os.getenv("CI_PROJECT_ID")
                pipeline_id = os.getenv("CI_PARENT_PIPELINE")

                if not project_id or not pipeline_id:
                    error_msg = "Missing required environment variables: CI_PROJECT_ID or CI_PARENT_PIPELINE"
                    self.logger.error(error_msg, context)
                    raise create_config_error(error_msg, "environment_variables")

                # Update context with pipeline information
                context.project_id = project_id
                context.pipeline_id = pipeline_id

                self.logger.debug(
                    "Starting pipeline data export",
                    context,
                    extra={"project_id": project_id, "pipeline_id": pipeline_id},
                )

                # Get GitLab project and pipeline
                try:
                    project = self.gl.projects.get(project_id)
                    pipeline = project.pipelines.get(pipeline_id)

                    self.logger.info(
                        "Processing pipeline",
                        context,
                        extra={
                            "project_name": project.name,
                            "pipeline_name": f"Pipeline #{pipeline.iid}",
                            "pipeline_status": pipeline.status,
                            "pipeline_ref": getattr(pipeline, "ref", "unknown"),
                        },
                    )
                except gitlab.exceptions.GitlabGetError as e:
                    raise create_gitlab_api_error(
                        f"Failed to retrieve project or pipeline: {e}",
                        status_code=getattr(e, "response_code", 404),
                        endpoint=f"projects/{project_id}/pipelines/{pipeline_id}",
                        original_exception=e,
                    ) from e

                # Get exclude list
                exclude_jobs = self.get_exclude_jobs_list()
                if exclude_jobs:
                    self.logger.info(
                        "Jobs exclusion list configured",
                        context,
                        extra={"excluded_jobs": exclude_jobs},
                    )

                # Initialize processors
                self.logger.debug("Initializing processors", context)
                pipeline_processor = PipelineProcessor(self.config, project, pipeline)
                job_processor = JobProcessor(self.config, project)
                bridge_processor = BridgeProcessor(self.config, project)

                # Process pipeline and get context
                self.logger.debug("Processing pipeline", context)
                pipeline_result = pipeline_processor.process(
                    self.config.otel_endpoint, self.config.gitlab_headers, exclude_jobs
                )

                if pipeline_result[0] is None:  # No data to export
                    self.logger.warning("No pipeline data to export", context)
                    return

                pipeline_span, pipeline_context, job_lst, bridge_lst = pipeline_result

                # Log summary of what will be processed
                job_names = (
                    [job.get("name", "unknown") for job in job_lst] if job_lst else []
                )
                bridge_names = (
                    [bridge.get("name", "unknown") for bridge in bridge_lst]
                    if bridge_lst
                    else []
                )

                if job_names or bridge_names:
                    self.logger.info(
                        "Processing pipeline data",
                        context,
                        extra={
                            "jobs": job_names,
                            "bridges": bridge_names,
                            "job_count": len(job_lst),
                            "bridge_count": len(bridge_lst),
                        },
                    )

                # Process jobs
                if job_lst:
                    job_processor.process(
                        job_lst,
                        pipeline_context,
                        self.config.otel_endpoint,
                        self.config.gitlab_headers,
                        pipeline_processor.service_name,
                    )

                # Process bridges
                if bridge_lst:
                    bridge_processor.process(
                        bridge_lst,
                        pipeline_context,
                        self.config.otel_endpoint,
                        self.config.gitlab_headers,
                        pipeline_processor.service_name,
                    )

                # Finalize pipeline
                self.logger.debug("Finalizing pipeline", context)
                pipeline_processor.finalize_pipeline(pipeline_span)

                # Log completion summary
                self.logger.info(
                    "Pipeline data export completed successfully",
                    context,
                    extra={
                        "project_name": project.name,
                        "pipeline_name": f"Pipeline #{pipeline.iid}",
                        "jobs_processed": len(job_lst),
                        "bridges_processed": len(bridge_lst),
                        "total_items": len(job_lst) + len(bridge_lst),
                    },
                )
                timer["success"] = True

            except (ConfigurationError, GitLabAPIError) as e:
                self.logger.error(
                    "Export failed with known error",
                    context,
                    exception=e,
                    extra=e.to_dict(),
                )
                raise
            except Exception as e:
                self.logger.critical(
                    "Export failed with unexpected error", context, exception=e
                )
                raise
            finally:
                # Clean up GitLab session
                if hasattr(self.gl, "session"):
                    self.gl.session.close()
                    self.logger.debug("GitLab session closed", context)


def main():
    """Main entry point for the GitLab exporter."""
    exporter = GitLabExporter()
    exporter.export_pipeline_data()


if __name__ == "__main__":
    main()
