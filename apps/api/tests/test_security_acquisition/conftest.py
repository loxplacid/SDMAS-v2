"""Shared fixtures for the acquisition-grade security & invariants suite.

The environment mirrors production tenancy semantics:

* Institution → Campus A (id 1) → Campus B (id 2)
* ``admin_a`` — ``admin`` role, member of campus A (default) → scoped to A
* ``admin_b`` — ``admin`` role, member of campus B (default) → scoped to B
* ``staff_a`` — ``staff`` role, member of campus A → scoped to A, limited perms
* ``teacher_a`` — ``teacher`` role, member of campus A
* ``student_a`` — ``student`` role, member of campus A
* ``staff_x`` — authenticated, NO campus / membership / platform perm → default-deny
* ``plat_admin`` — ``platform_admin`` role, no campus → explicit cross-tenant access

Every request goes through the same FastAPI app with dependency overrides
bound to an in-memory SQLite engine.  The engine enforces foreign keys
(``PRAGMA foreign_keys=ON``) so database-integrity invariants behave like
production PostgreSQL instead of default-permissive SQLite.
"""

from __future__ import annotations

import datetime
from collections.abc import AsyncGenerator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import event, select
from sqlalchemy.ext.asyncio import (
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from app.infrastructure.database import Base, get_session

# Import every model so Base.metadata can resolve cross-module FKs.
from app.domains.institution.models import Institution, Campus  # noqa: F401
from app.domains.auth.models import (  # noqa: F401
    User,
    UserSchoolMembership,
    RefreshToken,
)
from app.domains.auth.security import hash_password  # noqa: F401
from app.domains.student.models import Student  # noqa: F401
from app.domains.academic.models import (  # noqa: F401
    AcademicYear,
    Class,
    Section,
    Enrollment,
)
from app.domains.fees.models import FeeDue  # noqa: F401
from app.domains.documents.models import Document, DocumentCategory  # noqa: F401
from app.domains.notifications.models import Notification  # noqa: F401
from app.domains.jobs.models import Job  # noqa: F401
from app.domains.audit.models import AuditLog  # noqa: F401

TEST_DATABASE_URL = "sqlite+aiosqlite:///:memory:"


class AcqEnv:
    """Namespace exposing the API client, session factory and seeded ids."""

    def __init__(self, client: AsyncClient, factory, tmp_storage: str) -> None:
        self.client = client
        self.factory = factory
        self.tmp_storage = tmp_storage
        self.campus_a = 1
        self.campus_b = 2


@pytest_asyncio.fixture
async def acq_env(tmp_path) -> AsyncGenerator[AcqEnv, None]:
    """Two-campus environment with FK enforcement and a temp storage root."""
    from app.main import app  # registers every model with Base.metadata

    engine = create_async_engine(TEST_DATABASE_URL, echo=False)

    # SQLite does not enforce FKs by default; production (PostgreSQL) does.
    # Enabling the pragma makes FK-integrity tests meaningful and mirrors
    # the production database contract.
    @event.listens_for(engine.sync_engine, "connect")
    def _enable_fk_pragma(dbapi_conn, _record) -> None:  # pragma: no cover
        cursor = dbapi_conn.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    factory = async_sessionmaker(
        engine, class_=AsyncSession, expire_on_commit=False
    )

    async with factory() as seed:
        institution = Institution(name="Acq District", code="ACQ-DST")
        seed.add(institution)
        await seed.flush()
        campus_a = Campus(
            institution_id=institution.id, name="Campus A", code="ACQ-A",
            status="active",
        )
        campus_b = Campus(
            institution_id=institution.id, name="Campus B", code="ACQ-B",
            status="active",
        )
        seed.add_all([campus_a, campus_b])
        await seed.flush()

        def _user(username: str, role: str, campus_id: int | None) -> User:
            return User(
                username=username,
                email=f"{username}@acq.test",
                password_hash=hash_password(f"{username.title()}123!"),
                display_name=username.title(),
                role=role,
                campus_id=campus_id,
                is_active=True,
            )

        admin_a = _user("admin_a", "admin", campus_a.id)
        admin_b = _user("admin_b", "admin", campus_b.id)
        staff_a = _user("staff_a", "staff", campus_a.id)
        teacher_a = _user("teacher_a", "teacher", campus_a.id)
        student_a = _user("student_a", "student", campus_a.id)
        staff_x = _user("staff_x", "staff", None)
        plat_admin = _user("plat_admin", "platform_admin", None)
        seed.add_all(
            [admin_a, admin_b, staff_a, teacher_a, student_a, staff_x, plat_admin]
        )
        await seed.flush()

        seed.add_all([
            UserSchoolMembership(
                user_id=admin_a.id, campus_id=campus_a.id,
                role="admin", is_default=True, is_active=True,
            ),
            UserSchoolMembership(
                user_id=admin_b.id, campus_id=campus_b.id,
                role="admin", is_default=True, is_active=True,
            ),
            UserSchoolMembership(
                user_id=staff_a.id, campus_id=campus_a.id,
                role="staff", is_default=True, is_active=True,
            ),
            UserSchoolMembership(
                user_id=teacher_a.id, campus_id=campus_a.id,
                role="teacher", is_default=True, is_active=True,
            ),
            UserSchoolMembership(
                user_id=student_a.id, campus_id=campus_a.id,
                role="student", is_default=True, is_active=True,
            ),
        ])
        await seed.commit()

    tmp_storage = str(tmp_path / "doc-storage")

    async def override_get_session():
        async with factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    app.dependency_overrides[get_session] = override_get_session

    # Pin the document storage backend to a per-test temp directory.
    from app.config import settings

    old_root = settings.storage_root
    settings.storage_root = tmp_storage

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield AcqEnv(client=ac, factory=factory, tmp_storage=tmp_storage)

    settings.storage_root = old_root
    app.dependency_overrides.clear()
    await engine.dispose()


# ---------------------------------------------------------------------------
# Login helpers
# ---------------------------------------------------------------------------


async def login(env: AcqEnv, username: str) -> dict[str, str]:
    """Log in a seeded user and return bearer headers."""
    password = f"{username.title()}123!"
    resp = await env.client.post(
        "/auth/login", json={"login": username, "password": password}
    )
    assert resp.status_code == 200, f"login failed for {username}: {resp.text}"
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


async def login_full(env: AcqEnv, username: str) -> dict:
    """Log in and return the full token response (access + refresh)."""
    password = f"{username.title()}123!"
    resp = await env.client.post(
        "/auth/login", json={"login": username, "password": password}
    )
    assert resp.status_code == 200, resp.text
    return resp.json()


@pytest_asyncio.fixture
async def headers_a(acq_env: AcqEnv) -> dict[str, str]:
    return await login(acq_env, "admin_a")


@pytest_asyncio.fixture
async def headers_b(acq_env: AcqEnv) -> dict[str, str]:
    return await login(acq_env, "admin_b")


@pytest_asyncio.fixture
async def headers_staff_a(acq_env: AcqEnv) -> dict[str, str]:
    return await login(acq_env, "staff_a")


@pytest_asyncio.fixture
async def headers_staff_none(acq_env: AcqEnv) -> dict[str, str]:
    return await login(acq_env, "staff_x")


@pytest_asyncio.fixture
async def headers_platform(acq_env: AcqEnv) -> dict[str, str]:
    return await login(acq_env, "plat_admin")


# ---------------------------------------------------------------------------
# Seeding helpers (direct inserts via the shared engine)
# ---------------------------------------------------------------------------


async def seed_student(factory, campus_id: int, number: str, last_name: str) -> int:
    async with factory() as s:
        st = Student(
            first_name=f"Acq{last_name}", last_name=last_name,
            student_number=number, campus_id=campus_id, status="active",
        )
        s.add(st)
        await s.commit()
        return st.id


async def seed_academic(factory, campus_id: int, tag: str) -> dict:
    """Seed academic year + class for a campus (year_id/class_id)."""
    async with factory() as s:
        year = AcademicYear(
            name=f"Acq Year {tag}", start_date=datetime.date(2026, 1, 1),
            end_date=datetime.date(2026, 12, 31), campus_id=campus_id,
            status="active",
        )
        s.add(year)
        await s.flush()
        cls = Class(
            name=f"Acq Class {tag}", academic_year_id=year.id,
            campus_id=campus_id, status="active",
        )
        s.add(cls)
        await s.commit()
        return {"year_id": year.id, "class_id": cls.id}


async def seed_document(factory, campus_id: int, uploaded_by: int,
                        key: str) -> int:
    """Seed a document row + category directly (no storage write)."""
    async with factory() as s:
        cat = DocumentCategory(code=f"cat-{key}", name=f"Cat {key}")
        s.add(cat)
        await s.flush()
        doc = Document(
            category_id=cat.id, original_filename=f"{key}.pdf",
            storage_key=f"cat-{key}/2026/01/{key}.pdf", mime_type="application/pdf",
            file_size=10, lifecycle_state="active", campus_id=campus_id,
            uploaded_by=uploaded_by,
        )
        s.add(doc)
        await s.commit()
        return doc.id


async def seed_notification(factory, campus_id: int, user_id: int,
                            title: str) -> int:
    async with factory() as s:
        n = Notification(
            type="system", title=title, message=f"msg-{title}",
            campus_id=campus_id, user_id=user_id,
        )
        s.add(n)
        await s.commit()
        return n.id


async def seed_job(factory, campus_id: int, tag: str, user_id: int | None = None) -> int:
    async with factory() as s:
        job = Job(
            job_type=f"acq-{tag}", status="pending", campus_id=campus_id,
            user_id=user_id,
            created_at=datetime.datetime.now(datetime.timezone.utc),
            updated_at=datetime.datetime.now(datetime.timezone.utc),
        )
        s.add(job)
        await s.commit()
        return job.id


async def seed_audit(factory, campus_id: int | None, action: str,
                     resource: str, marker: str) -> int:
    import json

    async with factory() as s:
        entry = AuditLog(
            event_id=marker, user_id=None, username=None, actor_type="user",
            action=action, resource_type=resource, resource_id="1",
            campus_id=campus_id,
            details=json.dumps({"marker": marker}),
        )
        s.add(entry)
        await s.commit()
        return entry.id
