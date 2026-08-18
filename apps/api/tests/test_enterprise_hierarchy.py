"""Isolation and authorization tests for the enterprise organization
hierarchy (Organization → School Group → Region → Campus).

TASK 21 adds two aggregation levels *above* the campus (``SchoolGroup``,
``Region``) plus a new ``OrganizationAssignment`` table that pins an
administrator to a subtree (org / group / region / campus).  The campus
remains the tenant (data-isolation) unit; hierarchy administrators may
operate across campuses **inside their subtree only**.

These tests verify the invariants that keep tenant isolation intact:

1. ``TenantContext.scope_level`` classifies every context correctly.
2. ``resolve_tenant_context`` builds subtree-scoped contexts from
   organization assignments, and assignments take precedence over school
   memberships.
3. ``TenantScopedRepository`` pins every query to the caller's subtree —
   cross-campus, cross-group and cross-organization rows are invisible.
4. The hierarchy guards reject any node outside the caller's subtree.
5. End-to-end through the HTTP API: cross-tenant access fails (403).

See also:
  - ``app/multi_tenant/models.py`` (``TenantScopeLevel``, ``TenantContext``)
  - ``app/multi_tenant/dependencies.py`` (``resolve_tenant_context``)
  - ``app/multi_tenant/repository.py`` (``TenantScopedRepository``)
  - ``app/multi_tenant/guards.py`` (hierarchy guards)
"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app.core.exceptions import AuthorizationError
from app.domains.auth.models import (
    AssignmentNodeType,
    OrganizationAssignment,
    User,
)
from app.domains.institution.models import (
    Campus,
    Institution,
    Region,
    School,
    SchoolGroup,
)
from app.domains.student.models import Student
from app.multi_tenant.models import (
    TenantContext,
    TenantScopeLevel,
    hierarchy_context,
    platform_context,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


async def _seed_hierarchy(session) -> dict[str, int]:
    """Seed two organizations with group → region → campus chains.

    Organization 1 (``org_a``):
        Group 1A → Region 1A1 → Campus 11
                      Region 1A2 → Campus 12
        Group 1B → Region 1B1 → Campus 13
    Organization 2 (``org_b``):
        Group 2A → Region 2A1 → Campus 21

    Returns a dict of ``id`` lookups.
    """
    org_a = Institution(name="Org A", code="ORG-A")
    org_b = Institution(name="Org B", code="ORG-B")
    session.add_all([org_a, org_b])
    await session.flush()

    group_1a = SchoolGroup(institution_id=org_a.id, name="Group 1A", code="G1A")
    group_1b = SchoolGroup(institution_id=org_a.id, name="Group 1B", code="G1B")
    group_2a = SchoolGroup(institution_id=org_b.id, name="Group 2A", code="G2A")
    session.add_all([group_1a, group_1b, group_2a])
    await session.flush()

    region_1a1 = Region(
        school_group_id=group_1a.id, institution_id=org_a.id,
        name="Region 1A1", code="R1A1",
    )
    region_1a2 = Region(
        school_group_id=group_1a.id, institution_id=org_a.id,
        name="Region 1A2", code="R1A2",
    )
    region_1b1 = Region(
        school_group_id=group_1b.id, institution_id=org_a.id,
        name="Region 1B1", code="R1B1",
    )
    region_2a1 = Region(
        school_group_id=group_2a.id, institution_id=org_b.id,
        name="Region 2A1", code="R2A1",
    )
    session.add_all([region_1a1, region_1a2, region_1b1, region_2a1])
    await session.flush()

    campus_11 = Campus(
        institution_id=org_a.id, school_group_id=group_1a.id,
        region_id=region_1a1.id, name="Campus 11", code="CMP-11",
    )
    campus_12 = Campus(
        institution_id=org_a.id, school_group_id=group_1a.id,
        region_id=region_1a2.id, name="Campus 12", code="CMP-12",
    )
    campus_13 = Campus(
        institution_id=org_a.id, school_group_id=group_1b.id,
        region_id=region_1b1.id, name="Campus 13", code="CMP-13",
    )
    campus_21 = Campus(
        institution_id=org_b.id, school_group_id=group_2a.id,
        region_id=region_2a1.id, name="Campus 21", code="CMP-21",
    )
    session.add_all([campus_11, campus_12, campus_13, campus_21])
    await session.flush()

    return {
        "org_a": org_a.id,
        "org_b": org_b.id,
        "group_1a": group_1a.id,
        "group_1b": group_1b.id,
        "group_2a": group_2a.id,
        "region_1a1": region_1a1.id,
        "region_1a2": region_1a2.id,
        "region_1b1": region_1b1.id,
        "region_2a1": region_2a1.id,
        "campus_11": campus_11.id,
        "campus_12": campus_12.id,
        "campus_13": campus_13.id,
        "campus_21": campus_21.id,
    }


async def _seed_students(session, ids: dict[str, int]) -> None:
    """One student per campus across both organizations."""
    students = [
        Student(
            first_name=f"Stu{ids[cid]}", last_name="Campus",
            student_number=f"STU-H-{ids[cid]}",
            campus_id=ids[cid], status="active",
        )
        for cid in ("campus_11", "campus_12", "campus_13", "campus_21")
    ]
    session.add_all(students)
    await session.flush()


def _make_user(session, username: str, role: str = "org_admin") -> User:
    user = User(
        email=f"{username}@test.local",
        username=username,
        password_hash="x",
        display_name=username.title(),
        role=role,
    )
    session.add(user)
    return user


# ---------------------------------------------------------------------------
# TenantContext.scope_level classification (unit)
# ---------------------------------------------------------------------------


class TestTenantContextScopeLevel:
    def test_campus_scope_wins(self) -> None:
        tenant = TenantContext(campus_id=7, region_id=6, school_group_id=5, institution_id=4)
        assert tenant.scope_level == TenantScopeLevel.CAMPUS
        assert tenant.is_hierarchy_scoped
        assert tenant.is_tenant_scoped

    def test_region_scope(self) -> None:
        tenant = TenantContext(region_id=6, school_group_id=5, institution_id=4)
        assert tenant.scope_level == TenantScopeLevel.REGION
        assert tenant.is_hierarchy_scoped

    def test_group_scope(self) -> None:
        tenant = TenantContext(school_group_id=5, institution_id=4)
        assert tenant.scope_level == TenantScopeLevel.GROUP
        assert tenant.is_hierarchy_scoped

    def test_organization_scope(self) -> None:
        tenant = TenantContext(institution_id=4)
        assert tenant.scope_level == TenantScopeLevel.ORGANIZATION
        assert tenant.is_hierarchy_scoped

    def test_platform_scope(self) -> None:
        tenant = platform_context(user_id=1)
        assert tenant.scope_level == TenantScopeLevel.PLATFORM
        assert not tenant.is_hierarchy_scoped

    def test_none_scope(self) -> None:
        tenant = TenantContext(user_id=1)
        assert tenant.scope_level == TenantScopeLevel.NONE
        assert not tenant.is_hierarchy_scoped

    def test_hierarchy_context_never_implies_platform(self) -> None:
        tenant = hierarchy_context(institution_id=4)
        assert tenant.platform is False
        assert tenant.scope_level == TenantScopeLevel.ORGANIZATION


# ---------------------------------------------------------------------------
# resolve_tenant_context from organization assignments
# ---------------------------------------------------------------------------


class TestResolveTenantContextFromAssignment:
    async def test_organization_assignment(self, db_session) -> None:
        from app.multi_tenant.dependencies import resolve_tenant_context

        ids = await _seed_hierarchy(db_session)
        user = _make_user(db_session, "orgadmin")
        await db_session.flush()
        db_session.add(
            OrganizationAssignment(
                user_id=user.id,
                node_type=AssignmentNodeType.ORGANIZATION.value,
                node_id=ids["org_a"],
                role="org_admin",
            )
        )
        await db_session.commit()

        tenant = await resolve_tenant_context(db_session, user, require_school=True)
        assert tenant.scope_level == TenantScopeLevel.ORGANIZATION
        assert tenant.institution_id == ids["org_a"]
        assert tenant.campus_id is None
        assert tenant.platform is False

    async def test_group_assignment(self, db_session) -> None:
        from app.multi_tenant.dependencies import resolve_tenant_context

        ids = await _seed_hierarchy(db_session)
        user = _make_user(db_session, "groupadmin", role="group_admin")
        await db_session.flush()
        db_session.add(
            OrganizationAssignment(
                user_id=user.id,
                node_type=AssignmentNodeType.GROUP.value,
                node_id=ids["group_1a"],
                role="group_admin",
            )
        )
        await db_session.commit()

        tenant = await resolve_tenant_context(db_session, user, require_school=True)
        assert tenant.scope_level == TenantScopeLevel.GROUP
        assert tenant.school_group_id == ids["group_1a"]
        assert tenant.institution_id == ids["org_a"]

    async def test_region_assignment(self, db_session) -> None:
        from app.multi_tenant.dependencies import resolve_tenant_context

        ids = await _seed_hierarchy(db_session)
        user = _make_user(db_session, "regionadmin", role="region_admin")
        await db_session.flush()
        db_session.add(
            OrganizationAssignment(
                user_id=user.id,
                node_type=AssignmentNodeType.REGION.value,
                node_id=ids["region_1a1"],
                role="region_admin",
            )
        )
        await db_session.commit()

        tenant = await resolve_tenant_context(db_session, user, require_school=True)
        assert tenant.scope_level == TenantScopeLevel.REGION
        assert tenant.region_id == ids["region_1a1"]
        assert tenant.institution_id == ids["org_a"]

    async def test_campus_assignment(self, db_session) -> None:
        from app.multi_tenant.dependencies import resolve_tenant_context

        ids = await _seed_hierarchy(db_session)
        user = _make_user(db_session, "campusadmin", role="admin")
        await db_session.flush()
        db_session.add(
            OrganizationAssignment(
                user_id=user.id,
                node_type=AssignmentNodeType.CAMPUS.value,
                node_id=ids["campus_11"],
                role="admin",
            )
        )
        await db_session.commit()

        tenant = await resolve_tenant_context(db_session, user, require_school=True)
        assert tenant.scope_level == TenantScopeLevel.CAMPUS
        assert tenant.campus_id == ids["campus_11"]
        assert tenant.institution_id == ids["org_a"]

    async def test_assignment_takes_precedence_over_membership(
        self, db_session,
    ) -> None:
        """An org-admin who is also a member of campus 12 must resolve to
        the organization scope, not the campus."""
        from app.domains.auth.models import UserSchoolMembership
        from app.multi_tenant.dependencies import resolve_tenant_context

        ids = await _seed_hierarchy(db_session)
        user = _make_user(db_session, "dual", role="org_admin")
        user.campus_id = ids["campus_12"]
        await db_session.flush()
        db_session.add_all(
            [
                OrganizationAssignment(
                    user_id=user.id,
                    node_type=AssignmentNodeType.ORGANIZATION.value,
                    node_id=ids["org_a"],
                    role="org_admin",
                ),
                UserSchoolMembership(
                    user_id=user.id,
                    campus_id=ids["campus_12"],
                    role="admin",
                    is_default=True,
                    is_active=True,
                ),
            ]
        )
        await db_session.commit()

        tenant = await resolve_tenant_context(db_session, user, require_school=True)
        assert tenant.scope_level == TenantScopeLevel.ORGANIZATION
        assert tenant.campus_id is None


# ---------------------------------------------------------------------------
# Repository scope filtering across the hierarchy
# ---------------------------------------------------------------------------


class TestHierarchyScopedRepositoryFiltering:
    async def test_org_admin_sees_only_own_org(self, db_session) -> None:
        from app.multi_tenant.repository import TenantScopedRepository

        ids = await _seed_hierarchy(db_session)
        await _seed_students(db_session, ids)
        await db_session.commit()

        repo = TenantScopedRepository(
            db_session, TenantContext(institution_id=ids["org_a"], user_id=1)
        )
        result = await db_session.execute(repo.scoped_query(Student))
        students = list(result.scalars().all())
        campus_ids = {s.campus_id for s in students}

        assert campus_ids == {ids["campus_11"], ids["campus_12"], ids["campus_13"]}
        assert ids["campus_21"] not in campus_ids

    async def test_group_admin_sees_only_own_group(self, db_session) -> None:
        from app.multi_tenant.repository import TenantScopedRepository

        ids = await _seed_hierarchy(db_session)
        await _seed_students(db_session, ids)
        await db_session.commit()

        repo = TenantScopedRepository(
            db_session,
            TenantContext(school_group_id=ids["group_1a"], institution_id=ids["org_a"], user_id=1),
        )
        result = await db_session.execute(repo.scoped_query(Student))
        students = list(result.scalars().all())
        campus_ids = {s.campus_id for s in students}

        assert campus_ids == {ids["campus_11"], ids["campus_12"]}
        assert ids["campus_13"] not in campus_ids
        assert ids["campus_21"] not in campus_ids

    async def test_region_admin_sees_only_own_region(self, db_session) -> None:
        from app.multi_tenant.repository import TenantScopedRepository

        ids = await _seed_hierarchy(db_session)
        await _seed_students(db_session, ids)
        await db_session.commit()

        repo = TenantScopedRepository(
            db_session,
            TenantContext(region_id=ids["region_1a1"], institution_id=ids["org_a"], user_id=1),
        )
        result = await db_session.execute(repo.scoped_query(Student))
        students = list(result.scalars().all())
        campus_ids = {s.campus_id for s in students}

        assert campus_ids == {ids["campus_11"]}
        assert ids["campus_12"] not in campus_ids

    async def test_campus_admin_sees_only_own_campus(self, db_session) -> None:
        from app.multi_tenant.repository import TenantScopedRepository

        ids = await _seed_hierarchy(db_session)
        await _seed_students(db_session, ids)
        await db_session.commit()

        repo = TenantScopedRepository(
            db_session, TenantContext(campus_id=ids["campus_11"], user_id=1)
        )
        result = await db_session.execute(repo.scoped_query(Student))
        students = list(result.scalars().all())

        assert {s.campus_id for s in students} == {ids["campus_11"]}

    async def test_get_by_id_returns_none_for_foreign_row(self, db_session) -> None:
        """A campus-scoped caller cannot fetch a row from another campus."""
        from app.multi_tenant.repository import TenantScopedRepository

        ids = await _seed_hierarchy(db_session)
        await _seed_students(db_session, ids)
        await db_session.commit()

        repo = TenantScopedRepository(
            db_session, TenantContext(campus_id=ids["campus_11"], user_id=1)
        )
        rows = (await db_session.execute(select(Student))).scalars().all()
        foreign = next(s for s in rows if s.campus_id == ids["campus_12"])

        assert await repo.get_by_id(Student, foreign.id) is None

    async def test_unscoped_non_platform_caller_is_denied(self, db_session) -> None:
        from app.multi_tenant.repository import TenantScopedRepository

        repo = TenantScopedRepository(db_session, TenantContext(user_id=1))
        with pytest.raises(AuthorizationError, match="Cross-tenant access denied"):
            repo.scoped_query(Student)


# ---------------------------------------------------------------------------
# Hierarchy guards
# ---------------------------------------------------------------------------


class TestHierarchyGuards:
    async def test_assert_campus_in_scope_denies_cross_org(self, db_session) -> None:
        from app.multi_tenant.guards import assert_campus_in_scope

        ids = await _seed_hierarchy(db_session)
        await db_session.commit()

        org_a = TenantContext(institution_id=ids["org_a"], user_id=1)
        await assert_campus_in_scope(db_session, org_a, ids["campus_11"], resource="x")
        with pytest.raises(AuthorizationError, match="Cross-tenant access denied"):
            await assert_campus_in_scope(db_session, org_a, ids["campus_21"], resource="x")

    async def test_assert_campus_in_scope_denies_cross_group(self, db_session) -> None:
        from app.multi_tenant.guards import assert_campus_in_scope

        ids = await _seed_hierarchy(db_session)
        await db_session.commit()

        group = TenantContext(
            school_group_id=ids["group_1a"], institution_id=ids["org_a"], user_id=1
        )
        await assert_campus_in_scope(db_session, group, ids["campus_11"], resource="x")
        with pytest.raises(AuthorizationError, match="Cross-tenant access denied"):
            await assert_campus_in_scope(db_session, group, ids["campus_13"], resource="x")

    async def test_assert_campus_in_scope_denies_cross_region(self, db_session) -> None:
        from app.multi_tenant.guards import assert_campus_in_scope

        ids = await _seed_hierarchy(db_session)
        await db_session.commit()

        region = TenantContext(region_id=ids["region_1a1"], institution_id=ids["org_a"], user_id=1)
        await assert_campus_in_scope(db_session, region, ids["campus_11"], resource="x")
        with pytest.raises(AuthorizationError, match="Cross-tenant access denied"):
            await assert_campus_in_scope(db_session, region, ids["campus_12"], resource="x")

    async def test_campus_admin_cannot_reach_other_campus(self, db_session) -> None:
        from app.multi_tenant.guards import assert_campus_in_scope

        ids = await _seed_hierarchy(db_session)
        await db_session.commit()

        campus = TenantContext(campus_id=ids["campus_11"], user_id=1)
        await assert_campus_in_scope(db_session, campus, ids["campus_11"], resource="x")
        with pytest.raises(AuthorizationError, match="Cross-tenant access denied"):
            await assert_campus_in_scope(db_session, campus, ids["campus_12"], resource="x")

    async def test_assert_school_group_in_scope(self, db_session) -> None:
        from app.multi_tenant.guards import assert_school_group_in_scope

        ids = await _seed_hierarchy(db_session)
        await db_session.commit()

        group_1a = (await db_session.execute(
            select(SchoolGroup).where(SchoolGroup.id == ids["group_1a"])
        )).scalar_one()
        group_1b = (await db_session.execute(
            select(SchoolGroup).where(SchoolGroup.id == ids["group_1b"])
        )).scalar_one()

        org_admin = TenantContext(institution_id=ids["org_a"], user_id=1)
        await assert_school_group_in_scope(db_session, org_admin, group_1b)

        group_admin = TenantContext(
            school_group_id=ids["group_1a"], institution_id=ids["org_a"], user_id=1
        )
        await assert_school_group_in_scope(db_session, group_admin, group_1a)
        with pytest.raises(AuthorizationError, match="Cross-tenant access denied"):
            await assert_school_group_in_scope(db_session, group_admin, group_1b)

        with pytest.raises(AuthorizationError, match="Cross-tenant access denied"):
            await assert_school_group_in_scope(
                db_session, org_admin,
                (await db_session.execute(
                    select(SchoolGroup).where(SchoolGroup.id == ids["group_2a"])
                )).scalar_one(),
            )

    async def test_assert_region_in_scope(self, db_session) -> None:
        from app.multi_tenant.guards import assert_region_in_scope

        ids = await _seed_hierarchy(db_session)
        await db_session.commit()

        region_1a1 = (await db_session.execute(
            select(Region).where(Region.id == ids["region_1a1"])
        )).scalar_one()
        region_1b1 = (await db_session.execute(
            select(Region).where(Region.id == ids["region_1b1"])
        )).scalar_one()

        region_admin = TenantContext(
            region_id=ids["region_1a1"], institution_id=ids["org_a"], user_id=1
        )
        await assert_region_in_scope(db_session, region_admin, region_1a1)
        with pytest.raises(AuthorizationError, match="Cross-tenant access denied"):
            await assert_region_in_scope(db_session, region_admin, region_1b1)

    async def test_assert_institution_in_scope(self, db_session) -> None:
        from app.multi_tenant.guards import assert_institution_in_scope

        ids = await _seed_hierarchy(db_session)
        await db_session.commit()

        org_a_admin = TenantContext(institution_id=ids["org_a"], user_id=1)
        await assert_institution_in_scope(
            db_session, org_a_admin, ids["org_a"], resource="institution"
        )
        with pytest.raises(AuthorizationError, match="Cross-tenant access denied"):
            await assert_institution_in_scope(
                db_session, org_a_admin, ids["org_b"], resource="institution"
            )

        group_admin = TenantContext(
            school_group_id=ids["group_1a"], institution_id=ids["org_a"], user_id=1
        )
        with pytest.raises(AuthorizationError, match="Cross-tenant access denied"):
            await assert_institution_in_scope(
                db_session, group_admin, ids["org_a"], resource="institution"
            )


# ---------------------------------------------------------------------------
# End-to-end authorization through the HTTP API
# ---------------------------------------------------------------------------


def _api_session(api_client):
    """Yield the live session behind ``api_client``'s dependency override,
    so seed data lands in the SAME database the API serves."""
    from app.infrastructure.database import get_session
    from app.main import app

    override = app.dependency_overrides[get_session]
    gen = override()
    return gen


async def _seed_hierarchy_via_api(api_client) -> dict[str, int]:
    """Seed the enterprise hierarchy directly into the API client's DB."""

    gen = _api_session(api_client)
    session = await gen.__anext__()
    try:
        ids = await _seed_hierarchy(session)
        # The override's commit runs only when the generator is resumed
        # after ``yield``; ``aclose()`` raises GeneratorExit instead, so
        # commit explicitly here or the seed is rolled back.
        await session.commit()
        return ids
    finally:
        await gen.aclose()


async def _seed_api_admin(
    api_client,
    username: str,
    role: str,
    node_type: str,
    node_id: int,
    password: str = "HiePass123!",
) -> None:
    """Insert an admin user + organization assignment into the API DB."""
    from app.domains.auth.models import User
    from app.domains.auth.security import hash_password

    gen = _api_session(api_client)
    session = await gen.__anext__()
    try:
        user = User(
            username=username,
            email=f"{username}@hierarchy.test",
            password_hash=hash_password(password),
            display_name=username.title(),
            role=role,
            is_active=True,
        )
        session.add(user)
        await session.flush()
        session.add(
            OrganizationAssignment(
                user_id=user.id,
                node_type=node_type,
                node_id=node_id,
                role=role,
            )
        )
        await session.commit()
    finally:
        await gen.aclose()


async def _api_login(api_client, username: str, password: str = "HiePass123!") -> dict:
    resp = await api_client.post(
        "/auth/login", json={"login": username, "password": password},
    )
    assert resp.status_code == 200, resp.text
    return {"Authorization": f"Bearer {resp.json()['access_token']}"}


class TestApiAuthorization:
    async def test_org_admin_cannot_create_group_for_other_org(
        self, api_client,
    ) -> None:
        """An org-admin authenticated via an assignment must not create a
        school group under another organization."""
        ids = await _seed_hierarchy_via_api(api_client)
        await _seed_api_admin(
            api_client, "orgadmin_api", "org_admin",
            AssignmentNodeType.ORGANIZATION.value, ids["org_a"],
        )
        headers = await _api_login(api_client, "orgadmin_api")

        # Inside own org → 201
        ok = await api_client.post(
            "/api/institution/school-groups",
            headers=headers,
            json={"institution_id": ids["org_a"], "name": "Group A2", "code": "GA2"},
        )
        assert ok.status_code == 201, ok.text

        # Other org → 403 (cross-tenant)
        denied = await api_client.post(
            "/api/institution/school-groups",
            headers=headers,
            json={"institution_id": ids["org_b"], "name": "Group B", "code": "GB"},
        )
        assert denied.status_code == 403, denied.text

    async def test_group_admin_cannot_touch_other_group_region(
        self, api_client,
    ) -> None:
        """A group-admin must not create a region in another group's
        hierarchy."""
        ids = await _seed_hierarchy_via_api(api_client)
        await _seed_api_admin(
            api_client, "groupadmin_api", "group_admin",
            AssignmentNodeType.GROUP.value, ids["group_1a"],
        )
        headers = await _api_login(api_client, "groupadmin_api")

        ok = await api_client.post(
            "/api/institution/regions",
            headers=headers,
            json={
                "institution_id": ids["org_a"],
                "school_group_id": ids["group_1a"],
                "name": "Region 1A3", "code": "R1A3",
            },
        )
        assert ok.status_code == 201, ok.text

        denied = await api_client.post(
            "/api/institution/regions",
            headers=headers,
            json={
                "institution_id": ids["org_a"],
                "school_group_id": ids["group_1b"],
                "name": "Region 1B2", "code": "R1B2",
            },
        )
        assert denied.status_code == 403, denied.text

    async def test_region_admin_cannot_read_foreign_campus_school(
        self, api_client,
    ) -> None:
        """A region-admin must not list schools belonging to a campus
        outside their region."""

        gen = _api_session(api_client)
        session = await gen.__anext__()
        try:
            ids = await _seed_hierarchy(session)
            for campus_id in (ids["campus_11"], ids["campus_12"], ids["campus_13"]):
                session.add(
                    School(
                        campus_id=campus_id,
                        name=f"School {campus_id}",
                        code=f"SCH-{campus_id}",
                    )
                )
            await session.commit()
        finally:
            await gen.aclose()

        await _seed_api_admin(
            api_client, "regionadmin_api", "region_admin",
            AssignmentNodeType.REGION.value, ids["region_1a1"],
        )
        headers = await _api_login(api_client, "regionadmin_api")

        # Listing without a campus filter shows only the region's campus.
        listed = await api_client.get("/api/institution/schools", headers=headers)
        assert listed.status_code == 200, listed.text
        items = listed.json()["items"]
        assert len(items) == 1
        assert items[0]["campus_id"] == ids["campus_11"]

        # Filtering by a foreign campus is denied outright.
        denied = await api_client.get(
            "/api/institution/schools", headers=headers,
            params={"campus_id": ids["campus_13"]},
        )
        assert denied.status_code == 403, denied.text
