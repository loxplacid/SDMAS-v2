"""Tests for the event-driven notification system.

Coverage:
- Event dataclass creation and field access
- EventDispatcher registration / dispatch / clear
- Template rendering
- Preference model, repository, service
- Channel delivery (in-app creates a Notification record)
- Handler integration with session
- Full integration: event → handler → channel → DB record
"""

from __future__ import annotations

import asyncio

import pytest

from app.domains.notifications.events import (
    AcademicYearRolloverEvent,
    BatchOperationCompletedEvent,
    DomainEvent,
    EventDispatcher,
    FeeDueCreatedEvent,
    ImportantAdminEvent,
    LowAttendanceEvent,
    PaymentReceivedEvent,
)
from app.domains.notifications.preferences import (
    CHANNEL_IN_APP,
    NotificationPreference,
    NotificationPreferenceRepository,
    NotificationPreferenceService,
)
from app.domains.notifications.templates import get_templates, render_all
from app.domains.notifications.channels import (
    ChannelMessage,
    InAppChannel,
    EmailChannel,
    get_channel,
)
from app.domains.notifications.models import Notification
from app.multi_tenant.models import platform_context


# ===========================================================================
# Event dataclass tests
# ===========================================================================


class TestDomainEvents:
    def test_fee_due_created_event(self):
        event = FeeDueCreatedEvent(
            student_id=1,
            academic_year_id=2026,
            due_ids=[10, 11],
            total_amount=1500.0,
            due_count=2,
        )
        assert event.student_id == 1
        assert event.total_amount == 1500.0
        assert event.due_count == 2

    def test_payment_received_event(self):
        event = PaymentReceivedEvent(
            student_id=1,
            fee_due_id=10,
            payment_id=100,
            amount=500.0,
            payment_method="cash",
            receipt_number="RCP-001",
            new_due_status="partially_paid",
        )
        assert event.amount == 500.0
        assert event.receipt_number == "RCP-001"

    def test_low_attendance_event(self):
        event = LowAttendanceEvent(
            student_id=1,
            academic_year_id=2026,
            attendance_percentage=60.0,
            threshold=75.0,
            total_absences=10,
        )
        assert event.attendance_percentage == 60.0
        assert event.total_absences == 10

    def test_tenant_id_position(self):
        """tenant_id (with default) must follow required fields in subclasses."""
        event = FeeDueCreatedEvent(student_id=1, academic_year_id=2026)
        assert event.tenant_id is None

        event = FeeDueCreatedEvent(
            student_id=1, academic_year_id=2026, tenant_id=42
        )
        assert event.tenant_id == 42


# ===========================================================================
# EventDispatcher tests
# ===========================================================================


class TestEventDispatcher:
    async def test_dispatch_calls_registered_handler(self):
        dispatcher = EventDispatcher()
        calls = []

        async def handler(event: DomainEvent, **kwargs) -> None:
            calls.append(event)

        dispatcher.register(FeeDueCreatedEvent, handler)
        event = FeeDueCreatedEvent(student_id=1, academic_year_id=2026)
        await dispatcher.dispatch(event)

        assert len(calls) == 1
        assert calls[0] is event

    async def test_dispatch_no_handlers_does_not_error(self):
        dispatcher = EventDispatcher()
        event = FeeDueCreatedEvent(student_id=1, academic_year_id=2026)
        await dispatcher.dispatch(event)  # should not raise

    async def test_multiple_handlers_called_in_order(self):
        dispatcher = EventDispatcher()
        order: list[int] = []

        async def h1(event: DomainEvent, **kwargs) -> None:
            order.append(1)

        async def h2(event: DomainEvent, **kwargs) -> None:
            order.append(2)

        dispatcher.register(FeeDueCreatedEvent, h1)
        dispatcher.register(FeeDueCreatedEvent, h2)

        await dispatcher.dispatch(
            FeeDueCreatedEvent(student_id=1, academic_year_id=2026)
        )
        assert order == [1, 2]

    async def test_handler_exception_does_not_block_others(self):
        dispatcher = EventDispatcher()

        async def failing(event: DomainEvent, **kwargs) -> None:
            raise RuntimeError("Boom")

        called = False

        async def succeeding(event: DomainEvent, **kwargs) -> None:
            nonlocal called
            called = True

        dispatcher.register(FeeDueCreatedEvent, failing)
        dispatcher.register(FeeDueCreatedEvent, succeeding)

        await dispatcher.dispatch(
            FeeDueCreatedEvent(student_id=1, academic_year_id=2026)
        )
        assert called, "Second handler should still be called despite first failing"

    async def test_unregister(self):
        dispatcher = EventDispatcher()
        calls = []

        async def handler(event: DomainEvent, **kwargs) -> None:
            calls.append(event)

        dispatcher.register(FeeDueCreatedEvent, handler)
        dispatcher.unregister(FeeDueCreatedEvent, handler)

        await dispatcher.dispatch(
            FeeDueCreatedEvent(student_id=1, academic_year_id=2026)
        )
        assert len(calls) == 0

    async def test_clear(self):
        dispatcher = EventDispatcher()

        async def handler(event: DomainEvent, **kwargs) -> None:
            pass

        dispatcher.register(FeeDueCreatedEvent, handler)
        assert dispatcher.handler_count == 1
        dispatcher.clear()
        assert dispatcher.handler_count == 0

    async def test_handler_count(self):
        dispatcher = EventDispatcher()

        async def h1(event: DomainEvent, **kwargs) -> None:
            pass

        async def h2(event: DomainEvent, **kwargs) -> None:
            pass

        dispatcher.register(FeeDueCreatedEvent, h1)
        dispatcher.register(PaymentReceivedEvent, h2)
        assert dispatcher.handler_count == 2

    async def test_dispatch_async_creates_task(self):
        dispatcher = EventDispatcher()
        calls = []

        async def handler(event: DomainEvent, **kwargs) -> None:
            calls.append(event)

        dispatcher.register(FeeDueCreatedEvent, handler)
        task = dispatcher.dispatch_async(
            FeeDueCreatedEvent(student_id=1, academic_year_id=2026)
        )
        await task
        assert len(calls) == 1

    async def test_dispatch_passes_session_to_handler(self):
        dispatcher = EventDispatcher()
        received_session = None
        fake_session = object()

        async def handler(event: DomainEvent, **kwargs) -> None:
            nonlocal received_session
            received_session = kwargs.get("session")

        dispatcher.register(FeeDueCreatedEvent, handler)
        event = FeeDueCreatedEvent(student_id=1, academic_year_id=2026)
        await dispatcher.dispatch(event, session=fake_session)  # type: ignore[arg-type]

        assert received_session is fake_session

    async def test_dispatch_without_session_does_not_pass_it(self):
        dispatcher = EventDispatcher()
        received_kwargs = None

        async def handler(event: DomainEvent, **kwargs) -> None:
            nonlocal received_kwargs
            received_kwargs = kwargs

        dispatcher.register(FeeDueCreatedEvent, handler)
        await dispatcher.dispatch(
            FeeDueCreatedEvent(student_id=1, academic_year_id=2026)
        )
        assert "session" not in received_kwargs


# ===========================================================================
# Template tests
# ===========================================================================


class TestTemplates:
    def test_get_templates_known_event(self):
        templates = get_templates(FeeDueCreatedEvent)
        assert len(templates) >= 1

    def test_get_templates_unknown_event(self):
        class CustomEvent(DomainEvent):
            pass

        templates = get_templates(CustomEvent)
        assert templates == []

    def test_render_fee_due_created(self):
        event = FeeDueCreatedEvent(
            student_id=1,
            academic_year_id=2026,
            due_count=3,
            total_amount=2500.0,
        )
        rendered = render_all(event)
        assert len(rendered) >= 1
        assert rendered[0]["type"] == "fee"

    def test_render_payment_received(self):
        event = PaymentReceivedEvent(
            student_id=1,
            fee_due_id=10,
            payment_id=100,
            amount=500.0,
            payment_method="cash",
            new_due_status="paid",
        )
        rendered = render_all(event)
        assert len(rendered) >= 1
        assert rendered[0]["type"] == "payment"

    def test_render_low_attendance(self):
        event = LowAttendanceEvent(
            student_id=1,
            academic_year_id=2026,
            attendance_percentage=60.0,
            threshold=75.0,
            total_absences=10,
        )
        rendered = render_all(event)
        assert len(rendered) >= 1
        assert rendered[0]["type"] == "attendance"

    def test_render_important_admin(self):
        event = ImportantAdminEvent(
            event_type="crisis",
            title="System Alert",
            message="Something important happened",
        )
        rendered = render_all(event)
        assert len(rendered) >= 1
        assert rendered[0]["title"] == "System Alert"
        assert rendered[0]["message"] == "Something important happened"


# ===========================================================================
# NotificationPreference tests
# ===========================================================================


class TestNotificationPreference:
    async def test_preference_default_enabled(self, db_session):
        svc = NotificationPreferenceService(db_session)
        assert (
            await svc.is_enabled(
                user_id=1, event_type="fee", channel=CHANNEL_IN_APP
            )
            is True
        )

    async def test_preference_off_for_other_channels(self, db_session):
        svc = NotificationPreferenceService(db_session)
        assert (
            await svc.is_enabled(user_id=1, event_type="fee", channel="email")
            is False
        )

    async def test_upsert_preference(self, db_session):
        svc = NotificationPreferenceService(db_session)
        result = await svc.update_preference(
            user_id=1, event_type="fee", channel="email", enabled=True
        )
        assert result["event_type"] == "fee"
        assert result["channel"] == "email"
        assert result["enabled"] is True

    async def test_preference_respected_after_update(self, db_session):
        svc = NotificationPreferenceService(db_session)
        await svc.update_preference(
            user_id=1, event_type="fee", channel=CHANNEL_IN_APP, enabled=False
        )
        assert (
            await svc.is_enabled(
                user_id=1, event_type="fee", channel=CHANNEL_IN_APP
            )
            is False
        )

    async def test_bulk_update(self, db_session):
        svc = NotificationPreferenceService(db_session)
        prefs = await svc.bulk_update(
            user_id=1,
            preferences=[
                {"event_type": "fee", "channel": "email", "enabled": True},
                {
                    "event_type": "attendance",
                    "channel": "in_app",
                    "enabled": False,
                },
            ],
        )
        assert len(prefs) == 2

    async def test_get_preferences(self, db_session):
        svc = NotificationPreferenceService(db_session)
        await svc.bulk_update(
            user_id=1,
            preferences=[
                {"event_type": "fee", "channel": "email", "enabled": True},
                {
                    "event_type": "attendance",
                    "channel": "in_app",
                    "enabled": True,
                },
            ],
        )
        prefs = await svc.get_preferences(user_id=1)
        assert len(prefs) >= 2

    async def test_repository_upsert_creates_new(self, db_session):
        repo = NotificationPreferenceRepository(db_session)
        pref = await repo.upsert(
            user_id=1, event_type="test_event", channel="in_app", enabled=True
        )
        assert pref.id is not None
        assert pref.enabled is True

    async def test_repository_upsert_updates_existing(self, db_session):
        repo = NotificationPreferenceRepository(db_session)
        pref1 = await repo.upsert(
            user_id=2, event_type="test_event", channel="in_app", enabled=True
        )
        pref2 = await repo.upsert(
            user_id=2, event_type="test_event", channel="in_app", enabled=False
        )
        assert pref2.id == pref1.id
        assert pref2.enabled is False

    async def test_find_by_user(self, db_session):
        repo = NotificationPreferenceRepository(db_session)
        await repo.upsert(
            user_id=3, event_type="fee", channel="in_app", enabled=True
        )
        prefs = await repo.find_by_user(3)
        assert len(prefs) == 1
        assert prefs[0].event_type == "fee"


# ===========================================================================
# Channel tests
# ===========================================================================


class TestChannels:
    async def test_in_app_channel_creates_notification(self, db_session):
        channel = InAppChannel(db_session)
        msg = ChannelMessage(
            user_id=1,
            event_type="test",
            title="Test Title",
            message="Test message body",
            data={"key": "value"},
        )
        result = await channel.deliver(msg)
        assert result is True

        from app.domains.notifications.repository import NotificationRepository

        repo = NotificationRepository(db_session, platform_context())
        items, total = await repo.find_by_user(1)
        assert total >= 1
        assert items[-1].title == "Test Title"

    async def test_email_channel_delivers_to_user(self, db_session):
        """EmailChannel requires a session and delivers via SendGrid."""
        from app.domains.auth.models import User
        from app.domains.auth.repository import UserRepository

        user_repo = UserRepository(db_session)
        user = User(
            email="test@example.com",
            username="testuser",
            display_name="Test User",
            password_hash="fakehash",
            role="student",
        )
        user = await user_repo.create(user)

        channel = EmailChannel(db_session)
        msg = ChannelMessage(
            user_id=user.id,
            event_type="test",
            title="Email Test",
            message="Email body",
        )
        # Without a patched send_email, this will log only (no API key)
        result = await channel.deliver(msg)
        # Since SendGrid is unconfigured in tests, send_email returns True (soft pass)
        assert result is True

    async def test_get_channel_known(self, db_session):
        channel = get_channel("in_app", db_session)
        assert isinstance(channel, InAppChannel)

    async def test_get_channel_unknown(self, db_session):
        with pytest.raises(ValueError, match="Unknown notification channel"):
            get_channel("nonexistent", db_session)


# ===========================================================================
# Handler integration tests
# ===========================================================================


class TestHandlers:
    """Integration tests using a real dispatcher + real session."""

    async def test_fee_due_handler_creates_notification(
        self, db_session
    ):
        """FeeDueCreated handler should create an in-app notification."""
        dispatcher = EventDispatcher()
        from app.domains.notifications.handlers import handle_fee_due_created

        dispatcher.register(FeeDueCreatedEvent, handle_fee_due_created)

        event = FeeDueCreatedEvent(
            student_id=1,
            academic_year_id=2026,
            due_ids=[1],
            total_amount=500.0,
            due_count=1,
        )
        await dispatcher.dispatch(event, session=db_session)

        from app.domains.notifications.repository import NotificationRepository

        repo = NotificationRepository(db_session, platform_context())
        items, total = await repo.find_by_user(1)
        assert total >= 1
        assert any("fee" in n.type or "Fee" in n.title for n in items)

    async def test_payment_handler_creates_notification(
        self, db_session
    ):
        """PaymentReceived handler should create an in-app notification."""
        dispatcher = EventDispatcher()
        from app.domains.notifications.handlers import handle_payment_received

        dispatcher.register(PaymentReceivedEvent, handle_payment_received)

        event = PaymentReceivedEvent(
            student_id=11,
            fee_due_id=10,
            payment_id=100,
            amount=500.0,
            payment_method="cash",
            new_due_status="paid",
        )
        await dispatcher.dispatch(event, session=db_session)

        from app.domains.notifications.repository import NotificationRepository

        repo = NotificationRepository(db_session, platform_context())
        items, total = await repo.find_by_user(11)
        assert total >= 1
        assert any("payment" in n.type or "Payment" in n.title for n in items)

    async def test_low_attendance_handler_creates_notification(
        self, db_session
    ):
        """LowAttendance handler should create an in-app notification."""
        dispatcher = EventDispatcher()
        from app.domains.notifications.handlers import handle_low_attendance

        dispatcher.register(LowAttendanceEvent, handle_low_attendance)

        event = LowAttendanceEvent(
            student_id=12,
            academic_year_id=2026,
            attendance_percentage=50.0,
            threshold=75.0,
            total_absences=15,
        )
        await dispatcher.dispatch(event, session=db_session)

        from app.domains.notifications.repository import NotificationRepository

        repo = NotificationRepository(db_session, platform_context())
        items, total = await repo.find_by_user(12)
        assert total >= 1
        assert any("attendance" in n.type or "Attendance" in n.title for n in items)

    async def test_admin_handler_creates_notification(
        self, db_session
    ):
        """ImportantAdmin handler should notify the target user."""
        dispatcher = EventDispatcher()
        from app.domains.notifications.handlers import handle_important_admin

        dispatcher.register(ImportantAdminEvent, handle_important_admin)

        event = ImportantAdminEvent(
            event_type="user_created",
            title="New User Created",
            message="User test was created",
            target_user_id=13,
        )
        await dispatcher.dispatch(event, session=db_session)

        from app.domains.notifications.repository import NotificationRepository

        repo = NotificationRepository(db_session, platform_context())
        items, total = await repo.find_by_user(13)
        assert total >= 1
        assert any("User" in n.title for n in items)

    async def test_handler_respects_disabled_preference(
        self, db_session
    ):
        """When a user disables a preference, handler should NOT create notifications."""
        dispatcher = EventDispatcher()
        from app.domains.notifications.handlers import handle_fee_due_created

        dispatcher.register(FeeDueCreatedEvent, handle_fee_due_created)

        # Disable in-app notifications for "fee" event type for user 14
        pref_svc = NotificationPreferenceService(db_session)
        await pref_svc.update_preference(
            user_id=14, event_type="fee", channel="in_app", enabled=False
        )

        event = FeeDueCreatedEvent(
            student_id=14,
            academic_year_id=2026,
            due_ids=[1],
            total_amount=500.0,
            due_count=1,
        )
        await dispatcher.dispatch(event, session=db_session)

        from app.domains.notifications.repository import NotificationRepository

        repo = NotificationRepository(db_session, platform_context())
        items, total = await repo.find_by_user(14)
        assert total == 0


# ===========================================================================
# Full integration
# ===========================================================================


class TestFullIntegration:
    """End-to-end test of the event pipeline."""

    async def test_full_pipeline_creates_notification(
        self, db_session
    ):
        """Verify the complete pipeline: register handlers → dispatch → DB record."""
        dispatcher = EventDispatcher()
        from app.domains.notifications.handlers import register_all_handlers

        register_all_handlers(dispatcher)

        event = FeeDueCreatedEvent(
            student_id=20,
            academic_year_id=2026,
            due_ids=[1, 2],
            total_amount=1000.0,
            due_count=2,
        )
        await dispatcher.dispatch(event, session=db_session)

        await asyncio.sleep(0.01)

        from app.domains.notifications.repository import NotificationRepository

        repo = NotificationRepository(db_session, platform_context())
        items, total = await repo.find_by_user(20)
        assert total >= 1

    async def test_register_all_handlers_registers_six(self):
        """register_all_handlers should register all 6 handlers."""
        dispatcher = EventDispatcher()
        from app.domains.notifications.handlers import register_all_handlers

        register_all_handlers(dispatcher)
        assert dispatcher.handler_count == 6
