import json
import os
import threading
from datetime import datetime, timedelta, date, timezone
from typing import Dict, Any
import zulu
from opentelemetry.sdk.resources import Resource
from shared.otel import get_otel_logger, create_resource_attributes, get_meter
from shared.custom_parsers import parse_attributes, parse_metrics_attributes, do_parse, filter_otel_log_attributes
from opentelemetry.sdk.resources import SERVICE_NAME
from shared.logging.structured_logger import (
    get_logger as get_structured_logger,
    LogContext,
)
import re
from shared.global_variables import *
from shared.global_variables import OTEL_EXPORTER_TYPE
from shared.config.settings import get_config
from shared.utils import generate_service_name

# Cache config at module level — env vars don't change at runtime
_config = get_config()
import requests
import logging
import asyncio
import time
import concurrent.futures

# Global settings for logger,tracer,meter
global_resource_attributes = {
    "instrumentation.name": "gitlab-integration",
    "gitlab.source": "gitlab-metrics-exporter",
}
global_resource = Resource(attributes=global_resource_attributes)

# Global logger
global_logger = get_otel_logger(
    endpoint, headers, global_resource, "global_logger", OTEL_EXPORTER_TYPE
)

# General executor for all blocking python-gitlab list() API calls (pipelines,
# deployments, environments, releases). Keeps the asyncio event loop free so
# concurrent project coroutines actually run in parallel.
_executor = concurrent.futures.ThreadPoolExecutor(
    max_workers=int(os.getenv("GLAB_API_WORKERS", "50")),
    thread_name_prefix="glab-api",
)

# Dedicated executor for per-pipeline job fetches (can be tuned independently).
_job_executor = concurrent.futures.ThreadPoolExecutor(
    max_workers=int(os.getenv("GLAB_JOB_WORKERS", "20")),
    thread_name_prefix="glab-jobs",
)

# Cache GLAB_EXCLUDE_JOBS at module level — env vars don't change at runtime
_exclude_jobs: list = [
    j.strip().lower()
    for j in os.getenv("GLAB_EXCLUDE_JOBS", "").split(",")
    if j.strip()
]

# Pre-compile project regex — avoids recompilation on every project evaluation
_projects_regex = re.compile(str(GLAB_EXPORT_PROJECTS_REGEX))

# Structured logger for this module
structured_logger = get_structured_logger("gitlab-metrics-exporter", "get-resources")

# Flag to log data collection mode only once per collection run
_data_collection_mode_logged = False

# Thread-safe run stats — accumulates estate/window counts during a collection cycle
_run_stats_lock = threading.Lock()
_run_stats = {
    "pipeline_statuses": {},
    "job_statuses": {},
    "environments_total": 0,
    "runners_total": 0,
    "runners_online": 0,
    "runners_offline": 0,
    "runners_active": 0,
    "runners_paused": 0,
}


def reset_collection_flags():
    """Reset per-run flags. Call at the start of each collection cycle."""
    global _data_collection_mode_logged, _run_stats
    _data_collection_mode_logged = False
    with _run_stats_lock:
        _run_stats = {
            "pipeline_statuses": {},
            "job_statuses": {},
            "environments_total": 0,
            "runners_total": 0,
            "runners_online": 0,
            "runners_offline": 0,
            "runners_active": 0,
            "runners_paused": 0,
        }


def get_run_stats() -> dict:
    """Return a copy of accumulated run stats."""
    with _run_stats_lock:
        return dict(_run_stats)

# Global meter
global_meter = get_meter(endpoint, headers, global_resource, "global_meter")
gitlab_pipelines_duration = global_meter.create_histogram(
    "gitlab_pipelines.duration"
)
gitlab_pipelines_queued_duration = global_meter.create_histogram(
    "gitlab_pipelines.queued_duration"
)
gitlab_jobs_duration = global_meter.create_histogram("gitlab_jobs.duration")
gitlab_jobs_queued_duration = global_meter.create_histogram(
    "gitlab_jobs.queued_duration"
)

# DORA metric counters — created once at module level to avoid duplicate instrument warnings
_DORA_METRIC_NAMES = [
    "deployment_frequency",
    "lead_time_for_changes",
    "time_to_restore_service",
    "change_failure_rate",
]
dora_counters = {
    name: global_meter.create_counter(f"gitlab_dora_{name}")
    for name in _DORA_METRIC_NAMES
}


def get_runners():
    try:
        runners = []
        if GLAB_RUNNERS_INSTANCE:
            if "all" in GLAB_RUNNERS_SCOPE and len(GLAB_RUNNERS_SCOPE) == 1:
                runners = gl.runners_all.list(get_all=True)
            else:
                for scope in GLAB_RUNNERS_SCOPE:
                    runners.extend(gl.runners_all.list(scope=scope, get_all=True))
        else:
            if "all" in GLAB_RUNNERS_SCOPE and len(GLAB_RUNNERS_SCOPE) == 1:
                runners = gl.runners.list(get_all=True)
            else:
                for scope in GLAB_RUNNERS_SCOPE:
                    runners.extend(gl.runners.list(scope=scope, get_all=True))

        if len(runners) == 0:
            context = LogContext(
                service_name="gitlab-metrics-exporter",
                component="get-resources",
                operation="get_runners",
            )
            structured_logger.info(
                "No runners found available to this user, not exporting any runner data",
                context,
                extra={"runner_count": 0},
            )
        else:
            runners_online = 0
            runners_paused = 0
            for runner in runners:
                runner_json = json.loads(runner.to_json())
                if runner_json.get("online", False):
                    runners_online += 1
                if runner_json.get("paused", False):
                    runners_paused += 1
                runner_attributes = create_resource_attributes(
                    parse_attributes(runner_json), GLAB_SERVICE_NAME
                )
                runner_attributes.update({"gitlab.resource.type": "runner"})
                # Send runner data as log events with attributes
                msg = "Runner: " + str(runner_json["id"])
                global_logger.info(msg, extra=filter_otel_log_attributes(runner_attributes))
                context = LogContext(
                    service_name="gitlab-metrics-exporter",
                    component="get-resources",
                    operation="get_runners",
                    runner_id=str(runner_json["id"]),
                )
                structured_logger.info("Log events sent for runner", context)
            with _run_stats_lock:
                _run_stats["runners_total"] = len(runners)
                _run_stats["runners_online"] = runners_online
                _run_stats["runners_offline"] = len(runners) - runners_online
                _run_stats["runners_active"] = len(runners) - runners_paused
                _run_stats["runners_paused"] = runners_paused

    except Exception as e:
        context = LogContext(
            service_name="gitlab-metrics-exporter",
            component="get-resources",
            operation="get_runners",
        )
        structured_logger.error("Unable to obtain runners", context, exception=e)


async def grab_data(project):
    metadata_exported = False
    try:
        GLAB_SERVICE_NAME = generate_service_name(project, _config)
        project_json = json.loads(project.to_json())
        project_namespace_name = (
            str(project.attributes.get("name_with_namespace", "")).lower().replace(" ", "")
        )

        path_check = GLAB_EXPORT_PATHS_ALL or (
            paths and str(project_json["namespace"]["full_path"]) in paths
        )

        if path_check:
            # Export project metadata only for projects within the configured path scope.
            # When GLAB_EXPORT_ALL_PROJECTS=true, emit the project metadata event for all projects
            # regardless of last activity; otherwise only emit for recently active ones.
            should_export_project = GLAB_EXPORT_ALL_PROJECTS
            if not GLAB_EXPORT_ALL_PROJECTS:
                last_activity = project_json.get("last_activity_at")
                if last_activity:
                    should_export_project = zulu.parse(last_activity) >= (
                        datetime.now(timezone.utc)
                        - timedelta(minutes=int(GLAB_EXPORT_LAST_MINUTES))
                    )
                else:
                    should_export_project = True  # no timestamp, export to be safe

            if should_export_project:
                c_attributes = create_resource_attributes(
                    parse_attributes(project_json), GLAB_SERVICE_NAME
                )
                c_attributes.update({"gitlab.resource.type": "project"})
                msg = "Project: " + str(project_json["id"]) + " - " + str(GLAB_SERVICE_NAME)
                global_logger.info(msg, extra=filter_otel_log_attributes(c_attributes))
                context = LogContext(
                    service_name="gitlab-metrics-exporter",
                    component="get-resources",
                    operation="grab_data",
                    project_id=str(project_json["id"]),
                    project_name=str(GLAB_SERVICE_NAME),
                )
                structured_logger.info("Log events sent for project", context)

            metadata_exported = should_export_project

            # Check regex filter — use pre-compiled pattern (compiled once at module load)
            regex_check = _projects_regex.search(project_json["name"])

            # Log filter configuration information once per run (for diagnostics)
            global _data_collection_mode_logged
            if not _data_collection_mode_logged:
                _data_collection_mode_logged = True
                context = LogContext(
                    service_name="gitlab-metrics-exporter",
                    component="get-resources",
                    operation="grab_data",
                )
                if GLAB_EXPORT_ALL_PROJECTS:
                    structured_logger.info(
                        "Data collection mode: GLAB_EXPORT_ALL_PROJECTS=true - exporting project data for all projects regardless of last activity",
                        context,
                        extra={
                            "glab_export_all_projects": GLAB_EXPORT_ALL_PROJECTS,
                            "glab_export_last_minutes": GLAB_EXPORT_LAST_MINUTES,
                            "mode": "all_projects"
                        }
                    )
                else:
                    structured_logger.info(
                        "Data collection mode: GLAB_EXPORT_ALL_PROJECTS=false - exporting project data for recently active projects only",
                        context,
                        extra={
                            "glab_export_all_projects": GLAB_EXPORT_ALL_PROJECTS,
                            "glab_export_last_minutes": GLAB_EXPORT_LAST_MINUTES,
                            "mode": "recent_projects_only"
                        }
                    )

            if regex_check:
                try:
                    context = LogContext(
                        service_name="gitlab-metrics-exporter",
                        component="get-resources",
                        operation="grab_data",
                        project_name=project_namespace_name,
                    )
                    structured_logger.info(
                        "Project matched configuration, collecting data", context
                    )
                    project_id = project_json["id"]
                    # Check pipelines first — skip pipeline-dependent resources if none found.
                    # Jobs are implicitly skipped (fetched inside get_pipelines; 0 pipelines = 0 job calls).
                    # Deployments and environments only change state via pipeline jobs.
                    # Releases are independent (can be created via UI/API without a pipeline).
                    pipeline_count = await get_pipelines(project, project_id, GLAB_SERVICE_NAME)
                    # Environments are always emitted as a full snapshot (state, not events).
                    # Releases are independent (can be created via UI/API without a pipeline).
                    # Deployments only happen via pipeline jobs — skip if no pipelines ran.
                    secondary_tasks = [
                        get_environments(project, project_id, GLAB_SERVICE_NAME),
                        get_releases(project, project_id, GLAB_SERVICE_NAME),
                    ]
                    if pipeline_count > 0:
                        secondary_tasks.append(
                            get_deployments(project, project_id, GLAB_SERVICE_NAME)
                        )
                    await asyncio.gather(*secondary_tasks)
                    # Queue processing moved to centralized location after all projects are processed
                except Exception as e:
                    context = LogContext(
                        service_name="gitlab-metrics-exporter",
                        component="get-resources",
                        operation="grab_data",
                        project_name=project_namespace_name,
                    )
                    structured_logger.error(
                        "Failed to collect data for project, check your configuration",
                        context,
                        extra={"project_json": project_json},
                        exception=e,
                    )
                if GLAB_DORA_METRICS:
                    try:
                        loop = asyncio.get_running_loop()
                        await loop.run_in_executor(_executor, get_dora_metrics, project)
                    except Exception as e:
                        context = LogContext(
                            service_name="gitlab-metrics-exporter",
                            component="get-resources",
                            operation="get_dora_metrics",
                            project_name=project_namespace_name,
                        )
                        structured_logger.error(
                            "Unable to obtain DORA metrics", context, exception=e
                        )
                # Project metadata already exported at the top of grab_data()
                # Filters above only control detailed data collection
            else:
                context = LogContext(
                    service_name="gitlab-metrics-exporter",
                    component="get-resources",
                    operation="grab_data",
                    project_name=project_namespace_name,
                )
                structured_logger.debug(
                    f"Project filtered out by regex: {project_json['name']} doesn't match {GLAB_EXPORT_PROJECTS_REGEX}",
                    context,
                    extra={
                        "regex": str(GLAB_EXPORT_PROJECTS_REGEX),
                        "project_name": project_json["name"],
                    },
                )
        else:
            context = LogContext(
                service_name="gitlab-metrics-exporter",
                component="get-resources",
                operation="grab_data",
                project_name=project_namespace_name,
            )
            structured_logger.debug(
                f"Project filtered out by path: {project_json['namespace']['full_path']} not in allowed paths",
                context,
                extra={
                    "namespace_path": str(project_json["namespace"]["full_path"]),
                    "allowed_paths": str(paths),
                    "export_all_paths": GLAB_EXPORT_PATHS_ALL,
                },
            )
    except Exception as e:
        context = LogContext(
            service_name="gitlab-metrics-exporter",
            component="get-resources",
            operation="grab_data",
            project_name=str(project.attributes.get("name_with_namespace", "")).lower().replace(" ", ""),
        )
        structured_logger.error(
            "ERROR obtaining data for project", context, exception=e
        )
    return {"metadata_exported": metadata_exported}


def get_dora_metrics(current_project):
    GLAB_SERVICE_NAME = generate_service_name(current_project, _config)
    # Parse project JSON once and reuse
    project_json = json.loads(current_project.to_json())
    project_id = project_json["id"]
    today = date.today() - timedelta(days=1)
    base_url = (
        str(GLAB_ENDPOINT)
        + "/api/v4/projects/"
        + str(project_id)
        + "/dora/metrics?metric="
    )
    req_headers = {
        "PRIVATE-TOKEN": GLAB_TOKEN,
    }
    # Project identification passed as metric attributes so we can reuse global_meter
    project_attrs = {
        "service.name": GLAB_SERVICE_NAME,
        "gitlab.resource.type": "dora-metrics",
        "project.id": project_id,
        "namespace.path": project_json["namespace"]["path"],
        "namespace.kind": project_json["namespace"]["kind"],
    }
    for metric in _DORA_METRIC_NAMES:
        url = base_url + metric + "&start_date=" + str(today)
        r = requests.get(url, headers=req_headers)
        dora = dora_counters[metric]
        if r.status_code == 200 and do_parse(r.text):
            # Create metrics we want to populate
            res = json.loads(r.text)
            for i in range(len(res)):
                attrs = {**project_attrs, "date": str(res[i]["date"])}
                if res[i]["value"] is not None:
                    value = res[i]["value"] * 100 if metric == "change_failure_rate" else res[i]["value"]
                    dora.add(value, attributes=attrs)
                else:
                    dora.add(0, attributes=attrs)


def parse_deployment(data):
    deployment_json = data[0]
    project_id = data[1]
    GLAB_SERVICE_NAME = data[2]
    try:
        deployment_attributes = create_resource_attributes(
            parse_attributes(deployment_json), GLAB_SERVICE_NAME
        )
        deployment_attributes.update({"gitlab.resource.type": "deployment"})
        # Send deployment data as log events with attributes
        msg = (
            "Deployment: "
            + str(deployment_json["id"])
            + " from project: "
            + str(project_id)
            + " - "
            + str(GLAB_SERVICE_NAME)
        )
        global_logger.info(msg, extra=filter_otel_log_attributes(deployment_attributes))
        context = LogContext(
            service_name="gitlab-metrics-exporter",
            component="get-resources",
            operation="parse_deployment",
            deployment_id=str(deployment_json["id"]),
            project_id=str(project_id),
            project_name=str(GLAB_SERVICE_NAME),
        )
        structured_logger.info("Log events sent for deployment", context)
    except Exception as e:
        context = LogContext(
            service_name="gitlab-metrics-exporter",
            component="get-resources",
            operation="parse_deployment",
            project_id=str(project_id),
        )
        structured_logger.error(
            "Failed to obtain deployments for project", context, exception=e
        )


# ---------------------------------------------------------------------------
# Sync fetch helpers — run inside _executor so blocking HTTP calls don't
# stall the asyncio event loop while other project coroutines are waiting.
# ---------------------------------------------------------------------------

def _sync_fetch_pipelines(project, kwargs):
    """Fetch all pipeline objects in the window. Returns (objects, total)."""
    it = project.pipelines.list(**kwargs)
    objects = list(it)
    return objects, getattr(it, "total", None) or len(objects)


def _sync_fetch_deployments(project, cutoff):
    """Fetch deployments updated after cutoff; stops on first miss. Returns (matching_jsons, total_fetched, total_api)."""
    it = project.deployments.list(
        iterator=True, per_page=100, order_by="updated_at", sort="desc",
        updated_after=str(cutoff),
    )
    total_api = getattr(it, "total", None) or 0
    matching, total_fetched = [], 0
    for dep in it:
        total_fetched += 1
        dep_json = json.loads(dep.to_json())
        if zulu.parse(dep_json["created_at"]) >= cutoff:
            matching.append(dep_json)
        else:
            break
    return matching, total_fetched, total_api


def _sync_fetch_environments(project):
    """Fetch all environment objects for a project."""
    return project.environments.list(get_all=True, per_page=100)


def _sync_fetch_releases(project, cutoff):
    """Fetch releases created after cutoff; stops on first miss. Returns (matching_jsons, total_fetched)."""
    it = project.releases.list(iterator=True, per_page=100, order_by="created_at", sort="desc")
    matching, total_fetched = [], 0
    for rel in it:
        total_fetched += 1
        rel_json = json.loads(rel.to_json())
        if zulu.parse(rel_json["created_at"]) >= cutoff:
            matching.append(rel_json)
        else:
            break
    return matching, total_fetched


async def get_deployments(current_project, project_id, GLAB_SERVICE_NAME):
    global q
    cutoff = (
        datetime.now(timezone.utc)
        - timedelta(minutes=int(GLAB_EXPORT_LAST_MINUTES))
    )
    loop = asyncio.get_running_loop()
    matching, total_count, total_api = await loop.run_in_executor(
        _executor, _sync_fetch_deployments, current_project, cutoff
    )
    for deployment_json in matching:
        q.put([deployment_json, project_id, GLAB_SERVICE_NAME, "deployment"])
    if total_count > 0:
        context = LogContext(
            service_name="gitlab-metrics-exporter",
            component="get-resources",
            operation="get_deployments",
            project_id=str(project_id),
        )
        structured_logger.info(
            "Deployments processed",
            context,
            extra={"deployment_count": total_count, "matching_count": len(matching)},
        )


def parse_environment(data):
    environment_json = data[0]
    project_id = data[1]
    GLAB_SERVICE_NAME = data[2]
    try:
        environment_attributes = create_resource_attributes(
            parse_attributes(environment_json), GLAB_SERVICE_NAME
        )
        environment_attributes.update({"gitlab.resource.type": "environment"})
        # Send environment data as log events with attributes
        msg = (
            "Environment: "
            + str(environment_json["id"])
            + " from project: "
            + str(project_id)
            + " - "
            + str(GLAB_SERVICE_NAME)
        )
        global_logger.info(msg, extra=filter_otel_log_attributes(environment_attributes))
        context = LogContext(
            service_name="gitlab-metrics-exporter",
            component="get-resources",
            operation="parse_environment",
            environment_id=str(environment_json["id"]),
            project_id=str(project_id),
            project_name=str(GLAB_SERVICE_NAME),
        )
        structured_logger.info("Log events sent for environment", context)
    except Exception as e:
        context = LogContext(
            service_name="gitlab-metrics-exporter",
            component="get-resources",
            operation="parse_environment",
            project_id=str(project_id),
        )
        structured_logger.error(
            "Failed to obtain environments for project", context, exception=e
        )


async def get_environments(current_project, project_id, GLAB_SERVICE_NAME):
    global q
    loop = asyncio.get_running_loop()
    environments = await loop.run_in_executor(
        _executor, _sync_fetch_environments, current_project
    )
    if len(environments) > 0:  # check if there are environments in this project
        for environment in environments:
            environment_json = json.loads(environment.to_json())
            # we should send data for every environment each time
            q.put([environment_json, project_id, GLAB_SERVICE_NAME, "environment"])

        with _run_stats_lock:
            _run_stats["environments_total"] += len(environments)

        context = LogContext(
            service_name="gitlab-metrics-exporter",
            component="get-resources",
            operation="get_environments",
            project_id=str(project_id),
        )
        structured_logger.info(
            "Number of environments found",
            context,
            extra={"environment_count": len(environments)},
        )
    else:
        context = LogContext(
            service_name="gitlab-metrics-exporter",
            component="get-resources",
            operation="get_environments",
            project_id=str(project_id),
        )
        structured_logger.info("No environments found in project", context)


def parse_release(data):
    release_json = data[0]
    project_id = data[1]
    GLAB_SERVICE_NAME = data[2]
    try:
        release_attributes = create_resource_attributes(
            parse_attributes(release_json), GLAB_SERVICE_NAME
        )
        release_attributes.update({"gitlab.resource.type": "release"})
        # Send releases data as log events with attributes
        msg = (
            "Release: "
            + str(release_json["tag_name"])
            + " from project: "
            + str(project_id)
            + " - "
            + str(GLAB_SERVICE_NAME)
        )
        global_logger.info(msg, extra=filter_otel_log_attributes(release_attributes))
        context = LogContext(
            service_name="gitlab-metrics-exporter",
            component="get-resources",
            operation="parse_release",
            release_tag=str(release_json["tag_name"]),
            project_id=str(project_id),
            project_name=str(GLAB_SERVICE_NAME),
        )
        structured_logger.info("Log events sent for release", context)
    except Exception as e:
        context = LogContext(
            service_name="gitlab-metrics-exporter",
            component="get-resources",
            operation="parse_release",
            project_id=str(project_id),
        )
        structured_logger.error(
            "Failed to obtain releases for project", context, exception=e
        )


async def get_releases(current_project, project_id, GLAB_SERVICE_NAME):
    global q
    cutoff = (
        datetime.now(timezone.utc)
        - timedelta(minutes=int(GLAB_EXPORT_LAST_MINUTES))
    )
    loop = asyncio.get_running_loop()
    matching, total_count = await loop.run_in_executor(
        _executor, _sync_fetch_releases, current_project, cutoff
    )
    for release_json in matching:
        q.put([release_json, project_id, GLAB_SERVICE_NAME, "release"])
    if total_count > 0:
        context = LogContext(
            service_name="gitlab-metrics-exporter",
            component="get-resources",
            operation="get_releases",
            project_id=str(project_id),
        )
        structured_logger.info(
            "Releases processed",
            context,
            extra={"release_count": total_count, "matching_count": len(matching)},
        )


def parse_pipeline(data):
    pipeline_json = data[0]
    project_id = data[1]
    GLAB_SERVICE_NAME = data[2]
    pipeline_id = pipeline_json["id"]
    try:
        status = pipeline_json.get("status", "unknown")
        with _run_stats_lock:
            _run_stats["pipeline_statuses"][status] = _run_stats["pipeline_statuses"].get(status, 0) + 1

        attributes_pip = {"gitlab.resource.type": "pipeline"}
        # Grab pipeline attributes
        current_pipeline_attributes = create_resource_attributes(
            parse_attributes(pipeline_json), GLAB_SERVICE_NAME
        )
        # Check wich dimension to set on each metric
        currrent_pipeline_metrics_attributes = parse_metrics_attributes(
            current_pipeline_attributes
        )
        currrent_pipeline_metrics_attributes[2].update(attributes_pip)
        # Update attributes for the log events
        current_pipeline_attributes.update(attributes_pip)
        # Send pipeline metrics with configured dimensions
        gitlab_pipelines_duration.record(
            float(currrent_pipeline_metrics_attributes[0]),
            currrent_pipeline_metrics_attributes[2],
        )
        gitlab_pipelines_queued_duration.record(
            float(currrent_pipeline_metrics_attributes[1]),
            currrent_pipeline_metrics_attributes[2],
        )
        # Send pipeline data as log events with attributes
        msg = (
            "Pipeline: "
            + str(pipeline_id)
            + " - "
            + "from project: "
            + str(project_id)
            + " - "
            + str(GLAB_SERVICE_NAME)
        )
        global_logger.info(msg, extra=filter_otel_log_attributes(current_pipeline_attributes))
        context = LogContext(
            service_name="gitlab-metrics-exporter",
            component="get-resources",
            operation="parse_pipeline",
            pipeline_id=str(pipeline_id),
            project_id=str(project_id),
            project_name=str(GLAB_SERVICE_NAME),
        )
        structured_logger.info("Metrics and log events sent for pipeline", context)
    except Exception as e:
        context = LogContext(
            service_name="gitlab-metrics-exporter",
            component="get-resources",
            operation="parse_pipeline",
            project_id=str(project_id),
        )
        structured_logger.error(
            "Failed to obtain pipelines for project", context, exception=e
        )


async def get_pipelines(current_project, project_id, GLAB_SERVICE_NAME):
    context = LogContext(
        service_name="gitlab-metrics-exporter",
        component="get-resources",
        operation="get_pipelines",
        project_id=str(project_id),
    )
    structured_logger.info("Gathering pipeline data for project", context)

    pipeline_kwargs = {
        "iterator": True,
        "per_page": 100,
        "updated_after": str(
            datetime.now(timezone.utc)
            - timedelta(minutes=int(GLAB_EXPORT_LAST_MINUTES))
        ),
        "order_by": "updated_at",
        "sort": "desc",
    }

    # Fetch all pipeline objects in the thread pool — blocking HTTP calls must
    # not run on the event loop or they stall all other concurrent coroutines.
    loop = asyncio.get_running_loop()
    pipeline_objects, total = await loop.run_in_executor(
        _executor, _sync_fetch_pipelines, current_project, pipeline_kwargs
    )

    job_futures = []
    for pipelineobject in pipeline_objects:
        # Serialize once and share to avoid duplicate to_json() calls
        pipeline_dict = json.loads(pipelineobject.to_json())
        # Queue the pipeline record inline — it's just a q.put(), no I/O
        q.put([pipeline_dict, project_id, GLAB_SERVICE_NAME, "pipeline"])
        # Delegate blocking jobs list API call to the dedicated job thread pool
        job_futures.append(
            loop.run_in_executor(
                _job_executor, get_jobs, pipelineobject, project_id, GLAB_SERVICE_NAME, pipeline_dict
            )
        )

    # Await all job fetches — ensures queue is fully populated before get_pipelines returns
    if job_futures:
        await asyncio.gather(*job_futures, return_exceptions=True)

    return len(job_futures)  # number of pipelines found in the window


def parse_job(data):
    job_json = data[0]
    project_id = data[1]
    GLAB_SERVICE_NAME = data[2]
    current_pipeline_json = data[4]
    try:
        status = job_json.get("status", "unknown")
        with _run_stats_lock:
            _run_stats["job_statuses"][status] = _run_stats["job_statuses"].get(status, 0) + 1

        # Grab job attributes
        current_job_attributes = create_resource_attributes(
            parse_attributes(job_json), GLAB_SERVICE_NAME
        )
        attributes_j = {"gitlab.resource.type": "job"}
        # Check wich dimension to set on each metric
        job_metrics_attributes = parse_metrics_attributes(current_job_attributes)
        job_metrics_attributes[2].update(attributes_j)
        # Update attributes for the log events
        current_job_attributes.update(attributes_j)
        # Send job metrics with configured dimensions
        gitlab_jobs_duration.record(
            float(job_metrics_attributes[0]), job_metrics_attributes[2]
        )
        gitlab_jobs_queued_duration.record(
            float(job_metrics_attributes[1]), job_metrics_attributes[2]
        )
        # Send job data as log events with attributes
        msg = (
            "Job: "
            + str(job_json["id"])
            + " - "
            + "from project: "
            + str(project_id)
            + " - "
            + str(GLAB_SERVICE_NAME)
        )
        global_logger.info(msg, extra=filter_otel_log_attributes(current_job_attributes))
        context = LogContext(
            service_name="gitlab-metrics-exporter",
            component="get-resources",
            operation="parse_job",
            job_id=str(job_json["id"]),
            pipeline_id=str(current_pipeline_json["id"]),
            project_id=str(project_id),
            project_name=str(GLAB_SERVICE_NAME),
        )
        structured_logger.info("Metrics and log events sent for job", context)

    except Exception as e:
        context = LogContext(
            service_name="gitlab-metrics-exporter",
            component="get-resources",
            operation="parse_job",
            project_id=str(project_id),
        )
        structured_logger.error(
            "Failed to obtain jobs for project", context, exception=e
        )


def get_jobs(pipelineobject, project_id, GLAB_SERVICE_NAME, pipeline_dict):
    global q
    # Use iterator=True to fetch jobs page-by-page so we can stop early
    jobs = pipelineobject.jobs.list(iterator=True, per_page=100)
    current_pipeline_json = pipeline_dict  # reuse the already-serialized dict
    exclude_jobs = _exclude_jobs
    cutoff = (
        datetime.now(timezone.utc)
        - timedelta(minutes=int(GLAB_EXPORT_LAST_MINUTES))
    )
    for job in jobs:
        job_json = json.loads(job.to_json())
        job_name = str(job_json.get("name", "")).lower()
        job_stage = str(job_json.get("stage", "")).lower()
        if job_stage in ["new-relic-exporter", "new-relic-metrics-exporter"]:
            continue
        if job_name in exclude_jobs or job_stage in exclude_jobs:
            continue
        if zulu.parse(job_json["created_at"]) >= cutoff:
            q.put([job_json, project_id, GLAB_SERVICE_NAME, "job", current_pipeline_json])
        else:
            break  # Jobs are ordered by ID (creation order) — stop at first old job



def emit_collection_summary(collection_results: dict, projects: list) -> None:
    """
    Emit a single OTEL log event summarising the entire collection run.

    Attributes are split into two namespaces:
    - estate.*  — time-independent totals (not affected by GLAB_EXPORT_LAST_MINUTES)
    - window.*  — activity exported in the current collection window
    - run.*     — metadata about this collection run
    """
    queue_stats = collection_results.get("queue_stats", {})
    run_stats = get_run_stats()

    project_visibility_counts: dict = {}
    for p in projects:
        vis = getattr(p, "visibility", "unknown")
        project_visibility_counts[vis] = project_visibility_counts.get(vis, 0) + 1

    summary_attributes: dict = {
        "event.name": "GitLabCollectionSummary",
        "event.domain": "newrelic.gitlab",
        "gitlab.resource.type": "collection_summary",
        # Estate-wide (no time filter)
        "estate.total_projects": len(projects),
        "estate.total_environments": run_stats.get("environments_total", 0),
        "estate.runners_total": run_stats.get("runners_total", 0),
        "estate.runners_online": run_stats.get("runners_online", 0),
        "estate.runners_offline": run_stats.get("runners_offline", 0),
        "estate.runners_active": run_stats.get("runners_active", 0),
        "estate.runners_paused": run_stats.get("runners_paused", 0),
        # Collection window activity
        "window.minutes": int(GLAB_EXPORT_LAST_MINUTES),
        "window.pipelines": queue_stats.get("pipelines", 0),
        "window.jobs": queue_stats.get("jobs", 0),
        "window.deployments": queue_stats.get("deployments", 0),
        "window.environments": queue_stats.get("environments", 0),
        "window.releases": queue_stats.get("releases", 0),
        # Run metadata
        "run.duration_seconds": round(collection_results.get("duration_seconds", 0), 2),
        "run.errors_count": len(collection_results.get("errors", [])),
        "run.projects_successful": collection_results.get("successful_projects", 0),
        "run.projects_failed": collection_results.get("failed_projects", 0),
    }

    for vis, count in project_visibility_counts.items():
        summary_attributes[f"estate.projects_visibility.{vis}"] = count

    for status, count in run_stats.get("pipeline_statuses", {}).items():
        summary_attributes[f"window.pipeline_status.{status}"] = count

    for status, count in run_stats.get("job_statuses", {}).items():
        summary_attributes[f"window.job_status.{status}"] = count

    global_logger.info(
        "GitLab collection summary",
        extra=filter_otel_log_attributes(summary_attributes),
    )


class EnhancedResourceCollector:
    """
    Enhanced resource collector that wraps the existing get_resources functions
    to provide a class-based interface for the main exporter.
    """

    def __init__(self):
        """Initialize the enhanced resource collector."""
        self.logger = get_structured_logger(
            "gitlab-metrics-exporter", "enhanced-collector"
        )

    async def collect_project_data(self, project) -> Dict[str, Any]:
        """
        Collect data for a single project using the existing grab_data function.

        Args:
            project: GitLab project object

        Returns:
            Dictionary with collection results
        """
        context = LogContext(
            service_name="gitlab-metrics-exporter",
            component="enhanced-collector",
            operation="collect_project_data",
            project_id=str(project.id),
        )

        try:
            self.logger.info("Starting project data collection", context)

            # Use the existing grab_data function
            grab_result = await grab_data(project)

            # Return basic metrics about what was collected
            metrics = {
                "project_id": project.id,
                "project_name": project.name,
                "data_collected": True,
                "metadata_exported": (grab_result or {}).get("metadata_exported", False),
            }

            self.logger.info("Project data collection completed", context)
            return metrics

        except Exception as e:
            self.logger.error("Project data collection failed", context, exception=e)
            raise

    async def collect_runners_data(self) -> None:
        """
        Collect runners data using the existing get_runners function.
        """
        context = LogContext(
            service_name="gitlab-metrics-exporter",
            component="enhanced-collector",
            operation="collect_runners_data",
        )

        try:
            self.logger.info("Starting runners data collection", context)

            # Offload blocking HTTP calls to the thread pool
            loop = asyncio.get_running_loop()
            await loop.run_in_executor(_executor, get_runners)

            self.logger.info("Runners data collection completed", context)

        except Exception as e:
            self.logger.error("Runners data collection failed", context, exception=e)
            raise

    def process_queue(self) -> Dict[str, Any]:
        """
        Process all items in the global queue.
        This ensures all collected data is exported before service termination.

        Returns:
            Dictionary with processing statistics
        """
        from shared.global_variables import q

        context = LogContext(
            service_name="gitlab-metrics-exporter",
            component="enhanced-collector",
            operation="process_queue",
        )

        stats = {
            "total_items": 0,
            "deployments": 0,
            "environments": 0,
            "releases": 0,
            "pipelines": 0,
            "jobs": 0,
            "errors": 0,
        }

        initial_size = q.qsize()
        self.logger.info(
            f"Starting queue processing with {initial_size} items",
            context,
            extra={"queue_size": initial_size},
        )

        items = []
        while not q.empty():
            try:
                items.append(q.get(timeout=1))
            except Exception:
                break

        stats["total_items"] = len(items)

        def process_item(data):
            data_type = data[3]
            if data_type == "deployment":
                parse_deployment(data)
                return "deployments"
            elif data_type == "environment":
                parse_environment(data)
                return "environments"
            elif data_type == "release":
                parse_release(data)
                return "releases"
            elif data_type == "pipeline":
                parse_pipeline(data)
                return "pipelines"
            elif data_type == "job":
                parse_job(data)
                return "jobs"
            else:
                self.logger.warning(
                    f"Unknown data type in queue: {data_type!r}",
                    context,
                )
                return None

        futures = {_executor.submit(process_item, item): item for item in items}
        for future in concurrent.futures.as_completed(futures):
            try:
                result_type = future.result()
                if result_type:
                    stats[result_type] += 1
            except Exception as e:
                stats["errors"] += 1
                self.logger.error(
                    "Error processing queue item",
                    context,
                    exception=e,
                )

        self.logger.info(
            f"Queue processing completed - processed {stats['total_items']} items",
            context,
            extra=stats,
        )

        return stats
