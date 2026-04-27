"""
Import smoke tests — verify that key modules load without NameError or ImportError.

These tests catch regressions like a missing import or a renamed symbol at module
scope, which only surface at runtime otherwise (no dedicated unit tests exist for
these modules). They intentionally do nothing beyond importing.
"""
import os
import pytest
from unittest.mock import patch, MagicMock


def test_import_job_processor():
    from new_relic_exporter.processors.job_processor import JobProcessor  # noqa: F401


@patch("shared.otel.get_otel_logger", return_value=MagicMock())
@patch("shared.otel.get_meter", return_value=MagicMock())
@patch.dict(os.environ, {
    "NEW_RELIC_ENDPOINT": "https://otlp.nr-data.net:4317",
    "NEW_RELIC_API_KEY": "NRAK-TEST123",
    "GLAB_TOKEN": "glpat-test",
})
def test_import_get_resources(mock_meter, mock_logger):
    import importlib
    import sys
    # Force re-import so the test actually exercises the module-level code
    sys.modules.pop("new_relic_metrics_exporter.get_resources", None)
    import new_relic_metrics_exporter.get_resources  # noqa: F401
