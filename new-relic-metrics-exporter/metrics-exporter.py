import json
import os
from datetime import datetime, timedelta
import gitlab
import pytz
import zulu
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk.resources import Resource
from otel import get_logger, get_meter, create_resource_attributes
from parser import check_env_vars, parse_attributes, parse_metrics_attributes, do_string
import schedule
import time
import re

# Default global variables values
GLAB_STANDALONE=False
GLAB_EXPORT_LAST_MINUTES = 60

# Check if we running as pipeline schedule or standalone mode
if "GLAB_STANDALONE" in os.environ:
    GLAB_STANDALONE = os.getenv('GLAB_STANDALONE')

def send_to_nr():
    check_env_vars()
    
    # Default variable values
    global GLAB_EXPORT_LAST_MINUTES
    GLAB_SERVICE_NAME = ""
    NEW_RELIC_API_KEY = os.getenv('NEW_RELIC_API_KEY')
    GLAB_TOKEN = os.getenv('GLAB_TOKEN')
    GLAB_EXPORT_PROJECTS_REGEX = os.getenv('GLAB_EXPORT_PROJECTS_REGEX')
    GLAB_EXPORT_GROUPS_REGEX = os.getenv('GLAB_EXPORT_GROUPS_REGEX')
    GLAB_EXPORT_ONLY_NON_GROUP_PROJECTS= False

    if "GLAB_EXPORT_ONLY_NON_GROUP_PROJECTS" in os.environ:
        GLAB_EXPORT_ONLY_NON_GROUP_PROJECTS = os.getenv('GLAB_EXPORT_ONLY_NON_GROUP_PROJECTS')
       
    if "GLAB_EXPORT_LAST_MINUTES" in os.environ:
        GLAB_EXPORT_LAST_MINUTES = int(os.getenv('GLAB_EXPORT_LAST_MINUTES'))

    #Check which datacentre we exporting our data to
    if "OTEL_EXPORTER_OTEL_ENDPOINT" in os.environ:
        OTEL_EXPORTER_OTEL_ENDPOINT = os.getenv('OTEL_EXPORTER_OTEL_ENDPOINT')
    else: 
        if NEW_RELIC_API_KEY.startswith("eu"):
            OTEL_EXPORTER_OTEL_ENDPOINT = "https://otlp.eu01.nr-data.net:4318"
        else:
            OTEL_EXPORTER_OTEL_ENDPOINT = "https://otlp.nr-data.net:4318"
        
    # Set gitlab client
    gl = gitlab.Gitlab(private_token="{}".format(GLAB_TOKEN))

    #Set variables to use for OTEL metrics and logs exporters
    endpoint="{}".format(OTEL_EXPORTER_OTEL_ENDPOINT)
    headers="api-key={}".format(NEW_RELIC_API_KEY)
    LoggingInstrumentor().instrument(set_logging_format=True)

    #Collect project information
    projects = gl.projects.list(owned=True,get_all=True)
    project_ids= []
    for project in projects:
        project = gl.projects.get(project.attributes.get('id'))
        project_full_name = str((project.attributes.get('name_with_namespace'))).lower().replace(" ", "")
        if "GLAB_SERVICE_NAME" in os.environ:
            GLAB_SERVICE_NAME = os.getenv('GLAB_SERVICE_NAME')
        else:
            GLAB_SERVICE_NAME=project_full_name

        project_json = json.loads(project.to_json())

        # Check if we should export only data for specified group
        if not GLAB_EXPORT_ONLY_NON_GROUP_PROJECTS:
            if re.search(str(GLAB_EXPORT_GROUPS_REGEX), project_json['namespace']['name']):
                if re.search(str(GLAB_EXPORT_PROJECTS_REGEX), project_json["name"]):
                    project_ids.append(project_json['id'])
                    attributes = create_resource_attributes(parse_attributes(project_json), GLAB_SERVICE_NAME)
                    project_resource = Resource(attributes=attributes)
                    project_logger = get_logger(endpoint,headers,project_resource,"project_logger")
                    #Create meter to export metrics to NR
                    meter = get_meter(endpoint, headers, project_resource, "meter")
                    #Create metrics we want to populate
                    pipelines_duration = meter.create_counter("gitlab_pipelines.duration")
                    pipelines_queued_duration = meter.create_counter("gitlab_pipelines.queued_duration")
                    jobs_duration = meter.create_counter("gitlab_jobs.duration")
                    jobs_queued_duration = meter.create_counter("gitlab_jobs.queued_duration")
                    #Send project information as log events with attributes
                    project_logger.info("Project: "+ str(project_json['id']) + " data")
                    print("Log events sent for project : " + str(project_json['id']))
                else:
                    print("No group project names matched configured regex " + str(GLAB_EXPORT_PROJECTS_REGEX))
            else:
                print("Project "+ do_string(str(project_json["name_with_namespace"])) + " didn't match configured group regex " + str(GLAB_EXPORT_GROUPS_REGEX) + "...skip...")
        else:
            if project_json['namespace']['kind'] != "group":
                if re.search(str(GLAB_EXPORT_PROJECTS_REGEX), project_json["name"]):
                    project_ids.append(project_json['id'])
                    attributes = create_resource_attributes(parse_attributes(project_json), GLAB_SERVICE_NAME)
                    project_resource = Resource(attributes=attributes)
                    project_logger = get_logger(endpoint,headers,project_resource,"project_logger")
                    #Create meter to export metrics to NR
                    meter = get_meter(endpoint, headers, project_resource, "meter")
                    #Create metrics we want to populate
                    pipelines_duration = meter.create_counter("gitlab_pipelines.duration")
                    pipelines_queued_duration = meter.create_counter("gitlab_pipelines.queued_duration")
                    jobs_duration = meter.create_counter("gitlab_jobs.duration")
                    jobs_queued_duration = meter.create_counter("gitlab_jobs.queued_duration")
                    #Send project information as log events with attributes
                    project_logger.info("Project: "+ str(project_json['id']) + " data")
                    print("Log events sent for project : " + str(project_json['id']))
                else:
                    print("Project "+ str(project_json['id']) + "did not match configured project regex" + str(GLAB_EXPORT_PROJECTS_REGEX) + "...skip...")
            else:
                print("Project "+ do_string(str(project_json["name_with_namespace"]))) + " not user project...skip..."  

    if len(project_ids) == 0:
        print("No data matches configured regex")
        exit (1)

    #Collect environments information
    environments_ids_lst = []
    for project_id in project_ids:
        current_project = gl.projects.get(project_id)
        environments = current_project.environments.list(get_all=True, sort='desc')
        environments_ids = {}
        for environment in environments:
            environment_json = json.loads(environment.to_json())
            if zulu.parse(environment_json["created_at"]) >= (datetime.utcnow().replace(tzinfo=pytz.utc) - timedelta(minutes=int(GLAB_EXPORT_LAST_MINUTES))):
                    environments_ids_lst.append(environment_json["id"])
                    environments_ids[project_id]=environments_ids_lst

    if len(environments_ids) > 0:
        for project_id in environments_ids:
            for environments_id in environments_ids[project_id]:
                current_project = gl.projects.get(project_id)
                environment = current_project.environments.get(environments_id)
                environment_json = json.loads(environment.to_json())
                environment_attributes = create_resource_attributes(parse_attributes(environment_json),GLAB_SERVICE_NAME)
                environment_resource = Resource(attributes=environment_attributes)
                environment_logger = get_logger(endpoint,headers,environment_resource,"environment_logger")
                #Send runner data as log events with attributes
                environment_logger.info("Environment: "+ str(environment_json['name']) + " data")
                print("Log events sent for environment: " + str(environment_json['name']))
    else:
        print("No environments created in last " + str(GLAB_EXPORT_LAST_MINUTES) + " minutes")

    deployments_ids = {}
    #Collect deployments information
    for project_id in project_ids:
        current_project = gl.projects.get(project_id)
        deployments = current_project.deployments.list(get_all=True, sort='desc')
        deployments_ids_lst = []
        for deployment in deployments:
            deployment_json = json.loads(deployment.to_json())
            if zulu.parse(deployment_json["created_at"]) >= (datetime.utcnow().replace(tzinfo=pytz.utc) - timedelta(minutes=int(GLAB_EXPORT_LAST_MINUTES))):
                    deployments_ids_lst.append(deployment_json["id"])
                    deployments_ids[project_id]=deployments_ids_lst

    if len(deployments_ids) > 0:
        for projects in deployments_ids:
            for deployment_id in deployments_ids[projects]:
                current_project = gl.projects.get(projects)
                deployment = current_project.deployments.get(deployment_id)
                deployment_json = json.loads(deployment.to_json())
                deployment_attributes = create_resource_attributes(parse_attributes(deployment_json), GLAB_SERVICE_NAME)
                deployment_resource = Resource(attributes=deployment_attributes)
                deployment_logger = get_logger(endpoint,headers,deployment_resource,"deployment_logger")
                #Send runner data as log events with attributes
                deployment_logger.info("Deployment: "+ str(deployment_json['id']) + " data")
                print("Log events sent for deployment: " + str(deployment_json['id']))
    else:
        print("No deployments created in last " + str(GLAB_EXPORT_LAST_MINUTES) + " minutes")
    

    releases_tag_name = {}
    #Collect releases information
    for project_id in project_ids:
        current_project = gl.projects.get(project_id)
        releases = current_project.releases.list(get_all=True, sort='desc')
        releases_tag_name_lst = []
        for release in releases:
            release_json = json.loads(release.to_json())
            if zulu.parse(release_json["created_at"]) >= (datetime.utcnow().replace(tzinfo=pytz.utc) - timedelta(minutes=int(GLAB_EXPORT_LAST_MINUTES))):
                    releases_tag_name_lst.append(release_json["tag_name"])
                    releases_tag_name[project_id]=releases_tag_name_lst

    if len(releases_tag_name) > 0:
         for project_id in releases_tag_name:
            for release_name in releases_tag_name[project_id]:
                current_project = gl.projects.get(project_id)
                release = current_project.releases.get(release_name)
                release_json = json.loads(release.to_json())
                release_attributes = create_resource_attributes(parse_attributes(release_json),GLAB_SERVICE_NAME)
                release_resource = Resource(attributes=release_attributes)
                release_logger = get_logger(endpoint,headers,release_resource,"release_logger")
                #Send runner data as log events with attributes
                release_logger.info("Release: "+ str(release_json['name']) + " data")
                print("Log events sent for release: " + str(release_json['name']))
    else:
        print("No releases created in last " + str(GLAB_EXPORT_LAST_MINUTES) + " minutes")

    #Collect pipeline information
    pipeline_ids = {}
    for project_id in project_ids:
        current_project = gl.projects.get(project_id)
        print("Gathering pipeline data for project " + str(project_id) + " this may take while...")
        pipelines = current_project.pipelines.list(get_all=True, sort='desc')
        pipeline_ids_lst = []
        for pipeline in pipelines:
            pipeline_json = json.loads(pipeline.to_json())
            if pipeline_json['id'] not in pipeline_ids_lst:
                if zulu.parse(pipeline_json["created_at"]) >= (datetime.utcnow().replace(tzinfo=pytz.utc) - timedelta(minutes=int(GLAB_EXPORT_LAST_MINUTES))):
                    pipeline_ids_lst.append(pipeline_json['id'])
                    pipeline_ids[project_id]=pipeline_ids_lst

    #Ensure we don't export data for new-relic-exporter jobs
    current_pipeline_ids = {}
    for project_id in pipeline_ids:
        current_pipeline_ids_lst = []
        for pipeline_id in pipeline_ids[project_id]:
            current_project = gl.projects.get(project_id)
            current_pipeline = current_project.pipelines.get(pipeline_id)
            current_pipeline_json = json.loads(current_pipeline.to_json())
            jobs = current_pipeline.jobs.list(get_all=True)
            for job in jobs:
                job_json = json.loads(job.to_json())
                if (job_json['stage']) not in ["new-relic-exporter", "new-relic-metrics-exporter"]:
                    if current_pipeline_json['id'] not in current_pipeline_ids_lst:
                        current_pipeline_ids_lst.append(current_pipeline_json['id'])
                        current_pipeline_ids[project_id]=current_pipeline_ids_lst

    if len(current_pipeline_ids) > 0:
        for project_id in current_pipeline_ids:
            for pipeline_id in current_pipeline_ids[project_id]:
                current_project = gl.projects.get(project_id)
                current_pipeline = current_project.pipelines.get(pipeline_id)
                current_pipeline_json = json.loads(current_project.to_json())
                pipeline_attributes = create_resource_attributes(parse_attributes(current_pipeline_json),GLAB_SERVICE_NAME)
                #Send pipeline metrics with dimensions
                pipeline_metrics_attributes = parse_metrics_attributes(pipeline_attributes)
                pipelines_duration.add(pipeline_metrics_attributes[0],pipeline_metrics_attributes[2])
                pipelines_queued_duration.add(pipeline_metrics_attributes[1],pipeline_metrics_attributes[2])
                pipeline_resource = Resource(attributes=pipeline_attributes)
                pipeline_logger = get_logger(endpoint,headers,pipeline_resource,"pipeline_logger")
                #Send pipeline data as log events with attributes
                pipeline_logger.info("Pipeline: "+ str(pipeline_id) + " data")
                print("Metrics sent for pipeline: " + str(pipeline_id))
                print("Log events sent for pipeline: " + str(pipeline_id))
                jobs = current_pipeline.jobs.list()
                #Collect job information
                for job in jobs:
                    job_json = json.loads(current_project.jobs.get(job.attributes.get('id')).to_json())
                    job_attributes = create_resource_attributes(parse_attributes(job_json),GLAB_SERVICE_NAME)
                    #Send job metrics with dimensions
                    job_metrics_attributes = parse_metrics_attributes(job_attributes)
                    jobs_duration.add(job_metrics_attributes[0],job_metrics_attributes[2])
                    jobs_queued_duration.add(job_metrics_attributes[1],job_metrics_attributes[2])
                    job_resource = Resource(attributes=job_attributes)
                    job_logger = get_logger(endpoint,headers,job_resource,"job_logger")
                    #Send job data as log events with attributes
                    job_logger.info("Job: "+ str(job_json['id']) + " data")
                    print("Metrics sent for job: " + str(job_json['id']))
                    print("Log events sent for job: " + str(job_json['id']) + " for pipeline: "+ str(pipeline_id))
    else:
        print("No pipelines ran in last " + str(GLAB_EXPORT_LAST_MINUTES) + " minutes for any project.")

    #Collect runners information
    runners = gl.runners.list(get_all=True)
    for runner in runners:
        runner_json = json.loads(runner.to_json())
        runner_attributes = create_resource_attributes(parse_attributes(runner_json),GLAB_SERVICE_NAME)
        runner_resource = Resource(attributes=runner_attributes)
        runner_logger = get_logger(endpoint,headers,runner_resource,"runner_logger")
        #Send runner data as log events with attributes
        runner_logger.info("Runner: "+ str(runner_json['id']) + " data")
        print("Log events sent for runner: " + str(runner_json['id']))

    time.sleep(3)
    print("All data exported to New Relic")

if GLAB_STANDALONE:
    # Run once, then schedule every GLAB_EXPORT_LAST_MINUTES
    send_to_nr()
    time.sleep(1)
    schedule.every(int(GLAB_EXPORT_LAST_MINUTES)).minutes.do(send_to_nr) 
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