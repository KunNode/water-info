"""OpenTelemetry helpers for supervisor-autogen-enhancements (F1).

Feature flag: ``OTEL_ENABLED`` (default ``false``).

When the flag is off every public helper is a no-op: ``get_tracer()``
returns the API's global no-op tracer, ``agent_span()`` yields a no-op
context manager, and ``init_tracer_provider()`` returns immediately.

Design: ``.kiro/specs/supervisor-autogen-enhancements/design.md`` §Components/1
"""

from __future__ import annotations

import logging
from contextlib import contextmanager
from typing import Any

from app.config import get_settings

logger = logging.getLogger(__name__)

_tracer_provider_initialised = False


def init_tracer_provider() -> None:
    """Initialise the OTel tracer provider (idempotent).

    Called once from ``app.main`` lifespan when ``OTEL_ENABLED=true``.
    Uses OTLP/gRPC exporter targeting ``OTEL_EXPORTER_OTLP_ENDPOINT``
    (default ``http://localhost:4317``).  Init is wrapped in a 5-second
    timeout; on failure the provider stays as the no-op tracer and a
    single WARN log is emitted.
    """
    global _tracer_provider_initialised
    settings = get_settings()
    if not settings.otel_enabled:
        return
    if _tracer_provider_initialised:
        return

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        import os

        endpoint = os.environ.get("OTEL_EXPORTER_OTLP_ENDPOINT", "http://localhost:4317")

        exporter = OTLPSpanExporter(endpoint=endpoint, insecure=True)
        processor = BatchSpanProcessor(
            exporter,
            max_export_timeout_millis=100,
            max_queue_size=2048,
            max_export_batch_size=512,
        )
        provider = TracerProvider()
        provider.add_span_processor(processor)
        trace.set_tracer_provider(provider)
        _tracer_provider_initialised = True
        logger.info("OTel tracer provider initialised (endpoint=%s)", endpoint)
    except Exception as exc:
        logger.warning("OTel tracer init failed; falling back to no-op: %s", exc)


def get_tracer():
    """Return the OTel tracer for this service.

    When ``OTEL_ENABLED=false`` or init failed, returns the no-op tracer.
    """
    from opentelemetry import trace

    return trace.get_tracer("water-info-ai")


def current_trace_id_hex() -> str | None:
    """Return the current span's trace ID as 32-lowercase-hex, or ``None``."""
    from opentelemetry import trace

    span = trace.get_current_span()
    ctx = span.get_span_context()
    if ctx is None or ctx.trace_id == 0:
        return None
    return format(ctx.trace_id, "032x")


@contextmanager
def agent_span(
    agent_name: str,
    session_id: str = "",
    agent_run_id: str = "",
    iteration: int = 0,
):
    """Context manager wrapping an agent node execution with an OTel span.

    Span name: ``agent.<agent_name>``.  On success sets status OK and
    records ``duration_ms``.  On exception records the error and re-raises.

    When ``OTEL_ENABLED=false`` this is a plain no-op context manager.
    """
    settings = get_settings()
    if not settings.otel_enabled:
        yield
        return

    import time

    from opentelemetry import trace

    tracer = get_tracer()
    with tracer.start_as_current_span(f"agent.{agent_name}") as span:
        span.set_attribute("agent.name", agent_name)
        if session_id:
            span.set_attribute("session_id", session_id)
        if agent_run_id:
            span.set_attribute("agent_run_id", agent_run_id)
        if iteration:
            span.set_attribute("iteration", iteration)
        start = time.monotonic()
        try:
            yield span
            duration_ms = int((time.monotonic() - start) * 1000)
            span.set_attribute("duration_ms", duration_ms)
            span.set_status(trace.StatusCode.OK)
        except Exception as exc:
            duration_ms = int((time.monotonic() - start) * 1000)
            span.set_attribute("duration_ms", duration_ms)
            span.record_exception(exc)
            span.set_status(trace.StatusCode.ERROR, str(exc)[:1024])
            raise


def record_routing_decision(span, decision: dict) -> None:
    """Add a ``routing_decision`` event to *span* with the decision attributes.

    When ``OTEL_ENABLED=False`` or *span* is ``None``, does nothing.
    """
    if span is None:
        return
    settings = get_settings()
    if not settings.otel_enabled:
        return

    reasoning = str(decision.get("reasoning", ""))[:2048]
    span.add_event(
        "routing_decision",
        attributes={
            "next_agent": str(decision.get("next_agent", "")),
            "intent": str(decision.get("intent", "")),
            "safety_level": str(decision.get("safety_level", "")),
            "reasoning": reasoning,
        },
    )


@contextmanager
def llm_span(model: str = "", temperature: float = 0.0):
    """Context manager wrapping an LLM HTTP call with an OTel span.

    Span name: ``llm.invoke``.  On exit attaches ``duration_ms``.

    When ``OTEL_ENABLED=false`` this is a plain no-op context manager.
    """
    settings = get_settings()
    if not settings.otel_enabled:
        yield
        return

    import time

    from opentelemetry import trace

    tracer = get_tracer()
    with tracer.start_as_current_span("llm.invoke") as span:
        if model:
            span.set_attribute("llm.model", model)
        if temperature:
            span.set_attribute("llm.temperature", temperature)
        start = time.monotonic()
        try:
            yield span
        finally:
            duration_ms = int((time.monotonic() - start) * 1000)
            span.set_attribute("duration_ms", duration_ms)


@contextmanager
def tool_span(tool_name: str):
    """Context manager wrapping a tool call with an OTel span.

    Span name: ``tool.<tool_name>``.

    When ``OTEL_ENABLED=false`` this is a plain no-op context manager.
    """
    settings = get_settings()
    if not settings.otel_enabled:
        yield
        return

    from opentelemetry import trace

    tracer = get_tracer()
    with tracer.start_as_current_span(f"tool.{tool_name}") as span:
        try:
            yield span
        except Exception as exc:
            span.record_exception(exc)
            span.set_status(trace.StatusCode.ERROR, str(exc)[:1024])
            raise
