import time
from pyrfc3339 import parse
import os

def do_time(string):
    return (int(round(time.mktime(parse(string).timetuple())) * 1000000000))

def do_string(string):
    return str(string).lower().replace(" ", "")

def do_parse(string):
    return string != "" and string is not None and string != "None"

def check_env_vars():
    keys = ("GLAB_TOKEN","NEW_RELIC_API_KEY","GLAB_EXPORT_PROJECTS_REGEX")
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
        print("All required environment variables set, starting new-relic-exporter.")

def grab_span_att_vars():
    # Grab list enviroment variables to set as span attributes
    try:
        atts = os.environ
        # Remove unwanted/sensitive attributes
        for att in atts:
            if not att.startswith('CI') | att.startswith('GIT') | att.startswith('GLAB') | att.startswith('NEW') | att.startswith('OTEL') :
                atts.pop(att,None)

        atts_to_remove=["NEW_RELIC_API_KEY","GITLAB_FEATURES","CI_SERVER_TLS_CA_FILE","CI_RUNNER_TAGS","CI_JOB_JWT","CI_JOB_JWT_V1","CI_JOB_JWT_V2","GLAB_TOKEN","GIT_ASKPASS","CI_COMMIT_BEFORE_SHA","CI_BUILD_TOKEN","CI_DEPENDENCY_PROXY_PASSWORD","CI_RUNNER_SHORT_TOKEN","CI_BUILD_BEFORE_SHA","CI_BEFORE_SHA","OTEL_EXPORTER_OTEL_ENDPOINT"]
        if "GLAB_ENVS_DROP" in os.environ:
            attributes=os.getenv('GLAB_ENVS_DROP')
            atts_to_remove.append(attributes.split(","))
        for item in atts_to_remove:
            atts.pop(item, None)      

    except Exception as e:
        print(e)

    return atts

def parse_attributes(obj):
    obj_atts = {}
    attributes_to_drop = [""]
    if "GLAB_ATTRIBUTES_DROP" in os.environ:
        attributes=os.getenv('GLAB_ATTRIBUTES_DROP')
        attributes_to_drop.append(attributes.split(","))
    for attribute in obj:
        attribute_name = str(attribute)
        if attribute_name not in attributes_to_drop:
            if do_parse(obj[attribute]):
                if type(obj[attribute]) is dict:
                    for sub_att in obj[attribute]:
                        attribute_name = do_string(attribute)+"."+do_string(sub_att)
                        if attribute_name not in attributes_to_drop:
                            if type(obj[attribute][sub_att]) is dict:
                                for att in obj[attribute][sub_att]:
                                    attribute_name = do_string(attribute)+"."+do_string(sub_att)+"."+do_string(att)
                                    if attribute_name not in attributes_to_drop:
                                        obj_atts[attribute_name]=str(obj[attribute][sub_att][att])

                            elif type(obj[attribute][sub_att]) is list:
                                for key in obj[attribute][sub_att]:
                                    if type(key) is dict:
                                        for att in key:
                                            if do_parse(key[att]):
                                                attribute_name = do_string(attribute)+"."+do_string(sub_att)+"."+do_string(att)
                                                if attribute_name not in attributes_to_drop:
                                                    obj_atts[attribute_name]=str(key[att])
                                    else:
                                        attribute_name = do_string(attribute)+"."+do_string(sub_att)
                                        if attribute_name not in attributes_to_drop:
                                            obj_atts[attribute_name]=str(key)
                            else:
                                attribute_name = do_string(attribute)+"."+do_string(sub_att)
                                if attribute_name not in attributes_to_drop:
                                    obj_atts[attribute_name]=str(obj[attribute][sub_att])

                elif type(obj[attribute]) is list:
                    for key in obj[attribute]:
                        if type(key) is dict:
                            for att in key:
                                if do_parse(key[att]):
                                    attribute_name = do_string(attribute)+"."+do_string(att)
                                    if attribute_name not in attributes_to_drop:
                                        obj_atts[attribute_name]=str(key[att])
                else:
                    if do_parse(obj[attribute]):
                        attribute_name = do_string(attribute)
                        if attribute_name not in attributes_to_drop:
                            obj_atts[attribute_name]=str(obj[attribute])
    return obj_atts

def parse_metrics_attributes(attributes):
    metrics_attributes_to_keep = ["status","stage","name"]
    metrics_attributes = {}
    if "GLAB_DIMENSION_METRICS" in os.environ:
        metrics_attributes_to_keep.append(str(os.environ("GLAB_DIMENSION_METRICS")).split(","))
    for attribute in attributes:
        if str(attribute) in metrics_attributes_to_keep: #Choose attributes to keep as dimensions
            metrics_attributes[attribute]=attributes[attribute]

    if "queued_duration" in attributes:
        queued_duration=float(attributes["queued_duration"])
    else:
        queued_duration=0    

    if "duration" in attributes:
        duration=float(attributes["duration"])
    else:
        duration=0

    return duration, queued_duration, metrics_attributes    