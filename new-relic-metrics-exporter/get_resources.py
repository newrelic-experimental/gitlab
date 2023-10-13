import json
from datetime import datetime, timedelta, date
import pytz
import zulu
from opentelemetry.sdk.resources import Resource
from otel import get_logger, create_resource_attributes
from custom_parsers import parse_attributes, parse_metrics_attributes
from otel import get_logger, get_meter, create_resource_attributes
from custom_parsers import parse_attributes
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME
import re
from global_variables import *
import requests
import logging
import concurrent.futures

LoggingInstrumentor().instrument(set_logging_format=True,log_level=logging.INFO)

# Global settings for logger,tracer,meter
global_resource_attributes ={
"instrumentation.name": "gitlab-integration",
"gitlab.source": "gitlab-metrics-exporter",
}
global_resource = Resource(attributes=global_resource_attributes)

#Global logger
global_logger = get_logger(endpoint,headers,global_resource,"global_logger")


#Global meter
global_meter = get_meter(endpoint,headers,global_resource,"global_meter")
gitlab_pipelines_duration=global_meter.create_counter("gitlab_pipelines.duration")
gitlab_pipelines_queued_duration=global_meter.create_counter("gitlab_pipelines.queued_duration")
gitlab_jobs_duration=global_meter.create_counter("gitlab_jobs.duration")
gitlab_jobs_queued_duration=global_meter.create_counter("gitlab_jobs.queued_duration")
                
def get_runners():
    try:
        runners = gl.runners.list() #obtains the list available runners to this user(https://python-gitlab.readthedocs.io/en/stable/gl_objects/runners.html)
        # runners = gl.runners_all.list() #Get a list of all runners in the GitLab instance (specific and shared). Access is restricted to users with administrator access.(https://python-gitlab.readthedocs.io/en/stable/gl_objects/runners.html)
        if len(runners) == 0:
            print("Number of runners found available to this user is",len(runners),"not exporting any runner data")
        else:
            for runner in runners:
                runner_json = json.loads(runner.to_json())
                if str(runner_json ["is_shared"]).lower() == "false":
                    runner_attributes = create_resource_attributes(parse_attributes(runner_json),GLAB_SERVICE_NAME)                
                    runner_attributes.update({"gitlab.resource.type": "runner"})
                    #Send runner data as log events with attributes
                    msg = "Runner: "+ str(runner_json['id'])+ str(GLAB_SERVICE_NAME) 
                    global_logger._log(level=logging.INFO,msg=msg,extra=runner_attributes,args="")
                    print("Log events sent for runner: " + str(runner_json['id'])+ " - " + str(GLAB_SERVICE_NAME))
                    
    except Exception as e:
        print("Unable to obtain runners due to ",str(e))
        
def grab_data(project):
    try:
        #Collect project information
        GLAB_SERVICE_NAME = str((project.attributes.get('name_with_namespace'))).lower().replace(" ", "")
        project_json = json.loads(project.to_json())
        # Check if we should export only data for specific groups/projects
        if paths:
            for path in paths:          
                if str(project_json["namespace"]["full_path"]) == (str(path)):
                    if re.search(str(GLAB_EXPORT_PROJECTS_REGEX), project_json["name"]):
                        try:
                            print("Project: "+str((project.attributes.get('name_with_namespace'))).lower().replace(" ", "") + " matched configuration, collecting data...")
                            get_all_resources(project)
                        except Exception as e:
                            print(str(e) + " -> Failed to collect data for project:  "+str((project.attributes.get('name_with_namespace'))).lower().replace(" ", "")+" check your configuration.")
                        if GLAB_DORA_METRICS:
                            try:
                                get_dora_metrics(project)
                            except Exception as e:
                                print("Unable to obtain DORA metrics ",e)
                        # If we don't need to export all projects each time
                        # if zulu.parse(project_json["last_activity_at"]) >= (datetime.utcnow().replace(tzinfo=pytz.utc) - timedelta(minutes=int(GLAB_EXPORT_LAST_MINUTES))):
                        #Send project information as log events with attributes
                        c_attributes = create_resource_attributes(parse_attributes(project_json), GLAB_SERVICE_NAME)
                        c_attributes.update({"gitlab.resource.type": "project"})
                        msg = "Project: "+ str(project_json['id']) + " - "+ str(GLAB_SERVICE_NAME) 
                        global_logger._log(level=logging.INFO,msg=msg,extra=c_attributes,args="")
                        print("Log events sent for project: " + str(project_json['id']) + " - " + str(GLAB_SERVICE_NAME))              
                    else:
                        print("No project name matched configured regex " + "\"" + str(GLAB_EXPORT_PROJECTS_REGEX)+ "\" in path " + "\""+str(path)+"\"")
        else:
            print("GLAB_EXPORT_PATHS not configured")
            exit(1)  
                 
    except Exception as e:
        print(str(e) + " -> ERROR obtaining data for project:  "+str((project.attributes.get('name_with_namespace'))).lower().replace(" ", ""))

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
        "instrumentation.name": "gitlab-integration",
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
        dora=meter.create_counter("gitlab_dora_"+str(metric))
        if r.status_code == 200 and len(r.text) > 2:
            #Create metrics we want to populate
            res = json.loads(r.text)
            for i in range(len(res)):
                if res[i]['value'] is not None:
                    if metric == "change_failure_rate":
                        dora.add(res[i]['value']*100,attributes={"date":str(res[i]['date'])})
                    else:
                        dora.add(res[i]['value'],attributes={"date":str(res[i]['date'])})
                else:
                    dora.add(0,attributes={"date":str(res[i]['date'])})              
            
def get_all_resources(current_project):
    project_id = json.loads(current_project.to_json())["id"]
    GLAB_SERVICE_NAME = str((current_project.attributes.get('name_with_namespace'))).lower().replace(" ", "")
    with concurrent.futures.ThreadPoolExecutor(max_workers=5) as executor:
        # executor.submit(get_deployments, current_project,project_id,GLAB_SERVICE_NAME)
        # executor.submit(get_environments, current_project,project_id,GLAB_SERVICE_NAME)
        # executor.submit(get_releases, current_project,project_id,GLAB_SERVICE_NAME)
        executor.submit(get_pipelines, current_project,project_id,GLAB_SERVICE_NAME)

def get_deployments(current_project,project_id,GLAB_SERVICE_NAME):
    deployments = current_project.deployments.list(get_all=True, order_by="created_at", sort="desc")
    if len(deployments) > 0: # check if there are deployments in this project
        for deployment in deployments:
            deployment_json = json.loads(deployment.to_json())
            if zulu.parse(deployment_json["created_at"]) >= (datetime.utcnow().replace(tzinfo=pytz.utc) - timedelta(minutes=int(GLAB_EXPORT_LAST_MINUTES))):
                try:
                    deployment = current_project.deployments.get(deployment_json['id'])
                    deployment_attributes = create_resource_attributes(parse_attributes(deployment_json), GLAB_SERVICE_NAME)
                    deployment_attributes.update({"gitlab.resource.type": "deployment"})
                    #Send deployment data as log events with attributes
                    msg = "Deployment: "+ str(deployment_json['id'])+ " from project: " + str(project_id) + " - " + str(GLAB_SERVICE_NAME) 
                    global_logger._log(level=logging.INFO,msg=msg,extra=deployment_attributes,args="")   
                    print("Log events sent for deployment: " + str(deployment_json['id'])+ " from project: " + str(project_id) + " - " + str(GLAB_SERVICE_NAME))
                except Exception as e:
                    print("Failed to obtain deployments for project",project_id," due to error ", e)
            else:
                break

def get_environments (current_project,project_id,GLAB_SERVICE_NAME):
    environments = current_project.environments.list(get_all=True)
    if len(environments) > 0: # check if there are environments in this project
        for environment in environments:        
            environment_json = json.loads(environment.to_json())
            if zulu.parse(environment_json["created_at"]) >= (datetime.utcnow().replace(tzinfo=pytz.utc) - timedelta(minutes=int(GLAB_EXPORT_LAST_MINUTES))):
                try:
                    environment = current_project.environments.get(environment_json['id'])
                    environment_attributes = create_resource_attributes(parse_attributes(environment_json),GLAB_SERVICE_NAME)
                    environment_attributes.update({"gitlab.resource.type": "environment"})
                    #Send environment data as log events with attributes   
                    msg = "Environment: "+ str(environment_json['id'])+ " from project: " + str(project_id) + " - " + str(GLAB_SERVICE_NAME) 
                    global_logger._log(level=logging.INFO,msg=msg,extra=environment_attributes,args="")          
                    print("Log events sent for environment: " + str(environment_json['id'])+ " from project: " + str(project_id) + " - " + str(GLAB_SERVICE_NAME))
    
                except Exception as e:
                    print("Failed to obtain environments for project",project_id," due to error ", e)
        
def get_releases(current_project,project_id,GLAB_SERVICE_NAME):
    releases = current_project.releases.list(get_all=True, order_by="created_at", sort="desc")
    if len(releases) > 0: # check if there are releases in this project
        for release in releases:
            release_json = json.loads(release.to_json())
            if zulu.parse(release_json["created_at"]) >= (datetime.utcnow().replace(tzinfo=pytz.utc) - timedelta(minutes=int(GLAB_EXPORT_LAST_MINUTES))):
                try:
                    release = current_project.releases.get(release_json['tag_name'])
                    release_attributes = create_resource_attributes(parse_attributes(release_json),GLAB_SERVICE_NAME)
                    release_attributes.update({"gitlab.resource.type": "release"})
                    #Send releases data as log events with attributes
                    msg = "Release: "+ str(release_json['tag_name'])+ " from project: " + str(project_id) + " - " + str(GLAB_SERVICE_NAME) 
                    global_logger._log(level=logging.INFO,msg=msg,extra=release_attributes,args="")      
                    print("Log events sent for release: " + str(release_json['tag_name'])+ " from project: " + str(project_id) + " - " + str(GLAB_SERVICE_NAME))
                except Exception as e:
                    print("Failed to obtain releases for project",project_id," due to error ", e)
            else:
                break
            
def get_pipelines(current_project,project_id,GLAB_SERVICE_NAME):
    print("Gathering pipeline data for project " + str(project_id) + " this may take while...")
    pipelines = current_project.pipelines.list(get_all=True, updated_after=str((datetime.utcnow().replace(tzinfo=pytz.utc) - timedelta(minutes=int(GLAB_EXPORT_LAST_MINUTES)))))
    print("Found",len(pipelines),"pipelines")
    if len(pipelines)> 0: # check if there are pipelines in this project
        try:
            for pipeline in pipelines:
                pipeline_json = json.loads(pipeline.to_json())
                pipeline_id = pipeline_json['id']
                current_pipeline = current_project.pipelines.get(pipeline_id)
                current_pipeline_json = json.loads(current_pipeline.to_json())
                attributes_pip = {"gitlab.resource.type": "pipeline"}
                # # Grab pipeline attributes
                current_pipeline_attributes = create_resource_attributes(parse_attributes(current_pipeline_json),GLAB_SERVICE_NAME)      
                # Check wich dimension to set on each metric
                currrent_pipeline_metrics_attributes = parse_metrics_attributes(current_pipeline_attributes)
                currrent_pipeline_metrics_attributes[2].update(attributes_pip)
                # Update attributes for the log events
                current_pipeline_attributes.update(attributes_pip)
                # Send pipeline metrics with configured dimensions
                gitlab_pipelines_duration.add(currrent_pipeline_metrics_attributes[0],currrent_pipeline_metrics_attributes[2])
                gitlab_pipelines_queued_duration.add(currrent_pipeline_metrics_attributes[1],currrent_pipeline_metrics_attributes[2])
                # Send pipeline data as log events with attributes
                msg = "Pipeline: "+ str(pipeline_id)+ " - " + "from project: " + str(project_id)+ " - " + str(GLAB_SERVICE_NAME) 
                global_logger._log(level=logging.INFO,msg=msg,extra=current_pipeline_attributes,args="")   
                print("Metrics sent for pipeline: " + str(pipeline_id)+ " - " + "from project: " + str(project_id)+ " - " + str(GLAB_SERVICE_NAME))
                print("Log events sent for pipeline: " + str(pipeline_id)+ " - " + "from project: " + str(project_id)+ " - " + str(GLAB_SERVICE_NAME))
                #Collect job information
                get_jobs(current_pipeline,project_id,GLAB_SERVICE_NAME)
        except Exception as e:
            print("Failed to obtain pipelines for project",project_id," due to error ", e)

        
def get_jobs(current_pipeline,project_id,GLAB_SERVICE_NAME):
    try:
        jobs = current_pipeline.jobs.list(get_all=True)
        current_pipeline_json = json.loads(current_pipeline.to_json())
        #Collect job information
        for job in jobs:
            #Ensure we don't export data for exporters jobs
            job_json = json.loads(job.to_json())
            if (job_json['stage']) not in ["new-relic-exporter", "new-relic-metrics-exporter"]:
                #Grab job attributes
                current_job_attributes = create_resource_attributes(parse_attributes(job_json),GLAB_SERVICE_NAME)
                attributes_j = {"gitlab.resource.type": "job"}
                #Check wich dimension to set on each metric
                job_metrics_attributes = parse_metrics_attributes(current_job_attributes)
                job_metrics_attributes[2].update(attributes_j)
                # Update attributes for the log events
                current_job_attributes.update(attributes_j)
                #Send job metrics with configured dimensions
                gitlab_jobs_duration.add(job_metrics_attributes[0],job_metrics_attributes[2])
                gitlab_jobs_queued_duration.add(job_metrics_attributes[1],job_metrics_attributes[2])
                #Send job data as log events with attributes
                msg = "Job: "+ str(job_json['id']) + " - " + "from project: " + str(project_id)+ " - " + str(GLAB_SERVICE_NAME) 
                global_logger._log(level=logging.INFO,msg=msg,extra=current_job_attributes,args="")   
                print("Metrics sent for job: " + str(job_json['id'])+ " for pipeline: "+ str(current_pipeline_json['id'])+ " from project: " + str(project_id)+ " - " + str(GLAB_SERVICE_NAME))
                print("Log events sent for job: " + str(job_json['id']) + " for pipeline: "+ str(current_pipeline_json['id'])+ " from project: " + str(project_id)+ " - " + str(GLAB_SERVICE_NAME))          

    except Exception as e:
        print("Failed to obtain jobs for project",project_id," due to error ", e)
