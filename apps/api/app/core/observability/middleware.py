from __future__ import annotations

import time
import uuid
from collections.abc import Awaitable, Callable
from contextvars import ContextVar, Token
from typing import Any

from fastapi import FastAPI, Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from app.core.observability.metrics import get_metrics

_REQUEST_CONTEXT: ContextVar[dict[str, Any] | None] = ContextVar(
    "request_context", default=None
)


def current_request_context() -> dict[str, Any] | None:
    return _REQUEST_CONTEXT.get()


def _generate_id() -> str:
    return uuid.uuid4().hex[:16]


class ObservabilityMiddleware(BaseHTTPMiddleware):
    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = request.headers.get("X-Request-ID") or _generate_id()
        correlation_id = request.headers.get("X-Correlation-ID") or _generate_id()

        ctx = {
            "request_id": request_id,
            "correlation_id": correlation_id,
        }
        token: Token = _REQUEST_CONTEXT.set(ctx)
        request.state.request_id = request_id
        request.state.correlation_id = correlation_id

        start = time.monotonic()
        status_code = 500

        try:
            response: Response = await call_next(request)
            status_code = response.status_code
            response.headers["X-Request-ID"] = request_id
            response.headers["X-Correlation-ID"] = correlation_id
            return response
        finally:
            elapsed_ms = (time.monotonic() - start) * 1000
            _REQUEST_CONTEXT.reset(token)

            tags: dict[str, str] = {
                "method": request.method,
                "path": request.url.path,
                "status": str(status_code),
            }
            route = request.scope.get("route")
            if route is not None:
                tags["route"] = route.path

            metrics = get_metrics()
            metrics.histogram(
                "http_request_duration_ms",
                elapsed_ms,
                tags=tags,
            )
            metrics.counter("http_requests_total", tags=tags)


def register_observability_middleware(app: FastAPI) -> None:
    app.add_middleware(ObservabilityMiddleware)
