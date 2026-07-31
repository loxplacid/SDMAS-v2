from __future__ import annotations

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import router
from app.core.config import settings
from app.core.logging import LoggerFactory
from app.infrastructure.database import close_db


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncGenerator[None]:
    logger = LoggerFactory.create_logger(level=settings.log_level)
    logger.info(
        "Starting %s in %s mode",
        settings.app_name,
        settings.environment,
    )
    yield
    await close_db()
    logger.info("Application shutdown complete")


app = FastAPI(
    title=settings.app_name,
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(router)
