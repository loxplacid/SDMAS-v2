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
from app.domains.events.outbox import (  # noqa: F401
    OutboxEvent,
)
from app.temporal.models import (  # noqa: F401
    TxnLog,
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
    #
    # The default-deny tenant architecture means the admin must belong
    # to a real campus: we seed an Institution + two Campuses and make
    # the admin a default member of Campus A (id=1) so tenant-scoped
    # endpoints resolve to a concrete school context.
    from sqlalchemy import select as _select
    from app.domains.auth.models import User, UserSchoolMembership
    from app.domains.auth.security import hash_password
    from app.domains.institution.models import Institution, Campus

    async with factory() as seed_session:
        institution = Institution(name="Test District", code="TST-DIST")
        seed_session.add(institution)
        await seed_session.flush()
        campus_a = Campus(
            institution_id=institution.id, name="Campus A", code="CMP-A", status="active"
        )
        campus_b = Campus(
            institution_id=institution.id, name="Campus B", code="CMP-B", status="active"
        )
        seed_session.add_all([campus_a, campus_b])
        await seed_session.flush()

        existing = await seed_session.execute(
            _select(User).where(User.username == "admin")
        )
        admin = existing.scalar_one_or_none()
        if admin is None:
            admin = User(
                username="admin",
                email="admin@test.local",
                password_hash=hash_password("AdminPass123!"),
                display_name="Test Admin",
                role="admin",
                campus_id=campus_a.id,
                is_active=True,
            )
            seed_session.add(admin)
            await seed_session.flush()
        admin.campus_id = campus_a.id
        member = UserSchoolMembership(
            user_id=admin.id,
            campus_id=campus_a.id,
            role="admin",
            is_default=True,
            is_active=True,
        )
        seed_session.add(member)
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


@pytest_asyncio.fixture
async def admin_headers(api_client: AsyncClient) -> dict:
    """Authenticated ``Authorization`` headers for the seeded admin user.

    The admin is a default member of Campus A (id=1), so any tenant-
    scoped endpoint called with these headers resolves to campus 1.
    """
    resp = await api_client.post(
        "/auth/login",
        json={"login": "admin", "password": "AdminPass123!"},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest_asyncio.fixture
async def auth_client(api_client: AsyncClient) -> AsyncClient:
    """``api_client`` with the admin bearer token pre-attached.

    Every request sent through this client is authenticated as the
    seeded admin (campus 1), which satisfies the global auth gate and
    ``require_tenant_context`` on router endpoints.
    """
    resp = await api_client.post(
        "/auth/login",
        json={"login": "admin", "password": "AdminPass123!"},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    api_client.headers["Authorization"] = f"Bearer {token}"
    return api_client


@pytest.fixture(autouse=True)
def _reset_login_rate_limiter():
    """Reset the shared rate limiters before every test.

    The ``_login_limiter`` in ``auth/router.py`` and the app-wide
    ``rate_limit`` decorator limiter are module-level singletons keyed by
    client IP; every ``api_client``/``client`` request shares the same test
    IP, so without a reset the per-endpoint windows would 429 later tests
    in a full suite run.
    """
    from app.domains.auth.router import _login_limiter
    from app.core.security.rate_limiter import _global_limiter

    _login_limiter.reset()
    _global_limiter.reset()
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