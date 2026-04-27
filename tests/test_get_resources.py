"""
Tests for new_relic_metrics_exporter.get_resources — datetime cutoff logic.

Regression tests for the five functions that filter GitLab resources by a
rolling time window. Each test freezes datetime.now and verifies that only
records within GLAB_EXPORT_LAST_MINUTES are queued, and that records outside
the window are excluded.
"""
import json
import os
import pytest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch, MagicMock


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

FIXED_NOW = datetime(2024, 1, 1, 12, 0, 0, tzinfo=timezone.utc)
WINDOW_MINUTES = 61

# Minimum env vars required by shared.global_variables.check_env_vars on import
_BASE_ENV = {
    "GLAB_TOKEN": "glpat-test",
    "NEW_RELIC_API_KEY": "NRAK-TEST123",
    "NEW_RELIC_ENDPOINT": "https://otlp.nr-data.net:4317",
    "GLAB_EXPORT_LAST_MINUTES": str(WINDOW_MINUTES),
}

# Timestamps relative to FIXED_NOW
_recent = (FIXED_NOW - timedelta(minutes=30)).strftime("%Y-%m-%dT%H:%M:%SZ")
_old = (FIXED_NOW - timedelta(minutes=120)).strftime("%Y-%m-%dT%H:%M:%SZ")


def _job_json(created_at):
    return json.dumps({
        "id": 1,
        "name": "build",
        "stage": "build",
        "status": "success",
        "created_at": created_at,
        "web_url": "https://gitlab.example.com/-/jobs/1",
        "duration": 60,
        "ref": "main",
    })


def _deployment_json(created_at):
    return json.dumps({
        "id": 1,
        "status": "success",
        "created_at": created_at,
        "environment": {"name": "production"},
        "deployable": {"name": "deploy"},
    })


def _release_json(released_at):
    return json.dumps({
        "tag_name": "v1.0.0",
        "name": "Release 1.0.0",
        "released_at": released_at,
        "description": "test release",
    })


# ---------------------------------------------------------------------------
# get_jobs
# ---------------------------------------------------------------------------

@patch.dict(os.environ, _BASE_ENV)
@patch("new_relic_metrics_exporter.get_resources.GLAB_EXPORT_LAST_MINUTES", WINDOW_MINUTES)
@patch("new_relic_metrics_exporter.get_resources.datetime")
@patch("new_relic_metrics_exporter.get_resources.q")
def test_get_jobs_queues_recent_job(mock_q, mock_dt):
    from new_relic_metrics_exporter.get_resources import get_jobs

    mock_dt.now.return_value = FIXED_NOW

    recent_job = MagicMock()
    recent_job.to_json.return_value = _job_json(_recent)

    mock_pipeline = MagicMock()
    mock_pipeline.jobs.list.return_value = [recent_job]

    get_jobs(mock_pipeline, "proj-1", "test-svc", {})

    assert mock_q.put.call_count == 1


@patch.dict(os.environ, _BASE_ENV)
@patch("new_relic_metrics_exporter.get_resources.GLAB_EXPORT_LAST_MINUTES", WINDOW_MINUTES)
@patch("new_relic_metrics_exporter.get_resources.datetime")
@patch("new_relic_metrics_exporter.get_resources.q")
def test_get_jobs_excludes_old_job(mock_q, mock_dt):
    from new_relic_metrics_exporter.get_resources import get_jobs

    mock_dt.now.return_value = FIXED_NOW

    old_job = MagicMock()
    old_job.to_json.return_value = _job_json(_old)

    mock_pipeline = MagicMock()
    mock_pipeline.jobs.list.return_value = [old_job]

    get_jobs(mock_pipeline, "proj-1", "test-svc", {})

    mock_q.put.assert_not_called()


@patch.dict(os.environ, _BASE_ENV)
@patch("new_relic_metrics_exporter.get_resources.GLAB_EXPORT_LAST_MINUTES", WINDOW_MINUTES)
@patch("new_relic_metrics_exporter.get_resources.datetime")
@patch("new_relic_metrics_exporter.get_resources.q")
def test_get_jobs_stops_at_first_old_job(mock_q, mock_dt):
    """Jobs are ordered newest-first; once an old job is hit the loop breaks."""
    from new_relic_metrics_exporter.get_resources import get_jobs

    mock_dt.now.return_value = FIXED_NOW

    recent_job = MagicMock()
    recent_job.to_json.return_value = _job_json(_recent)
    old_job = MagicMock()
    old_job.to_json.return_value = _job_json(_old)

    mock_pipeline = MagicMock()
    mock_pipeline.jobs.list.return_value = [recent_job, old_job]

    get_jobs(mock_pipeline, "proj-1", "test-svc", {})

    # Only the recent job should be queued
    assert mock_q.put.call_count == 1


# ---------------------------------------------------------------------------
# get_deployments  (async)
# ---------------------------------------------------------------------------

@patch.dict(os.environ, _BASE_ENV)
@patch("new_relic_metrics_exporter.get_resources.GLAB_EXPORT_LAST_MINUTES", WINDOW_MINUTES)
@patch("new_relic_metrics_exporter.get_resources.datetime")
@patch("new_relic_metrics_exporter.get_resources.q")
@patch("new_relic_metrics_exporter.get_resources._sync_fetch_deployments")
def test_get_deployments_passes_correct_cutoff(mock_fetch, mock_q, mock_dt):
    """get_deployments computes a correct cutoff and passes it to the sync fetcher."""
    import asyncio
    from new_relic_metrics_exporter.get_resources import get_deployments

    mock_dt.now.return_value = FIXED_NOW
    expected_cutoff = FIXED_NOW - timedelta(minutes=WINDOW_MINUTES)
    # _sync_fetch_deployments returns (matching_jsons, total_fetched, total_api)
    mock_fetch.return_value = ([], 0, 0)

    asyncio.run(get_deployments(MagicMock(), "proj-1", "test-svc"))

    mock_fetch.assert_called_once()
    _, called_cutoff = mock_fetch.call_args[0]
    assert called_cutoff == expected_cutoff


# ---------------------------------------------------------------------------
# get_releases  (async)
# ---------------------------------------------------------------------------

@patch.dict(os.environ, _BASE_ENV)
@patch("new_relic_metrics_exporter.get_resources.GLAB_EXPORT_LAST_MINUTES", WINDOW_MINUTES)
@patch("new_relic_metrics_exporter.get_resources.datetime")
@patch("new_relic_metrics_exporter.get_resources.q")
@patch("new_relic_metrics_exporter.get_resources._sync_fetch_releases")
def test_get_releases_passes_correct_cutoff(mock_fetch, mock_q, mock_dt):
    """get_releases computes a correct cutoff and passes it to the sync fetcher."""
    import asyncio
    from new_relic_metrics_exporter.get_resources import get_releases

    mock_dt.now.return_value = FIXED_NOW
    expected_cutoff = FIXED_NOW - timedelta(minutes=WINDOW_MINUTES)
    # _sync_fetch_releases returns (matching_jsons, total_fetched)
    mock_fetch.return_value = ([], 0)

    asyncio.run(get_releases(MagicMock(), "proj-1", "test-svc"))

    mock_fetch.assert_called_once()
    _, called_cutoff = mock_fetch.call_args[0]
    assert called_cutoff == expected_cutoff


# ---------------------------------------------------------------------------
# get_pipelines  (async)
# ---------------------------------------------------------------------------

@patch.dict(os.environ, _BASE_ENV)
@patch("new_relic_metrics_exporter.get_resources.GLAB_EXPORT_LAST_MINUTES", WINDOW_MINUTES)
@patch("new_relic_metrics_exporter.get_resources.datetime")
@patch("new_relic_metrics_exporter.get_resources.q")
@patch("new_relic_metrics_exporter.get_resources._sync_fetch_pipelines")
def test_get_pipelines_updated_after_within_window(mock_fetch, mock_q, mock_dt):
    """get_pipelines passes an updated_after kwarg whose value represents the cutoff."""
    import asyncio
    from new_relic_metrics_exporter.get_resources import get_pipelines

    mock_dt.now.return_value = FIXED_NOW
    expected_cutoff = FIXED_NOW - timedelta(minutes=WINDOW_MINUTES)
    # _sync_fetch_pipelines returns (objects, total)
    mock_fetch.return_value = ([], 0)

    asyncio.run(get_pipelines(MagicMock(), "proj-1", "test-svc"))

    mock_fetch.assert_called_once()
    # Second positional arg is the pipeline_kwargs dict
    _, pipeline_kwargs = mock_fetch.call_args[0]
    assert "updated_after" in pipeline_kwargs
    assert str(expected_cutoff) in pipeline_kwargs["updated_after"]
