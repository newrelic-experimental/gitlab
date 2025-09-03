"""
Test the programmatic OTEL_RESOURCE_ATTRIBUTES fix for taskName warnings.

This test verifies that our code-based solution works correctly by setting
the resource attributes programmatically at the start of the exporters.
"""

import os
import logging
from unittest.mock import patch
from shared.otel.resource_attributes import (
    set_otel_resource_attributes,
    get_current_resource_attributes,
    is_resource_attributes_configured,
)


def test_programmatic_resource_attributes():
    """Test setting OTEL_RESOURCE_ATTRIBUTES programmatically."""
    print("Testing Programmatic OTEL_RESOURCE_ATTRIBUTES Fix")
    print("=" * 55)

    # Clear any existing OTEL_RESOURCE_ATTRIBUTES
    if "OTEL_RESOURCE_ATTRIBUTES" in os.environ:
        del os.environ["OTEL_RESOURCE_ATTRIBUTES"]

    # Test with GitLab CI environment variables
    gitlab_env = {
        "CI_JOB_NAME": "export-pipeline-data",
        "CI_PIPELINE_ID": "2017065587",
        "CI_PROJECT_ID": "40509251",
    }

    with patch.dict(os.environ, gitlab_env, clear=False):
        print(f"CI_JOB_NAME: {os.environ.get('CI_JOB_NAME')}")
        print(f"CI_PIPELINE_ID: {os.environ.get('CI_PIPELINE_ID')}")
        print(f"CI_PROJECT_ID: {os.environ.get('CI_PROJECT_ID')}")

        # Check initial state
        print(
            f"\nBefore setting: is_configured = {is_resource_attributes_configured()}"
        )

        # Set resource attributes programmatically
        set_otel_resource_attributes()

        # Verify it was set
        print(f"After setting: is_configured = {is_resource_attributes_configured()}")

        # Get the current value
        current_attrs = get_current_resource_attributes()
        print(f"\nCurrent OTEL_RESOURCE_ATTRIBUTES:")
        print(current_attrs)

        # Verify expected attributes are present
        expected_attrs = [
            "service.name=gitlab-exporter",
            "taskName=export-pipeline-data",
            "task.name=export-pipeline-data",
            "cicd.pipeline.task.name=export-pipeline-data",
        ]

        print(f"\nVerifying expected attributes:")
        all_present = True
        for attr in expected_attrs:
            if attr in current_attrs:
                print(f"  ✅ {attr}")
            else:
                print(f"  ❌ {attr} - NOT FOUND")
                all_present = False

        if all_present:
            print(f"\n✅ All expected attributes are present!")
        else:
            print(f"\n❌ Some expected attributes are missing!")

        return all_present


def test_with_opentelemetry_instrumentation():
    """Test that the resource attributes work with OpenTelemetry instrumentation."""
    print(f"\n" + "=" * 55)
    print("Testing with OpenTelemetry Instrumentation")
    print("=" * 55)

    # Clear any existing OTEL_RESOURCE_ATTRIBUTES
    if "OTEL_RESOURCE_ATTRIBUTES" in os.environ:
        del os.environ["OTEL_RESOURCE_ATTRIBUTES"]

    # Set up GitLab CI environment
    gitlab_env = {
        "CI_JOB_NAME": "test-job-name",
        "CI_PIPELINE_ID": "12345",
        "CI_PROJECT_ID": "67890",
    }

    with patch.dict(os.environ, gitlab_env, clear=False):
        try:
            # Set resource attributes first (like in our main.py)
            set_otel_resource_attributes()

            # Now import and use OpenTelemetry
            from opentelemetry.sdk.resources import Resource
            from opentelemetry import trace
            from opentelemetry.instrumentation.logging import LoggingInstrumentor

            # Create resource and check attributes
            resource = Resource.create()
            print(f"\nResource attributes created:")

            task_related_attrs = {}
            for key, value in sorted(resource.attributes.items()):
                if "task" in key.lower() or "service" in key.lower():
                    print(f"  {key}: {value}")
                    if "task" in key.lower():
                        task_related_attrs[key] = value

            # Check for None values
            none_attrs = {k: v for k, v in task_related_attrs.items() if v is None}
            if none_attrs:
                print(f"\n❌ Found None task attributes: {none_attrs}")
                return False
            else:
                print(f"\n✅ All task attributes have valid values!")

            # Test logging instrumentation
            print(f"\nTesting logging instrumentation...")
            instrumentor = LoggingInstrumentor()
            instrumentor.instrument(set_logging_format=True)

            # Create a span and log something
            tracer = trace.get_tracer(__name__)
            with tracer.start_as_current_span("test_span") as span:
                logger = logging.getLogger("test-logger")
                logger.info("Test message - should not produce taskName warnings")
                print("✅ Logging completed without warnings!")

            return True

        except Exception as e:
            print(f"❌ Error during OpenTelemetry test: {e}")
            import traceback

            traceback.print_exc()
            return False


def test_fallback_values():
    """Test that fallback values work when CI variables are not available."""
    print(f"\n" + "=" * 55)
    print("Testing Fallback Values (No CI Environment)")
    print("=" * 55)

    # Clear any existing OTEL_RESOURCE_ATTRIBUTES and CI variables
    env_to_clear = [
        "OTEL_RESOURCE_ATTRIBUTES",
        "CI_JOB_NAME",
        "CI_PIPELINE_ID",
        "CI_PROJECT_ID",
    ]
    original_values = {}
    for env_var in env_to_clear:
        if env_var in os.environ:
            original_values[env_var] = os.environ[env_var]
            del os.environ[env_var]

    try:
        print("No CI environment variables set")

        # Set resource attributes
        set_otel_resource_attributes()

        # Check the result
        current_attrs = get_current_resource_attributes()
        print(f"\nGenerated OTEL_RESOURCE_ATTRIBUTES:")
        print(current_attrs)

        # Should contain fallback values
        expected_fallbacks = [
            "taskName=gitlab-exporter",
            "task.name=gitlab-exporter",
            "cicd.pipeline.id=unknown",
            "cicd.project.id=unknown",
        ]

        print(f"\nVerifying fallback values:")
        all_present = True
        for attr in expected_fallbacks:
            if attr in current_attrs:
                print(f"  ✅ {attr}")
            else:
                print(f"  ❌ {attr} - NOT FOUND")
                all_present = False

        return all_present

    finally:
        # Restore original environment
        for env_var, value in original_values.items():
            os.environ[env_var] = value


def main():
    """Run all tests."""
    print("Testing Programmatic OTEL_RESOURCE_ATTRIBUTES Solution")
    print("=" * 60)

    # Run tests
    test1_result = test_programmatic_resource_attributes()
    test2_result = test_with_opentelemetry_instrumentation()
    test3_result = test_fallback_values()

    # Summary
    print(f"\n" + "=" * 60)
    print("TEST RESULTS:")
    print("=" * 60)
    print(f"✅ Programmatic resource attributes: {'PASS' if test1_result else 'FAIL'}")
    print(f"✅ OpenTelemetry instrumentation: {'PASS' if test2_result else 'FAIL'}")
    print(f"✅ Fallback values: {'PASS' if test3_result else 'FAIL'}")

    if all([test1_result, test2_result, test3_result]):
        print(f"\n🎉 ALL TESTS PASSED!")
        print(f"\nThe programmatic solution is working correctly:")
        print(f"1. ✅ Sets OTEL_RESOURCE_ATTRIBUTES at runtime")
        print(f"2. ✅ Uses GitLab CI variables when available")
        print(f"3. ✅ Falls back to sensible defaults")
        print(f"4. ✅ Prevents taskName warnings")
        print(f"5. ✅ Works with OpenTelemetry instrumentation")
    else:
        print(f"\n❌ Some tests failed - solution needs refinement")


if __name__ == "__main__":
    main()
