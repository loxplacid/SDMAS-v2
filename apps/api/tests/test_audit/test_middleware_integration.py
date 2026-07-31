"""Integration tests for the AuditMiddleware.

Verifies that mutating HTTP requests (POST, PATCH, PUT, DELETE) automatically
create audit log entries, while GET requests and skip-listed paths do not.
"""

from __future__ import annotations

import json
import asyncio
import sys
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.domains.audit.models import AuditLog
from app.domains.audit.middleware import (
    _resource_type_from_path,
    _should_audit,
)
from app.infrastructure.database import Base, get_session

# Use URI-based shared in-memory SQLite so that all connections
# (main request, audit middleware, test queries) see the SAME database.
# Without ``cache=shared`` each connection gets its own :memory: database.
TEST_DATABASE_URL = "sqlite+aiosqlite:///file::memory:?cache=shared&uri=true"


# ======================================================================
# Debug helpers
# ======================================================================


def _debug(msg: str) -> None:
    print(f"  [DEBUG] {msg}", file=sys.stderr, flush=True)


# ======================================================================
# Shared fixture
# ======================================================================


@pytest_asyncio.fixture
async def audit_client() -> AsyncGenerator[tuple[AsyncClient, async_sessionmaker], None]:
    """Return ``(httpx.AsyncClient, async_sessionmaker)`` where the audit
    middleware writes to the same in-memory SQLite as the app.

    The fixture:

    1. Imports the app first (which registers all models in Base.metadata).
    2. Creates an in-memory engine with ALL tables (including audit_logs).
    3. Overrides ``get_session`` + ``async_session_factory`` so both the
       app and the audit middleware write to the same in-memory database.
    4. Disables the 50ms latency gate so fast test requests are not skipped.
    """
    # ── Import app first to register ALL models in Base.metadata ──────
    from app.main import app

    # ── engine & factory ──────────────────────────────────────────────
    engine = create_async_engine(TEST_DATABASE_URL, echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Verify audit_logs table exists
    async with engine.begin() as conn:
        result = await conn.run_sync(
            lambda sync_conn: sync_conn.dialect.has_table(sync_conn, "audit_logs")
        )
        _debug(f"audit_logs table exists: {result}")

    factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async def override_get_session() -> AsyncGenerator[AsyncSession, None]:
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    # ── override the global session factory ───────────────────────────
    from app.infrastructure.database import override_async_session_factory, get_async_session_factory

    override_async_session_factory(factory)

    # Verify override works
    returned = get_async_session_factory()
    _debug(f"override works: factory is {factory}, returned is {returned}, same={factory is returned}")

    # ── disable the latency gate ──────────────────────────────────────
    import app.domains.audit.middleware as mw_module

    original_latency = mw_module._MINIMAL_LATENCY_S
    mw_module._MINIMAL_LATENCY_S = 0.0

    # Verify latency gate is disabled
    _debug(f"_MINIMAL_LATENCY_S = {mw_module._MINIMAL_LATENCY_S}")

    # ── patch the app ─────────────────────────────────────────────────
    app.dependency_overrides[get_session] = override_get_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac, factory

    # ── cleanup ───────────────────────────────────────────────────────
    app.dependency_overrides.clear()
    override_async_session_factory(None)
    mw_module._MINIMAL_LATENCY_S = original_latency
    await engine.dispose()


# ======================================================================
# Helpers
# ======================================================================


async def fetch_audit_entries(factory: async_sessionmaker) -> list[AuditLog]:
    async with factory() as session:
        result = await session.execute(
            select(AuditLog).order_by(AuditLog.created_at.desc())
        )
        return list(result.scalars().all())


async def raw_count_audit_entries(factory: async_sessionmaker) -> int:
    """Count audit entries using raw SQL to avoid ORM issues."""
    async with factory() as session:
        result = await session.execute(
            select(func.count(AuditLog.id))
        )
        return result.scalar() or 0


# ======================================================================
# Integration tests
# ======================================================================


class TestAuditMiddlewareMutationDetection:
    """Verify the middleware catches mutating requests."""

    async def test_post_register_creates_audit_entry(
        self, audit_client: tuple[AsyncClient, async_sessionmaker]
    ) -> None:
        client, factory = audit_client

        _debug("Sending POST /auth/register...")
        resp = await client.post(
            "/auth/register",
            json={
                "email": "audit@test.com",
                "username": "audituser",
                "password": "strongpass123",
                "display_name": "Audit User",
            },
        )
        _debug(f"Response status: {resp.status_code}")
        assert resp.status_code == 201, resp.text

        # Check audit entries
        raw_count = await raw_count_audit_entries(factory)
        _debug(f"Raw count of audit entries: {raw_count}")

        entries = await fetch_audit_entries(factory)
        _debug(f"Fetched {len(entries)} audit entries")

        if entries:
            e = entries[0]
            _debug(f"First entry: action={e.action}, resource={e.resource_type}, id={e.id}")

        assert len(entries) >= 1

        entry = entries[0]
        assert entry.action == "CREATE"
        assert entry.resource_type == "auth"
        assert entry.username is None  # unauthenticated request

    async def test_patch_auth_me_creates_audit_entry_with_user_info(
        self, audit_client: tuple[AsyncClient, async_sessionmaker]
    ) -> None:
        client, factory = audit_client

        # ── register a user ───────────────────────────────────────────
        reg_resp = await client.post(
            "/auth/register",
            json={
                "email": "patchme@test.com",
                "username": "patchuser",
                "password": "strongpass456",
                "display_name": "Patch User",
            },
        )
        assert reg_resp.status_code == 201

        # ── login ─────────────────────────────────────────────────────
        login_resp = await client.post(
            "/auth/login",
            json={"login": "patchuser", "password": "strongpass456"},
        )
        assert login_resp.status_code == 200
        token = login_resp.json()["access_token"]

        _debug("Sending PATCH /auth/me...")
        # ── PATCH /auth/me ────────────────────────────────────────────
        patch_resp = await client.patch(
            "/auth/me",
            json={"display_name": "Patched Name"},
            headers={"Authorization": f"Bearer {token}"},
        )
        _debug(f"PATCH response status: {patch_resp.status_code}")
        assert patch_resp.status_code == 200, patch_resp.text

        # ── verify audit entry ────────────────────────────────────────
        entries = await fetch_audit_entries(factory)
        _debug(f"Total audit entries: {len(entries)}")
        patch_entries = [e for e in entries if e.action == "UPDATE"]
        _debug(f"UPDATE entries: {len(patch_entries)}")
        assert len(patch_entries) >= 1

        entry = patch_entries[0]
        assert entry.resource_type == "auth"
        assert entry.user_id is not None
        assert entry.username == "patchuser"

        details = json.loads(entry.details)
        assert details["method"] == "PATCH"
        assert details["status_code"] == 200

    async def test_login_skipped_from_auditing(
        self, audit_client: tuple[AsyncClient, async_sessionmaker]
    ) -> None:
        """Requests to /auth/login should NOT be audited."""
        client, factory = audit_client

        await client.post(
            "/auth/register",
            json={
                "email": "skips@test.com",
                "username": "skipuser",
                "password": "strongpass789",
                "display_name": "Skip User",
            },
        )

        login_resp = await client.post(
            "/auth/login",
            json={"login": "skipuser", "password": "strongpass789"},
        )
        assert login_resp.status_code == 200

        entries = await fetch_audit_entries(factory)
        login_entries = [e for e in entries if e.details and "/auth/login" in e.details]
        assert len(login_entries) == 0, "Login should not be audited"


class TestAuditMiddlewareGetNotAudited:
    """Verify GET requests do not create audit entries."""

    async def test_get_auth_me_no_audit(
        self, audit_client: tuple[AsyncClient, async_sessionmaker]
    ) -> None:
        client, factory = audit_client

        await client.post(
            "/auth/register",
            json={
                "email": "gettest@test.com",
                "username": "getuser",
                "password": "strongpass000",
                "display_name": "Get User",
            },
        )
        login_resp = await client.post(
            "/auth/login",
            json={"login": "getuser", "password": "strongpass000"},
        )
        token = login_resp.json()["access_token"]

        # GET /auth/me — should NOT create audit entry
        get_resp = await client.get(
            "/auth/me",
            headers={"Authorization": f"Bearer {token}"},
        )
        assert get_resp.status_code == 200

        entries = await fetch_audit_entries(factory)
        # There should be 1 entry from the register (login is skipped, GET is skipped)
        get_entries = [e for e in entries if e.details and "/auth/me" in e.details and e.action != "UPDATE"]
        assert len(get_entries) == 0, "GET should not be audited"


class TestAuditMiddlewarePureFunctions:
    """Unit-test the pure helper functions directly."""

    def test_should_audit_mutating_methods(self):
        for method in ("POST", "PATCH", "PUT", "DELETE"):
            request = _make_mock_request(method=method, path="/students")
            assert _should_audit(request), f"{method} should be audited"

    def test_should_not_audit_get_head_options(self):
        for method in ("GET", "HEAD", "OPTIONS"):
            request = _make_mock_request(method=method, path="/students")
            assert not _should_audit(request), f"{method} should NOT be audited"

    def test_should_not_audit_skipped_paths(self):
        for path in ("/health", "/ready", "/auth/login", "/auth/refresh",
                     "/api/admin/audit-logs", "/api/admin/audit-logs/42",
                     "/docs", "/openapi.json", "/redoc"):
            request = _make_mock_request(method="POST", path=path)
            assert not _should_audit(request), f"path={path} should be skipped"

    def test_should_audit_non_skipped_mutating_paths(self):
        for path in ("/students", "/students/123", "/auth/register",
                     "/auth/me", "/fees/fee-types", "/attendance/record"):
            request = _make_mock_request(method="POST", path=path)
            assert _should_audit(request), f"path={path} should be audited"

    def test_resource_type_from_path(self):
        assert _resource_type_from_path("/students") == "student"
        assert _resource_type_from_path("/students/123") == "student"
        assert _resource_type_from_path("/fees/fee-types") == "fee"
        assert _resource_type_from_path("/teachers/5/classes") == "teacher"
        assert _resource_type_from_path("/auth/register") == "auth"
        assert _resource_type_from_path("/unknown/path") == "unknown"
        assert _resource_type_from_path("/") == "unknown"
        assert _resource_type_from_path("") == "unknown"


def _make_mock_request(method: str = "GET", path: str = "/") -> object:
    """Build a minimal request-like object for testing pure helpers."""

    class _MockURL:
        def __init__(self, path: str):
            self.path = path

    class _MockRequest:
        def __init__(self, method: str, path: str):
            self.method = method
            self.url = _MockURL(path)

    return _MockRequest(method=method, path=path)
