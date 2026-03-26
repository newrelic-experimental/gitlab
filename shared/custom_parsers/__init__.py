import time
import json
import sys
from pyrfc3339 import parse
import os
from re import search
import logging

# Use standard logging for module-level logger to avoid circular dependencies
logger = logging.getLogger(__name__)

# Import structured logger components for use in functions
from shared.logging.structured_logger import get_logger, LogContext

# Hardcoded sensitive attribute denylist — shared by grab_span_att_vars() and
# filter_otel_log_attributes() so both functions enforce the same rules.
# Keys are stored lowercase for case-insensitive comparison.
SENSITIVE_ATTRIBUTES = frozenset({
    "new_relic_api_key",
    "glab_token",
    "ci_job_jwt",
    "ci_job_jwt_v1",
    "ci_job_jwt_v2",
    "ci_job_token",
    "ci_build_token",
    "ci_registry_password",
    "ci_deploy_password",
    "ci_dependency_proxy_password",
    "ci_runner_short_token",
    "ci_server_tls_ca_file",
    "ci_server_tls_cert_file",
    "ci_server_tls_key_file",
    "ci_runner_tags",
    "git_askpass",
    "ci_commit_before_sha",
    "ci_build_before_sha",
    "ci_before_sha",
    "gitlab_features",
    "otel_exporter_otel_endpoint",
    "glab_export_paths",
    "glab_export_paths_all",
    "glab_export_projects_regex",
})

GLAB_CONVERT_TO_TIMESTAMP = False

# Check export logs is set
if (
    "GLAB_CONVERT_TO_TIMESTAMP" in os.environ
    and os.getenv("GLAB_CONVERT_TO_TIMESTAMP").lower() == "true"
):
    GLAB_CONVERT_TO_TIMESTAMP = True
else:
    GLAB_CONVERT_TO_TIMESTAMP = False

# Cache attribute/dimension drop lists at module level — env vars don't change at runtime
_ATTRIBUTES_DROP: list = [
    a.strip().lower()
    for a in os.getenv("GLAB_ATTRIBUTES_DROP", "").split(",")
    if a.strip()
]
_DIMENSION_METRICS: list = [
    d.strip().lower()
    for d in os.getenv("GLAB_DIMENSION_METRICS", "").split(",")
    if d.strip()
]


def do_time(string):
    """
    Parse RFC 3339 timestamp string to nanoseconds since epoch.
    Returns None if the timestamp is invalid or null.
    """
    if not string or string == "null" or string == "None" or string.lower() == "none":
        logger.debug(f"Timestamp is null or empty: '{string}'")
        return None
    try:
        parsed_time = parse(string)
        timestamp_ns = int(parsed_time.timestamp() * 1_000_000_000)
        logger.debug(
            f"Successfully parsed timestamp '{string}' to {timestamp_ns} nanoseconds"
        )
        return timestamp_ns
    except ValueError as e:
        logger.warning(
            f"ValueError parsing timestamp - "
            f"input: '{string}', "
            f"type: {type(string).__name__}, "
            f"length: {len(str(string))}, "
            f"error: {e}"
        )
        return None
    except TypeError as e:
        logger.warning(
            f"TypeError parsing timestamp - "
            f"input: '{string}', "
            f"type: {type(string).__name__}, "
            f"error: {e}"
        )
        return None
    except Exception as e:
        logger.error(
            f"Unexpected error parsing timestamp - "
            f"input: '{string}', "
            f"type: {type(string).__name__}, "
            f"exception_type: {type(e).__name__}, "
            f"error: {e}"
        )
        return None


def do_string(string):
    return str(string).lower().replace(" ", "")


def do_parse(string):
    return string != "" and string is not None and string != "None"


def log_attributes_debug(attributes, operation_name="attribute_processing"):
    """
    Log debug information about attributes.
    Logs: total count, each key with value length, and overall size.
    """
    if not attributes:
        logger.debug(f"[{operation_name}] No attributes to log")
        return

    total_count = len(attributes)
    details = []

    for key, value in attributes.items():
        value_str = str(value) if value is not None else "None"
        value_length = len(value_str)
        details.append(f"{key}(len={value_length})")

    logger.debug(
        f"[{operation_name}] Total attributes: {total_count} | "
        f"Details: {', '.join(details[:10])}"
        f"{'...' if total_count > 10 else ''}"
    )


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
                f"Environment variable not set: {key}", context, extra={"variable": key}
            )
        sys.exit(1)
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

        # Build remove list from the shared sensitive denylist (stored lowercase,
        # so match case-insensitively against the actual env var keys).
        atts_to_remove = [k for k in atts if k.lower() in SENSITIVE_ATTRIBUTES]
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

        # Log attributes debug information
        log_attributes_debug(filtered_atts, "grab_span_att_vars")

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


def filter_otel_log_attributes(attrs: dict) -> dict:
    """
    Filter attributes before sending as OTEL log record extra fields.

    Applies in order:
    1. Removes None, empty string, and 'None' string values
    2. Drops keys in the hardcoded SENSITIVE_ATTRIBUTES denylist
    3. Drops keys listed in GLAB_ATTRIBUTES_DROP (user-configured, comma-separated,
       applies to all data types including log records)

    After filtering, warns at DEBUG level if the OTEL SDK will truncate further
    due to OTEL_ATTRIBUTE_COUNT_LIMIT.
    """
    keys_to_drop = SENSITIVE_ATTRIBUTES | frozenset(_ATTRIBUTES_DROP)

    filtered = {
        k: v
        for k, v in attrs.items()
        if v is not None
        and v != ""
        and v != "None"
        and k.lower() not in keys_to_drop
    }

    # OTEL_LOGRECORD_ATTRIBUTE_COUNT_LIMIT takes precedence over OTEL_ATTRIBUTE_COUNT_LIMIT
    # for log records specifically. Fall back to the global limit if not set.
    count_limit = int(
        os.getenv("OTEL_LOGRECORD_ATTRIBUTE_COUNT_LIMIT")
        or os.getenv("OTEL_ATTRIBUTE_COUNT_LIMIT")
        or 128
    )
    value_limit = int(
        os.getenv("OTEL_LOGRECORD_ATTRIBUTE_VALUE_LENGTH_LIMIT")
        or os.getenv("OTEL_ATTRIBUTE_VALUE_LENGTH_LIMIT")
        or 0  # 0 = no limit
    )

    _log = None  # lazy — only create if we need to warn

    if len(filtered) > count_limit:
        all_keys = list(filtered.keys())
        will_be_dropped = all_keys[count_limit:]
        _log = get_logger("gitlab-exporter", "custom-parsers")
        _log.warning(
            f"OTEL will drop {len(will_be_dropped)} attributes due to count limit "
            f"(limit={count_limit}, have={len(filtered)}): {will_be_dropped}"
        )

    if value_limit:
        truncated = {k: v for k, v in filtered.items() if len(str(v)) > value_limit}
        if truncated:
            if _log is None:
                _log = get_logger("gitlab-exporter", "custom-parsers")
            _log.warning(
                f"OTEL will truncate {len(truncated)} attribute values exceeding "
                f"value length limit ({value_limit}): "
                f"{[(k, len(str(v))) for k, v in truncated.items()]}"
            )

    return filtered


def parse_attributes(obj, prefix=""):
    """
    Enhanced attribute parser that flattens GitLab job data into key-value pairs.
    Uses do_parse() to filter out None, empty, and invalid values.
    Handles nested objects, JSON strings, and arrays by flattening them with dot notation.
    """
    obj_atts = {}
    # Use module-level cached drop list (empty string sentinel + user-configured drops)
    attributes_to_drop = [""] + _ATTRIBUTES_DROP

    # Handle the case where obj is a list (from JSON parsing)
    if isinstance(obj, list):
        return _flatten_array(obj, prefix)

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

    # Log attributes debug information
    log_attributes_debug(obj_atts, "parse_attributes")

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
    metrics_attributes_to_keep = ["service.name", "status", "stage", "name"] + _DIMENSION_METRICS
    metrics_attributes = {}

    for attribute in attributes:
        if (
            str(attribute).lower() in metrics_attributes_to_keep
        ):  # Choose attributes to keep as dimensions
            metrics_attributes[str(attribute).lower()] = attributes[
                str(attribute).lower()
            ]

    queued_duration = float(attributes.get("queued_duration") or 0)
    duration = float(attributes.get("duration") or 0)

    # Log attributes debug information
    log_attributes_debug(metrics_attributes, "parse_metrics_attributes")

    return duration, queued_duration, metrics_attributes
