# Copyright 2026 DANG NT (dangnt.vn@gmail.com)
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
#
# Description: Observability bootstrap — structured JSON logging via
#              structlog with rotating file handlers, plus an OpenTelemetry
#              tracer for span-based tracing (intent -> agent -> tool ->
#              result, ARCH-001 §7). Reused verbatim from rag-health
#              (ADR-0021), only the OTel service.name tag was renamed.
###############################################################################

import logging
import logging.handlers
import os
from contextlib import contextmanager

import structlog
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor, ConsoleSpanExporter

from common.config import settings


def _configure_structlog() -> None:
    """Wire structlog to emit ISO-timestamped JSON log records.

    Sets up a shared processor chain used by both structlog-native loggers and
    any stdlib ``logging`` calls that pass through (e.g. from third-party libs).
    Two rotating file handlers are attached:

    - ``app.log``   — INFO and above, max 10 MB, 5 backups.
    - ``error.log`` — ERROR and above, max 10 MB, 5 backups.

    A stdout handler is also registered so container log drivers (e.g. Docker,
    Kubernetes) can capture structured output without reading files.
    """
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
    ]

    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        processor=structlog.processors.JSONRenderer(),
        foreign_pre_chain=shared_processors,
    )

    os.makedirs(settings.log_path, exist_ok=True)

    app_handler = logging.handlers.RotatingFileHandler(
        os.path.join(settings.log_path, "app.log"),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    app_handler.setLevel(logging.INFO)
    app_handler.setFormatter(formatter)

    error_handler = logging.handlers.RotatingFileHandler(
        os.path.join(settings.log_path, "error.log"),
        maxBytes=10 * 1024 * 1024,
        backupCount=5,
        encoding="utf-8",
    )
    error_handler.setLevel(logging.ERROR)
    error_handler.setFormatter(formatter)

    stdout_handler = logging.StreamHandler()
    stdout_handler.setFormatter(formatter)

    log_level = getattr(logging, settings.log_level, logging.INFO)
    root = logging.getLogger()
    root.setLevel(log_level)
    root.addHandler(stdout_handler)
    root.addHandler(app_handler)
    root.addHandler(error_handler)


def _configure_otel() -> None:
    """Bootstrap the OpenTelemetry SDK with a console exporter.

    Registers a ``TracerProvider`` tagged with ``service.name=ai-clinic-agent``
    and attaches a ``BatchSpanProcessor`` that writes spans to stdout. In a
    production deployment, swap ``ConsoleSpanExporter`` for an OTLP exporter
    (e.g. Jaeger, Tempo, Honeycomb) by adding the appropriate SDK exporter
    package and updating this function.
    """
    resource = Resource.create({"service.name": "ai-clinic-agent"})
    provider = TracerProvider(resource=resource)
    provider.add_span_processor(BatchSpanProcessor(ConsoleSpanExporter()))
    trace.set_tracer_provider(provider)


# Run configuration eagerly at import time so any module that imports
# get_logger() benefits from the full logging pipeline immediately.
_configure_structlog()
_configure_otel()

_tracer = trace.get_tracer("ai-clinic-agent")


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a structlog BoundLogger for the given module name.

    Args:
        name: Typically ``__name__`` of the calling module. Used as the
              ``logger`` field in JSON log output for easy filtering.

    Returns:
        structlog.stdlib.BoundLogger: A context-bound structured logger.
    """
    return structlog.get_logger(name)


@contextmanager
def create_span(name: str):
    """Context manager that wraps a code block in an OpenTelemetry span.

    Useful for marking meaningful units of work (embedding, Qdrant search,
    LLM generation) without invasively instrumenting every function.

    Args:
        name: The span name as it will appear in the trace backend.

    Yields:
        opentelemetry.trace.Span: The active span for the duration of the block.

    Example::

        with create_span("qdrant_search") as span:
            span.set_attribute("collection", settings.qdrant_collection)
            results = client.query_points(...)
    """
    with _tracer.start_as_current_span(name) as span:
        yield span
