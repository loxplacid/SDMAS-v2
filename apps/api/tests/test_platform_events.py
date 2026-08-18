"""Tests for the canonical event envelope (app/platform/events).

Covers:
- Envelope construction from standard and legacy events (field mapping)
- Deterministic serialization (stable canonical bytes)
- Integrity metadata (digest present, changes when payload changes, validates)
- Validation (required fields, types, version, timestamp, integrity)
- Backward compatibility with the existing serialize_event envelope
- Causation-chain propagation through the in-process dispatcher
- Outbox persistence of the canonical fields (event_version / causation_id / source)
"""

from __future__ import annotations

import hashlib
import json
import uuid
from dataclasses import field

# Import domain models so Base.metadata.create_all resolves FKs (same
# pattern as test_domain_events.py).
from app.domains.academic import models as _academic_models  # noqa: F401
from app.domains.events.base import DomainEvent, serialize_event
from app.domains.events.context import event_context
from app.domains.events.dispatcher import DomainEventDispatcher
from app.domains.events.events import StudentCreatedEvent
from app.domains.events.outbox import OutboxRepository, publish_durable
from app.domains.notifications.events import (
    FeeDueCreatedEvent as LegacyFeeDueCreatedEvent,
)
from app.domains.student import models as _student_models  # noqa: F401
from app.platform.events import (
    CANONICAL_VERSION,
    CanonicalEnvelope,
    compute_integrity,
    envelope_from_event,
    from_canonical_dict,
    to_canonical_dict,
    validate_envelope,
)

# ===========================================================================
# Envelope construction
# ===========================================================================


class TestEnvelopeConstruction:
    def test_standard_event_maps_all_fields(self):
        event = StudentCreatedEvent(
            student_id=42,
            student_number="S42",
            full_name="Grace Hopper",
            school_id=7,
            actor_user_id=3,
            correlation_id="corr-1",
        )
        env = envelope_from_event(event)
        assert env.event_id == event.event_id
        assert env.event_type == "student.created"
        assert env.entity_type == "student"
        assert env.entity_id == 42
        assert env.tenant_id == 7
        assert env.campus_id == 7
        assert env.actor_id == 3
        assert env.event_version == 1
        assert env.correlation_id == "corr-1"
        assert env.causation_id == ""
        assert env.payload["student_number"] == "S42"
        assert env.payload["full_name"] == "Grace Hopper"

    def test_legacy_event_maps_tenant_and_entity(self):
        """Legacy notification events (tenant_id, no standard envelope)."""
        event = LegacyFeeDueCreatedEvent(
            student_id=9, academic_year_id=2026, due_ids=[1, 2], tenant_id=5
        )
        env = envelope_from_event(event)
        assert env.tenant_id == 5
        assert env.campus_id == 5
        assert env.entity_id == 9  # derived from student_id candidate
        assert env.event_type == "FeeDueCreatedEvent"  # class-name fallback
        assert env.event_version == 1
        assert env.payload["academic_year_id"] == 2026
        assert env.payload["due_ids"] == [1, 2]

    def test_event_version_class_attribute(self):
        class V2Event(DomainEvent):
            EVENT_TYPE = "test.v2"
            ENTITY_TYPE = "test"
            EVENT_VERSION = 2

            entity_id: int | None = None
            payload: dict = field(default_factory=dict)

        event = V2Event(entity_id=1)
        env = envelope_from_event(event)
        assert env.event_version == 2

    def test_explicit_event_version_wins(self):
        event = StudentCreatedEvent(
            student_id=1, student_number="S", full_name="A", event_version=3
        )
        env = envelope_from_event(event)
        assert env.event_version == 3

    def test_campus_id_falls_back_to_tenant(self):
        env = CanonicalEnvelope(event_id="x", event_type="t", tenant_id=11, campus_id=None)
        assert env.campus_id == 11


# ===========================================================================
# Deterministic serialization
# ===========================================================================


class TestDeterministicSerialization:
    def test_canonical_body_bytes_are_stable(self):
        # Same event id + payload → byte-identical canonical bodies.
        e1 = StudentCreatedEvent(
            student_id=1, student_number="S1", full_name="A", event_id="fixed-id-1"
        )
        e2 = StudentCreatedEvent(
            student_id=1, student_number="S1", full_name="A", event_id="fixed-id-1"
        )
        env1 = envelope_from_event(e1)
        env2 = envelope_from_event(e2)
        assert env1.canonical_body_bytes() == env2.canonical_body_bytes()

    def test_canonical_body_bytes_differ_on_payload_change(self):
        env1 = envelope_from_event(
            StudentCreatedEvent(student_id=1, student_number="S1", full_name="A")
        )
        env2 = envelope_from_event(
            StudentCreatedEvent(student_id=1, student_number="S1", full_name="B")
        )
        assert env1.canonical_body_bytes() != env2.canonical_body_bytes()

    def test_to_full_dict_is_json_serializable(self):
        event = StudentCreatedEvent(student_id=1, student_number="S1", full_name="A", school_id=3)
        data = to_canonical_dict(event)
        json.dumps(data)  # must not raise
        assert data["event_version"] == 1
        assert data["timestamp"]
        assert "integrity" in data


# ===========================================================================
# Integrity metadata
# ===========================================================================


class TestIntegrity:
    def test_integrity_metadata_present(self):
        env = envelope_from_event(
            StudentCreatedEvent(student_id=1, student_number="S1", full_name="A")
        )
        integrity = env.integrity()
        assert integrity["algorithm"] == "sha256"
        assert integrity["version"] == str(CANONICAL_VERSION)
        assert len(integrity["digest"]) == 64  # sha256 hex

    def test_integrity_matches_direct_hash(self):
        env = envelope_from_event(
            StudentCreatedEvent(student_id=1, student_number="S1", full_name="A")
        )
        expected = hashlib.sha256(env.canonical_body_bytes()).hexdigest()
        assert env.integrity()["digest"] == expected

    def test_compute_integrity_from_dict(self):
        data = to_canonical_dict(
            StudentCreatedEvent(student_id=1, student_number="S1", full_name="A")
        )
        integrity = compute_integrity(data)
        assert integrity["digest"] == data["integrity"]["digest"]


# ===========================================================================
# Validation
# ===========================================================================


class TestValidation:
    def test_valid_envelope_passes(self):
        data = to_canonical_dict(
            StudentCreatedEvent(student_id=1, student_number="S1", full_name="A", school_id=2)
        )
        assert validate_envelope(data) == []

    def test_missing_event_id_rejected(self):
        data = to_canonical_dict(
            StudentCreatedEvent(student_id=1, student_number="S1", full_name="A")
        )
        data.pop("event_id")
        errors = validate_envelope(data)
        assert any("event_id" in e for e in errors)

    def test_missing_event_type_rejected(self):
        data = to_canonical_dict(
            StudentCreatedEvent(student_id=1, student_number="S1", full_name="A")
        )
        data["event_type"] = ""
        errors = validate_envelope(data)
        assert any("event_type" in e for e in errors)

    def test_invalid_version_rejected(self):
        data = to_canonical_dict(
            StudentCreatedEvent(student_id=1, student_number="S1", full_name="A")
        )
        data["event_version"] = 0
        assert any("event_version" in e for e in validate_envelope(data))
        data["event_version"] = "abc"
        assert any("event_version" in e for e in validate_envelope(data))

    def test_invalid_timestamp_rejected(self):
        data = to_canonical_dict(
            StudentCreatedEvent(student_id=1, student_number="S1", full_name="A")
        )
        data["timestamp"] = "not-a-date"
        errors = validate_envelope(data)
        assert any("timestamp" in e for e in errors)

    def test_tampered_integrity_rejected(self):
        data = to_canonical_dict(
            StudentCreatedEvent(student_id=1, student_number="S1", full_name="A")
        )
        # Tamper with the payload after the digest was computed.
        data["payload"]["student_number"] = "TAMPERED"
        errors = validate_envelope(data)
        assert any("integrity" in e for e in errors)

    def test_round_trip_preserves_fields(self):
        data = to_canonical_dict(
            StudentCreatedEvent(
                student_id=1,
                student_number="S1",
                full_name="A",
                school_id=4,
                actor_user_id=9,
            )
        )
        rebuilt = from_canonical_dict(data)
        assert rebuilt.tenant_id == 4
        assert rebuilt.actor_id == 9
        assert rebuilt.event_id == data["event_id"]
        assert rebuilt.payload["student_number"] == "S1"


# ===========================================================================
# Backward compatibility
# ===========================================================================


class TestBackwardCompatibility:
    def test_serialize_event_unchanged(self):
        """The legacy serialize_event output keeps its exact key set."""
        event = StudentCreatedEvent(
            student_id=1,
            student_number="S1",
            full_name="A",
            school_id=7,
            actor_user_id=3,
            correlation_id="corr-1",
        )
        data = serialize_event(event)
        assert data["event_id"] == event.event_id
        assert data["event_type"] == "student.created"
        assert data["entity_type"] == "student"
        assert data["entity_id"] == 1
        assert data["school_id"] == 7
        assert data["actor_user_id"] == 3
        assert data["correlation_id"] == "corr-1"
        assert data["payload"]["student_number"] == "S1"

    def test_to_canonical_available_on_domain_event(self):
        event = StudentCreatedEvent(student_id=1, student_number="S1", full_name="A")
        assert callable(event.to_canonical)
        data = event.to_canonical()
        assert data["event_type"] == "student.created"
        assert "integrity" in data


# ===========================================================================
# Causation-chain propagation (in-process dispatcher)
# ===========================================================================


class TestCausationPropagation:
    async def test_nested_dispatch_inherits_causation_id(self):
        from app.domains.events.events import PaymentRecordedEvent

        dispatcher = DomainEventDispatcher()
        nested_seen: dict = {}

        async def first_handler(event, **kwargs):
            # Emit a different event type from inside the parent's handler.
            await dispatcher.dispatch(
                PaymentRecordedEvent(
                    student_id=2,
                    fee_due_id=3,
                    payment_id=4,
                    amount=100,
                    payment_method="cash",
                )
            )

        async def nested_handler(event, **kwargs):
            nested_seen["event"] = event

        dispatcher.register(StudentCreatedEvent, first_handler)
        dispatcher.register(PaymentRecordedEvent, nested_handler)

        parent = StudentCreatedEvent(student_id=1, student_number="S1", full_name="Parent")
        with event_context(correlation_id="corr-parent", actor_user_id=7, school_id=3):
            await dispatcher.dispatch(parent)

        child = nested_seen["event"]
        assert isinstance(child, PaymentRecordedEvent)
        # The nested event's causation is the parent's event id.
        assert child.causation_id == parent.event_id
        # And the correlation chain is preserved.
        assert child.correlation_id == "corr-parent"
        assert child.school_id == 3
        assert child.actor_user_id == 7

    async def test_source_stamped_on_dispatch(self):
        dispatcher = DomainEventDispatcher()
        seen: dict = {}

        async def handler(event, **kwargs):
            seen["event"] = event

        dispatcher.register(StudentCreatedEvent, handler)
        await dispatcher.dispatch(
            StudentCreatedEvent(student_id=1, student_number="S1", full_name="A")
        )
        assert seen["event"].source == "api"

    async def test_explicit_source_preserved(self):
        dispatcher = DomainEventDispatcher()
        seen: dict = {}

        async def handler(event, **kwargs):
            seen["event"] = event

        dispatcher.register(StudentCreatedEvent, handler)
        await dispatcher.dispatch(
            StudentCreatedEvent(student_id=1, student_number="S1", full_name="A", source="worker")
        )
        assert seen["event"].source == "worker"


# ===========================================================================
# Outbox persistence of canonical fields
# ===========================================================================


class TestOutboxCanonicalFields:
    async def test_publish_durable_persists_canonical_fields(self, db_session):
        event = StudentCreatedEvent(
            student_id=5,
            student_number="S5",
            full_name="Outbox Test",
            school_id=2,
            actor_user_id=8,
            correlation_id="corr-outbox",
            causation_id="parent-event-1",
            event_version=2,
            source="api",
        )
        row = await publish_durable(event, db_session)
        assert row is not None
        assert row.event_version == 2
        assert row.causation_id == "parent-event-1"
        assert row.source == "api"
        assert row.school_id == 2
        assert row.actor_user_id == 8
        assert row.correlation_id == "corr-outbox"
        assert row.payload["student_number"] == "S5"

    async def test_enqueue_defaults_canonical_fields(self, db_session):
        """Legacy callers that omit the new fields keep working with defaults."""
        repo = OutboxRepository(db_session)
        row = await repo.enqueue(
            event_id=uuid.uuid4().hex,
            event_type="LegacyEvent",
            entity_type="fee_due",
            entity_id=10,
            school_id=1,
            actor_user_id=2,
            correlation_id="corr",
            occurred_at=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
            payload={"student_id": 1},
            max_attempts=10,
            now=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
        )
        assert row.event_version == 1
        assert row.causation_id is None
        assert row.source is None

    async def test_rehydrate_restores_canonical_fields(self, db_session):
        """Outbox delivery rehydration restores the canonical fields."""
        from app.domains.events.outbox import outbox_dispatcher

        event = StudentCreatedEvent(
            student_id=7,
            student_number="S7",
            full_name="Rehydrate",
            school_id=3,
            actor_user_id=4,
            correlation_id="corr-re",
            causation_id="cause-xyz",
            event_version=4,
            source="worker",
        )
        row = await publish_durable(event, db_session)
        assert row is not None
        rehydrated = outbox_dispatcher._rehydrate(row)
        assert rehydrated.causation_id == "cause-xyz"
        assert rehydrated.event_version == 4
        assert rehydrated.source == "worker"
        assert rehydrated.school_id == 3
