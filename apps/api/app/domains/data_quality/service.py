"""Data Quality Center — service layer.

Responsibilities:
- ``recompute`` — run every deterministic check for a campus and persist
  the finding snapshot (upsert open findings, close stale ones as
  ``resolved`` with reason ``rule_no_longer_applies``), write an audit
  entry, and notify leadership about new high/critical findings.
- ``list_findings`` / ``get_overview`` — cheap reads from the persisted
  snapshot, RBAC-filtered by role (financial entity types are hidden from
  non-financial roles).
- ``resolve_finding`` / ``ignore_finding`` — explicit, audited lifecycle
  transitions.  Users can never silently alter a finding's severity or
  description — only its lifecycle status.
"""

from __future__ import annotations

import datetime
from typing import Any, Optional, Sequence

from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError, ValidationError
from app.domains.audit.service import AuditService
from app.domains.data_quality.checks import all_checks, run_all_checks
from app.domains.data_quality.models import (
    DQ_ENTITY_FEE_DUE,
    DQ_ENTITY_PAYMENT,
    DQ_STATUS_IGNORED,
    DQ_STATUS_OPEN,
    DQ_STATUS_RESOLVED,
    DQ_VALID_STATUSES,
    DataQualityFinding,
)

#: Roles that may read/act on data-quality findings.
DQ_ROLES = {"admin", "principal", "staff"}

#: Deterministic severity ordering (mirrors the risk engine).
SEVERITY_RANK = case(
    (DataQualityFinding.severity == "critical", 0),
    (DataQualityFinding.severity == "high", 1),
    (DataQualityFinding.severity == "medium", 2),
    (DataQualityFinding.severity == "low", 3),
    else_=4,
)

#: Severity weight used for the deterministic overall-quality score —
#: one open finding subtracts its weight from 100 (floored at 0).  Exposed
#: in the overview payload so the score is always explainable.
SEVERITY_PENALTY = {"critical": 5.0, "high": 2.5, "medium": 1.0, "low": 0.25}

#: Entity types that carry financial meaning and must be hidden from roles
#: without ``fees.view`` (staff).
FINANCIAL_ENTITY_TYPES = {DQ_ENTITY_PAYMENT, DQ_ENTITY_FEE_DUE}


class DataQualityService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    # ------------------------------------------------------------------
    # Recompute
    # ------------------------------------------------------------------

    async def recompute(
        self,
        campus_id: Optional[int],
        actor_user_id: Optional[int] = None,
        checks: Optional[set[str]] = None,
    ) -> dict[str, Any]:
        """Run all (or a subset of) checks and persist the snapshot.

        Returns counts: created / updated / resolved / total_open / run_at.
        """
        drafts = await run_all_checks(self.session, campus_id, checks=checks)

        now = datetime.datetime.now(datetime.timezone.utc)
        created = updated = 0
        kept_keys: set[tuple[Optional[int], str, str, int, str]] = set()

        for d in drafts:
            key = (campus_id, d.check_code, d.entity_type, d.entity_id, d.field)
            q = select(DataQualityFinding).where(
                DataQualityFinding.campus_id == campus_id,
                DataQualityFinding.check_code == d.check_code,
                DataQualityFinding.entity_type == d.entity_type,
                DataQualityFinding.entity_id == d.entity_id,
                DataQualityFinding.field == d.field,
                DataQualityFinding.status == DQ_STATUS_OPEN,
            )
            existing = (await self.session.execute(q)).scalar_one_or_none()
            if existing is None:
                self.session.add(
                    DataQualityFinding(
                        campus_id=campus_id,
                        check_code=d.check_code,
                        category=d.category,
                        severity=d.severity,
                        entity_type=d.entity_type,
                        entity_id=d.entity_id,
                        student_id=d.student_id,
                        field=d.field,
                        description=d.description,
                        evidence=d.evidence,
                        status=DQ_STATUS_OPEN,
                        detected_at=now,
                        last_verified_at=now,
                    )
                )
                created += 1
            else:
                # Re-open on each run while the condition persists; refresh
                # the deterministic snapshot so the evidence stays current.
                existing.status = DQ_STATUS_OPEN
                existing.severity = d.severity
                existing.description = d.description
                existing.evidence = d.evidence
                existing.last_verified_at = now
                updated += 1
            kept_keys.add(key)

        # Close stale open findings whose check no longer fires.  History is
        # preserved — the row is never deleted, only lifecycle-advanced.
        stale_q = select(DataQualityFinding).where(
            DataQualityFinding.campus_id == campus_id,
            DataQualityFinding.status == DQ_STATUS_OPEN,
        )
        stale_rows = (await self.session.execute(stale_q)).scalars().all()
        resolved = 0
        for f in stale_rows:
            key = (campus_id, f.check_code, f.entity_type, f.entity_id, f.field)
            if key not in kept_keys:
                f.status = DQ_STATUS_RESOLVED
                f.resolved_at = now
                f.resolved_by = None
                f.resolved_reason = "rule_no_longer_applies"
                resolved += 1

        await self.session.flush()

        await AuditService(self.session).record(
            user_id=actor_user_id,
            username=None,
            action="RUN",
            resource_type="data_quality_recompute",
            details={
                "campus_id": campus_id,
                "checks_run": len(drafts) and len(all_checks()),
                "created": created,
                "updated": updated,
                "resolved": resolved,
            },
            campus_id=campus_id,
        )
        await self.session.flush()

        await self._notify_new_findings(campus_id, actor_user_id)

        total_open = (
            await self.session.execute(
                select(func.count(DataQualityFinding.id)).where(
                    DataQualityFinding.campus_id == campus_id,
                    DataQualityFinding.status == DQ_STATUS_OPEN,
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

            q = select(User.id).where(
                User.is_active.is_(True),
                User.role.in_(["admin", "principal"]),
            )
            if campus_id is not None:
                q = q.where(User.campus_id == campus_id)
            rows = (await self.session.execute(q)).all()
            target_ids = [r[0] for r in rows if r[0] != actor_user_id]
            if not target_ids:
                return

            counts = await self.get_overview(campus_id, role="admin")
            severe = counts.get("critical", 0) + counts.get("high", 0)
            if severe == 0:
                return

            from app.domains.notifications.service import NotificationService

            svc = NotificationService(self.session)
            for uid in target_ids:
                await svc.create_notification(
                    user_id=uid,
                    type="data_quality_alert",
                    title="Data quality issues found",
                    message=(
                        f"{severe} high/critical data-quality finding(s) are open "
                        "for your school. Review them in the Data Quality Center."
                    ),
                    data={"campus_id": campus_id, "severity_count": severe},
                )
            await self.session.flush()
        except Exception:  # noqa: BLE001 — notifications are best-effort
            return

    # ------------------------------------------------------------------
    # Reads (RBAC-filtered)
    # ------------------------------------------------------------------

    def _entity_filter_for_role(self, role: str) -> set[str]:
        """Entity types the role may see (financial data guarded)."""
        if role == "admin":
            return {"student", "attendance_record", "fee_due", "payment", "enrollment"}
        if role == "principal":
            return {"student", "attendance_record", "fee_due", "payment", "enrollment"}
        # staff: no financial entity types (payments / fee dues).
        return {"student", "attendance_record", "enrollment"}

    async def list_findings(
        self,
        campus_id: Optional[int],
        role: str,
        *,
        category: Optional[str] = None,
        severity: Optional[str] = None,
        status: Optional[str] = None,
        check_code: Optional[str] = None,
        entity_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[DataQualityFinding], int]:
        allowed = self._entity_filter_for_role(role)
        base = [DataQualityFinding.campus_id == campus_id]
        count_base = list(base)

        if entity_type is not None:
            if entity_type not in allowed:
                return [], 0
            base.append(DataQualityFinding.entity_type == entity_type)
            count_base.append(DataQualityFinding.entity_type == entity_type)
        else:
            base.append(DataQualityFinding.entity_type.in_(allowed))
            count_base.append(DataQualityFinding.entity_type.in_(allowed))
        if category is not None:
            base.append(DataQualityFinding.category == category)
            count_base.append(DataQualityFinding.category == category)
        if severity is not None:
            base.append(DataQualityFinding.severity == severity)
            count_base.append(DataQualityFinding.severity == severity)
        if status is not None:
            if status not in DQ_VALID_STATUSES:
                return [], 0
            base.append(DataQualityFinding.status == status)
            count_base.append(DataQualityFinding.status == status)
        if check_code is not None:
            base.append(DataQualityFinding.check_code == check_code)
            count_base.append(DataQualityFinding.check_code == check_code)

        total = (
            await self.session.execute(
                select(func.count(DataQualityFinding.id)).where(*count_base)
            )
        ).scalar() or 0
        q = (
            select(DataQualityFinding)
            .where(*base)
            .order_by(SEVERITY_RANK, DataQualityFinding.last_verified_at.desc())
            .offset(skip)
            .limit(limit)
        )
        rows = (await self.session.execute(q)).scalars().all()
        return rows, total

    async def get_overview(
        self, campus_id: Optional[int], role: str = "admin"
    ) -> dict[str, Any]:
        """Severity/category counts of open findings + overall quality score.

        The overall quality score is deterministic: 100 minus the sum of
        open-finding penalties (see ``SEVERITY_PENALTY``), floored at 0.
        The weights are returned so the number is always explainable.
        """
        allowed = self._entity_filter_for_role(role)
        base = [
            DataQualityFinding.campus_id == campus_id,
            DataQualityFinding.status == DQ_STATUS_OPEN,
            DataQualityFinding.entity_type.in_(allowed),
        ]
        rows = (
            await self.session.execute(
                select(
                    DataQualityFinding.severity,
                    func.count(DataQualityFinding.id),
                )
                .where(*base)
                .group_by(DataQualityFinding.severity)
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
                    DataQualityFinding.category,
                    func.count(DataQualityFinding.id),
                )
                .where(*base)
                .group_by(DataQualityFinding.category)
            )
        ).all()
        counts["by_category"] = {cat: n for cat, n in by_category}

        penalty = sum(SEVERITY_PENALTY[s] * counts[s] for s in SEVERITY_PENALTY)
        counts["overall_quality"] = round(max(0.0, 100.0 - penalty), 1)
        counts["severity_weights"] = SEVERITY_PENALTY
        counts["total_checks"] = len(all_checks())
        return counts

    # ------------------------------------------------------------------
    # Lifecycle transitions (audited)
    # ------------------------------------------------------------------

    async def _get_finding(
        self, finding_id: int, campus_id: Optional[int]
    ) -> DataQualityFinding:
        f = (
            await self.session.execute(
                select(DataQualityFinding).where(
                    DataQualityFinding.id == finding_id,
                    DataQualityFinding.campus_id == campus_id,
                )
            )
        ).scalar_one_or_none()
        if f is None:
            raise NotFoundError("Data quality finding not found")
        return f

    async def resolve_finding(
        self,
        finding_id: int,
        campus_id: Optional[int],
        actor_user_id: Optional[int],
        reason: str,
    ) -> DataQualityFinding:
        if not reason or not reason.strip():
            raise ValidationError("A resolution reason is required")
        f = await self._get_finding(finding_id, campus_id)
        if f.status == DQ_STATUS_RESOLVED:
            raise ValidationError("Finding is already resolved")
        now = datetime.datetime.now(datetime.timezone.utc)
        f.status = DQ_STATUS_RESOLVED
        f.resolved_at = now
        f.resolved_by = actor_user_id
        f.resolved_reason = reason.strip()
        await self.session.flush()

        await AuditService(self.session).record(
            user_id=actor_user_id,
            username=None,
            action="RESOLVE",
            resource_type="data_quality_finding",
            resource_id=str(f.id),
            details={
                "finding_id": f.id,
                "check_code": f.check_code,
                "entity_type": f.entity_type,
                "entity_id": f.entity_id,
                "reason": f.resolved_reason,
            },
            campus_id=campus_id,
        )
        await self.session.flush()
        return f

    async def ignore_finding(
        self,
        finding_id: int,
        campus_id: Optional[int],
        actor_user_id: Optional[int],
        reason: str,
    ) -> DataQualityFinding:
        if not reason or not reason.strip():
            raise ValidationError("An ignore reason is required")
        f = await self._get_finding(finding_id, campus_id)
        if f.status == DQ_STATUS_IGNORED:
            raise ValidationError("Finding is already ignored")
        now = datetime.datetime.now(datetime.timezone.utc)
        f.status = DQ_STATUS_IGNORED
        f.resolved_at = now
        f.resolved_by = actor_user_id
        f.resolved_reason = reason.strip()
        await self.session.flush()

        await AuditService(self.session).record(
            user_id=actor_user_id,
            username=None,
            action="IGNORE",
            resource_type="data_quality_finding",
            resource_id=str(f.id),
            details={
                "finding_id": f.id,
                "check_code": f.check_code,
                "entity_type": f.entity_type,
                "entity_id": f.entity_id,
                "reason": f.resolved_reason,
            },
            campus_id=campus_id,
        )
        await self.session.flush()
        return f
