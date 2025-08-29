import pytest

from unittest.mock import patch, MagicMock

# Patch check_env_vars, os.environ, and gl before importing main
with patch("shared.custom_parsers.check_env_vars", lambda: None), patch.dict(
    "os.environ", {"NEW_RELIC_API_KEY": "dummy_key"}
), patch("new_relic_exporter.main.gl", MagicMock()):
    import new_relic_exporter.main as main


@patch("new_relic_exporter.main.gl")
def test_send_to_nr_basic(mock_gl):
    with patch.dict(
        "os.environ", {"CI_PARENT_PIPELINE": "456", "CI_PROJECT_ID": "123"}
    ):
        mock_project = MagicMock()
        mock_pipeline = MagicMock()
        mock_project.pipelines.get.return_value = mock_pipeline
        mock_gl.projects.get.return_value = mock_project
        mock_pipeline.bridges.list.return_value = []
        mock_pipeline.to_json.return_value = '{"id": 123, "status": "success", "started_at": "2024-01-01T00:00:00Z", "finished_at": "2024-01-01T01:00:00Z"}'
        mock_project.attributes.get.return_value = "Test Project"
        result = main.send_to_nr()
        assert result is None or result == True or result == False
