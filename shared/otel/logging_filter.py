"""
OpenTelemetry logging filter to prevent None attribute warnings.

This module provides filtering functionality to prevent OpenTelemetry from
setting span attributes with None values, which causes warnings like:
"Invalid type NoneType for attribute 'taskName' value"
"""

import logging
import os
from opentelemetry.instrumentation.logging import LoggingInstrumentor


class FilteredLoggingInstrumentor(LoggingInstrumentor):
    """
    Custom LoggingInstrumentor that filters out None values from span attributes.

    This prevents the "Invalid type NoneType for attribute value" warnings
    that occur when OpenTelemetry automatically injects CICD attributes with None values.
    """

    @staticmethod
    def _get_filtered_attributes():
        """
        Get environment variables filtered to remove None values and problematic attributes.

        Returns:
            dict: Filtered environment variables safe for OpenTelemetry
        """
        # Get all environment variables
        env_vars = dict(os.environ)

        # Remove attributes that commonly have None values or cause issues
        problematic_attrs = [
            "TASK_NAME",
            "CICD_PIPELINE_TASK_NAME",
            "CI_PIPELINE_TASK_NAME",
            "taskName",
            "task_name",
        ]

        # Filter out problematic attributes and None values
        filtered_vars = {}
        for key, value in env_vars.items():
            # Skip if key is in problematic list
            if key in problematic_attrs:
                continue

            # Skip if value is None or empty
            if value is None or value == "" or value == "None":
                continue

            filtered_vars[key] = value

        return filtered_vars

    def _instrument(self, **kwargs):
        """
        Override the instrument method to add filtering.
        """
        # Store original environment
        original_env = dict(os.environ)

        try:
            # Temporarily filter environment variables
            filtered_env = self._get_filtered_attributes()

            # Clear problematic environment variables during instrumentation
            problematic_attrs = [
                "TASK_NAME",
                "CICD_PIPELINE_TASK_NAME",
                "CI_PIPELINE_TASK_NAME",
            ]

            for attr in problematic_attrs:
                if attr in os.environ:
                    del os.environ[attr]

            # Call parent instrumentation
            super()._instrument(**kwargs)

        finally:
            # Restore original environment
            os.environ.clear()
            os.environ.update(original_env)


def instrument_logging_with_filtering(**kwargs):
    """
    Instrument logging with OpenTelemetry while filtering out problematic attributes.

    Args:
        **kwargs: Arguments to pass to LoggingInstrumentor
    """
    instrumentor = FilteredLoggingInstrumentor()
    instrumentor.instrument(**kwargs)
    return instrumentor
