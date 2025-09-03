"""
Tests for service name generation utilities.
"""

import pytest
from unittest.mock import MagicMock
from shared.utils.service_name_generator import (
    generate_service_name,
    _convert_to_slug_format,
    get_legacy_service_name,
)
from shared.config.settings import GitLabConfig


class TestServiceNameGenerator:
    """Test cases for service name generation."""

    def test_generate_service_name_with_slug_enabled(self):
        """Test service name generation with slug format enabled."""
        # Mock project with path_with_namespace
        mock_project = MagicMock()
        mock_project.attributes.get.side_effect = lambda key, default="": {
            "path_with_namespace": "main-group/sub-group/my-project",
            "name_with_namespace": "Main Group / Sub Group / My Project",
        }.get(key, default)

        # Mock config with slug enabled
        config = GitLabConfig(
            token="test_token",
            new_relic_api_key="test_key",
            take_namespace_slug=True,
        )

        result = generate_service_name(mock_project, config)
        assert result == "main-group/sub-group/my-project"

    def test_generate_service_name_with_slug_disabled(self):
        """Test service name generation with slug format disabled."""
        # Mock project
        mock_project = MagicMock()
        mock_project.attributes.get.side_effect = lambda key, default="": {
            "name_with_namespace": "Main Group / Sub Group / My Project",
        }.get(key, default)

        # Mock config with slug disabled
        config = GitLabConfig(
            token="test_token",
            new_relic_api_key="test_key",
            take_namespace_slug=False,
        )

        result = generate_service_name(mock_project, config)
        assert result == "maingroup/subgroup/myproject"

    def test_generate_service_name_fallback_to_conversion(self):
        """Test fallback to slug conversion when path_with_namespace is not available."""
        # Mock project without path_with_namespace
        mock_project = MagicMock()
        mock_project.attributes.get.side_effect = lambda key, default="": {
            "name_with_namespace": "Töp Level Group/Secönd Level Group/My Service",
        }.get(key, default)

        # Mock config with slug enabled
        config = GitLabConfig(
            token="test_token",
            new_relic_api_key="test_key",
            take_namespace_slug=True,
        )

        result = generate_service_name(mock_project, config)
        assert result == "t-p-level-group/sec-nd-level-group/my-service"

    def test_convert_to_slug_format(self):
        """Test slug format conversion."""
        test_cases = [
            ("Main Group/Sub Group/My Project", "main-group/sub-group/my-project"),
            (
                "Töp Level Group/Secönd Level Group/My Service",
                "t-p-level-group/sec-nd-level-group/my-service",
            ),
            ("Group With Spaces/Project", "group-with-spaces/project"),
            ("group/project", "group/project"),
            ("Group-With-Hyphens/Project", "group-with-hyphens/project"),
            ("Group__With__Underscores/Project", "group-with-underscores/project"),
        ]

        for input_name, expected_output in test_cases:
            result = _convert_to_slug_format(input_name)
            assert result == expected_output, f"Failed for input: {input_name}"

    def test_get_legacy_service_name(self):
        """Test legacy service name generation."""
        mock_project = MagicMock()
        mock_project.attributes.get.side_effect = lambda key, default="": {
            "name_with_namespace": "Main Group / Sub Group / My Project",
        }.get(key, default)

        result = get_legacy_service_name(mock_project)
        assert result == "maingroup/subgroup/myproject"

    def test_convert_to_slug_format_edge_cases(self):
        """Test slug format conversion with edge cases."""
        test_cases = [
            ("", ""),
            ("Group/", "group"),
            ("/Project", "project"),
            ("Group//Project", "group/project"),
            ("Group---Project/Sub", "group-project/sub"),
            ("Group   Project/Sub", "group-project/sub"),
            ("123Group/456Project", "123group/456project"),
        ]

        for input_name, expected_output in test_cases:
            result = _convert_to_slug_format(input_name)
            assert result == expected_output, f"Failed for input: {input_name}"

    def test_generate_service_name_empty_values(self):
        """Test service name generation with empty values."""
        # Mock project with empty values
        mock_project = MagicMock()
        mock_project.attributes.get.side_effect = lambda key, default="": ""

        # Mock config with slug enabled
        config = GitLabConfig(
            token="test_token",
            new_relic_api_key="test_key",
            take_namespace_slug=True,
        )

        result = generate_service_name(mock_project, config)
        assert result == ""

    def test_generate_service_name_with_special_characters(self):
        """Test service name generation with various special characters."""
        mock_project = MagicMock()
        mock_project.attributes.get.side_effect = lambda key, default="": {
            "name_with_namespace": "Group@#$/Sub%^&/Project!@#",
        }.get(key, default)

        # Test with slug disabled (legacy behavior)
        config = GitLabConfig(
            token="test_token",
            new_relic_api_key="test_key",
            take_namespace_slug=False,
        )

        result = generate_service_name(mock_project, config)
        assert result == "group@#$/sub%^&/project!@#"

        # Test with slug enabled
        config.take_namespace_slug = True
        result = generate_service_name(mock_project, config)
        assert result == "group/sub/project"
