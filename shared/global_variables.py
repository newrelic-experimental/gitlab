import os
from shared.custom_parsers import check_env_vars
import gitlab
from queue import Queue

# Ensure that mandatory variables are configured before starting
check_env_vars()

# global variables
global GLAB_STANDALONE
global GLAB_EXPORT_LAST_MINUTES
global GLAB_PROJECT_OWNERSHIP
global GLAB_PROJECT_VISIBILITIES
global GLAB_SERVICE_NAME
global NEW_RELIC_API_KEY
global GLAB_TOKEN
global GLAB_EXPORT_PROJECTS_REGEX
global GLAB_EXPORT_PATHS
global GLAB_ENDPOINT
global gl
global OTEL_EXPORTER_OTEL_ENDPOINT
global endpoint
global headers
global paths
global GLAB_EXPORT_LOGS
global GLAB_DORA_METRICS
global q
global GLAB_RUNNERS_INSTANCE

# Initializing a queue
q = Queue()

GLAB_DORA_METRICS = False
GLAB_EXPORT_LOGS = True
GLAB_STANDALONE = False
GLAB_EXPORT_LAST_MINUTES = 61
GLAB_PROJECT_OWNERSHIP = True
GLAB_PROJECT_VISIBILITIES = [
    "private",
]
GLAB_SERVICE_NAME = (
    "gitlab-exporter"  # default -> updates dynamically with each project name
)
NEW_RELIC_API_KEY = os.getenv("NEW_RELIC_API_KEY")
GLAB_TOKEN = os.getenv("GLAB_TOKEN")
GLAB_EXPORT_PROJECTS_REGEX = ".*"
GLAB_EXPORT_PATHS = ""
GLAB_EXPORT_PATHS_ALL = False
GLAB_RUNNERS_SCOPE = [
    "all",
]
GLAB_RUNNERS_INSTANCE = True

# Check runners permissions to obtain all runners in instance
if (
    "GLAB_RUNNERS_INSTANCE" in os.environ
    and os.getenv("GLAB_RUNNERS_INSTANCE").lower() == "false"
):
    GLAB_RUNNERS_INSTANCE = False
else:
    GLAB_RUNNERS_INSTANCE = True


# Check export logs is set
if (
    "GLAB_DORA_METRICS" in os.environ
    and os.getenv("GLAB_DORA_METRICS").lower() == "true"
):
    GLAB_DORA_METRICS = os.getenv("GLAB_DORA_METRICS")
else:
    GLAB_DORA_METRICS = False

# Check export logs is set
if (
    "GLAB_EXPORT_LOGS" in os.environ
    and os.getenv("GLAB_EXPORT_LOGS").lower() == "false"
):
    GLAB_EXPORT_LOGS = False
else:
    GLAB_EXPORT_LOGS = True

# Check if project name regex is set
if "GLAB_EXPORT_PROJECTS_REGEX" in os.environ:
    GLAB_EXPORT_PROJECTS_REGEX = os.getenv("GLAB_EXPORT_PROJECTS_REGEX")

if (
    "GLAB_EXPORT_PATHS_ALL" in os.environ
    and os.getenv("GLAB_EXPORT_PATHS_ALL").lower() == "true"
):
    GLAB_EXPORT_PATHS_ALL = True

# Check base path
if "GLAB_EXPORT_PATHS" in os.environ:
    GLAB_EXPORT_PATHS = os.getenv("GLAB_EXPORT_PATHS")
else:
    if "CI_PROJECT_NAMESPACE" in os.environ:
        GLAB_EXPORT_PATHS = os.getenv("CI_PROJECT_NAMESPACE")

if GLAB_EXPORT_PATHS != "":
    paths = GLAB_EXPORT_PATHS.split(",")
else:
    paths = ""

# Set gitlab client
GLAB_ENDPOINT = ""
if "GLAB_ENDPOINT" in os.environ:
    GLAB_ENDPOINT = os.getenv("GLAB_ENDPOINT")
    gl = gitlab.Gitlab(url=str(GLAB_ENDPOINT), private_token="{}".format(GLAB_TOKEN))
else:
    GLAB_ENDPOINT = "https://gitlab.com/"
    gl = gitlab.Gitlab(private_token="{}".format(GLAB_TOKEN))

# Check project ownership and visibility
if (
    "GLAB_PROJECT_OWNERSHIP" in os.environ
    and os.getenv("GLAB_PROJECT_OWNERSHIP").lower() == "false"
):
    GLAB_PROJECT_OWNERSHIP = False


if "GLAB_PROJECT_VISIBILITIES" in os.environ:
    GLAB_PROJECT_VISIBILITIES = os.getenv("GLAB_PROJECT_VISIBILITIES").split(",")

# Check if we running as pipeline schedule or standalone mode
if "GLAB_STANDALONE" in os.environ and os.getenv("GLAB_STANDALONE").lower() == "true":
    GLAB_STANDALONE = True


# Check if we using default amount data to export
if "GLAB_EXPORT_LAST_MINUTES" in os.environ:
    GLAB_EXPORT_LAST_MINUTES = int(os.getenv("GLAB_EXPORT_LAST_MINUTES")) + 1

# Check which datacentre we exporting our data to
if "OTEL_EXPORTER_OTEL_ENDPOINT" in os.environ:
    OTEL_EXPORTER_OTEL_ENDPOINT = os.getenv("OTEL_EXPORTER_OTEL_ENDPOINT")
else:
    if NEW_RELIC_API_KEY.startswith("eu"):
        OTEL_EXPORTER_OTEL_ENDPOINT = "https://otlp.eu01.nr-data.net:4318"
    else:
        OTEL_EXPORTER_OTEL_ENDPOINT = "https://otlp.nr-data.net:4318"

# Check runners scope
if "GLAB_RUNNERS_SCOPE" in os.environ:
    # Split comma separated values into a list
    GLAB_RUNNERS_SCOPE = os.getenv("GLAB_RUNNERS_SCOPE").split(",")


# Set variables to use for OTEL metrics and logs exporters
endpoint = "{}".format(OTEL_EXPORTER_OTEL_ENDPOINT)
headers = "api-key={}".format(NEW_RELIC_API_KEY)
