#!/usr/bin/env python3
"""
Test script to reproduce the OpenTelemetry taskName warnings locally.

This script simulates the GitLab CI environment that causes the warnings.
"""

import os
import logging
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk.resources import Resource
from shared.otel import get_logger


def test_taskname_warnings():
    """Test that reproduces the taskName warnings locally."""

    print("=== Testing OpenTelemetry taskName warnings ===")

    # Set up environment variables that GitLab CI would have
    # These are the problematic ones that cause None values
    test_env_vars = {
        "CI": "true",
        "GITLAB_CI": "true",
        "CI_JOB_ID": "12345",
        "CI_JOB_NAME": "test-job",
        "CI_PIPELINE_ID": "67890",
        "CI_PROJECT_ID": "11111",
        # These are the problematic ones - they often have None values in GitLab CI
        "TASK_NAME": None,
        "CICD_PIPELINE_TASK_NAME": None,
        "CI_PIPELINE_TASK_NAME": None,
    }

    # Set environment variables
    original_env = {}
    for key, value in test_env_vars.items():
        original_env[key] = os.environ.get(key)
        if value is None:
            # Simulate None by setting empty string or removing
            if key in os.environ:
                del os.environ[key]
        else:
            os.environ[key] = str(value)

    try:
        print("1. Testing with standard LoggingInstrumentor...")

        # This should trigger the warnings
        LoggingInstrumentor().instrument(
            set_logging_format=True, log_level=logging.INFO
        )

        # Create a resource and logger (similar to job_processor.py)
        resource_attributes = {
            "service.name": "test-service",
            "job_id": "12345",
            "log": "Test log message",
        }

        resource = Resource(attributes=resource_attributes)

        # This should trigger the taskName warnings
        logger = get_logger(
            endpoint="http://localhost:4317",  # Dummy endpoint
            headers="api-key dummy",
            resource=resource,
            name="test_logger",
        )

        print("2. Attempting to log (this should trigger warnings)...")
        logger.info("Test message that should trigger taskName warnings")

        print(
            "3. If you see 'Invalid type NoneType for attribute taskName value' warnings above, the issue is reproduced!"
        )

    except Exception as e:
        print(f"Error during test: {e}")

    finally:
        # Restore original environment
        for key, original_value in original_env.items():
            if original_value is None:
                if key in os.environ:
                    del os.environ[key]
            else:
                os.environ[key] = original_value

        # Uninstrument to clean up
        try:
            LoggingInstrumentor().uninstrument()
        except:
            pass


def test_filtered_approach():
    """Test our filtered approach to see if it prevents warnings."""

    print("\n=== Testing Filtered Approach ===")

    # Set up the same problematic environment
    test_env_vars = {
        "CI": "true",
        "GITLAB_CI": "true",
        "CI_JOB_ID": "12345",
        "CI_JOB_NAME": "test-job",
        "TASK_NAME": None,
        "CICD_PIPELINE_TASK_NAME": None,
        "CI_PIPELINE_TASK_NAME": None,
    }

    original_env = {}
    for key, value in test_env_vars.items():
        original_env[key] = os.environ.get(key)
        if value is None:
            if key in os.environ:
                del os.environ[key]
        else:
            os.environ[key] = str(value)

    try:
        print("1. Testing with filtered logging instrumentation...")

        from shared.otel.logging_filter import instrument_logging_with_filtering

        instrument_logging_with_filtering(
            set_logging_format=True, log_level=logging.INFO
        )

        # Create filtered resource attributes
        resource_attributes = {
            "service.name": "test-service",
            "job_id": "12345",
            "log": "Test log message",
        }

        # Apply the same filtering as in job_processor.py
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

        resource = Resource(attributes=filtered_attrs)

        logger = get_logger(
            endpoint="http://localhost:4317",
            headers="api-key dummy",
            resource=resource,
            name="filtered_test_logger",
        )

        print("2. Attempting to log with filtered approach...")
        logger.info("Test message with filtered approach")

        print("3. If no taskName warnings appeared above, the fix is working!")

    except Exception as e:
        print(f"Error during filtered test: {e}")

    finally:
        # Restore original environment
        for key, original_value in original_env.items():
            if original_value is None:
                if key in os.environ:
                    del os.environ[key]
            else:
                os.environ[key] = original_value


if __name__ == "__main__":
    print("Local reproduction test for OpenTelemetry taskName warnings")
    print("=" * 60)

    test_taskname_warnings()
    test_filtered_approach()

    print("\n" + "=" * 60)
    print("Test completed. Check the output above for warnings.")
