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
from app.domains.auth.models import (  # noqa: F401
    User,
)
from app.domains.notifications.models import (  # noqa: F401
    Notification, DeviceToken,
)
from app.domains.notifications.preferences import (  # noqa: F401
    NotificationPreference,
)
from app.domains.audit.models import (  # noqa: F401
    AuditLog,
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
    # Import the app first so every domain model is registered with
    # Base.metadata before create_all runs — this makes table creation
    # order-independent regardless of which test file runs first.
    from app.main import app

    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    # Seed a default admin so permission-gated endpoints (e.g.
    # DELETE /students requiring students.delete) can be exercised
    # end-to-end through the API.
    from sqlalchemy import select as _select
    from app.domains.auth.models import User
    from app.domains.auth.security import hash_password

    async with factory() as seed_session:
        existing = await seed_session.execute(
            _select(User).where(User.username == "admin")
        )
        if existing.scalar_one_or_none() is None:
            seed_session.add(
                User(
                    username="admin",
                    email="admin@test.local",
                    password_hash=hash_password("AdminPass123!"),
                    display_name="Test Admin",
                    role="admin",
                    is_active=True,
                )
            )
            await seed_session.commit()

    async def override_get_session() -> AsyncGeneratorType[AsyncSession, None]:
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_session] = override_get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    app.dependency_overrides.clear()
    await engine.dispose()


@pytest.fixture(autouse=True)
def _reset_login_rate_limiter():
    """Reset the shared login rate limiter before every test.

    The ``_login_limiter`` in ``auth/router.py`` is a module-level singleton
    keyed by client IP; every ``api_client``/``client`` request shares the
    same test IP, so without a reset the 5-logins/60s window would 429 later
    tests in a full suite run.
    """
    from app.domains.auth.router import _login_limiter

    _login_limiter.reset()
    yield


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