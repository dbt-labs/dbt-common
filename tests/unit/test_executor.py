from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import SimpleSpanProcessor
from opentelemetry.sdk.trace.export.in_memory_span_exporter import InMemorySpanExporter
from dbt_common.utils.executor import executor
from dbt_common.context import set_invocation_context


class ThreadingType:
    def __init__(self, single_threaded):
        self.single_threaded = single_threaded


class TestConfig:
    def __init__(self, args, threads=1):
        self.args = args
        self.threads = threads


def test_multi_threaded_executor_opentelemetry_context_propagation():
    tracer_provider = TracerProvider(resource=Resource.get_empty())
    span_exporter = InMemorySpanExporter()
    trace.set_tracer_provider(tracer_provider)
    trace.get_tracer_provider().add_span_processor(SimpleSpanProcessor(span_exporter))
    tracer = trace.get_tracer("test.dbt.runner")
    set_invocation_context({})
    with tracer.start_as_current_span("test-span") as span:
        config = TestConfig(ThreadingType(single_threaded=False), threads=2)

        def func():
            return trace.get_current_span().get_span_context()

        with executor(config) as ex:
            future = ex.submit(func)
            span_context_in_thread = future.result()
            assert span.get_span_context().trace_id == span_context_in_thread.trace_id
            assert span.get_span_context().span_id == span_context_in_thread.span_id


# In single thread mode, it is executed on current thread. So no need to pass context explicitly
def test_single_threaded_executor_opentelemetry_context_propagation():
    tracer_provider = TracerProvider(resource=Resource.get_empty())
    span_exporter = InMemorySpanExporter()
    trace.set_tracer_provider(tracer_provider)
    trace.get_tracer_provider().add_span_processor(SimpleSpanProcessor(span_exporter))
    tracer = trace.get_tracer("test.dbt.runner")
    set_invocation_context({})
    with tracer.start_as_current_span("test-span") as span:
        config = TestConfig(ThreadingType(single_threaded=True))

        def func():
            return trace.get_current_span().get_span_context()

        with executor(config) as ex:
            future = ex.submit(func)
            span_context_in_thread = future.result()
            assert span.get_span_context().trace_id == span_context_in_thread.trace_id
            assert span.get_span_context().span_id == span_context_in_thread.span_id
