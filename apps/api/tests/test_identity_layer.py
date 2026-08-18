"""Canonical identity layer tests (TASK 8).

Covers:

- deterministic matching rules (order/case/accent-insensitive, no AI)
- confidence scoring + manual review state (auto-confirm vs pending)
- canonical person lifecycle (create / update / get / list)
- external identity linking with per-source dedupe + resolution
- aliases
- propose_match idempotency + review (confirm / reject)
- merge source → target with before/after snapshots, history and audit
- tenant isolation (campus A can never see / mutate campus B identity data)
"""

from __future__ import annotations

import datetime

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.domains.audit.actors import ActorType, AuditActor
from app.domains.audit.models import AuditLog
from app.multi_tenant.models import TenantContext
from app.platform.identities.matching import (
    match_persons,
    normalize_email,
    normalize_name,
    normalize_phone,
)
from app.platform.identities.models import (
    MATCH_STATUS_CONFIRMED,
    MATCH_STATUS_PENDING,
    MATCH_STATUS_REJECTED,
    PERSON_STATUS_MERGED,
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
from app.platform.identities.service import IdentityService


@pytest.fixture
def tenant_a() -> TenantContext:
    return TenantContext(campus_id=1, institution_id=1, user_id=99)


@pytest.fixture
def tenant_b() -> TenantContext:
    return TenantContext(campus_id=2, institution_id=1, user_id=98)


def _actor(user_id: int = 99) -> AuditActor:
    return AuditActor(actor_type=ActorType.USER, actor_id=str(user_id))


def _person_create(**overrides) -> PersonCreate:
    base = {
        "entity_type": "student",
        "entity_id": 101,
        "first_name": "John",
        "last_name": "Doe",
        "date_of_birth": datetime.date(2010, 5, 4),
        "email": "john.doe@example.com",
        "phone": "+254 700 123456",
    }
    base.update(overrides)
    return PersonCreate(**base)


# ---------------------------------------------------------------------------
# Deterministic matching (pure, no DB)
# ---------------------------------------------------------------------------


class TestMatchingDeterminism:
    def test_name_dob_auto_confirms(self) -> None:
        p = match_persons(
            {"first_name": "John", "last_name": "Doe", "date_of_birth": "2010-05-04"},
            {"first_name": "Doe", "last_name": "John", "date_of_birth": "2010-05-04"},
        )
        assert p is not None
        assert p.matched_by == "name_dob"
        assert p.confidence >= 0.95
        assert p.auto_confirm is True
        assert p.status == MATCH_STATUS_CONFIRMED

    def test_name_dob_case_and_accent_insensitive(self) -> None:
        p = match_persons(
            {"first_name": "José", "last_name": "García", "date_of_birth": "2010-01-01"},
            {"first_name": "JOSE", "last_name": "GARCIA", "date_of_birth": "2010-01-01"},
        )
        assert p is not None
        assert p.matched_by == "name_dob"
        assert p.status == MATCH_STATUS_CONFIRMED

    def test_exact_external_id_auto_confirms(self) -> None:
        p = match_persons(
            {"source_system": "legacy_erp", "external_id": "ADM-001", "first_name": "A"},
            {"source_system": "legacy_erp", "external_id": "adm-001", "first_name": "B"},
        )
        assert p is not None
        assert p.matched_by == "exact_external_id"
        assert p.confidence >= 0.95
        assert p.status == MATCH_STATUS_CONFIRMED

    def test_external_id_requires_same_source_system(self) -> None:
        p = match_persons(
            {"source_system": "legacy_erp", "external_id": "X-1", "first_name": "A"},
            {"source_system": "rfid", "external_id": "X-1", "first_name": "B"},
        )
        assert p is None

    def test_email_only_is_pending_manual_review(self) -> None:
        p = match_persons(
            {"first_name": "X", "last_name": "Y", "email": "a@b.com"},
            {"first_name": "X", "last_name": "Z", "email": "A@B.COM "},
        )
        assert p is not None
        assert p.matched_by == "exact_email"
        assert p.confidence < 0.95
        assert p.status == MATCH_STATUS_PENDING

    def test_name_email_and_name_phone(self) -> None:
        p = match_persons(
            {"first_name": "Mary", "last_name": "Jane", "email": "m@x.com"},
            {"first_name": "Mary", "last_name": "Jane", "email": "m@x.com"},
        )
        assert p is not None
        assert p.matched_by == "name_email"
        p2 = match_persons(
            {"first_name": "Mary", "last_name": "Jane", "phone": "0700 123 456"},
            {"first_name": "Mary", "last_name": "Jane", "phone": "0700-123-456"},
        )
        assert p2 is not None
        assert p2.matched_by == "name_phone"

    def test_weak_signal_below_manual_threshold_returns_none(self) -> None:
        # A lone phone is still above MANUAL_THRESHOLD; two unrelated
        # people with nothing in common must not match.
        assert (
            match_persons(
                {"first_name": "Alice", "last_name": "A"},
                {"first_name": "Bob", "last_name": "B"},
            )
            is None
        )

    def test_deterministic_same_input_same_output(self) -> None:
        a = {"first_name": "John", "last_name": "Doe", "email": "jd@x.com"}
        b = {"first_name": "John", "last_name": "Doe", "email": "jd@x.com"}
        first = match_persons(a, b)
        assert first is not None
        for _ in range(5):
            again = match_persons(a, b)
            assert again is not None
            assert (again.matched_by, again.confidence) == (first.matched_by, first.confidence)
            assert again.evidence == first.evidence

    def test_normalizers(self) -> None:
        assert normalize_name("  John  DOE ") == normalize_name("doe john")
        assert normalize_email("  A@B.COM ") == "a@b.com"
        assert normalize_phone("0700 123 456") == normalize_phone("0700-123-456")

    def test_no_match_never_auto_confirms(self) -> None:
        assert match_persons({}, {}) is None


# ---------------------------------------------------------------------------
# Person lifecycle
# ---------------------------------------------------------------------------


class TestPersonLifecycle:
    async def test_create_person_records_history_and_audit(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = IdentityService(db_session, tenant_a)
        person = await svc.create_person(_person_create(), actor=_actor())
        assert person.id is not None
        assert person.campus_id == 1
        assert person.status == "active"

        history = await svc.history(person.id)
        assert [h.action for h in history] == ["created"]
        assert history[0].actor_id == 99

        entries = (await db_session.execute(select(AuditLog))).scalars().all()
        assert [e.action for e in entries] == ["CREATE"]
        assert entries[0].resource_type == "canonical_person"
        assert entries[0].campus_id == 1

    async def test_get_person_404(self, db_session: AsyncSession, tenant_a: TenantContext) -> None:
        svc = IdentityService(db_session, tenant_a)
        with pytest.raises(NotFoundError):
            await svc.get_person(9999)

    async def test_update_person(self, db_session: AsyncSession, tenant_a: TenantContext) -> None:
        svc = IdentityService(db_session, tenant_a)
        person = await svc.create_person(_person_create(), actor=_actor())
        updated = await svc.update_person(
            person.id, PersonUpdate(first_name="Johnny"), actor=_actor()
        )
        assert updated.first_name == "Johnny"
        actions = [h.action for h in await svc.history(person.id)]
        # History is newest-first (append-only audit trail).
        assert actions == ["updated", "created"]

    async def test_rejects_unknown_entity_type(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = IdentityService(db_session, tenant_a)
        # model_construct bypasses the Pydantic pattern so the service's own
        # entity-type validation (defense in depth) is exercised.
        alien = PersonCreate.model_construct(
            entity_type="alien", entity_id=1, first_name="A", last_name="B"
        )
        with pytest.raises(ValidationError):
            await svc.create_person(alien)

    async def test_list_people_filters_by_status(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = IdentityService(db_session, tenant_a)
        await svc.create_person(_person_create(entity_id=1), actor=_actor())
        await svc.create_person(_person_create(entity_id=2, first_name="Jane"), actor=_actor())
        people, total = await svc.list_people()
        assert total == 2
        archived, _ = await svc.list_people(status="archived")
        assert archived == []


# ---------------------------------------------------------------------------
# External identities
# ---------------------------------------------------------------------------


class TestExternalIdentities:
    async def test_link_and_resolve(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = IdentityService(db_session, tenant_a)
        person = await svc.create_person(_person_create(), actor=_actor())
        identity = await svc.link_external_identity(
            ExternalIdentityCreate(
                canonical_person_id=person.id,
                source_system="legacy_erp",
                external_id="ADM-001",
                external_name="John Doe",
                confidence=1.0,
            ),
            actor=_actor(),
        )
        assert identity.campus_id == 1

        resolved = await svc.resolve_by_external_id("legacy_erp", "ADM-001")
        assert resolved is not None and resolved.id == person.id
        assert await svc.resolve_by_external_id("legacy_erp", "NOPE") is None

        # history records the link
        actions = [h.action for h in await svc.history(person.id)]
        assert "linked" in actions

    async def test_duplicate_external_id_conflicts(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = IdentityService(db_session, tenant_a)
        p1 = await svc.create_person(_person_create(entity_id=1), actor=_actor())
        p2 = await svc.create_person(_person_create(entity_id=2, first_name="Jane"), actor=_actor())
        await svc.link_external_identity(
            ExternalIdentityCreate(
                canonical_person_id=p1.id, source_system="rfid", external_id="TAG-9"
            ),
            actor=_actor(),
        )
        with pytest.raises(ConflictError):
            await svc.link_external_identity(
                ExternalIdentityCreate(
                    canonical_person_id=p2.id, source_system="rfid", external_id="TAG-9"
                ),
                actor=_actor(),
            )

    async def test_same_external_id_different_source_ok(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = IdentityService(db_session, tenant_a)
        p = await svc.create_person(_person_create(), actor=_actor())
        await svc.link_external_identity(
            ExternalIdentityCreate(
                canonical_person_id=p.id, source_system="rfid", external_id="X-1"
            ),
            actor=_actor(),
        )
        await svc.link_external_identity(
            ExternalIdentityCreate(
                canonical_person_id=p.id, source_system="transport", external_id="X-1"
            ),
            actor=_actor(),
        )
        ids = await svc.list_external_identities(p.id)
        assert len(ids) == 2

    async def test_link_missing_person_404(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = IdentityService(db_session, tenant_a)
        with pytest.raises(NotFoundError):
            await svc.link_external_identity(
                ExternalIdentityCreate(
                    canonical_person_id=999, source_system="rfid", external_id="T-1"
                ),
                actor=_actor(),
            )

    async def test_alias_lifecycle(self, db_session: AsyncSession, tenant_a: TenantContext) -> None:
        svc = IdentityService(db_session, tenant_a)
        person = await svc.create_person(_person_create(), actor=_actor())
        alias = await svc.add_alias(
            IdentityAliasCreate(
                canonical_person_id=person.id, alias_type="name", alias_value="Johnny"
            ),
            actor=_actor(),
        )
        assert alias.campus_id == 1
        aliases = await svc.list_aliases(person.id)
        assert [a.alias_value for a in aliases] == ["Johnny"]


# ---------------------------------------------------------------------------
# Propose + review
# ---------------------------------------------------------------------------


class TestMatchProposeAndReview:
    async def test_propose_auto_confirms_on_strong_rule(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = IdentityService(db_session, tenant_a)
        p1 = await svc.create_person(_person_create(entity_id=1), actor=_actor())
        p2 = await svc.create_person(
            _person_create(
                entity_id=2,
                first_name="John",  # same name, same DOB → name_dob
                last_name="Doe",
                date_of_birth=datetime.date(2010, 5, 4),
                email="other@x.com",
            ),
            actor=_actor(),
        )
        match = await svc.propose_match(p1.id, p2.id, actor=_actor())
        assert match.matched_by == "name_dob"
        assert match.status == MATCH_STATUS_CONFIRMED
        assert match.confidence >= 0.95

    async def test_propose_weak_rule_pending_and_idempotent(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = IdentityService(db_session, tenant_a)
        p1 = await svc.create_person(
            _person_create(entity_id=1, email="shared@x.com", first_name="A", last_name="B"),
            actor=_actor(),
        )
        p2 = await svc.create_person(
            _person_create(entity_id=2, email="shared@x.com", first_name="C", last_name="D"),
            actor=_actor(),
        )
        match = await svc.propose_match(p1.id, p2.id, actor=_actor())
        assert match.status == MATCH_STATUS_PENDING
        # Idempotent: second proposal returns the same row, no duplicate.
        again = await svc.propose_match(p1.id, p2.id, actor=_actor())
        assert again.id == match.id
        matches, total = await svc.list_matches(status=MATCH_STATUS_PENDING)
        assert total == 1

    async def test_review_confirm_and_reject(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = IdentityService(db_session, tenant_a)
        p1 = await svc.create_person(
            _person_create(entity_id=1, email="s@x.com", first_name="A", last_name="B"),
            actor=_actor(),
        )
        p2 = await svc.create_person(
            _person_create(entity_id=2, email="s@x.com", first_name="C", last_name="D"),
            actor=_actor(),
        )
        match = await svc.propose_match(p1.id, p2.id, actor=_actor())
        assert match.status == MATCH_STATUS_PENDING

        confirmed = await svc.review_match(
            match.id, MatchReview(decision="confirm", reviewer_id=55), actor=_actor()
        )
        assert confirmed.status == MATCH_STATUS_CONFIRMED
        assert confirmed.reviewed_by == 55
        assert confirmed.reviewed_at is not None

        p3 = await svc.create_person(
            _person_create(entity_id=3, email="s@x.com", first_name="E", last_name="F"),
            actor=_actor(),
        )
        rejected = await svc.propose_match(p1.id, p3.id, actor=_actor())
        assert rejected.status == MATCH_STATUS_PENDING
        rejected = await svc.review_match(
            rejected.id, MatchReview(decision="reject"), actor=_actor()
        )
        assert rejected.status == MATCH_STATUS_REJECTED
        # Re-reviewing a rejected proposal conflicts.
        with pytest.raises(ConflictError):
            await svc.review_match(rejected.id, MatchReview(decision="confirm"), actor=_actor())

    async def test_propose_self_rejected(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = IdentityService(db_session, tenant_a)
        person = await svc.create_person(_person_create(), actor=_actor())
        with pytest.raises(ValidationError):
            await svc.propose_match(person.id, person.id, actor=_actor())

    async def test_propose_no_rule_fires(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = IdentityService(db_session, tenant_a)
        p1 = await svc.create_person(
            _person_create(entity_id=1, first_name="Alice", last_name="A"), actor=_actor()
        )
        p2 = await svc.create_person(
            _person_create(
                entity_id=2,
                first_name="Bob",
                last_name="B",
                email="bob@other.com",
                date_of_birth=datetime.date(2012, 1, 1),
                phone="+1 555 000 0000",
            ),
            actor=_actor(),
        )
        with pytest.raises(ValidationError):
            await svc.propose_match(p1.id, p2.id, actor=_actor())

    async def test_find_matches_against_probe(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = IdentityService(db_session, tenant_a)
        await svc.create_person(_person_create(entity_id=1), actor=_actor())
        await svc.create_person(
            _person_create(entity_id=2, first_name="Jane", last_name="Smith"), actor=_actor()
        )
        probe = {
            "first_name": "John",
            "last_name": "Doe",
            "date_of_birth": "2010-05-04",
        }
        candidates, total = await svc.find_matches(probe)
        assert total == 2
        assert len(candidates) == 1
        person, proposal = candidates[0]
        assert proposal["matched_by"] == "name_dob"
        assert proposal["status"] == MATCH_STATUS_CONFIRMED
        assert proposal["confidence"] >= 0.95

    async def test_pending_match_count(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = IdentityService(db_session, tenant_a)
        p1 = await svc.create_person(
            _person_create(entity_id=1, email="s@x.com", first_name="A", last_name="B"),
            actor=_actor(),
        )
        p2 = await svc.create_person(
            _person_create(entity_id=2, email="s@x.com", first_name="C", last_name="D"),
            actor=_actor(),
        )
        assert await svc.pending_match_count() == 0
        await svc.propose_match(p1.id, p2.id, actor=_actor())
        assert await svc.pending_match_count() == 1


# ---------------------------------------------------------------------------
# Merge
# ---------------------------------------------------------------------------


class TestMerge:
    async def test_merge_moves_identities_and_marks_source(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = IdentityService(db_session, tenant_a)
        source = await svc.create_person(_person_create(entity_id=1), actor=_actor())
        target = await svc.create_person(
            _person_create(entity_id=2, first_name="John", last_name="Doe", email="primary@x.com"),
            actor=_actor(),
        )
        identity = await svc.link_external_identity(
            ExternalIdentityCreate(
                canonical_person_id=source.id,
                source_system="legacy_erp",
                external_id="ERP-77",
            ),
            actor=_actor(),
        )
        await svc.add_alias(
            IdentityAliasCreate(
                canonical_person_id=source.id, alias_type="name", alias_value="J D"
            ),
            actor=_actor(),
        )

        merge = await svc.merge_people(
            MergeRequest(
                source_person_id=source.id,
                target_person_id=target.id,
                reason="Same person verified in ERP",
            ),
            actor=_actor(),
        )
        assert merge.status == "completed"
        assert merge.performed_by == 99

        # Source is merged; identities + aliases moved to target.
        source_ref = await svc.get_person(source.id)
        assert source_ref.status == PERSON_STATUS_MERGED
        target_ids = await svc.list_external_identities(target.id)
        assert [i.id for i in target_ids] == [identity.id]
        assert [a.alias_value for a in await svc.list_aliases(target.id)] == ["J D"]
        assert await svc.list_external_identities(source.id) == []

        # Snapshots captured + history on both sides + audit.
        assert merge.before_snapshot is not None
        assert merge.after_snapshot is not None
        assert merge.before_snapshot["source"]["id"] == source.id
        assert merge.after_snapshot["moved_external_identities"] == 1
        assert merge.after_snapshot["moved_aliases"] == 1
        actions = [h.action for h in await svc.history(source.id)]
        assert "merged" in actions
        actions_t = [h.action for h in await svc.history(target.id)]
        assert "merged_into" in actions_t
        entries = (await db_session.execute(select(AuditLog))).scalars().all()
        assert any(e.action == "MERGE" for e in entries)
        merge_entry = next(e for e in entries if e.action == "MERGE")
        import json as _json

        assert merge_entry.after_state is not None
        after_state = _json.loads(merge_entry.after_state)
        assert after_state["moved_external_identities"] == 1

    async def test_merge_self_and_merged_source_conflict(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = IdentityService(db_session, tenant_a)
        p1 = await svc.create_person(_person_create(entity_id=1), actor=_actor())
        p2 = await svc.create_person(_person_create(entity_id=2, first_name="Jane"), actor=_actor())
        with pytest.raises(ValidationError):
            await svc.merge_people(
                MergeRequest(source_person_id=p1.id, target_person_id=p1.id, reason="x"),
                actor=_actor(),
            )
        await svc.merge_people(
            MergeRequest(source_person_id=p1.id, target_person_id=p2.id, reason="x"),
            actor=_actor(),
        )
        with pytest.raises(ConflictError):
            await svc.merge_people(
                MergeRequest(source_person_id=p1.id, target_person_id=p2.id, reason="again"),
                actor=_actor(),
            )

    async def test_merge_requires_campus_scoped_people(
        self,
        db_session: AsyncSession,
        tenant_a: TenantContext,
        tenant_b: TenantContext,
    ) -> None:
        svc_a = IdentityService(db_session, tenant_a)
        svc_b = IdentityService(db_session, tenant_b)
        pa = await svc_a.create_person(_person_create(entity_id=1), actor=_actor())
        pb = await svc_b.create_person(
            _person_create(entity_id=1, first_name="Jane"), actor=_actor()
        )
        # svc_b cannot see pa → NotFound, and vice versa.
        with pytest.raises(NotFoundError):
            await svc_a.merge_people(
                MergeRequest(source_person_id=pa.id, target_person_id=pb.id, reason="x"),
                actor=_actor(),
            )
        with pytest.raises(NotFoundError):
            await svc_b.merge_people(
                MergeRequest(source_person_id=pa.id, target_person_id=pb.id, reason="x"),
                actor=_actor(),
            )

    async def test_merge_history_audit_trail(
        self, db_session: AsyncSession, tenant_a: TenantContext
    ) -> None:
        svc = IdentityService(db_session, tenant_a)
        p1 = await svc.create_person(_person_create(entity_id=1), actor=_actor())
        p2 = await svc.create_person(_person_create(entity_id=2, first_name="Jane"), actor=_actor())
        await svc.merge_people(
            MergeRequest(source_person_id=p1.id, target_person_id=p2.id, reason="duplicate"),
            actor=_actor(),
        )
        merges, total = await svc.list_merges()
        assert total == 1
        assert merges[0].reason == "duplicate"
        assert merges[0].campus_id == 1


# ---------------------------------------------------------------------------
# Tenant isolation
# ---------------------------------------------------------------------------


class TestTenantIsolation:
    async def test_cross_tenant_person_invisible(
        self, db_session: AsyncSession, tenant_a: TenantContext, tenant_b: TenantContext
    ) -> None:
        svc_a = IdentityService(db_session, tenant_a)
        svc_b = IdentityService(db_session, tenant_b)
        pa = await svc_a.create_person(_person_create(entity_id=1), actor=_actor())
        # Campus B cannot read campus A's person (isolation, not existence).
        with pytest.raises(NotFoundError):
            await svc_b.get_person(pa.id)

    async def test_cross_tenant_update_denied(
        self, db_session: AsyncSession, tenant_a: TenantContext, tenant_b: TenantContext
    ) -> None:
        svc_a = IdentityService(db_session, tenant_a)
        svc_b = IdentityService(db_session, tenant_b)
        pa = await svc_a.create_person(_person_create(entity_id=1), actor=_actor())
        with pytest.raises(NotFoundError):
            await svc_b.update_person(pa.id, PersonUpdate(first_name="Hacked"))

    async def test_cross_tenant_external_identity_denied(
        self, db_session: AsyncSession, tenant_a: TenantContext, tenant_b: TenantContext
    ) -> None:
        svc_a = IdentityService(db_session, tenant_a)
        svc_b = IdentityService(db_session, tenant_b)
        pa = await svc_a.create_person(_person_create(entity_id=1), actor=_actor())
        with pytest.raises(NotFoundError):
            await svc_b.link_external_identity(
                ExternalIdentityCreate(
                    canonical_person_id=pa.id, source_system="rfid", external_id="T-1"
                ),
                actor=_actor(),
            )

    async def test_same_external_id_ok_in_different_campuses(
        self, db_session: AsyncSession, tenant_a: TenantContext, tenant_b: TenantContext
    ) -> None:
        svc_a = IdentityService(db_session, tenant_a)
        svc_b = IdentityService(db_session, tenant_b)
        pa = await svc_a.create_person(_person_create(entity_id=1), actor=_actor())
        pb = await svc_b.create_person(
            _person_create(entity_id=1, first_name="Jane"), actor=_actor()
        )
        await svc_a.link_external_identity(
            ExternalIdentityCreate(
                canonical_person_id=pa.id, source_system="rfid", external_id="TAG-9"
            ),
            actor=_actor(),
        )
        # Campus B may use the same external id — campus scoping makes the
        # unique constraint per-campus, so this must succeed.
        await svc_b.link_external_identity(
            ExternalIdentityCreate(
                canonical_person_id=pb.id, source_system="rfid", external_id="TAG-9"
            ),
            actor=_actor(),
        )
        resolved_a = await svc_a.resolve_by_external_id("rfid", "TAG-9")
        resolved_b = await svc_b.resolve_by_external_id("rfid", "TAG-9")
        assert resolved_a is not None and resolved_a.id == pa.id
        assert resolved_b is not None and resolved_b.id == pb.id

    async def test_cross_tenant_match_review_denied(
        self, db_session: AsyncSession, tenant_a: TenantContext, tenant_b: TenantContext
    ) -> None:
        svc_a = IdentityService(db_session, tenant_a)
        svc_b = IdentityService(db_session, tenant_b)
        p1 = await svc_a.create_person(
            _person_create(entity_id=1, email="s@x.com", first_name="A", last_name="B"),
            actor=_actor(),
        )
        p2 = await svc_a.create_person(
            _person_create(entity_id=2, email="s@x.com", first_name="C", last_name="D"),
            actor=_actor(),
        )
        match = await svc_a.propose_match(p1.id, p2.id, actor=_actor())
        with pytest.raises(NotFoundError):
            await svc_b.review_match(match.id, MatchReview(decision="confirm"), actor=_actor())

    async def test_repository_denies_unscoped_access(self, db_session: AsyncSession) -> None:
        """Unscoped (no campus) access fails closed — platform scope required."""
        from app.core.exceptions import AuthorizationError

        repo = IdentityRepository(db_session)
        with pytest.raises(AuthorizationError):
            await repo.list_people()

        platform_repo = IdentityRepository(db_session, TenantContext(user_id=1, platform=True))
        people, total = await platform_repo.list_people()
        assert total == 0

    async def test_audit_entries_are_campus_scoped(
        self, db_session: AsyncSession, tenant_a: TenantContext, tenant_b: TenantContext
    ) -> None:
        svc_a = IdentityService(db_session, tenant_a)
        await svc_a.create_person(_person_create(entity_id=1), actor=_actor())
        entries = (await db_session.execute(select(AuditLog))).scalars().all()
        assert len(entries) == 1
        assert entries[0].campus_id == 1
