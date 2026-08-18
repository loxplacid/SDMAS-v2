"""Canonical identity layer — application service.

Owns the identity lifecycle:

- create / update canonical persons (referencing existing entities)
- link external identifiers (legacy ERP, biometric, RFID, transport,
  external orgs) with dedupe and per-source uniqueness
- deterministic matching of candidates against a probe
  (:mod:`app.platform.identities.matching`)
- manual review of pending proposals (confirm / reject)
- merge source → target with before/after snapshots and append-only
  history + audit log

Every operation is tenant-scoped through the repository and audited through
the existing audit domain, so identity activity is observable and traceable.
"""

from __future__ import annotations

import logging
from typing import Any, Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, ValidationError
from app.domains.audit.actors import ActorType, AuditActor
from app.domains.audit.service import AuditService
from app.multi_tenant.models import TenantContext
from app.platform.identities.matching import match_persons
from app.platform.identities.models import (
    MATCH_STATUS_CONFIRMED,
    MATCH_STATUS_PENDING,
    MATCH_STATUS_REJECTED,
    MERGE_STATUS_COMPLETED,
    PERSON_STATUS_ACTIVE,
    PERSON_STATUS_MERGED,
    REFERENCED_ENTITY_TYPES,
    CanonicalPerson,
    ExternalIdentity,
    IdentityAlias,
    IdentityHistory,
    IdentityMatch,
    IdentityMerge,
)
from app.platform.identities.repository import IdentityRepository
from app.platform.identities.schemas import (
    ExternalIdentityCreate,
    IdentityAliasCreate,
    MatchReview,
    MergeRequest,
    PersonCreate,
    PersonUpdate,
)

logger = logging.getLogger(__name__)


class IdentityService:
    """Canonical identity operations (one tenant per instance)."""

    def __init__(
        self,
        session: AsyncSession,
        tenant: Optional[TenantContext] = None,
    ) -> None:
        self.session = session
        self.tenant = tenant
        self.repo = IdentityRepository(session, tenant)
        self.audit = AuditService(session, tenant)

    # ------------------------------------------------------------------
    # Persons
    # ------------------------------------------------------------------

    async def create_person(
        self, data: PersonCreate, actor: AuditActor | None = None
    ) -> CanonicalPerson:
        if data.entity_type not in REFERENCED_ENTITY_TYPES:
            raise ValidationError(f"entity_type must be one of {sorted(REFERENCED_ENTITY_TYPES)}")
        person = CanonicalPerson(
            campus_id=self.repo._effective_campus_id(),
            entity_type=data.entity_type,
            entity_id=data.entity_id,
            first_name=data.first_name,
            last_name=data.last_name,
            date_of_birth=data.date_of_birth,
            email=data.email,
            phone=data.phone,
            status=PERSON_STATUS_ACTIVE,
        )
        person = await self.repo.create_person(person)
        await self.repo.append_history(
            person.id,
            "created",
            actor_id=_actor_id(actor),
            details={"entity_type": data.entity_type, "entity_id": data.entity_id},
        )
        await self.audit.record(
            action="CREATE",
            resource_type="canonical_person",
            resource_id=str(person.id),
            actor=actor,
            details={"entity_type": data.entity_type, "entity_id": data.entity_id},
        )
        return person

    async def get_person(self, person_id: int) -> CanonicalPerson:
        return await self.repo.get_person_or_404(person_id)

    async def update_person(
        self, person_id: int, data: PersonUpdate, actor: AuditActor | None = None
    ) -> CanonicalPerson:
        person = await self.repo.get_person_or_404(person_id)
        changed: dict[str, Any] = {}
        for field in ("first_name", "last_name", "date_of_birth", "email", "phone", "status"):
            value = getattr(data, field)
            if value is not None:
                setattr(person, field, value)
                changed[field] = _jsonable(value)
        if changed:
            await self.session.flush()
            await self.repo.append_history(
                person.id, "updated", actor_id=_actor_id(actor), details=changed
            )
            await self.audit.record(
                action="UPDATE",
                resource_type="canonical_person",
                resource_id=str(person.id),
                actor=actor,
                after_state=changed,
            )
        return person

    async def list_people(
        self, *, skip: int = 0, limit: int = 100, status: Optional[str] = None
    ) -> tuple[Sequence[CanonicalPerson], int]:
        return await self.repo.list_people(skip=skip, limit=limit, status=status)

    # ------------------------------------------------------------------
    # External identities
    # ------------------------------------------------------------------

    async def link_external_identity(
        self, data: ExternalIdentityCreate, actor: AuditActor | None = None
    ) -> ExternalIdentity:
        """Link an external identifier to a canonical person (tenant-scoped).

        Raises :class:`ConflictError` when the same ``(source_system,
        external_id)`` is already linked — within this campus the pair is
        unique (DB constraint backs this up).  Raises :class:`NotFoundError`
        when the target person does not exist in this campus.
        """
        person = await self.repo.get_person_or_404(data.canonical_person_id)
        existing = await self.repo.find_external_identity(data.source_system, data.external_id)
        if existing is not None:
            raise ConflictError(
                f"External identity {data.source_system}:{data.external_id} is already linked"
            )
        identity = ExternalIdentity(
            campus_id=self.repo._effective_campus_id(),
            canonical_person_id=person.id,
            source_system=data.source_system,
            external_id=data.external_id,
            external_name=data.external_name,
            confidence=data.confidence,
        )
        identity = await self.repo.create_external_identity(identity)
        await self.repo.append_history(
            person.id,
            "linked",
            actor_id=_actor_id(actor),
            details={"source_system": data.source_system, "external_id": data.external_id},
        )
        await self.audit.record(
            action="LINK",
            resource_type="external_identity",
            resource_id=str(identity.id),
            actor=actor,
            details={
                "canonical_person_id": person.id,
                "source_system": data.source_system,
                "external_id": data.external_id,
            },
        )
        return identity

    async def list_external_identities(self, person_id: int) -> Sequence[ExternalIdentity]:
        person = await self.repo.get_person_or_404(person_id)
        return await self.repo.list_external_identities(person.id)

    async def resolve_by_external_id(
        self, source_system: str, external_id: str
    ) -> Optional[CanonicalPerson]:
        """Resolve the canonical person for an external identifier, or None."""
        return await self.repo.person_by_external_id(source_system, external_id)

    # ------------------------------------------------------------------
    # Aliases
    # ------------------------------------------------------------------

    async def add_alias(
        self, data: IdentityAliasCreate, actor: AuditActor | None = None
    ) -> IdentityAlias:
        person = await self.repo.get_person_or_404(data.canonical_person_id)
        alias = IdentityAlias(
            campus_id=self.repo._effective_campus_id(),
            canonical_person_id=person.id,
            alias_type=data.alias_type,
            alias_value=data.alias_value,
        )
        alias = await self.repo.create_alias(alias)
        await self.repo.append_history(
            person.id,
            "alias_added",
            actor_id=_actor_id(actor),
            details={"alias_type": data.alias_type, "alias_value": data.alias_value},
        )
        return alias

    async def list_aliases(self, person_id: int) -> Sequence[IdentityAlias]:
        person = await self.repo.get_person_or_404(person_id)
        return await self.repo.list_aliases(person.id)

    # ------------------------------------------------------------------
    # Matching
    # ------------------------------------------------------------------

    async def find_matches(
        self,
        probe: dict[str, Any],
        *,
        limit: int = 10,
        skip: int = 0,
    ) -> tuple[list[tuple[CanonicalPerson, dict[str, Any]]], int]:
        """Deterministically match a probe against this campus's people.

        Returns ``(candidate, proposal_dict)`` rows sorted by confidence
        descending.  Matching is deterministic (same probe → same
        proposals), and persistence happens only via :meth:`propose_match`
        for a chosen pair — scanning never writes rows, so repeated scans
        are side-effect free and idempotent.
        """
        people, total = await self.repo.list_people(limit=400)
        candidates: list[tuple[CanonicalPerson, dict[str, Any]]] = []
        for person in people:
            proposal = match_persons(probe, _person_attrs(person))
            if proposal is None:
                continue
            candidates.append(
                (
                    person,
                    {
                        "matched_by": proposal.matched_by,
                        "confidence": proposal.confidence,
                        "evidence": proposal.evidence,
                        "status": proposal.status,
                    },
                )
            )
        candidates.sort(key=lambda row: row[1]["confidence"], reverse=True)
        return candidates[skip : skip + limit], total

    async def propose_match(
        self,
        person_a_id: int,
        person_b_id: int,
        actor: AuditActor | None = None,
    ) -> IdentityMatch:
        """Deterministically propose a match between two canonical people.

        Auto-confirms when the rule clears the auto-confirm threshold;
        otherwise the proposal is stored ``pending`` for manual review.
        Idempotent: an existing proposal for the same ordered pair + rule
        is returned unchanged.
        """
        a = await self.repo.get_person_or_404(person_a_id)
        b = await self.repo.get_person_or_404(person_b_id)
        if a.id == b.id:
            raise ValidationError("A person cannot match themselves")

        proposal = match_persons(_person_attrs(a), _person_attrs(b))
        if proposal is None:
            raise ValidationError(
                "No deterministic rule fired with enough confidence for this pair"
            )

        existing = await self.repo.existing_match(a.id, b.id, proposal.matched_by)
        if existing is not None:
            return existing

        status = MATCH_STATUS_CONFIRMED if proposal.auto_confirm else MATCH_STATUS_PENDING
        match = IdentityMatch(
            campus_id=self.repo._effective_campus_id(),
            person_a_id=a.id,
            person_b_id=b.id,
            matched_by=proposal.matched_by,
            confidence=proposal.confidence,
            evidence=proposal.evidence,
            status=status,
        )
        match = await self.repo.create_match(match)
        await self.repo.append_history(
            a.id,
            "matched",
            actor_id=_actor_id(actor),
            details={
                "other_person_id": b.id,
                "matched_by": proposal.matched_by,
                "confidence": proposal.confidence,
                "status": status,
            },
        )
        await self.audit.record(
            action="MATCH",
            resource_type="identity_match",
            resource_id=str(match.id),
            actor=actor,
            details={
                "person_a_id": a.id,
                "person_b_id": b.id,
                "matched_by": proposal.matched_by,
                "confidence": proposal.confidence,
                "status": status,
            },
        )
        return match

    async def review_match(
        self, match_id: int, review: MatchReview, actor: AuditActor | None = None
    ) -> IdentityMatch:
        """Confirm or reject a pending proposal (manual review)."""
        match = await self.repo.get_match_or_404(match_id)
        if match.status == MATCH_STATUS_REJECTED:
            raise ConflictError("This proposal was already rejected")
        reviewer = review.reviewer_id or _actor_id(actor)
        match.status = (
            MATCH_STATUS_CONFIRMED if review.decision == "confirm" else MATCH_STATUS_REJECTED
        )
        match.reviewed_by = reviewer
        match.reviewed_at = _now()
        await self.session.flush()
        await self.repo.append_history(
            match.person_a_id,
            "reviewed",
            actor_id=reviewer,
            details={
                "match_id": match.id,
                "person_b_id": match.person_b_id,
                "decision": review.decision,
            },
        )
        await self.audit.record(
            action="REVIEW",
            resource_type="identity_match",
            resource_id=str(match.id),
            actor=actor,
            details={"decision": review.decision, "status": match.status},
        )
        return match

    async def list_matches(
        self, *, status: Optional[str] = None, skip: int = 0, limit: int = 100
    ) -> tuple[Sequence[IdentityMatch], int]:
        return await self.repo.list_matches(status=status, skip=skip, limit=limit)

    async def pending_match_count(self) -> int:
        return await self.repo.pending_match_count()

    # ------------------------------------------------------------------
    # Merges
    # ------------------------------------------------------------------

    async def merge_people(
        self, request: MergeRequest, actor: AuditActor | None = None
    ) -> IdentityMerge:
        """Fold ``source`` into ``target`` (same campus only).

        Moves external identities + active aliases to the target, marks the
        source ``merged``, and records before/after snapshots plus history
        and an audit entry.  Idempotency: merging an already-merged source
        raises :class:`ConflictError` instead of double-applying.
        """
        source = await self.repo.get_person_or_404(request.source_person_id)
        target = await self.repo.get_person_or_404(request.target_person_id)
        if source.id == target.id:
            raise ValidationError("Cannot merge a person into themselves")
        if source.status == PERSON_STATUS_MERGED:
            raise ConflictError(f"Person {source.id} is already merged")

        before = {
            "source": _person_snapshot(source),
            "target": _person_snapshot(target),
        }

        # Move external identities + aliases to the target.
        source_ids = await self.repo.list_external_identities(source.id)
        source_aliases = await self.repo.list_aliases(source.id)
        for identity in source_ids:
            identity.canonical_person_id = target.id
        for alias in source_aliases:
            alias.canonical_person_id = target.id

        source.status = PERSON_STATUS_MERGED
        await self.session.flush()

        after = {
            "source": _person_snapshot(source),
            "target": _person_snapshot(target),
            "moved_external_identities": len(source_ids),
            "moved_aliases": len(source_aliases),
        }
        merge = IdentityMerge(
            campus_id=self.repo._effective_campus_id(),
            source_person_id=source.id,
            target_person_id=target.id,
            reason=request.reason,
            status=MERGE_STATUS_COMPLETED,
            performed_by=_actor_id(actor),
            before_snapshot=before,
            after_snapshot=after,
        )
        merge = await self.repo.create_merge(merge)
        await self.repo.append_history(
            source.id,
            "merged",
            actor_id=_actor_id(actor),
            details={"target_person_id": target.id, "merge_id": merge.id, "reason": request.reason},
        )
        await self.repo.append_history(
            target.id,
            "merged_into",
            actor_id=_actor_id(actor),
            details={"source_person_id": source.id, "merge_id": merge.id},
        )
        await self.audit.record(
            action="MERGE",
            resource_type="identity_merge",
            resource_id=str(merge.id),
            actor=actor,
            before_state=before,
            after_state=after,
            details={"reason": request.reason},
        )
        return merge

    async def list_merges(
        self, *, skip: int = 0, limit: int = 100
    ) -> tuple[Sequence[IdentityMerge], int]:
        return await self.repo.list_merges(skip=skip, limit=limit)

    # ------------------------------------------------------------------
    # History
    # ------------------------------------------------------------------

    async def history(self, person_id: int, *, limit: int = 100) -> Sequence[IdentityHistory]:
        person = await self.repo.get_person_or_404(person_id)
        return await self.repo.list_history(person.id, limit=limit)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now():
    import datetime

    return datetime.datetime.now(datetime.timezone.utc)


def _actor_id(actor: AuditActor | None) -> Optional[int]:
    if actor is None or actor.actor_type != ActorType.USER:
        return None
    raw = actor.actor_id
    if raw is None:
        return None
    try:
        return int(raw)
    except (TypeError, ValueError):
        return None


def _person_attrs(person: CanonicalPerson) -> dict[str, Any]:
    return {
        "first_name": person.first_name,
        "last_name": person.last_name,
        "date_of_birth": person.date_of_birth,
        "email": person.email,
        "phone": person.phone,
        "source_system": None,
        "external_id": None,
    }


def _person_snapshot(person: CanonicalPerson) -> dict[str, Any]:
    return {
        "id": person.id,
        "entity_type": person.entity_type,
        "entity_id": person.entity_id,
        "first_name": person.first_name,
        "last_name": person.last_name,
        "date_of_birth": person.date_of_birth.isoformat() if person.date_of_birth else None,
        "email": person.email,
        "phone": person.phone,
        "status": person.status,
    }


def _jsonable(value: Any) -> Any:
    if hasattr(value, "isoformat"):
        return value.isoformat()
    return value
