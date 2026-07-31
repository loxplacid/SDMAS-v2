from __future__ import annotations

import logging
from typing import Any

logger = logging.getLogger(__name__)

_OTEL_AVAILABLE: bool = False


def is_otel_available() -> bool:
    return _OTEL_AVAILABLE


def setup_opentelemetry(
    app_name: str = "sdmas-api",
    endpoint: str | None = None,
    *,
    service_version: str = "0.1.0",
    environment: str = "development",
    **kwargs: Any,
) -> bool:
    global _OTEL_AVAILABLE

    try:
        from opentelemetry import trace
        from opentelemetry.exporter.otlp.proto.http.trace_exporter import (
            OTLPSpanExporter,
        )
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from opentelemetry.sdk.resources import Resource
        from opentelemetry.sdk.trace import TracerProvider
        from opentelemetry.sdk.trace.export import BatchSpanProcessor

        from app.core.observability.metrics import InMemoryMetricsBackend, get_metrics, set_metrics_backend
        from app.core.observability.errors import LoggingErrorTracker, set_error_tracker
        from app.infrastructure.database import engine

        resource = Resource.create(
            attributes={
                "service.name": app_name,
                "service.version": service_version,
                "deployment.environment": environment,
            }
        )
        provider = TracerProvider(resource=resource)

        if endpoint:
            exporter = OTLPSpanExporter(endpoint=endpoint)
            processor = BatchSpanProcessor(exporter)
            provider.add_span_processor(processor)
            logger.info("OTLP span exporter configured: %s", endpoint)
        else:
            logger.info(
                "No OTLP endpoint configured — spans will be processed "
                "in-process but not exported. Set OTEL_EXPORTER_OTLP_ENDPOINT "
                "to enable remote export."
            )

        trace.set_tracer_provider(provider)
        _OTEL_AVAILABLE = True

        if isinstance(get_metrics(), InMemoryMetricsBackend):
            from app.core.observability.metrics import LoggingMetricsBackend
            set_metrics_backend(LoggingMetricsBackend())

        if isinstance(
            __import__("app.core.observability.errors", fromlist=["get_error_tracker"]).get_error_tracker(),
            __import__("app.core.observability.errors", fromlist=["NoOpErrorTracker"]).NoOpErrorTracker,
        ):
            set_error_tracker(LoggingErrorTracker())

        return True

    except ImportError as exc:
        logger.warning(
            "OpenTelemetry packages not installed — %s. "
            "Install with: pip install opentelemetry-api opentelemetry-sdk "
            "opentelemetry-instrumentation-fastapi opentelemetry-instrumentation-sqlalchemy "
            "opentelemetry-exporter-otlp-proto-http",
            exc,
        )
        _OTEL_AVAILABLE = False
        return False


def instrument_fastapi(app: Any) -> None:
    if not _OTEL_AVAILABLE:
        logger.warning("OpenTelemetry not available — skipping FastAPI instrumentation")
        return
    try:
        from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

        FastAPIInstrumentor.instrument_app(app)
        logger.info("FastAPI instrumented with OpenTelemetry")
    except Exception as exc:
        logger.warning("Failed to instrument FastAPI: %s", exc)


def instrument_sqlalchemy() -> None:
    if not _OTEL_AVAILABLE:
        return
    try:
        from opentelemetry.instrumentation.sqlalchemy import SQLAlchemyInstrumentor
        from app.infrastructure.database import engine

        SQLAlchemyInstrumentor().instrument(engine=engine.sync_engine)
        logger.info("SQLAlchemy instrumented with OpenTelemetry")
    except Exception as exc:
        logger.warning("Failed to instrument SQLAlchemy: %s", exc)
