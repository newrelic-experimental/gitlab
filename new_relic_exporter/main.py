"""
Main entry point for GitLab New Relic Exporter.

This implementation uses the processor architecture with centralized configuration
and focused, testable classes for pipeline, job, and bridge processing.
"""

import logging
import os
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from new_relic_exporter.exporters.gitlab_exporter import GitLabExporter

# Set environment variables to prevent OpenTelemetry from adding None values
# for CICD attributes that it tries to auto-detect
if not os.getenv("TASK_NAME"):
    os.environ["TASK_NAME"] = "gitlab-exporter"

# Also set other potential CICD environment variables that OpenTelemetry might try to detect
if not os.getenv("CICD_PIPELINE_TASK_NAME"):
    os.environ["CICD_PIPELINE_TASK_NAME"] = "gitlab-exporter"

# Configure logging instrumentation
LoggingInstrumentor().instrument(set_logging_format=True, log_level=logging.INFO)


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
