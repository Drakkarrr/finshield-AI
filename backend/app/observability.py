"""Logging, tracing and error tracking (S4.4).

- structlog JSON logs; stdlib `logging` is routed through the same formatter, so every line carries
  request_id / tenant_id / user_id from contextvars (bound by the request middleware).
- OpenTelemetry: one trace per request; the screening pipeline opens a span per stage via stage(),
  which also records pipeline_latency_seconds. Exported over OTLP when OTEL_EXPORTER_OTLP_ENDPOINT is
  set. Spans carry ids and decisions, never personal data.
- Sentry when SENTRY_DSN is set.
"""
from __future__ import annotations

import logging
import os
import sys
import time
from contextlib import contextmanager
from typing import Any, Iterator

import structlog
from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor

from app import metrics

SERVICE = "finshield-api"
tracer = trace.get_tracer("finshield")
_configured = False


def configure(service: str = SERVICE) -> None:
    global _configured
    if _configured:
        return
    _configured = True
    shared: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.CallsiteParameterAdder({structlog.processors.CallsiteParameter.MODULE}),
    ]
    structlog.configure(
        processors=[*shared, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared,
        processors=[structlog.stdlib.ProcessorFormatter.remove_processors_meta,
                    lambda _l, _m, ev: {**ev, "service": service},
                    structlog.processors.JSONRenderer()]))
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(logging.DEBUG if os.getenv("DEBUG") == "true" else logging.INFO)

    provider = TracerProvider(resource=Resource.create({"service.name": service}))
    if os.getenv("OTEL_EXPORTER_OTLP_ENDPOINT"):
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        provider.add_span_processor(BatchSpanProcessor(OTLPSpanExporter()))
    trace.set_tracer_provider(provider)

    dsn = os.getenv("SENTRY_DSN")
    if dsn:
        import sentry_sdk

        sentry_sdk.init(dsn=dsn, environment=os.getenv("APP_ENV", "production"), send_default_pii=False,
                        traces_sample_rate=0.0)


@contextmanager
def stage(name: str, **attributes) -> Iterator[trace.Span]:
    """A pipeline stage: one span plus a pipeline_latency_seconds observation."""
    start = time.perf_counter()
    with tracer.start_as_current_span(f"screening.{name}", attributes=attributes) as span:
        try:
            yield span
        finally:
            metrics.PIPELINE_LATENCY.labels(stage=name).observe(time.perf_counter() - start)


def capture_exception(exc: BaseException) -> None:
    metrics.UNHANDLED_ERRORS.inc()
    if os.getenv("SENTRY_DSN"):
        import sentry_sdk

        sentry_sdk.capture_exception(exc)
