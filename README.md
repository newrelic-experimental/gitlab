[![New Relic Experimental header](https://github.com/newrelic/opensource-website/raw/master/src/images/categories/Experimental.png)](https://opensource.newrelic.com/oss-category/#new-relic-experimental)

# New Relic Gitlab Exporters
>Monitor Gitlab with OpenTelemetry and New Relic quickstarts

![GitHub forks](https://img.shields.io/github/forks/newrelic-experimental/tls-proxy?style=social)
![GitHub stars](https://img.shields.io/github/stars/newrelic-experimental/tls-proxy?style=social)
![GitHub watchers](https://img.shields.io/github/watchers/newrelic-experimental/tls-proxy?style=social)

![GitHub last commit](https://img.shields.io/github/last-commit/newrelic-experimental/tls-proxy)
![GitHub issues](https://img.shields.io/github/issues/newrelic-experimental/tls-proxy)
![GitHub pull requests](https://img.shields.io/github/issues-pr/newrelic-experimental/tls-proxy)

## How to monitor Gitlab with New Relic

Now, you can monitor your Gitlab data with New Relic using New Relic Exporter and Metrics Exporter, making it easier to get observability into your CI/CD pipeline health and performance.

Using these exporters you will be able to:

- Visualise key metrics on your Gitlab pipelines, such as how long your jobs are taking, how often they are failing
- Visualise jobs and pipeline executions as distributed traces with logs in context
- Pinpoint where issues are coming from in your pipelines.
- Create alerts on your Gitlab pipelines.

The next image shows a New Relic dashboard with some of the Gitlab metrics you'll be able to visualise.

## Gitlab Dashboard

![Gitlab Dashboard](screenshots/gitlab_dashboard.jpg)

## Configuration System

This project uses a centralized configuration management system with type safety and validation. Configuration is loaded from environment variables and provides backward compatibility with the previous global variables approach.

### Key Features

- **Type-safe configuration** with dataclasses and validation
- **Automatic New Relic region detection** (US/EU) based on API key
- **Environment variable validation** with clear error messages
- **Health monitoring** and configuration validation
- **Backward compatibility** with deprecation warnings for migration

### Configuration Usage

```python
from shared.config.settings import get_config

# Get the singleton configuration instance
config = get_config()

# Access configuration values
gitlab_token = config.token
new_relic_key = config.new_relic_api_key
otel_endpoint = config.otel_endpoint
```

For detailed configuration documentation, see [CONFIGURATION_SYSTEM.md](examples/CONFIGURATION_SYSTEM.md).

# New Relic Exporter

All tests should pass. There are no dummy tests included; all tests validate real functionality.

| Variables | Description | Optional | Values | Default |
| ---       |         --- |       ---| ---    |   ----   |
| `OTEL_EXPORTER_OTEL_ENDPOINT` | New Relic OTEL endpoint including port | True | String | Auto-detected: "https://otlp.nr-data.net:4318" (US) or "https://otlp.eu01.nr-data.net:4318" (EU) |
| `GLAB_TOKEN` | MASKED - Token to access gitlab API | False | String | None |
| `NEW_RELIC_API_KEY` | MASKED - New Relic License Key | False | String | None |
| `GLAB_EXPORT_LOGS` | Export job logs to New Relic | True | Boolean | True |
| `GLAB_ENDPOINT` | Gitlab API endpoint | True | String | "https://gitlab.com" |
| `GLAB_LOW_DATA_MODE` | export only bear minimum data (only recommended during testing) | True | Boolean | False |
| `GLAB_CONVERT_TO_TIMESTAMP` | converts datetime to timestamp | True | Boolean | False |
| `GLAB_EXCLUDE_JOBS` | Comma-separated list of job or bridge names or stages to exclude from export (e.g. "build,test,deploy,bridge-stage") | True | List* | None |
| `Pipeline Bridges Support` | Bridges in pipelines are now exported as spans/logs and can be excluded using `GLAB_EXCLUDE_JOBS` | True | Boolean | True |

# New Relic Metrics Exporter 

| Variables | Description | Optional | Values | Default |
| ---       |         --- |       ---| ---    |   ----   |
| `OTEL_EXPORTER_OTEL_ENDPOINT` | New Relic OTEL endpoint including port | True | String | Auto-detected: "https://otlp.nr-data.net:4318" (US) or "https://otlp.eu01.nr-data.net:4318" (EU) |
| `GLAB_ENDPOINT` | Gitlab API endpoint | True | String | "https://gitlab.com" |
| `GLAB_TOKEN` | MASKED - Token to access gitlab API | False | String | None |
| `NEW_RELIC_API_KEY` | MASKED - New Relic License Key | False | String | None |
| `GLAB_PROJECT_OWNERSHIP` | Project ownership | False | String | True |
| `GLAB_PROJECT_VISIBILITIES` | Project visibilities (public,private,internal) | False | List* | private |
| `GLAB_DORA_METRICS` | Export DORA metrics, requires Gitlab ULTIMATE | True | Bool | False |
| `GLAB_EXPORT_PATHS` | Project paths aka namespace full_path to obtain data from | False | List* | None if running as standalone or CI_PROJECT_ROOT_NAMESPACE if running as pipeline schedule|
| `GLAB_RUNNERS_INSTANCE` | Obtain runners from gitlab instance instead of project only  | True | String | |
| `GLAB_EXPORT_PROJECTS_REGEX` | Regex to match project names against ".*" for all | False | Boolean | None |
| `GLAB_EXPORT_PATHS_ALL` | When True ignore GLAB_EXPORT_PATHS variable and export projects matching GLAB_EXPORT_PROJECTS_REGEX in any groups or subgroups| True |  Boolean | False |
| `GLAB_CONVERT_TO_TIMESTAMP` | converts datetime to timestamp | True | Boolean | False |
| `GLAB_EXPORT_LAST_MINUTES` | The amount past minutes to export data from | True | Integer | 60 |
| `GLAB_ATTRIBUTES_DROP` | Attributes to drop from logs and spans events | True | List* | None |
| `GLAB_DIMENSION_METRICS` | Extra dimensional metric attributes to add to each metric | True | List* | NONE Note the following attributes will always be set as dimensions regardless of this setting: status,stage,name |
| `GLAB_RUNNERS_SCOPE` | Get runners scope : all, active, paused, online, shared, specific (separated by comma) | True | List* | all |
| `GLAB_STANDALONE` | Set to True if not running as gitlab pipeline schedule | True | Boolean | False |
| `GLAB_ENVS_DROP` | Extra system environment variables to drop from span attributes | True | List* | Note the following environment variables will always be dropped regardless of this setting: NEW_RELIC_API_KEY,GITLAB_FEATURES,CI_SERVER_TLS_CA_FILE,CI_RUNNER_TAGS,CI_JOB_JWT,CI_JOB_JWT_V1,CI_JOB_JWT_V2,GLAB_TOKEN,GIT_ASKPASS,CI_COMMIT_BEFORE_SHA,CI_BUILD_TOKEN,CI_DEPENDENCY_PROXY_PASSWORD,CI_RUNNER_SHORT_TOKEN,CI_BUILD_BEFORE_SHA,CI_BEFORE_SHA,OTEL_EXPORTER_OTEL_ENDPOINT,GLAB_DIMENSION_METRICS |
| `GLAB_EXCLUDE_JOBS` | Comma-separated list of job or bridge names or stages to exclude from export (e.g. "build,test,deploy,bridge-stage") | True | List* | None |
| `Pipeline Bridges Support` | Bridges in pipelines are now exported as metrics/logs and can be excluded using `GLAB_EXCLUDE_JOBS` | True | Boolean | True |
*comma separated

**Default configuration is based on using Gitlab runners with docker executor**

If using Kubernetes executors instead, use the below configuration

```
image:
    name: docker.io/dpacheconr/gitlab-exporter:1.0.19
    entrypoint: [""]
  script:
    - python3 -u /app/main.py
    - echo "Done"
```

## Development Setup

### Requirements

The project uses pinned dependencies for reproducible builds:

- **Production dependencies**: `shared/requirements.txt`
- **Development dependencies**: `requirements-dev.txt`

Install dependencies:

```bash
# Production dependencies
pip install -r shared/requirements.txt

# Development dependencies (for testing and code quality)
pip install -r requirements-dev.txt
```

### Running Tests

The project includes comprehensive test coverage with 76 tests covering:

- Configuration management and validation
- GitLab API integration
- New Relic integration
- Data transformation
- Performance testing
- Error handling

Run all tests:

```bash
python3 -m pytest tests/ -v
```

Run specific test modules:

```bash
# Configuration tests
python3 -m pytest tests/test_config.py -v

# Main module tests
python3 -m pytest tests/test_main.py -v

# Integration tests
python3 -m pytest tests/test_gitlab_integration.py -v
```

Run tests with coverage:

```bash
python3 -m pytest tests/ --cov=shared --cov=new_relic_exporter --cov=new_relic_metrics_exporter --cov-report=html
```

### Code Quality

The project includes code quality tools:

```bash
# Code formatting
black .

# Linting
flake8 .

# Type checking
mypy .

# Security scanning
bandit -r .
```

## New Relic Quickstart
> https://newrelic.com/instant-observability/gitlab

## How to 

> https://newrelic.com/blog/how-to-relic/monitor-gitlab-with-opentelemetry

Alternative to running new relic metrics exporter as pipeline schedule:
Rather than running in a GitLab pipeline the New Relic Metrics exporter can also  be run independently enabling standalone mode. To run in Docker for instance run the following:
 
docker run -e GLAB_STANDALONE=True -e GLAB_EXPORT_PATHS="dpacheconr" -e GLAB_EXPORT_PROJECTS_REGEX=".*" -e GLAB_TOKEN=glpat.... -e NEW_RELIC_API_KEY=....NRAL docker.io/dpacheconr/gitlab-metrics-exporter:2.0.0

## Recent Improvements

### OpenTelemetry Attribute Filtering (Latest)
- **Fixed critical OpenTelemetry warnings**: Eliminated "Invalid type NoneType for attribute" errors
- **Comprehensive filtering across all processors**: Applied to job, pipeline, and bridge processors
- **Robust None value handling**: Filters None values and empty strings before sending to OpenTelemetry
- **Extensive test coverage**: Added 13 comprehensive tests covering all filtering scenarios
- **Production stability**: Prevents exporter crashes in live GitLab environments

### Configuration System Overhaul
- Implemented centralized, type-safe configuration management
- Added automatic New Relic region detection
- Comprehensive validation and health monitoring
- Backward compatibility with deprecation warnings

### Dependencies Management
- Fixed duplicate dependencies in requirements.txt
- Added proper version pinning for reproducible builds
- Separated development dependencies
- Improved dependency categorization

### Testing Infrastructure
- Comprehensive test suite with 64+ tests
- Configuration validation testing
- Integration and performance testing
- OpenTelemetry attribute filtering tests
- 100% test pass rate

For detailed information about recent improvements, see:
- [CONFIGURATION_SYSTEM.md](examples/CONFIGURATION_SYSTEM.md)
- [REQUIREMENTS_FIXES.md](examples/REQUIREMENTS_FIXES.md)
- [IMPROVEMENT_PLAN.md](examples/IMPROVEMENT_PLAN.md)

## Contributing

We encourage your contributions to improve [Gitlab Exporters](../../)! Keep in mind when you submit your pull request, you'll need to sign the CLA via the click-through using CLA-Assistant. You only have to sign the CLA one time per project. If you have any questions, or to execute our corporate CLA, required if your contribution is on behalf of a company, please drop us an email at opensource@newrelic.com.

**A note about vulnerabilities**

As noted in our [security policy](../../security/policy), New Relic is committed to the privacy and security of our customers and their data. We believe that providing coordinated disclosure by security researchers and engaging with the security community are important means to achieve our security goals.

If you believe you have found a security vulnerability in this project or any of New Relic's products or websites, we welcome and greatly appreciate you reporting it to New Relic through [HackerOne](https://hackerone.com/newrelic).

## License

Gitlab Exporters are licensed under the [Apache 2.0](http://apache.org/licenses/LICENSE-2.0.txt) License.

>Gitlab Exporters also use source code from third-party libraries. You can find full details on which libraries are used and the terms under which they are licensed in the third-party notices document.
