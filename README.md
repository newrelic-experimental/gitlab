[![New Relic Experimental header](https://github.com/newrelic/opensource-website/raw/master/src/images/categories/Experimental.png)](https://opensource.newrelic.com/oss-category/#new-relic-experimental)

# New Relic GitLab Exporters
>Monitor GitLab with OpenTelemetry and New Relic quickstarts

![GitHub forks](https://img.shields.io/github/forks/newrelic-experimental/gitlab?style=social)
![GitHub stars](https://img.shields.io/github/stars/newrelic-experimental/gitlab?style=social)
![GitHub watchers](https://img.shields.io/github/watchers/newrelic-experimental/gitlab?style=social)

![GitHub last commit](https://img.shields.io/github/last-commit/newrelic-experimental/gitlab)
![GitHub issues](https://img.shields.io/github/issues/newrelic-experimental/gitlab)
![GitHub pull requests](https://img.shields.io/github/issues-pr/newrelic-experimental/gitlab)

## Overview

Monitor your GitLab CI/CD pipelines with comprehensive observability using New Relic's GitLab exporters. This project provides two complementary exporters that collect different types of data from your GitLab instance and send it to New Relic using OpenTelemetry.

### What You Can Monitor

- **Pipeline Performance**: Track pipeline duration, success rates, and failure patterns
- **Job-Level Insights**: Monitor individual job execution times and resource usage
- **Distributed Tracing**: Visualize complete pipeline executions as distributed traces with logs in context
- **DORA Metrics**: Track deployment frequency, lead time, and failure recovery (GitLab Ultimate required)
- **Runner Metrics**: Monitor GitLab runner performance and availability
- **Bridge Processing**: Full support for downstream pipeline triggers and multi-project pipelines

### GitLab Dashboard

![GitLab Dashboard](screenshots/gitlab_dashboard.jpg)

## Architecture

This project consists of two main components:

### 1. New Relic Exporter
- **Purpose**: Exports individual pipeline execution data as distributed traces
- **Data Type**: Traces and logs for specific pipeline runs
- **Use Case**: Detailed analysis of individual pipeline executions
- **Deployment**: Typically runs as part of GitLab CI/CD pipelines

### 2. New Relic Metrics Exporter  
- **Purpose**: Exports aggregated metrics and historical data
- **Data Type**: Metrics, project statistics, and runner information
- **Use Case**: High-level monitoring and alerting across multiple projects
- **Deployment**: Can run standalone or as scheduled GitLab pipeline

## Configuration System

This project uses a centralized configuration management system with type safety and validation. Configuration is loaded from environment variables and provides backward compatibility with the previous global variables approach.

### Key Features

- **Type-safe configuration** with dataclasses and validation
- **Automatic New Relic region detection** (US/EU) based on API key
- **Environment variable validation** with clear error messages
- **Health monitoring** and configuration validation
- **Backward compatibility** with deprecation warnings for migration

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
| `GLAB_USE_NAMESPACE_SLUG` | Use GitLab namespace slugs for service names instead of display names (e.g. "main-group/sub-group/project" vs "Main Group / Sub Group / Project") | True | Boolean | False |
| `LOG_LEVEL` | Logging level for structured logs | True | String | INFO |
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
| `GLAB_USE_NAMESPACE_SLUG` | Use GitLab namespace slugs for service names instead of display names (e.g. "main-group/sub-group/project" vs "Main Group / Sub Group / Project") | True | Boolean | False |
| `LOG_LEVEL` | Logging level for structured logs | True | String | INFO |
| `Pipeline Bridges Support` | Bridges in pipelines are now exported as metrics/logs and can be excluded using `GLAB_EXCLUDE_JOBS` | True | Boolean | True |
*comma separated

**Default configuration is based on using Gitlab runners with docker executor**

If using Kubernetes executors instead, use the below configuration

```
image:
    name: docker.io/dpacheconr/gitlab-exporter:2.0.0
    entrypoint: [""]
  script:
    - python3 -u /app/main.py
    - echo "Done"
```

## Development Setup

### Requirements

The project uses pinned dependencies for reproducible builds:

- **Dependencies**: `shared/requirements.txt`

Install dependencies:

```bash
# Production dependencies
pip install -r shared/requirements.txt
```

### Running Tests

The project includes comprehensive test coverage with **322 tests** covering:

- Configuration management and validation
- GitLab API integration
- New Relic integration
- Data transformation and processing
- Performance testing
- Error handling and edge cases
- Bridge and downstream pipeline processing
- OTEL attribute filtering and helpers

Run all tests:

```bash
python3 -m pytest tests/ -v
```

Run specific test modules:

```bash
# Configuration tests
python3 -m pytest tests/test_config_settings.py -v

# Main module tests
python3 -m pytest tests/test_main.py -v

# Integration tests
python3 -m pytest tests/test_gitlab_integration.py -v

# Processor tests
python3 -m pytest tests/test_*_processor.py -v
```

Run tests with coverage:

```bash
python3 -m pytest tests/ --cov=shared --cov=new_relic_exporter --cov=new_relic_metrics_exporter --cov-report=html
```

## Quick Start

### Prerequisites

1. **GitLab Access Token**: Create a GitLab personal access token with `read_api` scope
2. **New Relic License Key**: Get your New Relic license key from your account settings
3. **Docker** (recommended) or Python 3.8+ environment

### Option 1: Docker Deployment (Recommended)

#### New Relic Exporter (Pipeline-level tracing)
```bash
# Run as part of your GitLab CI/CD pipeline
docker run \
  -e GLAB_TOKEN="your_gitlab_token" \
  -e NEW_RELIC_API_KEY="your_newrelic_key" \
  -e GLAB_ENDPOINT="https://gitlab.com" \
  docker.io/dpacheconr/gitlab-exporter:2.0.0
```

#### New Relic Metrics Exporter (Standalone monitoring)
```bash
# Run standalone for continuous monitoring
docker run \
  -e GLAB_STANDALONE=True \
  -e GLAB_EXPORT_PATHS="your-namespace" \
  -e GLAB_EXPORT_PROJECTS_REGEX=".*" \
  -e GLAB_TOKEN="your_gitlab_token" \
  -e NEW_RELIC_API_KEY="your_newrelic_key" \
  docker.io/dpacheconr/gitlab-metrics-exporter:2.0.0
```

### Option 2: GitLab CI/CD Integration

Add to your `.gitlab-ci.yml`:

```yaml
# For pipeline tracing
new-relic-export:
  stage: .post
  image: docker.io/dpacheconr/gitlab-exporter:2.0.0
  script:
    - python3 -u /app/main.py
  variables:
    GLAB_TOKEN: $GITLAB_TOKEN
    NEW_RELIC_API_KEY: $NEW_RELIC_LICENSE_KEY
  when: always

# For metrics collection (scheduled pipeline)
new-relic-metrics:
  image: docker.io/dpacheconr/gitlab-metrics-exporter:2.0.0
  script:
    - python3 -u /app/main.py
  variables:
    GLAB_TOKEN: $GITLAB_TOKEN
    NEW_RELIC_API_KEY: $NEW_RELIC_LICENSE_KEY
    GLAB_EXPORT_PATHS: $CI_PROJECT_ROOT_NAMESPACE
  only:
    - schedules
```

## Resources

- **New Relic Quickstart**: https://newrelic.com/instant-observability/gitlab
- **Blog Tutorial**: https://newrelic.com/blog/how-to-relic/monitor-gitlab-with-opentelemetry
- **Docker Images**: 
  - `docker.io/dpacheconr/gitlab-exporter:2.0.0`
  - `docker.io/dpacheconr/gitlab-metrics-exporter:2.0.0`

## Production Deployment

### Docker Compose

Use the provided `docker-compose.yaml` for production deployments:

```bash
# Set version and build images
export VERSION=2.0.0
docker-compose build

# Run services
docker-compose up -d
```

### Environment Configuration

Create a `.env` file based on `.env.example`:

```bash
cp .env.example .env
# Edit .env with your configuration
```

### Health Monitoring

Both exporters include comprehensive health monitoring and structured logging:

- **Structured Logging**: JSON-formatted logs with correlation IDs
- **Performance Metrics**: Built-in timing and performance tracking
- **Error Handling**: Graceful error handling with detailed error context
- **Configuration Validation**: Startup validation of all required settings

### Security Considerations

- **Token Security**: All sensitive tokens are masked in logs
- **Environment Variables**: Sensitive environment variables are automatically filtered
- **HTTPS**: All New Relic endpoints use HTTPS by default
- **Minimal Permissions**: GitLab tokens only require `read_api` scope

## Troubleshooting

### Common Issues

1. **Authentication Errors**
   - Verify GitLab token has `read_api` scope
   - Check New Relic license key format
   - Ensure correct GitLab endpoint URL

2. **No Data in New Relic**
   - Verify OTEL endpoint is correct for your region
   - Check network connectivity to New Relic
   - Review structured logs for export errors

3. **Performance Issues**
   - Use `GLAB_LOW_DATA_MODE=True` for testing
   - Adjust `GLAB_EXPORT_LAST_MINUTES` for metrics exporter
   - Consider excluding jobs with `GLAB_EXCLUDE_JOBS`

### Debug Mode

The project supports configurable logging levels via the `LOG_LEVEL` environment variable:

```bash
# Set log level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
LOG_LEVEL=DEBUG
```

## Contributing

We encourage your contributions to improve [GitLab Exporters](../../)! Keep in mind when you submit your pull request, you'll need to sign the CLA via the click-through using CLA-Assistant. You only have to sign the CLA one time per project. If you have any questions, or to execute our corporate CLA, required if your contribution is on behalf of a company, please drop us an email at opensource@newrelic.com.

### Development Guidelines

- All code must pass the comprehensive test suite (322 tests)
- Follow the existing code structure and patterns
- Add tests for new functionality
- Update documentation for configuration changes

**A note about vulnerabilities**

As noted in our [security policy](../../security/policy), New Relic is committed to the privacy and security of our customers and their data. We believe that providing coordinated disclosure by security researchers and engaging with the security community are important means to achieve our security goals.

If you believe you have found a security vulnerability in this project or any of New Relic's products or websites, we welcome and greatly appreciate you reporting it to New Relic through [HackerOne](https://hackerone.com/newrelic).

## License

GitLab Exporters are licensed under the [Apache 2.0](http://apache.org/licenses/LICENSE-2.0.txt) License.

>GitLab Exporters also use source code from third-party libraries. You can find full details on which libraries are used and the terms under which they are licensed in the third-party notices document.
