"""
Improved GitLab Metrics Exporter with structured logging and error handling.

This module provides enhanced metrics collection from GitLab projects
with proper error handling, performance monitoring, and structured logging.
"""

import asyncio
import datetime
import time
from typing import List, Dict, Any, Optional
import schedule
from shared.logging import get_logger, LogContext

from shared.error_handling import (
    GitLabAPIError,
    ConfigurationError,
    DataProcessingError,
    create_gitlab_api_error,
    create_config_error,
    create_data_processing_error,
)
from shared.global_variables import (
    gl,
    GLAB_PROJECT_VISIBILITIES,
    GLAB_PROJECT_OWNERSHIP,
    GLAB_STANDALONE,
    GLAB_EXPORT_LAST_MINUTES,
)
from .enhanced_get_resources import EnhancedResourceCollector


class GitLabMetricsExporter:
    """
    Enhanced GitLab metrics exporter with structured logging and error handling.

    Provides comprehensive metrics collection from GitLab projects with
    proper error handling, performance monitoring, and retry logic.
    """

    def __init__(self):
        """Initialize the metrics exporter."""
        self.logger = get_logger("gitlab-metrics-exporter", "main")
        self.start_time = time.time()
        self.resource_collector = EnhancedResourceCollector()

        self.logger.info(
            "GitLab Metrics Exporter initialized",
            context=LogContext(
                service_name="gitlab-metrics-exporter",
                component="main",
                operation="init",
            ),
        )

    def get_projects(self) -> List[Any]:
        """
        Get list of GitLab projects based on configuration.

        Returns:
            List of GitLab project objects

        Raises:
            GitLabAPIError: If project retrieval fails
            ConfigurationError: If configuration is invalid
        """
        context = LogContext(
            service_name="gitlab-metrics-exporter",
            component="main",
            operation="get_projects",
        )

        with self.logger.operation_timer("get_projects", context) as timer:
            try:
                projects = []

                if not GLAB_PROJECT_VISIBILITIES:
                    raise create_config_error(
                        "No project visibilities configured",
                        "GLAB_PROJECT_VISIBILITIES",
                    )

                self.logger.info(
                    "Retrieving projects",
                    context,
                    extra={
                        "visibilities": GLAB_PROJECT_VISIBILITIES,
                        "ownership": GLAB_PROJECT_OWNERSHIP,
                    },
                )

                for visibility in GLAB_PROJECT_VISIBILITIES:
                    try:
                        visibility_projects = gl.projects.list(
                            owned=GLAB_PROJECT_OWNERSHIP,
                            visibility=visibility,
                            get_all=True,
                        )
                        projects.extend(visibility_projects)

                        self.logger.debug(
                            f"Retrieved {len(visibility_projects)} projects for visibility {visibility}",
                            context,
                            extra={
                                "visibility": visibility,
                                "project_count": len(visibility_projects),
                            },
                        )

                    except Exception as e:
                        raise create_gitlab_api_error(
                            f"Failed to retrieve projects for visibility {visibility}",
                            status_code=getattr(e, "response_code", 500),
                            endpoint=f"projects?visibility={visibility}",
                            original_exception=e,
                        ) from e

                # Log project names for visibility
                project_names = [
                    project.name for project in projects[:10]
                ]  # Show first 10
                if len(projects) > 10:
                    project_names.append(f"... and {len(projects) - 10} more")

                self.logger.info(
                    f"Retrieved total of {len(projects)} projects",
                    context,
                    extra={
                        "total_projects": len(projects),
                        "ownership": GLAB_PROJECT_OWNERSHIP,
                        "visibilities": GLAB_PROJECT_VISIBILITIES,
                        "sample_projects": project_names,
                    },
                )

                timer["success"] = True
                return projects

            except (GitLabAPIError, ConfigurationError):
                raise
            except Exception as e:
                raise create_gitlab_api_error(
                    f"Unexpected error retrieving projects: {e}",
                    status_code=500,
                    endpoint="projects",
                    original_exception=e,
                ) from e

    async def process_project(self, project: Any) -> Dict[str, Any]:
        """
        Process a single GitLab project for metrics collection.

        Args:
            project: GitLab project object

        Returns:
            Dictionary with processing results
        """
        project_context = LogContext(
            service_name="gitlab-metrics-exporter",
            component="main",
            operation="process_project",
            project_id=str(project.id),
        )

        result = {
            "project_id": project.id,
            "project_name": project.name,
            "success": False,
            "error": None,
            "metrics_collected": {},
        }

        with self.logger.operation_timer("process_project", project_context) as timer:
            try:
                self.logger.info(
                    f"Processing project: {project.name}",
                    project_context,
                    extra={
                        "project_name": project.name,
                        "project_id": project.id,
                        "namespace": project.namespace.get("full_path", "unknown"),
                    },
                )

                # Use the enhanced resource collector
                metrics = await self.resource_collector.collect_project_data(project)

                result["metrics_collected"] = metrics
                result["success"] = True
                timer["success"] = True

                self.logger.info(
                    f"Successfully processed project: {project.name}",
                    project_context,
                    extra={
                        "metrics_collected": len(metrics),
                        "processing_time": timer.get("duration_seconds", 0),
                    },
                )

            except Exception as e:
                result["error"] = str(e)

                self.logger.error(
                    f"Failed to process project: {project.name}",
                    project_context,
                    exception=e,
                    extra={"project_id": project.id, "error_type": type(e).__name__},
                )

                # Don't re-raise here, we want to continue with other projects

        return result

    async def run_collection(self) -> Dict[str, Any]:
        """
        Run the main metrics collection process.

        Returns:
            Dictionary with collection results and statistics
        """
        context = LogContext(
            service_name="gitlab-metrics-exporter",
            component="main",
            operation="run_collection",
        )

        collection_results = {
            "start_time": datetime.datetime.now().isoformat(),
            "total_projects": 0,
            "successful_projects": 0,
            "failed_projects": 0,
            "errors": [],
            "duration_seconds": 0,
        }

        with self.logger.operation_timer("run_collection", context) as timer:
            try:
                # Get projects
                projects = self.get_projects()
                collection_results["total_projects"] = len(projects)

                if len(projects) == 0:
                    self.logger.warning("No projects found to export", context)
                    return collection_results

                # Log which projects will be processed
                project_names = [project.name for project in projects]

                self.logger.info(
                    f"Starting concurrent processing of {len(projects)} projects",
                    context,
                    extra={
                        "project_count": len(projects),
                        "projects": project_names,
                    },
                )

                # Create tasks for concurrent processing
                tasks = [self.process_project(project) for project in projects]

                # Process with controlled concurrency
                results = await asyncio.gather(*tasks, return_exceptions=True)

                # Analyze results
                for result in results:
                    if isinstance(result, Exception):
                        collection_results["failed_projects"] += 1
                        collection_results["errors"].append(str(result))
                    elif result.get("success", False):
                        collection_results["successful_projects"] += 1
                    else:
                        collection_results["failed_projects"] += 1
                        if result.get("error"):
                            collection_results["errors"].append(result["error"])

                # Collect runners data
                try:
                    await self.resource_collector.collect_runners_data()
                    self.logger.info("Runners data collection completed", context)
                except Exception as e:
                    self.logger.error(
                        "Failed to collect runners data", context, exception=e
                    )
                    collection_results["errors"].append(
                        f"Runners collection failed: {e}"
                    )

                collection_results["duration_seconds"] = time.time() - self.start_time
                timer["success"] = True

                # Log completion summary with project details
                successful_projects = []
                failed_projects = []

                for result in results:
                    if isinstance(result, dict):
                        if result.get("success", False):
                            successful_projects.append(
                                result.get("project_name", "unknown")
                            )
                        else:
                            failed_projects.append(
                                result.get("project_name", "unknown")
                            )

                completion_summary = {
                    **collection_results,
                    "successful_projects_list": successful_projects,
                    "failed_projects_list": failed_projects,
                }

                self.logger.info(
                    "Metrics collection completed", context, extra=completion_summary
                )

            except Exception as e:
                collection_results["errors"].append(str(e))
                self.logger.critical(
                    "Metrics collection failed with critical error",
                    context,
                    exception=e,
                )
                raise

        return collection_results

    def run_standalone_mode(self) -> None:
        """Run the exporter in standalone mode with scheduling."""
        context = LogContext(
            service_name="gitlab-metrics-exporter",
            component="main",
            operation="standalone_mode",
        )

        self.logger.info("Starting standalone mode", context)

        try:
            # Run initial collection
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                results = loop.run_until_complete(self.run_collection())
                self.logger.log_performance_metrics(
                    "initial_collection", results, context
                )
            finally:
                loop.close()
                asyncio.set_event_loop(None)

            # Schedule recurring collections
            schedule.every(int(GLAB_EXPORT_LAST_MINUTES)).minutes.do(
                self._scheduled_collection
            )

            self.logger.info(
                f"Scheduled collections every {GLAB_EXPORT_LAST_MINUTES} minutes",
                context,
                extra={"interval_minutes": GLAB_EXPORT_LAST_MINUTES},
            )

            # Run scheduler
            while True:
                n = schedule.idle_seconds()
                if n is None:
                    break
                elif n > 0:
                    next_run_minutes = round(int(n) / 60)
                    self.logger.info(
                        f"Next collection run in {next_run_minutes} minutes",
                        context,
                        extra={"next_run_minutes": next_run_minutes},
                    )
                    time.sleep(n)
                schedule.run_pending()

        except KeyboardInterrupt:
            self.logger.info("Received shutdown signal", context)
        except Exception as e:
            self.logger.critical("Standalone mode failed", context, exception=e)
            raise
        finally:
            if hasattr(gl, "session"):
                gl.session.close()
                self.logger.info("GitLab session closed", context)

    def _scheduled_collection(self) -> None:
        """Run scheduled collection (wrapper for asyncio)."""
        context = LogContext(
            service_name="gitlab-metrics-exporter",
            component="main",
            operation="scheduled_collection",
        )

        self.logger.info("Starting scheduled collection", context)

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

        try:
            results = loop.run_until_complete(self.run_collection())
            self.logger.log_performance_metrics(
                "scheduled_collection", results, context
            )
        except Exception as e:
            self.logger.error("Scheduled collection failed", context, exception=e)
        finally:
            loop.close()
            asyncio.set_event_loop(None)


def main():
    """Main entry point for the improved metrics exporter."""
    exporter = GitLabMetricsExporter()

    try:
        if GLAB_STANDALONE:
            exporter.run_standalone_mode()
        else:
            # Run once
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)

            try:
                results = loop.run_until_complete(exporter.run_collection())
                context = LogContext(
                    service_name="gitlab-metrics-exporter",
                    component="main",
                    operation="main",
                )
                exporter.logger.info("Collection completed", context, results=results)
            finally:
                loop.close()
                asyncio.set_event_loop(None)

                if hasattr(gl, "session"):
                    gl.session.close()

    except Exception as e:
        context = LogContext(
            service_name="gitlab-metrics-exporter",
            component="main",
            operation="main",
        )
        exporter.logger.critical(
            "Fatal error in metrics exporter", context, exception=e
        )
        raise


if __name__ == "__main__":
    main()
