#!/usr/bin/env python3
"""
Debug script to reproduce the taskName OpenTelemetry attribute issue locally.
"""

import os
import json
from unittest.mock import Mock, patch
import sys

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
    }
)

# Sample job data similar to what we see in the GitLab CI logs
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
        "public_email": "",
        "name": "dpacheconr",
        "state": "active",
        "locked": False,
        "avatar_url": "https://secure.gravatar.com/avatar/95e87971db73537dfd4d26759c8d50877aeb00fdffc4995a02d1c622ce5e12bb?s=80&d=identicon",
        "web_url": "https://gitlab.com/dpacheconr",
        "created_at": "2022-10-25T12:52:33.307Z",
        "bio": "",
        "location": "",
        "linkedin": "",
        "twitter": "",
        "discord": "",
        "website_url": "",
        "github": "",
        "job_title": "",
        "pronouns": "",
        "organization": "",
        "bot": False,
        "work_information": None,
        "followers": 0,
        "following": 0,
        "local_time": "4:22 PM",
    },
    "commit": {
        "id": "dd4fe5ed75a9a90456f83ffbd96bed6bcbeb5991",
        "short_id": "dd4fe5ed",
        "created_at": "2025-09-02T14:54:26.000+03:00",
        "parent_ids": ["40fcb063e3c259e44a7021625dd7414e04344dc9"],
        "title": "Edit new-relic-exporter.yml",
        "message": "Edit new-relic-exporter.yml",
        "author_name": "dpacheconr",
        "author_email": "dpacheco@newrelic.com",
        "authored_date": "2025-09-02T14:54:26.000+03:00",
        "committer_name": "dpacheconr",
        "committer_email": "dpacheco@newrelic.com",
        "committed_date": "2025-09-02T14:54:26.000+03:00",
        "trailers": {},
        "extended_trailers": {},
        "web_url": "https://gitlab.com/dpacheconr/gitlab-metrics-exporter/-/commit/dd4fe5ed75a9a90456f83ffbd96bed6bcbeb5991",
    },
    "pipeline": {
        "id": 2017065587,
        "iid": 11225,
        "project_id": 40509251,
        "sha": "dd4fe5ed75a9a90456f83ffbd96bed6bcbeb5991",
        "ref": "main",
        "status": "success",
        "source": "push",
        "created_at": "2025-09-02T11:54:28.835Z",
        "updated_at": "2025-09-02T11:55:10.583Z",
        "web_url": "https://gitlab.com/dpacheconr/gitlab-metrics-exporter/-/pipelines/2017065587",
    },
    "web_url": "https://gitlab.com/dpacheconr/gitlab-metrics-exporter/-/jobs/11215821048",
    "project": {"ci_job_token_scope_enabled": False},
    "artifacts": [
        {"file_type": "trace", "size": 2966, "filename": "job.log", "file_format": None}
    ],
    "runner": {
        "id": 12270852,
        "description": "3-green.saas-linux-small-amd64.runners-manager.gitlab.com/default",
        "ip_address": None,
        "active": True,
        "paused": False,
        "is_shared": True,
        "runner_type": "instance_type",
        "name": "gitlab-runner",
        "online": True,
        "created_at": "2021-11-15T17:48:54.243Z",
        "status": "online",
        "job_execution_status": "active",
    },
    "runner_manager": {
        "id": 74819383,
        "system_id": "s_0e6850b2bce1",
        "version": "18.3.0~pre.23.gb8a899e1",
        "revision": "b8a899e1",
        "platform": "linux",
        "architecture": "amd64",
        "created_at": "2025-07-23T12:08:51.635Z",
        "contacted_at": "2025-09-02T13:22:59.475Z",
        "ip_address": "10.1.5.15",
        "status": "online",
        "job_execution_status": "active",
    },
    "artifacts_expire_at": None,
    "archived": False,
    "tag_list": [],
}


def debug_parse_attributes():
    """Debug the parse_attributes function to see what attributes it creates."""
    print("=== Debugging parse_attributes function ===")

    from shared.custom_parsers import parse_attributes

    # Test with the sample job data
    attributes = parse_attributes(sample_job)

    print(f"Total attributes created: {len(attributes)}")
    print("\nAll attributes:")
    for key, value in sorted(attributes.items()):
        print(f"  {key}: {value} (type: {type(value).__name__})")

    # Look specifically for taskName or similar attributes
    task_related = [k for k in attributes.keys() if "task" in k.lower()]
    if task_related:
        print(f"\nTask-related attributes found: {task_related}")
    else:
        print("\nNo task-related attributes found in parse_attributes output")

    # Check for None values
    none_values = [k for k, v in attributes.items() if v is None]
    if none_values:
        print(f"\nAttributes with None values: {none_values}")
    else:
        print("\nNo None values found in parse_attributes output")

    return attributes


def debug_resource_creation():
    """Debug the resource creation process."""
    print("\n=== Debugging resource creation ===")

    from shared.custom_parsers import parse_attributes, grab_span_att_vars
    from shared.otel import create_resource_attributes
    from opentelemetry.sdk.resources import Resource, SERVICE_NAME

    # Get job attributes
    job_attributes = parse_attributes(sample_job)
    print(f"Job attributes count: {len(job_attributes)}")

    # Get environment attributes
    env_attributes = grab_span_att_vars()
    print(f"Environment attributes count: {len(env_attributes)}")

    # Check for taskName in environment
    task_env_attrs = [k for k in env_attributes.keys() if "task" in k.lower()]
    if task_env_attrs:
        print(f"Task-related environment attributes: {task_env_attrs}")
        for attr in task_env_attrs:
            print(f"  {attr}: {env_attributes[attr]}")

    # Create resource attributes
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
    resource_attributes.update(create_resource_attributes(job_attributes, service_name))

    print(f"\nFinal resource attributes count: {len(resource_attributes)}")

    # Look for taskName in final attributes
    task_final_attrs = [k for k in resource_attributes.keys() if "task" in k.lower()]
    if task_final_attrs:
        print(f"Task-related final attributes: {task_final_attrs}")
        for attr in task_final_attrs:
            print(
                f"  {attr}: {resource_attributes[attr]} (type: {type(resource_attributes[attr]).__name__})"
            )

    # Check for None values in final attributes
    none_final = [k for k, v in resource_attributes.items() if v is None]
    if none_final:
        print(f"Final attributes with None values: {none_final}")
        for attr in none_final:
            print(f"  {attr}: {resource_attributes[attr]}")

    return resource_attributes


def debug_span_attributes():
    """Debug span attribute setting."""
    print("\n=== Debugging span attributes ===")

    from shared.custom_parsers import parse_attributes

    # Get job attributes that would be set on the span
    job_attributes = parse_attributes(sample_job)

    # Filter out None values (as done in the code)
    filtered_attributes = {
        key: value for key, value in job_attributes.items() if value is not None
    }

    print(f"Span attributes after None filtering: {len(filtered_attributes)}")

    # Look for taskName
    task_span_attrs = [k for k in filtered_attributes.keys() if "task" in k.lower()]
    if task_span_attrs:
        print(f"Task-related span attributes: {task_span_attrs}")
        for attr in task_span_attrs:
            print(
                f"  {attr}: {filtered_attributes[attr]} (type: {type(filtered_attributes[attr]).__name__})"
            )

    return filtered_attributes


def main():
    """Main debug function."""
    print("Starting taskName attribute debugging...")
    print("=" * 60)

    try:
        # Debug each step of the process
        job_attrs = debug_parse_attributes()
        resource_attrs = debug_resource_creation()
        span_attrs = debug_span_attributes()

        print("\n" + "=" * 60)
        print("SUMMARY:")

        # Check if taskName appears anywhere
        all_attrs = {}
        all_attrs.update(job_attrs)
        all_attrs.update(resource_attrs)
        all_attrs.update(span_attrs)

        task_attrs = [k for k in all_attrs.keys() if "task" in k.lower()]
        if task_attrs:
            print(f"Found task-related attributes: {task_attrs}")
            for attr in task_attrs:
                print(
                    f"  {attr}: {all_attrs[attr]} (type: {type(all_attrs[attr]).__name__})"
                )
        else:
            print("No task-related attributes found in any step")

        # Check for None values that could cause the warning
        none_attrs = [k for k, v in all_attrs.items() if v is None]
        if none_attrs:
            print(f"Found None values: {none_attrs}")
        else:
            print("No None values found")

    except Exception as e:
        print(f"Error during debugging: {e}")
        import traceback

        traceback.print_exc()


if __name__ == "__main__":
    main()
