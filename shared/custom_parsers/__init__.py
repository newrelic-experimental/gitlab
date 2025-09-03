import time
from pyrfc3339 import parse
import os
from re import search

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
    keys = ("GLAB_TOKEN", "NEW_RELIC_API_KEY")

    keys_not_set = []

    for key in keys:
        if key not in os.environ:
            keys_not_set.append(key)
    else:
        pass

    if len(keys_not_set) > 0:
        for key in keys_not_set:
            print(key + " not set")
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
            except:
                print("Unable to parse GLAB_ENVS_DROP, check your configuration")

        for item in atts_to_remove:
            atts.pop(item, None)

        # Filter out None values, empty strings, and problematic task-related attributes
        problematic_attrs = {
            "taskName",
            "task_name",
            "TASK_NAME",
            "CICD_PIPELINE_TASK_NAME",
            "CI_PIPELINE_TASK_NAME",
            "CI_TASK_NAME",
            "CI_JOB_TASK_NAME",
            "GITLAB_TASK_NAME",
            "PIPELINE_TASK_NAME",
            "JOB_TASK_NAME",
        }

        filtered_atts = {
            key: value
            for key, value in atts.items()
            if value is not None
            and value != ""
            and value != "None"
            and key not in problematic_attrs
        }

    except Exception as e:
        print(e)
        filtered_atts = {}

    return filtered_atts


def parse_attributes(obj):
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
        except:
            print("Unable to parse GLAB_ATTRIBUTES_DROP, check your configuration")

    for attribute in obj:
        attribute_name = str(attribute).lower()
        if attribute_name not in attributes_to_drop:
            if do_parse(obj[attribute]):
                if type(obj[attribute]) is dict:
                    for sub_att in obj[attribute]:
                        attribute_name = do_string(attribute) + "." + do_string(sub_att)
                        if attribute_name not in attributes_to_drop:
                            if type(obj[attribute][sub_att]) is dict:
                                for att in obj[attribute][sub_att]:
                                    attribute_name = (
                                        do_string(attribute)
                                        + "."
                                        + do_string(sub_att)
                                        + "."
                                        + do_string(att)
                                    )
                                    if attribute_name not in attributes_to_drop:
                                        if GLAB_CONVERT_TO_TIMESTAMP:
                                            if search("_at|_date", attribute_name):
                                                if do_parse(
                                                    str(obj[attribute][sub_att][att])
                                                ):
                                                    obj_atts[attribute_name] = do_time(
                                                        str(
                                                            obj[attribute][sub_att][att]
                                                        )
                                                    )
                                                else:
                                                    obj_atts[attribute_name] = str(
                                                        obj[attribute][sub_att][att]
                                                    )
                                            else:
                                                obj_atts[attribute_name] = str(
                                                    obj[attribute][sub_att][att]
                                                )
                                        else:
                                            obj_atts[attribute_name] = str(
                                                obj[attribute][sub_att][att]
                                            )

                            elif type(obj[attribute][sub_att]) is list:
                                for key in obj[attribute][sub_att]:
                                    if type(key) is dict:
                                        for att in key:
                                            if do_parse(key[att]):
                                                attribute_name = (
                                                    do_string(attribute)
                                                    + "."
                                                    + do_string(sub_att)
                                                    + "."
                                                    + do_string(att)
                                                )
                                                if (
                                                    attribute_name
                                                    not in attributes_to_drop
                                                ):
                                                    if GLAB_CONVERT_TO_TIMESTAMP:
                                                        if search(
                                                            "_at|_date", attribute_name
                                                        ):
                                                            if do_parse(str(key[att])):
                                                                obj_atts[
                                                                    attribute_name
                                                                ] = do_time(
                                                                    str(key[att])
                                                                )
                                                            else:
                                                                obj_atts[
                                                                    attribute_name
                                                                ] = str(key[att])
                                                        else:
                                                            obj_atts[attribute_name] = (
                                                                str(key[att])
                                                            )
                                                    else:
                                                        obj_atts[attribute_name] = str(
                                                            key[att]
                                                        )

                                    else:
                                        attribute_name = (
                                            do_string(attribute)
                                            + "."
                                            + do_string(sub_att)
                                        )
                                        if attribute_name not in attributes_to_drop:
                                            if GLAB_CONVERT_TO_TIMESTAMP:
                                                if search("_at|_date", attribute_name):
                                                    if do_parse(str(key)):
                                                        obj_atts[attribute_name] = (
                                                            do_time(str(key))
                                                        )
                                                    else:
                                                        obj_atts[attribute_name] = str(
                                                            key
                                                        )
                                                else:
                                                    obj_atts[attribute_name] = str(key)
                                            else:
                                                obj_atts[attribute_name] = str(key)
                            else:
                                attribute_name = (
                                    do_string(attribute) + "." + do_string(sub_att)
                                )
                                if attribute_name not in attributes_to_drop:
                                    if GLAB_CONVERT_TO_TIMESTAMP:
                                        if search("_at|_date", attribute_name):
                                            if do_parse(str(obj[attribute][sub_att])):
                                                obj_atts[attribute_name] = do_time(
                                                    str(obj[attribute][sub_att])
                                                )
                                            else:
                                                obj_atts[attribute_name] = str(
                                                    obj[attribute][sub_att]
                                                )
                                        else:
                                            obj_atts[attribute_name] = str(
                                                obj[attribute][sub_att]
                                            )
                                    else:
                                        obj_atts[attribute_name] = str(
                                            obj[attribute][sub_att]
                                        )

                elif type(obj[attribute]) is list:
                    for key in obj[attribute]:
                        if type(key) is dict:
                            for att in key:
                                if do_parse(key[att]):
                                    attribute_name = (
                                        do_string(attribute) + "." + do_string(att)
                                    )
                                    if attribute_name not in attributes_to_drop:
                                        if GLAB_CONVERT_TO_TIMESTAMP:
                                            if search("_at|_date", attribute_name):
                                                if do_parse(str(key[att])):
                                                    obj_atts[attribute_name] = do_time(
                                                        str(key[att])
                                                    )
                                                else:
                                                    obj_atts[attribute_name] = str(
                                                        key[att]
                                                    )
                                            else:
                                                obj_atts[attribute_name] = str(key[att])
                                        else:
                                            obj_atts[attribute_name] = str(key[att])
                else:
                    if do_parse(obj[attribute]):
                        attribute_name = do_string(attribute)
                        if attribute_name not in attributes_to_drop:
                            if GLAB_CONVERT_TO_TIMESTAMP:
                                if search("_at|_date", attribute_name):
                                    if do_parse(str(obj[attribute])):
                                        obj_atts[attribute_name] = do_time(
                                            str(obj[attribute])
                                        )
                                    else:
                                        obj_atts[attribute_name] = str(obj[attribute])
                                else:
                                    obj_atts[attribute_name] = str(obj[attribute])
                            else:
                                obj_atts[attribute_name] = str(obj[attribute])
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
        except:
            print(
                "Unable to parse GLAB_DIMENSION_METRICS, exporting with default dimensions, check your configuration"
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
