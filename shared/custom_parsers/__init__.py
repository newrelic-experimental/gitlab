import time
from pyrfc3339 import parse
import os
from re import search
from shared.logging.structured_logger import get_logger, LogContext

GLAB_CONVERT_TO_TIMESTAMP = False

# Check export logs is set
if (
    "GLAB_CONVERT_TO_TIMESTAMP" in os.environ
    and os.getenv("GLAB_CONVERT_TO_TIMESTAMP").lower() == "true"
):
    GLAB_CONVERT_TO_TIMESTAMP = True
else:
    GLAB_CONVERT_TO_TIMESTAMP = False


def do_time(string):
    return int(round(time.mktime(parse(string).timetuple())) * 1000000000)


def do_string(string):
    return str(string).lower().replace(" ", "")


def do_parse(string):
    return string != "" and string is not None and string != "None"


def check_env_vars():
    logger = get_logger("gitlab-exporter", "custom-parsers")
    keys = ("GLAB_TOKEN", "NEW_RELIC_API_KEY")

    keys_not_set = []

    for key in keys:
        if key not in os.environ:
            keys_not_set.append(key)
    else:
        pass

    if len(keys_not_set) > 0:
        context = LogContext(
            service_name="gitlab-exporter",
            component="custom-parsers",
            operation="check_env_vars",
        )
        for key in keys_not_set:
            logger.critical(
                f"Environment variable not set: {key}", context, variable=key
            )
        exit(1)
    else:
        pass  # All required environment variables set


def grab_span_att_vars():
    # Grab list enviroment variables to set as span attributes
    try:
        atts = dict(os.environ)  # Create a copy to avoid modifying os.environ
        # Remove unwanted/sensitive attributes
        keys_to_remove = []
        for att in atts:
            if not (
                att.startswith("CI")
                or att.startswith("GIT")
                or att.startswith("GLAB")
                or att.startswith("NEW")
                or att.startswith("OTEL")
            ):
                keys_to_remove.append(att)

        for key in keys_to_remove:
            atts.pop(key, None)

        atts_to_remove = [
            "NEW_RELIC_API_KEY",
            "GITLAB_FEATURES",
            "CI_SERVER_TLS_CA_FILE",
            "CI_RUNNER_TAGS",
            "CI_JOB_JWT",
            "CI_JOB_JWT_V1",
            "CI_JOB_JWT_V2",
            "GLAB_TOKEN",
            "GIT_ASKPASS",
            "CI_COMMIT_BEFORE_SHA",
            "CI_BUILD_TOKEN",
            "CI_DEPENDENCY_PROXY_PASSWORD",
            "CI_RUNNER_SHORT_TOKEN",
            "CI_BUILD_BEFORE_SHA",
            "CI_BEFORE_SHA",
            "OTEL_EXPORTER_OTEL_ENDPOINT",
            "GLAB_EXPORT_PATHS",
            "GLAB_EXPORT_PATHS_ALL",
            "GLAB_EXPORT_PROJECTS_REGEX",
        ]
        if "GLAB_ENVS_DROP" in os.environ:
            try:
                if os.getenv("GLAB_ENVS_DROP") != "":
                    user_envs_to_drop = str(os.getenv("GLAB_ENVS_DROP")).split(",")
                    for attribute in user_envs_to_drop:
                        atts_to_remove.append(attribute)
            except Exception as e:
                logger = get_logger("gitlab-exporter", "custom-parsers")
                context = LogContext(
                    service_name="gitlab-exporter",
                    component="custom-parsers",
                    operation="grab_span_att_vars",
                )
                logger.error(
                    "Unable to parse GLAB_ENVS_DROP, check your configuration",
                    context,
                    exception=e,
                )

        for item in atts_to_remove:
            atts.pop(item, None)

        # Filter out None values and empty strings
        filtered_atts = {
            key: value
            for key, value in atts.items()
            if value is not None and value != "" and value != "None"
        }

    except Exception as e:
        logger = get_logger("gitlab-exporter", "custom-parsers")
        context = LogContext(
            service_name="gitlab-exporter",
            component="custom-parsers",
            operation="grab_span_att_vars",
        )
        logger.error("Error processing span attributes", context, exception=e)
        filtered_atts = {}

    return filtered_atts


def parse_attributes(obj, prefix=""):
    """
    Simple attribute parser that flattens GitLab job data into key-value pairs.
    Uses do_parse() to filter out None, empty, and invalid values.
    Handles nested objects by flattening them with dot notation.
    """
    obj_atts = {}
    attributes_to_drop = [""]

    if "GLAB_ATTRIBUTES_DROP" in os.environ:
        try:
            if os.getenv("GLAB_ATTRIBUTES_DROP") != "":
                user_attributes_to_drop = (
                    str(os.getenv("GLAB_ATTRIBUTES_DROP")).lower().split(",")
                )
                for attribute in user_attributes_to_drop:
                    attributes_to_drop.append(attribute)
        except Exception as e:
            logger = get_logger("gitlab-exporter", "custom-parsers")
            context = LogContext(
                service_name="gitlab-exporter",
                component="custom-parsers",
                operation="parse_attributes",
            )
            logger.error(
                "Unable to parse GLAB_ATTRIBUTES_DROP, check your configuration",
                context,
                exception=e,
            )

    for attribute in obj:
        attribute_name = str(attribute).lower()
        full_attribute_name = f"{prefix}.{attribute_name}" if prefix else attribute_name

        if attribute_name not in attributes_to_drop:
            value = obj[attribute]

            # Handle nested dictionaries by recursively flattening them
            if isinstance(value, dict):
                nested_attrs = parse_attributes(value, full_attribute_name)
                obj_atts.update(nested_attrs)
            elif do_parse(value):
                obj_atts[full_attribute_name] = str(value)

    return obj_atts


def parse_metrics_attributes(attributes):
    metrics_attributes_to_keep = ["service.name", "status", "stage", "name"]
    metrics_attributes = {}
    if "GLAB_DIMENSION_METRICS" in os.environ:
        try:
            if os.getenv("GLAB_DIMENSION_METRICS") != "":
                user_attributes_to_keep = (
                    str(os.getenv("GLAB_DIMENSION_METRICS")).lower().split(",")
                )
                for attribute in user_attributes_to_keep:
                    metrics_attributes_to_keep.append(attribute)
        except Exception as e:
            logger = get_logger("gitlab-exporter", "custom-parsers")
            context = LogContext(
                service_name="gitlab-exporter",
                component="custom-parsers",
                operation="parse_metrics_attributes",
            )
            logger.error(
                "Unable to parse GLAB_DIMENSION_METRICS, exporting with default dimensions, check your configuration",
                context,
                exception=e,
            )

    for attribute in attributes:
        if (
            str(attribute).lower() in metrics_attributes_to_keep
        ):  # Choose attributes to keep as dimensions
            metrics_attributes[str(attribute).lower()] = attributes[
                str(attribute).lower()
            ]

    if "queued_duration" in attributes:
        queued_duration = float(attributes["queued_duration"])
    else:
        queued_duration = 0

    if "duration" in attributes:
        duration = float(attributes["duration"])
    else:
        duration = 0

    return duration, queued_duration, metrics_attributes
