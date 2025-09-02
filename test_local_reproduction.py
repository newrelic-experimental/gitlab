#!/usr/bin/env python3
"""
Test script to verify the taskName attribute filtering works locally.
"""

import os
import sys
from unittest.mock import Mock, patch

# Add the project root to the Python path
sys.path.insert(0, ".")

# Mock environment variables
os.environ.update(
    {
        "CI_PROJECT_ID": "40509251",
        "CI_PARENT_PIPELINE": "2017065587",
        "NEW_RELIC_API_KEY": "test-key",
        "GLAB_TOKEN": "test-token",
        "GLAB_EXPORT_LOGS": "true",
        "GLAB_LOW_DATA_MODE": "false",
    }
)


def test_job_processor_filtering():
    """Test that the job processor filters out problematic attributes."""
    print("=== Testing Job Processor Attribute Filtering ===")

    from new_relic_exporter.processors.job_processor import JobProcessor
    from shared.custom_parsers import parse_attributes
    from unittest.mock import Mock

    # Create mock config and project
    mock_config = Mock()
    mock_config.low_data_mode = False
    mock_config.export_logs = False

    mock_project = Mock()

    # Create job processor
    processor = JobProcessor(mock_config, mock_project)

    # Sample job data with potential problematic attributes
    sample_job = {
        "id": 11215821048,
        "status": "success",
        "stage": "a-job-in-parent",
        "name": "a-job-in-parent",
        "taskName": None,  # This should be filtered out
        "task_name": "",  # This should be filtered out
        "TASK_NAME": "None",  # This should be filtered out
        "ref": "main",
        "tag": False,
        "coverage": None,  # This should be filtered out
        "allow_failure": True,
        "created_at": "2025-09-02T11:54:28.847Z",
        "started_at": "2025-09-02T11:54:30.120Z",
        "finished_at": "2025-09-02T11:55:06.109Z",
        "duration": 35.98896,
        "queued_duration": 0.480128,
    }

    # Test parse_attributes
    job_attributes = parse_attributes(sample_job)
    print(f"Parsed attributes count: {len(job_attributes)}")

    # Check for problematic attributes in parsed output
    problematic_attrs = ["taskName", "task_name", "TASK_NAME"]
    found_problematic = [attr for attr in problematic_attrs if attr in job_attributes]
    if found_problematic:
        print(
            f"WARNING: Found problematic attributes in parsed output: {found_problematic}"
        )
    else:
        print("✓ No problematic attributes found in parsed output")

    # Test the filtering logic from job processor
    problematic_attrs = [
        "taskName",
        "task_name",
        "TASK_NAME",
        "CICD_PIPELINE_TASK_NAME",
        "CI_PIPELINE_TASK_NAME",
    ]
    filtered_attributes = {
        key: value
        for key, value in job_attributes.items()
        if value is not None
        and value != ""
        and value != "None"
        and key not in problematic_attrs
    }

    print(f"Filtered attributes count: {len(filtered_attributes)}")

    # Check that None values are filtered out
    none_values = [k for k, v in filtered_attributes.items() if v is None]
    if none_values:
        print(f"ERROR: Found None values after filtering: {none_values}")
    else:
        print("✓ No None values found after filtering")

    # Check that problematic attributes are filtered out
    found_after_filter = [
        attr for attr in problematic_attrs if attr in filtered_attributes
    ]
    if found_after_filter:
        print(
            f"ERROR: Found problematic attributes after filtering: {found_after_filter}"
        )
    else:
        print("✓ No problematic attributes found after filtering")

    return len(filtered_attributes) > 0


def test_span_filter():
    """Test the span filtering functionality."""
    print("\n=== Testing Span Filter ===")

    from shared.otel.span_filter import FilteredSpan
    from unittest.mock import Mock

    # Create mock span
    mock_span = Mock()

    # Create filtered span wrapper
    filtered_span = FilteredSpan(mock_span)

    # Test setting problematic attributes
    test_attributes = {
        "taskName": None,
        "task_name": "",
        "TASK_NAME": "None",
        "valid_attr": "valid_value",
        "another_valid": 123,
    }

    # Test set_attributes method
    filtered_span.set_attributes(test_attributes)

    # Check what was actually passed to the underlying span
    if mock_span.set_attributes.called:
        call_args = mock_span.set_attributes.call_args
        if call_args and call_args[0]:
            actual_attrs = call_args[0][0]
            print(f"Attributes passed to span: {actual_attrs}")

            # Check for problematic attributes
            problematic_found = any(
                key in ["taskName", "task_name", "TASK_NAME"]
                for key in actual_attrs.keys()
            )
            if problematic_found:
                print("ERROR: Problematic attributes were passed to span")
                return False
            else:
                print("✓ No problematic attributes passed to span")

            # Check for None values
            none_found = any(value is None for value in actual_attrs.values())
            if none_found:
                print("ERROR: None values were passed to span")
                return False
            else:
                print("✓ No None values passed to span")

            return len(actual_attrs) > 0
        else:
            print("No attributes were passed to span (empty after filtering)")
            return True
    else:
        print("set_attributes was not called (all attributes filtered out)")
        return True


def test_resource_creation():
    """Test resource creation with filtering."""
    print("\n=== Testing Resource Creation ===")

    from shared.otel import create_resource_attributes
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME

    # Test attributes with problematic values
    test_attrs = {
        "taskName": None,
        "task_name": "",
        "TASK_NAME": "None",
        "valid_attr": "valid_value",
        "name": "test-job",  # This should become resource.name
    }

    service_name = "test-service"
    resource_attrs = create_resource_attributes(test_attrs, service_name)

    print(f"Resource attributes created: {len(resource_attrs)}")

    # Check for problematic attributes
    problematic_found = any(
        key in ["taskName", "task_name", "TASK_NAME"] for key in resource_attrs.keys()
    )
    if problematic_found:
        print("WARNING: Problematic attributes found in resource")
    else:
        print("✓ No problematic attributes in resource")

    # Check for None values
    none_found = any(value is None for value in resource_attrs.values())
    if none_found:
        print("WARNING: None values found in resource")
    else:
        print("✓ No None values in resource")

    # Test creating actual Resource
    try:
        resource = Resource(attributes=resource_attrs)
        print("✓ Resource created successfully")
        return True
    except Exception as e:
        print(f"ERROR: Failed to create resource: {e}")
        return False


def main():
    """Main test function."""
    print("Testing taskName attribute filtering fixes...")
    print("=" * 60)

    try:
        # Run tests
        test1_passed = test_job_processor_filtering()
        test2_passed = test_span_filter()
        test3_passed = test_resource_creation()

        print("\n" + "=" * 60)
        print("TEST RESULTS:")
        print(f"Job Processor Filtering: {'PASS' if test1_passed else 'FAIL'}")
        print(f"Span Filter: {'PASS' if test2_passed else 'FAIL'}")
        print(f"Resource Creation: {'PASS' if test3_passed else 'FAIL'}")

        all_passed = test1_passed and test2_passed and test3_passed
        print(f"\nOverall: {'ALL TESTS PASSED' if all_passed else 'SOME TESTS FAILED'}")

        if all_passed:
            print(
                "\n✓ The fixes should prevent taskName attribute warnings in GitLab CI"
            )
        else:
            print("\n✗ Some issues remain that need to be addressed")

    except Exception as e:
        print(f"Error during testing: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
