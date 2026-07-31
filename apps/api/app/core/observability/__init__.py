from app.core.observability.logging import JSONFormatter, configure_json_logging
from app.core.observability.errors import (
    ErrorTracker,
    LoggingErrorTracker,
    NoOpErrorTracker,
    capture_exception,
    capture_message,
    get_error_tracker,
    set_error_tracker,
)
from app.core.observability.metrics import (
    InMemoryMetricsBackend,
    LoggingMetricsBackend,
    MetricsBackend,
    get_metrics,
    set_metrics_backend,
)
from app.core.observability.middleware import (
    ObservabilityMiddleware,
    current_request_context,
    register_observability_middleware,
)
from app.core.observability.otel import (
    instrument_fastapi,
    instrument_sqlalchemy,
    is_otel_available,
    setup_opentelemetry,
)
from app.core.observability.routes import router as observability_router

__all__ = [
    "JSONFormatter",
    "configure_json_logging",
    "ErrorTracker",
    "LoggingErrorTracker",
    "NoOpErrorTracker",
    "capture_exception",
    "capture_message",
    "get_error_tracker",
    "set_error_tracker",
    "InMemoryMetricsBackend",
    "LoggingMetricsBackend",
    "MetricsBackend",
    "get_metrics",
    "set_metrics_backend",
    "ObservabilityMiddleware",
    "current_request_context",
    "register_observability_middleware",
    "instrument_fastapi",
    "instrument_sqlalchemy",
    "is_otel_available",
    "setup_opentelemetry",
    "observability_router",
]
