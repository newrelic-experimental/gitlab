"""
OpenTelemetry span attribute filter to prevent taskName warnings.

This module provides a wrapper around OpenTelemetry spans to filter out
problematic attributes like 'taskName' that cause None value warnings.
"""

from typing import Dict, Any, Optional
from opentelemetry.trace import Span
from opentelemetry.util.types import AttributeValue


class FilteredSpan:
    """
    Wrapper around OpenTelemetry Span that filters out problematic attributes.

    This prevents warnings like "Invalid type NoneType for attribute 'taskName' value"
    by filtering out None values and known problematic attributes before they reach
    the OpenTelemetry SDK.
    """

    def __init__(self, span: Span):
        """
        Initialize the filtered span wrapper.

        Args:
            span: The OpenTelemetry span to wrap
        """
        self._span = span
        self._problematic_attrs = {
            "taskName",
            "task_name",
            "TASK_NAME",
            "CICD_PIPELINE_TASK_NAME",
            "CI_PIPELINE_TASK_NAME",
            "CI_PIPELINE_TASK_NAME",
        }

    def _filter_attributes(
        self, attributes: Dict[str, AttributeValue]
    ) -> Dict[str, AttributeValue]:
        """
        Filter out problematic attributes and None values.

        Args:
            attributes: Dictionary of attributes to filter

        Returns:
            Filtered dictionary with problematic attributes removed
        """
        if not attributes:
            return {}

        filtered = {}
        for key, value in attributes.items():
            # Skip problematic attribute names
            if key in self._problematic_attrs:
                continue

            # Skip None values
            if value is None:
                continue

            # Skip empty strings that might become None
            if isinstance(value, str) and (value == "" or value == "None"):
                continue

            filtered[key] = value

        return filtered

    def set_attribute(self, key: str, value: AttributeValue) -> None:
        """
        Set a single attribute on the span, filtering out problematic ones.

        Args:
            key: Attribute key
            value: Attribute value
        """
        # Filter the single attribute
        filtered = self._filter_attributes({key: value})
        if filtered:
            self._span.set_attribute(key, value)

    def set_attributes(self, attributes: Dict[str, AttributeValue]) -> None:
        """
        Set multiple attributes on the span, filtering out problematic ones.

        Args:
            attributes: Dictionary of attributes to set
        """
        filtered = self._filter_attributes(attributes)
        if filtered:
            self._span.set_attributes(filtered)

    def __getattr__(self, name):
        """
        Delegate all other method calls to the wrapped span.

        Args:
            name: Method name

        Returns:
            Method from the wrapped span
        """
        return getattr(self._span, name)


def create_filtered_span(span: Span) -> FilteredSpan:
    """
    Create a filtered span wrapper.

    Args:
        span: OpenTelemetry span to wrap

    Returns:
        FilteredSpan wrapper
    """
    return FilteredSpan(span)


def patch_span_creation():
    """
    Monkey patch OpenTelemetry span creation to use filtered spans.

    This should be called early in the application lifecycle to ensure
    all spans are created with filtering enabled.
    """
    try:
        from opentelemetry.sdk.trace import Tracer

        # Store original start_span method
        original_start_span = Tracer.start_span

        def filtered_start_span(
            self,
            name,
            context=None,
            kind=None,
            attributes=None,
            links=None,
            start_time=None,
            record_exception=True,
            set_status_on_exception=True,
        ):
            """
            Patched start_span method that returns a filtered span.
            """
            # Create the original span
            span = original_start_span(
                self,
                name,
                context,
                kind,
                attributes,
                links,
                start_time,
                record_exception,
                set_status_on_exception,
            )

            # Return a filtered wrapper
            return create_filtered_span(span)

        # Apply the patch
        Tracer.start_span = filtered_start_span

        print("OpenTelemetry span filtering patch applied successfully")

    except Exception as e:
        print(f"Warning: Could not apply OpenTelemetry span filtering patch: {e}")
