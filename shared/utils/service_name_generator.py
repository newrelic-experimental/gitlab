"""
Service name generation utilities for GitLab New Relic Exporters.

This module provides utilities to generate service names based on GitLab project
information and configuration settings.
"""

import re
from typing import Optional
from shared.config.settings import GitLabConfig


def generate_service_name(project, config: GitLabConfig) -> str:
    """
    Generate a service name based on project information and configuration.

    Args:
        project: GitLab project object with attributes
        config: GitLab configuration instance

    Returns:
        str: Generated service name
    """
    if config.take_namespace_slug:
        # Use path_with_namespace (slug format) instead of name_with_namespace
        service_name = str(project.attributes.get("path_with_namespace", ""))
        if not service_name:
            # Fallback to name_with_namespace if path_with_namespace is not available
            service_name = str(project.attributes.get("name_with_namespace", ""))
            service_name = _convert_to_slug_format(service_name)
    else:
        # Use the original behavior: name_with_namespace with spaces removed
        service_name = str(project.attributes.get("name_with_namespace", ""))
        service_name = service_name.lower().replace(" ", "")

    return service_name


def _convert_to_slug_format(name_with_namespace: str) -> str:
    """
    Convert a name_with_namespace to slug format.

    This function converts display names with special characters and spaces
    to a slug-like format similar to GitLab's path_with_namespace.

    Args:
        name_with_namespace: The display name with namespace

    Returns:
        str: Slug-formatted name
    """
    # Convert to lowercase
    slug = name_with_namespace.lower()

    # Replace spaces and special characters with hyphens
    slug = re.sub(r"[^a-z0-9/]", "-", slug)

    # Remove multiple consecutive hyphens
    slug = re.sub(r"-+", "-", slug)

    # Remove leading/trailing hyphens from each path segment
    segments = slug.split("/")
    segments = [segment.strip("-") for segment in segments if segment.strip("-")]

    return "/".join(segments)


def get_legacy_service_name(project) -> str:
    """
    Get the legacy service name format for backward compatibility.

    Args:
        project: GitLab project object with attributes

    Returns:
        str: Legacy formatted service name
    """
    return (
        str(project.attributes.get("name_with_namespace", "")).lower().replace(" ", "")
    )
