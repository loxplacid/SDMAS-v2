"""Risk rule evaluator.

Runs the enabled deterministic rules against persisted school data for a
single campus (or globally for unscoped admins) and produces
``RiskFindingDraft`` objects. The service layer persists drafts into
``risk_findings``.

Design goals:
- **Batched queries** — one (or a few) set-based SQL queries per rule
  instead of N+1 per-student lookups, so a full-school recompute stays
  cheap.
- **Tenant isolation** — every query is scoped by ``campus_id`` when the
  caller is tenant-scoped.
- **Deterministic** — same data in → same findings out. No randomness,
  no machine learning.
"""

from __future__ import annotations

import datetime
from dataclasses import dataclass
from typing import Any, Optional

from sqlalchemy import and_, case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.academic.models import AcademicYear, Enrollment, Term
from app.domains.academic_ops.models import GradeRecord
from app.domains.admission.models import AdmissionApplication
from app.domains.attendance.models import AttendanceRecord
from app.domains.documents.models import Document, DocumentCategory
from app.domains.fees.models import FeeDue
from app.domains.risk.rules import (
    RULE_REGISTRY,
    RuleDefinition,
    _pct_score,
    severity_from_score,
)
from app.domains.student.models import Student

# Minimum score to emit a finding (rules that just "qualify" start here).
MIN_FINDING_SCORE = 20.0

# A "school day" is any day with at least one attendance record in the
# campus — we derive it rather than assuming Mon–Fri so partial weeks
# and exam weeks stay fair.
NO_GUARDIAN_DEFAULT = {
    "required_categories": ["birth_certificate", "admission_form"],
}


@dataclass
class RiskFindingDraft:
    entity_type: str
    entity_id: int
    student_id: Optional[int]
    rule_code: str
    category: str
    severity: str
    score: float
    reason: str
    recommended_action: str
    evidence: Optional[dict] = None


class RiskEvaluator:
    """Evaluates the configured rules for one campus scope."""

    def __init__(
        self,
        session: AsyncSession,
        campus_id: Optional[int],
        enabled_rules: dict[str, RuleDefinition],
        configs: dict[str, dict],
    ) -> None:
        self.session = session
        self.campus_id = campus_id
        self.enabled_rules = enabled_rules
        self.configs = configs
        self.today = datetime.date.today()
        self.today_iso = self.today.isoformat()

    # ------------------------------------------------------------------
    # Public entry
    # ------------------------------------------------------------------

    async def evaluate_all(self) -> list[RiskFindingDraft]:
        drafts: list[RiskFindingDraft] = []
        for code in self.enabled_rules:
            handler = getattr(self, f"_evaluate_{code}", None)
            if handler is None:
                continue
            try:
                drafts.extend(await handler())
            except Exception as exc:  # noqa: BLE001 — a broken rule degrades
                import logging

                logging.getLogger(__name__).warning(
                    "Risk rule '%s' failed: %s", code, exc
                )
        return drafts

    # ------------------------------------------------------------------
    # Helpers
    # ------------------------------------------------------------------

    def _cfg(self, code: str, key: str, default: Any) -> Any:
        return self.configs.get(code, {}).get(key, default)

    async def _active_students(self) -> list[tuple[int, int | None]]:
        """(student_id, campus_id) for active students."""
        q = select(Student.id, Student.campus_id).where(Student.status == "active")
        if self.campus_id is not None:
            q = q.where(Student.campus_id == self.campus_id)
        rows = (await self.session.execute(q)).all()
        return [(r[0], r[1]) for r in rows]

    async def _student_name_map(self, student_ids: list[int]) -> dict[int, str]:
        if not student_ids:
            return {}
        q = select(Student.id, Student.first_name, Student.last_name).where(
            Student.id.in_(student_ids)
        )
        rows = (await self.session.execute(q)).all()
        return {r[0]: f"{r[1]} {r[2]}".strip() for r in rows}

    # ------------------------------------------------------------------
    # Attendance rules
    # ------------------------------------------------------------------

    async def _evaluate_attendance_below_threshold(self) -> list[RiskFindingDraft]:
        min_pct = float(self._cfg("attendance_below_threshold", "min_percentage", 75.0))
        window = int(self._cfg("attendance_below_threshold", "window_days", 30))
        start = (self.today - datetime.timedelta(days=window)).isoformat()

        q = (
            select(
                AttendanceRecord.student_id,
                func.count(AttendanceRecord.id),
                func.sum(
                    case(
                        (AttendanceRecord.status == "present", 1), else_=0
                    )
                ),
            )
            .where(
                AttendanceRecord.attendance_date >= start,
                AttendanceRecord.attendance_date <= self.today_iso,
            )
            .group_by(AttendanceRecord.student_id)
            .having(func.count(AttendanceRecord.id) >= 5)
        )
        if self.campus_id is not None:
            q = q.where(AttendanceRecord.campus_id == self.campus_id)
        rows = (await self.session.execute(q)).all()

        names = await self._student_name_map([r[0] for r in rows])
        drafts: list[RiskFindingDraft] = []
        for student_id, total, present in rows:
            present = present or 0
            pct = (present / total) * 100
            score = _pct_score(pct, min_pct, floor=0.0)
            if score < MIN_FINDING_SCORE:
                continue
            drafts.append(
                RiskFindingDraft(
                    entity_type="student",
                    entity_id=student_id,
                    student_id=student_id,
                    rule_code="attendance_below_threshold",
                    category="attendance",
                    severity=severity_from_score(score),
                    score=score,
                    reason=(
                        f"Attendance {pct:.1f}% over the last {window} days "
                        f"(below {min_pct:.0f}%)."
                    ),
                    recommended_action=RULE_REGISTRY[
                        "attendance_below_threshold"
                    ].recommended_action,
                    evidence={
                        "student": names.get(student_id),
                        "percentage": round(pct, 1),
                        "present": present,
                        "total": total,
                        "min_percentage": min_pct,
                        "window_days": window,
                    },
                )
            )
        return drafts

    async def _evaluate_attendance_consecutive_absences(self) -> list[RiskFindingDraft]:
        max_abs = int(
            self._cfg("attendance_consecutive_absences", "max_consecutive_absences", 5)
        )
        window = max(max_abs + 21, 30)  # a bit more history than the streak

        q = (
            select(
                AttendanceRecord.student_id,
                AttendanceRecord.attendance_date,
            )
            .where(
                AttendanceRecord.status.in_(["absent", "late"]),
                AttendanceRecord.attendance_date
                >= (self.today - datetime.timedelta(days=window)).isoformat(),
                AttendanceRecord.attendance_date <= self.today_iso,
            )
            .order_by(AttendanceRecord.student_id, AttendanceRecord.attendance_date.desc())
        )
        if self.campus_id is not None:
            q = q.where(AttendanceRecord.campus_id == self.campus_id)
        rows = (await self.session.execute(q)).all()

        # Group by student, count the longest streak of *consecutive dates*
        # in the student's own attendance calendar (only their recorded days).
        streaks: dict[int, int] = {}
        per_student: dict[int, list[str]] = {}
        for student_id, date_str in rows:
            per_student.setdefault(student_id, []).append(date_str)

        for student_id, dates in per_student.items():
            # Dates are already descending (newest first). Longest run of
            # consecutive recorded dates.
            run = 1
            longest = 1
            for i in range(len(dates) - 1):
                prev = datetime.date.fromisoformat(dates[i])
                cur = datetime.date.fromisoformat(dates[i + 1])
                if (prev - cur).days == 1:
                    run += 1
                    longest = max(longest, run)
                else:
                    run = 1
            if longest >= max_abs:
                streaks[student_id] = longest

        if not streaks:
            return []
        names = await self._student_name_map(list(streaks.keys()))
        drafts: list[RiskFindingDraft] = []
        for student_id, longest in streaks.items():
            score = min(100.0, 40.0 + (longest - max_abs) * 12)
            drafts.append(
                RiskFindingDraft(
                    entity_type="student",
                    entity_id=student_id,
                    student_id=student_id,
                    rule_code="attendance_consecutive_absences",
                    category="attendance",
                    severity=severity_from_score(score),
                    score=round(score, 1),
                    reason=(
                        f"{longest} consecutive absent/late days recorded "
                        f"(threshold {max_abs})."
                    ),
                    recommended_action=RULE_REGISTRY[
                        "attendance_consecutive_absences"
                    ].recommended_action,
                    evidence={
                        "student": names.get(student_id),
                        "consecutive_absences": longest,
                        "threshold": max_abs,
                    },
                )
            )
        return drafts

    async def _evaluate_attendance_declining_trend(self) -> list[RiskFindingDraft]:
        decline = float(
            self._cfg("attendance_declining_trend", "decline_threshold", 10.0)
        )
        window = int(self._cfg("attendance_declining_trend", "window_days", 14))
        midpoint = self.today - datetime.timedelta(days=window)
        start = (midpoint - datetime.timedelta(days=window)).isoformat()

        def _window_q(lo: str, hi: str):
            q = (
                select(
                    AttendanceRecord.student_id,
                    func.count(AttendanceRecord.id),
                    func.sum(
                        case(
                            (AttendanceRecord.status == "present", 1), else_=0
                        )
                    ),
                )
                .where(
                    AttendanceRecord.attendance_date >= lo,
                    AttendanceRecord.attendance_date <= hi,
                )
                .group_by(AttendanceRecord.student_id)
                .having(func.count(AttendanceRecord.id) >= 3)
            )
            if self.campus_id is not None:
                q = q.where(AttendanceRecord.campus_id == self.campus_id)
            return q

        recent = {
            r[0]: (r[1] or 0, r[2] or 0)
            for r in (await self.session.execute(_window_q(midpoint.isoformat(), self.today_iso))).all()
        }
        earlier = {
            r[0]: (r[1] or 0, r[2] or 0)
            for r in (await self.session.execute(_window_q(start, midpoint.isoformat()))).all()
        }

        drafts: list[RiskFindingDraft] = []
        flagged: list[int] = []
        trend_map: dict[int, dict] = {}
        for sid in recent:
            if sid not in earlier:
                continue
            r_total, r_present = recent[sid]
            e_total, e_present = earlier[sid]
            if r_total == 0 or e_total == 0:
                continue
            recent_pct = (r_present / r_total) * 100
            earlier_pct = (e_present / e_total) * 100
            drop = earlier_pct - recent_pct
            if drop >= decline:
                flagged.append(sid)
                trend_map[sid] = {
                    "recent_pct": round(recent_pct, 1),
                    "earlier_pct": round(earlier_pct, 1),
                    "drop": round(drop, 1),
                }

        if not flagged:
            return []
        names = await self._student_name_map(flagged)
        out: list[RiskFindingDraft] = []
        for sid in flagged:
            t = trend_map[sid]
            score = min(100.0, _pct_score(t["recent_pct"], 100.0 - decline, floor=0.0))
            out.append(
                RiskFindingDraft(
                    entity_type="student",
                    entity_id=sid,
                    student_id=sid,
                    rule_code="attendance_declining_trend",
                    category="attendance",
                    severity=severity_from_score(score),
                    score=round(score, 1),
                    reason=(
                        f"Attendance declined from {t['earlier_pct']:.1f}% to "
                        f"{t['recent_pct']:.1f}% over the last {window} days."
                    ),
                    recommended_action=RULE_REGISTRY[
                        "attendance_declining_trend"
                    ].recommended_action,
                    evidence={
                        "student": names.get(sid),
                        "recent_percentage": t["recent_pct"],
                        "earlier_percentage": t["earlier_pct"],
                        "decline": t["drop"],
                        "threshold": decline,
                    },
                )
            )
        return out

    # ------------------------------------------------------------------
    # Finance rules
    # ------------------------------------------------------------------

    async def _evaluate_fees_overdue(self) -> list[RiskFindingDraft]:
        q = (
            select(
                FeeDue.student_id,
                func.count(FeeDue.id),
                func.coalesce(
                    func.sum(FeeDue.original_amount - FeeDue.amount_paid), 0
                ),
            )
            .where(
                FeeDue.due_date.isnot(None),
                FeeDue.due_date < self.today_iso,
                FeeDue.amount_paid < FeeDue.original_amount,
            )
            .group_by(FeeDue.student_id)
        )
        if self.campus_id is not None:
            q = q.where(FeeDue.campus_id == self.campus_id)
        rows = (await self.session.execute(q)).all()

        if not rows:
            return []
        names = await self._student_name_map([r[0] for r in rows])
        drafts: list[RiskFindingDraft] = []
        for student_id, count, balance in rows:
            balance = balance or 0
            score = min(100.0, 40.0 + count * 10)
            drafts.append(
                RiskFindingDraft(
                    entity_type="student",
                    entity_id=student_id,
                    student_id=student_id,
                    rule_code="fees_overdue",
                    category="finance",
                    severity=severity_from_score(score),
                    score=round(score, 1),
                    reason=f"{count} overdue fee due(s); balance ₹{balance/100:,.0f}.",
                    recommended_action=RULE_REGISTRY["fees_overdue"].recommended_action,
                    evidence={
                        "student": names.get(student_id),
                        "overdue_count": count,
                        "balance_paise": balance,
                    },
                )
            )
        return drafts

    async def _evaluate_fees_overdue_duration(self) -> list[RiskFindingDraft]:
        max_days = int(self._cfg("fees_overdue_duration", "max_overdue_days", 30))
        cutoff = (self.today - datetime.timedelta(days=max_days)).isoformat()

        q = (
            select(
                FeeDue.student_id,
                func.count(FeeDue.id),
                func.min(FeeDue.due_date),
            )
            .where(
                FeeDue.due_date.isnot(None),
                FeeDue.due_date <= cutoff,
                FeeDue.amount_paid < FeeDue.original_amount,
            )
            .group_by(FeeDue.student_id)
        )
        if self.campus_id is not None:
            q = q.where(FeeDue.campus_id == self.campus_id)
        rows = (await self.session.execute(q)).all()

        if not rows:
            return []
        names = await self._student_name_map([r[0] for r in rows])
        drafts: list[RiskFindingDraft] = []
        for student_id, count, earliest in rows:
            days = (self.today - datetime.date.fromisoformat(earliest)).days
            score = min(100.0, 50.0 + (days - max_days) * 1.5)
            drafts.append(
                RiskFindingDraft(
                    entity_type="student",
                    entity_id=student_id,
                    student_id=student_id,
                    rule_code="fees_overdue_duration",
                    category="finance",
                    severity=severity_from_score(score),
                    score=round(score, 1),
                    reason=(
                        f"{count} fee due(s) overdue for {days} days "
                        f"(threshold {max_days} days)."
                    ),
                    recommended_action=RULE_REGISTRY[
                        "fees_overdue_duration"
                    ].recommended_action,
                    evidence={
                        "student": names.get(student_id),
                        "overdue_days": days,
                        "overdue_count": count,
                        "threshold_days": max_days,
                    },
                )
            )
        return drafts

    async def _evaluate_fees_high_outstanding(self) -> list[RiskFindingDraft]:
        max_out = int(self._cfg("fees_high_outstanding", "max_outstanding", 50_000_00))

        q = (
            select(
                FeeDue.student_id,
                func.coalesce(
                    func.sum(FeeDue.original_amount - FeeDue.amount_paid), 0
                ),
            )
            .group_by(FeeDue.student_id)
            .having(
                func.coalesce(
                    func.sum(FeeDue.original_amount - FeeDue.amount_paid), 0
                )
                > max_out
            )
        )
        if self.campus_id is not None:
            q = q.where(FeeDue.campus_id == self.campus_id)
        rows = (await self.session.execute(q)).all()

        if not rows:
            return []
        names = await self._student_name_map([r[0] for r in rows])
        drafts: list[RiskFindingDraft] = []
        for student_id, balance in rows:
            balance = balance or 0
            score = min(100.0, 45.0 + (balance - max_out) / max_out * 40)
            drafts.append(
                RiskFindingDraft(
                    entity_type="student",
                    entity_id=student_id,
                    student_id=student_id,
                    rule_code="fees_high_outstanding",
                    category="finance",
                    severity=severity_from_score(score),
                    score=round(score, 1),
                    reason=f"Outstanding balance ₹{balance/100:,.0f} exceeds threshold.",
                    recommended_action=RULE_REGISTRY[
                        "fees_high_outstanding"
                    ].recommended_action,
                    evidence={
                        "student": names.get(student_id),
                        "outstanding_paise": balance,
                        "threshold_paise": max_out,
                    },
                )
            )
        return drafts

    # ------------------------------------------------------------------
    # Academic rules (grade records)
    # ------------------------------------------------------------------

    async def _grade_summary(self) -> dict[int, tuple[float, float, int]]:
        """student_id -> (avg_pct, total_marks_pct, subject_count) grouped by term."""
        # We need per-student average across their grade records. GradeRecord
        # links to Enrollment -> student.
        q = (
            select(
                Enrollment.student_id,
                func.avg(
                    (GradeRecord.marks_obtained / GradeRecord.max_marks) * 100
                ),
                func.sum(GradeRecord.marks_obtained),
                func.sum(GradeRecord.max_marks),
                func.count(GradeRecord.id),
            )
            .join(Enrollment, Enrollment.id == GradeRecord.enrollment_id)
            .where(GradeRecord.marks_obtained.isnot(None), GradeRecord.status == "active")
            .group_by(Enrollment.student_id)
        )
        if self.campus_id is not None:
            q = q.where(GradeRecord.campus_id == self.campus_id)
        rows = (await self.session.execute(q)).all()
        return {
            r[0]: (float(r[1] or 0), float(r[2] or 0), float(r[3] or 0), int(r[4] or 0))
            for r in rows
        }

    async def _evaluate_academic_low_performance(self) -> list[RiskFindingDraft]:
        min_pct = float(self._cfg("academic_low_performance", "min_percentage", 40.0))
        summary = await self._grade_summary()

        drafts: list[RiskFindingDraft] = []
        names = await self._student_name_map(list(summary.keys()))
        for sid, (avg_pct, _, _, _) in summary.items():
            if avg_pct >= min_pct:
                continue
            score = _pct_score(avg_pct, min_pct, floor=0.0)
            if score < MIN_FINDING_SCORE:
                continue
            drafts.append(
                RiskFindingDraft(
                    entity_type="student",
                    entity_id=sid,
                    student_id=sid,
                    rule_code="academic_low_performance",
                    category="academic",
                    severity=severity_from_score(score),
                    score=round(score, 1),
                    reason=f"Average marks {avg_pct:.1f}% below {min_pct:.0f}% threshold.",
                    recommended_action=RULE_REGISTRY[
                        "academic_low_performance"
                    ].recommended_action,
                    evidence={
                        "student": names.get(sid),
                        "average_percentage": round(avg_pct, 1),
                        "min_percentage": min_pct,
                    },
                )
            )
        return drafts

    async def _evaluate_academic_declining_performance(self) -> list[RiskFindingDraft]:
        decline = float(
            self._cfg("academic_declining_performance", "decline_threshold", 10.0)
        )

        # Latest two terms per student: compare average % between the two
        # most recent distinct terms.
        q = (
            select(
                Enrollment.student_id,
                Term.id,
                Term.name,
                func.avg((GradeRecord.marks_obtained / GradeRecord.max_marks) * 100),
            )
            .join(Enrollment, Enrollment.id == GradeRecord.enrollment_id)
            .join(Term, Term.id == GradeRecord.term_id)
            .where(
                GradeRecord.marks_obtained.isnot(None),
                GradeRecord.term_id.isnot(None),
                GradeRecord.status == "active",
            )
            .group_by(Enrollment.student_id, Term.id, Term.name)
        )
        if self.campus_id is not None:
            q = q.where(GradeRecord.campus_id == self.campus_id)
        rows = (await self.session.execute(q)).all()

        # Keep two most recent terms by term id (assumes ids increase with time).
        per_student: dict[int, list[tuple[int, str, float]]] = {}
        for sid, term_id, term_name, avg in rows:
            per_student.setdefault(sid, []).append((term_id, term_name, float(avg or 0)))
        flagged: dict[int, dict] = {}
        for sid, terms in per_student.items():
            terms.sort(key=lambda t: t[0])
            if len(terms) < 2:
                continue
            _, older_name, older_avg = terms[-2]
            _, newer_name, newer_avg = terms[-1]
            drop = older_avg - newer_avg
            if drop >= decline:
                flagged[sid] = {
                    "older_avg": round(older_avg, 1),
                    "newer_avg": round(newer_avg, 1),
                    "drop": round(drop, 1),
                    "older_name": older_name,
                    "newer_name": newer_name,
                }

        if not flagged:
            return []
        names = await self._student_name_map(list(flagged.keys()))
        drafts: list[RiskFindingDraft] = []
        for sid, f in flagged.items():
            score = min(100.0, 40.0 + f["drop"] * 3)
            drafts.append(
                RiskFindingDraft(
                    entity_type="student",
                    entity_id=sid,
                    student_id=sid,
                    rule_code="academic_declining_performance",
                    category="academic",
                    severity=severity_from_score(score),
                    score=round(score, 1),
                    reason=(
                        f"Average marks declined from {f['older_avg']:.1f}% "
                        f"({f['older_name']}) to {f['newer_avg']:.1f}% ({f['newer_name']})."
                    ),
                    recommended_action=RULE_REGISTRY[
                        "academic_declining_performance"
                    ].recommended_action,
                    evidence={
                        "student": names.get(sid),
                        "older_term": f["older_name"],
                        "newer_term": f["newer_name"],
                        "drop": f["drop"],
                        "threshold": decline,
                    },
                )
            )
        return drafts

    # ------------------------------------------------------------------
    # Documents rule
    # ------------------------------------------------------------------

    async def _evaluate_documents_missing_required(self) -> list[RiskFindingDraft]:
        required = self._cfg(
            "documents_missing_required",
            "required_categories",
            NO_GUARDIAN_DEFAULT["required_categories"],
        )
        required_set = set(required)

        # Which categories does each student actually have active documents in?
        # Documents link to DocumentCategory via category_id.
        q = (
            select(Document.student_id, DocumentCategory.code)
            .join(DocumentCategory, DocumentCategory.id == Document.category_id)
            .where(
                Document.student_id.isnot(None),
                Document.lifecycle_state == "active",
            )
        )
        if self.campus_id is not None:
            q = q.where(Document.campus_id == self.campus_id)
        rows = (await self.session.execute(q)).all()

        per_student: dict[int, set[str]] = {}
        for sid, code in rows:
            per_student.setdefault(sid, set()).add(code)

        active = await self._active_students()
        flagged: list[tuple[int, list[str]]] = []
        for sid, _ in active:
            have = per_student.get(sid, set())
            missing = sorted(required_set - have)
            if missing:
                flagged.append((sid, missing))
        if not flagged:
            return []

        names = await self._student_name_map([sid for sid, _ in flagged])
        drafts: list[RiskFindingDraft] = []
        for sid, missing in flagged:
            drafts.append(
                RiskFindingDraft(
                    entity_type="student",
                    entity_id=sid,
                    student_id=sid,
                    rule_code="documents_missing_required",
                    category="documents",
                    severity="medium",
                    score=50.0,
                    reason=(
                        f"Student is missing required document(s): {', '.join(missing)}."
                    ),
                    recommended_action=RULE_REGISTRY[
                        "documents_missing_required"
                    ].recommended_action,
                    evidence={
                        "student": names.get(sid),
                        "required_categories": sorted(required_set),
                        "missing_categories": missing,
                    },
                )
            )
        return drafts

    # ------------------------------------------------------------------
    # Admissions rule
    # ------------------------------------------------------------------

    async def _evaluate_admissions_stalled(self) -> list[RiskFindingDraft]:
        max_days = int(self._cfg("admissions_stalled", "max_stalled_days", 14))
        cutoff = self.today - datetime.timedelta(days=max_days)

        terminal = {"enrolled", "student_created", "rejected"}
        q = (
            select(
                AdmissionApplication.id,
                AdmissionApplication.applicant_name,
                AdmissionApplication.updated_at,
            )
            .where(AdmissionApplication.status.notin_(terminal))
        )
        if self.campus_id is not None:
            q = q.where(AdmissionApplication.campus_id == self.campus_id)
        rows = (await self.session.execute(q)).all()

        drafts: list[RiskFindingDraft] = []
        for app_id, name, updated_at in rows:
            if updated_at is None:
                continue
            # updated_at is tz-aware datetime; compare with cutoff as date
            updated_date = updated_at.date()
            if updated_date > cutoff:
                continue
            days = (self.today - updated_date).days
            score = min(100.0, 50.0 + (days - max_days) * 4)
            drafts.append(
                RiskFindingDraft(
                    entity_type="admission_application",
                    entity_id=app_id,
                    student_id=None,
                    rule_code="admissions_stalled",
                    category="admissions",
                    severity=severity_from_score(score),
                    score=round(score, 1),
                    reason=(
                        f"Application '{name}' has not progressed for {days} days "
                        f"(threshold {max_days})."
                    ),
                    recommended_action=RULE_REGISTRY[
                        "admissions_stalled"
                    ].recommended_action,
                    evidence={
                        "applicant": name,
                        "stalled_days": days,
                        "threshold_days": max_days,
                        "status": None,
                    },
                )
            )
        return drafts

    # ------------------------------------------------------------------
    # Operational rule
    # ------------------------------------------------------------------

    async def _evaluate_operational_no_guardian(self) -> list[RiskFindingDraft]:
        """Students with no guardian/primary contact recorded.

        Uses ``guardian_links`` (the canonical parent-child table). If the
        table is absent (early environments), the rule degrades gracefully.
        """
        active = await self._active_students()
        if not active:
            return []

        guardian_table = __import__("sqlalchemy").text("guardian_links")
        try:
            result = await self.session.execute(
                select(func.count()).select_from(guardian_table)
            )
            result.scalar()
        except Exception:  # noqa: BLE001 — table may not exist yet
            return []

        ids = [sid for sid, _ in active]
        guarded = (
            await self.session.execute(
                select(guardian_table.c.student_id)
                .where(guardian_table.c.student_id.in_(ids))
            )
        ).all()
        have_guardian = {r[0] for r in guarded}
        flagged = [sid for sid in ids if sid not in have_guardian]
        if not flagged:
            return []

        names = await self._student_name_map(flagged)
        return [
            RiskFindingDraft(
                entity_type="student",
                entity_id=sid,
                student_id=sid,
                rule_code="operational_no_guardian",
                category="operational",
                severity="low",
                score=25.0,
                reason="Student has no guardian or primary contact recorded.",
                recommended_action=RULE_REGISTRY[
                    "operational_no_guardian"
                ].recommended_action,
                evidence={"student": names.get(sid)},
            )
            for sid in flagged
        ]
