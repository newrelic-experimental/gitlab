"""
Centralized configuration management for GitLab New Relic Exporters.

This module provides a centralized way to manage all configuration settings,
replacing scattered environment variable access throughout the codebase.
"""

import os
import re
from dataclasses import dataclass, field
from typing import List, Optional, Union
from urllib.parse import urlparse
from shared.logging.structured_logger import get_logger, LogContext


@dataclass
class GitLabConfig:
    """Configuration for GitLab API connection and data export settings."""

    # Required settings
    token: str
    new_relic_api_key: str

    # GitLab settings
    endpoint: str = "https://gitlab.com/"
    project_id: Optional[str] = None
    pipeline_id: Optional[str] = None

    # Export behavior settings
    export_logs: bool = True
    low_data_mode: bool = False
    standalone_mode: bool = False
    dora_metrics: bool = False

    # Project filtering
    export_projects_regex: str = ".*"
    export_paths: str = ""
    export_paths_all: bool = False
    project_ownership: bool = True
    project_visibilities: List[str] = field(default_factory=lambda: ["private"])

    # Job filtering
    exclude_jobs: List[str] = field(default_factory=list)

    # Time-based filtering
    export_last_minutes: int = 61

    # Runner settings
    runners_instance: bool = True
    runners_scope: List[str] = field(default_factory=lambda: ["all"])

    # New Relic settings
    otel_endpoint: Optional[str] = None
    service_name: str = "gitlab-exporter"

    def __post_init__(self):
        """Validate configuration after initialization."""
        self._validate_required_fields()
        self._set_derived_fields()
        self._validate_settings()

    def _validate_required_fields(self):
        """Validate that required fields are present."""
        if not self.token:
            raise ValueError("GLAB_TOKEN is required")

        if not self.new_relic_api_key:
            raise ValueError("NEW_RELIC_API_KEY is required")

    def _set_derived_fields(self):
        """Set fields that are derived from other settings."""
        # Set OTEL endpoint based on New Relic API key region if not specified
        if not self.otel_endpoint:
            if self.new_relic_api_key.startswith("eu"):
                self.otel_endpoint = "https://otlp.eu01.nr-data.net:4318"
            else:
                self.otel_endpoint = "https://otlp.nr-data.net:4318"

        # Parse export paths into list
        if self.export_paths:
            self.export_paths_list = [
                path.strip() for path in self.export_paths.split(",") if path.strip()
            ]
        else:
            self.export_paths_list = []

    def _validate_settings(self):
        """Validate configuration settings."""
        # Validate GitLab endpoint
        if self.endpoint:
            parsed = urlparse(self.endpoint)
            if not parsed.scheme or not parsed.netloc:
                raise ValueError(f"Invalid GitLab endpoint: {self.endpoint}")

        # Validate regex pattern
        try:
            re.compile(self.export_projects_regex)
        except re.error as e:
            raise ValueError(
                f"Invalid regex pattern '{self.export_projects_regex}': {e}"
            )

        # Validate time settings
        if self.export_last_minutes < 1:
            raise ValueError("export_last_minutes must be at least 1")

        # Validate project visibilities
        valid_visibilities = ["private", "internal", "public"]
        for visibility in self.project_visibilities:
            if visibility not in valid_visibilities:
                raise ValueError(
                    f"Invalid project visibility '{visibility}'. Must be one of: {valid_visibilities}"
                )

    @property
    def gitlab_headers(self) -> str:
        """Get formatted headers for OTEL exporter."""
        return f"api-key={self.new_relic_api_key}"

    @property
    def export_paths_list(self) -> List[str]:
        """Get export paths as a list."""
        if hasattr(self, "_export_paths_list"):
            return self._export_paths_list
        return []

    @export_paths_list.setter
    def export_paths_list(self, value: List[str]):
        """Set export paths list."""
        self._export_paths_list = value


def load_config_from_env() -> GitLabConfig:
    """
    Load configuration from environment variables.

    Returns:
        GitLabConfig: Configured instance with values from environment

    Raises:
        ValueError: If required environment variables are missing or invalid
    """
    # Required environment variables
    token = os.getenv("GLAB_TOKEN")
    new_relic_api_key = os.getenv("NEW_RELIC_API_KEY")

    # GitLab settings
    endpoint = os.getenv("GLAB_ENDPOINT", "https://gitlab.com/")
    project_id = os.getenv("CI_PROJECT_ID")
    pipeline_id = os.getenv("CI_PARENT_PIPELINE") or os.getenv("CI_PIPELINE_ID")

    # Export behavior settings
    export_logs = _get_bool_env("GLAB_EXPORT_LOGS", True)
    low_data_mode = _get_bool_env("GLAB_LOW_DATA_MODE", False)
    standalone_mode = _get_bool_env("GLAB_STANDALONE", False)
    dora_metrics = _get_bool_env("GLAB_DORA_METRICS", False)

    # Project filtering
    export_projects_regex = os.getenv("GLAB_EXPORT_PROJECTS_REGEX", ".*")
    export_paths = os.getenv("GLAB_EXPORT_PATHS", "")
    export_paths_all = _get_bool_env("GLAB_EXPORT_PATHS_ALL", False)
    project_ownership = _get_bool_env("GLAB_PROJECT_OWNERSHIP", True)

    # Parse project visibilities
    project_visibilities_str = os.getenv("GLAB_PROJECT_VISIBILITIES", "private")
    project_visibilities = [
        v.strip() for v in project_visibilities_str.split(",") if v.strip()
    ]

    # Job filtering
    exclude_jobs_str = os.getenv("GLAB_EXCLUDE_JOBS", "")
    exclude_jobs = [j.strip().lower() for j in exclude_jobs_str.split(",") if j.strip()]

    # Time-based filtering
    export_last_minutes = int(os.getenv("GLAB_EXPORT_LAST_MINUTES", "60")) + 1

    # Runner settings
    runners_instance = _get_bool_env("GLAB_RUNNERS_INSTANCE", True)
    runners_scope_str = os.getenv("GLAB_RUNNERS_SCOPE", "all")
    runners_scope = [s.strip() for s in runners_scope_str.split(",") if s.strip()]

    # New Relic settings
    otel_endpoint = os.getenv("OTEL_EXPORTER_OTEL_ENDPOINT")
    service_name = os.getenv("GLAB_SERVICE_NAME", "gitlab-exporter")

    # Set export_paths from CI_PROJECT_NAMESPACE if not specified
    if not export_paths and os.getenv("CI_PROJECT_NAMESPACE"):
        export_paths = os.getenv("CI_PROJECT_NAMESPACE")

    return GitLabConfig(
        token=token,
        new_relic_api_key=new_relic_api_key,
        endpoint=endpoint,
        project_id=project_id,
        pipeline_id=pipeline_id,
        export_logs=export_logs,
        low_data_mode=low_data_mode,
        standalone_mode=standalone_mode,
        dora_metrics=dora_metrics,
        export_projects_regex=export_projects_regex,
        export_paths=export_paths,
        export_paths_all=export_paths_all,
        project_ownership=project_ownership,
        project_visibilities=project_visibilities,
        exclude_jobs=exclude_jobs,
        export_last_minutes=export_last_minutes,
        runners_instance=runners_instance,
        runners_scope=runners_scope,
        otel_endpoint=otel_endpoint,
        service_name=service_name,
    )


def _get_bool_env(key: str, default: bool = False) -> bool:
    """
    Get a boolean value from environment variable.

    Args:
        key: Environment variable name
        default: Default value if not set

    Returns:
        bool: Parsed boolean value
    """
    value = os.getenv(key)
    if value is None:
        return default
    return value.lower() in ("true", "1", "yes", "on")


def validate_environment() -> None:
    """
    Validate that all required environment variables are present.

    Raises:
        SystemExit: If required variables are missing
    """
    logger = get_logger("gitlab-exporter", "config")
    required_vars = ["GLAB_TOKEN", "NEW_RELIC_API_KEY"]
    missing_vars = []

    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)

    if missing_vars:
        context = LogContext(
            service_name="gitlab-exporter",
            component="config",
            operation="validate_environment",
        )
        logger.critical(
            f"Missing required environment variables: {', '.join(missing_vars)}",
            context,
            missing_variables=missing_vars,
        )
        logger.critical("Please set the following environment variables:", context)
        for var in missing_vars:
            logger.critical(f"  export {var}=<your_value>", context, variable=var)
        raise SystemExit(1)


# Global configuration instance (will be initialized when first imported)
_config_instance: Optional[GitLabConfig] = None


def get_config() -> GitLabConfig:
    """
    Get the global configuration instance.

    Returns:
        GitLabConfig: The global configuration instance
    """
    global _config_instance
    if _config_instance is None:
        validate_environment()
        _config_instance = load_config_from_env()
    return _config_instance


def reset_config():
    """Reset the global configuration instance (mainly for testing)."""
    global _config_instance
    _config_instance = None
