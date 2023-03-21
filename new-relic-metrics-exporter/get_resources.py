import json
from datetime import datetime, timedelta, date
import pytz
import zulu
from opentelemetry.sdk.resources import Resource
from otel import get_logger, create_resource_attributes
from custom_parsers import parse_attributes
from custom_parsers import parse_attributes, parse_metrics_attributes
from otel import get_logger, get_meter, create_resource_attributes
from custom_parsers import parse_attributes
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME
import re
from global_variables import *
import requests

LoggingInstrumentor().instrument(set_logging_format=True)

def grab_data(project):
    try:
        #Collect project information
        GLAB_SERVICE_NAME = str((project.attributes.get('name_with_namespace'))).lower().replace(" ", "")
        project_json = json.loads(project.to_json())
        attributes_p ={
        "gitlab.source": "gitlab-metrics-exporter",
        "gitlab.resource.type": "project"
        }
        attributes = create_resource_attributes(parse_attributes(project_json), GLAB_SERVICE_NAME)
        attributes.update(attributes_p)
        project_resource = Resource(attributes=attributes)
        project_logger = get_logger(endpoint,headers,project_resource,"project_logger")
        # Check if we should export only data for specific groups/projects
        if paths:
            for path in paths:          
                if str(project_json["namespace"]["full_path"]) == (str(path)):
                    if re.search(str(GLAB_EXPORT_PROJECTS_REGEX), project_json["name"]):
                        try:
                            print("Project: "+str((project.attributes.get('name_with_namespace'))).lower().replace(" ", "") + " matched configuration, collecting data...")
                            get_all_resources(project)
                        except Exception as e:
                            print(e + " -> Failed to collect data for project:  "+str((project.attributes.get('name_with_namespace'))).lower().replace(" ", "")+" check your configuration.")
                        if GLAB_DORA_METRICS:
                            try:
                                get_dora_metrics(project)
                            except Exception as e:
                                print("Unable to obtain DORA metrics ",e)
                        # If we don't need to export all projects each time
                        # if zulu.parse(project_json["last_activity_at"]) >= (datetime.utcnow().replace(tzinfo=pytz.utc) - timedelta(minutes=int(GLAB_EXPORT_LAST_MINUTES))):
                        #Send project information as log events with attributes
                        project_logger.info("Project: "+ str(project_json['id']) + " - "+ str(GLAB_SERVICE_NAME) + " data")
                        print("Log events sent for project: " + str(project_json['id']) + " - " + str(GLAB_SERVICE_NAME))              
                    else:
                        print("No project name matched configured regex " + "\"" + str(GLAB_EXPORT_PROJECTS_REGEX)+ "\" in path " + "\""+str(path)+"\"")
        else:
            print("GLAB_EXPORT_PATHS not configured")
            exit(1)  
                 
    except Exception as e:
        print(e + " -> ERROR obtaining data for project:  "+str((project.attributes.get('name_with_namespace'))).lower().replace(" ", ""))

def get_dora_metrics(current_project):
    GLAB_SERVICE_NAME = str((current_project.attributes.get('name_with_namespace'))).lower().replace(" ", "")
    project_id = json.loads(current_project.to_json())["id"]
    today = date.today()-timedelta(days=1)
    deployment_frequency = str(GLAB_ENDPOINT)+"/api/v4/projects/"+str(project_id)+"/dora/metrics?metric=deployment_frequency&start_date="+str(today)
    lead_time_for_changes = str(GLAB_ENDPOINT)+"/api/v4/projects/"+str(project_id)+"/dora/metrics?metric=lead_time_for_changes&start_date"+str(today)
    time_to_restore_service = str(GLAB_ENDPOINT)+"/api/v4/projects/"+str(project_id)+"/dora/metrics?metric=time_to_restore_service&start_date"+str(today)
    change_failure_rate = str(GLAB_ENDPOINT)+"/api/v4/projects/"+str(project_id)+"/dora/metrics?metric=change_failure_rate&start_date"+str(today)
    metrics = {"deployment_frequency":deployment_frequency,"lead_time_for_changes":lead_time_for_changes,"time_to_restore_service":time_to_restore_service,"change_failure_rate":change_failure_rate}
    req_headers = {
    'PRIVATE-TOKEN': GLAB_TOKEN,
    }
    attributes_dora_metrics ={
        SERVICE_NAME: GLAB_SERVICE_NAME,
        "gitlab.source": "gitlab-metrics-exporter",
        "gitlab.resource.type": "dora-metrics",
        "project.id": project_id,
        "namespace.path": json.loads(current_project.to_json())["namespace"]["path"],
        "namespace.kind": json.loads(current_project.to_json())["namespace"]["kind"],
        "url": json.loads(current_project.to_json())["web_url"]
        }
    dora_metrics_resource = Resource(attributes=attributes_dora_metrics)
    meter = get_meter(endpoint, headers, dora_metrics_resource, str(project_id))
    for metric in metrics:
        r = requests.get(metrics[metric],headers=req_headers)
        if r.status_code == 200 and len(r.text) > 2:
            #Create metrics we want to populate
            res = json.loads(r.text)
            for i in range(len(res)):
                if res[i]['value'] is not None:
                    if metric == "change_failure_rate":
                        meter.create_counter("gitlab_dora_"+str(metric)).add(res[i]['value']*100,attributes={"date":str(res[i]['date'])})
                    else:
                        meter.create_counter("gitlab_dora_"+str(metric)).add(res[i]['value'],attributes={"date":str(res[i]['date'])})
                else:
                    meter.create_counter("gitlab_dora_"+str(metric)).add(0,attributes={"date":str(res[i]['date'])})
                
                
            
def get_all_resources(current_project):
    #Collect environments information
    get_environments(current_project)
    #Collect deployments information
    get_deployments(current_project)
    #Collect releases information
    get_releases(current_project)
    #Collect runners information
    get_runners(current_project)
    #Collect pipeline information
    get_pipelines(current_project)
    
def get_environments (current_project):
    project_id = json.loads(current_project.to_json())["id"]
    GLAB_SERVICE_NAME = str((current_project.attributes.get('name_with_namespace'))).lower().replace(" ", "")
    try:
        environments = current_project.environments.list(get_all=True, updated_after=str((datetime.utcnow().replace(tzinfo=pytz.utc) - timedelta(minutes=int(GLAB_EXPORT_LAST_MINUTES)))))
        if len(environments) > 0: # check if there are environments in this project
            for environment in environments:
                environment_json = json.loads(environment.to_json())
                attributes_e ={
                "gitlab.source": "gitlab-metrics-exporter",
                "gitlab.resource.type": "environment"
                }
                environment = current_project.environments.get(environment_json['id'])
                environment_attributes = create_resource_attributes(parse_attributes(environment_json),GLAB_SERVICE_NAME)
                environment_attributes.update(attributes_e)
                environment_resource = Resource(attributes=environment_attributes)
                environment_logger = get_logger(endpoint,headers,environment_resource,"environment_logger")
                #Send environment data as log events with attributes                  
                environment_logger.info("Environment: "+ str(environment_json['id'])+ " from project: " + str(project_id) + " - " + str(GLAB_SERVICE_NAME) + " data")
                print("Log events sent for environment: " + str(environment_json['id'])+ " from project: " + str(project_id) + " - " + str(GLAB_SERVICE_NAME))
            
    except Exception as e:
        print(project_id,e)
        
def get_deployments (current_project):
    project_id = json.loads(current_project.to_json())["id"]
    GLAB_SERVICE_NAME = str((current_project.attributes.get('name_with_namespace'))).lower().replace(" ", "")
    try:
        deployments = current_project.deployments.list(get_all=True, updated_after=str((datetime.utcnow().replace(tzinfo=pytz.utc) - timedelta(minutes=int(GLAB_EXPORT_LAST_MINUTES)))))
        if len(deployments) > 0: # check if there are deployments in this project
            for deployment in deployments:
                deployment_json = json.loads(deployment.to_json())
                attributes_d ={
                "gitlab.source": "gitlab-metrics-exporter",
                "gitlab.resource.type": "deployment"
                }
                deployment = current_project.deployments.get(deployment_json['id'])
                deployment_attributes = create_resource_attributes(parse_attributes(deployment_json), GLAB_SERVICE_NAME)
                deployment_attributes.update(attributes_d)
                deployment_resource = Resource(attributes=deployment_attributes)
                deployment_logger = get_logger(endpoint,headers,deployment_resource,"deployment_logger")
                #Send deployment data as log events with attributes
                deployment_logger.info("Deployment: "+ str(deployment_json['id'])+ " from project: " + str(project_id) + " - " + str(GLAB_SERVICE_NAME) + " data")
                print("Log events sent for deployment: " + str(deployment_json['id'])+ " from project: " + str(project_id) + " - " + str(GLAB_SERVICE_NAME))           
                
    except Exception as e:
        print(project_id,e)

def get_releases(current_project):
    project_id = json.loads(current_project.to_json())["id"]
    GLAB_SERVICE_NAME = str((current_project.attributes.get('name_with_namespace'))).lower().replace(" ", "")
    #Collect releases information
    try:
        releases = current_project.releases.list(get_all=True, sort='desc')
        if len(releases) > 0: # check if there are releases in this project
            for release in releases:
                release_json = json.loads(release.to_json())
                if zulu.parse(release_json["created_at"]) >= (datetime.utcnow().replace(tzinfo=pytz.utc) - timedelta(minutes=int(GLAB_EXPORT_LAST_MINUTES))):
                    attributes_r ={
                    "gitlab.source": "gitlab-metrics-exporter",
                    "gitlab.resource.type": "release"
                    }
                    release = current_project.releases.get(release)
                    release_json = json.loads(release.to_json())
                    release_attributes = create_resource_attributes(parse_attributes(release_json),GLAB_SERVICE_NAME)
                    release_attributes.update(attributes_r)
                    release_resource = Resource(attributes=release_attributes)
                    release_logger = get_logger(endpoint,headers,release_resource,"release_logger")
                    #Send releases data as log events with attributes
                    release_logger.info("Release: "+ str(release_json['id'])+ " from project: " + str(project_id) + " - " + str(GLAB_SERVICE_NAME) + " data")
                    print("Log events sent for release: " + str(release_json['id'])+ " from project: " + str(project_id) + " - " + str(GLAB_SERVICE_NAME))
            
    except Exception as e:
        print(project_id,e)

def get_runners(current_project):
    try:
        project_id = json.loads(current_project.to_json())["id"]
        runners = current_project.runners.list(get_all=True)
        GLAB_SERVICE_NAME = str((current_project.attributes.get('name_with_namespace'))).lower().replace(" ", "")
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
                runner_logger.info("Runner: "+ str(runner_json['id'])+ " from project: " + str(project_id) + " - " + str(GLAB_SERVICE_NAME) + " data")
                print("Log events sent for runner: " + str(runner_json['id'])+ " from project: " + str(project_id) + " - " + str(GLAB_SERVICE_NAME))
    except Exception as e:
        print(project_id,e)

def get_pipelines(current_project):
    project_id = json.loads(current_project.to_json())["id"]
    GLAB_SERVICE_NAME = str((current_project.attributes.get('name_with_namespace'))).lower().replace(" ", "")
    try:
        print("Gathering pipeline data for project " + str(project_id) + " this may take while...")
        pipelines = current_project.pipelines.list(get_all=True, updated_after=str((datetime.utcnow().replace(tzinfo=pytz.utc) - timedelta(minutes=int(GLAB_EXPORT_LAST_MINUTES)))))
        for pipeline in pipelines:
            pipeline_json = json.loads(pipeline.to_json())
            pipeline_id = pipeline_json['id']
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
            pipeline_logger.info("Pipeline: "+ str(pipeline_id)+ " - " + "from project: " + str(project_id)+ " - " + str(GLAB_SERVICE_NAME) + " data")
            print("Metrics sent for pipeline: " + str(pipeline_id)+ " - " + "from project: " + str(project_id)+ " - " + str(GLAB_SERVICE_NAME))
            print("Log events sent for pipeline: " + str(pipeline_id)+ " - " + "from project: " + str(project_id)+ " - " + str(GLAB_SERVICE_NAME))
            #Collect job information
            get_jobs(current_project,current_pipeline)

    except Exception as e:
        print(project_id,e)
        
def get_jobs(current_project,current_pipeline):
    try:
        project_id = json.loads(current_project.to_json())["id"]
        GLAB_SERVICE_NAME = str((current_project.attributes.get('name_with_namespace'))).lower().replace(" ", "")
        jobs = current_pipeline.jobs.list(get_all=True)
        current_pipeline_json = json.loads(current_pipeline.to_json())
        #Collect job information
        for job in jobs:
            #Ensure we don't export data for exporters jobs
            job_json = json.loads(job.to_json())
            if (job_json['stage']) not in ["new-relic-exporter", "new-relic-metrics-exporter"]:
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
                job_logger.info("Job: "+ str(job_json['id']) + " - " + "from project: " + str(project_id)+ " - " + str(GLAB_SERVICE_NAME) + " data")
                print("Metrics sent for job: " + str(job_json['id'])+ " for pipeline: "+ str(current_pipeline_json['id'])+ " from project: " + str(project_id)+ " - " + str(GLAB_SERVICE_NAME))
                print("Log events sent for job: " + str(job_json['id']) + " for pipeline: "+ str(current_pipeline_json['id'])+ " from project: " + str(project_id)+ " - " + str(GLAB_SERVICE_NAME))          

    except Exception as e:
        print(project_id,e)           
