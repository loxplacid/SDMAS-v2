from __future__ import annotations

from collections.abc import AsyncGenerator

from sqlalchemy import NullPool, text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)
from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass


def create_engine_and_factory(
    database_url: str,
    echo: bool = False,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    engine = create_async_engine(
        database_url,
        echo=echo,
        poolclass=NullPool,
    )
    factory = async_sessionmaker(
        engine,
        class_=AsyncSession,
        expire_on_commit=False,
    )
    return engine, factory


from app.config import settings  # noqa: E402

engine, async_session_factory = create_engine_and_factory(
    database_url=str(settings.database_url),
    echo=settings.database_echo if settings.database_echo is not None else settings.debug,
)


async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with async_session_factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise


async def check_database_connection(
    engine_override: AsyncEngine | None = None,
) -> bool:
    target = engine_override or engine
    try:
        async with target.connect() as conn:
            await conn.execute(text("SELECT 1"))
        return True
    except Exception:
        return False


async def close_db() -> None:
    await engine.dispose()