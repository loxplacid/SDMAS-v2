from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.notifications.models import Notification
from app.domains.notifications.service import NotificationService


async def _create_test_notifications(
    svc: NotificationService, count: int, user_id: int = 1
) -> list[Notification]:
    results: list[Notification] = []
    for i in range(count):
        n = await svc.create_notification(
            user_id=user_id,
            type="info",
            title=f"Notification {i}",
            message=f"Message {i}",
        )
        results.append(n)
    return results


async def test_create_notification(db_session: AsyncSession) -> None:
    svc = NotificationService(db_session)
    n = await svc.create_notification(
        user_id=1,
        type="info",
        title="Test Notification",
        message="This is a test",
        data={"key": "value"},
    )
    assert n.id is not None
    assert n.title == "Test Notification"
    assert n.message == "This is a test"
    assert n.type == "info"
    assert n.data == {"key": "value"}
    assert n.user_id == 1
    assert n.read_at is None


async def test_notification_defaults(db_session: AsyncSession) -> None:
    svc = NotificationService(db_session)
    n = await svc.create_notification(
        user_id=1,
        type="alert",
        title="Simple",
        message="No data",
    )
    assert n.data is None
    assert n.read_at is None
    assert n.created_at is not None


async def test_list_notifications(db_session: AsyncSession) -> None:
    svc = NotificationService(db_session)
    await _create_test_notifications(svc, 5)

    items, total = await svc.get_user_notifications(user_id=1, limit=50)
    assert total == 5
    assert len(items) == 5
    assert items[0].title == "Notification 4"


async def test_list_notifications_pagination(db_session: AsyncSession) -> None:
    svc = NotificationService(db_session)
    await _create_test_notifications(svc, 10)

    page1, total = await svc.get_user_notifications(user_id=1, skip=0, limit=3)
    assert total == 10
    assert len(page1) == 3
    assert page1[0].title == "Notification 9"

    page2, _ = await svc.get_user_notifications(user_id=1, skip=3, limit=3)
    assert len(page2) == 3
    assert page2[0].title == "Notification 6"


async def test_unread_count(db_session: AsyncSession) -> None:
    svc = NotificationService(db_session)
    assert await svc.get_unread_count(1) == 0

    n = await svc.create_notification(
        user_id=1, type="info", title="Unread", message="Unread"
    )
    assert await svc.get_unread_count(1) == 1

    await svc.mark_as_read(n.id)
    assert await svc.get_unread_count(1) == 0


async def test_unread_only_filter(db_session: AsyncSession) -> None:
    svc = NotificationService(db_session)
    n1 = await svc.create_notification(
        user_id=1, type="info", title="Read me", message="Read me"
    )
    await svc.create_notification(
        user_id=1, type="info", title="Keep unread", message="Keep unread"
    )

    await svc.mark_as_read(n1.id)

    items, total = await svc.get_user_notifications(
        user_id=1, unread_only=True, limit=50
    )
    assert total == 1
    assert items[0].title == "Keep unread"


async def test_mark_as_read(db_session: AsyncSession) -> None:
    svc = NotificationService(db_session)
    n = await svc.create_notification(
        user_id=1, type="info", title="Read me", message="Read me"
    )
    assert n.read_at is None

    updated = await svc.mark_as_read(n.id)
    assert updated.read_at is not None


async def test_mark_all_as_read(db_session: AsyncSession) -> None:
    svc = NotificationService(db_session)
    await _create_test_notifications(svc, 3)

    updated_count = await svc.mark_all_as_read(user_id=1)
    assert updated_count == 3
    assert await svc.get_unread_count(1) == 0


async def test_delete_notification(db_session: AsyncSession) -> None:
    svc = NotificationService(db_session)
    n = await svc.create_notification(
        user_id=1, type="info", title="Delete me", message="Delete me"
    )
    assert await svc.get_unread_count(1) == 1

    await svc.delete_notification(n.id)
    assert await svc.get_unread_count(1) == 0


async def test_notification_is_read_property(db_session: AsyncSession) -> None:
    svc = NotificationService(db_session)
    n = await svc.create_notification(
        user_id=1, type="info", title="Test", message="Test"
    )
    assert not n.is_read

    updated = await svc.mark_as_read(n.id)
    assert updated.is_read
