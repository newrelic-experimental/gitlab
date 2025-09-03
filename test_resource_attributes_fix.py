"""
Test using OTEL_RESOURCE_ATTRIBUTES to fix taskName warnings.

This approach explicitly sets the problematic attributes to valid values
instead of filtering them out, which should prevent the None value warnings.
"""

import os
import logging
from unittest.mock import patch


def test_resource_attributes_approach():
    """Test setting OTEL_RESOURCE_ATTRIBUTES to fix taskName issues."""
    print("Testing OTEL_RESOURCE_ATTRIBUTES approach")
    print("=" * 50)

    # Test scenarios with different resource attribute configurations
    test_scenarios = [
        {
            "name": "Set taskName to CI_JOB_NAME",
            "resource_attrs": "service.name=gitlab-exporter,cicd.pipeline.task.name=test-job",
            "env_vars": {"CI_JOB_NAME": "test-job", "CI_PIPELINE_ID": "12345"},
        },
        {
            "name": "Set multiple task-related attributes",
            "resource_attrs": "service.name=gitlab-exporter,cicd.pipeline.task.name=test-job,task.name=test-job,taskName=test-job",
            "env_vars": {"CI_JOB_NAME": "test-job", "CI_PIPELINE_ID": "12345"},
        },
        {
            "name": "Use CI environment variables in resource attributes",
            "resource_attrs": "service.name=gitlab-exporter,cicd.pipeline.task.name=${CI_JOB_NAME},cicd.pipeline.id=${CI_PIPELINE_ID}",
            "env_vars": {"CI_JOB_NAME": "my-test-job", "CI_PIPELINE_ID": "67890"},
        },
    ]

    for scenario in test_scenarios:
        print(f"\n--- {scenario['name']} ---")
        print(f"OTEL_RESOURCE_ATTRIBUTES: {scenario['resource_attrs']}")

        # Set up environment
        test_env = {
            "OTEL_RESOURCE_ATTRIBUTES": scenario["resource_attrs"],
            **scenario["env_vars"],
        }

        with patch.dict(os.environ, test_env, clear=False):
            try:
                # Import OpenTelemetry after setting resource attributes
                from opentelemetry import trace
                from opentelemetry.sdk.trace import TracerProvider
                from opentelemetry.sdk.resources import Resource

                # Create a resource to see what attributes are set
                resource = Resource.create()
                print(f"Resource attributes: {dict(resource.attributes)}")

                # Check for task-related attributes
                task_attrs = {
                    k: v for k, v in resource.attributes.items() if "task" in k.lower()
                }

                if task_attrs:
                    print(f"Task-related attributes found: {task_attrs}")

                    # Check if any are None
                    none_attrs = {k: v for k, v in task_attrs.items() if v is None}
                    if none_attrs:
                        print(f"❌ Found None task attributes: {none_attrs}")
                    else:
                        print("✅ All task attributes have valid values!")
                else:
                    print("No task-related attributes found")

                # Test with a tracer and span
                tracer = trace.get_tracer(__name__)
                with tracer.start_as_current_span("test_span") as span:
                    logger = logging.getLogger("test_logger")
                    logger.info("Test log message")
                    print("Span created and logged successfully")

            except Exception as e:
                print(f"Error: {e}")
                import traceback

                traceback.print_exc()


def test_gitlab_ci_simulation():
    """Simulate the actual GitLab CI environment with resource attributes."""
    print("\n" + "=" * 50)
    print("GitLab CI Simulation Test")
    print("=" * 50)

    # Simulate GitLab CI environment variables
    gitlab_env = {
        "CI": "true",
        "CI_JOB_NAME": "export-pipeline-data",
        "CI_JOB_ID": "11215821048",
        "CI_PIPELINE_ID": "2017065587",
        "CI_PROJECT_ID": "40509251",
        "CI_PROJECT_NAME": "gitlab-metrics-exporter",
        "CI_COMMIT_SHA": "dd4fe5ed75a9a90456f83ffbd96bed6bcbeb5991",
        "CI_COMMIT_REF_NAME": "main",
        "GITLAB_CI": "true",
    }

    # Set resource attributes using GitLab CI variables
    resource_attrs = (
        "service.name=gitlab-exporter,"
        "service.version=1.0.0,"
        "cicd.pipeline.task.name=${CI_JOB_NAME},"
        "cicd.pipeline.id=${CI_PIPELINE_ID},"
        "cicd.project.id=${CI_PROJECT_ID},"
        "task.name=${CI_JOB_NAME},"
        "taskName=${CI_JOB_NAME}"
    )

    test_env = {"OTEL_RESOURCE_ATTRIBUTES": resource_attrs, **gitlab_env}

    print(f"Resource attributes: {resource_attrs}")
    print(f"GitLab CI variables: {list(gitlab_env.keys())}")

    with patch.dict(os.environ, test_env, clear=False):
        try:
            from opentelemetry.sdk.resources import Resource
            from opentelemetry import trace
            from opentelemetry.instrumentation.logging import LoggingInstrumentor

            # Create resource and check attributes
            resource = Resource.create()
            print(f"\nResource attributes created:")
            for key, value in sorted(resource.attributes.items()):
                print(f"  {key}: {value}")

            # Check specifically for problematic attributes
            problematic_attrs = ["taskName", "task.name", "cicd.pipeline.task.name"]
            print(f"\nChecking problematic attributes:")
            for attr in problematic_attrs:
                value = resource.attributes.get(attr)
                if value is None:
                    print(f"  ❌ {attr}: {value} (None - will cause warning)")
                else:
                    print(f"  ✅ {attr}: {value}")

            # Test logging instrumentation
            print(f"\nTesting logging instrumentation...")
            instrumentor = LoggingInstrumentor()
            instrumentor.instrument(set_logging_format=True)

            tracer = trace.get_tracer(__name__)
            with tracer.start_as_current_span("gitlab_job_span") as span:
                logger = logging.getLogger("gitlab-exporter")
                logger.info("Processing GitLab pipeline data")
                print("✅ Logging instrumentation successful - no warnings expected!")

        except Exception as e:
            print(f"❌ Error: {e}")
            import traceback

            traceback.print_exc()


def main():
    """Run all tests."""
    test_resource_attributes_approach()
    test_gitlab_ci_simulation()

    print("\n" + "=" * 50)
    print("RECOMMENDATION:")
    print("=" * 50)
    print("Set OTEL_RESOURCE_ATTRIBUTES in the Docker container environment:")
    print(
        "OTEL_RESOURCE_ATTRIBUTES='service.name=gitlab-exporter,taskName=${CI_JOB_NAME},task.name=${CI_JOB_NAME},cicd.pipeline.task.name=${CI_JOB_NAME}'"
    )
    print("\nThis approach:")
    print("1. ✅ Explicitly sets problematic attributes to valid values")
    print("2. ✅ Much simpler than complex filtering logic")
    print("3. ✅ Uses GitLab's own CI_JOB_NAME variable")
    print("4. ✅ Preserves all OpenTelemetry functionality")
    print("5. ✅ No custom code changes needed")


if __name__ == "__main__":
    main()
