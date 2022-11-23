
#New Relic Exporter

| Variables | Description | Optional | Values | Default |
| ---       |         --- |       ---| ---    |   ----   |
| `OTEL_EXPORTER_OTEL_ENDPOINT` | New Relic OTEL endpoint including port | True | String | "https://otlp.nr-data.net:4318" or "https://otlp.eu01.nr-data.net:4318" |
| `GLAB_TOKEN` | Token to access gitlab API | False | String | None |
| `NEW_RELIC_API_KEY` | New Relic License Key | False | String | None |
| `GLAB_SERVICE_NAME` | New Relic OTEL entity name | True | String | True |
| `GLAB_EXPORT_LOGS` | Export job logs to New Relic | True | Boolean | True |

#New Relic Metrics Exporter

| Variables | Description | Optional | Values | Default |
| ---       |         --- |       ---| ---    |   ----   |
| `OTEL_EXPORTER_OTEL_ENDPOINT` | New Relic OTEL endpoint including port | True | String | "https://otlp.nr-data.net:4318" or "https://otlp.eu01.nr-data.net:4318" |
| `GLAB_TOKEN` | Token to access gitlab API | False | String | None |
| `NEW_RELIC_API_KEY` | New Relic License Key | False | String | None |
| `GLAB_SERVICE_NAME` | New Relic OTEL entity name | True | String | Project name |
| `GLAB_EXPORT_GROUPS_REGEX` | Regex to match group names against | False | Boolean | None |
| `GLAB_EXPORT_PROJECTS_REGEX` | Regex to match project names against | False | Boolean | None |
| `GLAB_EXPORT_NON_GROUP_PROJECTS` | Enable if we should export non group projects, i.e. user projects | True | Boolean | False |
| `GLAB_EXPORT_LAST_MINUTES` | The amount past minutes to export data from | True | Integer | 60 |
| `GLAB_ENVS_DROP` | Extra system environment variables to drop from span attributes | True | List* | NEW_RELIC_API_KEY,GITLAB_FEATURES,CI_SERVER_TLS_CA_FILE,CI_RUNNER_TAGS,CI_JOB_JWT,CI_JOB_JWT_V1,CI_JOB_JWT_V2,GLAB_TOKEN,GIT_ASKPASS,CI_COMMIT_BEFORE_SHA,CI_BUILD_TOKEN,CI_DEPENDENCY_PROXY_PASSWORD,CI_RUNNER_SHORT_TOKEN,CI_BUILD_BEFORE_SHA,CI_BEFORE_SHA,OTEL_EXPORTER_OTEL_ENDPOINT,GLAB_DIMENSION_METRICS |
| `GLAB_ATTRIBUTES_DROP` | Attributes to drop from logs and spans events | True | List* | None |
| `GLAB_DIMENSION_METRICS` | Extra dimensional metric attributes to add to each metric | True | List* | status,stage,name |
| `GLAB_STANDALONE` | Set to True if not running as gitlab pipeline schedule | True | Boolean | False |
*comma separated


TODO
Dora Metrics
Sidekiq Metrics
