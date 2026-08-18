"""Canonical identity layer — tenant-scoped repository.

Every query is built through :class:`TenantScopedRepository`, which pins
``campus_id`` at query-construction time — a caller from campus A can never
read or mutate a canonical person, external identity, match, merge, or
history row belonging to campus B (IDOR closed in the repository layer).
"""

from __future__ import annotations

from typing import Any, Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.multi_tenant.models import TenantContext
from app.multi_tenant.repository import TenantScopedRepository
from app.platform.identities.models import (
    MATCH_STATUS_PENDING,
    CanonicalPerson,
    ExternalIdentity,
    IdentityAlias,
    IdentityHistory,
    IdentityMatch,
    IdentityMerge,
)


class IdentityRepository(TenantScopedRepository):
    """Tenant-scoped data access for the canonical identity layer."""

    def __init__(
        self,
        session: AsyncSession,
        tenant: Optional[TenantContext] = None,
    ) -> None:
        super().__init__(session, tenant)

    # ------------------------------------------------------------------
    # CanonicalPerson
    # ------------------------------------------------------------------

    async def create_person(self, person: CanonicalPerson) -> CanonicalPerson:
        self.session.add(person)
        await self.session.flush()
        return person

    async def get_person(self, person_id: int) -> Optional[CanonicalPerson]:
        return await self.get_by_id(CanonicalPerson, person_id)

    async def get_person_or_404(self, person_id: int) -> CanonicalPerson:
        return await self.get_by_id_or_404(CanonicalPerson, person_id, resource="canonical person")

    async def find_person_by_entity(
        self, entity_type: str, entity_id: int
    ) -> Optional[CanonicalPerson]:
        """Find the canonical person referencing an existing entity."""
        query = self.scoped_query(CanonicalPerson).where(
            CanonicalPerson.entity_type == entity_type,
            CanonicalPerson.entity_id == entity_id,
        )
        result = await self.session.execute(query.limit(1))
        return result.scalars().first()

    async def list_people(
        self,
        *,
        skip: int = 0,
        limit: int = 100,
        status: Optional[str] = None,
    ) -> tuple[Sequence[CanonicalPerson], int]:
        extra = [CanonicalPerson.status == status] if status else None
        return await self._list_by_tenant(
            CanonicalPerson,
            order_by_attr="id",
            skip=skip,
            limit=limit,
            extra_filters=extra,
        )

    # ------------------------------------------------------------------
    # ExternalIdentity
    # ------------------------------------------------------------------

    async def create_external_identity(self, identity: ExternalIdentity) -> ExternalIdentity:
        self.session.add(identity)
        await self.session.flush()
        return identity

    async def get_external_identity(self, identity_id: int) -> Optional[ExternalIdentity]:
        return await self.get_by_id(ExternalIdentity, identity_id)

    async def list_external_identities(self, person_id: int) -> Sequence[ExternalIdentity]:
        """All external identities linked to a canonical person."""
        query = self.scoped_query(ExternalIdentity).where(
            ExternalIdentity.canonical_person_id == person_id
        )
        result = await self.session.execute(query.order_by(ExternalIdentity.id))
        return list(result.scalars().all())

    async def find_external_identity(
        self, source_system: str, external_id: str
    ) -> Optional[ExternalIdentity]:
        query = self.scoped_query(ExternalIdentity).where(
            ExternalIdentity.source_system == source_system,
            ExternalIdentity.external_id == external_id,
        )
        result = await self.session.execute(query.limit(1))
        return result.scalars().first()

    async def person_by_external_id(
        self, source_system: str, external_id: str
    ) -> Optional[CanonicalPerson]:
        """Resolve a canonical person from an external identifier."""
        identity = await self.find_external_identity(source_system, external_id)
        if identity is None:
            return None
        return await self.get_person(identity.canonical_person_id)

    # ------------------------------------------------------------------
    # IdentityAlias
    # ------------------------------------------------------------------

    async def create_alias(self, alias: IdentityAlias) -> IdentityAlias:
        self.session.add(alias)
        await self.session.flush()
        return alias

    async def list_aliases(self, person_id: int) -> Sequence[IdentityAlias]:
        query = self.scoped_query(IdentityAlias).where(
            IdentityAlias.canonical_person_id == person_id,
            IdentityAlias.is_active.is_(True),
        )
        result = await self.session.execute(query.order_by(IdentityAlias.id))
        return list(result.scalars().all())

    # ------------------------------------------------------------------
    # IdentityMatch
    # ------------------------------------------------------------------

    async def create_match(self, match: IdentityMatch) -> IdentityMatch:
        self.session.add(match)
        await self.session.flush()
        return match

    async def get_match(self, match_id: int) -> Optional[IdentityMatch]:
        return await self.get_by_id(IdentityMatch, match_id)

    async def get_match_or_404(self, match_id: int) -> IdentityMatch:
        return await self.get_by_id_or_404(IdentityMatch, match_id, resource="identity match")

    async def existing_match(
        self, person_a_id: int, person_b_id: int, matched_by: str
    ) -> Optional[IdentityMatch]:
        """The stored proposal for an ordered pair + rule, if any."""
        query = self.scoped_query(IdentityMatch).where(
            IdentityMatch.person_a_id == person_a_id,
            IdentityMatch.person_b_id == person_b_id,
            IdentityMatch.matched_by == matched_by,
        )
        result = await self.session.execute(query.limit(1))
        return result.scalars().first()

    async def list_matches(
        self,
        *,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[IdentityMatch], int]:
        extra = [IdentityMatch.status == status] if status else None
        return await self._list_by_tenant(
            IdentityMatch,
            order_by_attr="id",
            skip=skip,
            limit=limit,
            extra_filters=extra,
        )

    async def pending_match_count(self) -> int:
        """Number of proposals awaiting manual review (dashboard KPI)."""
        query = self.scoped_count(IdentityMatch).where(IdentityMatch.status == MATCH_STATUS_PENDING)
        result = await self.session.execute(query)
        return result.scalar() or 0

    # ------------------------------------------------------------------
    # IdentityMerge
    # ------------------------------------------------------------------

    async def create_merge(self, merge: IdentityMerge) -> IdentityMerge:
        self.session.add(merge)
        await self.session.flush()
        return merge

    async def list_merges(
        self, *, skip: int = 0, limit: int = 100
    ) -> tuple[Sequence[IdentityMerge], int]:
        return await self._list_by_tenant(IdentityMerge, order_by_attr="id", skip=skip, limit=limit)

    # ------------------------------------------------------------------
    # IdentityHistory (append-only)
    # ------------------------------------------------------------------

    async def append_history(
        self,
        person_id: int,
        action: str,
        actor_id: Optional[int] = None,
        details: Optional[dict[str, Any]] = None,
    ) -> IdentityHistory:
        entry = IdentityHistory(
            campus_id=self._effective_campus_id(),
            canonical_person_id=person_id,
            action=action,
            actor_id=actor_id,
            details=details,
        )
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def list_history(self, person_id: int, *, limit: int = 100) -> Sequence[IdentityHistory]:
        query = self.scoped_query(IdentityHistory).where(
            IdentityHistory.canonical_person_id == person_id
        )
        result = await self.session.execute(
            query.order_by(IdentityHistory.created_at.desc(), IdentityHistory.id.desc()).limit(
                limit
            )
        )
        return list(result.scalars().all())
