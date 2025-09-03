"""
Configuration validation utilities for GitLab New Relic Exporters.

This module provides validation functions for configuration settings
and environment setup.
"""

import os
import re
import gitlab
from typing import List, Optional
from urllib.parse import urlparse

from .settings import GitLabConfig


class ConfigurationError(Exception):
    """Raised when configuration validation fails."""

    pass


def validate_gitlab_connection(config: GitLabConfig) -> bool:
    """
    Validate GitLab API connection using the provided configuration.

    Args:
        config: GitLab configuration to validate

    Returns:
        bool: True if connection is successful

    Raises:
        ConfigurationError: If connection fails
    """
    try:
        if config.endpoint == "https://gitlab.com/":
            gl = gitlab.Gitlab(private_token=config.token)
        else:
            gl = gitlab.Gitlab(url=config.endpoint, private_token=config.token)

        # Test the connection by getting current user
        user = gl.user
        if not user:
            raise ConfigurationError("Failed to authenticate with GitLab API")

        return True

    except gitlab.exceptions.GitlabAuthenticationError:
        raise ConfigurationError("GitLab authentication failed. Check your GLAB_TOKEN.")
    except gitlab.exceptions.GitlabError as e:
        raise ConfigurationError(f"GitLab API error: {e}")
    except Exception as e:
        raise ConfigurationError(f"Failed to connect to GitLab: {e}")


def validate_new_relic_endpoint(config: GitLabConfig) -> bool:
    """
    Validate New Relic OTLP endpoint accessibility.

    Args:
        config: Configuration containing New Relic settings

    Returns:
        bool: True if endpoint is accessible

    Raises:
        ConfigurationError: If endpoint validation fails
    """
    import requests

    try:
        # Test basic connectivity to the endpoint
        response = requests.head(
            config.otel_endpoint,
            headers={"api-key": config.new_relic_api_key},
            timeout=10,
        )

        # OTLP endpoints typically return 405 for HEAD requests, which is expected
        if response.status_code in [200, 405, 404]:
            return True
        else:
            raise ConfigurationError(
                f"New Relic endpoint returned unexpected status: {response.status_code}"
            )

    except requests.exceptions.RequestException as e:
        raise ConfigurationError(f"Failed to connect to New Relic endpoint: {e}")


def validate_project_access(config: GitLabConfig) -> bool:
    """
    Validate access to the specified GitLab project.

    Args:
        config: Configuration containing project settings

    Returns:
        bool: True if project is accessible

    Raises:
        ConfigurationError: If project access validation fails
    """
    if not config.project_id:
        # No specific project to validate
        return True

    try:
        if config.endpoint == "https://gitlab.com/":
            gl = gitlab.Gitlab(private_token=config.token)
        else:
            gl = gitlab.Gitlab(url=config.endpoint, private_token=config.token)

        project = gl.projects.get(config.project_id)
        if not project:
            raise ConfigurationError(f"Project {config.project_id} not found")

        return True

    except gitlab.exceptions.GitlabGetError:
        raise ConfigurationError(
            f"Cannot access project {config.project_id}. Check permissions."
        )
    except Exception as e:
        raise ConfigurationError(f"Failed to validate project access: {e}")


def validate_pipeline_access(config: GitLabConfig) -> bool:
    """
    Validate access to the specified pipeline.

    Args:
        config: Configuration containing pipeline settings

    Returns:
        bool: True if pipeline is accessible

    Raises:
        ConfigurationError: If pipeline access validation fails
    """
    if not config.project_id or not config.pipeline_id:
        # No specific pipeline to validate
        return True

    try:
        if config.endpoint == "https://gitlab.com/":
            gl = gitlab.Gitlab(private_token=config.token)
        else:
            gl = gitlab.Gitlab(url=config.endpoint, private_token=config.token)

        project = gl.projects.get(config.project_id)
        pipeline = project.pipelines.get(config.pipeline_id)

        if not pipeline:
            raise ConfigurationError(f"Pipeline {config.pipeline_id} not found")

        return True

    except gitlab.exceptions.GitlabGetError:
        raise ConfigurationError(
            f"Cannot access pipeline {config.pipeline_id}. Check permissions."
        )
    except Exception as e:
        raise ConfigurationError(f"Failed to validate pipeline access: {e}")


def validate_regex_patterns(config: GitLabConfig) -> bool:
    """
    Validate all regex patterns in the configuration.

    Args:
        config: Configuration containing regex patterns

    Returns:
        bool: True if all patterns are valid

    Raises:
        ConfigurationError: If any regex pattern is invalid
    """
    patterns = {
        "export_projects_regex": config.export_projects_regex,
    }

    for name, pattern in patterns.items():
        try:
            re.compile(pattern)
        except re.error as e:
            raise ConfigurationError(f"Invalid regex pattern in {name}: {e}")

    return True


def validate_environment_variables() -> List[str]:
    """
    Validate that all required environment variables are present.

    Returns:
        List[str]: List of missing required variables (empty if all present)
    """
    required_vars = ["GLAB_TOKEN", "NEW_RELIC_API_KEY"]
    missing_vars = []

    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)

    return missing_vars


def validate_ci_environment() -> bool:
    """
    Validate that we're running in a proper CI environment.

    Returns:
        bool: True if CI environment is properly configured

    Raises:
        ConfigurationError: If CI environment is invalid
    """
    ci_vars = ["CI_PROJECT_ID", "CI_PARENT_PIPELINE", "CI_PIPELINE_ID"]
    present_vars = [var for var in ci_vars if os.getenv(var)]

    if not present_vars:
        raise ConfigurationError(
            "No CI environment variables found. This exporter should run in GitLab CI."
        )

    # Check for required CI variables
    if not os.getenv("CI_PROJECT_ID"):
        raise ConfigurationError("CI_PROJECT_ID is required in CI environment")

    if not (os.getenv("CI_PARENT_PIPELINE") or os.getenv("CI_PIPELINE_ID")):
        raise ConfigurationError(
            "Either CI_PARENT_PIPELINE or CI_PIPELINE_ID is required"
        )

    return True


def perform_full_validation(config: GitLabConfig, skip_network: bool = False) -> bool:
    """
    Perform comprehensive validation of the configuration.

    Args:
        config: Configuration to validate
        skip_network: If True, skip network-dependent validations

    Returns:
        bool: True if all validations pass

    Raises:
        ConfigurationError: If any validation fails
    """
    # Validate regex patterns (no network required)
    validate_regex_patterns(config)

    # Validate environment variables
    missing_vars = validate_environment_variables()
    if missing_vars:
        raise ConfigurationError(
            f"Missing required environment variables: {', '.join(missing_vars)}"
        )

    # Skip network-dependent validations if requested
    if skip_network:
        return True

    # Validate GitLab connection
    validate_gitlab_connection(config)

    # Validate New Relic endpoint
    validate_new_relic_endpoint(config)

    # Validate project access if project_id is specified
    if config.project_id:
        validate_project_access(config)

    # Validate pipeline access if pipeline_id is specified
    if config.pipeline_id:
        validate_pipeline_access(config)

    return True


def check_configuration_health(config: GitLabConfig) -> dict:
    """
    Check the health of the configuration and return a status report.

    Args:
        config: Configuration to check

    Returns:
        dict: Health status report with details about each check
    """
    health_report = {
        "overall_status": "healthy",
        "checks": {},
        "warnings": [],
        "errors": [],
    }

    # Check environment variables
    try:
        missing_vars = validate_environment_variables()
        if missing_vars:
            health_report["checks"]["environment"] = "failed"
            health_report["errors"].append(
                f"Missing variables: {', '.join(missing_vars)}"
            )
            health_report["overall_status"] = "unhealthy"
        else:
            health_report["checks"]["environment"] = "passed"
    except Exception as e:
        health_report["checks"]["environment"] = "error"
        health_report["errors"].append(f"Environment check error: {e}")
        health_report["overall_status"] = "unhealthy"

    # Check regex patterns
    try:
        validate_regex_patterns(config)
        health_report["checks"]["regex_patterns"] = "passed"
    except ConfigurationError as e:
        health_report["checks"]["regex_patterns"] = "failed"
        health_report["errors"].append(str(e))
        health_report["overall_status"] = "unhealthy"

    # Check GitLab connection
    try:
        validate_gitlab_connection(config)
        health_report["checks"]["gitlab_connection"] = "passed"
    except ConfigurationError as e:
        health_report["checks"]["gitlab_connection"] = "failed"
        health_report["errors"].append(f"GitLab connection: {e}")
        health_report["overall_status"] = "unhealthy"

    # Check New Relic endpoint
    try:
        validate_new_relic_endpoint(config)
        health_report["checks"]["newrelic_endpoint"] = "passed"
    except ConfigurationError as e:
        health_report["checks"]["newrelic_endpoint"] = "failed"
        health_report["errors"].append(f"New Relic endpoint: {e}")
        health_report["overall_status"] = "unhealthy"

    # Add warnings for potential issues
    if config.low_data_mode:
        health_report["warnings"].append("Running in low data mode - reduced telemetry")

    if not config.export_logs:
        health_report["warnings"].append("Log export is disabled")

    if health_report["warnings"] and health_report["overall_status"] == "healthy":
        health_report["overall_status"] = "healthy_with_warnings"

    return health_report
