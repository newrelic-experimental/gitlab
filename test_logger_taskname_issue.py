#!/usr/bin/env python3
"""
Test to reproduce the taskName issue specifically in the logger context.
"""

import os
import sys
from unittest.mock import Mock

# Add the project root to the path
sys.path.insert(0, ".")

# Mock environment variables
os.environ["CI_PROJECT_ID"] = "40509251"
os.environ["CI_PARENT_PIPELINE"] = "2017065587"
os.environ["NEW_RELIC_API_KEY"] = "test-key"
os.environ["GLAB_TOKEN"] = "test-token"


def test_logger_taskname_issue():
    """Test to reproduce the taskName issue in logger context."""

    print("Testing logger resource creation with problematic attributes...")

    # Simulate resource attributes that might contain None values
    resource_attributes = {
        "service.name": "test-service",
        "pipeline_id": "2017065587",
        "project_id": "40509251",
        "job_id": "11215821048",
        "log": "test log message",
        "taskName": None,  # This is the problematic attribute
        "CI_TASK_NAME": "",
        "TASK_NAME": None,
    }

    print("Original resource attributes:")
    for key, value in resource_attributes.items():
        print(f"  {key}: {value} (type: {type(value)})")

    # Test the filtering logic from handle_job_logs
    problematic_attrs = [
        "TASK_NAME",
        "CICD_PIPELINE_TASK_NAME",
        "CI_PIPELINE_TASK_NAME",
        "taskName",
        "task_name",
    ]

    filtered_attrs = {
        key: value
        for key, value in resource_attributes.items()
        if value is not None
        and value != ""
        and value != "None"
        and key not in problematic_attrs
    }

    print(f"\nFiltered attributes ({len(filtered_attrs)} total):")
    for key, value in filtered_attrs.items():
        print(f"  {key}: {value} (type: {type(value)})")

    # Test creating a resource with these attributes
    try:
        from opentelemetry.sdk.resources import Resource
        from shared.otel import get_logger

        resource_log = Resource(attributes=filtered_attrs)
        print(
            f"\nResource created successfully with {len(resource_log.attributes)} attributes"
        )

        # Test creating a logger with this resource
        print("Testing logger creation...")

        # Mock endpoint and headers
        endpoint = "https://otlp.nr-data.net:4318"
        headers = "api-key=test-key"

        job_logger = get_logger(endpoint, headers, resource_log, "job_logger")
        print("Logger created successfully")

        # Test logging - this is where the warning should occur if there are issues
        print("Testing logging...")
        job_logger.info("")
        print("Logging completed")

    except Exception as e:
        print(f"Error: {e}")
        import traceback

        traceback.print_exc()


def test_environment_attributes():
    """Test if environment variables are causing the issue."""

    print("\n" + "=" * 50)
    print("Testing environment variable attributes...")

    # Add problematic environment variables
    test_env_vars = {
        "CI_PIPELINE_TASK_NAME": "",
        "CI_TASK_NAME": "",
        "TASK_NAME": "",
        "taskName": "",  # This might be set by some CI systems
    }

    for key, value in test_env_vars.items():
        os.environ[key] = value

    try:
        from shared.custom_parsers import grab_span_att_vars

        span_attributes = grab_span_att_vars()
        print(f"Environment attributes ({len(span_attributes)} total):")
        for key, value in span_attributes.items():
            print(f"  {key}: {value} (type: {type(value)})")
            if value is None or value == "":
                print(f"    WARNING: Found None/empty value for key '{key}'")

        # Test if any of these attributes would cause issues
        problematic_keys = ["taskName", "task_name", "TASK_NAME"]
        for key in problematic_keys:
            if key in span_attributes:
                print(f"FOUND PROBLEMATIC KEY: {key} = {span_attributes[key]}")

    except Exception as e:
        print(f"Error testing environment attributes: {e}")

    finally:
        # Clean up
        for key in test_env_vars.keys():
            if key in os.environ:
                del os.environ[key]


if __name__ == "__main__":
    test_logger_taskname_issue()
    test_environment_attributes()
