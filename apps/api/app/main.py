from __future__ import annotations

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.config import settings
from app.core.error_handlers import (
    auth_error_handler,
    conflict_handler,
    forbidden_handler,
    not_found_handler,
    validation_handler,
)
from app.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ConflictError,
    NotFoundError,
    ValidationError,
)
from app.domains.academic.router import router as academic_router
from app.domains.attendance.router import router as attendance_router
from app.domains.auth.router import router as auth_router
from app.domains.auth.admin_router import router as admin_router
from app.domains.fees.router import router as fees_router
from app.domains.analytics.router import router as analytics_router
from app.domains.notifications.router import router as notifications_router
from app.domains.reports.router import router as reports_router
from app.domains.student.router import router as student_router
from app.infrastructure.database import check_database_connection, close_db

logger = logging.getLogger(__name__)


def _configure_logging() -> None:
    logging.basicConfig(
        level=getattr(logging, settings.log_level.upper(), logging.INFO),
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


_configure_logging()


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None, None]:
    logger.info(
        "Starting SDMAS API",
        extra={"environment": settings.environment, "version": "0.1.0"},
    )
    yield
    logger.info("Shutting down SDMAS API — closing database connections")
    await close_db()


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

app.add_exception_handler(NotFoundError, not_found_handler)
app.add_exception_handler(ConflictError, conflict_handler)
app.add_exception_handler(ValidationError, validation_handler)
app.add_exception_handler(AuthenticationError, auth_error_handler)
app.add_exception_handler(AuthorizationError, forbidden_handler)

app.include_router(auth_router)
app.include_router(admin_router)
app.include_router(student_router)
app.include_router(academic_router)
app.include_router(attendance_router)
app.include_router(fees_router)
app.include_router(notifications_router)
app.include_router(analytics_router)
app.include_router(reports_router)


class HealthResponse(BaseModel):
    status: str


class ReadyResponse(BaseModel):
    status: str
    database: str


@app.get("/health")
async def health() -> HealthResponse:
    return HealthResponse(status="healthy")


@app.get("/ready")
async def ready() -> Response:
    db_ok = await check_database_connection()
    if not db_ok:
        logger.warning("Readiness check failed — database unavailable")
        return JSONResponse(
            content={"status": "not ready", "database": "unavailable"},
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
    logger.debug("Readiness check passed — database connected")
    return JSONResponse(content={"status": "ready", "database": "connected"})