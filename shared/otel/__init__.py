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


def flush_otel_logs(logger):
    """
    Flush all pending OTEL logs from a logger.

    This ensures all batched logs are exported before process exit.
    Critical for high-volume scenarios where logs may accumulate faster
    than the batch flush interval.

    Args:
        logger: Python logging.Logger instance created by get_logger()
    """
    if logger is None:
        return

    _debug_print("flush_otel_logs() - flushing pending logs")

    try:
        # Check if logger has the attached OTEL provider
        if hasattr(logger, "_otel_logger_provider"):
            _debug_print(f"  Found attached LoggerProvider, forcing flush...")
            logger._otel_logger_provider.force_flush(timeout_millis=30000)
            _debug_print(f"  ✓ Logs flushed successfully (30 second timeout)")
            return

        _debug_print(f"  No OTEL LoggerProvider attached to logger")
    except Exception as e:
        _debug_print(f"  Error during flush: {type(e).__name__}: {e}")


def shutdown_otel_providers(logger, tracer_provider=None, meter_provider=None):
    """
    Shutdown all OTEL providers, ensuring all queued data is exported.

    The shutdown() method:
    1. Stops accepting new data
    2. Exports all queued/batched data
    3. Waits for all exports to complete (respects timeout)
    4. Cleans up resources

    Args:
        logger: Python logging.Logger instance created by get_logger()
        tracer_provider: Optional TracerProvider to shutdown
        meter_provider: Optional MeterProvider to shutdown
    """
    import time

    shutdown_start = time.time()
    _debug_print("=" * 80)
    _debug_print(f"shutdown_otel_providers() - START at {time.strftime('%H:%M:%S')}")
    _debug_print("=" * 80)

    shutdown_successful = True

    # Shutdown LoggerProvider (logs)
    if logger and hasattr(logger, "_otel_logger_provider"):
        try:
            log_provider_start = time.time()
            _debug_print("  [LoggerProvider] Initiating shutdown...")

            # Try to get queue stats before shutdown
            try:
                provider = logger._otel_logger_provider
                _debug_print(f"    [Provider] Type: {type(provider).__name__}")

                # Access the multi processor and its child processors
                if hasattr(provider, "_multi_log_record_processor"):
                    multi_processor = provider._multi_log_record_processor
                    _debug_print(
                        f"    [MultiProcessor] Type: {type(multi_processor).__name__}"
                    )

                    if hasattr(multi_processor, "_log_record_processors"):
                        processors = multi_processor._log_record_processors
                        _debug_print(
                            f"    [MultiProcessor] Number of child processors: {len(processors)}"
                        )

                        for i, processor in enumerate(processors):
                            processor_type = type(processor).__name__
                            _debug_print(f"    [Processor {i}] Type: {processor_type}")

                            # Only BatchLogRecordProcessor has queue stats
                            if "Batch" in processor_type:
                                # The actual batch processor is nested inside
                                batch_proc = None
                                if hasattr(processor, "_batch_processor"):
                                    batch_proc = processor._batch_processor
                                    _debug_print(f"      Found nested _batch_processor")
                                else:
                                    batch_proc = processor

                                if batch_proc:
                                    try:
                                        if hasattr(batch_proc, "_queue"):
                                            queue = batch_proc._queue
                                            queue_size = (
                                                queue.qsize()
                                                if hasattr(queue, "qsize")
                                                else "unknown"
                                            )
                                            _debug_print(
                                                f"      ⚠ Queue size: {queue_size} records QUEUED"
                                            )
                                        else:
                                            _debug_print(
                                                "      No _queue found in batch processor"
                                            )
                                    except Exception as qe:
                                        _debug_print(
                                            f"      Could not get queue size: {qe}"
                                        )

                                    try:
                                        if hasattr(batch_proc, "_max_queue_size"):
                                            _debug_print(
                                                f"      Max queue size: {batch_proc._max_queue_size}"
                                            )
                                    except Exception as mqe:
                                        _debug_print(
                                            f"      Could not get max queue size: {mqe}"
                                        )

                                    try:
                                        if hasattr(
                                            batch_proc, "_max_export_batch_size"
                                        ):
                                            _debug_print(
                                                f"      Max export batch size: {batch_proc._max_export_batch_size}"
                                            )
                                    except Exception as mbe:
                                        _debug_print(
                                            f"      Could not get max batch size: {mbe}"
                                        )

                                    try:
                                        if hasattr(
                                            batch_proc, "_schedule_delay_millis"
                                        ):
                                            delay_ms = batch_proc._schedule_delay_millis
                                            _debug_print(
                                                f"      Schedule delay: {delay_ms}ms ({delay_ms/1000:.1f}s)"
                                            )
                                            _debug_print(
                                                f"      Schedule delay: First export occurs {delay_ms}ms after process start"
                                            )
                                    except Exception as sde:
                                        _debug_print(
                                            f"      Could not get schedule delay: {sde}"
                                        )

                                try:
                                    if hasattr(processor, "_max_queue_size"):
                                        _debug_print(
                                            f"      Max queue size: {processor._max_queue_size}"
                                        )
                                except Exception as mqe:
                                    _debug_print(
                                        f"      Could not get max queue size: {mqe}"
                                    )

                                try:
                                    if hasattr(processor, "_max_export_batch_size"):
                                        _debug_print(
                                            f"      Max export batch size: {processor._max_export_batch_size}"
                                        )
                                except Exception as mbe:
                                    _debug_print(
                                        f"      Could not get max batch size: {mbe}"
                                    )

                                try:
                                    if hasattr(processor, "_schedule_delay_millis"):
                                        delay_ms = processor._schedule_delay_millis
                                        _debug_print(
                                            f"      Schedule delay: {delay_ms}ms ({delay_ms/1000:.1f}s)"
                                        )
                                        _debug_print(
                                            f"      Schedule delay: First export occurs {delay_ms}ms after process start"
                                        )
                                except Exception as sde:
                                    _debug_print(
                                        f"      Could not get schedule delay: {sde}"
                                    )
                    else:
                        _debug_print(
                            "    [MultiProcessor] No _log_record_processors found"
                        )
                else:
                    _debug_print(
                        "    [Provider] No _multi_log_record_processor attribute found"
                    )
            except Exception as e:
                import traceback

                _debug_print(f"    Could not retrieve queue stats: {e}")
                _debug_print(f"    {traceback.format_exc()}")

            _debug_print(
                "    [Action] Calling shutdown() - will block until queue is empty or timeout (30s)"
            )
            _debug_print(
                "    [Action] Stopping batch processor from accepting new records"
            )
            _debug_print("    [Action] Exporting all queued log records")
            _debug_print("    [Action] Waiting for all export operations to complete")

            # shutdown() will:
            # 1. Signal the batch processor to stop accepting new records
            # 2. Export all queued records (respects max_export_batch_size)
            # 3. Wait for all export operations to complete
            # 4. Clean up resources
            result = logger._otel_logger_provider.shutdown()

            shutdown_duration = time.time() - log_provider_start

            if result:
                _debug_print(
                    f"  ✓ [LoggerProvider] Shutdown successful - all logs exported"
                )
                _debug_print(f"    [Timing] Shutdown took {shutdown_duration:.3f}s")
            else:
                _debug_print(
                    f"  ⚠ [LoggerProvider] Shutdown timed out after {shutdown_duration:.3f}s - some logs may be lost"
                )
                shutdown_successful = False

        except Exception as e:
            shutdown_duration = time.time() - log_provider_start
            _debug_print(
                f"  ✗ [LoggerProvider] Error during shutdown after {shutdown_duration:.3f}s: {type(e).__name__}: {e}"
            )
            import traceback

            _debug_print(f"    [Error Details] {traceback.format_exc()}")
            shutdown_successful = False
    else:
        _debug_print(
            "  [LoggerProvider] No LoggerProvider to shutdown (logger has no _otel_logger_provider attribute)"
        )

    # Shutdown TracerProvider (spans)
    if tracer_provider:
        try:
            tracer_start = time.time()
            _debug_print("  [TracerProvider] Shutting down...")
            result = tracer_provider.shutdown()
            tracer_duration = time.time() - tracer_start
            if result:
                _debug_print(
                    f"  ✓ [TracerProvider] Shutdown successful - all spans exported ({tracer_duration:.3f}s)"
                )
            else:
                _debug_print(
                    f"  ⚠ [TracerProvider] Shutdown timed out after {tracer_duration:.3f}s"
                )
                shutdown_successful = False
        except Exception as e:
            tracer_duration = time.time() - tracer_start
            _debug_print(
                f"  ✗ [TracerProvider] Error during shutdown after {tracer_duration:.3f}s: {type(e).__name__}: {e}"
            )
            shutdown_successful = False
    else:
        _debug_print(
            "  [TracerProvider] No TracerProvider provided (optional parameter)"
        )

    # Shutdown MeterProvider (metrics)
    if meter_provider:
        try:
            meter_start = time.time()
            _debug_print("  [MeterProvider] Shutting down...")
            result = meter_provider.shutdown()
            meter_duration = time.time() - meter_start
            if result:
                _debug_print(
                    f"  ✓ [MeterProvider] Shutdown successful - all metrics exported ({meter_duration:.3f}s)"
                )
            else:
                _debug_print(
                    f"  ⚠ [MeterProvider] Shutdown timed out after {meter_duration:.3f}s"
                )
                shutdown_successful = False
        except Exception as e:
            meter_duration = time.time() - meter_start
            _debug_print(
                f"  ✗ [MeterProvider] Error during shutdown after {meter_duration:.3f}s: {type(e).__name__}: {e}"
            )
            shutdown_successful = False
    else:
        _debug_print("  [MeterProvider] No MeterProvider provided (optional parameter)")

    total_duration = time.time() - shutdown_start
    _debug_print("=" * 80)
    if shutdown_successful:
        _debug_print(
            f"shutdown_otel_providers() completed successfully in {total_duration:.3f}s - all data exported"
        )
    else:
        _debug_print(
            f"shutdown_otel_providers() completed with warnings in {total_duration:.3f}s - check logs above"
        )
    _debug_print("=" * 80)

    return shutdown_successful


def create_resource_attributes(atts, GLAB_SERVICE_NAME):
    attributes = {SERVICE_NAME: GLAB_SERVICE_NAME}

    for att in atts:
        # Only filter out None values and empty strings - rely on do_parse() for validation
        if atts[att] is not None and atts[att] != "" and atts[att] != "None":
            if att != "name":
                attributes[att] = atts[att]
            else:
                attributes["resource.name"] = atts[att]

    # Log attributes debug information
    log_attributes_debug(attributes, "create_resource_attributes")

    return attributes


def get_logger(endpoint, headers, resource, name, exporter_type="otlp"):
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
        f"get_logger() called - name='{name}', exporter_type='{exporter_type}'"
    )
    _debug_print(f"  Endpoint: {endpoint}")
    _debug_print(
        f"  Headers (first 20 chars): {headers[:20] if headers else 'None'}..."
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

    # Attach logger_provider to logger so flush_otel_logs can access it
    logger._otel_logger_provider = logger_provider

    _debug_print(f"get_logger() completed successfully - logger '{name}' ready")
    return logger


def get_meter(endpoint, headers, resource, meter):
    _debug_print(f"get_meter() called - meter='{meter}'")
    _debug_print(f"  Endpoint: {endpoint}")
    _debug_print(
        f"  Headers (first 20 chars): {headers[:20] if headers else 'None'}..."
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
    _debug_print(f"get_meter() completed successfully - meter ready")
    return meter


def get_tracer(endpoint, headers, resource, tracer):
    _debug_print(f"get_tracer() called - tracer='{tracer}'")
    _debug_print(f"  Endpoint: {endpoint}")
    _debug_print(
        f"  Headers (first 20 chars): {headers[:20] if headers else 'None'}..."
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
