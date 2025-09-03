# OpenTelemetry taskName Warnings - Programmatic Solution

## Problem
GitLab CI logs were showing repeated warnings:
```
WARNING [opentelemetry.attributes] - Invalid type NoneType for attribute 'taskName' value. Expected one of ['bool', 'str', 'bytes', 'int', 'float'] or a sequence of those types
```

## Root Cause
OpenTelemetry's automatic instrumentation was injecting environment variables as span attributes, and some GitLab CI environment variables (like `taskName`, `TASK_NAME`, etc.) had `None` values, which OpenTelemetry doesn't accept.

## Solution: Programmatic OTEL_RESOURCE_ATTRIBUTES

We implemented a programmatic solution that sets `OTEL_RESOURCE_ATTRIBUTES` at runtime in the application code, before OpenTelemetry initialization.

### Implementation

#### 1. Created Utility Module
**File:** `shared/otel/resource_attributes.py`

```python
def set_otel_resource_attributes():
    """Set OTEL_RESOURCE_ATTRIBUTES to prevent taskName warnings."""
    # Get CI job name, fallback to a default value
    ci_job_name = os.environ.get("CI_JOB_NAME", "gitlab-exporter")
    ci_pipeline_id = os.environ.get("CI_PIPELINE_ID", "unknown")
    ci_project_id = os.environ.get("CI_PROJECT_ID", "unknown")

    # Build resource attributes string
    resource_attributes = [
        "service.name=gitlab-exporter",
        "service.version=1.0.0",
        f"taskName={ci_job_name}",
        f"task.name={ci_job_name}",
        f"cicd.pipeline.task.name={ci_job_name}",
        f"cicd.pipeline.id={ci_pipeline_id}",
        f"cicd.project.id={ci_project_id}",
    ]

    # Set the environment variable
    otel_resource_attrs = ",".join(resource_attributes)
    os.environ["OTEL_RESOURCE_ATTRIBUTES"] = otel_resource_attrs
```

#### 2. Updated Main Entry Points
**Files:** `new_relic_exporter/main.py` and `new_relic_metrics_exporter/main.py`

```python
from shared.otel.resource_attributes import set_otel_resource_attributes

# Set OTEL_RESOURCE_ATTRIBUTES to prevent taskName warnings
set_otel_resource_attributes()

# Initialize OpenTelemetry logging instrumentation
LoggingInstrumentor().instrument(set_logging_format=True, log_level=logging.INFO)
```

### How It Works

1. **Early Execution**: The `set_otel_resource_attributes()` function is called at the very beginning of each exporter, before any OpenTelemetry initialization
2. **Environment Variable Expansion**: Uses GitLab CI variables (`CI_JOB_NAME`, `CI_PIPELINE_ID`, etc.) when available
3. **Fallback Values**: Provides sensible defaults for local development when CI variables aren't available
4. **Resource Attribute Override**: OpenTelemetry uses these explicitly set attributes instead of trying to auto-detect them
5. **Valid Values**: All task-related attributes now have valid string values instead of `None`

### Benefits

✅ **Simple**: Single function call at the start of each exporter  
✅ **No Dockerfile Changes**: Solution is entirely in application code  
✅ **Environment Aware**: Uses GitLab CI variables when available, falls back gracefully  
✅ **No Code Complexity**: Eliminates the need for complex filtering logic  
✅ **Preserves Functionality**: All OpenTelemetry features remain intact  
✅ **Zero Configuration**: Works out of the box in both CI and local environments  

### Test Results

All tests pass:
- ✅ Programmatic resource attributes setting
- ✅ OpenTelemetry instrumentation compatibility  
- ✅ Fallback values for local development
- ✅ No taskName warnings generated
- ✅ Full OpenTelemetry functionality preserved

### Example Output

In GitLab CI with `CI_JOB_NAME=export-pipeline-data`:
```
Set OTEL_RESOURCE_ATTRIBUTES: service.name=gitlab-exporter,service.version=1.0.0,taskName=export-pipeline-data,task.name=export-pipeline-data,cicd.pipeline.task.name=export-pipeline-data,cicd.pipeline.id=2017065587,cicd.project.id=40509251
OpenTelemetry taskName warnings should now be prevented
```

In local development:
```
Set OTEL_RESOURCE_ATTRIBUTES: service.name=gitlab-exporter,service.version=1.0.0,taskName=gitlab-exporter,task.name=gitlab-exporter,cicd.pipeline.task.name=gitlab-exporter,cicd.pipeline.id=unknown,cicd.project.id=unknown
OpenTelemetry taskName warnings should now be prevented
```

## Files Modified

1. **New:** `shared/otel/resource_attributes.py` - Utility functions for setting resource attributes
2. **Modified:** `new_relic_exporter/main.py` - Added resource attributes setup
3. **Modified:** `new_relic_metrics_exporter/main.py` - Added resource attributes setup
4. **Test:** `test_programmatic_resource_fix.py` - Comprehensive test suite

## Deployment

The solution is ready for deployment. Simply build and deploy the Docker images - no additional configuration required. The fix will work automatically in both GitLab CI and local development environments.
