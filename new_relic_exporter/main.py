"""
Main entry point for GitLab New Relic Exporter.

This implementation uses the processor architecture with centralized configuration
and focused, testable classes for pipeline, job, and bridge processing.
"""

# Suppress pkg_resources deprecation warnings from OpenTelemetry dependencies
# This must be done before importing OpenTelemetry modules
import warnings

warnings.filterwarnings(
    "ignore", message="pkg_resources is deprecated", category=UserWarning
)

import logging
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from new_relic_exporter.exporters.gitlab_exporter import GitLabExporter
from shared.logging.structured_logger import get_logger, LogContext

# Initialize OpenTelemetry logging instrumentation only if not already instrumented
# Note: The taskName warnings come from automatic environment variable injection
# We'll handle this by filtering in the job processor instead
instrumentor = LoggingInstrumentor()
if not instrumentor.is_instrumented_by_opentelemetry:
    instrumentor.instrument(set_logging_format=True, log_level=logging.INFO)


def main():
    """
    Main entry point for the GitLab exporter.

    This function:
    1. Initializes the GitLab exporter with configuration
    2. Exports pipeline data to New Relic
    3. Handles any errors gracefully
    """
    # Initialize logger
    logger = get_logger("gitlab-exporter", "main")
    context = LogContext(
        service_name="gitlab-exporter",
        component="main",
        operation="export_pipeline_data",
    )

    try:
        import time
        import sys

        start_time = time.time()

        logger.info("Starting GitLab New Relic Exporter", context)
        print(
            f"[MAIN] Process started at {time.strftime('%H:%M:%S')}",
            file=sys.stderr,
            flush=True,
        )

        # Create and run the exporter
        export_start = time.time()
        exporter = GitLabExporter()
        exporter.export_pipeline_data()
        export_duration = time.time() - export_start

        logger.info("GitLab New Relic Exporter completed successfully", context)
        print(
            f"[MAIN] Export completed in {export_duration:.2f}s",
            file=sys.stderr,
            flush=True,
        )
        print(
            f"[MAIN] Total runtime before shutdown: {time.time() - start_time:.2f}s",
            file=sys.stderr,
            flush=True,
        )

        # Shutdown OTEL providers to ensure all data is exported
        from shared.otel import shutdown_otel_providers

        logger.info(
            "Shutting down OTEL providers - waiting for all queued data to be exported",
            LogContext(
                service_name="gitlab-exporter", component="main", operation="shutdown"
            ),
        )
        print(
            f"[MAIN] Initiating OTEL shutdown at {time.strftime('%H:%M:%S')}",
            file=sys.stderr,
            flush=True,
        )
        shutdown_success = shutdown_otel_providers(logger)
        shutdown_total = time.time() - start_time
        print(
            f"[MAIN] OTEL shutdown {'successful' if shutdown_success else 'completed with warnings'}",
            file=sys.stderr,
            flush=True,
        )
        print(
            f"[MAIN] Total process runtime: {shutdown_total:.2f}s",
            file=sys.stderr,
            flush=True,
        )

    except Exception as e:
        logger.critical("Fatal error in GitLab exporter", context, exception=e)
        raise


if __name__ == "__main__":
    main()
