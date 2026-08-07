"""Lever semantics — every product-brief lever applies deterministically.

Each test asserts the *pure* effect of a lever on the snapshot (the forecast
models that consume the changed fields are covered in ``test_models.py``).
"""

from __future__ import annotations

import pytest

from app.simulation.model.lever import (
    AddBuses,
    ChangeSchedule,
    ClassSizeChange,
    MergeClasses,
    RemoveTeacher,
)
from app.simulation.snapshot.snapshot import Schedule, SimulationSnapshot
from tests.test_simulation.test_revenue import make_snapshot


class TestRemoveTeacher:
    def test_removes_teacher(self) -> None:
        updated = RemoveTeacher(teacher_id=3).apply(make_snapshot())
        assert [t.teacher_id for t in updated.teachers] == [1, 2, 4]

    def test_unknown_teacher_raises(self) -> None:
        with pytest.raises(ValueError, match="not in snapshot"):
            RemoveTeacher(teacher_id=99).validate(make_snapshot())


class TestAddBuses:
    def test_increments_fleet(self) -> None:
        updated = AddBuses(count=2).apply(make_snapshot())
        assert updated.fleet_size == 4

    def test_negative_count_raises(self) -> None:
        with pytest.raises(ValueError, match=">= 0"):
            AddBuses(count=-1).validate(make_snapshot())


class TestChangeSchedule:
    def test_updates_only_given_fields(self) -> None:
        updated = ChangeSchedule(periods_per_day=9).apply(make_snapshot())
        assert updated.schedule.periods_per_day == 9
        assert updated.schedule.day_start == "08:30"
        assert updated.schedule.period_minutes == 45

    def test_invalid_periods_raise(self) -> None:
        with pytest.raises(ValueError, match="periods_per_day"):
            ChangeSchedule(periods_per_day=0).validate(make_snapshot())


class TestClassSizeChange:
    def test_caps_oversized_sections(self) -> None:
        updated = ClassSizeChange(cap=22).apply(make_snapshot())
        # grade 1 (25 students/section) is capped; grade 2 (20) is untouched.
        assert updated.section_sizes == {1: 22, 2: 20}
        # Rebalancing: grade 1 now needs ceil(50/22) = 3 sections.
        assert updated.sections_for(1) == 3

    def test_invalid_cap_raises(self) -> None:
        with pytest.raises(ValueError, match="> 0"):
            ClassSizeChange(cap=0).validate(make_snapshot())


class TestMergeClasses:
    def test_merges_into_target(self) -> None:
        updated = MergeClasses(source_grade=1, target_grade=2).apply(make_snapshot())
        assert updated.enrollment == {2: 90}
        assert updated.fee_rate == {2: 120_000}  # target rate wins
        assert updated.scholarship_grants == {2: 5_000}
        assert updated.sections_for(2) == 5  # ceil(90 / 20)
        assert all(t.grade == 2 for t in updated.teachers)
        assert len(updated.teachers) == 4

    def test_weighted_baselines(self) -> None:
        updated = MergeClasses(source_grade=1, target_grade=2).apply(make_snapshot())
        # (92×50 + 90×40) / 90
        assert updated.base_attendance[2] == pytest.approx(91.1111, abs=1e-3)
        assert updated.base_risk[2] == pytest.approx(9.7778, abs=1e-3)
        assert updated.base_performance[2] == pytest.approx(76.2222, abs=1e-3)

    def test_self_merge_raises(self) -> None:
        with pytest.raises(ValueError, match="must differ"):
            MergeClasses(source_grade=1, target_grade=1).validate(make_snapshot())

    def test_missing_source_raises(self) -> None:
        with pytest.raises(ValueError, match="not enrolled"):
            MergeClasses(source_grade=9, target_grade=2).validate(make_snapshot())


def test_levers_never_mutate_the_source_snapshot() -> None:
    source = make_snapshot()
    RemoveTeacher(teacher_id=1).apply(source)
    AddBuses(count=5).apply(source)
    ChangeSchedule(periods_per_day=12).apply(source)
    MergeClasses(source_grade=1, target_grade=2).apply(source)
    assert source.enrollment == {1: 50, 2: 40}
    assert source.fleet_size == 2
    assert source.schedule == Schedule()
    assert len(source.teachers) == 4


def test_minimal_snapshot_still_constructs() -> None:
    """Old-style minimal snapshots (revenue-only) remain valid."""
    snap = SimulationSnapshot(
        campus_id=1,
        academic_year="2026-27",
        fee_rate={1: 100_000},
        enrollment={1: 50},
    )
    assert snap.teacher_count() == 0
    assert snap.sections_for(1) == 50  # section_size defaults to 1


def test_teacher_record_tenure_orders_redistribution() -> None:
    """The redistribution priority is deterministic: tenure desc, then id."""
    teachers = make_snapshot().teachers
    ordered = sorted(teachers, key=lambda t: (-t.tenure, t.teacher_id))
    assert [t.teacher_id for t in ordered] == [1, 3, 2, 4]
