"""Universal reconciliation engine — tenant-scoped repository.

Every query is built through :class:`TenantScopedRepository`, which pins
``campus_id`` at query-construction time — a caller from campus A can never
read or mutate a reconciliation run, rule, match, exception, approval, or
evidence row belonging to campus B.
"""

from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.multi_tenant.models import TenantContext
from app.multi_tenant.repository import TenantScopedRepository
from app.platform.reconciliation.models import (
    ReconciliationApproval,
    ReconciliationEvidence,
    ReconciliationException,
    ReconciliationMatch,
    ReconciliationRuleConfig,
    ReconciliationRun,
)


class ReconciliationRepository(TenantScopedRepository):
    """Tenant-scoped data access for the reconciliation engine."""

    def __init__(
        self,
        session: AsyncSession,
        tenant: Optional[TenantContext] = None,
    ) -> None:
        super().__init__(session, tenant)

    # ------------------------------------------------------------------
    # Runs
    # ------------------------------------------------------------------

    async def create_run(self, run: ReconciliationRun) -> ReconciliationRun:
        self.session.add(run)
        await self.session.flush()
        return run

    async def get_run(self, run_id: int) -> Optional[ReconciliationRun]:
        return await self.get_by_id(ReconciliationRun, run_id)

    async def get_run_or_404(self, run_id: int) -> ReconciliationRun:
        return await self.get_by_id_or_404(ReconciliationRun, run_id, resource="reconciliation run")

    async def find_run_by_idempotency(self, idempotency_key: str) -> Optional[ReconciliationRun]:
        query = self.scoped_query(ReconciliationRun).where(
            ReconciliationRun.idempotency_key == idempotency_key
        )
        result = await self.session.execute(query.limit(1))
        return result.scalars().first()

    async def list_runs(
        self,
        *,
        run_type: Optional[str] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[ReconciliationRun], int]:
        extra = []
        if run_type:
            extra.append(ReconciliationRun.run_type == run_type)
        if status:
            extra.append(ReconciliationRun.status == status)
        return await self._list_by_tenant(
            ReconciliationRun,
            order_by_attr="id",
            skip=skip,
            limit=limit,
            extra_filters=extra or None,
        )

    # ------------------------------------------------------------------
    # Rule configs
    # ------------------------------------------------------------------

    async def create_rule(self, rule: ReconciliationRuleConfig) -> ReconciliationRuleConfig:
        self.session.add(rule)
        await self.session.flush()
        return rule

    async def get_rule(self, rule_id: int) -> Optional[ReconciliationRuleConfig]:
        return await self.get_by_id(ReconciliationRuleConfig, rule_id)

    async def find_rule(self, name: str) -> Optional[ReconciliationRuleConfig]:
        query = self.scoped_query(ReconciliationRuleConfig).where(
            ReconciliationRuleConfig.name == name,
            ReconciliationRuleConfig.is_active.is_(True),
        )
        result = await self.session.execute(query.limit(1))
        return result.scalars().first()

    async def list_rules(
        self, *, skip: int = 0, limit: int = 100
    ) -> tuple[Sequence[ReconciliationRuleConfig], int]:
        return await self._list_by_tenant(
            ReconciliationRuleConfig, order_by_attr="id", skip=skip, limit=limit
        )

    # ------------------------------------------------------------------
    # Matches
    # ------------------------------------------------------------------

    async def create_match(self, match: ReconciliationMatch) -> ReconciliationMatch:
        self.session.add(match)
        await self.session.flush()
        return match

    async def get_match(self, match_id: int) -> Optional[ReconciliationMatch]:
        return await self.get_by_id(ReconciliationMatch, match_id)

    async def get_match_or_404(self, match_id: int) -> ReconciliationMatch:
        return await self.get_by_id_or_404(
            ReconciliationMatch, match_id, resource="reconciliation match"
        )

    async def list_matches(
        self,
        run_id: int,
        *,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[ReconciliationMatch], int]:
        run = await self.get_run_or_404(run_id)
        extra = [ReconciliationMatch.run_id == run.id]
        if status:
            extra.append(ReconciliationMatch.status == status)
        return await self._list_by_tenant(
            ReconciliationMatch,
            order_by_attr="id",
            skip=skip,
            limit=limit,
            extra_filters=extra,
        )

    async def count_matches(self, run_id: int) -> dict[str, int]:
        """Per-status match counts for a run (summary building)."""
        run = await self.get_run_or_404(run_id)
        query = (
            select(ReconciliationMatch.status, func.count(ReconciliationMatch.id))
            .where(ReconciliationMatch.run_id == run.id)
            .group_by(ReconciliationMatch.status)
        )
        query = self._apply_tenant_to_count(query, ReconciliationMatch)
        result = await self.session.execute(query)
        return {status: count for status, count in result.all()}

    # ------------------------------------------------------------------
    # Exceptions
    # ------------------------------------------------------------------

    async def create_exception(self, exception: ReconciliationException) -> ReconciliationException:
        self.session.add(exception)
        await self.session.flush()
        return exception

    async def get_exception(self, exception_id: int) -> Optional[ReconciliationException]:
        return await self.get_by_id(ReconciliationException, exception_id)

    async def get_exception_or_404(self, exception_id: int) -> ReconciliationException:
        return await self.get_by_id_or_404(
            ReconciliationException, exception_id, resource="reconciliation exception"
        )

    async def list_exceptions(
        self,
        run_id: int,
        *,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[ReconciliationException], int]:
        run = await self.get_run_or_404(run_id)
        extra = [ReconciliationException.run_id == run.id]
        if status:
            extra.append(ReconciliationException.status == status)
        return await self._list_by_tenant(
            ReconciliationException,
            order_by_attr="id",
            skip=skip,
            limit=limit,
            extra_filters=extra,
        )

    async def open_exception_count(self, run_id: int) -> int:
        """Exceptions still open (not resolved/closed) for a run."""
        run = await self.get_run_or_404(run_id)
        query = select(func.count(ReconciliationException.id)).where(
            ReconciliationException.run_id == run.id,
            ReconciliationException.status.in_(["open", "in_review"]),
        )
        query = self._apply_tenant_to_count(query, ReconciliationException)
        result = await self.session.execute(query)
        return result.scalar() or 0

    # ------------------------------------------------------------------
    # Approvals
    # ------------------------------------------------------------------

    async def create_approval(self, approval: ReconciliationApproval) -> ReconciliationApproval:
        self.session.add(approval)
        await self.session.flush()
        return approval

    async def list_approvals(self, run_id: int) -> Sequence[ReconciliationApproval]:
        run = await self.get_run_or_404(run_id)
        query = self.scoped_query(ReconciliationApproval).where(
            ReconciliationApproval.run_id == run.id
        )
        result = await self.session.execute(
            query.order_by(ReconciliationApproval.created_at.desc())
        )
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # Evidence
    # ------------------------------------------------------------------

    async def create_evidence(self, evidence: ReconciliationEvidence) -> ReconciliationEvidence:
        self.session.add(evidence)
        await self.session.flush()
        return evidence

    async def list_evidence(self, run_id: int) -> Sequence[ReconciliationEvidence]:
        run = await self.get_run_or_404(run_id)
        query = self.scoped_query(ReconciliationEvidence).where(
            ReconciliationEvidence.run_id == run.id
        )
        result = await self.session.execute(
            query.order_by(ReconciliationEvidence.created_at.desc())
        )
        return list(result.scalars().all())
