import os

from phoenix.otel import register
from openinference.instrumentation.langchain import LangChainInstrumentor


_TRACING_INITIALIZED = False

def setup_tracing_phoenix():
    global _TRACING_INITIALIZED

    if _TRACING_INITIALIZED:
        return

    if os.getenv("ENABLE_TRACING", "false").lower() != "true":
        return

    endpoint = os.getenv("PHOENIX_COLLECTOR_ENDPOINT", "http://phoenix:6006/v1/traces")
    project_name = os.getenv("PHOENIX_PROJECT_NAME", "EurecaChat")

    tracer_provider = register(
        endpoint=endpoint,
        protocol="http/protobuf",
        project_name=project_name,
        auto_instrument=False,
        batch=True
    )

    LangChainInstrumentor().instrument(tracer_provider=tracer_provider)

    _TRACING_INITIALIZED = True