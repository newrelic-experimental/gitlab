import json
import os
from datetime import datetime, timedelta
import gitlab
import pytz
import zulu
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk.resources import Resource, SERVICE_NAME
from otel import get_logger,create_resource_attributes
from custom_parsers import parse_attributes, do_string
import schedule
import time
import re
from get_resources import get_environments, get_deployments, get_releases, get_runners
import global_variables as var

# Initialize variables
var.init()  
LoggingInstrumentor().instrument(set_logging_format=True)

GLAB_SERVICE_NAME=var.GLAB_SERVICE_NAME
GLAB_PROJECT_OWNERSHIP=var.GLAB_PROJECT_OWNERSHIP
GLAB_PROJECT_VISIBILITY=var.GLAB_PROJECT_VISIBILITY
gl = var.gl
endpoint= var.endpoint
headers=var.headers
GLAB_EXPORT_PROJECTS_REGEX=var.GLAB_EXPORT_PROJECTS_REGEX
GLAB_EXPORT_GROUPS_REGEX=var.GLAB_EXPORT_GROUPS_REGEX
GLAB_EXPORT_NON_GROUP_PROJECTS=var.GLAB_EXPORT_NON_GROUP_PROJECTS

def send_to_nr():
    #Collect project information
    projects = gl.projects.list(owned=GLAB_PROJECT_OWNERSHIP,visibility=GLAB_PROJECT_VISIBILITY,get_all=True)
    project_ids= []
    for project in projects:
        project = gl.projects.get(project.attributes.get('id'))
        project_full_name = str((project.attributes.get('name_with_namespace'))).lower().replace(" ", "")
        GLAB_SERVICE_NAME = project_full_name
        project_json = json.loads(project.to_json())
        attributes_p ={
        "gitlab.source": "gitlab-metrics-exporter",
        "gitlab.resource.type": "project"
        }
        attributes = create_resource_attributes(parse_attributes(project_json), GLAB_SERVICE_NAME)
        attributes.update(attributes_p)
        project_resource = Resource(attributes=attributes)
        project_logger = get_logger(endpoint,headers,project_resource,"project_logger")
        # Check if we should export only data for specified group
        if re.search(str(GLAB_EXPORT_GROUPS_REGEX), project_json['namespace']['name']):
            if re.search(str(GLAB_EXPORT_PROJECTS_REGEX), project_json["name"]):
                if GLAB_EXPORT_NON_GROUP_PROJECTS:
                    project_ids.append(project_json['id'])
                    #Send project information as log events with attributes
                    project_logger.info("Project: "+ str(project_json['id']) + " data")
                    print("Log events sent for project : " + str(project_json['id']))
                else:
                    if str(project_json['namespace']['kind']) != "group":
                        print("Project "+ do_string(str(project_json["name_with_namespace"])) + " not group project and GLAB_EXPORT_NON_GROUP_PROJECTS is set to "+ str(GLAB_EXPORT_NON_GROUP_PROJECTS) +" ...skip...")
                    else:
                        project_ids.append(project_json['id'])
                        #Send project information as log events with attributes
                        project_logger.info("Project: "+ str(project_json['id']) + " data")
                        print("Log events sent for project : " + str(project_json['id']))
            else:
                print("No group project names matched configured regex " + str(GLAB_EXPORT_PROJECTS_REGEX))
        else:
            print("Project "+ do_string(str(project_json["name_with_namespace"])) + " didn't match configured group regex " + str(GLAB_EXPORT_GROUPS_REGEX) + "...skip...")

    if len(project_ids) == 0:
        print("No data matches configured group and project regex, check your configuration")
        exit (1)

    #Collect resource information
    for project_id in project_ids:
        current_project = gl.projects.get(project_id)
        current_project_full_name = str((current_project.attributes.get('name_with_namespace'))).lower().replace(" ", "")
        GLAB_SERVICE_NAME = current_project_full_name
        #Collect environments information
        get_environments(current_project)
        #Collect deployments information
        get_deployments(current_project)
        #Collect releases information
        get_releases(current_project)
        #Collect runners information
        get_runners(current_project)
        
    time.sleep(3)
    print("All data exported to New Relic")

if var.GLAB_STANDALONE:
    # Run once, then schedule every var._EXPORT_LAST_MINUTES
    send_to_nr()
    time.sleep(1)
    schedule.every(int(var.GLAB_EXPORT_LAST_MINUTES)).minutes.do(send_to_nr) 
    while 1:
        n = schedule.idle_seconds()
        if n is None:
            # no more jobs
            break
        elif n > 0:
            # sleep exactly the right amount of time
            print("Next job run in " + str(round(int(n)/60)) + " minutes")
            time.sleep(n)
        schedule.run_pending()
else:
    send_to_nr()