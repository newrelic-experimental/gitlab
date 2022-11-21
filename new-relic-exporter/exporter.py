import json
import logging
import os
from os.path import exists
from parser import (check_env_vars, do_parse, do_string, do_time,
                    grab_span_att_vars, parse_attributes)

import gitlab
from opentelemetry import trace
from opentelemetry.instrumentation.logging import LoggingInstrumentor
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.trace import Status, StatusCode
from otel import create_resource_attributes, get_logger, get_tracer

GLAB_SERVICE_NAME = ""

def send_to_nr():
    check_env_vars()
    NEW_RELIC_API_KEY = os.getenv('NEW_RELIC_API_KEY')
    if "OTEL_EXPORTER_OTEL_ENDPOINT" in os.environ:
        OTEL_EXPORTER_OTEL_ENDPOINT = os.getenv('OTEL_EXPORTER_OTEL_ENDPOINT')
    else: 
        if NEW_RELIC_API_KEY.startswith("eu"):
            OTEL_EXPORTER_OTEL_ENDPOINT = "https://otlp.eu01.nr-data.net:4318"
        else:
            OTEL_EXPORTER_OTEL_ENDPOINT = "https://otlp.nr-data.net:4318"
        
    if "GLAB_EXPORT_LOGS" in os.environ:
        GLAB_EXPORT_LOGS = os.getenv('GLAB_EXPORT_LOGS')
    else:
        GLAB_EXPORT_LOGS=True

    GLAB_TOKEN = os.getenv('GLAB_TOKEN')
    
    # Set gitlab client
    gl = gitlab.Gitlab(private_token="{}".format(GLAB_TOKEN))

    # Set gitlab project/pipeline/jobs details
    project_id = os.getenv('CI_PROJECT_ID')
    project = gl.projects.get(project_id)
    pipeline_id = os.getenv('CI_PARENT_PIPELINE')
    pipeline = project.pipelines.get(pipeline_id)
    project_full_name = str((project.attributes.get('name_with_namespace'))).lower().replace(" ", "")
    jobs = pipeline.jobs.list()
    job_lst=[]
    for job in jobs:
        job_json = json.loads(job.to_json())
        if (job_json['name']) not in ["new-relic-exporter", "new-relic-metrics-exporter"]:
            job_lst.append(job_json)

    global GLAB_SERVICE_NAME
    
    if "GLAB_SERVICE_NAME" in os.environ:
        GLAB_SERVICE_NAME = os.getenv('GLAB_SERVICE_NAME')
    else:
        GLAB_SERVICE_NAME=project_full_name

    #Set variables to use for OTEL metrics and logs exporters
    global_resource = Resource(attributes={
    SERVICE_NAME: GLAB_SERVICE_NAME,
    "pipeline_id": str(os.getenv('CI_PARENT_PIPELINE')),
    "project_id": str(os.getenv('CI_PROJECT_ID')),
    })
    endpoint="{}".format(OTEL_EXPORTER_OTEL_ENDPOINT)
    headers="api-key={}".format(NEW_RELIC_API_KEY)
    LoggingInstrumentor().instrument(set_logging_format=True)
    logging.basicConfig(filename="exporter.log")

    #Create global tracer to export traces to NR
    tracer = get_tracer(endpoint, headers, global_resource, "tracer")
    
    #Configure env variables as span attributes
    atts = grab_span_att_vars()
    
    #Configure spans
    pipeline_att = json.loads(pipeline.to_json())
    # Create a new root span(use start_span to manually end span with timestamp)
    p_parent = tracer.start_span(name=GLAB_SERVICE_NAME + " - pipeline: "+os.getenv('CI_PARENT_PIPELINE'), attributes=atts, start_time=do_time(str(pipeline_att['started_at'])))
    try:
        for item in pipeline_att:
            if item in ("user","detailed_status"):
                for i in pipeline_att[item]:
                    p_parent.set_attribute(do_string(item)+"."+str(i),str(pipeline_att[item][i]))
            else:
                p_parent.set_attribute(do_string(item),str(pipeline_att[item]))

        if pipeline_att['status'] == "failed":
            p_parent.set_status(Status(StatusCode.ERROR,"Pipeline failed, check jobs for more details")) 

        #Set the current span in context(parent)
        pcontext = trace.set_span_in_context(p_parent)
        for job in job_lst:
            #Set job level tracer and logger
            job_attributes = parse_attributes(job)
            resource_attributes ={SERVICE_NAME: GLAB_SERVICE_NAME,"pipeline_id": str(os.getenv('CI_PARENT_PIPELINE')),"project_id": str(os.getenv('CI_PROJECT_ID')),"job_id": str(job["id"])}
            resource_attributes.update(create_resource_attributes(job_attributes,GLAB_SERVICE_NAME ))
            resource_log = Resource(attributes=resource_attributes)
            job_tracer = get_tracer(endpoint, headers, resource_log, "job_tracer")
            try:
                if (job['status']) == "skipped":
                    # Create a new child span for every valid job, set it as the current span in context
                    child = job_tracer.start_span(name="Stage: " + str(job['name'])+" - job_id: "+ str(job['id']) + "- SKIPPED",context=pcontext)
                    child.end()
                else:
                    # Create a new child span for every valid job, set it as the current span in context
                    child = job_tracer.start_span(name="Stage: " + str(job['name'])+" - job_id: "+ str(job['id']), start_time=do_time(job['started_at']),context=pcontext)
                    with trace.use_span(child, end_on_exit=False):
                        try:
                            if job['status'] == "failed":
                                current_job = project.jobs.get(job['id'], lazy=True)
                                with open("job.log", "wb") as f:
                                    current_job.trace(streamed=True, action=f.write)

                                with open("job.log", "rb") as f:
                                    log_data = ""
                                    for string in f:
                                        log_data+=str(string.decode('utf-8', 'ignore'))
                                
                                match = log_data.split("ERROR: Job failed: ")
                                if do_parse(match):
                                    child.set_status(Status(StatusCode.ERROR,str(match[1])))
                                else:
                                    child.set_status(Status(StatusCode.ERROR,str(job['failure_reason'])))
                            child.set_attributes(parse_attributes(job))

                            if GLAB_EXPORT_LOGS:
                                try:
                                    if job['status'] == "failed":
                                        pass
                                    else:
                                        with open("job.log", "wb") as f:
                                            current_job = project.jobs.get(job['id'], lazy=True)
                                            current_job.trace(streamed=True, action=f.write)
                                    with open("job.log", "rb") as f:  
                                        err = False
                                        for string in f:
                                            if string.decode('utf-8').__contains__('ERROR'):
                                                err = True
                                                
                                    with open("job.log", "rb") as f:
                                        resource_attributes_base ={SERVICE_NAME: GLAB_SERVICE_NAME,"pipeline_id": str(os.getenv('CI_PARENT_PIPELINE')),"project_id": str(os.getenv('CI_PROJECT_ID')),"job_id": str(job["id"])}
                                        if err:
                                            count = 1
                                            for string in f:
                                                if string.decode('utf-8') != "\n":
                                                    if count == 1:
                                                        resource_attributes["message"] = string.decode('utf-8')
                                                        resource_log = Resource(attributes=resource_attributes)
                                                        job_logger = get_logger(endpoint,headers,resource_log, "job_logger")
                                                        job_logger.error("")
                                                    else:
                                                        resource_attributes_base["message"] = string.decode('utf-8')
                                                        resource_log = Resource(attributes=resource_attributes_base)
                                                        job_logger = get_logger(endpoint,headers,resource_log, "job_logger")
                                                        job_logger.error("")
                                                    count += 1
                                        else: 
                                            count = 1
                                            for string in f:
                                                if count == 1:
                                                    if string.decode('utf-8') != "\n":
                                                        resource_attributes["message"] = string.decode('utf-8')
                                                        resource_log = Resource(attributes=resource_attributes)
                                                        job_logger = get_logger(endpoint,headers,resource_log, "job_logger")
                                                        job_logger.info("")
                                                else:
                                                    if string.decode('utf-8') != "\n":
                                                        resource_attributes_base["message"] = string.decode('utf-8')
                                                        resource_log = Resource(attributes=resource_attributes_base)
                                                        job_logger = get_logger(endpoint,headers,resource_log, "job_logger")
                                                        job_logger.info("")
                                                count += 1

                                    # n = 3500
                                    # chunks = [log_data[i:i+n] for i in range(0, len(log_data), n)]
                                except Exception as e:
                                    print(e)
                            else:
                                print("Not configured to send logs New Relic, skipping")    

                        finally:
                            child.end(end_time=do_time(job['finished_at']))

            except Exception as e:
                print(e)      

        
        print("All data sent to New Relic for pipeline: " + str(pipeline_att['id']))
        print("Terminating...")

    finally:
        p_parent.end(end_time=do_time(str(pipeline_att['finished_at'])))

send_to_nr()