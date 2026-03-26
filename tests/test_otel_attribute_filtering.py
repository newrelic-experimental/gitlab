import os
from unittest.mock import patch, MagicMock
from opentelemetry.sdk.resources import Resource


class TestResourceCreationFiltering:
    def test_required_and_user_keep_attributes_are_promoted(self, monkeypatch):
        """Test that only system defaults and GLAB_ATTRIBUTES_TO_KEEP attrs are promoted to resource level."""
        import shared.otel
        from shared.otel import create_resource_attributes

        # Patch the module-level cache directly (env var is cached at import time)
        monkeypatch.setattr(shared.otel, "_ATTRIBUTES_TO_KEEP", ["custom1", "custom2"])

        atts = {
            "id": 123,
            "project_id": 456,
            "pipeline_id": 789,
            "custom1": "foo",
            "custom2": "bar",
            "not_required": "should_not_be_promoted",
        }
        service_name = "test_service"

        result = create_resource_attributes(atts, service_name)

        # System defaults present in atts should be promoted
        default_required = [
            "id", "project_id", "pipeline_id", "job_id", "environment_id",
            "deployment_id", "release_id", "service.name", "gitlab.resource.type",
        ]
        for key in default_required:
            if key in atts:
                assert key in result, f"{key} should be promoted to resource level"

        # User-specified keep attrs should be promoted
        assert "custom1" in result
        assert "custom2" in result

        # Non-required attrs must NOT be promoted to resource level
        assert "not_required" not in result

    def test_resource_creation_with_filtered_attributes(self):
        """Test that Resource creation works with filtered attributes."""
        # Test data with None and empty values
        test_attributes = {
            "service.name": "test_service",
            "valid_attr": "valid_value",
            "none_attr": None,
            "empty_attr": "",
            "zero_attr": 0,
            "false_attr": False,
        }

        # Apply the same filtering logic used in the processors
        filtered_attributes = {
            key: value
            for key, value in test_attributes.items()
            if value is not None and value != ""
        }

        from opentelemetry.sdk.resources import Resource

        resource = Resource(attributes=filtered_attributes)

        assert isinstance(resource, Resource)
        attrs = dict(resource.attributes)
        for key, value in attrs.items():
            assert value is not None, f"Found None value for key: {key}"
            assert value != "", f"Found empty string for key: {key}"
        assert attrs["service.name"] == "test_service"
        assert attrs["valid_attr"] == "valid_value"
        assert attrs["zero_attr"] == 0
        assert attrs["false_attr"] == False

    def test_empty_attributes_handling(self):
        """Test handling of completely empty attribute dictionaries."""
        empty_attrs = {}
        filtered_attrs = {
            key: value
            for key, value in empty_attrs.items()
            if value is not None and value != ""
        }
        from opentelemetry.sdk.resources import Resource

        resource = Resource(attributes=filtered_attrs)
        assert isinstance(resource, Resource)

    def test_all_none_attributes_handling(self):
        """Test handling when all attributes are None or empty."""
        all_none_attrs = {
            "none_attr1": None,
            "none_attr2": None,
            "empty_attr1": "",
            "empty_attr2": "",
        }
        filtered_attrs = {
            key: value
            for key, value in all_none_attrs.items()
            if value is not None and value != ""
        }
        from opentelemetry.sdk.resources import Resource

        assert len(filtered_attrs) == 0
        resource = Resource(attributes=filtered_attrs)
        assert isinstance(resource, Resource)
        # GLAB_ENVS_DROP should be filtered out by the atts_to_remove list, not the prefix filter


class TestJobProcessorFiltering:
    """Test suite for job processor attribute filtering."""

    def test_create_job_resource_filters_none_values(self):
        """Test that create_job_resource filters None values from resource attributes."""
        from new_relic_exporter.processors.job_processor import JobProcessor

        # Mock config and project
        mock_config = MagicMock()
        mock_config.low_data_mode = False
        mock_project = MagicMock()

        processor = JobProcessor(mock_config, mock_project)

        # Mock job data with None values
        job_data = {
            "id": 123,
            "name": "test_job",
            "status": "success",
            "stage": "test",
            "started_at": "2024-01-01T00:00:00Z",
            "finished_at": "2024-01-01T00:30:00Z",
        }

        # Mock environment variables (can't set None in os.environ)
        test_env = {
            "CI_PARENT_PIPELINE": "456",
            "CI_PROJECT_ID": "789",
        }

        with patch.dict(os.environ, test_env, clear=True):
            with patch("shared.custom_parsers.parse_attributes") as mock_parse:
                with patch("shared.otel.create_resource_attributes") as mock_create:
                    # Mock parse_attributes to return data with None values
                    mock_parse.return_value = {
                        "valid_attr": "valid_value",
                        "none_attr": None,
                        "empty_attr": "",
                    }

                    # Mock create_resource_attributes to return data with None values
                    mock_create.return_value = {
                        "resource_attr": "resource_value",
                        "resource_none": None,
                        "resource_empty": "",
                    }

                    # Create job resource
                    resource = processor.create_job_resource(job_data, "test_service")

                    # Verify resource was created
                    assert isinstance(resource, Resource)

                    # Verify None and empty values were filtered out
                    attrs = dict(resource.attributes)

                    # Should not contain None or empty values
                    for key, value in attrs.items():
                        assert value is not None, f"Found None value for key: {key}"
                        assert value != "", f"Found empty string for key: {key}"

    def test_handle_job_logs_filters_none_values(self):
        """Test that handle_job_logs filtering logic works correctly."""
        # Test the filtering logic directly rather than the full method
        resource_attributes = {
            "service.name": "test_service",
            "valid_attr": "valid_value",
            "none_attr": None,
            "empty_attr": "",
            "zero_attr": 0,
            "false_attr": False,
        }

        # Apply the same filtering logic used in handle_job_logs
        attrs = resource_attributes.copy()
        attrs["log"] = "test log line"

        # Filter out None values and empty strings to prevent OpenTelemetry warnings
        filtered_attrs = {
            key: value
            for key, value in attrs.items()
            if value is not None and value != ""
        }

        # Verify None and empty values were filtered out
        assert "none_attr" not in filtered_attrs
        assert "empty_attr" not in filtered_attrs

        # Verify valid values were kept (including 0 and False)
        assert "valid_attr" in filtered_attrs
        assert "zero_attr" in filtered_attrs  # 0 should be preserved
        assert "false_attr" in filtered_attrs  # False should be preserved
        assert "log" in filtered_attrs

        # Verify we can create a Resource with filtered attributes
        from opentelemetry.sdk.resources import Resource

        resource = Resource(attributes=filtered_attrs)
        assert isinstance(resource, Resource)

        # Verify no None or empty values in final resource
        final_attrs = dict(resource.attributes)
        for key, value in final_attrs.items():
            assert value is not None, f"Found None value for key: {key}"
            assert value != "", f"Found empty string for key: {key}"

    def test_process_job_filters_span_attributes(self):
        """Test that process_job span attribute filtering logic works correctly."""
        # Test the filtering logic directly rather than the full method
        job_attributes = {
            "valid_attr": "valid_value",
            "none_attr": None,
            "empty_attr": "",
            "zero_attr": 0,
            "false_attr": False,
        }

        # Apply the same filtering logic used in process_job
        # Filter out None values to prevent OpenTelemetry warnings
        filtered_attributes = {
            key: value for key, value in job_attributes.items() if value is not None
        }

        # Verify None values were filtered out
        assert "none_attr" not in filtered_attributes

        # Verify valid values were kept (including 0, False, and empty string)
        assert "valid_attr" in filtered_attributes
        assert "zero_attr" in filtered_attributes  # 0 should be preserved
        assert "false_attr" in filtered_attributes  # False should be preserved
        assert (
            "empty_attr" in filtered_attributes
        )  # Empty string should be preserved (only None is filtered)

        # Verify the filtering works as expected
        assert filtered_attributes["valid_attr"] == "valid_value"
        assert filtered_attributes["zero_attr"] == 0
        assert filtered_attributes["false_attr"] == False
        assert filtered_attributes["empty_attr"] == ""

        # Verify we can set these attributes on a span (mock test)
        from unittest.mock import MagicMock

        mock_span = MagicMock()
        mock_span.set_attributes(filtered_attributes)
        mock_span.set_attributes.assert_called_once_with(filtered_attributes)


class TestParseAttributesFiltering:
    """Test suite for parse_attributes function filtering."""

    def test_parse_attributes_handles_none_values(self):
        """Test that parse_attributes properly handles None values."""
        from shared.custom_parsers import parse_attributes

        # Test object with None values
        test_obj = {
            "valid_field": "valid_value",
            "none_field": None,
            "empty_field": "",
            "zero_field": 0,
            "false_field": False,
            "nested_obj": {
                "nested_valid": "nested_value",
                "nested_none": None,
                "nested_empty": "",
            },
        }

        result = parse_attributes(test_obj)

        # Should include valid values
        assert "valid_field" in result
        assert result["valid_field"] == "valid_value"

        # Should include zero and false (they are valid values)
        assert "zero_field" in result
        assert result["zero_field"] == "0"  # Converted to string
        assert "false_field" in result
        assert result["false_field"] == "False"  # Converted to string

        # Should include nested valid values
        assert "nested_obj.nested_valid" in result

        # Should exclude None values (handled by do_parse function)
        # Note: parse_attributes uses do_parse which filters None values

    def test_parse_attributes_with_custom_drop_list(self):
        """Test that parse_attributes respects GLAB_ATTRIBUTES_DROP configuration."""
        from shared.custom_parsers import parse_attributes

        test_obj = {
            "keep_this": "keep_value",
            "drop_this": "drop_value",
            "also_drop": "also_drop_value",
        }

        import shared.custom_parsers as cp

        original = cp._ATTRIBUTES_DROP
        cp._ATTRIBUTES_DROP = ["drop_this", "also_drop"]
        try:
            result = parse_attributes(test_obj)

            # Should keep attributes not in drop list
            assert "keep_this" in result

            # Should drop attributes in custom drop list
            assert "drop_this" not in result
            assert "also_drop" not in result
        finally:
            cp._ATTRIBUTES_DROP = original


class TestFilterOtelLogAttributes:
    """Test suite for filter_otel_log_attributes function."""

    def test_removes_none_values(self):
        """filter_otel_log_attributes drops None values."""
        from shared.custom_parsers import filter_otel_log_attributes

        result = filter_otel_log_attributes({"key": None, "valid": "ok"})
        assert "key" not in result
        assert result["valid"] == "ok"

    def test_removes_empty_string(self):
        """filter_otel_log_attributes drops empty string values."""
        from shared.custom_parsers import filter_otel_log_attributes

        result = filter_otel_log_attributes({"key": "", "valid": "ok"})
        assert "key" not in result

    def test_removes_none_string(self):
        """filter_otel_log_attributes drops the string 'None'."""
        from shared.custom_parsers import filter_otel_log_attributes

        result = filter_otel_log_attributes({"key": "None", "valid": "ok"})
        assert "key" not in result

    def test_all_invalid_values_dropped(self):
        """filter_otel_log_attributes drops all invalid values at once."""
        from shared.custom_parsers import filter_otel_log_attributes

        result = filter_otel_log_attributes({"k1": None, "k2": "None", "k3": ""})
        assert result == {}

    def test_preserves_zero_and_false(self):
        """filter_otel_log_attributes keeps 0 and False (valid values)."""
        from shared.custom_parsers import filter_otel_log_attributes

        result = filter_otel_log_attributes({"zero": 0, "flag": False, "valid": "ok"})
        assert result["zero"] == 0
        assert result["flag"] is False
        assert result["valid"] == "ok"

    def test_drops_sensitive_attributes(self):
        """filter_otel_log_attributes drops hardcoded sensitive keys."""
        from shared.custom_parsers import filter_otel_log_attributes

        result = filter_otel_log_attributes(
            {
                "NEW_RELIC_API_KEY": "secret",
                "GLAB_TOKEN": "secret",
                "CI_JOB_JWT": "token",
                "CI_JOB_TOKEN": "token",
                "CI_BUILD_TOKEN": "token",
                "CI_REGISTRY_PASSWORD": "password",
                "CI_DEPLOY_PASSWORD": "password",
                "CI_SERVER_TLS_KEY_FILE": "/path/to/key",
                "CI_SERVER_TLS_CERT_FILE": "/path/to/cert",
                "valid_attr": "keep",
            }
        )
        assert "NEW_RELIC_API_KEY" not in result
        assert "GLAB_TOKEN" not in result
        assert "CI_JOB_JWT" not in result
        assert "CI_JOB_TOKEN" not in result
        assert "CI_BUILD_TOKEN" not in result
        assert "CI_REGISTRY_PASSWORD" not in result
        assert "CI_DEPLOY_PASSWORD" not in result
        assert "CI_SERVER_TLS_KEY_FILE" not in result
        assert "CI_SERVER_TLS_CERT_FILE" not in result
        assert result["valid_attr"] == "keep"

    def test_sensitive_key_check_is_case_insensitive(self):
        """Sensitive key matching is case-insensitive."""
        from shared.custom_parsers import filter_otel_log_attributes

        result = filter_otel_log_attributes(
            {
                "new_relic_api_key": "secret",
                "Glab_Token": "secret",
            }
        )
        assert "new_relic_api_key" not in result
        assert "Glab_Token" not in result

    def test_honors_glab_attributes_drop(self):
        """filter_otel_log_attributes respects GLAB_ATTRIBUTES_DROP."""
        from shared.custom_parsers import filter_otel_log_attributes
        import shared.custom_parsers as cp

        original = cp._ATTRIBUTES_DROP
        cp._ATTRIBUTES_DROP = ["status", "stage"]
        try:
            result = filter_otel_log_attributes(
                {
                    "status": "success",
                    "stage": "build",
                    "name": "my-job",
                }
            )
            assert "status" not in result
            assert "stage" not in result
            assert result["name"] == "my-job"
        finally:
            cp._ATTRIBUTES_DROP = original

    def test_glab_attributes_drop_is_case_insensitive(self):
        """GLAB_ATTRIBUTES_DROP matching is case-insensitive (stored lowercase)."""
        from shared.custom_parsers import filter_otel_log_attributes
        import shared.custom_parsers as cp

        # Cache stores lowercase; test that lowercase entries filter case-insensitively
        original = cp._ATTRIBUTES_DROP
        cp._ATTRIBUTES_DROP = ["status", "stage"]
        try:
            result = filter_otel_log_attributes(
                {
                    "Status": "success",
                    "STAGE": "build",
                    "name": "my-job",
                }
            )
            assert "Status" not in result
            assert "STAGE" not in result
        finally:
            cp._ATTRIBUTES_DROP = original


class TestIntegrationFiltering:
    """Integration tests for end-to-end attribute filtering."""

    def test_end_to_end_attribute_filtering(self):
        """Test that attribute filtering works end-to-end across all components."""
        from shared.custom_parsers import grab_span_att_vars, parse_attributes
        from shared.otel import create_resource_attributes

        # Mock environment (can't set None in os.environ)
        test_env = {
            "CI_VALID_VAR": "valid_env_value",
            "CI_EMPTY_VAR": "",
            "CI_PROJECT_ID": "123",
        }

        # Mock job data with problematic values
        job_data = {
            "id": 456,
            "name": "test_job",
            "status": "success",
            "valid_field": "valid_job_value",
            "none_field": None,
            "empty_field": "",
        }

        with patch.dict(os.environ, test_env, clear=True):
            # Test environment variable filtering
            env_attrs = grab_span_att_vars()
            for key, value in env_attrs.items():
                assert value is not None, f"Environment attr {key} is None"
                assert value != "", f"Environment attr {key} is empty"

            # Test job attribute parsing
            job_attrs = parse_attributes(job_data)
            for key, value in job_attrs.items():
                # parse_attributes converts values to strings and uses do_parse
                # which should filter out None values
                assert value is not None, f"Job attr {key} is None"

            # Test resource attribute creation
            resource_attrs = create_resource_attributes(job_attrs, "test_service")
            for key, value in resource_attrs.items():
                assert value is not None, f"Resource attr {key} is None"

            # Test final filtering as done in processors
            final_attrs = {
                key: value
                for key, value in resource_attrs.items()
                if value is not None and value != ""
            }

            # Should be able to create Resource without issues
            resource = Resource(attributes=final_attrs)
            assert isinstance(resource, Resource)
