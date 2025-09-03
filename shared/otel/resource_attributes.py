"""
OpenTelemetry resource attributes configuration.

This module provides functionality to programmatically set OTEL_RESOURCE_ATTRIBUTES
to prevent taskName warnings by explicitly setting problematic attributes to valid values.
"""

import os


def set_otel_resource_attributes():
    """
    Set OTEL_RESOURCE_ATTRIBUTES and fix problematic environment variables to prevent taskName warnings.

    This function programmatically sets or merges OTEL_RESOURCE_ATTRIBUTES environment variable
    to explicitly define problematic attributes (like taskName) with valid values,
    preventing OpenTelemetry from trying to auto-detect them and getting None values.

    Additionally, it explicitly sets problematic environment variables that OpenTelemetry
    might auto-detect to valid values.

    The function:
    1. Preserves any existing OTEL_RESOURCE_ATTRIBUTES set by users
    2. Adds our taskName fix attributes
    3. Uses GitLab CI environment variables when available
    4. Falls back to sensible defaults for local development
    5. Explicitly sets problematic environment variables to prevent None value detection
    """
    # Get CI job name, fallback to a default value
    ci_job_name = os.environ.get("CI_JOB_NAME", "gitlab-exporter")
    ci_pipeline_id = os.environ.get("CI_PIPELINE_ID", "unknown")
    ci_project_id = os.environ.get("CI_PROJECT_ID", "unknown")

    # CRITICAL: Set problematic environment variables to valid values
    # This prevents OpenTelemetry from auto-detecting them as None
    problematic_vars = {
        "taskName": ci_job_name,
        "task.name": ci_job_name,
        "job.name": ci_job_name,
        "pipeline.name": f"pipeline-{ci_pipeline_id}",
    }

    for var_name, var_value in problematic_vars.items():
        # Only set if not already set or if currently None
        current_value = os.environ.get(var_name)
        if current_value is None or current_value == "None":
            os.environ[var_name] = var_value
            print(f"Set environment variable {var_name}={var_value}")

    # Get existing OTEL_RESOURCE_ATTRIBUTES if any
    existing_attrs = os.environ.get("OTEL_RESOURCE_ATTRIBUTES", "")

    # Build our taskName fix attributes
    fix_attributes = [
        f"taskName={ci_job_name}",
        f"task.name={ci_job_name}",
        f"cicd.pipeline.task.name={ci_job_name}",
        f"cicd.pipeline.id={ci_pipeline_id}",
        f"cicd.project.id={ci_project_id}",
    ]

    # Add default service attributes if not already present in existing config
    default_attributes = [
        "service.name=gitlab-exporter",
        "service.version=1.0.0",
    ]

    # Parse existing attributes and build final merged attributes
    final_attributes_dict = {}

    # Start with existing attributes if any
    if existing_attrs:
        for attr in existing_attrs.split(","):
            if "=" in attr:
                key, value = attr.split("=", 1)  # Split only on first =
                key = key.strip()
                value = value.strip()
                final_attributes_dict[key] = value

    # Add default attributes only if user doesn't have any service.* attributes
    has_service_attrs = any(
        key.startswith("service.") for key in final_attributes_dict.keys()
    )

    if not has_service_attrs:
        # User has no service attributes, add our defaults
        for attr in default_attributes:
            key, value = attr.split("=", 1)
            final_attributes_dict[key] = value
    # If user has service attributes, respect their configuration completely

    # Always add our taskName fix attributes (these override any existing taskName settings)
    for attr in fix_attributes:
        key, value = attr.split("=", 1)
        final_attributes_dict[key] = value

    # Convert back to comma-separated string
    final_attributes = [
        f"{key}={value}" for key, value in final_attributes_dict.items()
    ]

    # Set the merged environment variable
    otel_resource_attrs = ",".join(final_attributes)
    os.environ["OTEL_RESOURCE_ATTRIBUTES"] = otel_resource_attrs

    if existing_attrs:
        print(f"Merged existing OTEL_RESOURCE_ATTRIBUTES with taskName fix")
        print(f"Original: {existing_attrs}")
        print(f"Final: {otel_resource_attrs}")
    else:
        print(f"Set OTEL_RESOURCE_ATTRIBUTES: {otel_resource_attrs}")

    print("OpenTelemetry taskName warnings should now be prevented")


def get_current_resource_attributes():
    """
    Get the current OTEL_RESOURCE_ATTRIBUTES value.

    Returns:
        str: Current OTEL_RESOURCE_ATTRIBUTES value or empty string if not set
    """
    return os.environ.get("OTEL_RESOURCE_ATTRIBUTES", "")


def is_resource_attributes_configured():
    """
    Check if OTEL_RESOURCE_ATTRIBUTES is already configured.

    Returns:
        bool: True if OTEL_RESOURCE_ATTRIBUTES is set, False otherwise
    """
    return bool(os.environ.get("OTEL_RESOURCE_ATTRIBUTES"))
