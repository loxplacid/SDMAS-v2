"""M1 engine tests: close-open writes, AS-OF readback, atomicity.

The fault-injection test is the centerpiece: it injects a failure into the
*last* statement of a close-open write (the txn_log append) and proves the
already-executed history-close and current-open statements vanish with the
rollback — no partial temporal state can persist.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from sqlalchemy import DateTime, String, select
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base
from app.temporal import TxnManager
from app.temporal.models import TxnLog  # noqa: F401  (registers txn_log)
from app.temporal.registry import TemporalError, registry

T1 = datetime(2024, 6, 1, 9, 0, tzinfo=timezone.utc)
T2 = datetime(2024, 6, 10, 9, 0, tzinfo=timezone.utc)
T3 = datetime(2024, 6, 20, 9, 0, tzinfo=timezone.utc)


class VersionedStudent(Base):
    """Fixture: a versioned current table holding open versions only."""

    __tablename__ = "versioned_student"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    status: Mapped[str] = mapped_column(String(20), nullable=False)
    tt_from: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False
    )
    tt_to: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )


SPEC = registry.register("versioned_student")
HISTORY = Base.metadata.tables["versioned_student_history"]


class FakeClock:
    """Returns the next scheduled instant on every call."""

    def __init__(self, times: list[datetime]) -> None:
        self._times = list(times)

    def __call__(self) -> datetime:
        return self._times.pop(0)


def utc(dt: datetime) -> datetime:
    """Normalize a SQLite-read datetime (naive) to aware UTC.

    SQLite has no timezone support: ``DateTime(timezone=True)`` round-trips
    tz-naive on read (PostgreSQL preserves the tzinfo). The engine only
    compares ranges in SQL, so this is purely an assertion convenience.
    """
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


async def _as_of_state(session, when: datetime) -> dict | None:
    """Manual AS-OF lookup over current + history mirrors (the M2 rewriter
    will automate this; M1 proves the data shape supports it)."""
    closed = (
        await session.execute(
            select(HISTORY).where(
                HISTORY.c.tt_from <= when,
                HISTORY.c.tt_to > when,
            )
        )
    ).mappings().all()
    open_rows = (
        await session.execute(
            select(Base.metadata.tables["versioned_student"]).where(
                Base.metadata.tables["versioned_student"].c.tt_from <= when,
                Base.metadata.tables["versioned_student"].c.tt_to.is_(None),
            )
        )
    ).mappings().all()
    rows = [dict(r) for r in closed + open_rows]
    if not rows:
        return None
    return max(rows, key=lambda r: r["tt_from"])


async def test_create_opens_first_version_and_logs_txn(db_session) -> None:
    txn = TxnManager(clock=FakeClock([T1]))
    txn_id = await txn.create(
        db_session,
        "versioned_student",
        {"name": "Amina Kante", "status": "active"},
        actor_id=7,
        reason="initial enrollment",
        tenant_id=1,
        campus_id=2,
    )
    await db_session.commit()

    row = (await db_session.execute(select(VersionedStudent))).scalar_one()
    assert row.name == "Amina Kante"
    assert utc(row.tt_from) == T1
    assert row.tt_to is None

    log = (await db_session.execute(select(TxnLog))).scalar_one()
    assert log.id == txn_id
    assert log.action == "create"
    assert log.actor_id == 7
    assert log.reason == "initial enrollment"
    assert log.entity_type == "versioned_student"
    assert log.entity_id == str(row.id)
    assert log.tenant_id == 1
    assert log.campus_id == 2
    assert log.change["kind"] == "create"
    assert log.change["old"] is None
    assert log.change["new"]["name"] == "Amina Kante"


async def test_update_closes_previous_version_and_opens_new(db_session) -> None:
    txn = TxnManager(clock=FakeClock([T1, T2]))
    await txn.create(
        db_session, "versioned_student", {"name": "Amina Kante", "status": "active"},
        actor_id=7,
    )
    await db_session.commit()
    student_id = (
        await db_session.execute(select(VersionedStudent))
    ).scalar_one().id

    await txn.update(
        db_session,
        "versioned_student",
        student_id,
        {"name": "Amina Kante", "status": "graduated"},
        actor_id=7,
        reason="graduation",
    )
    await db_session.commit()

    current = (await db_session.execute(select(VersionedStudent))).scalar_one()
    assert current.status == "graduated"
    assert utc(current.tt_from) == T2
    assert current.tt_to is None

    closed = (await db_session.execute(select(HISTORY))).mappings().all()
    assert len(closed) == 1
    assert closed[0]["entity_id"] == student_id
    assert closed[0]["status"] == "active"
    assert utc(closed[0]["tt_from"]) == T1
    assert utc(closed[0]["tt_to"]) == T2

    update_log = (
        await db_session.execute(select(TxnLog).where(TxnLog.action == "update"))
    ).scalar_one()
    assert update_log.change["old"]["status"] == "active"
    assert update_log.change["new"]["status"] == "graduated"
    assert update_log.change["reason"] == "graduation"


async def test_delete_closes_version_and_removes_open(db_session) -> None:
    txn = TxnManager(clock=FakeClock([T1, T2]))
    await txn.create(
        db_session, "versioned_student", {"name": "Amina Kante", "status": "active"},
        actor_id=7,
    )
    await db_session.commit()
    student_id = (
        await db_session.execute(select(VersionedStudent))
    ).scalar_one().id

    await txn.delete(
        db_session, "versioned_student", student_id, actor_id=9, reason="withdrawn"
    )
    await db_session.commit()

    assert (
        await db_session.execute(select(VersionedStudent))
    ).scalar_one_or_none() is None
    closed = (await db_session.execute(select(HISTORY))).mappings().all()
    assert len(closed) == 1
    assert utc(closed[0]["tt_to"]) == T2

    delete_log = (
        await db_session.execute(select(TxnLog).where(TxnLog.action == "delete"))
    ).scalar_one()
    assert delete_log.change["new"] is None
    assert delete_log.change["old"]["status"] == "active"


async def test_as_of_readback_resolves_each_version(db_session) -> None:
    txn = TxnManager(clock=FakeClock([T1, T2, T3]))
    await txn.create(
        db_session, "versioned_student", {"name": "Amina", "status": "active"},
        actor_id=7,
    )
    await db_session.commit()
    student_id = (
        await db_session.execute(select(VersionedStudent))
    ).scalar_one().id

    await txn.update(
        db_session, "versioned_student", student_id,
        {"name": "Amina", "status": "graduated"}, actor_id=7,
    )
    await db_session.commit()
    await txn.update(
        db_session, "versioned_student", student_id,
        {"name": "Amina K.", "status": "graduated"}, actor_id=7,
    )
    await db_session.commit()

    before = datetime(2024, 5, 1, tzinfo=timezone.utc)
    assert await _as_of_state(db_session, before) is None

    mid_1 = datetime(2024, 6, 5, tzinfo=timezone.utc)
    assert (await _as_of_state(db_session, mid_1))["status"] == "active"

    mid_2 = datetime(2024, 6, 15, tzinfo=timezone.utc)
    state = await _as_of_state(db_session, mid_2)
    assert state["status"] == "graduated"
    assert state["name"] == "Amina"

    later = datetime(2024, 7, 1, tzinfo=timezone.utc)
    assert (await _as_of_state(db_session, later))["name"] == "Amina K."


async def test_update_of_unknown_row_raises(db_session) -> None:
    txn = TxnManager(clock=FakeClock([T2]))
    with pytest.raises(TemporalError, match="no row with id=999"):
        await txn.update(
            db_session, "versioned_student", 999,
            {"name": "X", "status": "active"},
        )


async def test_fault_injection_rolls_back_atomically(db_session) -> None:
    """Prove current + history + txn_log commit as one unit.

    The failure is injected into the *last* statement (txn_log append), so
    the history-close and current-open statements have already executed
    in-transaction. After rollback, none of them may persist.
    """
    txn = TxnManager(clock=FakeClock([T1]))
    await txn.create(
        db_session, "versioned_student", {"name": "Amina", "status": "active"},
        actor_id=7,
    )
    await db_session.commit()
    student_id = (
        await db_session.execute(select(VersionedStudent))
    ).scalar_one().id

    async def boom(session, txn_log, payload):
        raise RuntimeError("injected failure after close+open statements")

    failing = TxnManager(clock=FakeClock([T2]))
    failing._append_txn_log = boom  # type: ignore[method-assign]
    with pytest.raises(RuntimeError, match="injected"):
        await failing.update(
            db_session, "versioned_student", student_id,
            {"name": "X", "status": "active"}, actor_id=7,
        )
    await db_session.rollback()

    row = (await db_session.execute(select(VersionedStudent))).scalar_one()
    assert row.name == "Amina"
    assert row.status == "active"
    assert utc(row.tt_from) == T1
    assert (
        await db_session.execute(select(HISTORY))
    ).scalar_one_or_none() is None
    assert len((await db_session.execute(select(TxnLog))).all()) == 1
