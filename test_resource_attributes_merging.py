"""
Test OTEL_RESOURCE_ATTRIBUTES merging functionality.

This test verifies that our solution correctly merges existing user-configured
OTEL_RESOURCE_ATTRIBUTES with our taskName fix, preserving user settings while
preventing taskName warnings.
"""

import os
from unittest.mock import patch
from shared.otel.resource_attributes import (
    set_otel_resource_attributes,
    get_current_resource_attributes,
)


def test_no_existing_attributes():
    """Test behavior when no OTEL_RESOURCE_ATTRIBUTES are pre-configured."""
    print("Test 1: No existing OTEL_RESOURCE_ATTRIBUTES")
    print("=" * 50)

    # Clear any existing attributes
    if "OTEL_RESOURCE_ATTRIBUTES" in os.environ:
        del os.environ["OTEL_RESOURCE_ATTRIBUTES"]

    gitlab_env = {
        "CI_JOB_NAME": "test-job",
        "CI_PIPELINE_ID": "12345",
        "CI_PROJECT_ID": "67890",
    }

    with patch.dict(os.environ, gitlab_env, clear=False):
        set_otel_resource_attributes()

        result = get_current_resource_attributes()
        print(f"Result: {result}")

        # Should contain our defaults and fix attributes
        expected_parts = [
            "service.name=gitlab-exporter",
            "service.version=1.0.0",
            "taskName=test-job",
            "task.name=test-job",
            "cicd.pipeline.task.name=test-job",
        ]

        success = all(part in result for part in expected_parts)
        print(f"✅ Contains all expected attributes: {success}")
        return success


def test_existing_user_attributes():
    """Test merging with existing user-configured attributes."""
    print("\nTest 2: Existing user OTEL_RESOURCE_ATTRIBUTES")
    print("=" * 50)

    # Set up existing user configuration
    user_config = "service.name=my-custom-service,deployment.environment=production,custom.attribute=value123"

    gitlab_env = {
        "OTEL_RESOURCE_ATTRIBUTES": user_config,
        "CI_JOB_NAME": "deploy-job",
        "CI_PIPELINE_ID": "98765",
        "CI_PROJECT_ID": "54321",
    }

    with patch.dict(os.environ, gitlab_env, clear=False):
        set_otel_resource_attributes()

        result = get_current_resource_attributes()
        print(f"Result: {result}")

        # Should preserve user attributes and add our fix
        user_parts = [
            "service.name=my-custom-service",
            "deployment.environment=production",
            "custom.attribute=value123",
        ]
        fix_parts = [
            "taskName=deploy-job",
            "task.name=deploy-job",
            "cicd.pipeline.task.name=deploy-job",
        ]

        user_preserved = all(part in result for part in user_parts)
        fix_added = all(part in result for part in fix_parts)

        print(f"✅ User attributes preserved: {user_preserved}")
        print(f"✅ TaskName fix added: {fix_added}")

        # Should NOT add default service.version since user already has service.name
        should_not_have_default_version = "service.version=1.0.0" not in result
        print(
            f"✅ Didn't override user service config: {should_not_have_default_version}"
        )

        return user_preserved and fix_added and should_not_have_default_version


def test_existing_partial_attributes():
    """Test merging when user has some but not all default attributes."""
    print("\nTest 3: Partial existing OTEL_RESOURCE_ATTRIBUTES")
    print("=" * 50)

    # User has custom attributes but no service name
    user_config = "deployment.environment=staging,team=backend"

    gitlab_env = {
        "OTEL_RESOURCE_ATTRIBUTES": user_config,
        "CI_JOB_NAME": "integration-test",
        "CI_PIPELINE_ID": "11111",
        "CI_PROJECT_ID": "22222",
    }

    with patch.dict(os.environ, gitlab_env, clear=False):
        set_otel_resource_attributes()

        result = get_current_resource_attributes()
        print(f"Result: {result}")

        # Should preserve user attributes
        user_parts = ["deployment.environment=staging", "team=backend"]
        user_preserved = all(part in result for part in user_parts)

        # Should add our defaults since user doesn't have service.name
        default_parts = ["service.name=gitlab-exporter", "service.version=1.0.0"]
        defaults_added = all(part in result for part in default_parts)

        # Should add our fix
        fix_parts = ["taskName=integration-test", "task.name=integration-test"]
        fix_added = all(part in result for part in fix_parts)

        print(f"✅ User attributes preserved: {user_preserved}")
        print(f"✅ Default attributes added: {defaults_added}")
        print(f"✅ TaskName fix added: {fix_added}")

        return user_preserved and defaults_added and fix_added


def test_existing_conflicting_taskname():
    """Test that our fix overrides existing problematic taskName attributes."""
    print("\nTest 4: Existing conflicting taskName attributes")
    print("=" * 50)

    # User has existing taskName that might be problematic
    user_config = "service.name=user-service,taskName=old-task,task.name=old-name"

    gitlab_env = {
        "OTEL_RESOURCE_ATTRIBUTES": user_config,
        "CI_JOB_NAME": "new-correct-job",
        "CI_PIPELINE_ID": "33333",
        "CI_PROJECT_ID": "44444",
    }

    with patch.dict(os.environ, gitlab_env, clear=False):
        set_otel_resource_attributes()

        result = get_current_resource_attributes()
        print(f"Result: {result}")

        # Should preserve user service name
        user_service_preserved = "service.name=user-service" in result

        # Should override old taskName with new correct one
        new_taskname = "taskName=new-correct-job" in result
        new_task_name = "task.name=new-correct-job" in result
        old_taskname_gone = "taskName=old-task" not in result
        old_task_name_gone = "task.name=old-name" not in result

        print(f"✅ User service name preserved: {user_service_preserved}")
        print(f"✅ New taskName set: {new_taskname}")
        print(f"✅ New task.name set: {new_task_name}")
        print(f"✅ Old taskName removed: {old_taskname_gone}")
        print(f"✅ Old task.name removed: {old_task_name_gone}")

        return all(
            [
                user_service_preserved,
                new_taskname,
                new_task_name,
                old_taskname_gone,
                old_task_name_gone,
            ]
        )


def test_with_opentelemetry():
    """Test that merged attributes work correctly with OpenTelemetry."""
    print("\nTest 5: OpenTelemetry integration with merged attributes")
    print("=" * 50)

    # Clear existing attributes
    if "OTEL_RESOURCE_ATTRIBUTES" in os.environ:
        del os.environ["OTEL_RESOURCE_ATTRIBUTES"]

    # Set up user configuration
    user_config = "service.name=my-app,deployment.environment=production"

    gitlab_env = {
        "OTEL_RESOURCE_ATTRIBUTES": user_config,
        "CI_JOB_NAME": "production-deploy",
        "CI_PIPELINE_ID": "55555",
        "CI_PROJECT_ID": "66666",
    }

    with patch.dict(os.environ, gitlab_env, clear=False):
        try:
            # Set merged attributes
            set_otel_resource_attributes()

            # Test with OpenTelemetry
            from opentelemetry.sdk.resources import Resource

            resource = Resource.create()
            attrs = dict(resource.attributes)

            print(f"OpenTelemetry resource attributes:")
            for key, value in sorted(attrs.items()):
                if not key.startswith("telemetry.sdk"):
                    print(f"  {key}: {value}")

            # Check that user attributes are preserved
            user_preserved = (
                attrs.get("service.name") == "my-app"
                and attrs.get("deployment.environment") == "production"
            )

            # Check that our fix is applied
            fix_applied = (
                attrs.get("taskName") == "production-deploy"
                and attrs.get("task.name") == "production-deploy"
                and attrs.get("cicd.pipeline.task.name") == "production-deploy"
            )

            # Check no None values in task attributes
            task_attrs = {k: v for k, v in attrs.items() if "task" in k.lower()}
            no_none_values = all(v is not None for v in task_attrs.values())

            print(f"✅ User attributes preserved: {user_preserved}")
            print(f"✅ TaskName fix applied: {fix_applied}")
            print(f"✅ No None task values: {no_none_values}")

            return user_preserved and fix_applied and no_none_values

        except Exception as e:
            print(f"❌ Error: {e}")
            return False


def main():
    """Run all merging tests."""
    print("Testing OTEL_RESOURCE_ATTRIBUTES Merging Functionality")
    print("=" * 60)

    tests = [
        test_no_existing_attributes,
        test_existing_user_attributes,
        test_existing_partial_attributes,
        test_existing_conflicting_taskname,
        test_with_opentelemetry,
    ]

    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Test failed with error: {e}")
            results.append(False)

    # Summary
    print("\n" + "=" * 60)
    print("TEST RESULTS:")
    print("=" * 60)

    test_names = [
        "No existing attributes",
        "Existing user attributes",
        "Partial existing attributes",
        "Conflicting taskName attributes",
        "OpenTelemetry integration",
    ]

    for i, (name, result) in enumerate(zip(test_names, results), 1):
        status = "PASS" if result else "FAIL"
        print(f"{i}. {name}: {status}")

    all_passed = all(results)
    if all_passed:
        print(f"\n🎉 ALL TESTS PASSED!")
        print(f"\nThe merging functionality works correctly:")
        print(f"✅ Preserves existing user OTEL_RESOURCE_ATTRIBUTES")
        print(f"✅ Adds taskName fix attributes")
        print(f"✅ Handles conflicts appropriately")
        print(f"✅ Works with OpenTelemetry")
        print(f"✅ Prevents taskName warnings")
    else:
        print(f"\n❌ Some tests failed - merging needs refinement")

    return all_passed


if __name__ == "__main__":
    main()
