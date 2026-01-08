import logging
import os

from opentelemetry import metrics, trace
from opentelemetry.exporter.otlp.proto.grpc._log_exporter import OTLPLogExporter
from opentelemetry.exporter.otlp.proto.grpc.metric_exporter import OTLPMetricExporter
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import PeriodicExportingMetricReader
from opentelemetry.sdk.metrics.view import View
from opentelemetry.sdk.resources import SERVICE_NAME
from opentelemetry.sdk.trace import TracerProvider, SpanLimits
from opentelemetry.sdk.trace.export import BatchSpanProcessor


def log_attributes_debug(attributes, source_name=""):
    """
    Debug function to log attribute count and their value lengths.
    Useful for debugging attribute limits issues.
    """
    if not attributes:
        logging.debug(f"[{source_name}] Attributes: NONE")
        return

    attr_count = len(attributes)
    attr_lengths = {key: len(str(value)) for key, value in attributes.items()}
    max_length = max(attr_lengths.values()) if attr_lengths else 0
    total_length = sum(attr_lengths.values())

    logging.debug(
        f"[{source_name}] Attribute Count: {attr_count}, "
        f"Max Value Length: {max_length}, Total Length: {total_length}"
    )

    # Log attributes with values that might exceed typical limits
    for key, value in attributes.items():
        value_str = str(value)
        if len(value_str) > 1024:  # Flag values over 1024 chars
            logging.debug(
                f"[{source_name}] Long attribute - {key}: {len(value_str)} chars"
            )


def create_resource_attributes(atts, GLAB_SERVICE_NAME):
    attributes = {SERVICE_NAME: GLAB_SERVICE_NAME}

    for att in atts:
        # Only filter out None values and empty strings - rely on do_parse() for validation
        if atts[att] is not None and atts[att] != "" and atts[att] != "None":
            if att != "name":
                attributes[att] = atts[att]
            else:
                attributes["resource.name"] = atts[att]
    return attributes


def get_logger(endpoint, headers, resource, name):
    exporter = OTLPLogExporter(endpoint=endpoint, headers=headers)
    logger = logging.getLogger(str(name))
    logger.handlers.clear()

    # Debug: Log the attribute limits being applied
    attr_value_length_limit = os.getenv("OTEL_ATTRIBUTE_VALUE_LENGTH_LIMIT", "default")
    attr_count_limit = os.getenv("OTEL_ATTRIBUTE_COUNT_LIMIT", "default")
    logging.debug(
        f"[LoggerProvider] Initializing - respecting OTEL environment variables: "
        f"OTEL_ATTRIBUTE_VALUE_LENGTH_LIMIT={attr_value_length_limit}, "
        f"OTEL_ATTRIBUTE_COUNT_LIMIT={attr_count_limit}"
    )

    logger_provider = LoggerProvider(resource=resource)
    logger_provider.add_log_record_processor(BatchLogRecordProcessor(exporter))
    handler = LoggingHandler(level=logging.NOTSET, logger_provider=logger_provider)
    logger.addHandler(handler)
    return logger


def get_meter(endpoint, headers, resource, meter):
    reader = PeriodicExportingMetricReader(
        OTLPMetricExporter(endpoint=endpoint, headers=headers)
    )
    view = View(instrument_name="*")

    # Debug: Log the attribute limits being applied
    attr_value_length_limit = os.getenv("OTEL_ATTRIBUTE_VALUE_LENGTH_LIMIT", "default")
    attr_count_limit = os.getenv("OTEL_ATTRIBUTE_COUNT_LIMIT", "default")
    logging.debug(
        f"[MeterProvider] Initializing with limits - "
        f"OTEL_ATTRIBUTE_VALUE_LENGTH_LIMIT={attr_value_length_limit}, "
        f"OTEL_ATTRIBUTE_COUNT_LIMIT={attr_count_limit}"
    )

    provider = MeterProvider(resource=resource, metric_readers=[reader], views=[view])
    meter = metrics.get_meter(__name__, meter_provider=provider)
    return meter


def get_tracer(endpoint, headers, resource, tracer):
    processor = BatchSpanProcessor(OTLPSpanExporter(endpoint=endpoint, headers=headers))
    span_limits = SpanLimits()

    # Debug: Log the attribute limits being applied
    attr_value_length_limit = os.getenv("OTEL_ATTRIBUTE_VALUE_LENGTH_LIMIT", "default")
    attr_count_limit = os.getenv("OTEL_ATTRIBUTE_COUNT_LIMIT", "default")
    logging.debug(
        f"[TracerProvider] Initializing with limits - "
        f"OTEL_ATTRIBUTE_VALUE_LENGTH_LIMIT={attr_value_length_limit}, "
        f"OTEL_ATTRIBUTE_COUNT_LIMIT={attr_count_limit}"
    )

    tracer = TracerProvider(resource=resource, span_limits=span_limits)
    tracer.add_span_processor(processor)
    tracer = trace.get_tracer(__name__, tracer_provider=tracer)

    return tracer
