"""
Shared utilities for GitLab New Relic Exporters.
"""

from .service_name_generator import generate_service_name, get_legacy_service_name

__all__ = ["generate_service_name", "get_legacy_service_name"]
