#!/usr/bin/env python3
"""
Test script to reproduce the OpenTelemetry taskName issue by simulating the actual span creation.
"""

import os
import sys
from unittest.mock import Mock, patch

# Add the project root to the Python path
sys.path.insert(0, ".")

# Mock environment variables that would be present in GitLab CI
os.environ.update(
    {
        "CI_PROJECT_ID": "40509251",
        "CI_PARENT_PIPELINE": "2017065587",
        "NEW_RELIC_API_KEY": "test-key",
        "GLAB_TOKEN": "test-token",
        "GLAB_EXPORT_LOGS": "true",
        "GLAB_LOW_DATA_MODE": "false",
        # Add some potential task-related environment variables that might exist in GitLab CI
        "CI_JOB_NAME": "a-job-in-parent",
        "CI_JOB_STAGE": "a-job-in-parent",
        "CI_PIPELINE_SOURCE": "push",
    }
)

# Sample job data
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
}


def test_with_mock_otel():
    """Test with mocked OpenTelemetry to see what attributes are being set."""
    print("=== Testing with mocked OpenTelemetry ===")

    from shared.custom_parsers import parse_attributes
    from shared.otel import create_resource_attributes
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME

    # Mock the OpenTelemetry components
    with patch("opentelemetry.trace.get_tracer") as mock_get_tracer, patch(
        "opentelemetry.trace.use_span"
    ) as mock_use_span:

        # Create mock span
        mock_span = Mock()
        mock_tracer = Mock()
        mock_tracer.start_span.return_value = mock_span
        mock_get_tracer.return_value = mock_tracer

        # Create job resource (similar to JobProcessor.create_job_resource)
        service_name = "test-service"
        resource_attributes = {
            SERVICE_NAME: service_name,
            "pipeline_id": str(os.getenv("CI_PARENT_PIPELINE")),
            "project_id": str(os.getenv("CI_PROJECT_ID")),
            "job_id": str(sample_job["id"]),
            "instrumentation.name": "gitlab-integration",
            "gitlab.source": "gitlab-exporter",
            "gitlab.resource.type": "span",
        }

        # Add job attributes
        job_attributes = parse_attributes(sample_job)
        resource_attributes.update(
            create_resource_attributes(job_attributes, service_name)
        )

        # Filter out None values
        filtered_resource_attributes = {
            key: value
            for key, value in resource_attributes.items()
            if value is not None and value != ""
        }

        print(f"Resource attributes count: {len(filtered_resource_attributes)}")

        # Create resource
        resource = Resource(attributes=filtered_resource_attributes)

        # Check resource attributes for taskName
        resource_attrs = dict(resource.attributes)
        task_attrs = [k for k in resource_attrs.keys() if "task" in k.lower()]
        if task_attrs:
            print(f"Task-related resource attributes: {task_attrs}")
            for attr in task_attrs:
                print(
                    f"  {attr}: {resource_attrs[attr]} (type: {type(resource_attrs[attr]).__name__})"
                )

        # Simulate span attribute setting
        span_attributes = parse_attributes(sample_job)
        filtered_span_attributes = {
            key: value for key, value in span_attributes.items() if value is not None
        }

        print(f"Span attributes count: {len(filtered_span_attributes)}")

        # Check what would be passed to set_attributes
        task_span_attrs = [
            k for k in filtered_span_attributes.keys() if "task" in k.lower()
        ]
        if task_span_attrs:
            print(f"Task-related span attributes: {task_span_attrs}")
            for attr in task_span_attrs:
                print(
                    f"  {attr}: {filtered_span_attributes[attr]} (type: {type(filtered_span_attributes[attr]).__name__})"
                )

        # Check if set_attributes was called with any problematic values
        if mock_span.set_attributes.called:
            call_args = mock_span.set_attributes.call_args
            if call_args:
                attrs = call_args[0][0] if call_args[0] else {}
                none_attrs = [k for k, v in attrs.items() if v is None]
                if none_attrs:
                    print(f"None attributes passed to set_attributes: {none_attrs}")


def test_environment_variables():
    """Test what environment variables might be creating taskName."""
    print("\n=== Testing environment variables ===")

    from shared.custom_parsers import grab_span_att_vars

    env_attrs = grab_span_att_vars()
    print(f"Environment attributes count: {len(env_attrs)}")

    # Look for any task-related environment variables
    task_env_attrs = [k for k in env_attrs.keys() if "task" in k.lower()]
    if task_env_attrs:
        print(f"Task-related environment attributes: {task_env_attrs}")
        for attr in task_env_attrs:
            print(
                f"  {attr}: {env_attrs[attr]} (type: {type(env_attrs[attr]).__name__})"
            )
    else:
        print("No task-related environment attributes found")

    # Check for None values in environment
    none_env_attrs = [k for k, v in env_attrs.items() if v is None]
    if none_env_attrs:
        print(f"Environment attributes with None values: {none_env_attrs}")
    else:
        print("No None values in environment attributes")


def test_with_additional_env_vars():
    """Test with additional environment variables that might exist in GitLab CI."""
    print("\n=== Testing with additional GitLab CI environment variables ===")

    # Add more GitLab CI environment variables that might contain taskName
    additional_env_vars = {
        "CI_PIPELINE_ID": "2017065587",
        "CI_JOB_ID": "11215821048",
        "CI_JOB_TOKEN": "test-token",
        "CI_JOB_URL": "https://gitlab.com/dpacheconr/gitlab-metrics-exporter/-/jobs/11215821048",
        "CI_RUNNER_ID": "12270852",
        "CI_RUNNER_DESCRIPTION": "3-green.saas-linux-small-amd64.runners-manager.gitlab.com/default",
        "CI_RUNNER_TAGS": "",
        "CI_COMMIT_SHA": "dd4fe5ed75a9a90456f83ffbd96bed6bcbeb5991",
        "CI_COMMIT_SHORT_SHA": "dd4fe5ed",
        "CI_COMMIT_REF_NAME": "main",
        "CI_COMMIT_BRANCH": "main",
        "CI_COMMIT_MESSAGE": "Edit new-relic-exporter.yml",
        "CI_COMMIT_TITLE": "Edit new-relic-exporter.yml",
        "CI_COMMIT_AUTHOR": "dpacheconr",
        "CI_COMMIT_TIMESTAMP": "2025-09-02T14:54:26.000+03:00",
        "CI_PROJECT_NAME": "gitlab-metrics-exporter",
        "CI_PROJECT_PATH": "dpacheconr/gitlab-metrics-exporter",
        "CI_PROJECT_URL": "https://gitlab.com/dpacheconr/gitlab-metrics-exporter",
        "CI_PIPELINE_SOURCE": "push",
        "CI_PIPELINE_URL": "https://gitlab.com/dpacheconr/gitlab-metrics-exporter/-/pipelines/2017065587",
        "GITLAB_CI": "true",
        # Potentially problematic variables that might have None values
        "CI_MERGE_REQUEST_ID": "",
        "CI_MERGE_REQUEST_IID": "",
        "CI_MERGE_REQUEST_TITLE": "",
        "CI_MERGE_REQUEST_SOURCE_BRANCH_NAME": "",
        "CI_MERGE_REQUEST_TARGET_BRANCH_NAME": "",
        "CI_EXTERNAL_PULL_REQUEST_IID": "",
        "CI_EXTERNAL_PULL_REQUEST_SOURCE_BRANCH_NAME": "",
        "CI_EXTERNAL_PULL_REQUEST_TARGET_BRANCH_NAME": "",
    }

    # Temporarily add these environment variables
    original_env = dict(os.environ)
    os.environ.update(additional_env_vars)

    try:
        from shared.custom_parsers import grab_span_att_vars

        env_attrs = grab_span_att_vars()
        print(f"Environment attributes count with additional vars: {len(env_attrs)}")

        # Look for task-related attributes
        task_env_attrs = [k for k in env_attrs.keys() if "task" in k.lower()]
        if task_env_attrs:
            print(f"Task-related environment attributes: {task_env_attrs}")
            for attr in task_env_attrs:
                print(
                    f"  {attr}: {env_attrs[attr]} (type: {type(env_attrs[attr]).__name__})"
                )

        # Look for empty string values that might become None
        empty_attrs = [k for k, v in env_attrs.items() if v == ""]
        if empty_attrs:
            print(f"Environment attributes with empty string values: {empty_attrs}")

        # Check for None values
        none_attrs = [k for k, v in env_attrs.items() if v is None]
        if none_attrs:
            print(f"Environment attributes with None values: {none_attrs}")

    finally:
        # Restore original environment
        os.environ.clear()
        os.environ.update(original_env)


def main():
    """Main test function."""
    print("Testing OpenTelemetry taskName attribute issue...")
    print("=" * 60)

    try:
        test_with_mock_otel()
        test_environment_variables()
        test_with_additional_env_vars()

        print("\n" + "=" * 60)
        print("CONCLUSION:")
        print("If no taskName attributes were found in the tests above,")
        print("the issue might be coming from:")
        print("1. OpenTelemetry instrumentation libraries")
        print("2. Environment variables not captured in our tests")
        print("3. GitLab CI-specific environment variables")
        print("4. The actual OpenTelemetry SDK creating default attributes")

    except Exception as e:
        print(f"Error during testing: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
