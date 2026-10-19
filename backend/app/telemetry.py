"""OpenTelemetry traces and metrics, and structured JSON logs, for the backend (product spec 7.2).

* Traces: one server span per request (route template as ``http.route``) with a child span per
  database statement. Metrics: the FastAPI instrumentation's ``http.server.request.duration``
  histogram, whose count gives request and error (5xx) rates per route template.
* Logs: one JSON object per line on stdout through one formatter. Every line inside a request
  carries the request's ``trace_id`` and ``span_id``. With ``GOOGLE_CLOUD_PROJECT`` set the lines
  also carry Cloud Logging's trace fields.
* Export over OTLP happens only when ``OTEL_EXPORTER_OTLP_ENDPOINT`` is set. Otherwise no exporter
  exists: no retries, no timeouts, no startup delay. Trace and span IDs still appear in the logs.
* Privacy (spec 7.2) is enforced here, not by configuration. Span attributes pass through
  ``ScrubbingSpanExporter``; metric attributes pass through an allow-list view; log lines have a
  fixed set of fields and the database URL is redacted from any text. Nothing that identifies a
  reader (client address, user agent, query string, cookies, body) is ever recorded.
"""

from __future__ import annotations

import json
import logging
import os
import re
import sys
import time
from collections.abc import Sequence
from datetime import UTC, datetime
from typing import Any, TextIO

# Opt in to the stable HTTP semantic conventions (http.route, http.response.status_code and
# http.server.request.duration in seconds). Must be set before the instrumentation is imported.
os.environ.setdefault("OTEL_SEMCONV_STABILITY_OPT_IN", "http")

from opentelemetry import trace
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
from opentelemetry.instrumentation.psycopg import PsycopgInstrumentor
from opentelemetry.propagate import set_global_textmap
from opentelemetry.sdk._logs import LoggerProvider, LoggingHandler
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor, LogExporter
from opentelemetry.sdk.metrics import MeterProvider
from opentelemetry.sdk.metrics.export import MetricReader, PeriodicExportingMetricReader
from opentelemetry.sdk.metrics.view import View
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import ReadableSpan, TracerProvider
from opentelemetry.sdk.trace.export import (
    BatchSpanProcessor,
    SimpleSpanProcessor,
    SpanExporter,
    SpanExportResult,
)
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

SERVICE_NAME = "cfe-backend"
REDACTED = "[redacted]"

# The healthcheck (every few seconds) is not worth a trace, a metric point or a log line.
EXCLUDED_URLS = r"^https?://[^/]+/api/health(\?.*)?$"
UNTRACED_PATHS = ("/api/health",)

# Span attributes that can identify a reader or reveal where the database is. Matched by exact
# key or by prefix.
FORBIDDEN_ATTRIBUTE_KEYS = frozenset(
    {
        "url.full", "url.path", "url.query", "http.url", "http.target", "http.user_agent",
        "http.client_ip", "http.host", "http.request.header.user-agent",
        "http.request.header.cookie", "http.request.header.x-forwarded-for",
        "db.connection_string", "db.user", "server.address", "server.port",
    }
)  # fmt: skip
FORBIDDEN_ATTRIBUTE_PREFIXES = (
    "client.", "net.peer.", "net.sock.", "network.peer.", "network.local.", "user_agent.",
    "http.request.header.", "http.response.header.",
)  # fmt: skip

# The only metric attributes that are ever recorded.
METRIC_ATTRIBUTE_KEYS = frozenset(
    {"http.route", "http.request.method", "http.response.status_code"}
)

METRIC_EXPORT_INTERVAL_MS = 10_000


# --------------------------------------------------------------------------- secrets


def _secret_values() -> list[str]:
    """The database URL and its password, if set: strings that must never be written out."""
    url = os.environ.get("DATABASE_URL", "")
    values = [url] if url else []
    match = re.match(r"^[\w+.-]+://[^:/@]*:([^@]+)@", url)
    if match:
        values.append(match.group(1))
    return sorted(values, key=len, reverse=True)


def redact(text: str) -> str:
    for secret in _secret_values():
        text = text.replace(secret, REDACTED)
    return text


# --------------------------------------------------------------------------- spans


def _forbidden(key: str) -> bool:
    return key in FORBIDDEN_ATTRIBUTE_KEYS or key.startswith(FORBIDDEN_ATTRIBUTE_PREFIXES)


def _clean_value(value: Any) -> Any:
    if isinstance(value, str):
        return redact(value)
    if isinstance(value, (list, tuple)):
        return type(value)(_clean_value(v) for v in value)
    return value


def scrub_attributes(attributes: Any) -> dict[str, Any]:
    return {k: _clean_value(v) for k, v in (attributes or {}).items() if not _forbidden(k)}


def scrub_span(span: ReadableSpan) -> ReadableSpan:
    events = []
    for event in span.events:
        events.append(
            type(event)(
                name=event.name,
                attributes=scrub_attributes(event.attributes),
                timestamp=event.timestamp,
            )
        )
    status = span.status
    if status.description:
        status = type(status)(status.status_code, redact(status.description))
    return ReadableSpan(
        name=span.name,
        context=span.context,
        parent=span.parent,
        resource=span.resource,
        attributes=scrub_attributes(span.attributes),
        events=events,
        links=span.links,
        kind=span.kind,
        status=status,
        start_time=span.start_time,
        end_time=span.end_time,
        instrumentation_scope=span.instrumentation_scope,
    )


class ScrubbingSpanExporter(SpanExporter):
    """Wraps an exporter so only scrubbed copies of finished spans reach it."""

    def __init__(self, inner: SpanExporter):
        self.inner = inner

    def export(self, spans: Sequence[ReadableSpan]) -> SpanExportResult:
        return self.inner.export([scrub_span(s) for s in spans])

    def shutdown(self) -> None:
        self.inner.shutdown()

    def force_flush(self, timeout_millis: int = 30000) -> bool:
        return self.inner.force_flush(timeout_millis)


# --------------------------------------------------------------------------- logs


def trace_ids() -> tuple[str | None, str | None]:
    ctx = trace.get_current_span().get_span_context()
    if not ctx.is_valid:
        return None, None
    return format(ctx.trace_id, "032x"), format(ctx.span_id, "016x")


class JsonFormatter(logging.Formatter):
    """One JSON object per record. Fields are fixed; arbitrary record attributes are not copied."""

    ACCESS_FIELDS = ("method", "route", "status", "duration_ms")

    def format(self, record: logging.LogRecord) -> str:
        trace_id, span_id = trace_ids()
        entry: dict[str, Any] = {
            "timestamp": datetime.fromtimestamp(record.created, UTC).isoformat(
                timespec="milliseconds"
            ),
            "severity": record.levelname,
            "message": redact(record.getMessage()),
            "logger": record.name,
            "trace_id": trace_id,
            "span_id": span_id,
        }
        for field in self.ACCESS_FIELDS:
            if hasattr(record, field):
                entry[field] = getattr(record, field)
        project = os.environ.get("GOOGLE_CLOUD_PROJECT")
        if project and trace_id:
            entry["logging.googleapis.com/trace"] = f"projects/{project}/traces/{trace_id}"
            entry["logging.googleapis.com/spanId"] = span_id
        if record.exc_info:
            entry["exception"] = redact(self.formatException(record.exc_info))
        return json.dumps(entry, ensure_ascii=False)


_STDOUT_HANDLER = "cfe-json-stdout"
_OTLP_HANDLER = "cfe-otlp-logs"


class _OtlpLogHandler(LoggingHandler):
    """Forward records to the OTel logger provider, except the SDK's own (which would loop)."""

    def emit(self, record: logging.LogRecord) -> None:
        if record.name.startswith("opentelemetry"):
            return
        # The message is redacted here; the SDK handler reads getMessage().
        record.msg, record.args = redact(record.getMessage()), None
        super().emit(record)


def configure_logging(
    stream: TextIO | None = None, logger_provider: LoggerProvider | None = None
) -> None:
    """Route every record, including uvicorn's, through the JSON formatter on stdout. Idempotent."""
    root = logging.getLogger()
    for handler in list(root.handlers):
        if handler.get_name() in (_STDOUT_HANDLER, _OTLP_HANDLER):
            root.removeHandler(handler)
    stdout = logging.StreamHandler(stream or sys.stdout)
    stdout.set_name(_STDOUT_HANDLER)
    stdout.setFormatter(JsonFormatter())
    root.addHandler(stdout)
    if logger_provider is not None:
        otlp = _OtlpLogHandler(level=logging.NOTSET, logger_provider=logger_provider)
        otlp.set_name(_OTLP_HANDLER)
        root.addHandler(otlp)
    root.setLevel(logging.INFO)
    # uvicorn installs its own non-JSON handlers on these; hand them to the root handler instead.
    for name in ("uvicorn", "uvicorn.error", "uvicorn.access"):
        logger = logging.getLogger(name)
        logger.handlers = []
        logger.propagate = True
    logging.getLogger("uvicorn.access").disabled = True


ACCESS_LOGGER = logging.getLogger("cfe.access")


class AccessLogMiddleware:
    """Pure ASGI middleware: one log line per request, with the route template, never the URL.

    It sits inside the OpenTelemetry middleware, so the line carries the request's trace ID.
    """

    def __init__(self, app):
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope.get("path") in UNTRACED_PATHS:
            await self.app(scope, receive, send)
            return
        status = 500
        started = time.perf_counter()

        async def send_wrapper(message):
            nonlocal status
            if message["type"] == "http.response.start":
                status = message["status"]
            await send(message)

        try:
            await self.app(scope, receive, send_wrapper)
        finally:
            route = scope.get("route")
            template = getattr(route, "path", None) or "unmatched"
            duration_ms = round((time.perf_counter() - started) * 1000, 1)
            method = scope.get("method", "")
            ACCESS_LOGGER.info(
                "%s %s %s %.1fms",
                method,
                template,
                status,
                duration_ms,
                extra={
                    "method": method,
                    "route": template,
                    "status": status,
                    "duration_ms": duration_ms,
                },
            )


# --------------------------------------------------------------------------- setup


def build_resource() -> Resource:
    return Resource.create({"service.name": SERVICE_NAME})


def setup(
    app: Any,
    *,
    span_exporters: Sequence[SpanExporter] = (),
    metric_readers: Sequence[MetricReader] = (),
    log_exporters: Sequence[LogExporter] = (),
    simple_processors: bool = False,
    log_stream: TextIO | None = None,
) -> None:
    """Instrument ``app``. Providers are per call and not set as process globals, so tests can
    call this repeatedly with in-memory exporters."""
    resource = build_resource()
    tracer_provider = TracerProvider(resource=resource)
    for exporter in span_exporters:
        scrubbed = ScrubbingSpanExporter(exporter)
        tracer_provider.add_span_processor(
            SimpleSpanProcessor(scrubbed) if simple_processors else BatchSpanProcessor(scrubbed)
        )
    meter_provider = MeterProvider(
        resource=resource,
        metric_readers=list(metric_readers),
        views=[View(instrument_name="*", attribute_keys=set(METRIC_ATTRIBUTE_KEYS))],
    )
    logger_provider = None
    if log_exporters:
        logger_provider = LoggerProvider(resource=resource)
        for exporter in log_exporters:
            logger_provider.add_log_record_processor(BatchLogRecordProcessor(exporter))

    set_global_textmap(TraceContextTextMapPropagator())  # W3C trace-context only

    # Added before instrumenting, so the OTel middleware wraps it and the line runs inside the span.
    if not getattr(app.state, "access_log_installed", False):
        app.add_middleware(AccessLogMiddleware)
        app.state.access_log_installed = True
    if getattr(app, "_is_instrumented_by_opentelemetry", False):
        FastAPIInstrumentor.uninstrument_app(app)
    FastAPIInstrumentor.instrument_app(
        app,
        tracer_provider=tracer_provider,
        meter_provider=meter_provider,
        excluded_urls=EXCLUDED_URLS,
        exclude_spans=["receive", "send"],
    )
    # psycopg (not SQLAlchemy) instrumentation: the locked SQLAlchemy 2.1 is outside the
    # SQLAlchemy instrumentation's supported range.
    if PsycopgInstrumentor().is_instrumented_by_opentelemetry:
        PsycopgInstrumentor().uninstrument()
    PsycopgInstrumentor().instrument(tracer_provider=tracer_provider, meter_provider=meter_provider)
    app.middleware_stack = None  # Starlette keeps a built stack; force a rebuild

    configure_logging(log_stream, logger_provider)
    app.state.telemetry = {
        "tracer_provider": tracer_provider,
        "meter_provider": meter_provider,
        "logger_provider": logger_provider,
    }


def setup_from_env(app: Any) -> None:
    """Production entry point: OTLP export only when OTEL_EXPORTER_OTLP_ENDPOINT is set."""
    span_exporters: list[SpanExporter] = []
    metric_readers: list[MetricReader] = []
    log_exporters: list[LogExporter] = []
    if os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "").strip():  # empty counts as unset
        from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
        from opentelemetry.exporter.otlp.proto.http.metric_exporter import OTLPMetricExporter
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter

        span_exporters.append(OTLPSpanExporter())
        metric_readers.append(
            PeriodicExportingMetricReader(
                OTLPMetricExporter(), export_interval_millis=METRIC_EXPORT_INTERVAL_MS
            )
        )
        log_exporters.append(OTLPLogExporter())
    setup(
        app,
        span_exporters=span_exporters,
        metric_readers=metric_readers,
        log_exporters=log_exporters,
    )
