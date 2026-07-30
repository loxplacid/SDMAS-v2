from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import AsyncGenerator as AsyncGeneratorType

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.infrastructure.database import Base, get_session

# Import all models so Base.metadata can resolve cross-module foreign keys
from app.domains.institution.models import (  # noqa: F401
    Institution, Campus, School, Department, Program, Branch, Semester,
)

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


@pytest_asyncio.fixture
async def db_session() -> AsyncGenerator[AsyncSession, None]:
    """Create a fresh in-memory SQLite database with all metadata per test."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with factory() as session:
        yield session

    await engine.dispose()


@pytest_asyncio.fixture
async def client() -> AsyncGenerator[AsyncClient, None]:
    """FastAPI test client bound to the application's live engine."""
    from app.main import app

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest_asyncio.fixture
async def api_client() -> AsyncGenerator[AsyncClient, None]:
    """FastAPI test client with in-memory SQLite and dependency overrides."""
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_session() -> AsyncGeneratorType[AsyncSession, None]:
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    from app.main import app

    app.dependency_overrides[get_session] = override_get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
    await engine.dispose()


# ---------------------------------------------------------------------------
# PostgreSQL integration test fixture (requires Docker + Testcontainers)
# ---------------------------------------------------------------------------

def _is_docker_available() -> bool:
    import shutil
    return shutil.which("docker") is not None


pytest_register_postgres = pytest.mark.skipif(
    not _is_docker_available(),
    reason="Docker is not available — PostgreSQL integration tests cannot run",
)


@pytest_asyncio.fixture
async def postgres_session() -> AsyncGenerator[AsyncSession, None]:
    """PostgreSQL session via Testcontainers.

    Requires Docker to be running.  Mark dependent tests with
    @pytest.mark.integration and they will be automatically skipped when
    Docker is unavailable.
    """
    try:
        from testcontainers.postgres import PostgresContainer
    except ImportError:
        pytest.skip("testcontainers package not installed")

    with PostgresContainer("postgres:16-alpine") as pg:
        url = pg.get_connection_url().replace("psycopg2", "asyncpg")
        engine = create_async_engine(url, echo=False)
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)

        factory = async_sessionmaker(
            engine, class_=AsyncSession, expire_on_commit=False
        )

        async with factory() as session:
            yield session

        await engine.dispose()