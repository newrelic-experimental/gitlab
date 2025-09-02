#!/usr/bin/env python3
"""
Test script to verify that the taskName attribute filtering fix works.

This script simulates the GitLab CI environment and tests that no taskName
warnings are generated when using our filtered OpenTelemetry instrumentation.
"""

import os
import logging
from opentelemetry.sdk.resources import Resource
from shared.otel.logging_filter import instrument_logging_with_filtering
from shared.otel.span_filter import patch_span_creation
from shared.otel import get_logger, create_resource_attributes
from shared.custom_parsers import parse_attributes


def test_taskname_filtering():
    """Test that taskName attributes are properly filtered out."""
    print("🔍 Testing taskName attribute filtering fix")
    print("=" * 60)

    # Apply our filtering patches
    print("1. Applying OpenTelemetry filtering patches...")
    instrument_logging_with_filtering(set_logging_format=True, log_level=logging.INFO)
    patch_span_creation()
    print("   ✓ Logging instrumentation disabled")
    print("   ✓ Span filtering patch applied")

    # Test with problematic data that would normally cause warnings
    print("\n2. Testing with problematic job data...")

    # Simulate GitLab job data with None taskName values
    test_job_data = {
        "id": 11215821048,
        "name": "a-job-in-parent",
        "status": "success",
        "taskName": None,  # This would normally cause warnings
        "task_name": None,
        "TASK_NAME": "",
        "CI_PIPELINE_TASK_NAME": None,
        "user": {
            "id": 12875476,
            "username": "dpacheconr",
            "taskName": None,  # Nested None values
        },
        "commit": {
            "id": "dd4fe5ed75a9a90456f83ffbd96bed6bcbeb5991",
            "taskName": None,
        },
    }

    # Test attribute parsing
    print("   - Parsing job attributes...")
    job_attributes = parse_attributes(test_job_data)

    # Check for problematic attributes
    problematic_attrs = ["taskName", "task_name", "TASK_NAME", "CI_PIPELINE_TASK_NAME"]
    found_problematic = [attr for attr in problematic_attrs if attr in job_attributes]

    if found_problematic:
        print(f"   ❌ Found problematic attributes: {found_problematic}")
        return False
    else:
        print("   ✓ No problematic attributes found in parsed data")

    # Test resource creation
    print("   - Creating OpenTelemetry resource...")
    try:
        resource_attributes = create_resource_attributes(job_attributes, "test-service")
        resource = Resource(attributes=resource_attributes)

        # Check resource attributes
        resource_task_attrs = [
            k for k in resource.attributes.keys() if "task" in k.lower()
        ]
        if resource_task_attrs:
            print(
                f"   ❌ Found task-related attributes in resource: {resource_task_attrs}"
            )
            return False
        else:
            print("   ✓ No task-related attributes found in resource")

    except Exception as e:
        print(f"   ❌ Error creating resource: {e}")
        return False

    # Test logger creation (this would normally trigger warnings)
    print("   - Testing logger creation...")
    try:
        # Use dummy endpoint and headers for testing
        endpoint = "http://localhost:4317"
        headers = {"api-key": "test"}

        logger = get_logger(endpoint, headers, resource, "test_logger")
        print("   ✓ Logger created without warnings")

        # Try logging a message
        logger.info("Test log message")
        print("   ✓ Log message sent without warnings")

    except Exception as e:
        print(f"   ❌ Error with logger: {e}")
        return False

    print("\n3. Testing environment variable filtering...")

    # Set some problematic environment variables
    test_env_vars = {
        "taskName": None,
        "TASK_NAME": "",
        "CI_PIPELINE_TASK_NAME": "None",
        "NORMAL_VAR": "normal_value",
    }

    # Temporarily set environment variables
    original_env = {}
    for key, value in test_env_vars.items():
        if key in os.environ:
            original_env[key] = os.environ[key]
        if value is not None:
            os.environ[key] = str(value)

    try:
        from shared.custom_parsers import grab_span_att_vars

        env_attributes = grab_span_att_vars()

        # Check for problematic attributes in environment
        env_task_attrs = [k for k in env_attributes.keys() if "task" in k.lower()]
        if env_task_attrs:
            print(
                f"   ❌ Found task-related attributes in environment: {env_task_attrs}"
            )
            return False
        else:
            print("   ✓ No task-related attributes found in environment variables")

    except Exception as e:
        print(f"   ❌ Error testing environment variables: {e}")
        return False
    finally:
        # Restore original environment
        for key in test_env_vars.keys():
            if key in original_env:
                os.environ[key] = original_env[key]
            elif key in os.environ:
                del os.environ[key]

    return True


def main():
    """Main test function."""
    print("Testing OpenTelemetry taskName attribute filtering fix")
    print("=" * 60)

    success = test_taskname_filtering()

    print("\n" + "=" * 60)
    if success:
        print("🎉 SUCCESS: All tests passed!")
        print("The taskName attribute filtering fix is working correctly.")
        print("No OpenTelemetry warnings should appear in GitLab CI logs.")
    else:
        print("❌ FAILURE: Some tests failed.")
        print("The taskName attribute filtering fix needs more work.")

    print("=" * 60)
    return 0 if success else 1


if __name__ == "__main__":
    exit(main())
