"""
GitLab New Relic Exporter Package.

This package provides functionality to export GitLab CI/CD pipeline data
to New Relic using OpenTelemetry.
"""

from .main import main

__version__ = "1.0.0"
__all__ = ["main"]
