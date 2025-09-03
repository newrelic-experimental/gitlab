"""
Tests for shared.custom_parsers module.

Comprehensive tests for parsing functions and attribute handling.
"""

import pytest
import os
import json
from unittest.mock import patch, MagicMock
from shared.custom_parsers import (
    do_time,
    do_string,
    do_parse,
    check_env_vars,
    grab_span_att_vars,
    parse_attributes,
    _is_json_string,
    _flatten_json_string,
    _flatten_array,
    parse_metrics_attributes,
)


class TestTimeHandling:
    """Test suite for time parsing functions."""

    def test_do_time_valid_iso_string(self):
        """Test do_time converts ISO string to nanoseconds."""
        iso_string = "2024-01-01T00:00:00.000Z"
        result = do_time(iso_string)

        # Should return nanoseconds timestamp
        assert isinstance(result, int)
        assert result > 0

    def test_do_time_with_timezone(self):
        """Test do_time handles timezone information."""
        iso_string = "2024-01-01T12:30:45+02:00"
        result = do_time(iso_string)

        assert isinstance(result, int)
        assert result > 0

    def test_do_time_different_formats(self):
        """Test do_time handles different ISO formats."""
        formats = [
            "2024-01-01T00:00:00Z",
            "2024-01-01T00:00:00.123Z",
            "2024-01-01T00:00:00.123456Z",
            "2024-01-01T00:00:00+00:00",
        ]

        for format_str in formats:
            result = do_time(format_str)
            assert isinstance(result, int)
            assert result > 0


class TestStringHandling:
    """Test suite for string processing functions."""

    def test_do_string_basic_conversion(self):
        """Test do_string converts to lowercase and removes spaces."""
        assert do_string("Hello World") == "helloworld"
        assert do_string("TEST STRING") == "teststring"
        assert do_string("  spaced  ") == "spaced"

    def test_do_string_special_characters(self):
        """Test do_string handles special characters."""
        assert do_string("test-string_123") == "test-string_123"
        assert do_string("Test With Spaces") == "testwithspaces"

    def test_do_string_empty_input(self):
        """Test do_string handles empty input."""
        assert do_string("") == ""
        assert do_string("   ") == ""

    def test_do_parse_valid_values(self):
        """Test do_parse returns True for valid values."""
        valid_values = ["test", "123", "0", "false", True, 42, 0.5]

        for value in valid_values:
            assert do_parse(value) is True

    def test_do_parse_invalid_values(self):
        """Test do_parse returns False for invalid values."""
        invalid_values = ["", None, "None"]

        for value in invalid_values:
            assert do_parse(value) is False


class TestEnvironmentVariableChecking:
    """Test suite for environment variable validation."""

    def test_check_env_vars_success(self, clean_environment):
        """Test check_env_vars passes with required variables set."""
        env_vars = {"GLAB_TOKEN": "test-token", "NEW_RELIC_API_KEY": "test-key"}

        with patch.dict(os.environ, env_vars):
            # Should not raise SystemExit
            check_env_vars()

    def test_check_env_vars_missing_token(self, clean_environment):
        """Test check_env_vars exits when GLAB_TOKEN is missing."""
        env_vars = {"NEW_RELIC_API_KEY": "test-key"}

        with patch.dict(os.environ, env_vars):
            with pytest.raises(SystemExit):
                check_env_vars()

    def test_check_env_vars_missing_api_key(self, clean_environment):
        """Test check_env_vars exits when NEW_RELIC_API_KEY is missing."""
        env_vars = {"GLAB_TOKEN": "test-token"}

        with patch.dict(os.environ, env_vars):
            with pytest.raises(SystemExit):
                check_env_vars()

    def test_check_env_vars_missing_both(self, clean_environment):
        """Test check_env_vars exits when both variables are missing."""
        with patch.dict(os.environ, {}, clear=True):
            with pytest.raises(SystemExit):
                check_env_vars()


class TestSpanAttributeGrabbing:
    """Test suite for span attribute collection."""

    def test_grab_span_att_vars_filters_correctly(self, clean_environment):
        """Test grab_span_att_vars includes only relevant environment variables."""
        env_vars = {
            "CI_PROJECT_ID": "123",
            "CI_PIPELINE_ID": "456",
            "GIT_BRANCH": "main",
            "GLAB_EXPORT_LOGS": "true",
            "NEW_RELIC_API_KEY": "secret-key",  # Should be filtered out
            "GLAB_TOKEN": "secret-token",  # Should be filtered out
            "HOME": "/home/user",  # Should be filtered out
            "PATH": "/usr/bin",  # Should be filtered out
            "OTEL_ENDPOINT": "https://otlp.nr-data.net",
        }

        with patch.dict(os.environ, env_vars):
            result = grab_span_att_vars()

            # Should include CI, GIT, GLAB, OTEL variables
            assert "CI_PROJECT_ID" in result
            assert "CI_PIPELINE_ID" in result
            assert "GIT_BRANCH" in result
            assert "GLAB_EXPORT_LOGS" in result
            assert "OTEL_ENDPOINT" in result

            # Should exclude sensitive and irrelevant variables
            assert "NEW_RELIC_API_KEY" not in result
            assert "GLAB_TOKEN" not in result
            assert "HOME" not in result
            assert "PATH" not in result

    def test_grab_span_att_vars_custom_drop_list(self, clean_environment):
        """Test grab_span_att_vars respects GLAB_ENVS_DROP configuration."""
        env_vars = {
            "CI_PROJECT_ID": "123",
            "CI_PIPELINE_ID": "456",
            "CI_COMMIT_SHA": "abc123",
            "GLAB_ENVS_DROP": "CI_COMMIT_SHA,CI_PIPELINE_ID",
        }

        with patch.dict(os.environ, env_vars):
            result = grab_span_att_vars()

            assert "CI_PROJECT_ID" in result
            assert "CI_PIPELINE_ID" not in result  # Should be dropped
            assert "CI_COMMIT_SHA" not in result  # Should be dropped

    def test_grab_span_att_vars_filters_none_values(self, clean_environment):
        """Test grab_span_att_vars filters out None and empty values."""
        env_vars = {"CI_PROJECT_ID": "123", "CI_EMPTY_VAR": "", "CI_NONE_VAR": "None"}

        with patch.dict(os.environ, env_vars):
            result = grab_span_att_vars()

            assert "CI_PROJECT_ID" in result
            assert "CI_EMPTY_VAR" not in result
            assert "CI_NONE_VAR" not in result

    def test_grab_span_att_vars_handles_malformed_drop_list(self, clean_environment):
        """Test grab_span_att_vars handles malformed GLAB_ENVS_DROP gracefully."""
        env_vars = {"CI_PROJECT_ID": "123", "GLAB_ENVS_DROP": ""}  # Empty drop list

        with patch.dict(os.environ, env_vars):
            result = grab_span_att_vars()

            assert "CI_PROJECT_ID" in result


class TestAttributeParsing:
    """Test suite for attribute parsing functions."""

    def test_parse_attributes_simple_dict(self):
        """Test parse_attributes handles simple dictionary."""
        data = {"id": 123, "name": "test-job", "status": "success"}

        result = parse_attributes(data)

        assert result["id"] == "123"
        assert result["name"] == "test-job"
        assert result["status"] == "success"

    def test_parse_attributes_nested_dict(self):
        """Test parse_attributes flattens nested dictionaries."""
        data = {
            "job": {
                "id": 123,
                "runner": {"name": "docker-runner", "tags": ["docker", "linux"]},
            }
        }

        result = parse_attributes(data)

        assert result["job.id"] == "123"
        assert result["job.runner.name"] == "docker-runner"
        assert result["job.runner.tags[0]"] == "docker"
        assert result["job.runner.tags[1]"] == "linux"

    def test_parse_attributes_filters_none_values(self):
        """Test parse_attributes filters out None and empty values."""
        data = {
            "valid_field": "value",
            "none_field": None,
            "empty_field": "",
            "none_string": "None",
        }

        result = parse_attributes(data)

        assert "valid_field" in result
        assert "none_field" not in result
        assert "empty_field" not in result
        assert "none_string" not in result

    def test_parse_attributes_with_custom_drop_list(self, clean_environment):
        """Test parse_attributes respects GLAB_ATTRIBUTES_DROP configuration."""
        env_vars = {"GLAB_ATTRIBUTES_DROP": "sensitive_field,another_field"}

        data = {
            "id": 123,
            "sensitive_field": "secret",
            "another_field": "drop_me",
            "keep_field": "keep_me",
        }

        with patch.dict(os.environ, env_vars):
            result = parse_attributes(data)

            assert "id" in result
            assert "keep_field" in result
            assert "sensitive_field" not in result
            assert "another_field" not in result

    def test_parse_attributes_handles_list_input(self):
        """Test parse_attributes handles list input."""
        data = ["item1", "item2", "item3"]

        result = parse_attributes(data)

        assert result["[0]"] == "item1"
        assert result["[1]"] == "item2"
        assert result["[2]"] == "item3"


class TestJSONStringHandling:
    """Test suite for JSON string detection and parsing."""

    def test_is_json_string_valid_json(self):
        """Test _is_json_string detects valid JSON strings."""
        valid_json_strings = [
            '{"key": "value"}',
            '{"nested": {"key": "value"}}',
            "[1, 2, 3]",
            '{"number": 123, "boolean": true}',
        ]

        for json_str in valid_json_strings:
            assert _is_json_string(json_str) is True

    def test_is_json_string_invalid_json(self):
        """Test _is_json_string rejects invalid JSON strings."""
        invalid_json_strings = [
            "not json",
            '{"invalid": json}',
            "{incomplete",
            "",
            None,
            123,
        ]

        for json_str in invalid_json_strings:
            assert _is_json_string(json_str) is False

    def test_flatten_json_string_valid_json(self):
        """Test _flatten_json_string parses and flattens JSON."""
        json_str = '{"user": {"name": "John", "age": 30}, "active": true}'
        prefix = "metadata"

        result = _flatten_json_string(json_str, prefix)

        assert result["metadata.user.name"] == "John"
        assert result["metadata.user.age"] == "30"
        assert result["metadata.active"] == "True"

    def test_flatten_json_string_invalid_json(self):
        """Test _flatten_json_string handles invalid JSON gracefully."""
        json_str = "not valid json"
        prefix = "metadata"

        result = _flatten_json_string(json_str, prefix)

        # Should return the string as-is
        assert result[prefix] == json_str


class TestArrayFlattening:
    """Test suite for array flattening functionality."""

    def test_flatten_array_simple_array(self):
        """Test _flatten_array handles simple arrays."""
        array = ["item1", "item2", "item3"]
        prefix = "tags"

        result = _flatten_array(array, prefix)

        assert result["tags[0]"] == "item1"
        assert result["tags[1]"] == "item2"
        assert result["tags[2]"] == "item3"

    def test_flatten_array_with_none_values(self):
        """Test _flatten_array filters out None values and compacts indices."""
        array = ["item1", None, "", "item2", "None"]
        prefix = "tags"

        result = _flatten_array(array, prefix)

        # Should only include valid items with compacted indices
        assert result["tags[0]"] == "item1"
        assert result["tags[1]"] == "item2"
        assert len(result) == 2

    def test_flatten_array_nested_objects(self):
        """Test _flatten_array handles nested objects in arrays."""
        array = [
            {"name": "runner1", "active": True},
            {"name": "runner2", "active": False},
        ]
        prefix = "runners"

        result = _flatten_array(array, prefix)

        assert result["runners[0].name"] == "runner1"
        assert result["runners[0].active"] == "True"
        assert result["runners[1].name"] == "runner2"
        assert result["runners[1].active"] == "False"

    def test_flatten_array_nested_arrays(self):
        """Test _flatten_array handles nested arrays."""
        array = [["tag1", "tag2"], ["tag3", "tag4"]]
        prefix = "nested_tags"

        result = _flatten_array(array, prefix)

        assert result["nested_tags[0][0]"] == "tag1"
        assert result["nested_tags[0][1]"] == "tag2"
        assert result["nested_tags[1][0]"] == "tag3"
        assert result["nested_tags[1][1]"] == "tag4"


class TestMetricsAttributeParsing:
    """Test suite for metrics attribute parsing."""

    def test_parse_metrics_attributes_default_dimensions(self):
        """Test parse_metrics_attributes with default dimensions."""
        attributes = {
            "service.name": "gitlab-exporter",
            "status": "success",
            "stage": "build",
            "name": "docker-build",
            "duration": "300.5",
            "queued_duration": "10.2",
            "extra_field": "should_be_filtered",
        }

        duration, queued_duration, metrics_attrs = parse_metrics_attributes(attributes)

        assert duration == 300.5
        assert queued_duration == 10.2
        assert "service.name" in metrics_attrs
        assert "status" in metrics_attrs
        assert "stage" in metrics_attrs
        assert "name" in metrics_attrs
        assert "extra_field" not in metrics_attrs

    def test_parse_metrics_attributes_custom_dimensions(self, clean_environment):
        """Test parse_metrics_attributes with custom dimensions."""
        env_vars = {"GLAB_DIMENSION_METRICS": "custom_field,another_field"}

        attributes = {
            "service.name": "gitlab-exporter",
            "status": "success",
            "custom_field": "custom_value",
            "another_field": "another_value",
            "filtered_field": "filtered",
            "duration": "200.0",
        }

        with patch.dict(os.environ, env_vars):
            duration, queued_duration, metrics_attrs = parse_metrics_attributes(
                attributes
            )

            assert duration == 200.0
            assert queued_duration == 0  # Default when not present
            assert "custom_field" in metrics_attrs
            assert "another_field" in metrics_attrs
            assert "filtered_field" not in metrics_attrs

    def test_parse_metrics_attributes_missing_durations(self):
        """Test parse_metrics_attributes handles missing duration fields."""
        attributes = {"service.name": "gitlab-exporter", "status": "success"}

        duration, queued_duration, metrics_attrs = parse_metrics_attributes(attributes)

        assert duration == 0
        assert queued_duration == 0
        assert len(metrics_attrs) > 0

    def test_parse_metrics_attributes_malformed_config(self, clean_environment):
        """Test parse_metrics_attributes handles malformed GLAB_DIMENSION_METRICS."""
        env_vars = {"GLAB_DIMENSION_METRICS": ""}  # Empty config

        attributes = {
            "service.name": "gitlab-exporter",
            "status": "success",
            "duration": "100.0",
        }

        with patch.dict(os.environ, env_vars):
            duration, queued_duration, metrics_attrs = parse_metrics_attributes(
                attributes
            )

            # Should fall back to defaults
            assert duration == 100.0
            assert "service.name" in metrics_attrs
            assert "status" in metrics_attrs


class TestIntegrationScenarios:
    """Test suite for integration scenarios combining multiple functions."""

    def test_complete_job_attribute_parsing(self):
        """Test complete job attribute parsing workflow."""
        job_data = {
            "id": 12345,
            "name": "build:docker",
            "status": "success",
            "stage": "build",
            "started_at": "2024-01-01T10:00:00Z",
            "finished_at": "2024-01-01T10:05:00Z",
            "duration": 300.0,
            "runner": {
                "id": 1,
                "description": "docker-runner",
                "tags": ["docker", "linux", "x64"],
            },
            "artifacts": [
                {"name": "binary", "size": 1024},
                {"name": "logs", "size": 512},
            ],
            "variables": '{"ENV": "production", "VERSION": "1.0.0"}',
        }

        result = parse_attributes(job_data)

        # Verify basic attributes
        assert result["id"] == "12345"
        assert result["name"] == "build:docker"
        assert result["status"] == "success"

        # Verify nested object flattening
        assert result["runner.id"] == "1"
        assert result["runner.description"] == "docker-runner"

        # Verify array flattening
        assert result["runner.tags[0]"] == "docker"
        assert result["runner.tags[1]"] == "linux"
        assert result["runner.tags[2]"] == "x64"

        # Verify nested array of objects
        assert result["artifacts[0].name"] == "binary"
        assert result["artifacts[0].size"] == "1024"
        assert result["artifacts[1].name"] == "logs"
        assert result["artifacts[1].size"] == "512"

        # Verify JSON string parsing
        assert result["variables.env"] == "production"
        assert result["variables.version"] == "1.0.0"

    def test_pipeline_data_with_complex_nesting(self):
        """Test parsing complex pipeline data with deep nesting."""
        pipeline_data = {
            "id": 789,
            "project": {
                "id": 123,
                "namespace": {"name": "my-group", "path": "my-group"},
            },
            "jobs": [
                {"name": "test", "status": "success", "artifacts": []},
                {
                    "name": "deploy",
                    "status": "failed",
                    "failure_reason": "script_failure",
                },
            ],
        }

        result = parse_attributes(pipeline_data)

        assert result["id"] == "789"
        assert result["project.id"] == "123"
        assert result["project.namespace.name"] == "my-group"
        assert result["project.namespace.path"] == "my-group"
        assert result["jobs[0].name"] == "test"
        assert result["jobs[0].status"] == "success"
        assert result["jobs[1].name"] == "deploy"
        assert result["jobs[1].status"] == "failed"
        assert result["jobs[1].failure_reason"] == "script_failure"
