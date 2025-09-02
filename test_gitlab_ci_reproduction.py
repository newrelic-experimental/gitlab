#!/usr/bin/env python3
"""
Comprehensive local reproduction of the GitLab CI taskName issue.
This script simulates the exact GitLab CI environment and job data structure.
"""

import os
import sys
import json
from unittest.mock import Mock, patch

# Add the project root to Python path
sys.path.insert(0, os.path.abspath("."))

# Set up GitLab CI environment variables exactly as they appear in CI
os.environ.update(
    {
        "CI": "true",
        "GITLAB_CI": "true",
        "CI_PROJECT_ID": "40509251",
        "CI_PIPELINE_ID": "2017065587",
        "CI_JOB_ID": "11215821048",
        "CI_JOB_NAME": "a-job-in-parent",
        "CI_JOB_STAGE": "a-job-in-parent",
        "CI_COMMIT_SHA": "dd4fe5ed75a9a90456f83ffbd96bed6bcbeb5991",
        "CI_COMMIT_REF_NAME": "main",
        "CI_PROJECT_NAME": "gitlab-metrics-exporter",
        "CI_PROJECT_NAMESPACE": "dpacheconr",
        "CI_RUNNER_ID": "12270852",
        "CI_RUNNER_DESCRIPTION": "3-green.saas-linux-small-amd64.runners-manager.gitlab.com/default",
        "GITLAB_USER_LOGIN": "dpacheconr",
        "GITLAB_USER_EMAIL": "dpacheco@newrelic.com",
        "NEW_RELIC_LICENSE_KEY": "test_key_12345",
        "NEW_RELIC_API_KEY": "test_api_key_12345",
        "GITLAB_TOKEN": "test_gitlab_token",
        # Potentially problematic environment variables (as strings since env vars are always strings)
        "TASK_NAME": "",
        "CI_TASK_NAME": "",
        "PIPELINE_TASK_NAME": "None",
        "JOB_TASK_NAME": "",
        "GITLAB_TASK_NAME": "",
    }
)


def create_real_gitlab_job_data():
    """Create the exact job data structure from the GitLab CI logs."""
    return {
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
        "taskName": None,  # This is the problematic attribute
        "task_name": None,
        "TASK_NAME": None,
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


def test_job_processor_with_real_data():
    """Test the job processor with the exact data structure from GitLab CI."""
    print("=" * 80)
    print("TESTING JOB PROCESSOR WITH REAL GITLAB CI DATA")
    print("=" * 80)

    try:
        from new_relic_exporter.processors.job_processor import JobProcessor
        from shared.config.settings import Settings

        # Create settings
        settings = Settings()

        # Create job processor
        processor = JobProcessor(settings)

        # Create the real job data
        job_data = create_real_gitlab_job_data()

        print(f"Job data keys: {list(job_data.keys())}")
        print(f"Problematic attributes in job data:")
        for key, value in job_data.items():
            if "task" in key.lower() and value is None:
                print(f"  {key}: {value} (type: {type(value)})")

        print("\nProcessing job data...")

        # This should trigger the same code path as in GitLab CI
        result = processor.process_job(job_data)

        print(f"Job processing result: {result}")
        print("Job processing completed successfully!")

    except Exception as e:
        print(f"Error during job processing: {e}")
        import traceback

        traceback.print_exc()


def test_attribute_parsing():
    """Test the attribute parsing functions directly."""
    print("\n" + "=" * 80)
    print("TESTING ATTRIBUTE PARSING FUNCTIONS")
    print("=" * 80)

    try:
        from shared.custom_parsers import grab_span_att_vars, parse_attributes

        # Test environment variable parsing
        print("Testing grab_span_att_vars...")
        env_attrs = grab_span_att_vars()
        print(f"Environment attributes count: {len(env_attrs)}")

        problematic_found = []
        for key, value in env_attrs.items():
            if "task" in key.lower():
                problematic_found.append((key, value, type(value)))

        if problematic_found:
            print("Problematic attributes found in environment:")
            for key, value, value_type in problematic_found:
                print(f"  {key}: {value} (type: {value_type})")
        else:
            print("No problematic taskName attributes found in environment - GOOD!")

        # Test job data parsing
        print("\nTesting parse_attributes...")
        job_data = create_real_gitlab_job_data()
        parsed_attrs = parse_attributes(job_data)
        print(f"Parsed attributes count: {len(parsed_attrs)}")

        problematic_found = []
        for key, value in parsed_attrs.items():
            if "task" in key.lower():
                problematic_found.append((key, value, type(value)))

        if problematic_found:
            print("Problematic attributes found in parsed data:")
            for key, value, value_type in problematic_found:
                print(f"  {key}: {value} (type: {value_type})")
        else:
            print("No problematic taskName attributes found in parsed data - GOOD!")

    except Exception as e:
        print(f"Error during attribute parsing test: {e}")
        import traceback

        traceback.print_exc()


def test_resource_creation():
    """Test the OpenTelemetry resource creation directly."""
    print("\n" + "=" * 80)
    print("TESTING OPENTELEMETRY RESOURCE CREATION")
    print("=" * 80)

    try:
        from shared.otel import create_resource_attributes

        # Test with problematic data
        test_attrs = {
            "service.name": "gitlab-exporter",
            "taskName": None,
            "task_name": None,
            "TASK_NAME": "",
            "CI_TASK_NAME": "None",
            "job.id": "11215821048",
            "job.name": "a-job-in-parent",
            "pipeline.id": "2017065587",
            "project.id": "40509251",
        }

        print(f"Input attributes: {test_attrs}")

        # This should filter out the problematic attributes
        filtered_attrs = create_resource_attributes(test_attrs)

        print(f"Filtered attributes: {filtered_attrs}")

        # Check if any problematic attributes remain
        problematic_found = []
        for key, value in filtered_attrs.items():
            if "task" in key.lower():
                problematic_found.append((key, value, type(value)))
            if value is None:
                problematic_found.append((key, value, type(value)))

        if problematic_found:
            print("ERROR: Problematic attributes still present after filtering:")
            for key, value, value_type in problematic_found:
                print(f"  {key}: {value} (type: {value_type})")
        else:
            print("SUCCESS: No problematic attributes found after filtering!")

    except Exception as e:
        print(f"Error during resource creation test: {e}")
        import traceback

        traceback.print_exc()


def test_logger_creation():
    """Test the actual logger creation that's causing the warnings."""
    print("\n" + "=" * 80)
    print("TESTING LOGGER CREATION (THE ACTUAL PROBLEM)")
    print("=" * 80)

    try:
        from shared.logging.structured_logger import StructuredLogger
        from shared.custom_parsers import grab_span_att_vars, parse_attributes

        # Simulate the exact scenario from job_processor.py:129
        job_data = create_real_gitlab_job_data()

        # Get attributes the same way as in the actual code
        env_attrs = grab_span_att_vars()
        job_attrs = parse_attributes(job_data)

        # Combine attributes
        combined_attrs = {**env_attrs, **job_attrs}

        print(f"Combined attributes count: {len(combined_attrs)}")

        # Check for problematic attributes
        problematic_found = []
        for key, value in combined_attrs.items():
            if "task" in key.lower() or value is None:
                problematic_found.append((key, value, type(value)))

        if problematic_found:
            print("Problematic attributes found before logger creation:")
            for key, value, value_type in problematic_found:
                print(f"  {key}: {value} (type: {value_type})")

        # Create the logger (this is where the warning occurs)
        print("\nCreating logger...")
        logger = StructuredLogger("job_logger", combined_attrs)

        # Try to log something (this triggers the warning)
        print(
            "Attempting to log (this should trigger the warning if the bug exists)..."
        )
        logger.info("")  # This is the exact line from job_processor.py:129

        print("Logger creation and logging completed!")

    except Exception as e:
        print(f"Error during logger creation test: {e}")
        import traceback

        traceback.print_exc()


def main():
    """Run all tests to reproduce the GitLab CI issue locally."""
    print("GITLAB CI TASKNAME ISSUE - LOCAL REPRODUCTION")
    print("=" * 80)
    print("This script reproduces the exact GitLab CI environment and data")
    print("to debug the 'Invalid type NoneType for attribute taskName' warnings.")
    print("=" * 80)

    # Run all tests
    test_attribute_parsing()
    test_resource_creation()
    test_logger_creation()
    test_job_processor_with_real_data()

    print("\n" + "=" * 80)
    print("REPRODUCTION TEST COMPLETED")
    print("=" * 80)
    print("If you see OpenTelemetry warnings above, the issue is reproduced locally.")
    print("If no warnings appear, the filtering is working correctly.")


if __name__ == "__main__":
    main()
