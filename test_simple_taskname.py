#!/usr/bin/env python3
"""
Simple test to reproduce the OpenTelemetry taskName issue.
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


def test_taskname_issue():
    """Test to reproduce the taskName issue."""
    print("🔍 Testing OpenTelemetry taskName issue")
    print("=" * 50)

    # Sample job data from GitLab
    sample_job = {
        "id": 11215821048,
        "status": "success",
        "stage": "a-job-in-parent",
        "name": "a-job-in-parent",
        "ref": "main",
        "tag": False,
        "coverage": None,
        "allow_failure": True,
        "created_at": "2025-09-02T11:54:28.847Z",
        "started_at": "2025-09-02T11:54:30.120Z",
        "finished_at": "2025-09-02T11:55:06.109Z",
        "erased_at": None,
        "duration": 35.98896,
        "queued_duration": 0.480128,
        "user": {
            "id": 12875476,
            "username": "dpacheconr",
            "name": "dpacheconr",
            "state": "active",
        },
        "commit": {
            "id": "dd4fe5ed75a9a90456f83ffbd96bed6bcbeb5991",
            "short_id": "dd4fe5ed",
            "title": "Edit new-relic-exporter.yml",
        },
        "pipeline": {"id": 2017065587, "status": "success", "source": "push"},
        "runner": {
            "id": 12270852,
            "description": "3-green.saas-linux-small-amd64.runners-manager.gitlab.com/default",
            "active": True,
            "is_shared": True,
            "runner_type": "instance_type",
            "name": "gitlab-runner",
        },
        "artifacts": [{"file_type": "trace", "size": 2966, "filename": "job.log"}],
        "tag_list": [],
    }

    print("1. Testing parse_attributes function...")

    try:
        from shared.custom_parsers import parse_attributes

        # Parse job attributes
        job_attributes = parse_attributes(sample_job)
        print(f"   Parsed {len(job_attributes)} attributes")

        # Check for None values
        none_attrs = {k: v for k, v in job_attributes.items() if v is None}
        if none_attrs:
            print(f"   ❌ Found None values: {none_attrs}")
        else:
            print("   ✅ No None values found")

        # Check for taskName variations
        task_attrs = {k: v for k, v in job_attributes.items() if "task" in k.lower()}
        if task_attrs:
            print(f"   Found task attributes: {task_attrs}")
        else:
            print("   No task attributes found")

    except Exception as e:
        print(f"   Error in parse_attributes: {e}")

    print("\n2. Testing environment variables...")

    try:
        from shared.custom_parsers import grab_span_att_vars

        env_attrs = grab_span_att_vars()
        print(f"   Found {len(env_attrs)} environment attributes")

        # Check for task-related env vars
        task_env_attrs = {k: v for k, v in env_attrs.items() if "task" in k.lower()}
        if task_env_attrs:
            print(f"   Found task env attributes: {task_env_attrs}")
        else:
            print("   No task env attributes found")

    except Exception as e:
        print(f"   Error in grab_span_att_vars: {e}")

    print("\n3. Testing JobProcessor...")

    try:
        from shared.config.settings import GitLabConfig
        from new_relic_exporter.processors.job_processor import JobProcessor

        # Create config
        config = GitLabConfig(
            token="test-token",
            new_relic_api_key="test-key",
            low_data_mode=False,
            export_logs=False,
        )

        # Mock project
        project = Mock()

        # Create processor
        processor = JobProcessor(config, project)

        # Test resource creation
        resource = processor.create_job_resource(sample_job, "test-service")
        print(f"   Created resource with {len(resource.attributes)} attributes")

        # Check for None values in resource
        resource_none_attrs = {
            k: v for k, v in resource.attributes.items() if v is None
        }
        if resource_none_attrs:
            print(f"   ❌ Found None values in resource: {resource_none_attrs}")
        else:
            print("   ✅ No None values in resource")

        # Check for taskName in resource
        resource_task_attrs = {
            k: v for k, v in resource.attributes.items() if "task" in k.lower()
        }
        if resource_task_attrs:
            print(f"   Found task attributes in resource: {resource_task_attrs}")
        else:
            print("   No task attributes in resource")

    except Exception as e:
        print(f"   Error in JobProcessor: {e}")

    print("\n4. Simulating span.set_attributes() call...")

    # This is where the issue likely occurs
    try:
        # Mock OpenTelemetry span
        mock_span = Mock()

        # Get attributes that would be passed to set_attributes
        from shared.custom_parsers import parse_attributes

        span_attrs = parse_attributes(sample_job)

        # Check what would happen if we call set_attributes with these
        print(f"   Would set {len(span_attrs)} span attributes")

        # Look for None values that would cause warnings
        none_span_attrs = {k: v for k, v in span_attrs.items() if v is None}
        if none_span_attrs:
            print(f"   ❌ These None values would cause OpenTelemetry warnings:")
            for k, v in none_span_attrs.items():
                print(f"      {k}: {v}")
        else:
            print("   ✅ No None values that would cause warnings")

        # Filter out None values (this is what we should do)
        filtered_attrs = {k: v for k, v in span_attrs.items() if v is not None}
        print(f"   After filtering: {len(filtered_attrs)} attributes")

        # Simulate the call
        mock_span.set_attributes(filtered_attrs)
        print("   ✅ Mock span.set_attributes() call successful")

    except Exception as e:
        print(f"   Error in span simulation: {e}")

    print("\n" + "=" * 50)
    print("🎯 Summary:")
    print("The issue is likely that span.set_attributes() is being called")
    print("with attributes that contain None values, specifically 'taskName'.")
    print("The fix is to filter out None values before calling set_attributes().")


if __name__ == "__main__":
    test_taskname_issue()
