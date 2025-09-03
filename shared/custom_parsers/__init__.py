import time
import json
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
    Enhanced attribute parser that flattens GitLab job data into key-value pairs.
    Uses do_parse() to filter out None, empty, and invalid values.
    Handles nested objects, JSON strings, and arrays by flattening them with dot notation.
    """
    obj_atts = {}
    attributes_to_drop = [""]

    # Handle the case where obj is a list (from JSON parsing)
    if isinstance(obj, list):
        return _flatten_array(obj, prefix)

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
            # Handle lists/arrays by flattening them with indexed keys
            elif isinstance(value, list):
                array_attrs = _flatten_array(value, full_attribute_name)
                obj_atts.update(array_attrs)
            # Handle JSON strings by parsing and flattening them
            elif isinstance(value, str) and _is_json_string(value):
                json_attrs = _flatten_json_string(value, full_attribute_name)
                obj_atts.update(json_attrs)
            elif do_parse(value):
                obj_atts[full_attribute_name] = str(value)

    return obj_atts


def _is_json_string(value):
    """
    Check if a string value is a valid JSON string.

    Args:
        value: String value to check

    Returns:
        bool: True if the string is valid JSON, False otherwise
    """
    if not isinstance(value, str) or len(value.strip()) == 0:
        return False

    # Quick check for JSON-like structure
    stripped = value.strip()
    if not (
        (stripped.startswith("{") and stripped.endswith("}"))
        or (stripped.startswith("[") and stripped.endswith("]"))
    ):
        return False

    try:
        json.loads(value)
        return True
    except (json.JSONDecodeError, ValueError):
        return False


def _flatten_json_string(json_str, prefix):
    """
    Parse a JSON string and flatten it into key-value pairs.

    Args:
        json_str: JSON string to parse and flatten
        prefix: Prefix for the flattened keys

    Returns:
        dict: Flattened key-value pairs
    """
    try:
        parsed_json = json.loads(json_str)
        return parse_attributes(parsed_json, prefix)
    except (json.JSONDecodeError, ValueError) as e:
        # If JSON parsing fails, treat as regular string
        logger = get_logger("gitlab-exporter", "custom-parsers")
        context = LogContext(
            service_name="gitlab-exporter",
            component="custom-parsers",
            operation="_flatten_json_string",
        )
        logger.debug(
            f"Failed to parse JSON string for attribute {prefix}",
            context,
            extra={"json_string": json_str[:100], "error": str(e)},
        )
        return {prefix: json_str}


def _flatten_array(array, prefix):
    """
    Flatten an array into key-value pairs with indexed keys.
    Filters out None and empty values, compacting the indices.

    Args:
        array: List/array to flatten
        prefix: Prefix for the flattened keys

    Returns:
        dict: Flattened key-value pairs with indexed keys
    """
    flattened = {}
    valid_index = 0  # Track the index for valid (non-filtered) items

    for item in array:
        # Skip None, empty strings, and "None" strings
        if not do_parse(item):
            continue

        indexed_key = f"{prefix}[{valid_index}]"

        if isinstance(item, dict):
            # Recursively flatten nested dictionaries
            nested_attrs = parse_attributes(item, indexed_key)
            flattened.update(nested_attrs)
            valid_index += 1
        elif isinstance(item, list):
            # Recursively flatten nested arrays
            nested_array_attrs = _flatten_array(item, indexed_key)
            flattened.update(nested_array_attrs)
            valid_index += 1
        elif isinstance(item, str) and _is_json_string(item):
            # Handle JSON strings within arrays
            json_attrs = _flatten_json_string(item, indexed_key)
            flattened.update(json_attrs)
            valid_index += 1
        else:
            # Valid primitive value
            flattened[indexed_key] = str(item)
            valid_index += 1

    return flattened


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
