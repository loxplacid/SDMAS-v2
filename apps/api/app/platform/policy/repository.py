"""Policy-as-code foundation — tenant-scoped repository.

Every query is built through :class:`TenantScopedRepository`, which pins
``campus_id`` at query-construction time — a caller from campus A can never
read or mutate a policy definition, version, or evaluation belonging to
campus B.
"""

from __future__ import annotations

import datetime
from typing import Optional, Sequence

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.multi_tenant.models import TenantContext
from app.multi_tenant.repository import TenantScopedRepository
from app.platform.policy.models import (
    PolicyDefinition,
    PolicyEvaluation,
    PolicyVersion,
)


class PolicyRepository(TenantScopedRepository):
    """Tenant-scoped data access for the policy engine."""

    def __init__(
        self,
        session: AsyncSession,
        tenant: Optional[TenantContext] = None,
    ) -> None:
        super().__init__(session, tenant)

    # ------------------------------------------------------------------
    # Definitions
    # ------------------------------------------------------------------

    async def create_policy(self, policy: PolicyDefinition) -> PolicyDefinition:
        self.session.add(policy)
        await self.session.flush()
        return policy

    async def get_policy(self, policy_def_id: int) -> Optional[PolicyDefinition]:
        return await self.get_by_id(PolicyDefinition, policy_def_id)

    async def get_policy_or_404(self, policy_def_id: int) -> PolicyDefinition:
        return await self.get_by_id_or_404(PolicyDefinition, policy_def_id, resource="policy")

    async def find_by_key(self, policy_id: str) -> Optional[PolicyDefinition]:
        query = self.scoped_query(PolicyDefinition).where(PolicyDefinition.policy_id == policy_id)
        result = await self.session.execute(query.limit(1))
        return result.scalars().first()

    async def list_policies(
        self,
        *,
        scope: Optional[str] = None,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[PolicyDefinition], int]:
        extra = []
        if scope:
            extra.append(PolicyDefinition.scope == scope)
        if status:
            extra.append(PolicyDefinition.status == status)
        return await self._list_by_tenant(
            PolicyDefinition,
            order_by_attr="id",
            skip=skip,
            limit=limit,
            extra_filters=extra or None,
        )

    # ------------------------------------------------------------------
    # Versions
    # ------------------------------------------------------------------

    async def create_version(self, version: PolicyVersion) -> PolicyVersion:
        self.session.add(version)
        await self.session.flush()
        return version

    async def get_version(self, version_id: int) -> Optional[PolicyVersion]:
        return await self.get_by_id(PolicyVersion, version_id)

    async def get_version_or_404(self, version_id: int) -> PolicyVersion:
        return await self.get_by_id_or_404(PolicyVersion, version_id, resource="policy version")

    async def next_version_number(self, policy_def_id: int) -> int:
        """The next sequential version number for a policy (1-based)."""
        query = (
            select(PolicyVersion.version)
            .where(PolicyVersion.policy_def_id == policy_def_id)
            .order_by(PolicyVersion.version.desc())
            .limit(1)
        )
        query = self._apply_tenant_to_count(query, PolicyVersion)
        result = await self.session.execute(query)
        latest = result.scalar()
        return (latest or 0) + 1

    async def list_versions(
        self,
        policy_def_id: int,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[PolicyVersion], int]:
        policy = await self.get_policy_or_404(policy_def_id)
        extra = [PolicyVersion.policy_def_id == policy.id]
        return await self._list_by_tenant(
            PolicyVersion,
            order_by_attr="version",
            skip=skip,
            limit=limit,
            extra_filters=extra,
        )

    async def find_current_version(self, policy_def_id: int) -> Optional[PolicyVersion]:
        query = self.scoped_query(PolicyVersion).where(
            PolicyVersion.policy_def_id == policy_def_id,
            PolicyVersion.is_current.is_(True),
        )
        result = await self.session.execute(query.limit(1))
        return result.scalars().first()

    async def find_effective_version(
        self,
        policy_def_id: int,
        at: datetime.datetime,
    ) -> Optional[PolicyVersion]:
        """The version effective at ``at``: ``effective_from <= at`` and
        (``effective_until`` is null or ``at < effective_until``); when
        several windows overlap, the highest version wins."""
        query = (
            self.scoped_query(PolicyVersion)
            .where(
                PolicyVersion.policy_def_id == policy_def_id,
                PolicyVersion.status == "published",
                PolicyVersion.effective_from.is_not(None),
                PolicyVersion.effective_from <= at,
            )
            .order_by(PolicyVersion.version.desc())
        )
        result = await self.session.execute(query)
        for version in result.scalars().all():
            if version.effective_until is None or at < version.effective_until:
                return version
        return None

    # ------------------------------------------------------------------
    # Evaluations (traceability)
    # ------------------------------------------------------------------

    async def create_evaluation(self, evaluation: PolicyEvaluation) -> PolicyEvaluation:
        self.session.add(evaluation)
        await self.session.flush()
        return evaluation

    async def list_evaluations(
        self,
        *,
        policy_id: Optional[str] = None,
        subject_type: Optional[str] = None,
        subject_id: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[PolicyEvaluation], int]:
        extra = []
        if policy_id:
            extra.append(PolicyEvaluation.policy_id == policy_id)
        if subject_type:
            extra.append(PolicyEvaluation.subject_type == subject_type)
        if subject_id:
            extra.append(PolicyEvaluation.subject_id == subject_id)
        return await self._list_by_tenant(
            PolicyEvaluation,
            order_by_attr="id",
            skip=skip,
            limit=limit,
            extra_filters=extra or None,
        )
