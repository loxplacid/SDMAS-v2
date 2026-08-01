"""Tests for the SDMAS domain event foundation.

Coverage:
- Standard envelope model (event_id, event_type, entity_type, entity_id,
  school_id, actor_user_id, occurred_at, correlation_id, payload) + serialization
- Central event catalog
- DomainEventDispatcher: envelope stamping, correlation propagation,
  tenant/actor propagation, handler failure isolation, duplicate protection
- Initial handlers: student created audit, attendance threshold risk,
  admission approved lifecycle, workflow approved notification,
  rollover completed notification + audit
- Service emissions: student, admission, rollover, workflow
"""

from __future__ import annotations

import asyncio
import json
from datetime import datetime

import pytest

from app.domains.audit.constants import RISK
from app.domains.audit.repository import AuditLogRepository
from app.domains.events import event_bus, publish_event
from app.domains.events.base import (
    DomainEvent,
    new_correlation_id,
    serialize_event,
)
from app.domains.events.catalog import (
    EVENT_CATALOG,
    all_event_definitions,
    get_event_definition,
    get_definition_for_event,
)
from app.domains.events.context import event_context, get_actor_user_id, get_correlation_id, get_school_id
from app.domains.events.dispatcher import DomainEventDispatcher
from app.domains.events.events import (
    AcademicYearRolloverCompletedEvent,
    AdmissionApprovedEvent,
    AttendanceThresholdBreachedEvent,
    StudentCreatedEvent,
    WorkflowApprovedEvent,
)
from app.domains.events.handlers import (
    handle_admission_approved_lifecycle,
    handle_attendance_threshold_risk,
    handle_rollover_completed_notification,
    handle_student_created_audit,
    handle_workflow_approved_notification,
    register_domain_event_handlers,
)
from app.domains.notifications.events import EventDispatcher

# Import all domain models so ``Base.metadata.create_all`` (in the
# ``db_session`` fixture) resolves every cross-module foreign key — the
# same pattern conftest.py uses for its module-level model imports.
from app.domains.academic import models as _academic_models  # noqa: F401
from app.domains.admission import models as _admission_models  # noqa: F401
from app.domains.attendance import models as _attendance_models  # noqa: F401
from app.domains.student import models as _student_models  # noqa: F401
from app.domains.workflow import models as _workflow_models  # noqa: F401


# ---------------------------------------------------------------------------
# Local fixtures (self-contained; do not depend on other test modules)
# ---------------------------------------------------------------------------


@pytest.fixture
async def seeded_rollover(db_session):
    """Seed data for rollover testing (same shape as test_reports fixture)."""
    import datetime
    from datetime import timezone

    from sqlalchemy.ext.asyncio import AsyncSession

    from app.domains.academic.models import AcademicYear, Class, Section, Enrollment
    from app.domains.academic.repository import (
        AcademicYearRepository,
        ClassRepository,
        SectionRepository,
        EnrollmentRepository,
    )
    from app.domains.student.models import Student
    from app.domains.student.repository import StudentRepository
    from app.domains.reports.rollover_service import RolloverService

    student_repo = StudentRepository(db_session)
    year_repo = AcademicYearRepository(db_session)
    class_repo = ClassRepository(db_session)
    section_repo = SectionRepository(db_session)
    enrollment_repo = EnrollmentRepository(db_session)
    rollover_svc = RolloverService(db_session)

    year = await year_repo.create(
        AcademicYear(
            name="Source Year 2025-2026",
            start_date=datetime.date(2025, 9, 1),
            end_date=datetime.date(2026, 8, 31),
            status="active",
        )
    )
    cls = await class_repo.create(
        Class(name="Grade 10", academic_year_id=year.id, status="active")
    )
    section = await section_repo.create(
        Section(name="Section A", class_id=cls.id, status="active")
    )
    s1 = await student_repo.create(
        Student(first_name="Alice", last_name="Smith", student_number="EVT-RL001", status="active")
    )
    s2 = await student_repo.create(
        Student(first_name="Bob", last_name="Jones", student_number="EVT-RL002", status="active")
    )
    now = datetime.datetime.now(timezone.utc)
    for s in [s1, s2]:
        await enrollment_repo.create(
            Enrollment(
                student_id=s.id, academic_year_id=year.id,
                class_id=cls.id, section_id=section.id,
                status="active", enrolled_at=now,
                created_at=now, updated_at=now,
            )
        )

    return {
        "rollover_svc": rollover_svc,
        "year_repo": year_repo,
        "class_repo": class_repo,
        "section_repo": section_repo,
        "enrollment_repo": enrollment_repo,
        "source_year": year,
        "cls": cls,
        "section": section,
        "s1": s1,
        "s2": s2,
    }


@pytest.fixture
async def seeded_workflow(db_session):
    """A minimal 3-step workflow (submitted -> approved | rejected)."""
    import datetime

    from app.domains.workflow.models import Workflow, WorkflowStep, WorkflowTransition
    from app.domains.workflow.repository import (
        ApprovalHistoryRepository,
        WorkflowActionRepository,
        WorkflowInstanceRepository,
        WorkflowRepository,
        WorkflowStepRepository,
        WorkflowTransitionRepository,
    )
    from app.domains.workflow.service import WorkflowExecutionService

    now = datetime.datetime.now(datetime.timezone.utc)
    wf = Workflow(
        name="EVT Workflow",
        code="EVT_WF",
        description="Test",
        entity_type="test_entity",
        status="active",
        created_at=now,
        updated_at=now,
    )
    db_session.add(wf)
    await db_session.flush()

    step1 = WorkflowStep(workflow_id=wf.id, name="submitted", label="Submitted",
                         step_order=1, is_initial=True, is_final=False)
    step2 = WorkflowStep(workflow_id=wf.id, name="approved", label="Approved",
                         step_order=2, is_initial=False, is_final=True)
    db_session.add_all([step1, step2])
    await db_session.flush()

    db_session.add(WorkflowTransition(workflow_id=wf.id, from_step_id=step1.id,
                                      to_step_id=step2.id, label="Approve"))
    await db_session.flush()

    exec_svc = WorkflowExecutionService(
        instance_repo=WorkflowInstanceRepository(db_session),
        workflow_repo=WorkflowRepository(db_session),
        step_repo=WorkflowStepRepository(db_session),
        transition_repo=WorkflowTransitionRepository(db_session),
        action_repo=WorkflowActionRepository(db_session),
        history_repo=ApprovalHistoryRepository(db_session),
    )
    return {"exec": exec_svc, "workflow_id": wf.id}


# ===========================================================================
# Envelope model
# ===========================================================================


class TestEnvelope:
    def test_default_envelope_fields(self):
        event = StudentCreatedEvent(student_id=1, student_number="S1", full_name="Ada Lovelace")
        assert event.event_id
        assert event.event_type == "student.created"
        assert event.entity_type == "student"
        assert event.entity_id == 1  # derived from student_id
        assert event.school_id is None
        assert event.actor_user_id is None
        assert isinstance(event.occurred_at, datetime)
        assert event.correlation_id == ""  # stamped at dispatch time

    def test_event_ids_unique(self):
        e1 = StudentCreatedEvent(student_id=1, student_number="S1", full_name="A")
        e2 = StudentCreatedEvent(student_id=1, student_number="S1", full_name="A")
        assert e1.event_id != e2.event_id

    def test_serialize_event_json_compatible(self):
        event = StudentCreatedEvent(
            student_id=42,
            student_number="S42",
            full_name="Grace Hopper",
            email="grace@example.com",
            school_id=7,
            actor_user_id=3,
            correlation_id="corr-1",
        )
        data = serialize_event(event)
        # Fully JSON-serializable
        json.dumps(data)
        assert data["event_id"] == event.event_id
        assert data["event_type"] == "student.created"
        assert data["entity_type"] == "student"
        assert data["entity_id"] == 42
        assert data["school_id"] == 7
        assert data["actor_user_id"] == 3
        assert data["correlation_id"] == "corr-1"
        assert data["payload"]["student_number"] == "S42"

    def test_explicit_event_id_preserved(self):
        event = StudentCreatedEvent(
            student_id=1, student_number="S1", full_name="A", event_id="fixed-id"
        )
        assert event.event_id == "fixed-id"


# ===========================================================================
# Catalog
# ===========================================================================


class TestCatalog:
    def test_catalog_contains_required_events(self):
        required = {
            "student.created",
            "student.updated",
            "student.status_changed",
            "attendance.threshold_breached",
            "fee.due_created",
            "payment.recorded",
            "payment.overdue",
            "admission.submitted",
            "admission.approved",
            "admission.rejected",
            "leave.submitted",
            "leave.approved",
            "leave.rejected",
            "document.uploaded",
            "document.verified",
            "workflow.submitted",
            "workflow.approved",
            "workflow.rejected",
            "academic_year.rollover_started",
            "academic_year.rollover_completed",
            "academic_year.rollover_failed",
        }
        for event_type in required:
            assert get_event_definition(event_type) is not None, event_type

    def test_catalog_definitions_have_metadata(self):
        for event_type, definition in EVENT_CATALOG.items():
            assert definition.event_type == event_type
            assert definition.entity_type
            assert definition.description
            assert definition.event_class is not None

    def test_catalog_lookup_by_event_instance(self):
        event = AttendanceThresholdBreachedEvent(student_id=1, attendance_percentage=60.0)
        definition = get_definition_for_event(event)
        assert definition is not None
        assert definition.event_type == "attendance.threshold_breached"

    def test_all_definitions_sorted(self):
        definitions = all_event_definitions()
        types = [d.event_type for d in definitions]
        assert types == sorted(types)


# ===========================================================================
# DomainEventDispatcher
# ===========================================================================


class TestDomainEventDispatcher:
    async def test_dispatch_stamps_envelope(self):
        dispatcher = DomainEventDispatcher()
        captured = {}

        async def handler(event, **kwargs):
            captured["event"] = event

        dispatcher.register(StudentCreatedEvent, handler)
        await dispatcher.dispatch(
            StudentCreatedEvent(student_id=1, student_number="S1", full_name="A")
        )
        event = captured["event"]
        assert event.event_id
        assert event.occurred_at is not None
        assert event.correlation_id

    async def test_dispatch_propagates_context_to_event(self):
        dispatcher = DomainEventDispatcher()
        captured = {}

        async def handler(event, **kwargs):
            captured["event"] = event

        dispatcher.register(StudentCreatedEvent, handler)
        with event_context(correlation_id="corr-xyz", actor_user_id=9, school_id=4):
            await dispatcher.dispatch(
                StudentCreatedEvent(student_id=1, student_number="S1", full_name="A")
            )
        event = captured["event"]
        assert event.correlation_id == "corr-xyz"
        assert event.actor_user_id == 9
        assert event.school_id == 4

    async def test_dispatch_explicit_context_overrides(self):
        dispatcher = DomainEventDispatcher()
        captured = {}

        async def handler(event, **kwargs):
            captured["event"] = event

        dispatcher.register(StudentCreatedEvent, handler)
        await dispatcher.dispatch(
            StudentCreatedEvent(student_id=1, student_number="S1", full_name="A"),
            correlation_id="override-corr",
            actor_user_id=5,
            school_id=2,
        )
        event = captured["event"]
        assert event.correlation_id == "override-corr"
        assert event.actor_user_id == 5
        assert event.school_id == 2

    async def test_nested_dispatch_inherits_correlation(self):
        """A handler that emits a new event inherits the correlation id."""
        dispatcher = DomainEventDispatcher()
        nested_seen = {}

        async def first_handler(event, **kwargs):
            # Emit a second event from within the handler
            await dispatcher.dispatch(
                AdmissionApprovedEvent(application_id=99, applicant_name="Nested")
            )

        async def nested_handler(event, **kwargs):
            nested_seen["event"] = event

        dispatcher.register(StudentCreatedEvent, first_handler)
        dispatcher.register(AdmissionApprovedEvent, nested_handler)

        with event_context(correlation_id="corr-parent", actor_user_id=7, school_id=3):
            await dispatcher.dispatch(
                StudentCreatedEvent(student_id=1, student_number="S1", full_name="A")
            )
        assert nested_seen["event"].correlation_id == "corr-parent"
        assert nested_seen["event"].actor_user_id == 7
        assert nested_seen["event"].school_id == 3

    async def test_handler_failure_does_not_block_others(self):
        dispatcher = DomainEventDispatcher()
        calls = []

        async def failing(event, **kwargs):
            raise RuntimeError("boom")

        async def succeeding(event, **kwargs):
            calls.append(event)

        dispatcher.register(StudentCreatedEvent, failing)
        dispatcher.register(StudentCreatedEvent, succeeding)

        await dispatcher.dispatch(
            StudentCreatedEvent(student_id=1, student_number="S1", full_name="A")
        )
        assert len(calls) == 1, "Second handler should still run after first fails"

    async def test_no_duplicate_side_effects(self):
        """Dispatching the same event twice runs handlers once."""
        dispatcher = DomainEventDispatcher()
        calls = []

        async def handler(event, **kwargs):
            calls.append(event)

        dispatcher.register(StudentCreatedEvent, handler)
        event = StudentCreatedEvent(student_id=1, student_number="S1", full_name="A")
        await dispatcher.dispatch(event, session=None)
        await dispatcher.dispatch(event, session=None)
        assert len(calls) == 1

    async def test_distinct_events_both_processed(self):
        dispatcher = DomainEventDispatcher()
        calls = []

        async def handler(event, **kwargs):
            calls.append(event)

        dispatcher.register(StudentCreatedEvent, handler)
        await dispatcher.dispatch(
            StudentCreatedEvent(student_id=1, student_number="S1", full_name="A")
        )
        await dispatcher.dispatch(
            StudentCreatedEvent(student_id=2, student_number="S2", full_name="B")
        )
        assert len(calls) == 2

    async def test_session_passed_to_handler(self):
        dispatcher = DomainEventDispatcher()
        received = {}
        fake_session = object()

        async def handler(event, **kwargs):
            received["session"] = kwargs.get("session")

        dispatcher.register(StudentCreatedEvent, handler)
        await dispatcher.dispatch(
            StudentCreatedEvent(student_id=1, student_number="S1", full_name="A"),
            session=fake_session,  # type: ignore[arg-type]
        )
        assert received["session"] is fake_session

    async def test_clear_and_reset(self):
        dispatcher = DomainEventDispatcher()

        async def handler(event, **kwargs):
            pass

        dispatcher.register(StudentCreatedEvent, handler)
        assert dispatcher.handler_count == 1
        dispatcher.clear()
        assert dispatcher.handler_count == 0


# ===========================================================================
# Context
# ===========================================================================


class TestEventContext:
    def test_context_setters(self):
        with event_context(correlation_id="c1", actor_user_id=1, school_id=2):
            assert get_correlation_id() == "c1"
            assert get_actor_user_id() == 1
            assert get_school_id() == 2
        # Context restored after block
        assert get_correlation_id() is None

    def test_context_none_leaves_unchanged(self):
        with event_context(correlation_id="c1"):
            with event_context(actor_user_id=5):
                assert get_correlation_id() == "c1"
                assert get_actor_user_id() == 5


# ===========================================================================
# Initial handlers
# ===========================================================================


class TestHandlers:
    async def test_student_created_audit_handler(self, db_session):
        event = StudentCreatedEvent(
            student_id=10,
            student_number="S10",
            full_name="Test Student",
            actor_user_id=3,
            school_id=1,
        )
        await handle_student_created_audit(event, session=db_session)
        repo = AuditLogRepository(db_session)
        items, total = await repo.list(resource_type="student", resource_id="10")
        assert total >= 1
        assert items[-1].action == "CREATE"
        assert items[-1].user_id == 3

    async def test_student_created_audit_handler_is_idempotent(self, db_session):
        """No duplicate side effect: when a CREATE entry already exists for
        the student (the service writes it synchronously), the handler must
        not write a second one."""
        from app.domains.audit.models import AuditLog
        from app.domains.audit.constants import STUDENT

        db_session.add(
            AuditLog(
                action="CREATE",
                resource_type=STUDENT,
                resource_id="10",
                user_id=3,
            )
        )
        await db_session.flush()

        repo = AuditLogRepository(db_session)
        _, before = await repo.list(resource_type="student", resource_id="10")

        event = StudentCreatedEvent(
            student_id=10,
            student_number="S10",
            full_name="Test Student",
            actor_user_id=3,
        )
        await handle_student_created_audit(event, session=db_session)

        _, after = await repo.list(resource_type="student", resource_id="10")
        assert after == before == 1

    async def test_attendance_threshold_risk_handler(self, db_session):
        event = AttendanceThresholdBreachedEvent(
            student_id=11,
            attendance_percentage=55.0,
            threshold=75.0,
            total_absences=9,
        )
        await handle_attendance_threshold_risk(event, session=db_session)
        repo = AuditLogRepository(db_session)
        items, total = await repo.list(resource_type="attendance", resource_id="11")
        assert total >= 1
        assert items[-1].action == RISK
        assert "attendance_percentage" in (items[-1].details or "")

    async def test_admission_approved_lifecycle_handler(self, db_session):
        event = AdmissionApprovedEvent(
            application_id=12,
            applicant_name="Applicant",
            actor_user_id=4,
            school_id=1,
        )
        await handle_admission_approved_lifecycle(event, session=db_session)
        repo = AuditLogRepository(db_session)
        items, total = await repo.list(resource_type="admission", resource_id="12")
        assert total >= 1
        assert items[-1].action == "APPROVE"

    async def test_workflow_approved_notification_handler(self, db_session):
        """WorkflowApproved handler notifies the submitter (created_by),
        falling back to the actor, and produces a notification event."""
        from app.domains.notifications.events import ImportantAdminEvent

        received = {}

        async def spy_handler(event: ImportantAdminEvent, **kwargs):
            received["event"] = event

        dispatcher = EventDispatcher()
        dispatcher.register(ImportantAdminEvent, spy_handler)
        import app.domains.events.handlers as handlers_module

        original = handlers_module.notification_dispatcher
        handlers_module.notification_dispatcher = dispatcher
        try:
            event = WorkflowApprovedEvent(
                instance_id=1,
                workflow_id=2,
                entity_type="test",
                entity_id=100,
                step_name="approved",
                actor_id=5,  # the approver
                created_by=7,  # the submitter
            )
            await handle_workflow_approved_notification(event, session=db_session)
        finally:
            handlers_module.notification_dispatcher = original
        assert received["event"] is not None
        assert "workflow" in received["event"].event_type
        # The submitter is notified, not the approver
        assert received["event"].target_user_id == 7

    async def test_workflow_approved_notification_falls_back_to_actor(self, db_session):
        """When no submitter is recorded, the acting user is notified."""
        from app.domains.notifications.events import ImportantAdminEvent

        received = {}

        async def spy_handler(event: ImportantAdminEvent, **kwargs):
            received["event"] = event

        dispatcher = EventDispatcher()
        dispatcher.register(ImportantAdminEvent, spy_handler)
        import app.domains.events.handlers as handlers_module

        original = handlers_module.notification_dispatcher
        handlers_module.notification_dispatcher = dispatcher
        try:
            event = WorkflowApprovedEvent(
                instance_id=1,
                workflow_id=2,
                entity_type="test",
                entity_id=100,
                step_name="approved",
                actor_id=5,
                created_by=None,
            )
            await handle_workflow_approved_notification(event, session=db_session)
        finally:
            handlers_module.notification_dispatcher = original
        assert received["event"].target_user_id == 5

    async def test_rollover_completed_handler_audit(self, db_session):
        event = AcademicYearRolloverCompletedEvent(
            previous_year_id=2024,
            new_year_id=2025,
            new_year_name="2025-2026",
            students_rolled=50,
            classes_migrated=4,
            actor_user_id=6,
            school_id=1,
        )
        await handle_rollover_completed_notification(event, session=db_session)
        repo = AuditLogRepository(db_session)
        items, total = await repo.list(resource_type="academic", resource_id="2025")
        assert total >= 1


# ===========================================================================
# Handler registration
# ===========================================================================


class TestRegistration:
    def test_register_domain_event_handlers(self):
        dispatcher = DomainEventDispatcher()
        register_domain_event_handlers(dispatcher)
        assert dispatcher.handler_count >= 5
        # Handlers registered for the initial set
        assert dispatcher._handlers.get(StudentCreatedEvent)
        assert dispatcher._handlers.get(AttendanceThresholdBreachedEvent)
        assert dispatcher._handlers.get(AdmissionApprovedEvent)
        assert dispatcher._handlers.get(WorkflowApprovedEvent)
        assert dispatcher._handlers.get(AcademicYearRolloverCompletedEvent)


# ===========================================================================
# Service emissions
# ===========================================================================


class TestServiceEmissions:
    """Verify services publish standard events with correct envelope data."""

    @pytest.fixture
    def captured(self):
        """Register capture handlers on the global event bus and clean up."""
        captured: list = []

        async def capture(event, **kwargs):
            captured.append(event)

        event_bus.register(StudentCreatedEvent, capture)
        event_bus.register(AdmissionApprovedEvent, capture)
        event_bus.register(AcademicYearRolloverCompletedEvent, capture)
        event_bus.register(WorkflowApprovedEvent, capture)
        event_bus.register(AttendanceThresholdBreachedEvent, capture)
        event_bus.reset_dedup()
        try:
            yield captured
        finally:
            for event_type in (
                StudentCreatedEvent,
                AdmissionApprovedEvent,
                AcademicYearRolloverCompletedEvent,
                WorkflowApprovedEvent,
                AttendanceThresholdBreachedEvent,
            ):
                event_bus.unregister(event_type, capture)

    async def test_student_service_emits_created(self, db_session, captured):
        from app.domains.student.repository import StudentRepository
        from app.domains.student.schemas import StudentCreate
        from app.domains.student.service import StudentService

        service = StudentService(StudentRepository(db_session))
        student = await service.create_student(
            StudentCreate(
                first_name="Ada",
                last_name="Lovelace",
                student_number="EVT-001",
            )
        )
        assert any(e.student_id == student.id for e in captured)
        event = [e for e in captured if isinstance(e, StudentCreatedEvent)][0]
        assert event.entity_id == student.id
        assert event.entity_type == "student"

    async def test_admission_service_emits_approved(self, db_session, captured):
        from app.domains.admission.repository import AdmissionApplicationRepository
        from app.domains.admission.service import AdmissionApplicationService

        service = AdmissionApplicationService(AdmissionApplicationRepository(db_session))
        from app.domains.admission.schemas import AdmissionApplicationCreate

        app = await service.create(
            AdmissionApplicationCreate(
                campus_id=None,
                academic_year_id=None,
                program_id=None,
                branch_id=None,
                semester_id=None,
                applicant_name="John Doe",
                email="john@example.com",
                phone="1234567890",
                source="website",
            )
        )
        # Walk the full flow (the service forbids skipping states)
        from app.domains.admission.models import (
            ADMISSION_STATUS_ENROLLED,
            ADMISSION_STATUS_FLOW,
        )

        enrolled_idx = ADMISSION_STATUS_FLOW.index(ADMISSION_STATUS_ENROLLED)
        for status in ADMISSION_STATUS_FLOW[1 : enrolled_idx + 1]:
            await service.transition_status(app.id, status)
        assert any(isinstance(e, AdmissionApprovedEvent) for e in captured)
        event = [e for e in captured if isinstance(e, AdmissionApprovedEvent)][0]
        assert event.application_id == app.id

    async def test_attendance_service_emits_threshold_breached(
        self, db_session, captured
    ):
        """record_daily_attendance publishes AttendanceThresholdBreachedEvent
        when a student's attendance percentage drops below the threshold."""
        import datetime
        from datetime import timezone

        from app.domains.academic.models import (
            AcademicYear,
            Class,
            Section,
            Enrollment,
        )
        from app.domains.academic.repository import (
            AcademicYearRepository,
            ClassRepository,
            SectionRepository,
            EnrollmentRepository,
        )
        from app.domains.attendance.repository import AttendanceRepository
        from app.domains.attendance.schemas import (
            DailyAttendanceCreate,
            DailyAttendanceItem,
        )
        from app.domains.attendance.service import AttendanceService
        from app.domains.events.events import AttendanceThresholdBreachedEvent
        from app.domains.student.models import Student
        from app.domains.student.repository import StudentRepository

        student_repo = StudentRepository(db_session)
        year_repo = AcademicYearRepository(db_session)
        class_repo = ClassRepository(db_session)
        section_repo = SectionRepository(db_session)
        enrollment_repo = EnrollmentRepository(db_session)
        att_repo = AttendanceRepository(db_session)

        service = AttendanceService(
            att_repo, student_repo, year_repo, class_repo, section_repo
        )

        year = await year_repo.create(
            AcademicYear(
                name="EVT-ATT Year",
                start_date=datetime.date(2026, 1, 1),
                end_date=datetime.date(2026, 12, 31),
                status="active",
            )
        )
        cls = await class_repo.create(
            Class(name="Grade 10", academic_year_id=year.id, status="active")
        )
        section = await section_repo.create(
            Section(name="Section A", class_id=cls.id, status="active")
        )
        s1 = await student_repo.create(
            Student(first_name="Alice", last_name="Smith", student_number="EVT-ATT1", status="active")
        )
        s2 = await student_repo.create(
            Student(first_name="Bob", last_name="Jones", student_number="EVT-ATT2", status="active")
        )
        now = datetime.datetime.now(timezone.utc)
        for s in [s1, s2]:
            await enrollment_repo.create(
                Enrollment(
                    student_id=s.id, academic_year_id=year.id,
                    class_id=cls.id, section_id=section.id,
                    status="active", enrolled_at=now,
                    created_at=now, updated_at=now,
                )
            )

        # Record all-absent days until Alice's percentage drops below 75%
        for day in range(1, 6):
            date_str = f"2026-03-{day:02d}"
            await service.record_daily_attendance(
                DailyAttendanceCreate(
                    section_id=section.id,
                    attendance_date=date_str,
                    records=[
                        DailyAttendanceItem(student_id=s1.id, status="absent"),
                        DailyAttendanceItem(student_id=s2.id, status="present"),
                    ],
                )
            )

        assert any(
            isinstance(e, AttendanceThresholdBreachedEvent) for e in captured
        )
        event = [
            e for e in captured if isinstance(e, AttendanceThresholdBreachedEvent)
        ][0]
        assert event.student_id == s1.id
        assert event.section_id == section.id
        assert event.attendance_percentage < 75.0

    async def test_rollover_service_emits_completed(
        self, db_session, captured, seeded_rollover
    ):
        svc = seeded_rollover["rollover_svc"]
        source_year = seeded_rollover["source_year"]
        result = await svc.execute_rollover(
            from_year_id=source_year.id,
            to_year_name="EVT-2027",
            to_start_date="2027-09-01",
            to_end_date="2028-08-31",
        )
        assert result["success"] is True
        assert any(isinstance(e, AcademicYearRolloverCompletedEvent) for e in captured)
        event = [
            e for e in captured if isinstance(e, AcademicYearRolloverCompletedEvent)
        ][0]
        assert event.new_year_id == result["academic_year_id"]
        assert event.students_rolled == result["enrollments_created"]

    async def test_workflow_service_emits_approved(
        self, db_session, captured, seeded_workflow
    ):
        svc = seeded_workflow["exec"]
        instance = await svc.start_instance(
            workflow_id=seeded_workflow["workflow_id"],
            entity_type="test_entity",
            entity_id=5000,
            created_by=1,
        )
        await svc.perform_action(
            instance_id=instance.id, action="approve", actor_id=2
        )
        assert any(isinstance(e, WorkflowApprovedEvent) for e in captured)
        event = [e for e in captured if isinstance(e, WorkflowApprovedEvent)][0]
        assert event.instance_id == instance.id
        assert event.actor_id == 2
        assert event.created_by == 1  # the submitter is carried on the event
        assert event.step_name == "approved"


# ===========================================================================
# publish_event helper
# ===========================================================================


class TestPublishEvent:
    async def test_publish_event_routes_to_event_bus(self):
        calls = []

        async def handler(event, **kwargs):
            calls.append(event)

        event_bus.register(StudentCreatedEvent, handler)
        try:
            await publish_event(
                StudentCreatedEvent(student_id=1, student_number="S1", full_name="A"),
                actor_user_id=2,
                school_id=3,
            )
        finally:
            event_bus.unregister(StudentCreatedEvent, handler)
        assert len(calls) == 1
        assert calls[0].actor_user_id == 2
        assert calls[0].school_id == 3

    async def test_event_bus_is_domain_event_dispatcher(self):
        from app.domains.events.dispatcher import DomainEventDispatcher

        assert isinstance(event_bus, DomainEventDispatcher)


# ===========================================================================
# Request-path context propagation (tenant middleware)
# ===========================================================================


class TestRequestContextPropagation:
    async def test_middleware_stamps_actor_tenant_and_correlation(self):
        """A request through the tenant middleware must stamp the event
        context so services publishing events during the request carry the
        correct actor, school, and correlation id."""
        from fastapi import FastAPI
        from httpx import ASGITransport, AsyncClient

        from app.domains.auth.security import create_access_token
        from app.domains.events.context import (
            get_actor_user_id,
            get_correlation_id,
            get_school_id,
        )
        from app.multi_tenant.middleware import TenantContextMiddleware

        app = FastAPI()
        app.add_middleware(TenantContextMiddleware)

        @app.get("/_echo_context")
        async def echo_context():
            return {
                "school_id": get_school_id(),
                "actor_user_id": get_actor_user_id(),
                "correlation_id": get_correlation_id(),
            }

        token = create_access_token(
            data={"sub": "42", "username": "admin"},
            campus_id=7,
        )
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get(
                "/_echo_context",
                headers={
                    "Authorization": f"Bearer {token}",
                    "X-Correlation-ID": "corr-abc-123",
                },
            )
        assert response.status_code == 200
        body = response.json()
        assert body["school_id"] == 7
        assert body["actor_user_id"] == 42
        assert body["correlation_id"] == "corr-abc-123"

    async def test_middleware_unauthenticated_leaves_context_blank(self):
        """Unauthenticated requests must not set actor/tenant context."""
        from fastapi import FastAPI
        from httpx import ASGITransport, AsyncClient

        from app.domains.events.context import (
            get_actor_user_id,
            get_school_id,
        )
        from app.multi_tenant.middleware import TenantContextMiddleware

        app = FastAPI()
        app.add_middleware(TenantContextMiddleware)

        @app.get("/_echo_context")
        async def echo_context():
            return {
                "school_id": get_school_id(),
                "actor_user_id": get_actor_user_id(),
            }

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as ac:
            response = await ac.get("/_echo_context")
        assert response.status_code == 200
        body = response.json()
        assert body["school_id"] is None
        assert body["actor_user_id"] is None
