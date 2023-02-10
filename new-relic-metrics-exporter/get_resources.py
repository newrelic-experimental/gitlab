import json
import os
from datetime import datetime, timedelta
import pytz
import zulu
from opentelemetry.sdk.resources import Resource
from otel import get_logger, create_resource_attributes
from custom_parsers import parse_attributes
import global_variables as var
from custom_parsers import parse_attributes, parse_metrics_attributes
from otel import get_logger, get_meter, create_resource_attributes

var.init()  

GLAB_EXPORT_LAST_MINUTES = var.GLAB_EXPORT_LAST_MINUTES
GLAB_SERVICE_NAME = var.GLAB_SERVICE_NAME
endpoint = var.endpoint
headers = var.headers
gl = var.gl

def get_environments (current_project):
    environments_ids = {}
    project_id = json.loads(current_project.to_json())["id"]
    try:
        environments = current_project.environments.list(get_all=True, sort='desc')
        environments_ids_lst = []
        for environment in environments:
            environment_json = json.loads(environment.to_json())
            if zulu.parse(environment_json["created_at"]) >= (datetime.utcnow().replace(tzinfo=pytz.utc) - timedelta(minutes=int(GLAB_EXPORT_LAST_MINUTES))):
                    environments_ids_lst.append(environment_json["id"])
                    environments_ids[project_id]=environments_ids_lst
    except Exception as e:
        print(current_project['id'],e)
    
    if len(environments_ids) > 0:
        for project_id in environments_ids:
            for environments_id in environments_ids[project_id]:
                attributes_e ={
                "gitlab.source": "gitlab-metrics-exporter",
                "gitlab.resource.type": "environment"
                }
                environment = current_project.environments.get(environments_id)
                environment_json = json.loads(environment.to_json())
                environment_attributes = create_resource_attributes(parse_attributes(environment_json),GLAB_SERVICE_NAME)
                environment_attributes.update(attributes_e)
                environment_resource = Resource(attributes=environment_attributes)
                environment_logger = get_logger(endpoint,headers,environment_resource,"environment_logger")
                #Send runner data as log events with attributes
                environment_logger.info("Environment: "+ str(environment_json['name']) + " data")
                print("Log events sent for environment: " + str(environment_json['name']))
    else:
        print("No environments created in last " + str(GLAB_EXPORT_LAST_MINUTES) + " minutes")
        
def get_deployments (current_project):
    deployments_ids = {}
    project_id = json.loads(current_project.to_json())["id"]
    try:
        deployments = current_project.deployments.list(get_all=True, sort='desc')
        deployments_ids_lst = []
        for deployment in deployments:
            deployment_json = json.loads(deployment.to_json())
            if zulu.parse(deployment_json["created_at"]) >= (datetime.utcnow().replace(tzinfo=pytz.utc) - timedelta(minutes=int(GLAB_EXPORT_LAST_MINUTES))):
                    deployments_ids_lst.append(deployment_json["id"])
                    deployments_ids[project_id]=deployments_ids_lst
    except Exception as e:
        print(project_id,e)

    if len(deployments_ids) > 0:
        for projects in deployments_ids:
            for deployment_id in deployments_ids[projects]:
                attributes_d ={
                "gitlab.source": "gitlab-metrics-exporter",
                "gitlab.resource.type": "deployment"
                }
                deployment = current_project.deployments.get(deployment_id)
                deployment_json = json.loads(deployment.to_json())
                deployment_attributes = create_resource_attributes(parse_attributes(deployment_json), GLAB_SERVICE_NAME)
                deployment_attributes.update(attributes_d)
                deployment_resource = Resource(attributes=deployment_attributes)
                deployment_logger = get_logger(endpoint,headers,deployment_resource,"deployment_logger")
                #Send runner data as log events with attributes
                deployment_logger.info("Deployment: "+ str(deployment_json['id']) + " data")
                print("Log events sent for deployment: " + str(deployment_json['id']))
    else:
        print("No deployments created in last " + str(GLAB_EXPORT_LAST_MINUTES) + " minutes")


def get_releases(current_project):
    releases_tag_name = {}
    project_id = json.loads(current_project.to_json())["id"]
    #Collect releases information
    try:
        releases = current_project.releases.list(get_all=True, sort='desc')
        releases_tag_name_lst = []
        for release in releases:
            release_json = json.loads(release.to_json())
            if zulu.parse(release_json["created_at"]) >= (datetime.utcnow().replace(tzinfo=pytz.utc) - timedelta(minutes=int(GLAB_EXPORT_LAST_MINUTES))):
                    releases_tag_name_lst.append(release_json["tag_name"])
                    releases_tag_name[project_id]=releases_tag_name_lst
    except Exception as e:
        print(project_id,e)

    if len(releases_tag_name) > 0:
         for project_id in releases_tag_name:
            for release_name in releases_tag_name[project_id]:
                attributes_r ={
                "gitlab.source": "gitlab-metrics-exporter",
                "gitlab.resource.type": "release"
                }
                release = current_project.releases.get(release_name)
                release_json = json.loads(release.to_json())
                release_attributes = create_resource_attributes(parse_attributes(release_json),GLAB_SERVICE_NAME)
                release_attributes.update(attributes_r)
                release_resource = Resource(attributes=release_attributes)
                release_logger = get_logger(endpoint,headers,release_resource,"release_logger")
                #Send runner data as log events with attributes
                release_logger.info("Release: "+ str(release_json['name']) + " data")
                print("Log events sent for release: " + str(release_json['name']))
    else:
        print("No releases created in last " + str(GLAB_EXPORT_LAST_MINUTES) + " minutes")

def get_runners(current_project):
    project_id = json.loads(current_project.to_json())["id"]
    runners = current_project.runners.list(get_all=True)
    for runner in runners:
        runner_json = json.loads(runner.to_json())
        if str(runner_json ["is_shared"]).lower() == "false":
            attributes_run = {
            "gitlab.source": "gitlab-metrics-exporter",
            "gitlab.resource.type": "runner"
            }
            runner_attributes = create_resource_attributes(parse_attributes(runner_json),GLAB_SERVICE_NAME)
            runner_attributes.update(attributes_run)
            runner_resource = Resource(attributes=runner_attributes)
            runner_logger = get_logger(endpoint,headers,runner_resource,"runner_logger")
            #Send runner data as log events with attributes
            runner_logger.info("Runner: "+ str(runner_json['id']) + " data")
            print("Log events sent for runner: " + str(runner_json['id']))

def get_pipelines(current_project):
    
    #Collect pipeline information
    pipeline_ids = {}
    project_id = json.loads(current_project.to_json())["id"]
    try:
        print("Gathering pipeline data for project " + str(project_id) + " this may take while...")
        pipelines = current_project.pipelines.list(get_all=True, sort='desc')
        pipeline_ids_lst = []
        for pipeline in pipelines:
            pipeline_json = json.loads(pipeline.to_json())
            if pipeline_json['id'] not in pipeline_ids_lst:
                if zulu.parse(pipeline_json["created_at"]) >= (datetime.utcnow().replace(tzinfo=pytz.utc) - timedelta(minutes=int(GLAB_EXPORT_LAST_MINUTES))):
                        #Ensure we don't export data for exporters jobs
                        jobs = pipeline.jobs.list(get_all=True)
                        for job in jobs:
                            job_json = json.loads(job.to_json())
                            if (job_json['stage']) not in ["new-relic-exporter", "new-relic-metrics-exporter"]:
                                if current_pipeline_json['id'] not in pipeline_ids_lst:
                                    pipeline_ids_lst.append(current_pipeline_json['id'])
                                    pipeline_ids[project_id]=pipeline_ids_lst
    except Exception as e:
        print(project_id,e)

        
    if len(pipeline_ids) > 0:
        for project_id in pipeline_ids:
            for pipeline_id in pipeline_ids[project_id]:
                current_project = gl.projects.get(project_id)
                current_pipeline = current_project.pipelines.get(pipeline_id)
                current_pipeline_json = json.loads(current_pipeline.to_json())
                #Grab pipeline attributes
                current_pipeline_attributes = create_resource_attributes(parse_attributes(current_pipeline_json),GLAB_SERVICE_NAME)
                attributes_pip = {
                "gitlab.source": "gitlab-metrics-exporter",
                "gitlab.resource.type": "pipeline"
                }
                #Check wich dimension to set on each metric
                currrent_pipeline_metrics_attributes = parse_metrics_attributes(current_pipeline_attributes)
                currrent_pipeline_metrics_attributes[2].update(attributes_pip)
                #Create meter to export metrics to NR
                pipeline_resource = Resource(attributes=currrent_pipeline_metrics_attributes[2])
                meter = get_meter(endpoint, headers, pipeline_resource, str(current_pipeline_json["id"]))
                #Create metrics we want to populate
                p_duration= str(current_pipeline_json["id"])+"_duration"
                p_queued_duration= str(current_pipeline_json["id"])+"_queued_duration"
                #Send pipeline metrics with configured dimensions
                p_duration = meter.create_counter("gitlab_pipelines.duration").add(currrent_pipeline_metrics_attributes[0],currrent_pipeline_metrics_attributes[2])
                p_queued_duration = meter.create_counter("gitlab_pipelines.queued_duration").add(currrent_pipeline_metrics_attributes[1],currrent_pipeline_metrics_attributes[2])
                #Update pipeline log event attributes with resource attributes
                current_pipeline_attributes.update(attributes_pip)
                pipeline_resource = Resource(attributes=current_pipeline_attributes)
                pipeline_logger = get_logger(endpoint,headers,pipeline_resource,"pipeline_logger")
                #Send pipeline data as log events with attributes
                pipeline_logger.info("Pipeline: "+ str(pipeline_id) + " data")
                print("Metrics sent for pipeline: " + str(pipeline_id))
                print("Log events sent for pipeline: " + str(pipeline_id))
                jobs = current_pipeline.jobs.list()
                #Collect job information
                for job in jobs:
                    job_json = json.loads(current_project.jobs.get(job.attributes.get('id')).to_json())
                    #Grab job attributes
                    current_job_attributes = create_resource_attributes(parse_attributes(job_json),GLAB_SERVICE_NAME)
                    attributes_j = {
                    "gitlab.source": "gitlab-metrics-exporter",
                    "gitlab.resource.type": "job"
                    }
                    #Check wich dimension to set on each metric
                    job_metrics_attributes = parse_metrics_attributes(current_job_attributes)
                    job_metrics_attributes[2].update(attributes_j)
                    #Create meter to export metrics to NR
                    job_resource = Resource(attributes=job_metrics_attributes[2])
                    meter = get_meter(endpoint, headers, job_resource, str(job_json["id"]))
                    #Create metrics we want to populate
                    j_duration = str(job_json["id"])+"_duration"
                    j_queued_duration= str(job_json["id"])+"_queued_duration"
                    #Send job metrics with configured dimensions
                    j_duration = meter.create_counter("gitlab_jobs.duration").add(job_metrics_attributes[0],job_metrics_attributes[2])
                    j_queued_duration = meter.create_counter("gitlab_jobs.queued_duration").add(job_metrics_attributes[1],job_metrics_attributes[2])
                    #Update job log event attributes with resource attributes
                    current_job_attributes.update(attributes_j)
                    job_resource = Resource(attributes=current_job_attributes)
                    job_logger = get_logger(endpoint,headers,job_resource,"job_logger")
                    #Send job data as log events with attributes
                    job_logger.info("Job: "+ str(job_json['id']) + " data")
                    print("Metrics sent for job: " + str(job_json['id']))
                    print("Log events sent for job: " + str(job_json['id']) + " for pipeline: "+ str(pipeline_id))
    else:
        print("No pipelines ran in last " + str(GLAB_EXPORT_LAST_MINUTES) + " minutes for any project.")
