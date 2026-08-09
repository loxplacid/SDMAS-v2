"""Risk & Attention Engine service layer.

Responsibilities:
- ``recompute`` — run all enabled rules for a campus and persist findings
  (upsert open findings, close stale ones as ``resolved``), write an
  audit entry, and notify leadership about new high/critical findings.
- ``list_findings`` / ``get_overview`` — cheap reads from the persisted
  snapshot, RBAC-filtered by role.
- ``get_config`` / ``update_config`` — school-level rule configuration,
  admin-only for writes, audited.
- ``resolve_finding`` / ``acknowledge_finding`` — explicit, audited
  status changes. Users can never silently alter a finding's severity,
  score or reason — only its lifecycle status.
"""

from __future__ import annotations

import datetime
from typing import Any, Optional, Sequence

from sqlalchemy import case, func, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.domains.audit.service import AuditService
from app.domains.notifications.service import NotificationService
from app.domains.risk.evaluator import RiskEvaluator
from app.domains.risk.models import (
    RISK_ENTITY_ADMISSION,
    RISK_STATUS_ACKNOWLEDGED,
    RISK_STATUS_OPEN,
    RISK_STATUS_RESOLVED,
    RiskFinding,
    RiskRuleConfig,
)
from app.domains.academic.models import AcademicYear, Class, Enrollment, TeacherAssignment
from app.domains.risk.rules import (
    DEFAULT_RULES,
    RULE_REGISTRY,
    RuleDefinition,
)
from app.domains.student.models import Student

# Roles that may view/act on risk findings.
RISK_ROLES = {"admin", "principal", "staff"}
CONFIG_ROLES = {"admin", "principal"}

# Deterministic severity ordering — string comparison would put
# "medium" above "high" alphabetically, which is backwards for risk.
SEVERITY_RANK = case(
    (RiskFinding.severity == "critical", 0),
    (RiskFinding.severity == "high", 1),
    (RiskFinding.severity == "medium", 2),
    (RiskFinding.severity == "low", 3),
    else_=4,
)


class RiskService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    async def _load_config(self, campus_id: Optional[int]) -> dict[str, dict]:
        """rule_code -> effective config dict (global defaults + campus row).

        ``enabled`` lives on the row; thresholds/severity overrides merge.
        """
        q = select(RiskRuleConfig)
        rows = (await self.session.execute(q)).scalars().all()

        effective: dict[str, dict] = {}
        for rule in DEFAULT_RULES:
            effective[rule.code] = {
                "enabled": True,
                "thresholds": dict(rule.defaults),
                "severity_overrides": None,
            }

        by_key: dict[tuple[Optional[int], str], RiskRuleConfig] = {
            (r.campus_id, r.rule_code): r for r in rows
        }
        # Global row first, then campus row overrides.
        for r in rows:
            if r.campus_id is not None:
                continue
            code = r.rule_code
            row = by_key.get((None, code))
            if row:
                effective[code]["enabled"] = row.enabled
                effective[code]["thresholds"].update(row.thresholds or {})
                effective[code]["severity_overrides"] = row.severity_overrides
        for r in rows:
            if campus_id is None or r.campus_id != campus_id:
                continue
            code = r.rule_code
            row = by_key.get((campus_id, code))
            if row:
                effective[code]["enabled"] = row.enabled
                effective[code]["thresholds"].update(row.thresholds or {})
                effective[code]["severity_overrides"] = row.severity_overrides
        return effective

    async def _enabled_definitions(
        self, campus_id: Optional[int]
    ) -> tuple[dict[str, RuleDefinition], dict[str, dict]]:
        cfg = await self._load_config(campus_id)
        enabled = {
            code: RULE_REGISTRY[code]
            for code, c in cfg.items()
            if c["enabled"]
        }
        return enabled, cfg

    async def get_config(
        self, campus_id: Optional[int]
    ) -> list[dict[str, Any]]:
        cfg = await self._load_config(campus_id)
        out: list[dict[str, Any]] = []
        for rule in DEFAULT_RULES:
            c = cfg[rule.code]
            out.append(
                {
                    "rule_code": rule.code,
                    "category": rule.category,
                    "name": rule.name,
                    "description": rule.description,
                    "entity_type": rule.entity_type,
                    "enabled": c["enabled"],
                    "thresholds": c["thresholds"],
                    "severity_overrides": c["severity_overrides"],
                    "defaults": rule.defaults,
                    "recommended_action": rule.recommended_action,
                }
            )
        return out

    async def update_config(
        self,
        campus_id: Optional[int],
        rule_code: str,
        *,
        enabled: Optional[bool] = None,
        thresholds: Optional[dict] = None,
        severity_overrides: Optional[dict] = None,
        actor_user_id: Optional[int] = None,
    ) -> dict[str, Any]:
        """Create/update a campus-scoped rule config row (audited)."""
        if rule_code not in RULE_REGISTRY:
            raise ValidationError(f"Unknown rule code: {rule_code}")

        q = select(RiskRuleConfig).where(
            RiskRuleConfig.campus_id == campus_id,
            RiskRuleConfig.rule_code == rule_code,
        )
        row = (await self.session.execute(q)).scalar_one_or_none()
        if row is None:
            row = RiskRuleConfig(
                campus_id=campus_id,
                rule_code=rule_code,
                category=RULE_REGISTRY[rule_code].category,
                enabled=True,
                thresholds={},
            )
            self.session.add(row)
        if enabled is not None:
            row.enabled = enabled
        if thresholds is not None:
            merged = dict(row.thresholds or {})
            merged.update(thresholds)
            row.thresholds = merged
        if severity_overrides is not None:
            row.severity_overrides = severity_overrides or None
        row.updated_by = actor_user_id
        await self.session.flush()

        await AuditService(self.session).record(
            user_id=actor_user_id,
            username=None,
            action="UPDATE",
            resource_type="risk_rule_config",
            resource_id=str(row.id),
            details={
                "rule_code": rule_code,
                "campus_id": campus_id,
                "enabled": row.enabled,
                "thresholds": row.thresholds,
                "severity_overrides": row.severity_overrides,
            },
            campus_id=campus_id,
        )
        await self.session.flush()

        cfg = await self._load_config(campus_id)
        c = cfg[rule_code]
        return {
            "rule_code": rule_code,
            "category": row.category,
            "enabled": c["enabled"],
            "thresholds": c["thresholds"],
            "severity_overrides": c["severity_overrides"],
        }

    # ------------------------------------------------------------------
    # Recompute
    # ------------------------------------------------------------------

    async def recompute(
        self,
        campus_id: Optional[int],
        actor_user_id: Optional[int] = None,
    ) -> dict[str, Any]:
        """Run all enabled rules and persist the snapshot.

        Returns counts: created / updated / resolved / total_open.
        """
        enabled, cfg = await self._enabled_definitions(campus_id)
        evaluator = RiskEvaluator(
            session=self.session,
            campus_id=campus_id,
            enabled_rules=enabled,
            configs={
                code: dict(cfg[code]["thresholds"])
                for code in cfg
                if code in enabled
            },
        )
        drafts = await evaluator.evaluate_all()

        now = datetime.datetime.now(datetime.timezone.utc)
        created = updated = 0
        kept_keys: set[tuple[Optional[int], str, int, str]] = set()

        for d in drafts:
            key = (campus_id, d.entity_type, d.entity_id, d.rule_code)
            # Match an existing open OR acknowledged row so that an
            # acknowledged finding is *reopened* on the next run instead of
            # silently duplicated as a fresh open finding.
            q = select(RiskFinding).where(
                RiskFinding.campus_id == campus_id,
                RiskFinding.entity_type == d.entity_type,
                RiskFinding.entity_id == d.entity_id,
                RiskFinding.rule_code == d.rule_code,
                RiskFinding.status.in_([RISK_STATUS_OPEN, RISK_STATUS_ACKNOWLEDGED]),
            )
            existing = (await self.session.execute(q)).scalar_one_or_none()
            if existing is None:
                self.session.add(
                    RiskFinding(
                        campus_id=campus_id,
                        entity_type=d.entity_type,
                        entity_id=d.entity_id,
                        student_id=d.student_id,
                        rule_code=d.rule_code,
                        category=d.category,
                        severity=d.severity,
                        score=d.score,
                        reason=d.reason,
                        recommended_action=d.recommended_action,
                        evidence=d.evidence,
                        status=RISK_STATUS_OPEN,
                        detected_at=now,
                        last_verified_at=now,
                    )
                )
                created += 1
            else:
                existing.status = RISK_STATUS_OPEN
                existing.severity = d.severity
                existing.score = d.score
                existing.reason = d.reason
                existing.recommended_action = d.recommended_action
                existing.evidence = d.evidence
                existing.last_verified_at = now
                updated += 1
            kept_keys.add(key)

        # Close stale open findings whose rule no longer fires.
        stale_q = select(RiskFinding).where(
            RiskFinding.campus_id == campus_id,
            RiskFinding.status == RISK_STATUS_OPEN,
        )
        stale_rows = (await self.session.execute(stale_q)).scalars().all()
        resolved = 0
        for f in stale_rows:
            key = (campus_id, f.entity_type, f.entity_id, f.rule_code)
            if key not in kept_keys:
                f.status = RISK_STATUS_RESOLVED
                f.resolved_at = now
                f.resolved_reason = "rule_no_longer_applies"
                resolved += 1

        await self.session.flush()

        # Audit the recompute run.
        await AuditService(self.session).record(
            user_id=actor_user_id,
            username=None,
            action="RUN",
            resource_type="risk_recompute",
            details={
                "campus_id": campus_id,
                "rules_run": len(enabled),
                "created": created,
                "updated": updated,
                "resolved": resolved,
            },
            campus_id=campus_id,
        )
        await self.session.flush()

        # Notify leadership about newly detected high/critical findings.
        await self._notify_new_findings(campus_id, actor_user_id)

        total_open = (
            await self.session.execute(
                select(func.count(RiskFinding.id)).where(
                    RiskFinding.campus_id == campus_id,
                    RiskFinding.status == RISK_STATUS_OPEN,
                )
            )
        ).scalar() or 0

        return {
            "created": created,
            "updated": updated,
            "resolved": resolved,
            "total_open": total_open,
            "run_at": now.isoformat(),
        }

    async def _notify_new_findings(
        self, campus_id: Optional[int], actor_user_id: Optional[int]
    ) -> None:
        """Notify admin/principal users about open high/critical findings."""
        try:
            from app.domains.auth.models import User

            q = (
                select(User.id)
                .where(
                    User.is_active.is_(True),
                    User.role.in_(["admin", "principal"]),
                )
            )
            if campus_id is not None:
                q = q.where(User.campus_id == campus_id)
            rows = (await self.session.execute(q)).all()
            target_ids = [r[0] for r in rows if r[0] != actor_user_id]
            if not target_ids:
                return

            # Notifications are leadership-only — role "admin" sees all categories.
            counts = await self.get_overview(campus_id, role="admin")
            severe = counts.get("critical", 0) + counts.get("high", 0)
            if severe == 0:
                return

            svc = NotificationService(self.session)
            for uid in target_ids:
                await svc.create_notification(
                    user_id=uid,
                    type="risk_alert",
                    title="Risk review needed",
                    message=(
                        f"{severe} high/critical risk finding(s) are open "
                        "for your school. Review them in the Risk Center."
                    ),
                    data={"campus_id": campus_id, "severity_count": severe},
                )
            await self.session.flush()
        except Exception:  # noqa: BLE001 — notifications are best-effort
            return

    # ------------------------------------------------------------------
    # Reads (RBAC-filtered)
    # ------------------------------------------------------------------

    def _category_filter_for_role(self, role: str) -> set[str]:
        """Categories the role may see (financial data guarded)."""
        if role == "admin":
            return {
                "attendance", "finance", "academic", "documents", "admissions",
                "operational",
            }
        if role == "principal":
            return {
                "attendance", "finance", "academic", "documents", "admissions",
                "operational",
            }
        if role == "staff":
            return {"attendance", "academic", "documents", "operational"}
        if role == "accountant":
            return {"finance", "attendance", "documents", "operational"}
        if role == "teacher":
            return {"attendance", "academic", "documents", "operational"}
        return set()

    async def list_findings(
        self,
        campus_id: Optional[int],
        role: str,
        *,
        category: Optional[str] = None,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        rule_code: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[RiskFinding], int]:
        allowed = self._category_filter_for_role(role)
        q = select(RiskFinding).where(RiskFinding.campus_id == campus_id)
        count_q = select(func.count(RiskFinding.id)).where(
            RiskFinding.campus_id == campus_id
        )

        if category is not None:
            if category not in allowed:
                return [], 0
            q = q.where(RiskFinding.category == category)
            count_q = count_q.where(RiskFinding.category == category)
        else:
            q = q.where(RiskFinding.category.in_(allowed))
            count_q = count_q.where(RiskFinding.category.in_(allowed))
        if severity is not None:
            q = q.where(RiskFinding.severity == severity)
            count_q = count_q.where(RiskFinding.severity == severity)
        if status is not None:
            q = q.where(RiskFinding.status == status)
            count_q = count_q.where(RiskFinding.status == status)
        if rule_code is not None:
            q = q.where(RiskFinding.rule_code == rule_code)
            count_q = count_q.where(RiskFinding.rule_code == rule_code)

        total = (await self.session.execute(count_q)).scalar() or 0
        q = (
            q.order_by(SEVERITY_RANK, RiskFinding.score.desc())
            .offset(skip)
            .limit(limit)
        )
        rows = (await self.session.execute(q)).scalars().all()
        return rows, total

    async def get_finding(
        self, finding_id: int, campus_id: Optional[int], role: str
    ) -> RiskFinding:
        """Single finding for deep-linking (case → Risk Center context).

        P11 — lets the case detail "View underlying records" land on the
        exact finding even when list filters/pagination would hide it.
        Mirrors ``list_findings`` RBAC: a finding in a category the role
        cannot see is treated as missing (404), never silently leaked.
        """
        f = await self._get_finding(finding_id, campus_id)
        allowed = self._category_filter_for_role(role)
        if f.category not in allowed:
            raise NotFoundError(f"Risk finding {finding_id} not found")
        return f

    async def linked_cases_for_findings(
        self, campus_id: Optional[int], finding_ids: list[int]
    ) -> dict[int, dict[str, Any]]:
        """finding_id → linked case info (id, number, status), campus-scoped.

        P11 — lets the Risk Center show the open case for a finding and
        offer "Open case" instead of a duplicate "Create case". The
        ``uq_cases_source`` unique constraint guarantees at most one case
        per (campus, source_type, source_id).
        """
        if not finding_ids:
            return {}
        from app.domains.cases.models import Case

        q = select(Case.source_id, Case.id, Case.case_number, Case.status).where(
            Case.source_type == "risk_finding",
            Case.source_id.in_(finding_ids),
        )
        if campus_id is not None:
            q = q.where(Case.campus_id == campus_id)
        return {
            source_id: {
                "case_id": case_id,
                "case_number": case_number,
                "case_status": status,
            }
            for source_id, case_id, case_number, status in (
                await self.session.execute(q)
            ).all()
        }

    async def get_overview(
        self, campus_id: Optional[int], role: str = "admin"
    ) -> dict[str, Any]:
        """Severity/category counts of open findings, RBAC-filtered by role."""
        allowed = self._category_filter_for_role(role)
        base = [
            RiskFinding.campus_id == campus_id,
            RiskFinding.status == RISK_STATUS_OPEN,
            RiskFinding.category.in_(allowed),
        ]
        rows = (
            await self.session.execute(
                select(
                    RiskFinding.severity,
                    func.count(RiskFinding.id),
                ).where(*base).group_by(RiskFinding.severity)
            )
        ).all()
        counts = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        total = 0
        for severity, n in rows:
            counts[severity] = counts.get(severity, 0) + n
            total += n
        counts["total"] = total

        by_category = (
            await self.session.execute(
                select(
                    RiskFinding.category,
                    func.count(RiskFinding.id),
                ).where(*base).group_by(RiskFinding.category)
            )
        ).all()
        counts["by_category"] = {
            cat: n for cat, n in by_category
        }
        return counts

    async def resolve_teacher_id_for_user(
        self, email: Optional[str], display_name: Optional[str]
    ) -> Optional[int]:
        """Best-effort user → teacher mapping (schema has no direct link).

        Used to prevent a teacher-role caller from reading another
        teacher's students. Matches by email first, then full name.
        """
        # Note: Teacher.email isn't unique in the schema, so both lookups
        # defensively use limit(1) to avoid MultipleResultsFound on dupes.
        if email:
            row = (
                await self.session.execute(
                    select(Teacher.id).where(Teacher.email == email).limit(1)
                )
            ).scalar_one_or_none()
            if row:
                return row
        if display_name:
            parts = [p for p in display_name.split(" ") if p]
            if len(parts) >= 2:
                row = (
                    await self.session.execute(
                        select(Teacher.id).where(
                            Teacher.first_name == parts[0],
                            Teacher.last_name == parts[-1],
                        ).limit(1)
                    )
                ).scalar_one_or_none()
                if row:
                    return row
        return None

    async def _active_academic_year_id(
        self, campus_id: Optional[int]
    ) -> Optional[int]:
        """Current active academic year id for the campus (or None)."""
        q = select(AcademicYear.id).where(AcademicYear.status == "active")
        if campus_id is not None:
            q = q.where(AcademicYear.campus_id == campus_id)
        return (await self.session.execute(q.limit(1))).scalar_one_or_none()

    async def get_teacher_findings(
        self,
        teacher_id: int,
        campus_id: Optional[int],
        role: str,
    ) -> list[RiskFinding]:
        """Open risk findings for the students a teacher teaches.

        Resolves the teacher's active class assignments → the students
        enrolled in those classes → their open findings. RBAC-filtered by
        role (teachers never see finance/admissions) and campus-scoped.
        """
        allowed = self._category_filter_for_role(role)

        # 1. Classes this teacher is actively assigned to.
        ta_q = select(TeacherAssignment.class_id).where(
            TeacherAssignment.teacher_id == teacher_id,
            TeacherAssignment.status == "active",
        )
        if campus_id is not None:
            ta_q = ta_q.where(TeacherAssignment.campus_id == campus_id)
        class_ids = [r[0] for r in (await self.session.execute(ta_q)).all()]
        if not class_ids:
            return []

        # 2. Students actively enrolled in those classes — scoped to the
        #    current active academic year (a student may hold active
        #    enrollments across years; only the current one is relevant).
        active_year = await self._active_academic_year_id(campus_id)
        enr_q = select(Enrollment.student_id).where(
            Enrollment.class_id.in_(class_ids),
            Enrollment.status == "active",
        )
        if active_year is not None:
            enr_q = enr_q.where(Enrollment.academic_year_id == active_year)
        if campus_id is not None:
            enr_q = enr_q.where(Enrollment.campus_id == campus_id)
        student_ids = [r[0] for r in (await self.session.execute(enr_q)).all()]
        if not student_ids:
            return []

        # 3. Open findings for those students (role-filtered categories).
        q = (
            select(RiskFinding)
            .where(
                RiskFinding.student_id.in_(student_ids),
                RiskFinding.status == RISK_STATUS_OPEN,
                RiskFinding.category.in_(allowed),
            )
            .order_by(SEVERITY_RANK, RiskFinding.score.desc())
            .limit(100)
        )
        if campus_id is not None:
            q = q.where(RiskFinding.campus_id == campus_id)
        return list((await self.session.execute(q)).scalars().all())

    async def get_teacher_risk_summary(
        self,
        teacher_id: int,
        campus_id: Optional[int],
        role: str,
    ) -> dict[str, Any]:
        """Enriched teacher-facing summary: findings + student/class names.

        ``get_teacher_findings`` does the scoping; this joins student and
        class display info so the teacher dashboard can render directly.
        """
        findings = await self.get_teacher_findings(teacher_id, campus_id, role)
        if not findings:
            return {
                "total": 0,
                "by_severity": {"critical": 0, "high": 0, "medium": 0, "low": 0},
                "findings": [],
            }

        student_ids = [f.student_id for f in findings if f.student_id]
        students: dict[int, tuple[str, str]] = {}
        if student_ids:
            rows = (
                await self.session.execute(
                    select(Student.id, Student.first_name, Student.last_name, Student.student_number).where(
                        Student.id.in_(student_ids)
                    )
                )
            ).all()
            students = {
                r[0]: (f"{r[1]} {r[2]}".strip(), r[3]) for r in rows
            }

        # Map each finding's student → their enrollment class in the current
        # active academic year (deterministic — a student may hold active
        # enrollments across years, but we only care about the current one).
        active_year = await self._active_academic_year_id(campus_id)
        enr_q = select(Enrollment.student_id, Enrollment.class_id).where(
            Enrollment.student_id.in_(student_ids),
            Enrollment.status == "active",
        )
        if active_year is not None:
            enr_q = enr_q.where(Enrollment.academic_year_id == active_year)
        enr_rows = (await self.session.execute(enr_q)).all()
        student_class: dict[int, int] = {sid: cid for sid, cid in enr_rows}
        class_ids = list({cid for cid in student_class.values() if cid})
        classes: dict[int, str] = {}
        if class_ids:
            rows = (
                await self.session.execute(
                    select(Class.id, Class.name).where(Class.id.in_(class_ids))
                )
            ).all()
            classes = {r[0]: r[1] for r in rows}

        by_severity: dict[str, int] = {"critical": 0, "high": 0, "medium": 0, "low": 0}
        items: list[dict[str, Any]] = []
        for f in findings:
            by_severity[f.severity] = by_severity.get(f.severity, 0) + 1
            sid = f.student_id
            name, number = students.get(sid, (None, None))
            cid = student_class.get(sid)
            items.append(
                {
                    "id": f.id,
                    "student_id": sid,
                    "student_name": name,
                    "student_number": number,
                    "class_id": cid,
                    "class_name": classes.get(cid) if cid else None,
                    "rule_code": f.rule_code,
                    "category": f.category,
                    "severity": f.severity,
                    "score": f.score,
                    "reason": f.reason,
                    "recommended_action": f.recommended_action,
                    "detected_at": f.detected_at,
                    "evidence": f.evidence,
                }
            )

        return {
            "total": len(items),
            "by_severity": by_severity,
            "findings": items,
        }

    async def get_student_findings(
        self,
        student_id: int,
        campus_id: Optional[int],
        role: str,
    ) -> list[RiskFinding]:
        allowed = self._category_filter_for_role(role)
        q = (
            select(RiskFinding)
            .where(
                RiskFinding.student_id == student_id,
                RiskFinding.status == RISK_STATUS_OPEN,
                RiskFinding.category.in_(allowed),
            )
            .order_by(SEVERITY_RANK, RiskFinding.score.desc())
        )
        if campus_id is not None:
            q = q.where(RiskFinding.campus_id == campus_id)
        return list((await self.session.execute(q)).scalars().all())

    # ------------------------------------------------------------------
    # Lifecycle (audited)
    # ------------------------------------------------------------------

    async def _get_finding(self, finding_id: int, campus_id: Optional[int]) -> RiskFinding:
        q = select(RiskFinding).where(RiskFinding.id == finding_id)
        if campus_id is not None:
            q = q.where(RiskFinding.campus_id == campus_id)
        f = (await self.session.execute(q)).scalar_one_or_none()
        if f is None:
            raise NotFoundError(f"Risk finding {finding_id} not found")
        return f

    async def resolve_finding(
        self,
        finding_id: int,
        campus_id: Optional[int],
        actor_user_id: Optional[int],
        reason: str,
    ) -> RiskFinding:
        if not reason or not reason.strip():
            raise ValidationError("A resolution reason is required")
        f = await self._get_finding(finding_id, campus_id)
        if f.status == RISK_STATUS_RESOLVED:
            raise ValidationError("Finding is already resolved")
        now = datetime.datetime.now(datetime.timezone.utc)
        f.status = RISK_STATUS_RESOLVED
        f.resolved_at = now
        f.resolved_by = actor_user_id
        f.resolved_reason = reason.strip()
        await self.session.flush()

        await AuditService(self.session).record(
            user_id=actor_user_id,
            username=None,
            action="RESOLVE",
            resource_type="risk_finding",
            resource_id=str(f.id),
            details={
                "finding_id": f.id,
                "rule_code": f.rule_code,
                "entity_type": f.entity_type,
                "entity_id": f.entity_id,
                "reason": f.resolved_reason,
            },
            campus_id=campus_id,
        )
        await self.session.flush()
        return f

    async def acknowledge_finding(
        self,
        finding_id: int,
        campus_id: Optional[int],
        actor_user_id: Optional[int],
    ) -> RiskFinding:
        f = await self._get_finding(finding_id, campus_id)
        if f.status != RISK_STATUS_OPEN:
            raise ValidationError("Only open findings can be acknowledged")
        f.status = RISK_STATUS_ACKNOWLEDGED
        await self.session.flush()

        await AuditService(self.session).record(
            user_id=actor_user_id,
            username=None,
            action="ACKNOWLEDGE",
            resource_type="risk_finding",
            resource_id=str(f.id),
            details={"finding_id": f.id, "rule_code": f.rule_code},
            campus_id=campus_id,
        )
        await self.session.flush()
        return f
