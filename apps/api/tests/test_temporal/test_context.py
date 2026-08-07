"""Unit tests for TimeContext and ChangeEnvelope (The Archive, M1)."""

from __future__ import annotations

from datetime import datetime, timezone

from app.temporal import ChangeEnvelope, TimeContext


def test_empty_context_is_current() -> None:
    ctx = TimeContext()
    assert ctx.is_temporal is False
    assert ctx.as_of_utc is None
    assert ctx.valid_utc is None


def test_as_of_normalized_to_aware_utc() -> None:
    naive = datetime(2024, 6, 15, 10, 0)
    ctx = TimeContext(as_of=naive)
    assert ctx.is_temporal is True
    assert ctx.as_of_utc == naive.replace(tzinfo=timezone.utc)


def test_valid_instant_normalization() -> None:
    aware = datetime(2024, 6, 15, 12, 0, tzinfo=timezone.utc)
    ctx = TimeContext(valid=aware)
    assert ctx.valid_utc == aware


def test_envelope_json_round_trip() -> None:
    env = ChangeEnvelope.build(
        "update",
        {"name": "Amina", "status": "active"},
        {"name": "Amina", "status": "graduated"},
        actor_id=7,
        reason="graduation ceremony",
    )
    restored = ChangeEnvelope.from_json(env.to_json())
    assert restored.kind == "update"
    assert restored.actor_id == 7
    assert restored.reason == "graduation ceremony"
    assert restored.field_diff() == {
        "status": {"old": "active", "new": "graduated"}
    }


def test_envelope_field_diff_includes_additions() -> None:
    env = ChangeEnvelope.build("create", None, {"name": "Amina"})
    assert env.field_diff() == {"name": {"old": None, "new": "Amina"}}
