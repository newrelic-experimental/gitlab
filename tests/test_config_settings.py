"""
Tests for shared.config.settings module.

Comprehensive tests for GitLabConfig class and configuration loading.
"""

import pytest
import os
from unittest.mock import patch, MagicMock
from shared.config.settings import (
    GitLabConfig,
    load_config_from_env,
    _get_bool_env,
    validate_environment,
    get_config,
    reset_config,
)


class TestGitLabConfig:
    """Test suite for GitLabConfig class."""

    def test_config_initialization_with_required_fields(self):
        """Test GitLabConfig initialization with required fields."""
        config = GitLabConfig(token="test-token", new_relic_api_key="NRAK-test123")

        assert config.token == "test-token"
        assert config.new_relic_api_key == "NRAK-test123"
        assert config.endpoint == "https://gitlab.com/"
        assert config.export_logs is True
        assert config.low_data_mode is False

    def test_config_initialization_missing_token(self):
        """Test GitLabConfig raises error when token is missing."""
        with pytest.raises(ValueError, match="GLAB_TOKEN is required"):
            GitLabConfig(token="", new_relic_api_key="NRAK-test123")

    def test_config_initialization_missing_api_key(self):
        """Test GitLabConfig raises error when API key is missing."""
        with pytest.raises(ValueError, match="NEW_RELIC_API_KEY is required"):
            GitLabConfig(token="test-token", new_relic_api_key="")

    def test_config_otel_endpoint_us_region(self):
        """Test OTEL endpoint is set correctly for US region."""
        config = GitLabConfig(token="test-token", new_relic_api_key="NRAK-test123")
        assert config.otel_endpoint == "https://otlp.nr-data.net:4318"

    def test_config_otel_endpoint_eu_region(self):
        """Test OTEL endpoint is set correctly for EU region."""
        config = GitLabConfig(token="test-token", new_relic_api_key="eu01xx-test123")
        assert config.otel_endpoint == "https://otlp.eu01.nr-data.net:4318"

    def test_config_export_paths_parsing(self):
        """Test export paths are parsed correctly."""
        config = GitLabConfig(
            token="test-token",
            new_relic_api_key="NRAK-test123",
            export_paths="path1, path2, path3",
        )
        assert config.export_paths_list == ["path1", "path2", "path3"]

    def test_config_invalid_gitlab_endpoint(self):
        """Test invalid GitLab endpoint raises error."""
        with pytest.raises(ValueError, match="Invalid GitLab endpoint"):
            GitLabConfig(
                token="test-token",
                new_relic_api_key="NRAK-test123",
                endpoint="invalid-url",
            )

    def test_config_invalid_regex_pattern(self):
        """Test invalid regex pattern raises error."""
        with pytest.raises(ValueError, match="Invalid regex pattern"):
            GitLabConfig(
                token="test-token",
                new_relic_api_key="NRAK-test123",
                export_projects_regex="[invalid-regex",
            )

    def test_config_invalid_export_last_minutes(self):
        """Test invalid export_last_minutes raises error."""
        with pytest.raises(ValueError, match="export_last_minutes must be at least 1"):
            GitLabConfig(
                token="test-token",
                new_relic_api_key="NRAK-test123",
                export_last_minutes=0,
            )

    def test_config_invalid_project_visibility(self):
        """Test invalid project visibility raises error."""
        with pytest.raises(ValueError, match="Invalid project visibility"):
            GitLabConfig(
                token="test-token",
                new_relic_api_key="NRAK-test123",
                project_visibilities=["invalid"],
            )

    def test_gitlab_headers_property(self):
        """Test gitlab_headers property returns correct format."""
        config = GitLabConfig(token="test-token", new_relic_api_key="NRAK-test123")
        assert config.gitlab_headers == "api-key=NRAK-test123"


class TestConfigLoading:
    """Test suite for configuration loading from environment."""

    def test_load_config_from_env_success(self, clean_environment):
        """Test successful config loading from environment."""
        env_vars = {
            "GLAB_TOKEN": "test-token",
            "NEW_RELIC_API_KEY": "NRAK-test123",
            "CI_PROJECT_ID": "123",
            "CI_PIPELINE_ID": "456",
        }

        with patch.dict(os.environ, env_vars):
            config = load_config_from_env()

            assert config.token == "test-token"
            assert config.new_relic_api_key == "NRAK-test123"
            assert config.project_id == "123"
            assert config.pipeline_id == "456"

    def test_load_config_with_parent_pipeline(self, clean_environment):
        """Test config loading prioritizes CI_PARENT_PIPELINE over CI_PIPELINE_ID."""
        env_vars = {
            "GLAB_TOKEN": "test-token",
            "NEW_RELIC_API_KEY": "NRAK-test123",
            "CI_PARENT_PIPELINE": "789",
            "CI_PIPELINE_ID": "456",
        }

        with patch.dict(os.environ, env_vars):
            config = load_config_from_env()
            assert config.pipeline_id == "789"

    def test_load_config_boolean_env_vars(self, clean_environment):
        """Test boolean environment variable parsing."""
        env_vars = {
            "GLAB_TOKEN": "test-token",
            "NEW_RELIC_API_KEY": "NRAK-test123",
            "GLAB_EXPORT_LOGS": "false",
            "GLAB_LOW_DATA_MODE": "true",
            "GLAB_STANDALONE": "1",
            "GLAB_DORA_METRICS": "yes",
        }

        with patch.dict(os.environ, env_vars):
            config = load_config_from_env()

            assert config.export_logs is False
            assert config.low_data_mode is True
            assert config.standalone_mode is True
            assert config.dora_metrics is True

    def test_load_config_list_parsing(self, clean_environment):
        """Test list environment variable parsing."""
        env_vars = {
            "GLAB_TOKEN": "test-token",
            "NEW_RELIC_API_KEY": "NRAK-test123",
            "GLAB_PROJECT_VISIBILITIES": "private,public",
            "GLAB_EXCLUDE_JOBS": "job1, job2, job3",
            "GLAB_RUNNERS_SCOPE": "active,paused",
        }

        with patch.dict(os.environ, env_vars):
            config = load_config_from_env()

            assert config.project_visibilities == ["private", "public"]
            assert config.exclude_jobs == ["job1", "job2", "job3"]
            assert config.runners_scope == ["active", "paused"]

    def test_load_config_namespace_fallback(self, clean_environment):
        """Test export_paths falls back to CI_PROJECT_NAMESPACE."""
        env_vars = {
            "GLAB_TOKEN": "test-token",
            "NEW_RELIC_API_KEY": "NRAK-test123",
            "CI_PROJECT_NAMESPACE": "my-namespace",
        }

        with patch.dict(os.environ, env_vars):
            config = load_config_from_env()
            assert config.export_paths == "my-namespace"


class TestBooleanEnvironmentParsing:
    """Test suite for boolean environment variable parsing."""

    def test_get_bool_env_true_values(self):
        """Test _get_bool_env recognizes true values."""
        true_values = ["true", "1", "yes", "on", "TRUE", "Yes", "ON"]

        for value in true_values:
            with patch.dict(os.environ, {"TEST_BOOL": value}):
                assert _get_bool_env("TEST_BOOL") is True

    def test_get_bool_env_false_values(self):
        """Test _get_bool_env recognizes false values."""
        false_values = ["false", "0", "no", "off", "FALSE", "No", "OFF", ""]

        for value in false_values:
            with patch.dict(os.environ, {"TEST_BOOL": value}):
                assert _get_bool_env("TEST_BOOL") is False

    def test_get_bool_env_default_value(self):
        """Test _get_bool_env returns default when env var not set."""
        with patch.dict(os.environ, {}, clear=True):
            assert _get_bool_env("NONEXISTENT", default=True) is True
            assert _get_bool_env("NONEXISTENT", default=False) is False


class TestEnvironmentValidation:
    """Test suite for environment validation."""

    def test_validate_environment_success(self, clean_environment):
        """Test successful environment validation."""
        env_vars = {"GLAB_TOKEN": "test-token", "NEW_RELIC_API_KEY": "NRAK-test123"}

        with patch.dict(os.environ, env_vars):
            # Should not raise any exception
            validate_environment()

    def test_validate_environment_missing_token(self, clean_environment):
        """Test environment validation fails with missing token."""
        env_vars = {"NEW_RELIC_API_KEY": "NRAK-test123"}

        with patch.dict(os.environ, env_vars):
            with patch("shared.config.settings.get_logger") as mock_get_logger:
                mock_logger = MagicMock()
                mock_get_logger.return_value = mock_logger

                with pytest.raises(SystemExit):
                    validate_environment()

                # Verify error was logged
                mock_logger.critical.assert_called()

    def test_validate_environment_missing_api_key(self, clean_environment):
        """Test environment validation fails with missing API key."""
        env_vars = {"GLAB_TOKEN": "test-token"}

        with patch.dict(os.environ, env_vars):
            with patch("shared.config.settings.get_logger") as mock_get_logger:
                mock_logger = MagicMock()
                mock_get_logger.return_value = mock_logger

                with pytest.raises(SystemExit):
                    validate_environment()

                # Verify error was logged
                mock_logger.critical.assert_called()

    def test_validate_environment_missing_both(self, clean_environment):
        """Test environment validation fails with both missing."""
        with patch.dict(os.environ, {}, clear=True):
            with patch("shared.config.settings.get_logger") as mock_get_logger:
                mock_logger = MagicMock()
                mock_get_logger.return_value = mock_logger

                with pytest.raises(SystemExit):
                    validate_environment()

                # Verify error was logged
                mock_logger.critical.assert_called()


class TestGlobalConfigInstance:
    """Test suite for global configuration instance management."""

    def test_get_config_creates_instance(self, clean_environment):
        """Test get_config creates and returns config instance."""
        env_vars = {"GLAB_TOKEN": "test-token", "NEW_RELIC_API_KEY": "NRAK-test123"}

        reset_config()  # Ensure clean state

        with patch.dict(os.environ, env_vars):
            config1 = get_config()
            config2 = get_config()

            # Should return the same instance
            assert config1 is config2
            assert config1.token == "test-token"

    def test_reset_config_clears_instance(self, clean_environment):
        """Test reset_config clears the global instance."""
        env_vars = {"GLAB_TOKEN": "test-token", "NEW_RELIC_API_KEY": "NRAK-test123"}

        with patch.dict(os.environ, env_vars):
            config1 = get_config()
            reset_config()
            config2 = get_config()

            # Should be different instances after reset
            assert config1 is not config2
            assert config1.token == config2.token  # But same values
