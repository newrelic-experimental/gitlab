#!/usr/bin/env python3
"""
Test to reproduce the resource attributes issue with taskName.
"""

import os
import sys
from unittest.mock import Mock

# Add the project root to the Python path
sys.path.insert(0, ".")

# Mock environment variables
os.environ.update(
    {
        "CI_PROJECT_ID": "40509251",
        "CI_PARENT_PIPELINE": "2017065587",
        "NEW_RELIC_API_KEY": "test-key",
        "GLAB_TOKEN": "test-token",
    }
)


def test_resource_attributes_issue():
    """Test the resource attributes creation with problematic data."""
    print("🔍 Testing resource attributes with taskName issue")
    print("=" * 60)

    # Import the functions
    from shared.custom_parsers import parse_attributes, grab_span_att_vars
    from shared.otel import create_resource_attributes
    from opentelemetry.sdk.resources import Resource

    # Test 1: Job attributes that might contain taskName
    print("1. Testing job attributes...")

    # Sample job with potential taskName issues
    sample_job = {
        "id": 11215821048,
        "status": "success",
        "name": "a-job-in-parent",
        "taskName": None,  # This could be the issue
        "task_name": None,
        "user": {
            "taskName": None,
            "task_name": None,
        },
        "commit": {
            "taskName": None,
        },
        "pipeline": {
            "taskName": None,
        },
    }

    job_attributes = parse_attributes(sample_job)
    print(f"   Job attributes: {len(job_attributes)}")

    # Check for taskName in job attributes
    task_attrs = {k: v for k, v in job_attributes.items() if "task" in k.lower()}
    if task_attrs:
        print(f"   Task attributes in job: {task_attrs}")
    else:
        print("   No task attributes in job")

    # Test 2: Environment attributes
    print("\n2. Testing environment attributes...")

    # Add some problematic environment variables
    os.environ.update(
        {
            "CI_TASK_NAME": "",
            "TASK_NAME": "",
            "CI_PIPELINE_TASK_NAME": "",
        }
    )

    env_attributes = grab_span_att_vars()
    print(f"   Environment attributes: {len(env_attributes)}")

    # Check for taskName in environment
    env_task_attrs = {k: v for k, v in env_attributes.items() if "task" in k.lower()}
    if env_task_attrs:
        print(f"   Task attributes in env: {env_task_attrs}")
    else:
        print("   No task attributes in env")

    # Test 3: create_resource_attributes function
    print("\n3. Testing create_resource_attributes function...")

    # Combine job and environment attributes
    all_attributes = {**job_attributes, **env_attributes}

    # Test create_resource_attributes with these
    resource_attrs = create_resource_attributes(all_attributes, "test-service")
    print(f"   Resource attributes: {len(resource_attrs)}")

    # Check for None values in resource attributes
    none_attrs = {k: v for k, v in resource_attrs.items() if v is None}
    if none_attrs:
        print(f"   ❌ Found None values in resource attributes: {none_attrs}")
    else:
        print("   ✅ No None values in resource attributes")

    # Check for taskName in resource attributes
    resource_task_attrs = {
        k: v for k, v in resource_attrs.items() if "task" in k.lower()
    }
    if resource_task_attrs:
        print(f"   Task attributes in resource: {resource_task_attrs}")
    else:
        print("   No task attributes in resource")

    # Test 4: Create actual Resource object
    print("\n4. Testing Resource object creation...")

    try:
        resource = Resource(attributes=resource_attrs)
        print(
            f"   ✅ Resource created successfully with {len(resource.attributes)} attributes"
        )

        # Check the actual resource attributes
        actual_attrs = dict(resource.attributes)
        actual_none_attrs = {k: v for k, v in actual_attrs.items() if v is None}
        if actual_none_attrs:
            print(f"   ❌ Found None values in actual resource: {actual_none_attrs}")
        else:
            print("   ✅ No None values in actual resource")

        # Check for taskName in actual resource
        actual_task_attrs = {
            k: v for k, v in actual_attrs.items() if "task" in k.lower()
        }
        if actual_task_attrs:
            print(f"   Task attributes in actual resource: {actual_task_attrs}")
            for k, v in actual_task_attrs.items():
                print(f"      {k}: {v} (type: {type(v)})")
        else:
            print("   No task attributes in actual resource")

    except Exception as e:
        print(f"   ❌ Error creating resource: {e}")

    # Test 5: Simulate the exact scenario from job_processor.py
    print("\n5. Testing job_processor scenario...")

    try:
        from shared.config.settings import GitLabConfig
        from new_relic_exporter.processors.job_processor import JobProcessor

        # Create config
        config = GitLabConfig(
            token="test-token",
            new_relic_api_key="test-key",
            low_data_mode=False,
            export_logs=True,
        )

        # Mock project
        project = Mock()

        # Create processor
        processor = JobProcessor(config, project)

        # Create job resource
        job_resource = processor.create_job_resource(sample_job, "test-service")
        print(f"   Job resource created with {len(job_resource.attributes)} attributes")

        # Check job resource attributes
        job_resource_attrs = dict(job_resource.attributes)
        job_resource_none_attrs = {
            k: v for k, v in job_resource_attrs.items() if v is None
        }
        if job_resource_none_attrs:
            print(f"   ❌ Found None values in job resource: {job_resource_none_attrs}")
        else:
            print("   ✅ No None values in job resource")

        # Check for taskName in job resource
        job_resource_task_attrs = {
            k: v for k, v in job_resource_attrs.items() if "task" in k.lower()
        }
        if job_resource_task_attrs:
            print(f"   Task attributes in job resource: {job_resource_task_attrs}")
            for k, v in job_resource_task_attrs.items():
                print(f"      {k}: {v} (type: {type(v)})")
        else:
            print("   No task attributes in job resource")

        # Test the handle_job_logs scenario (this is where the issue occurs)
        print("\n   Testing handle_job_logs scenario...")

        # Simulate the attrs creation in handle_job_logs
        attrs = job_resource_attrs.copy()
        attrs["log"] = "test log message"

        # Apply the filtering from handle_job_logs
        problematic_attrs = [
            "TASK_NAME",
            "CICD_PIPELINE_TASK_NAME",
            "CI_PIPELINE_TASK_NAME",
            "taskName",
            "task_name",
        ]

        filtered_attrs = {
            key: value
            for key, value in attrs.items()
            if value is not None
            and value != ""
            and value != "None"
            and key not in problematic_attrs
        }

        print(f"   Filtered attributes: {len(filtered_attrs)}")

        # Check for None values after filtering
        filtered_none_attrs = {k: v for k, v in filtered_attrs.items() if v is None}
        if filtered_none_attrs:
            print(f"   ❌ Found None values after filtering: {filtered_none_attrs}")
        else:
            print("   ✅ No None values after filtering")

        # Check for taskName after filtering
        filtered_task_attrs = {
            k: v for k, v in filtered_attrs.items() if "task" in k.lower()
        }
        if filtered_task_attrs:
            print(
                f"   ❌ Task attributes still present after filtering: {filtered_task_attrs}"
            )
        else:
            print("   ✅ No task attributes after filtering")

        # Try creating the resource_log
        try:
            resource_log = Resource(attributes=filtered_attrs)
            print(f"   ✅ Resource log created successfully")
        except Exception as e:
            print(f"   ❌ Error creating resource log: {e}")

    except Exception as e:
        print(f"   ❌ Error in job_processor scenario: {e}")

    # Clean up environment variables
    for key in ["CI_TASK_NAME", "TASK_NAME", "CI_PIPELINE_TASK_NAME"]:
        if key in os.environ:
            del os.environ[key]

    print("\n" + "=" * 60)
    print("🎯 Analysis:")
    print("The issue is likely in the resource attribute creation or filtering.")
    print("We need to ensure that taskName attributes are completely filtered out")
    print("before creating Resource objects for both spans and logs.")


if __name__ == "__main__":
    test_resource_attributes_issue()
