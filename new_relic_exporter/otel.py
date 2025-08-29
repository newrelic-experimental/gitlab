# Minimal otel.py stub for local testing


def create_resource_attributes(*args, **kwargs):
    return {}


def get_logger(*args, **kwargs):
    class DummyLogger:
        def info(self, msg):
            pass

        def error(self, msg):
            pass

    return DummyLogger()


def get_tracer(*args, **kwargs):
    class DummyTracer:
        def start_span(self, *args, **kwargs):
            class DummySpan:
                def set_attributes(self, attrs):
                    pass

                def set_status(self, status):
                    pass

                def end(self, end_time=None):
                    pass

            return DummySpan()

    return DummyTracer()
