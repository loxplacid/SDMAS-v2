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
    *,
    pool_size: int | None = None,
    max_overflow: int | None = None,
) -> tuple[AsyncEngine, async_sessionmaker[AsyncSession]]:
    """Create the async engine + session factory.

    - SQLite uses ``NullPool`` (each connection is a file/``:memory:``
      handle — pooling adds nothing and breaks ``:memory:`` semantics).
    - PostgreSQL uses the default async queue pool with configurable
      size so a handful of workers don't open a fresh connection per
      request (a real load hazard at production concurrency).
    """
    if database_url.startswith("sqlite"):
        engine = create_async_engine(
            database_url,
            echo=echo,
            poolclass=NullPool,
        )
    else:
        # Pass pool_size/max_overflow only when the caller supplied them —
        # SQLAlchemy raises if it receives explicit None (e.g. the seed
        # script calling without pool kwargs); omitted kwargs fall back to
        # the driver's own defaults.
        pool_kwargs: dict[str, int] = {}
        if pool_size is not None:
            pool_kwargs["pool_size"] = pool_size
        if max_overflow is not None:
            pool_kwargs["max_overflow"] = max_overflow
        engine = create_async_engine(database_url, echo=echo, **pool_kwargs)
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
    pool_size=settings.db_pool_size,
    max_overflow=settings.db_pool_max_overflow,
)

# ---------------------------------------------------------------------------
# Overridable session factory for tests (e.g. audit middleware integration)
# ---------------------------------------------------------------------------

_async_session_factory_override: async_sessionmaker[AsyncSession] | None = None


def get_async_session_factory() -> async_sessionmaker[AsyncSession]:
    """Return the active async session factory.

    Tests can call ``override_async_session_factory()`` to redirect
    database writes made by code that imports this function (e.g.
    the audit middleware) to an in-memory SQLite database.
    """
    if _async_session_factory_override is not None:
        return _async_session_factory_override
    return async_session_factory


def override_async_session_factory(
    factory: async_sessionmaker[AsyncSession] | None,
) -> None:
    """Set or clear the override for the global session factory.

    Pass ``None`` to restore the original factory.
    """
    global _async_session_factory_override
    _async_session_factory_override = factory


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