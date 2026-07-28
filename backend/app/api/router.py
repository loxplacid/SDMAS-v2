from __future__ import annotations

from fastapi import APIRouter
from pydantic import BaseModel

from app.core.config import settings

router = APIRouter()


class RootResponse(BaseModel):
    application: str
    environment: str
    status: str
    version: str


class HealthResponse(BaseModel):
    status: str


@router.get("/", response_model=RootResponse)
async def root():
    return RootResponse(
        application=settings.app_name,
        environment=settings.environment,
        status="running",
        version="0.1.0",
    )


@router.get("/health", response_model=HealthResponse)
async def health():
    return HealthResponse(status="healthy")
