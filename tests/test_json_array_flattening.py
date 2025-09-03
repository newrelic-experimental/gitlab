"""
Tests for JSON and array flattening functionality in parse_attributes.

This test suite ensures that the enhanced parse_attributes function properly
handles JSON strings and arrays by flattening them appropriately.
"""

import pytest
import json
from shared.custom_parsers import (
    parse_attributes,
    _is_json_string,
    _flatten_json_string,
    _flatten_array,
)


class TestJsonStringDetection:
    """Test suite for JSON string detection."""

    def test_is_json_string_valid_object(self):
        """Test detection of valid JSON object strings."""
        json_obj = '{"key": "value", "number": 123}'
        assert _is_json_string(json_obj) is True

    def test_is_json_string_valid_array(self):
        """Test detection of valid JSON array strings."""
        json_array = '["item1", "item2", 123]'
        assert _is_json_string(json_array) is True

    def test_is_json_string_nested_json(self):
        """Test detection of nested JSON structures."""
        nested_json = '{"outer": {"inner": {"deep": "value"}}}'
        assert _is_json_string(nested_json) is True

    def test_is_json_string_invalid_json(self):
        """Test rejection of invalid JSON strings."""
        invalid_json = '{"key": "value"'  # Missing closing brace
        assert _is_json_string(invalid_json) is False

    def test_is_json_string_regular_string(self):
        """Test rejection of regular strings."""
        regular_string = "This is just a regular string"
        assert _is_json_string(regular_string) is False

    def test_is_json_string_empty_string(self):
        """Test rejection of empty strings."""
        assert _is_json_string("") is False
        assert _is_json_string("   ") is False

    def test_is_json_string_non_string_input(self):
        """Test rejection of non-string inputs."""
        assert _is_json_string(123) is False
        assert _is_json_string(None) is False
        assert _is_json_string({"key": "value"}) is False


class TestJsonStringFlattening:
    """Test suite for JSON string flattening."""

    def test_flatten_json_string_simple_object(self):
        """Test flattening of simple JSON object."""
        json_str = '{"name": "test", "status": "success"}'
        result = _flatten_json_string(json_str, "config")

        expected = {"config.name": "test", "config.status": "success"}
        assert result == expected

    def test_flatten_json_string_nested_object(self):
        """Test flattening of nested JSON object."""
        json_str = '{"database": {"host": "localhost", "port": 5432}}'
        result = _flatten_json_string(json_str, "config")

        expected = {"config.database.host": "localhost", "config.database.port": "5432"}
        assert result == expected

    def test_flatten_json_string_with_array(self):
        """Test flattening of JSON object containing arrays."""
        json_str = '{"tags": ["tag1", "tag2"], "name": "test"}'
        result = _flatten_json_string(json_str, "metadata")

        expected = {
            "metadata.tags[0]": "tag1",
            "metadata.tags[1]": "tag2",
            "metadata.name": "test",
        }
        assert result == expected

    def test_flatten_json_string_invalid_json(self):
        """Test handling of invalid JSON strings."""
        invalid_json = '{"key": "value"'  # Missing closing brace
        result = _flatten_json_string(invalid_json, "config")

        # Should return the original string as-is
        expected = {"config": invalid_json}
        assert result == expected


class TestArrayFlattening:
    """Test suite for array flattening."""

    def test_flatten_array_simple_values(self):
        """Test flattening of array with simple values."""
        array = ["item1", "item2", "item3"]
        result = _flatten_array(array, "tags")

        expected = {"tags[0]": "item1", "tags[1]": "item2", "tags[2]": "item3"}
        assert result == expected

    def test_flatten_array_mixed_types(self):
        """Test flattening of array with mixed data types."""
        array = ["string", 123, True, None]
        result = _flatten_array(array, "mixed")

        expected = {
            "mixed[0]": "string",
            "mixed[1]": "123",
            "mixed[2]": "True",
            # None values are filtered out by do_parse
        }
        assert result == expected

    def test_flatten_array_nested_objects(self):
        """Test flattening of array containing objects."""
        array = [{"name": "item1", "value": 100}, {"name": "item2", "value": 200}]
        result = _flatten_array(array, "items")

        expected = {
            "items[0].name": "item1",
            "items[0].value": "100",
            "items[1].name": "item2",
            "items[1].value": "200",
        }
        assert result == expected

    def test_flatten_array_nested_arrays(self):
        """Test flattening of array containing nested arrays."""
        array = [["a", "b"], ["c", "d"]]
        result = _flatten_array(array, "matrix")

        expected = {
            "matrix[0][0]": "a",
            "matrix[0][1]": "b",
            "matrix[1][0]": "c",
            "matrix[1][1]": "d",
        }
        assert result == expected

    def test_flatten_array_with_json_strings(self):
        """Test flattening of array containing JSON strings."""
        array = ['{"key": "value1"}', '{"key": "value2"}']
        result = _flatten_array(array, "configs")

        expected = {"configs[0].key": "value1", "configs[1].key": "value2"}
        assert result == expected

    def test_flatten_array_empty(self):
        """Test flattening of empty array."""
        array = []
        result = _flatten_array(array, "empty")

        assert result == {}


class TestParseAttributesEnhanced:
    """Test suite for enhanced parse_attributes functionality."""

    def test_parse_attributes_with_json_string(self):
        """Test parse_attributes with JSON string values."""
        obj = {
            "name": "test_job",
            "config": '{"timeout": 300, "retry": true}',
            "status": "success",
        }
        result = parse_attributes(obj)

        expected = {
            "name": "test_job",
            "config.timeout": "300",
            "config.retry": "True",
            "status": "success",
        }
        assert result == expected

    def test_parse_attributes_with_array(self):
        """Test parse_attributes with array values."""
        obj = {
            "name": "test_job",
            "tags": ["ci", "test", "production"],
            "status": "success",
        }
        result = parse_attributes(obj)

        expected = {
            "name": "test_job",
            "tags[0]": "ci",
            "tags[1]": "test",
            "tags[2]": "production",
            "status": "success",
        }
        assert result == expected

    def test_parse_attributes_complex_nested_structure(self):
        """Test parse_attributes with complex nested structures."""
        obj = {
            "job": {
                "name": "test_job",
                "config": '{"env": {"NODE_ENV": "production"}}',
                "artifacts": [
                    {"name": "report.xml", "size": 1024},
                    {"name": "coverage.json", "size": 2048},
                ],
            },
            "pipeline": {"variables": '["VAR1=value1", "VAR2=value2"]'},
        }
        result = parse_attributes(obj)

        expected = {
            "job.name": "test_job",
            "job.config.env.node_env": "production",
            "job.artifacts[0].name": "report.xml",
            "job.artifacts[0].size": "1024",
            "job.artifacts[1].name": "coverage.json",
            "job.artifacts[1].size": "2048",
            "pipeline.variables[0]": "VAR1=value1",
            "pipeline.variables[1]": "VAR2=value2",
        }
        assert result == expected

    def test_parse_attributes_gitlab_job_example(self):
        """Test parse_attributes with realistic GitLab job data."""
        gitlab_job = {
            "id": 12345,
            "name": "test:unit",
            "stage": "test",
            "status": "success",
            "variables": '{"CI_NODE_INDEX": "1", "CI_NODE_TOTAL": "3"}',
            "artifacts": [
                {"filename": "junit.xml", "file_type": "junit"},
                {"filename": "coverage.xml", "file_type": "cobertura"},
            ],
            "runner": {"description": "docker-runner", "tags": ["docker", "linux"]},
        }
        result = parse_attributes(gitlab_job)

        # Verify key flattened attributes exist
        assert "id" in result
        assert "variables.ci_node_index" in result
        assert "variables.ci_node_total" in result
        assert "artifacts[0].filename" in result
        assert "artifacts[1].file_type" in result
        assert "runner.description" in result
        assert "runner.tags[0]" in result
        assert "runner.tags[1]" in result

        # Verify values are correctly flattened
        assert result["variables.ci_node_index"] == "1"
        assert result["artifacts[0].filename"] == "junit.xml"
        assert result["runner.tags[0]"] == "docker"

    def test_parse_attributes_handles_malformed_json(self):
        """Test parse_attributes gracefully handles malformed JSON."""
        obj = {
            "name": "test_job",
            "config": '{"timeout": 300, "retry":}',  # Malformed JSON
            "status": "success",
        }
        result = parse_attributes(obj)

        expected = {
            "name": "test_job",
            "config": '{"timeout": 300, "retry":}',  # Should be kept as-is
            "status": "success",
        }
        assert result == expected

    def test_parse_attributes_filters_none_values_in_arrays(self):
        """Test that None values in arrays are properly filtered."""
        obj = {"tags": ["valid", None, "also_valid", ""], "name": "test"}
        result = parse_attributes(obj)

        expected = {
            "tags[0]": "valid",
            "tags[1]": "also_valid",
            # None and empty string should be filtered out
            "name": "test",
        }
        assert result == expected

    def test_parse_attributes_deeply_nested_json_arrays(self):
        """Test parse_attributes with deeply nested JSON and arrays."""
        obj = {
            "metadata": '{"environments": [{"name": "prod", "config": {"replicas": 3}}]}'
        }
        result = parse_attributes(obj)

        expected = {
            "metadata.environments[0].name": "prod",
            "metadata.environments[0].config.replicas": "3",
        }
        assert result == expected


class TestIntegrationWithProcessors:
    """Integration tests to ensure the enhanced functionality works with processors."""

    def test_integration_with_job_processor_data(self):
        """Test integration with typical job processor data structures."""
        # Simulate data that might come from GitLab API
        job_data = {
            "id": 123,
            "name": "build:docker",
            "stage": "build",
            "variables": json.dumps(
                {"DOCKER_IMAGE": "node:16", "BUILD_ARGS": ["--no-cache", "--pull"]}
            ),
            "artifacts": [
                {"name": "image.tar", "expire_at": "2024-01-01T00:00:00Z"},
                {"name": "manifest.json", "expire_at": "2024-01-01T00:00:00Z"},
            ],
        }

        result = parse_attributes(job_data)

        # Verify complex flattening works correctly
        assert "variables.docker_image" in result
        assert "variables.build_args[0]" in result
        assert "variables.build_args[1]" in result
        assert "artifacts[0].name" in result
        assert "artifacts[1].expire_at" in result

        assert result["variables.docker_image"] == "node:16"
        assert result["variables.build_args[0]"] == "--no-cache"
        assert result["artifacts[0].name"] == "image.tar"
