from __future__ import annotations

import logging
import time

from fastapi import APIRouter, Response, status
from pydantic import BaseModel

from app.core.observability.metrics import InMemoryMetricsBackend, get_metrics
from app.infrastructure.database import check_database_connection, engine

logger = logging.getLogger(__name__)

router = APIRouter(tags=["observability"])


class ComponentStatus(BaseModel):
    status: str
    latency_ms: float | None = None
    error: str | None = None


class HealthResponse(BaseModel):
    status: str
    version: str = "0.1.0"
    environment: str = ""
    uptime_seconds: float = 0.0
    components: dict[str, ComponentStatus] = {}


class ReadyResponse(BaseModel):
    status: str
    components: dict[str, ComponentStatus] = {}


class MetricsResponse(BaseModel):
    counters: dict[str, float] = {}
    histograms: dict[str, dict[str, float]] = {}
    gauges: dict[str, float] = {}


_start_time: float = time.monotonic()


@router.get("/health", response_model=HealthResponse)
async def health() -> HealthResponse:
    from app.config import settings

    uptime = time.monotonic() - _start_time

    db_ok, db_latency = await _check_db()

    components: dict[str, ComponentStatus] = {
        "database": ComponentStatus(
            status="healthy" if db_ok else "unhealthy",
            latency_ms=db_latency,
            error=None if db_ok else "database unreachable",
        ),
    }

    overall = "healthy"
    if any(c.status != "healthy" for c in components.values()):
        overall = "degraded"

    return HealthResponse(
        status=overall,
        environment=settings.environment,
        uptime_seconds=uptime,
        components=components,
    )


@router.get("/ready", response_model=ReadyResponse)
async def ready() -> Response:
    db_ok, db_latency = await _check_db()

    db_status = ComponentStatus(
        status="ready" if db_ok else "not ready",
        latency_ms=db_latency,
        error=None if db_ok else "database unreachable",
    )

    if not db_ok:
        return Response(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content=ReadyResponse(
                status="not ready",
                components={"database": db_status},
            ).model_dump_json(),
            media_type="application/json",
        )

    return Response(
        content=ReadyResponse(
            status="ready",
            components={"database": db_status},
        ).model_dump_json(),
        media_type="application/json",
    )


@router.get("/metrics", response_model=MetricsResponse)
async def metrics() -> MetricsResponse:
    backend = get_metrics()
    if isinstance(backend, InMemoryMetricsBackend):
        snap = backend.snapshot()
        return MetricsResponse(
            counters=snap["counters"],
            histograms=snap["histograms"],
            gauges=snap["gauges"],
        )
    return MetricsResponse()


async def _check_db() -> tuple[bool, float | None]:
    start = time.monotonic()
    try:
        ok = await check_database_connection()
        latency = (time.monotonic() - start) * 1000
        return ok, round(latency, 2)
    except Exception as exc:
        latency = (time.monotonic() - start) * 1000
        logger.warning("Database health check failed: %s", exc)
        return False, round(latency, 2)
