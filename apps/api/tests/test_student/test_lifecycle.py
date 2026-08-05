from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.domains.student.lifecycle_service import StudentLifecycleService
from app.domains.student.models import (
    ALLOWED_LIFECYCLE_TRANSITIONS,
    STUDENT_STATUS_ACTIVE,
    STUDENT_STATUS_ADMITTED,
    STUDENT_STATUS_ALUMNI,
    STUDENT_STATUS_ENROLLED,
    STUDENT_STATUS_GRADUATED,
    STUDENT_STATUS_PROSPECTIVE,
    STUDENT_STATUS_TRANSFERRED,
    STUDENT_STATUS_WITHDRAWN,
    Student,
    StudentLifecycleEvent,
)
from app.domains.student.repository import StudentRepository
from app.domains.student.schemas import StudentCreate
from app.domains.student.service import StudentService
from app.multi_tenant.models import platform_context


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


async def _create_student(db_session: AsyncSession, number: str = "LC001") -> Student:
    svc = StudentService(StudentRepository(db_session, platform_context()))
    return await svc.create_student(
        StudentCreate(
            first_name="Life", last_name="Cycle", student_number=number
        )
    )


def _svc(db_session: AsyncSession) -> StudentLifecycleService:
    return StudentLifecycleService(db_session, platform_context())


async def _transition_events(db_session: AsyncSession, student_id: int) -> list[StudentLifecycleEvent]:
    result = await db_session.execute(
        select(StudentLifecycleEvent)
        .where(StudentLifecycleEvent.student_id == student_id)
        .order_by(StudentLifecycleEvent.created_at)
    )
    return list(result.scalars().all())


# ---------------------------------------------------------------------------
# Transition state machine
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_state_machine_definitions_are_consistent(db_session: AsyncSession):
    """Every listed status has an entry; terminal statuses map to empty set."""
    for status, targets in ALLOWED_LIFECYCLE_TRANSITIONS.items():
        assert isinstance(targets, set)
        # All targets must themselves be valid keys.
        for target in targets:
            assert target in ALLOWED_LIFECYCLE_TRANSITIONS, (
                f"{status} -> {target} points at unknown status"
            )


@pytest.mark.asyncio
async def test_transition_happy_path_records_event_and_updates_status(db_session: AsyncSession):
    student = await _create_student(db_session, "LC002")
    state = await _svc(db_session).transition(
        student.id, STUDENT_STATUS_ENROLLED, reason="Enrolled for term"
    )
    assert state.current_status == STUDENT_STATUS_ENROLLED
    events = await _transition_events(db_session, student.id)
    assert len(events) == 1
    assert events[0].from_status == STUDENT_STATUS_ACTIVE
    assert events[0].to_status == STUDENT_STATUS_ENROLLED
    assert events[0].reason == "Enrolled for term"

    # Student row reflects the new status.
    reloaded = await StudentRepository(db_session, platform_context()).get_by_id(student.id)
    assert reloaded.status == STUDENT_STATUS_ENROLLED


@pytest.mark.asyncio
async def test_transition_requires_valid_source_and_target(db_session: AsyncSession):
    student = await _create_student(db_session, "LC003")
    svc = _svc(db_session)

    # Same status -> Conflict
    with pytest.raises(ConflictError, match="already in status"):
        await svc.transition(student.id, STUDENT_STATUS_ACTIVE)

    # Disallowed transition (active -> alumni) -> ValidationError
    with pytest.raises(ValidationError, match="Invalid transition"):
        await svc.transition(student.id, STUDENT_STATUS_ALUMNI)

    # Unknown status -> ValidationError
    with pytest.raises(ValidationError, match="Invalid transition"):
        await svc.transition(student.id, "stardust")


@pytest.mark.asyncio
async def test_terminal_statuses_reject_all_transitions(db_session: AsyncSession):
    student = await _create_student(db_session, "LC004")
    svc = _svc(db_session)
    # Drive active -> withdrawn (terminal) -> any target must fail.
    await svc.transition(student.id, STUDENT_STATUS_WITHDRAWN, reason="Left school")
    with pytest.raises(ValidationError, match="terminal"):
        await svc.transition(student.id, STUDENT_STATUS_ACTIVE)


@pytest.mark.asyncio
async def test_full_canonical_flow(db_session: AsyncSession):
    """prospective -> admitted -> enrolled -> active -> graduated -> alumni."""
    student = await _create_student(db_session, "LC005")
    svc = _svc(db_session)

    # Directly seed the prospective start (bypasses default active start).
    student.status = STUDENT_STATUS_PROSPECTIVE
    await db_session.flush()

    flow = [
        (STUDENT_STATUS_ADMITTED, "Seat allocated"),
        (STUDENT_STATUS_ENROLLED, "Enrolled"),
        (STUDENT_STATUS_ACTIVE, "Started"),
        (STUDENT_STATUS_GRADUATED, "Completed"),
        (STUDENT_STATUS_ALUMNI, "Alumni"),
    ]
    for status, reason in flow:
        state = await svc.transition(student.id, status, reason=reason)
        assert state.current_status == status

    events = await _transition_events(db_session, student.id)
    assert [e.to_status for e in events] == [s for s, _ in flow]
    assert len(events) == 5


@pytest.mark.asyncio
async def test_transition_not_found(db_session: AsyncSession):
    with pytest.raises(NotFoundError, match="not found"):
        await _svc(db_session).transition(99999, STUDENT_STATUS_ENROLLED)


@pytest.mark.asyncio
async def test_transition_concurrency_guard(db_session: AsyncSession):
    """Stale-status transitions fail loudly instead of double-applying.        Simulates two staff members transitioning the same student concurrently:
        the row is moved underneath the in-memory object (``synchronize_session=
        False``), so the second transition's guarded UPDATE matches 0 rows and
        raises ``ConflictError`` rather than silently overwriting.
        """

    student = await _create_student(db_session, "LC008")
    # Materialize the INSERT first so the raw UPDATE below actually targets
    # an existing row (create_student may leave the insert pending).
    await db_session.flush()
    # Identity-mapped object still reports ``active``; the database row now
    # says ``enrolled`` — the service validates against the stale status.
    await db_session.execute(
        update(Student)
        .where(Student.id == student.id)
        .values(status=STUDENT_STATUS_ENROLLED)
        .execution_options(synchronize_session=False)
    )
    await db_session.flush()

    with pytest.raises(ConflictError, match="changed concurrently"):
        await _svc(db_session).transition(student.id, STUDENT_STATUS_WITHDRAWN)

    # No lifecycle event may be recorded for a rejected transition, and the
    # concurrent value ('enrolled') must not have been overwritten.
    assert await _transition_events(db_session, student.id) == []
    row_status = await db_session.execute(
        select(Student.status).where(Student.id == student.id)
    )
    assert row_status.scalar() == STUDENT_STATUS_ENROLLED
    await db_session.rollback()  # drop the raw-update row state


@pytest.mark.asyncio
async def test_get_state_reports_allowed_transitions_and_history(db_session: AsyncSession):
    student = await _create_student(db_session, "LC006")
    svc = _svc(db_session)
    await svc.transition(student.id, STUDENT_STATUS_ENROLLED, reason="Enrolled")

    state = await svc.get_state(student.id)
    assert state.current_status == STUDENT_STATUS_ENROLLED
    assert set(state.allowed_transitions) == ALLOWED_LIFECYCLE_TRANSITIONS[STUDENT_STATUS_ENROLLED]
    assert len(state.recent_events) == 1
    assert state.recent_events[0].to_status == STUDENT_STATUS_ENROLLED


@pytest.mark.asyncio
async def test_list_events_pagination(db_session: AsyncSession):
    student = await _create_student(db_session, "LC007")
    svc = _svc(db_session)
    student.status = STUDENT_STATUS_PROSPECTIVE
    await db_session.flush()
    for status in (STUDENT_STATUS_ADMITTED, STUDENT_STATUS_ENROLLED, STUDENT_STATUS_ACTIVE, STUDENT_STATUS_GRADUATED):
        await svc.transition(student.id, status, reason=f"step {status}")

    events, total = await svc.list_events(student.id, skip=0, limit=2)
    assert total == 4
    assert len(events) == 2
    # Newest first.
    assert events[0].to_status == STUDENT_STATUS_GRADUATED

    # Newest-first: [graduated, active, enrolled, admitted] — page 2 is
    # [enrolled, admitted].
    events, total = await svc.list_events(student.id, skip=2, limit=2)
    assert total == 4
    assert len(events) == 2
    assert events[0].to_status == STUDENT_STATUS_ENROLLED
    assert events[1].to_status == STUDENT_STATUS_ADMITTED


# ---------------------------------------------------------------------------
# API layer
# ---------------------------------------------------------------------------


async def _admin_headers(api_client: AsyncClient) -> dict:
    resp = await api_client.post(
        "/auth/login",
        json={"login": "admin", "password": "AdminPass123!"},
    )
    assert resp.status_code == 200, resp.text
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


@pytest.mark.asyncio
async def test_api_transition_requires_auth(api_client: AsyncClient):
    resp = await api_client.post("/students/1/lifecycle/transitions", json={"to_status": "enrolled"})
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_api_transition_requires_update_permission(api_client: AsyncClient):
    # UserCreate has no role field, so a registered user gets the default
    # ``staff`` role — which lacks ``students.update``. The 403 proves the
    # transition endpoint enforces the permission boundary.
    await api_client.post(
        "/auth/register",
        json={
            "username": "staff_user",
            "email": "staff@test.local",
            "password": "StaffPass123!",
            "display_name": "Staff User",
        },
    )
    login = await api_client.post(
        "/auth/login", json={"login": "staff_user", "password": "StaffPass123!"}
    )
    staff_headers = {"Authorization": f"Bearer {login.json()['access_token']}"}

    admin_headers = await _admin_headers(api_client)
    create = await api_client.post(
        "/students",
        json={"first_name": "A", "last_name": "B", "student_number": "LCAPI01"},
        headers=admin_headers,
    )
    assert create.status_code == 201, create.text
    student_id = create.json()["id"]

    resp = await api_client.post(
        f"/students/{student_id}/lifecycle/transitions",
        json={"to_status": "enrolled"},
        headers=staff_headers,
    )
    assert resp.status_code == 403


@pytest.mark.asyncio
async def test_api_transition_happy_path_and_history(api_client: AsyncClient):
    headers = await _admin_headers(api_client)
    create = await api_client.post(
        "/students",
        json={"first_name": "API", "last_name": "Lifecycle", "student_number": "LCAPI02"},
        headers=headers,
    )
    assert create.status_code == 201, create.text
    student_id = create.json()["id"]

    resp = await api_client.post(
        f"/students/{student_id}/lifecycle/transitions",
        json={"to_status": "enrolled", "reason": "Enrolled via API"},
        headers=headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["current_status"] == "enrolled"
    assert "active" in data["allowed_transitions"]

    # State endpoint
    state_resp = await api_client.get(
        f"/students/{student_id}/lifecycle", headers=headers
    )
    assert state_resp.status_code == 200
    assert state_resp.json()["recent_events"][0]["to_status"] == "enrolled"

    # Paginated events endpoint
    events_resp = await api_client.get(
        f"/students/{student_id}/lifecycle/events?page=1&size=1", headers=headers
    )
    assert events_resp.status_code == 200
    events_data = events_resp.json()
    assert events_data["total"] == 1
    assert len(events_data["items"]) == 1


@pytest.mark.asyncio
async def test_api_transition_rejects_invalid_transition(api_client: AsyncClient):
    headers = await _admin_headers(api_client)
    create = await api_client.post(
        "/students",
        json={"first_name": "Bad", "last_name": "Flow", "student_number": "LCAPI03"},
        headers=headers,
    )
    assert create.status_code == 201, create.text
    student_id = create.json()["id"]

    # active -> alumni is disallowed (must go through graduated).
    # The app maps domain ValidationError to HTTP 422.
    resp = await api_client.post(
        f"/students/{student_id}/lifecycle/transitions",
        json={"to_status": "alumni"},
        headers=headers,
    )
    assert resp.status_code == 422
    assert "Invalid transition" in resp.json()["detail"]


@pytest.mark.asyncio
async def test_api_transition_unknown_student_404(api_client: AsyncClient):
    headers = await _admin_headers(api_client)
    resp = await api_client.post(
        "/students/99999/lifecycle/transitions",
        json={"to_status": "enrolled"},
        headers=headers,
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_api_360_includes_lifecycle_and_documents(api_client: AsyncClient):
    headers = await _admin_headers(api_client)
    create = await api_client.post(
        "/students",
        json={"first_name": "Three", "last_name": "Sixty", "student_number": "LC36001"},
        headers=headers,
    )
    assert create.status_code == 201, create.text
    student_id = create.json()["id"]

    await api_client.post(
        f"/students/{student_id}/lifecycle/transitions",
        json={"to_status": "enrolled", "reason": "Now enrolled"},
        headers=headers,
    )

    resp = await api_client.get(f"/students/{student_id}/360", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["lifecycle"]["current_status"] == "enrolled"
    assert len(data["lifecycle"]["recent_events"]) == 1
    assert data["documents"] == []


@pytest.mark.asyncio
async def test_api_360_requires_tenant_scope(db_session: AsyncSession):
    """The 360 router rejects cross-tenant student reads (IDOR guard).

    The ``api_client`` fixture's seeded admin is unscoped (no memberships),
    so the guard is exercised directly here against the same
    ``assert_tenant_scope`` helper the router uses — mirroring
    ``tests/test_multi_tenant/test_guards.py`` conventions.
    """
    from app.core.exceptions import AuthorizationError
    from app.multi_tenant.guards import assert_tenant_scope
    from app.multi_tenant.models import TenantContext

    student = await _create_student(db_session, "LCT01")
    student.campus_id = 1
    await db_session.flush()

    # Same campus passes.
    assert_tenant_scope(student, TenantContext(campus_id=1), resource="student")

    # Foreign campus raises 403-equivalent.
    with pytest.raises(AuthorizationError, match="Cross-tenant access denied"):
        assert_tenant_scope(student, TenantContext(campus_id=2), resource="student")

    # Legacy untagged row invisible to scoped tenant.
    student.campus_id = None
    await db_session.flush()
    with pytest.raises(AuthorizationError, match="Cross-tenant access denied"):
        assert_tenant_scope(student, TenantContext(campus_id=1), resource="student")

    # Default-deny: an unscoped caller without explicit platform
    # authorization is refused (it must never imply full access).
    with pytest.raises(AuthorizationError, match="Cross-tenant access denied"):
        assert_tenant_scope(student, TenantContext(campus_id=None), resource="student")

    # Explicit platform callers may operate across campuses.
    assert_tenant_scope(
        student, TenantContext(campus_id=None, platform=True), resource="student"
    )
