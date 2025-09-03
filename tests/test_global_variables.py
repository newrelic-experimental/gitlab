"""
Tests for global variables initialization and configuration.
"""

import pytest
import os
from unittest.mock import patch, MagicMock
from queue import Queue


class TestGlobalVariables:
    """Test global variables initialization."""

    def test_default_values(self):
        """Test default values are set correctly."""
        # We need to mock the environment and reimport to test defaults
        with patch.dict(
            os.environ,
            {"GLAB_TOKEN": "test-token", "NEW_RELIC_API_KEY": "test-key"},
            clear=True,
        ), patch("shared.custom_parsers.check_env_vars"), patch(
            "gitlab.Gitlab"
        ) as mock_gitlab:

            # Clear any existing module to force reimport
            import sys

            if "shared.global_variables" in sys.modules:
                del sys.modules["shared.global_variables"]

            import shared.global_variables as gv

            # Test default values
            assert gv.GLAB_DORA_METRICS is False
            assert gv.GLAB_EXPORT_LOGS is True
            assert gv.GLAB_STANDALONE is False
            assert gv.GLAB_EXPORT_LAST_MINUTES == 61
            assert gv.GLAB_PROJECT_OWNERSHIP is True
            assert gv.GLAB_PROJECT_VISIBILITIES == ["private"]
            assert gv.GLAB_SERVICE_NAME == "gitlab-exporter"
            assert gv.GLAB_EXPORT_PROJECTS_REGEX == ".*"
            assert gv.GLAB_EXPORT_PATHS == ""
            assert gv.GLAB_EXPORT_PATHS_ALL is False
            assert gv.GLAB_RUNNERS_SCOPE == ["all"]
            assert gv.GLAB_RUNNERS_INSTANCE is True
            assert isinstance(gv.q, Queue)

    def test_environment_variable_overrides(self):
        """Test that environment variables override defaults."""
        env_vars = {
            "GLAB_TOKEN": "test-token",
            "NEW_RELIC_API_KEY": "test-key",
            "GLAB_DORA_METRICS": "true",
            "GLAB_EXPORT_LOGS": "false",
            "GLAB_STANDALONE": "true",
            "GLAB_EXPORT_LAST_MINUTES": "120",
            "GLAB_PROJECT_OWNERSHIP": "false",
            "GLAB_PROJECT_VISIBILITIES": "public,internal",
            "GLAB_EXPORT_PROJECTS_REGEX": "test-.*",
            "GLAB_EXPORT_PATHS": "group1,group2",
            "GLAB_EXPORT_PATHS_ALL": "true",
            "GLAB_RUNNERS_SCOPE": "active,paused",
            "GLAB_RUNNERS_INSTANCE": "false",
            "GLAB_ENDPOINT": "https://custom-gitlab.com",
            "OTEL_EXPORTER_OTEL_ENDPOINT": "https://custom-otel.com:4318",
        }

        with patch.dict(os.environ, env_vars, clear=True), patch(
            "shared.custom_parsers.check_env_vars"
        ), patch("gitlab.Gitlab") as mock_gitlab:

            # Clear any existing module to force reimport
            import sys

            if "shared.global_variables" in sys.modules:
                del sys.modules["shared.global_variables"]

            import shared.global_variables as gv

            # Test overridden values
            assert gv.GLAB_DORA_METRICS == "true"  # String when set to true
            assert gv.GLAB_EXPORT_LOGS is False
            assert gv.GLAB_STANDALONE is True
            assert gv.GLAB_EXPORT_LAST_MINUTES == 121  # +1 added
            assert gv.GLAB_PROJECT_OWNERSHIP is False
            assert gv.GLAB_PROJECT_VISIBILITIES == ["public", "internal"]
            assert gv.GLAB_EXPORT_PROJECTS_REGEX == "test-.*"
            assert gv.GLAB_EXPORT_PATHS == "group1,group2"
            assert gv.GLAB_EXPORT_PATHS_ALL is True
            assert gv.GLAB_RUNNERS_SCOPE == ["active", "paused"]
            assert gv.GLAB_RUNNERS_INSTANCE is False
            assert gv.GLAB_ENDPOINT == "https://custom-gitlab.com"
            assert gv.OTEL_EXPORTER_OTEL_ENDPOINT == "https://custom-otel.com:4318"

    def test_gitlab_client_initialization_with_endpoint(self):
        """Test GitLab client initialization with custom endpoint."""
        with patch.dict(
            os.environ,
            {
                "GLAB_TOKEN": "test-token",
                "NEW_RELIC_API_KEY": "test-key",
                "GLAB_ENDPOINT": "https://custom-gitlab.com",
            },
            clear=True,
        ), patch("shared.custom_parsers.check_env_vars"), patch(
            "gitlab.Gitlab"
        ) as mock_gitlab:

            import sys

            if "shared.global_variables" in sys.modules:
                del sys.modules["shared.global_variables"]

            import shared.global_variables as gv

            # Verify GitLab client was initialized with custom endpoint
            mock_gitlab.assert_called_once_with(
                url="https://custom-gitlab.com", private_token="test-token"
            )

    def test_gitlab_client_initialization_default(self):
        """Test GitLab client initialization with default endpoint."""
        with patch.dict(
            os.environ,
            {"GLAB_TOKEN": "test-token", "NEW_RELIC_API_KEY": "test-key"},
            clear=True,
        ), patch("shared.custom_parsers.check_env_vars"), patch(
            "gitlab.Gitlab"
        ) as mock_gitlab:

            import sys

            if "shared.global_variables" in sys.modules:
                del sys.modules["shared.global_variables"]

            import shared.global_variables as gv

            # Verify GitLab client was initialized with default endpoint
            mock_gitlab.assert_called_once_with(private_token="test-token")
            assert gv.GLAB_ENDPOINT == "https://gitlab.com/"

    def test_otel_endpoint_eu_api_key(self):
        """Test OTEL endpoint selection for EU API key."""
        with patch.dict(
            os.environ,
            {"GLAB_TOKEN": "test-token", "NEW_RELIC_API_KEY": "eu01xxxxxxxxxxxx"},
            clear=True,
        ), patch("shared.custom_parsers.check_env_vars"), patch("gitlab.Gitlab"):

            import sys

            if "shared.global_variables" in sys.modules:
                del sys.modules["shared.global_variables"]

            import shared.global_variables as gv

            assert (
                gv.OTEL_EXPORTER_OTEL_ENDPOINT == "https://otlp.eu01.nr-data.net:4318"
            )

    def test_otel_endpoint_us_api_key(self):
        """Test OTEL endpoint selection for US API key."""
        with patch.dict(
            os.environ,
            {"GLAB_TOKEN": "test-token", "NEW_RELIC_API_KEY": "NRAK-xxxxxxxxxxxx"},
            clear=True,
        ), patch("shared.custom_parsers.check_env_vars"), patch("gitlab.Gitlab"):

            import sys

            if "shared.global_variables" in sys.modules:
                del sys.modules["shared.global_variables"]

            import shared.global_variables as gv

            assert gv.OTEL_EXPORTER_OTEL_ENDPOINT == "https://otlp.nr-data.net:4318"

    def test_paths_processing_with_ci_project_namespace(self):
        """Test paths processing when CI_PROJECT_NAMESPACE is set."""
        with patch.dict(
            os.environ,
            {
                "GLAB_TOKEN": "test-token",
                "NEW_RELIC_API_KEY": "test-key",
                "CI_PROJECT_NAMESPACE": "default-namespace",
            },
            clear=True,
        ), patch("shared.custom_parsers.check_env_vars"), patch("gitlab.Gitlab"):

            import sys

            if "shared.global_variables" in sys.modules:
                del sys.modules["shared.global_variables"]

            import shared.global_variables as gv

            assert gv.GLAB_EXPORT_PATHS == "default-namespace"
            assert gv.paths == ["default-namespace"]

    def test_paths_processing_empty(self):
        """Test paths processing when no paths are set."""
        with patch.dict(
            os.environ,
            {"GLAB_TOKEN": "test-token", "NEW_RELIC_API_KEY": "test-key"},
            clear=True,
        ), patch("shared.custom_parsers.check_env_vars"), patch("gitlab.Gitlab"):

            import sys

            if "shared.global_variables" in sys.modules:
                del sys.modules["shared.global_variables"]

            import shared.global_variables as gv

            assert gv.GLAB_EXPORT_PATHS == ""
            assert gv.paths == ""

    def test_paths_processing_comma_separated(self):
        """Test paths processing with comma-separated values."""
        with patch.dict(
            os.environ,
            {
                "GLAB_TOKEN": "test-token",
                "NEW_RELIC_API_KEY": "test-key",
                "GLAB_EXPORT_PATHS": "group1,group2,group3",
            },
            clear=True,
        ), patch("shared.custom_parsers.check_env_vars"), patch("gitlab.Gitlab"):

            import sys

            if "shared.global_variables" in sys.modules:
                del sys.modules["shared.global_variables"]

            import shared.global_variables as gv

            assert gv.GLAB_EXPORT_PATHS == "group1,group2,group3"
            assert gv.paths == ["group1", "group2", "group3"]

    def test_boolean_environment_variables_case_insensitive(self):
        """Test that boolean environment variables are case insensitive."""
        test_cases = [
            ("TRUE", True),
            ("True", True),
            ("true", True),
            ("FALSE", False),
            ("False", False),
            ("false", False),
            ("invalid", False),  # Invalid values default to False
        ]

        for value, expected in test_cases:
            with patch.dict(
                os.environ,
                {
                    "GLAB_TOKEN": "test-token",
                    "NEW_RELIC_API_KEY": "test-key",
                    "GLAB_STANDALONE": value,
                },
                clear=True,
            ), patch("shared.custom_parsers.check_env_vars"), patch("gitlab.Gitlab"):

                import sys

                if "shared.global_variables" in sys.modules:
                    del sys.modules["shared.global_variables"]

                import shared.global_variables as gv

                assert gv.GLAB_STANDALONE == expected

    def test_headers_and_endpoint_formatting(self):
        """Test that headers and endpoint are formatted correctly."""
        with patch.dict(
            os.environ,
            {
                "GLAB_TOKEN": "test-token",
                "NEW_RELIC_API_KEY": "test-api-key",
                "OTEL_EXPORTER_OTEL_ENDPOINT": "https://custom-endpoint.com:4318",
            },
            clear=True,
        ), patch("shared.custom_parsers.check_env_vars"), patch("gitlab.Gitlab"):

            import sys

            if "shared.global_variables" in sys.modules:
                del sys.modules["shared.global_variables"]

            import shared.global_variables as gv

            assert gv.endpoint == "https://custom-endpoint.com:4318"
            assert gv.headers == "api-key=test-api-key"

    def test_export_last_minutes_conversion(self):
        """Test that GLAB_EXPORT_LAST_MINUTES is converted to int and incremented."""
        with patch.dict(
            os.environ,
            {
                "GLAB_TOKEN": "test-token",
                "NEW_RELIC_API_KEY": "test-key",
                "GLAB_EXPORT_LAST_MINUTES": "30",
            },
            clear=True,
        ), patch("shared.custom_parsers.check_env_vars"), patch("gitlab.Gitlab"):

            import sys

            if "shared.global_variables" in sys.modules:
                del sys.modules["shared.global_variables"]

            import shared.global_variables as gv

            assert gv.GLAB_EXPORT_LAST_MINUTES == 31  # 30 + 1

    def test_queue_initialization(self):
        """Test that queue is properly initialized."""
        with patch.dict(
            os.environ,
            {"GLAB_TOKEN": "test-token", "NEW_RELIC_API_KEY": "test-key"},
            clear=True,
        ), patch("shared.custom_parsers.check_env_vars"), patch("gitlab.Gitlab"):

            import sys

            if "shared.global_variables" in sys.modules:
                del sys.modules["shared.global_variables"]

            import shared.global_variables as gv

            assert isinstance(gv.q, Queue)
            assert gv.q.empty()

    def test_runners_scope_comma_separated(self):
        """Test runners scope with comma-separated values."""
        with patch.dict(
            os.environ,
            {
                "GLAB_TOKEN": "test-token",
                "NEW_RELIC_API_KEY": "test-key",
                "GLAB_RUNNERS_SCOPE": "active,paused,online",
            },
            clear=True,
        ), patch("shared.custom_parsers.check_env_vars"), patch("gitlab.Gitlab"):

            import sys

            if "shared.global_variables" in sys.modules:
                del sys.modules["shared.global_variables"]

            import shared.global_variables as gv

            assert gv.GLAB_RUNNERS_SCOPE == ["active", "paused", "online"]

    def test_dora_metrics_string_value_when_true(self):
        """Test that GLAB_DORA_METRICS becomes string when set to true."""
        with patch.dict(
            os.environ,
            {
                "GLAB_TOKEN": "test-token",
                "NEW_RELIC_API_KEY": "test-key",
                "GLAB_DORA_METRICS": "true",
            },
            clear=True,
        ), patch("shared.custom_parsers.check_env_vars"), patch("gitlab.Gitlab"):

            import sys

            if "shared.global_variables" in sys.modules:
                del sys.modules["shared.global_variables"]

            import shared.global_variables as gv

            # When GLAB_DORA_METRICS is "true", it gets the env var value (string)
            assert gv.GLAB_DORA_METRICS == "true"

    def test_check_env_vars_called(self):
        """Test that check_env_vars is called during import."""
        with patch.dict(
            os.environ,
            {"GLAB_TOKEN": "test-token", "NEW_RELIC_API_KEY": "test-key"},
            clear=True,
        ), patch("shared.custom_parsers.check_env_vars") as mock_check, patch(
            "gitlab.Gitlab"
        ):

            import sys

            if "shared.global_variables" in sys.modules:
                del sys.modules["shared.global_variables"]

            import shared.global_variables as gv

            mock_check.assert_called_once()
