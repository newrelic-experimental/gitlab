import os
from custom_parsers import check_env_vars
import gitlab

#Ensure that mandatory variables are configured before starting
check_env_vars(metrics=True)
       
def init():      
    # global variables 
    global GLAB_STANDALONE
    global GLAB_EXPORT_LAST_MINUTES
    global GLAB_EXPORT_NON_GROUP_PROJECTS
    global GLAB_PROJECT_OWNERSHIP
    global GLAB_PROJECT_VISIBILITY
    global GLAB_SERVICE_NAME
    global NEW_RELIC_API_KEY
    global GLAB_TOKEN
    global GLAB_EXPORT_PROJECTS_REGEX
    global GLAB_EXPORT_GROUPS_REGEX
    global GLAB_ENDPOINT
    global gl
    global OTEL_EXPORTER_OTEL_ENDPOINT
    global endpoint
    global headers
    
    GLAB_STANDALONE=False
    GLAB_EXPORT_LAST_MINUTES=61
    GLAB_EXPORT_NON_GROUP_PROJECTS = False
    GLAB_PROJECT_OWNERSHIP=True
    GLAB_PROJECT_VISIBILITY="private"
    GLAB_SERVICE_NAME="gitlab-exporter" # default -> updates dynamically with each project name 
    NEW_RELIC_API_KEY = os.getenv('NEW_RELIC_API_KEY')
    GLAB_TOKEN = os.getenv('GLAB_TOKEN')
    GLAB_EXPORT_PROJECTS_REGEX = os.getenv('GLAB_EXPORT_PROJECTS_REGEX')
    GLAB_EXPORT_GROUPS_REGEX = os.getenv('GLAB_EXPORT_GROUPS_REGEX')

   
    # Set gitlab client
    GLAB_ENDPOINT = ""
    if "GLAB_ENDPOINT" in os.environ:
        GLAB_ENDPOINT = os.getenv('GLAB_ENDPOINT')
        gl = gitlab.Gitlab(url=str(GLAB_ENDPOINT),private_token="{}".format(GLAB_TOKEN))
    else:
        gl = gitlab.Gitlab(private_token="{}".format(GLAB_TOKEN))

    # Check project ownership and visibility
    if "GLAB_PROJECT_OWNERSHIP" in os.environ:
        GLAB_PROJECT_OWNERSHIP = os.getenv('GLAB_PROJECT_OWNERSHIP')
        
    if "GLAB_PROJECT_VISIBILITY" in os.environ:
        GLAB_PROJECT_VISIBILITY = os.getenv('GLAB_PROJECT_VISIBILITY')
        
    # Check if we running as pipeline schedule or standalone mode
    if "GLAB_STANDALONE" in os.environ:
        GLAB_STANDALONE = os.getenv('GLAB_STANDALONE')

    # Check if we using default amount data to export
    if "GLAB_EXPORT_LAST_MINUTES" in os.environ:
        GLAB_EXPORT_LAST_MINUTES = int(os.getenv('GLAB_EXPORT_LAST_MINUTES'))+1

    # Check if we should export non group projects
    if "GLAB_EXPORT_NON_GROUP_PROJECTS" in os.environ:
        GLAB_EXPORT_NON_GROUP_PROJECTS = os.getenv('GLAB_EXPORT_NON_GROUP_PROJECTS')
        if GLAB_EXPORT_NON_GROUP_PROJECTS.lower() == "true":
            GLAB_EXPORT_NON_GROUP_PROJECTS = True

    #Check which datacentre we exporting our data to
    if "OTEL_EXPORTER_OTEL_ENDPOINT" in os.environ:
        OTEL_EXPORTER_OTEL_ENDPOINT = os.getenv('OTEL_EXPORTER_OTEL_ENDPOINT')
    else: 
        if NEW_RELIC_API_KEY.startswith("eu"):
            OTEL_EXPORTER_OTEL_ENDPOINT = "https://otlp.eu01.nr-data.net:4318"
        else:
            OTEL_EXPORTER_OTEL_ENDPOINT = "https://otlp.nr-data.net:4318"
            
    #Set variables to use for OTEL metrics and logs exporters
    endpoint="{}".format(OTEL_EXPORTER_OTEL_ENDPOINT)
    headers="api-key={}".format(NEW_RELIC_API_KEY)
