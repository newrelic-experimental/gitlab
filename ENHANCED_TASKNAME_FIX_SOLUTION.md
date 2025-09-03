# Enhanced TaskName Fix Solution

## Problem
OpenTelemetry LoggingInstrumentor was producing warnings in GitLab CI:
```
WARNING [opentelemetry.attributes] - Invalid type NoneType for attribute 'taskName' value. Expected one of ['bool', 'str', 'bytes', 'int', 'float'] or a sequence of those types
```

## Root Cause
OpenTelemetry's LoggingInstrumentor automatically detects environment variables and tries to use them as span attributes. In GitLab CI environments, certain variables like `taskName`, `task.name`, `job.name`, etc., may be present but have `None` values, causing type validation errors.

## Enhanced Solution

### 1. Programmatic Environment Variable Setting
The enhanced solution explicitly sets problematic environment variables to valid values before OpenTelemetry initialization:

**File: `shared/otel/resource_attributes.py`**
```python
def set_otel_resource_attributes():
    """
    Set OTEL_RESOURCE_ATTRIBUTES and fix problematic environment variables to prevent taskName warnings.
    
    This function:
    1. Preserves any existing OTEL_RESOURCE_ATTRIBUTES set by users
    2. Adds our taskName fix attributes  
    3. Uses GitLab CI environment variables when available
    4. Falls back to sensible defaults for local development
    5. Explicitly sets problematic environment variables to prevent None value detection
    """
    # Get CI job name, fallback to a default value
    ci_job_name = os.environ.get("CI_JOB_NAME", "gitlab-exporter")
    ci_pipeline_id = os.environ.get("CI_PIPELINE_ID", "unknown")
    ci_project_id = os.environ.get("CI_PROJECT_ID", "unknown")

    # CRITICAL: Set problematic environment variables to valid values
    # This prevents OpenTelemetry from auto-detecting them as None
    problematic_vars = {
        "taskName": ci_job_name,
        "task.name": ci_job_name,
        "job.name": ci_job_name,
        "pipeline.name": f"pipeline-{ci_pipeline_id}",
    }

    for var_name, var_value in problematic_vars.items():
        # Only set if not already set or if currently None
        current_value = os.environ.get(var_name)
        if current_value is None or current_value == "None":
            os.environ[var_name] = var_value
            print(f"Set environment variable {var_name}={var_value}")

    # ... rest of OTEL_RESOURCE_ATTRIBUTES configuration
```

### 2. Integration in Main Files
Both main entry points call the fix before OpenTelemetry initialization:

**File: `new_relic_exporter/main.py`**
```python
from shared.otel.resource_attributes import set_otel_resource_attributes

# Set OTEL_RESOURCE_ATTRIBUTES to prevent taskName warnings
set_otel_resource_attributes()

# Initialize OpenTelemetry logging instrumentation
LoggingInstrumentor().instrument(set_logging_format=True, log_level=logging.INFO)
```

**File: `new_relic_metrics_exporter/main.py`**
```python
from shared.otel.resource_attributes import set_otel_resource_attributes

# Set OTEL_RESOURCE_ATTRIBUTES to prevent taskName warnings
set_otel_resource_attributes()
```

## Key Features

### 1. User Configuration Preservation
- Merges with existing `OTEL_RESOURCE_ATTRIBUTES` if set by users
- Only adds default service attributes if user doesn't have any service.* attributes
- Respects user's existing configuration completely

### 2. Environment Variable Fixing
- Explicitly sets `taskName`, `task.name`, `job.name`, `pipeline.name` to valid values
- Only overwrites if current value is `None` or `"None"`
- Uses GitLab CI variables when available, falls back to defaults

### 3. GitLab CI Integration
- Uses `CI_JOB_NAME`, `CI_PIPELINE_ID`, `CI_PROJECT_ID` when available
- Provides sensible defaults for local development
- Works in both GitLab CI and local environments

## Testing

### Test Results
```bash
$ python test_enhanced_taskname_fix.py
🔧 Testing Enhanced TaskName Fix
==================================================
1. Before fix - problematic environment variables:
   taskName: None
   task.name: None
   job.name: None
   pipeline.name: None

2. Applying enhanced fix...
Set environment variable taskName=gitlab-exporter
Set environment variable task.name=gitlab-exporter
Set environment variable job.name=gitlab-exporter
Set environment variable pipeline.name=pipeline-2017065587

3. After fix - environment variables:
   taskName: gitlab-exporter
   task.name: gitlab-exporter
   job.name: gitlab-exporter
   pipeline.name: pipeline-2017065587

5. Testing OpenTelemetry LoggingInstrumentor...
   ✅ LoggingInstrumentor initialized successfully
   ✅ Test log message sent without warnings

🎯 Enhanced fix applied successfully!
```

## Implementation Status

✅ **Implemented in both exporters:**
- `new_relic_exporter/main.py` - ✅ Fixed
- `new_relic_metrics_exporter/main.py` - ✅ Fixed

✅ **Comprehensive solution:**
- Environment variable setting - ✅ Implemented
- OTEL_RESOURCE_ATTRIBUTES merging - ✅ Implemented
- User configuration preservation - ✅ Implemented
- Testing - ✅ Verified

## Expected Results

After deploying this enhanced solution:
1. **No more taskName warnings** in GitLab CI logs
2. **Preserved user configurations** for OTEL_RESOURCE_ATTRIBUTES
3. **Proper OpenTelemetry functionality** maintained
4. **Works in all environments** (GitLab CI, local development)

The enhanced solution addresses the root cause by preventing OpenTelemetry from detecting problematic environment variables with None values, while maintaining full compatibility with user configurations.
