"""Tests for the audit logging service and repository."""

from __future__ import annotations

import json

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.audit.models import AuditLog
from app.domains.audit.repository import AuditLogRepository
from app.domains.audit.service import AuditService


# ======================================================================
# AuditLogRepository tests
# ======================================================================


class TestAuditLogRepository:
    async def test_create_entry(self, db_session: AsyncSession):
        repo = AuditLogRepository(db_session)
        entry = AuditLog(
            action="CREATE",
            resource_type="student",
            resource_id="42",
        )
        created = await repo.create(entry)
        assert created.id is not None
        assert created.action == "CREATE"

    async def test_get_by_id_found(self, db_session: AsyncSession):
        repo = AuditLogRepository(db_session)
        entry = AuditLog(action="DELETE", resource_type="fee_type", resource_id="7")
        created = await repo.create(entry)

        found = await repo.get_by_id(created.id)
        assert found.id == created.id
        assert found.action == "DELETE"

    async def test_get_by_id_not_found(self, db_session: AsyncSession):
        repo = AuditLogRepository(db_session)
        from app.core.exceptions import NotFoundError

        with pytest.raises(NotFoundError):
            await repo.get_by_id(999)

    async def test_list_with_filters(self, db_session: AsyncSession):
        repo = AuditLogRepository(db_session)
        for i in range(3):
            await repo.create(
                AuditLog(
                    user_id=1, action="CREATE",
                    resource_type="student", resource_id=str(i),
                )
            )
        await repo.create(
            AuditLog(
                user_id=2, action="DELETE",
                resource_type="fee", resource_id="1",
            )
        )

        # Filter by user_id
        items, total = await repo.list(user_id=1)
        assert total == 3
        assert len(items) == 3

        # Filter by action
        items, total = await repo.list(action="DELETE")
        assert total == 1

        # Filter by resource_type
        items, total = await repo.list(resource_type="fee")
        assert total == 1

    async def test_list_pagination(self, db_session: AsyncSession):
        repo = AuditLogRepository(db_session)
        for i in range(10):
            await repo.create(
                AuditLog(
                    action="UPDATE", resource_type="student",
                    resource_id=str(i),
                )
            )

        items, total = await repo.list(skip=0, limit=5)
        assert total == 10
        assert len(items) == 5

        items, total = await repo.list(skip=5, limit=5)
        assert total == 10
        assert len(items) == 5

    async def test_list_empty(self, db_session: AsyncSession):
        repo = AuditLogRepository(db_session)
        items, total = await repo.list()
        assert total == 0
        assert items == []

    async def test_list_ordered_by_created_at_desc(self, db_session: AsyncSession):
        repo = AuditLogRepository(db_session)
        import datetime
        from datetime import timezone

        entries = []
        for i in range(5):
            e = AuditLog(
                action="CREATE", resource_type="test",
                resource_id=str(i),
                created_at=datetime.datetime.now(timezone.utc),
            )
            entries.append(await repo.create(e))

        items, total = await repo.list()
        # Most recent first
        assert items[0].id >= items[-1].id


# ======================================================================
# AuditService tests
# ======================================================================


class TestAuditService:
    async def test_record_minimal(self, db_session: AsyncSession):
        svc = AuditService(db_session)
        entry = await svc.record(
            action="CREATE",
            resource_type="student",
        )
        assert entry.id is not None
        assert entry.action == "CREATE"
        assert entry.resource_type == "student"

    async def test_record_full(self, db_session: AsyncSession):
        svc = AuditService(db_session)
        entry = await svc.record(
            user_id=1,
            username="admin",
            action="UPDATE",
            resource_type="fee_type",
            resource_id="5",
            details={"before": {"amount": 100}, "after": {"amount": 150}},
            ip_address="192.168.1.1",
            user_agent="TestAgent/1.0",
            campus_id=2,
        )
        assert entry.user_id == 1
        assert entry.username == "admin"
        assert entry.action == "UPDATE"
        assert entry.resource_type == "fee_type"
        assert entry.resource_id == "5"
        assert json.loads(entry.details) == {"before": {"amount": 100}, "after": {"amount": 150}}
        assert entry.ip_address == "192.168.1.1"
        assert entry.user_agent == "TestAgent/1.0"
        assert entry.campus_id == 2

    async def test_record_no_details(self, db_session: AsyncSession):
        svc = AuditService(db_session)
        entry = await svc.record(
            action="DELETE", resource_type="student", resource_id="10",
        )
        assert entry.details is None

    async def test_list_entries(self, db_session: AsyncSession):
        svc = AuditService(db_session)
        for i in range(5):
            await svc.record(
                user_id=1, action="CREATE",
                resource_type="student", resource_id=str(i),
            )

        items, total = await svc.list_entries(user_id=1)
        assert total == 5
        assert len(items) == 5

    async def test_get_entry(self, db_session: AsyncSession):
        svc = AuditService(db_session)
        created = await svc.record(action="CREATE", resource_type="test")
        found = await svc.get_entry(created.id)
        assert found.id == created.id
