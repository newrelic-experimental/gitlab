"""
Test using OTEL_PYTHON_DISABLED_INSTRUMENTATIONS to prevent taskName warnings.

This approach disables specific OpenTelemetry instrumentations that might be
causing the problematic attribute injection, rather than filtering attributes.
"""

import os
import logging
import sys
from unittest.mock import patch

# Test different combinations of disabled instrumentations
TEST_SCENARIOS = [
    {"name": "Disable logging instrumentation", "disabled": "logging"},
    {"name": "Disable system metrics instrumentation", "disabled": "system-metrics"},
    {"name": "Disable runtime metrics instrumentation", "disabled": "runtime-metrics"},
    {
        "name": "Disable multiple instrumentations",
        "disabled": "logging,system-metrics,runtime-metrics",
    },
    {"name": "Disable all auto instrumentations", "disabled": "all"},
]


def test_scenario(scenario):
    """Test a specific OTEL_PYTHON_DISABLED_INSTRUMENTATIONS scenario."""
    print(f"\n=== Testing: {scenario['name']} ===")
    print(f"OTEL_PYTHON_DISABLED_INSTRUMENTATIONS={scenario['disabled']}")

    # Set the environment variable
    os.environ["OTEL_PYTHON_DISABLED_INSTRUMENTATIONS"] = scenario["disabled"]

    # Mock problematic environment variables that cause taskName warnings
    test_env = {
        "TASK_NAME": "",
        "CI_TASK_NAME": "",
        "taskName": "",
        "CI_JOB_NAME": "test-job",
        "CI_PIPELINE_ID": "12345",
    }

    with patch.dict(os.environ, test_env):
        try:
            # Import and initialize OpenTelemetry after setting the disabled instrumentations
            from opentelemetry import trace
            from opentelemetry.instrumentation.auto_instrumentation import sitecustomize

            # Create a tracer and span to test attribute injection
            tracer = trace.get_tracer(__name__)

            with tracer.start_as_current_span("test_span") as span:
                # Try to log something that might trigger attribute injection
                logger = logging.getLogger("test_logger")
                logger.info("Test log message")

                # Check what attributes are on the span
                if hasattr(span, "_attributes"):
                    print(f"Span attributes: {span._attributes}")

                    # Check for problematic attributes
                    problematic_found = False
                    for attr_name in span._attributes:
                        if (
                            "task" in attr_name.lower()
                            and span._attributes[attr_name] is None
                        ):
                            print(
                                f"WARNING: Found problematic attribute: {attr_name} = {span._attributes[attr_name]}"
                            )
                            problematic_found = True

                    if not problematic_found:
                        print("✅ No problematic taskName attributes found!")
                else:
                    print("No span attributes found")

        except Exception as e:
            print(f"Error during test: {e}")
            import traceback

            traceback.print_exc()

    # Clean up
    if "OTEL_PYTHON_DISABLED_INSTRUMENTATIONS" in os.environ:
        del os.environ["OTEL_PYTHON_DISABLED_INSTRUMENTATIONS"]


def test_simple_disable_logging():
    """Test the simplest approach - just disable logging instrumentation."""
    print("\n=== Simple Test: Disable Logging Instrumentation ===")

    # Set environment variable to disable logging instrumentation
    os.environ["OTEL_PYTHON_DISABLED_INSTRUMENTATIONS"] = "logging"

    # Mock the problematic environment
    problematic_env = {"TASK_NAME": "", "CI_TASK_NAME": "", "taskName": ""}

    with patch.dict(os.environ, problematic_env):
        try:
            # Import OpenTelemetry components
            from opentelemetry.instrumentation.logging import LoggingInstrumentor

            # Try to instrument logging - should be disabled
            instrumentor = LoggingInstrumentor()
            print(f"LoggingInstrumentor available: {instrumentor is not None}")

            # Check if instrumentation is actually disabled
            if hasattr(instrumentor, "_is_instrumented_by_opentelemetry"):
                print(
                    f"Is instrumented: {instrumentor._is_instrumented_by_opentelemetry}"
                )

            # Try to instrument anyway and see what happens
            try:
                instrumentor.instrument()
                print("Instrumentation succeeded (or was already done)")
            except Exception as e:
                print(f"Instrumentation failed/disabled: {e}")

        except ImportError as e:
            print(f"Import error: {e}")
        except Exception as e:
            print(f"Other error: {e}")
            import traceback

            traceback.print_exc()


def main():
    """Run all test scenarios."""
    print("Testing OTEL_PYTHON_DISABLED_INSTRUMENTATIONS approach")
    print("=" * 60)

    # Test simple approach first
    test_simple_disable_logging()

    # Test various scenarios
    for scenario in TEST_SCENARIOS:
        test_scenario(scenario)

    print("\n" + "=" * 60)
    print("Testing complete!")

    print("\nRecommendation:")
    print("If disabling 'logging' instrumentation eliminates the warnings,")
    print("we can simply set OTEL_PYTHON_DISABLED_INSTRUMENTATIONS=logging")
    print("in the Docker container environment instead of our complex filtering.")


if __name__ == "__main__":
    main()
