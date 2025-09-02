#!/usr/bin/env python3
"""
Test with the actual GitLab job data structure from the CI logs.
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


def test_with_real_gitlab_data():
    """Test with the actual GitLab job data from the CI logs."""
    print("🔍 Testing with real GitLab job data")
    print("=" * 60)

    # This is the actual job data from the GitLab CI logs
    real_job_data = {
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
            {
                "file_type": "trace",
                "size": 2966,
                "filename": "job.log",
                "file_format": None,
            }
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

    print("1. Testing parse_attributes with real GitLab data...")

    try:
        from shared.custom_parsers import parse_attributes

        # Parse the real job attributes
        job_attributes = parse_attributes(real_job_data)
        print(f"   Parsed {len(job_attributes)} attributes from real data")

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

        # Print all attributes to see what we're working with
        print(f"\n   All parsed attributes:")
        for k, v in sorted(job_attributes.items()):
            print(f"      {k}: {v}")

    except Exception as e:
        print(f"   Error in parse_attributes: {e}")

    print("\n2. Testing with environment variables that might exist in GitLab CI...")

    # Add environment variables that might exist in the actual GitLab CI environment
    gitlab_env_vars = {
        "CI_JOB_NAME": "a-job-in-parent",
        "CI_JOB_STAGE": "a-job-in-parent",
        "CI_JOB_ID": "11215821048",
        "CI_PIPELINE_ID": "2017065587",
        "CI_PIPELINE_IID": "11225",
        "CI_COMMIT_SHA": "dd4fe5ed75a9a90456f83ffbd96bed6bcbeb5991",
        "CI_COMMIT_SHORT_SHA": "dd4fe5ed",
        "CI_COMMIT_REF_NAME": "main",
        "CI_COMMIT_BRANCH": "main",
        "CI_COMMIT_MESSAGE": "Edit new-relic-exporter.yml",
        "CI_COMMIT_TITLE": "Edit new-relic-exporter.yml",
        "CI_COMMIT_AUTHOR": "dpacheconr",
        "CI_PROJECT_NAME": "gitlab-metrics-exporter",
        "CI_PROJECT_PATH": "dpacheconr/gitlab-metrics-exporter",
        "CI_PROJECT_URL": "https://gitlab.com/dpacheconr/gitlab-metrics-exporter",
        "CI_PIPELINE_SOURCE": "push",
        "CI_PIPELINE_URL": "https://gitlab.com/dpacheconr/gitlab-metrics-exporter/-/pipelines/2017065587",
        "CI_RUNNER_ID": "12270852",
        "CI_RUNNER_DESCRIPTION": "3-green.saas-linux-small-amd64.runners-manager.gitlab.com/default",
        "CI_RUNNER_TAGS": "",
        "GITLAB_CI": "true",
        # These might be the problematic ones
        "CI_JOB_TOKEN": "glcbt-64_chars_token_here",
        "CI_BUILD_TOKEN": "glcbt-64_chars_token_here",
        "CI_REGISTRY_PASSWORD": "glcbt-64_chars_token_here",
        # Potentially empty/None values
        "CI_MERGE_REQUEST_ID": "",
        "CI_MERGE_REQUEST_IID": "",
        "CI_MERGE_REQUEST_TITLE": "",
        "CI_EXTERNAL_PULL_REQUEST_IID": "",
        "CI_DEPLOY_PASSWORD": "",
        "CI_DEPLOY_USER": "",
    }

    # Set environment variables
    original_env = dict(os.environ)
    os.environ.update(gitlab_env_vars)

    try:
        from shared.custom_parsers import grab_span_att_vars

        env_attrs = grab_span_att_vars()
        print(f"   Environment attributes: {len(env_attrs)}")

        # Check for task-related attributes
        task_env_attrs = {k: v for k, v in env_attrs.items() if "task" in k.lower()}
        if task_env_attrs:
            print(f"   Task env attributes: {task_env_attrs}")
        else:
            print("   No task env attributes found")

        # Check for None or empty values
        problematic_env_attrs = {
            k: v for k, v in env_attrs.items() if v is None or v == ""
        }
        if problematic_env_attrs:
            print(f"   Problematic env attributes: {problematic_env_attrs}")
        else:
            print("   No problematic env attributes")

    except Exception as e:
        print(f"   Error in grab_span_att_vars: {e}")

    print("\n3. Testing JobProcessor with real data...")

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

        # Test resource creation with real data
        job_resource = processor.create_job_resource(real_job_data, "gitlab-exporter")
        print(f"   Job resource created with {len(job_resource.attributes)} attributes")

        # Check for None values
        resource_attrs = dict(job_resource.attributes)
        none_resource_attrs = {k: v for k, v in resource_attrs.items() if v is None}
        if none_resource_attrs:
            print(f"   ❌ Found None values in resource: {none_resource_attrs}")
        else:
            print("   ✅ No None values in resource")

        # Check for taskName
        task_resource_attrs = {
            k: v for k, v in resource_attrs.items() if "task" in k.lower()
        }
        if task_resource_attrs:
            print(f"   Task attributes in resource: {task_resource_attrs}")
        else:
            print("   No task attributes in resource")

        # Print all resource attributes to debug
        print(f"\n   All resource attributes:")
        for k, v in sorted(resource_attrs.items()):
            if v is None:
                print(f"      {k}: {v} ❌ (None value)")
            else:
                print(f"      {k}: {v}")

    except Exception as e:
        print(f"   Error in JobProcessor: {e}")

    # Restore original environment
    os.environ.clear()
    os.environ.update(original_env)

    print("\n" + "=" * 60)
    print("🎯 Summary:")
    print(
        "Testing with real GitLab job data to identify the source of taskName attributes."
    )


if __name__ == "__main__":
    test_with_real_gitlab_data()
