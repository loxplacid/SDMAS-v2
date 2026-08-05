"""Tests for Phase 4.7 business-event notification integration.

Covers:
- Batch operation completion notifications (success + failure counts)
- DB-level deduplication via ``event_key`` (survives duplicate dispatches)
- Admin fan-out for system-wide events (no target user)
- Rollover failure notification handler
- Transaction isolation: notification failures never break business ops
- User scoping / authorization regression
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.notifications import dispatcher as global_dispatcher
from app.domains.notifications.channels import ChannelMessage, InAppChannel
from app.domains.notifications.events import (
    BatchOperationCompletedEvent,
    FeeDueCreatedEvent,
    ImportantAdminEvent,
)
from app.domains.notifications.handlers import (
    handle_batch_operation_completed,
    handle_fee_due_created,
    handle_important_admin,
)
from app.domains.notifications.models import Notification
from app.domains.notifications.repository import NotificationRepository
from app.domains.reports.batch_service import BatchService
from app.multi_tenant.models import platform_context


# ===========================================================================
# Batch operation notifications
# ===========================================================================


class TestBatchNotifications:
    async def test_batch_handler_creates_notification_for_target_user(
        self, db_session: AsyncSession
    ) -> None:
        """A completed batch op creates an in-app notification for the actor."""
        from app.domains.notifications.events import EventDispatcher

        dispatcher = EventDispatcher()
        dispatcher.register(BatchOperationCompletedEvent, handle_batch_operation_completed)

        event = BatchOperationCompletedEvent(
            operation_type="batch_enroll",
            total_processed=10,
            success_count=8,
            error_count=2,
            summary="8/10 enrolled",
            target_user_id=101,
            event_key="batch_enroll:run-1",
        )
        await dispatcher.dispatch(event, session=db_session)

        repo = NotificationRepository(db_session, platform_context())
        items, total = await repo.find_by_user(101)
        assert total == 1
        assert items[0].type == "system"
        assert "Batch Operation Complete" in items[0].title
        assert "8/10" in items[0].message

    async def test_batch_handler_skips_without_target_user(
        self, db_session: AsyncSession
    ) -> None:
        """Without a target user the handler logs only (no orphan broadcasts)."""
        from app.domains.notifications.events import EventDispatcher

        dispatcher = EventDispatcher()
        dispatcher.register(BatchOperationCompletedEvent, handle_batch_operation_completed)

        event = BatchOperationCompletedEvent(
            operation_type="batch_fee_dues",
            total_processed=5,
            success_count=5,
            error_count=0,
        )
        await dispatcher.dispatch(event, session=db_session)

        repo = NotificationRepository(db_session, platform_context())
        _, total = await repo.find_by_user(99999)
        assert total == 0

    async def test_batch_service_dispatches_completion_event(
        self, db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """BatchService enqueues a durable BatchOperationCompletedEvent."""
        from app.domains.academic.models import AcademicYear
        from app.domains.events.outbox import OutboxEvent
        from datetime import date
        from sqlalchemy import select

        year = AcademicYear(
            name="Integration Year",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            status="active",
        )
        db_session.add(year)
        await db_session.flush()

        service = BatchService(db_session, platform_context())
        # Empty payload: batch completes with zero processed.
        result = await service.batch_enroll(year.id, [], actor_user_id=42)
        assert result["total"] == 0

        rows = (
            await db_session.execute(
                select(OutboxEvent).where(
                    OutboxEvent.event_type == "BatchOperationCompletedEvent"
                )
            )
        ).scalars().all()
        assert len(rows) == 1
        ev = rows[0]
        payload = ev.payload or {}
        assert payload["operation_type"] == "batch_enroll"
        assert payload["target_user_id"] == 42
        assert payload["total_processed"] == 0
        assert payload["event_key"] and payload["event_key"].startswith("batch_enroll:")
        assert ev.event_id == payload["event_key"]

    async def test_batch_notification_failure_does_not_break_batch(
        self, db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """A durable-publish failure must not fail the batch op itself."""
        from app.domains.academic.models import AcademicYear
        from datetime import date

        year = AcademicYear(
            name="Isolation Year",
            start_date=date(2026, 1, 1),
            end_date=date(2026, 12, 31),
            status="active",
        )
        db_session.add(year)
        await db_session.flush()

        async def boom(*args, **kwargs):
            raise RuntimeError("outbox infra down")

        monkeypatch.setattr(
            "app.domains.reports.batch_service.publish_durable",
            boom,
        )

        service = BatchService(db_session, platform_context())
        result = await service.batch_create_fee_dues(year.id, [], actor_user_id=1)
        assert result["total"] == 0
        assert result["succeeded"] == 0


# ===========================================================================
# Deduplication
# ===========================================================================


class TestDedup:
    async def test_in_app_channel_dedups_same_event_key(
        self, db_session: AsyncSession
    ) -> None:
        channel = InAppChannel(db_session)
        msg = ChannelMessage(
            user_id=1,
            event_type="fee",
            title="Fee Dues Created",
            message="2 dues totalling 1500",
            data={},
            event_key="fee_due:1:2026",
        )
        assert await channel.deliver(msg) is True
        # Duplicate delivery of the same event -> skipped.
        assert await channel.deliver(msg) is False

        repo = NotificationRepository(db_session, platform_context())
        _, total = await repo.find_by_user(1)
        assert total == 1

    async def test_different_event_keys_create_separate_notifications(
        self, db_session: AsyncSession
    ) -> None:
        channel = InAppChannel(db_session)
        for key in ("fee_due:1:2026", "payment:99"):
            msg = ChannelMessage(
                user_id=1,
                event_type="fee",
                title="Notification",
                message="body",
                event_key=key,
            )
            await channel.deliver(msg)

        repo = NotificationRepository(db_session, platform_context())
        _, total = await repo.find_by_user(1)
        assert total == 2

    async def test_fee_due_duplicate_dispatch_single_notification(
        self, db_session: AsyncSession
    ) -> None:
        """Dispatching the same fee-due event twice yields one notification."""
        from app.domains.notifications.events import EventDispatcher

        dispatcher = EventDispatcher()
        dispatcher.register(FeeDueCreatedEvent, handle_fee_due_created)

        event = FeeDueCreatedEvent(
            student_id=1,
            academic_year_id=2026,
            due_ids=[1, 2],
            total_amount=1500.0,
            due_count=2,
        )
        await dispatcher.dispatch(event, session=db_session)
        await dispatcher.dispatch(event, session=db_session)

        repo = NotificationRepository(db_session, platform_context())
        items, total = await repo.find_by_user(1)
        assert total == 1

    async def test_read_notification_allows_new_same_event(
        self, db_session: AsyncSession
    ) -> None:
        """Once read, a later occurrence of the same event may notify again."""
        channel = InAppChannel(db_session)
        msg = ChannelMessage(
            user_id=1, event_type="fee", title="T", message="m",
            event_key="fee_due:1:2026",
        )
        await channel.deliver(msg)

        repo = NotificationRepository(db_session, platform_context())
        items, _ = await repo.find_by_user(1)
        await repo.mark_read(items[0].id)

        # A fresh occurrence after read -> new notification.
        assert await channel.deliver(msg) is True
        _, total = await repo.find_by_user(1)
        assert total == 2


# ===========================================================================
# Admin fan-out
# ===========================================================================


class TestAdminFanOut:
    async def _seed_users(
        self, db_session: AsyncSession
    ) -> dict[int, str]:
        from app.domains.auth.models import User
        from app.domains.auth.security import hash_password

        roles = {1: "admin", 2: "staff", 3: "teacher"}
        for uid, role in roles.items():
            db_session.add(
                User(
                    username=f"user{uid}",
                    email=f"user{uid}@test.local",
                    password_hash=hash_password("AdminPass123!"),
                    display_name=f"User {uid}",
                    role=role,
                    is_active=True,
                )
            )
        await db_session.flush()
        return roles

    async def test_important_admin_fans_out_to_admin_and_staff(
        self, db_session: AsyncSession
    ) -> None:
        roles = await self._seed_users(db_session)
        from app.domains.notifications.events import EventDispatcher

        dispatcher = EventDispatcher()
        dispatcher.register(ImportantAdminEvent, handle_important_admin)

        event = ImportantAdminEvent(
            event_type="rollover_completed",
            title="Rollover Complete",
            message="Rollover finished",
            metadata={"new_year_id": 10},
        )
        await dispatcher.dispatch(event, session=db_session)

        repo = NotificationRepository(db_session, platform_context())
        for uid, role in roles.items():
            _, total = await repo.find_by_user(uid)
            if role in ("admin", "staff"):
                assert total == 1, f"{role} user {uid} should be notified"
            else:
                assert total == 0, f"teacher {uid} should NOT be notified"

    async def test_important_admin_target_user_only(
        self, db_session: AsyncSession
    ) -> None:
        await self._seed_users(db_session)
        from app.domains.notifications.events import EventDispatcher

        dispatcher = EventDispatcher()
        dispatcher.register(ImportantAdminEvent, handle_important_admin)

        event = ImportantAdminEvent(
            event_type="workflow_approved",
            title="Approved",
            message="Your request was approved",
            target_user_id=3,
        )
        await dispatcher.dispatch(event, session=db_session)

        repo = NotificationRepository(db_session, platform_context())
        _, total = await repo.find_by_user(3)
        assert total == 1
        _, admin_total = await repo.find_by_user(1)
        assert admin_total == 0

    async def test_rollover_failed_handler_notifies_admins(
        self, db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """AcademicYearRolloverFailedEvent produces an admin notification."""
        await self._seed_users(db_session)

        # Fresh dispatchers to avoid cross-test global state.
        from app.domains.events.dispatcher import DomainEventDispatcher
        from app.domains.events.events import AcademicYearRolloverFailedEvent
        from app.domains.events.handlers import handle_rollover_failed_notification
        from app.domains.notifications.events import EventDispatcher

        event_bus = DomainEventDispatcher()
        event_bus.register(
            AcademicYearRolloverFailedEvent, handle_rollover_failed_notification
        )

        notif_dispatcher = EventDispatcher()
        notif_dispatcher.register(ImportantAdminEvent, handle_important_admin)

        monkeypatch.setattr(
            "app.domains.events.handlers.notification_dispatcher",
            notif_dispatcher,
        )

        await event_bus.publish(
            AcademicYearRolloverFailedEvent(
                previous_year_id=1,
                new_year_name="2027-28",
                error="Duplicate year",
            ),
            session=db_session,
        )

        repo = NotificationRepository(db_session, platform_context())
        items, total = await repo.find_by_user(1)  # admin
        assert total >= 1
        assert any("Rollover Failed" in n.title for n in items)

    async def test_rollover_completed_fans_out_to_admins(
        self, db_session: AsyncSession,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        """The existing rollover-completed path now reaches admins via fan-out."""
        await self._seed_users(db_session)

        from app.domains.events.dispatcher import DomainEventDispatcher
        from app.domains.events.events import AcademicYearRolloverCompletedEvent
        from app.domains.events.handlers import handle_rollover_completed_notification
        from app.domains.notifications.events import EventDispatcher

        event_bus = DomainEventDispatcher()
        event_bus.register(
            AcademicYearRolloverCompletedEvent,
            handle_rollover_completed_notification,
        )

        notif_dispatcher = EventDispatcher()
        notif_dispatcher.register(ImportantAdminEvent, handle_important_admin)

        monkeypatch.setattr(
            "app.domains.events.handlers.notification_dispatcher",
            notif_dispatcher,
        )

        await event_bus.publish(
            AcademicYearRolloverCompletedEvent(
                previous_year_id=1,
                new_year_id=2,
                new_year_name="2027-28",
                students_rolled=5,
                classes_migrated=2,
            ),
            session=db_session,
        )

        repo = NotificationRepository(db_session, platform_context())
        items, total = await repo.find_by_user(1)
        assert total >= 1
        assert any("Rollover Complete" in n.title for n in items)


# ===========================================================================
# Transaction isolation & scoping (regression)
# ===========================================================================


class TestIsolationAndScoping:
    async def test_handler_failure_does_not_block_other_handlers(
        self, db_session: AsyncSession
    ) -> None:
        from app.domains.notifications.events import DomainEvent, EventDispatcher

        dispatcher = EventDispatcher()

        async def failing(event: DomainEvent, **kwargs) -> None:
            raise RuntimeError("boom")

        called = []

        async def succeeding(event: DomainEvent, **kwargs) -> None:
            called.append(True)

        dispatcher.register(FeeDueCreatedEvent, failing)
        dispatcher.register(FeeDueCreatedEvent, succeeding)

        await dispatcher.dispatch(
            FeeDueCreatedEvent(student_id=1, academic_year_id=2026),
            session=db_session,
        )
        assert called == [True]

    async def test_notification_scoped_to_recipient_user(
        self, api_client,
    ) -> None:
        """A user cannot read or delete another user's notification."""
        # Seed two users and a notification for user 1 through the app session.
        from sqlalchemy import select

        from app.domains.auth.models import User
        from app.domains.auth.security import hash_password
        from app.infrastructure.database import get_session
        from app.main import app

        async def _seed(session: AsyncSession) -> None:
            existing = await session.execute(
                select(User).where(User.username == "user_a")
            )
            if existing.scalar_one_or_none() is None:
                session.add_all(
                    [
                        User(
                            username="user_a",
                            email="a@test.local",
                            password_hash=hash_password("AdminPass123!"),
                            display_name="User A",
                            role="staff",
                        ),
                        User(
                            username="user_b",
                            email="b@test.local",
                            password_hash=hash_password("AdminPass123!"),
                            display_name="User B",
                            role="staff",
                        ),
                    ]
                )
                await session.flush()
                a = (
                    await session.execute(
                        select(User).where(User.username == "user_a")
                    )
                ).scalar_one()
                b = (
                    await session.execute(
                        select(User).where(User.username == "user_b")
                    )
                ).scalar_one()
                # Default-deny tenant architecture: grant both users a
                # Campus A (id=1) membership so require_tenant_context
                # resolves instead of 403-ing campus-less staff users.
                from app.domains.auth.models import UserSchoolMembership

                session.add_all(
                    [
                        UserSchoolMembership(
                            user_id=a.id,
                            campus_id=1,
                            role="staff",
                            is_default=True,
                            is_active=True,
                        ),
                        UserSchoolMembership(
                            user_id=b.id,
                            campus_id=1,
                            role="staff",
                            is_default=True,
                            is_active=True,
                        ),
                    ]
                )
                await session.flush()
                a.campus_id = 1
                b.campus_id = 1
                session.add(
                    Notification(
                        user_id=a.id,
                        type="system",
                        title="Secret",
                        message="for A only",
                        campus_id=1,
                    )
                )
                await session.commit()

        override = app.dependency_overrides[get_session]
        gen = override()
        try:
            session = await gen.__anext__()
            await _seed(session)
        finally:
            await gen.aclose()

        # Login as user A and B.
        async def _login(username: str) -> str:
            resp = await api_client.post(
                "/auth/login",
                json={"login": username, "password": "AdminPass123!"},
            )
            assert resp.status_code == 200
            return resp.json()["access_token"]

        token_a = await _login("user_a")
        token_b = await _login("user_b")

        list_a = await api_client.get(
            "/api/notifications",
            headers={"Authorization": f"Bearer {token_a}"},
        )
        assert list_a.status_code == 200
        notif_id = list_a.json()["items"][0]["id"]

        # User B cannot see or mutate A's notification.
        list_b = await api_client.get(
            "/api/notifications",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert list_b.status_code == 200
        assert not list_b.json()["items"]

        read_b = await api_client.patch(
            f"/api/notifications/{notif_id}/read",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert read_b.status_code == 404

        del_b = await api_client.delete(
            f"/api/notifications/{notif_id}",
            headers={"Authorization": f"Bearer {token_b}"},
        )
        assert del_b.status_code == 404
