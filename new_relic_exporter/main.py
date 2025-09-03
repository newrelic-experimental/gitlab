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
    try:
        print("Starting GitLab New Relic Exporter")

        # Create and run the exporter
        exporter = GitLabExporter()
        exporter.export_pipeline_data()

        print("GitLab New Relic Exporter completed successfully")

    except Exception as e:
        print(f"Fatal error in GitLab exporter: {e}")
        raise


if __name__ == "__main__":
    main()
