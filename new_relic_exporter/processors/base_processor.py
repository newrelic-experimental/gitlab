"""
Base processor class for GitLab New Relic Exporter.

Provides common functionality and interface for all processors.
"""

from abc import ABC, abstractmethod
from typing import Dict, Any, List
from opentelemetry.sdk.resources import Resource
from shared.config.settings import GitLabConfig


class BaseProcessor(ABC):
    """
    Abstract base class for all GitLab entity processors.

    Provides common functionality like configuration access,
    resource creation, and attribute parsing.
    """

    def __init__(self, config: GitLabConfig):
        """
        Initialize the processor with configuration.

        Args:
            config: GitLab configuration instance
        """
        self.config = config
        self.service_name = config.service_name

    def create_resource_attributes(
        self, base_attributes: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Create standardized resource attributes for OpenTelemetry.

        Args:
            base_attributes: Base attributes to extend

        Returns:
            Dictionary of resource attributes
        """
        attributes = {
            "instrumentation.name": "gitlab-integration",
            "gitlab.source": "gitlab-exporter",
            "service.name": self.service_name,
        }
        attributes.update(base_attributes)
        return attributes

    def should_exclude_item(
        self, item_name: str, item_stage: str, exclude_list: List[str]
    ) -> bool:
        """
        Check if an item should be excluded based on name or stage.

        Args:
            item_name: Name of the item (job/bridge)
            item_stage: Stage of the item
            exclude_list: List of items to exclude

        Returns:
            True if item should be excluded, False otherwise
        """
        # Always exclude exporter stages
        if item_stage.lower() in ["new-relic-exporter", "new-relic-metrics-exporter"]:
            return True

        # Check against exclude list
        return item_name.lower() in exclude_list or item_stage.lower() in exclude_list

    @abstractmethod
    def process(self, *args, **kwargs) -> Any:
        """
        Abstract method that must be implemented by concrete processors.

        Each processor should implement its specific processing logic here.
        """
        pass
