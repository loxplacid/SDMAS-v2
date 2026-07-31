from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import Settings, settings
from app.core.logging import LoggerFactory, get_logger
from app.infrastructure.database import async_session_factory


async def get_settings() -> Settings:
    return settings


async def get_db_session() -> AsyncGenerator[AsyncSession]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


def get_logger_instance(name: str = "sdmas"):
    return get_logger(name)
