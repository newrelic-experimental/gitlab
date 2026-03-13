"""
Improved GitLab Metrics Exporter with structured logging and error handling.

This module provides enhanced metrics collection from GitLab projects
with proper error handling, performance monitoring, and structured logging.
"""

import asyncio
import datetime
import os
import time
import logging
import sys
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
    GLAB_EXPORT_ALL_PROJECTS,
)
from get_resources import EnhancedResourceCollector, global_logger, global_meter, reset_collection_flags, emit_collection_summary
from shared.otel import shutdown_otel_providers


class GitLabMetricsExporter:
    """
    Enhanced GitLab metrics exporter with structured logging and error handling.

    Provides comprehensive metrics collection from GitLab projects with
    proper error handling, performance monitoring, and retry logic.
    """

    def __init__(self):
        """Initialize the metrics exporter."""
        # Use StructuredLogger - OTEL will capture these logs via LoggingHandler
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
                        kwargs = {
                            "owned": GLAB_PROJECT_OWNERSHIP,
                            "visibility": visibility,
                            "get_all": True,
                        }
                        # NOTE: Do NOT apply last_activity_after here.
                        # GitLab does NOT update last_activity_at when pipelines run —
                        # only code pushes, MRs, issues, etc. trigger it.
                        # A project with a recent pipeline but no recent commits would be
                        # silently excluded. Time-windowing is handled inside get_pipelines(),
                        # get_deployments(), get_releases(), and get_jobs() instead.
                        visibility_projects = gl.projects.list(**kwargs)
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

        run_start = time.time()
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
                # Reset per-run flags so scheduled collections each get a fresh log entry
                reset_collection_flags()

                # Get projects
                projects = self.get_projects()
                collection_results["total_projects"] = len(projects)

                if len(projects) == 0:
                    self.logger.warning("No projects found to export", context)
                    return collection_results

                self.logger.info(
                    f"Starting concurrent processing of {len(projects)} projects",
                    context,
                    extra={"project_count": len(projects)},
                )

                # Process projects in batches to allow periodic flushing
                # This prevents OTEL queue overflow when processing 1000+ projects
                batch_size = int(os.getenv("GLAB_EXPORT_BATCH_SIZE", "100"))
                total_batches = (len(projects) + batch_size - 1) // batch_size

                self.logger.info(
                    f"Processing {len(projects)} projects in {total_batches} batches of {batch_size}",
                    context,
                    extra={"batch_size": batch_size, "total_batches": total_batches},
                )

                all_results = []
                cumulative_queue_stats = {
                    "total_items": 0, "deployments": 0, "environments": 0,
                    "releases": 0, "pipelines": 0, "jobs": 0, "errors": 0,
                }
                for batch_num in range(total_batches):
                    start_idx = batch_num * batch_size
                    end_idx = min(start_idx + batch_size, len(projects))
                    batch_projects = projects[start_idx:end_idx]

                    self.logger.info(
                        f"Processing batch {batch_num + 1}/{total_batches} ({len(batch_projects)} projects)",
                        context,
                        extra={
                            "batch_number": batch_num + 1,
                            "batch_size": len(batch_projects),
                            "start_index": start_idx,
                            "end_index": end_idx,
                        },
                    )

                    # Create tasks for this batch
                    batch_tasks = [
                        self.process_project(project) for project in batch_projects
                    ]

                    # Process batch with controlled concurrency
                    batch_results = await asyncio.gather(
                        *batch_tasks, return_exceptions=True
                    )
                    all_results.extend(batch_results)

                    # Drain queue after each batch — safe because get_pipelines now
                    # awaits all job futures before returning, so the queue is fully
                    # populated by the time asyncio.gather completes above.
                    batch_queue_stats = self.resource_collector.process_queue()
                    for key in cumulative_queue_stats:
                        cumulative_queue_stats[key] += batch_queue_stats.get(key, 0)
                    self.logger.debug(
                        f"Batch {batch_num + 1} queue drained: {batch_queue_stats['total_items']} items",
                        context,
                        extra={"batch_number": batch_num + 1, **batch_queue_stats},
                    )

                # Analyze results from all batches
                results = all_results
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

                self.logger.info(
                    f"All {len(projects)} projects processed across {total_batches} batches",
                    context,
                    extra={"total_projects": len(projects), "batches": total_batches},
                )

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

                # Final queue drain — catches runners data added after the batch loop
                try:
                    final_queue_stats = self.resource_collector.process_queue()
                    for key in cumulative_queue_stats:
                        cumulative_queue_stats[key] += final_queue_stats.get(key, 0)
                    self.logger.info(
                        "Queue processing completed",
                        context,
                        extra={"queue_stats": cumulative_queue_stats},
                    )
                    collection_results["queue_stats"] = cumulative_queue_stats

                except Exception as e:
                    self.logger.error("Failed to process queue", context, exception=e)
                    collection_results["errors"].append(f"Queue processing failed: {e}")

                collection_results["duration_seconds"] = time.time() - run_start

                # Emit estate + window summary to New Relic
                try:
                    emit_collection_summary(collection_results, projects)
                    self.logger.info("Collection summary event emitted", context)
                except Exception as e:
                    self.logger.error(
                        "Failed to emit collection summary", context, exception=e
                    )

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
                    "start_time": collection_results["start_time"],
                    "duration_seconds": collection_results["duration_seconds"],
                    "total_projects": collection_results["total_projects"],
                    "successful_projects": collection_results["successful_projects"],
                    "failed_projects": collection_results["failed_projects"],
                    "errors_count": len(collection_results["errors"]),
                    # Cap lists to avoid oversized OTEL payloads on large instances
                    "failed_projects_sample": failed_projects[:10],
                    "queue_stats": collection_results.get("queue_stats", {}),
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
            results = asyncio.run(self.run_collection())
            self.logger.log_performance_metrics(
                "initial_collection", results, context
            )

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

        try:
            results = asyncio.run(self.run_collection())
            self.logger.log_performance_metrics(
                "scheduled_collection", results, context
            )
        except Exception as e:
            self.logger.error("Scheduled collection failed", context, exception=e)


def main():
    """Main entry point for the improved metrics exporter."""
    exporter = GitLabMetricsExporter()

    try:
        if GLAB_STANDALONE:
            exporter.run_standalone_mode()
        else:
            # Run once
            results = asyncio.run(exporter.run_collection())
            context = LogContext(
                service_name="gitlab-metrics-exporter",
                component="main",
                operation="main",
            )
            exporter.logger.info(
                "Collection completed", context, extra={"results": results}
            )

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
    finally:
        # Shutdown OTEL providers to ensure all data is exported
        shutdown_start = time.time()
        print(
            f"[MAIN] Initiating OTEL shutdown at {time.strftime('%H:%M:%S')}...",
            file=sys.stderr,
            flush=True,
        )
        shutdown_success = shutdown_otel_providers(global_logger, meter=global_meter)
        shutdown_duration = time.time() - shutdown_start
        print(
            f"[MAIN] OTEL shutdown {'successful' if shutdown_success else 'completed with warnings'} in {shutdown_duration:.2f}s",
            file=sys.stderr,
            flush=True,
        )


if __name__ == "__main__":
    main()
