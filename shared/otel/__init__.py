import logging
import os
import sys

from opentelemetry import metrics, trace
from shared.custom_parsers import log_attributes_debug
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor, ConsoleLogExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.resources import SERVICE_NAME
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def _is_debug_enabled():
    """Check if DEBUG logging is enabled."""
    log_level = os.getenv("LOG_LEVEL", "INFO").upper()
    return log_level == "DEBUG"


def _debug_print(message: str):
    """Print debug message to stderr when LOG_LEVEL=DEBUG."""
    if _is_debug_enabled():
        print(f"[OTEL_DEBUG] {message}", file=sys.stderr, flush=True)


def shutdown_otel_providers(
    logger, tracer_provider=None, meter_provider=None, meter=None
):
    """
    Shutdown all OTEL providers, flushing any queued telemetry before exit.

    Required for short-lived processes: shutdown() drains the BatchLogRecordProcessor
    queue and waits for all in-flight exports to complete before returning.

    Args:
        logger: Python logging.Logger instance created by get_logger()
        tracer_provider: Optional TracerProvider to shutdown
        meter_provider: Optional MeterProvider to shutdown
        meter: Optional meter returned by get_meter(); provider extracted via _meter_provider
    """
    shutdown_successful = True

    if logger and hasattr(logger, "_otel_logger_provider"):
        try:
            _debug_print("Shutting down LoggerProvider...")
            logger._otel_logger_provider.shutdown()
            _debug_print("LoggerProvider shutdown complete")
        except Exception as e:
            _debug_print(f"LoggerProvider shutdown error: {type(e).__name__}: {e}")
            shutdown_successful = False

    if tracer_provider:
        try:
            _debug_print("Shutting down TracerProvider...")
            tracer_provider.shutdown()
            _debug_print("TracerProvider shutdown complete")
        except Exception as e:
            _debug_print(f"TracerProvider shutdown error: {type(e).__name__}: {e}")
            shutdown_successful = False

    # Resolve meter_provider from meter if not passed directly
    resolved_meter_provider = meter_provider or (
        getattr(meter, "_meter_provider", None) if meter else None
    )
    if resolved_meter_provider:
        try:
            _debug_print("Shutting down MeterProvider...")
            resolved_meter_provider.shutdown()
            _debug_print("MeterProvider shutdown complete")
        except Exception as e:
            _debug_print(f"MeterProvider shutdown error: {type(e).__name__}: {e}")
            shutdown_successful = False

    return shutdown_successful


# Attributes always promoted to resource level, regardless of GLAB_ATTRIBUTES_TO_KEEP
_DEFAULT_REQUIRED_ATTRS = frozenset([
    # Entity identifiers
    "id",
    "project_id",
    "pipeline_id",
    "job_id",
    "environment_id",
    "deployment_id",
    "release_id",
    # OTel / GitLab metadata
    "service.name",
    "gitlab.resource.type",
    "gitlab.source",
    # Dashboard-critical filtering/grouping attributes
    "status",
    "stage",
    "online",
    "failure_reason",
    "entity.name",
    "finished_at",
    "description",
])

# Cache user-configured keep list at module level — env vars don't change at runtime
_ATTRIBUTES_TO_KEEP: list = [
    a.strip()
    for a in os.getenv("GLAB_ATTRIBUTES_TO_KEEP", "").split(",")
    if a.strip()
]


def create_resource_attributes(atts, GLAB_SERVICE_NAME):
    """
    Build resource-level attributes for an OpenTelemetry Resource.

    Only required system attributes and user-specified GLAB_ATTRIBUTES_TO_KEEP
    attributes are promoted to resource level. All other attributes should be
    passed as log-record-level attributes so the SDK can manage truncation via
    OTEL_LOGRECORD_ATTRIBUTE_COUNT_LIMIT.
    """
    required_attrs = _DEFAULT_REQUIRED_ATTRS | frozenset(_ATTRIBUTES_TO_KEEP)

    attributes = {SERVICE_NAME: GLAB_SERVICE_NAME}

    for key in required_attrs:
        if (
            key in atts
            and atts[key] is not None
            and atts[key] != ""
            and atts[key] != "None"
        ):
            attributes[key] = atts[key]

    # Log attributes debug information
    log_attributes_debug(attributes, "create_resource_attributes")

    return attributes


def get_otel_logger(endpoint, headers, resource, name, exporter_type="otlp"):
    """
    Create a logger with configurable exporter type.

    Args:
        endpoint: OTLP endpoint URL
        headers: OTLP headers (api-key)
        resource: OpenTelemetry resource
        name: Logger name
        exporter_type: Type of exporter - "otlp", "console", or "both" (default: "otlp")

    Returns:
        Configured logger instance
    """
    _debug_print(
        f"get_otel_logger() called - name='{name}', exporter_type='{exporter_type}'"
    )
    _debug_print(f"  Endpoint: {endpoint}")
    _debug_print(
        f"  Headers: {'<set>' if headers else 'None'}"
    )
    _debug_print(
        f"  Resource attributes: {resource.attributes if hasattr(resource, 'attributes') else 'N/A'}"
    )

    logger = logging.getLogger(str(name))
    logger.handlers.clear()
    logger_provider = LoggerProvider(resource=resource)
    _debug_print(f"  LoggerProvider created")

    # BatchLogRecordProcessor automatically reads these environment variables:
    # - OTEL_BLRP_MAX_QUEUE_SIZE (default: 2048)
    # - OTEL_BLRP_MAX_EXPORT_BATCH_SIZE (default: 512)
    # - OTEL_BLRP_SCHEDULE_DELAY (default: 5000 milliseconds)
    # - OTEL_BLRP_EXPORT_TIMEOUT (default: 30000 milliseconds)
    # Set these in your environment to tune for high-volume scenarios (e.g., 1000+ log records)

    # Add exporters based on exporter_type
    if exporter_type.lower() == "console":
        # Console only
        _debug_print(f"  Initializing ConsoleLogExporter (console only mode)")
        console_exporter = ConsoleLogExporter()
        logger_provider.add_log_record_processor(
            BatchLogRecordProcessor(console_exporter)
        )
        _debug_print(f"  ✓ ConsoleLogExporter registered with BatchLogRecordProcessor")
    elif exporter_type.lower() == "both":
        # Both OTLP and Console
        _debug_print(
            f"  Initializing OTLPLogExporter and ConsoleLogExporter (both mode)"
        )
        otlp_exporter = OTLPLogExporter(endpoint=endpoint, headers=headers)
        logger_provider.add_log_record_processor(BatchLogRecordProcessor(otlp_exporter))
        _debug_print(f"  ✓ OTLPLogExporter registered with BatchLogRecordProcessor")
        console_exporter = ConsoleLogExporter()
        logger_provider.add_log_record_processor(
            BatchLogRecordProcessor(console_exporter)
        )
        _debug_print(f"  ✓ ConsoleLogExporter registered with BatchLogRecordProcessor")
    else:
        # Default to OTLP only
        _debug_print(f"  Initializing OTLPLogExporter (OTLP only mode - default)")
        otlp_exporter = OTLPLogExporter(endpoint=endpoint, headers=headers)
        logger_provider.add_log_record_processor(BatchLogRecordProcessor(otlp_exporter))
        _debug_print(f"  ✓ OTLPLogExporter registered with BatchLogRecordProcessor")

    handler = LoggingHandler(level=logging.NOTSET, logger_provider=logger_provider)
    logger.addHandler(handler)

    # Attach logger_provider to logger so shutdown_otel_providers can access it
    logger._otel_logger_provider = logger_provider

    _debug_print(f"get_otel_logger() completed successfully - logger '{name}' ready")
    return logger


def get_meter(endpoint, headers, resource, meter):
    _debug_print(f"get_meter() called - meter='{meter}'")
    _debug_print(f"  Endpoint: {endpoint}")
    _debug_print(
        f"  Headers: {'<set>' if headers else 'None'}"
    )
    _debug_print(
        f"  Resource attributes: {resource.attributes if hasattr(resource, 'attributes') else 'N/A'}"
    )

    _debug_print(f"  Initializing OTLPMetricExporter")
    metric_exporter = OTLPMetricExporter(endpoint=endpoint, headers=headers)
    _debug_print(f"  ✓ OTLPMetricExporter created")

    _debug_print(f"  Creating PeriodicExportingMetricReader")
    reader = PeriodicExportingMetricReader(metric_exporter)
    _debug_print(f"  ✓ PeriodicExportingMetricReader created")

    _debug_print(f"  Creating MeterProvider")
    provider = MeterProvider(resource=resource, metric_readers=[reader])
    _debug_print(f"  ✓ MeterProvider created")

    _debug_print(f"  Getting meter from provider")
    meter = metrics.get_meter(__name__, meter_provider=provider)
    # Attach provider so shutdown_otel_providers can flush buffered metrics
    meter._meter_provider = provider
    _debug_print(f"get_meter() completed successfully - meter ready")
    return meter


def get_tracer(endpoint, headers, resource, tracer):
    _debug_print(f"get_tracer() called - tracer='{tracer}'")
    _debug_print(f"  Endpoint: {endpoint}")
    _debug_print(
        f"  Headers: {'<set>' if headers else 'None'}"
    )
    _debug_print(
        f"  Resource attributes: {resource.attributes if hasattr(resource, 'attributes') else 'N/A'}"
    )

    _debug_print(f"  Initializing OTLPSpanExporter")
    span_exporter = OTLPSpanExporter(endpoint=endpoint, headers=headers)
    _debug_print(f"  ✓ OTLPSpanExporter created")

    # BatchSpanProcessor automatically reads these environment variables:
    # - OTEL_BSP_MAX_QUEUE_SIZE (default: 2048)
    # - OTEL_BSP_MAX_EXPORT_BATCH_SIZE (default: 512)
    # - OTEL_BSP_SCHEDULE_DELAY (default: 5000 milliseconds)
    # - OTEL_BSP_EXPORT_TIMEOUT (default: 30000 milliseconds)
    # Set these in your environment to tune for high-volume scenarios

    _debug_print(f"  Creating BatchSpanProcessor")
    processor = BatchSpanProcessor(span_exporter)
    _debug_print(f"  ✓ BatchSpanProcessor created")

    _debug_print(f"  Creating TracerProvider")
    tracer_provider = TracerProvider(resource=resource)
    _debug_print(f"  ✓ TracerProvider created")

    _debug_print(f"  Registering span processor")
    tracer_provider.add_span_processor(processor)
    _debug_print(f"  ✓ BatchSpanProcessor registered")

    _debug_print(f"  Getting tracer from provider")
    tracer = trace.get_tracer(__name__, tracer_provider=tracer_provider)
    _debug_print(f"get_tracer() completed successfully - tracer ready")
    return tracer
