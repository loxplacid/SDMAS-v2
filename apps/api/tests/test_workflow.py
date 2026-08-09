"""Tests for the workflow and approval engine.

Covers:
- Workflow definition CRUD (admin)
- Starting workflow instances
- Approval transitions (approve, reject, return, submit)
- Authorization role enforcement
- Duplicate instance prevention
- Audit integration
- History recording
- Invalid state transitions
"""

from __future__ import annotations

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.events import event_bus
from app.domains.events.events import WorkflowCancelledEvent
from app.multi_tenant.models import platform_context
from app.domains.workflow.models import (
    ApprovalHistory,
    Workflow,
    WorkflowInstance,
    WorkflowStep,
    WorkflowTransition,
)
from app.domains.workflow.repository import (
    ApprovalHistoryRepository,
    WorkflowActionRepository,
    WorkflowInstanceRepository,
    WorkflowRepository,
    WorkflowStepRepository,
    WorkflowTransitionRepository,
)
from app.domains.workflow.schemas import AvailableTransition
from app.domains.workflow.service import (
    WorkflowAdminService,
    WorkflowExecutionService,
)


# ---------------------------------------------------------------------------
# Fixtures: build a test workflow with steps + transitions
# ---------------------------------------------------------------------------


async def _create_minimal_workflow(
    session: AsyncSession,
    *,
    approve_role: str | None = None,
    step_role: str | None = None,
) -> dict:
    """Create a 3-step workflow (submitted → approved | rejected) and return IDs.

    ``approve_role`` sets the Approve transition's ``required_role``;
    ``step_role`` sets the submitted step's ``assigned_role``.
    """
    import datetime
    now = datetime.datetime.now(datetime.timezone.utc)

    wf = Workflow(
        name="Test Workflow",
        code="TEST_WF",
        description="Test",
        entity_type="test_entity",
        status="active",
        created_at=now,
        updated_at=now,
    )
    session.add(wf)
    await session.flush()  # assign wf.id

    step1 = WorkflowStep(workflow_id=wf.id, name="submitted", label="Submitted",
                         step_order=1, is_initial=True, is_final=False,
                         assigned_role=step_role)
    step2 = WorkflowStep(workflow_id=wf.id, name="approved", label="Approved",
                         step_order=2, is_initial=False, is_final=True)
    step3 = WorkflowStep(workflow_id=wf.id, name="rejected", label="Rejected",
                         step_order=3, is_initial=False, is_final=True)
    session.add_all([step1, step2, step3])
    await session.flush()  # assign step ids

    session.add(WorkflowTransition(workflow_id=wf.id, from_step_id=step1.id,
                                   to_step_id=step2.id, label="Approve",
                                   required_role=approve_role))
    session.add(WorkflowTransition(workflow_id=wf.id, from_step_id=step1.id,
                                   to_step_id=step3.id, label="Reject"))
    await session.flush()  # assign transition ids

    return {
        "workflow_id": wf.id,
        "step_submitted": step1.id,
        "step_approved": step2.id,
        "step_rejected": step3.id,
    }


def _exec_service(session: AsyncSession) -> WorkflowExecutionService:
    return WorkflowExecutionService(
        instance_repo=WorkflowInstanceRepository(session, platform_context()),
        workflow_repo=WorkflowRepository(session, platform_context()),
        step_repo=WorkflowStepRepository(session, platform_context()),
        transition_repo=WorkflowTransitionRepository(session, platform_context()),
        action_repo=WorkflowActionRepository(session, platform_context()),
        history_repo=ApprovalHistoryRepository(session, platform_context()),
    )


def _admin_service(session: AsyncSession) -> WorkflowAdminService:
    return WorkflowAdminService(
        workflow_repo=WorkflowRepository(session, platform_context()),
        step_repo=WorkflowStepRepository(session, platform_context()),
        transition_repo=WorkflowTransitionRepository(session, platform_context()),
        action_repo=WorkflowActionRepository(session, platform_context()),
    )


# ===========================================================================
# Workflow Definition Tests
# ===========================================================================


class TestWorkflowDefinition:
    async def test_create_workflow(self, db_session):
        svc = _admin_service(db_session)
        wf = await svc.create_workflow(
            name="Approval WF", code="APPROVAL_TEST",
            entity_type="purchase_order",
            description="Test workflow",
        )
        assert wf.id is not None
        assert wf.code == "APPROVAL_TEST"
        assert wf.status == "active"

    async def test_create_duplicate_workflow_raises(self, db_session):
        svc = _admin_service(db_session)
        await svc.create_workflow(name="WF", code="DUP", entity_type="test")
        from app.core.exceptions import ConflictError

        with pytest.raises(ConflictError, match="already exists"):
            await svc.create_workflow(name="WF2", code="DUP", entity_type="test")

    async def test_get_workflow_by_code(self, db_session):
        svc = _admin_service(db_session)
        await svc.create_workflow(name="Get Test", code="GET_TEST", entity_type="test")
        wf = await svc.get_workflow_by_code("GET_TEST")
        assert wf.name == "Get Test"

    async def test_get_workflow_by_code_not_found(self, db_session):
        svc = _admin_service(db_session)
        from app.core.exceptions import NotFoundError

        with pytest.raises(NotFoundError):
            await svc.get_workflow_by_code("NONEXISTENT")

    async def test_list_workflows(self, db_session):
        svc = _admin_service(db_session)
        for i in range(3):
            await svc.create_workflow(
                name=f"WF {i}", code=f"LIST_{i}", entity_type="test"
            )
        items, total = await svc.list_workflows()
        assert total >= 3

    async def test_list_workflows_filter_by_status(self, db_session):
        svc = _admin_service(db_session)
        wf = await svc.create_workflow(name="Active", code="ACTIVE", entity_type="test")
        await svc.update_workflow(wf.id, status="inactive")

        items, total = await svc.list_workflows(status="inactive")
        assert total >= 1

    async def test_delete_workflow(self, db_session):
        svc = _admin_service(db_session)
        wf = await svc.create_workflow(name="Delete", code="DELETE", entity_type="test")
        await svc.delete_workflow(wf.id)

        from app.core.exceptions import NotFoundError
        with pytest.raises(NotFoundError):
            await svc.get_workflow(wf.id)


# ===========================================================================
# Workflow Step & Transition Tests
# ===========================================================================


class TestWorkflowSteps:
    async def test_create_step(self, db_session):
        ids = await _create_minimal_workflow(db_session)
        svc = _admin_service(db_session)
        from app.domains.workflow.schemas import WorkflowStepCreate

        step = await svc.create_step(WorkflowStepCreate(
            workflow_id=ids["workflow_id"],
            name="extra_step",
            step_order=4,
            is_final=True,
            assigned_role="admin",
        ))
        assert step.name == "extra_step"
        assert step.assigned_role == "admin"

    async def test_create_step_missing_workflow(self, db_session):
        svc = _admin_service(db_session)
        from app.domains.workflow.schemas import WorkflowStepCreate
        from app.core.exceptions import NotFoundError

        with pytest.raises(NotFoundError):
            await svc.create_step(WorkflowStepCreate(
                workflow_id=99999, name="ghost", step_order=1
            ))


# ===========================================================================
# Workflow Instance & Transition Tests
# ===========================================================================


class TestWorkflowExecution:
    async def test_start_instance(self, db_session):
        ids = await _create_minimal_workflow(db_session)
        svc = _exec_service(db_session)

        instance = await svc.start_instance(
            workflow_id=ids["workflow_id"],
            entity_type="test_entity",
            entity_id=100,
            created_by=1,
        )
        assert instance.id is not None
        assert instance.status == "active"
        assert instance.current_step_id == ids["step_submitted"]
        assert instance.created_by == 1

    async def test_start_instance_inactive_workflow(self, db_session):
        """Starting an instance on an inactive workflow should fail."""
        ids = await _create_minimal_workflow(db_session)
        wf_repo = WorkflowRepository(db_session, platform_context())
        wf = await wf_repo.get_by_id(ids["workflow_id"])
        wf.status = "inactive"
        await wf_repo.update(wf)

        svc = _exec_service(db_session)
        from app.core.exceptions import ValidationError

        with pytest.raises(ValidationError, match="not active"):
            await svc.start_instance(
                workflow_id=ids["workflow_id"],
                entity_type="test_entity", entity_id=101,
            )

    async def test_duplicate_instance_prevented(self, db_session):
        """Cannot start a second active instance for the same entity."""
        ids = await _create_minimal_workflow(db_session)
        svc = _exec_service(db_session)

        await svc.start_instance(
            workflow_id=ids["workflow_id"],
            entity_type="test_entity", entity_id=200, created_by=1,
        )
        from app.core.exceptions import ConflictError

        with pytest.raises(ConflictError, match="already exists"):
            await svc.start_instance(
                workflow_id=ids["workflow_id"],
                entity_type="test_entity", entity_id=200, created_by=1,
            )

    async def test_approve_transition_moves_to_next_step(self, db_session):
        ids = await _create_minimal_workflow(db_session)
        svc = _exec_service(db_session)

        instance = await svc.start_instance(
            workflow_id=ids["workflow_id"],
            entity_type="test_entity", entity_id=300, created_by=1,
        )

        # Approve → should move to 'approved'
        instance = await svc.perform_action(
            instance_id=instance.id,
            action="approve",
            actor_id=2,
            comment="Looks good",
        )
        assert instance.current_step_id == ids["step_approved"]
        assert instance.status == "completed"  # approved is final
        assert len(instance.history) == 2  # submit + approve

    async def test_reject_marks_as_cancelled(self, db_session):
        ids = await _create_minimal_workflow(db_session)
        svc = _exec_service(db_session)

        instance = await svc.start_instance(
            workflow_id=ids["workflow_id"],
            entity_type="test_entity", entity_id=400, created_by=1,
        )

        # Move to approve step first to have a transition
        transitions = await svc.get_available_transitions(instance.id)
        reject_transition = [t for t in transitions
                             if t.to_step_id == ids["step_rejected"]]
        assert len(reject_transition) == 1

        instance = await svc.perform_action(
            instance_id=instance.id,
            action="reject",
            actor_id=2,
            comment="Not approved",
            to_step_id=reject_transition[0].to_step_id,
        )
        assert instance.status == "cancelled"

    async def test_approve_with_specific_step(self, db_session):
        """Approving with a specific to_step_id should respect it."""
        ids = await _create_minimal_workflow(db_session)
        svc = _exec_service(db_session)

        instance = await svc.start_instance(
            workflow_id=ids["workflow_id"],
            entity_type="test_entity", entity_id=500, created_by=1,
        )

        instance = await svc.perform_action(
            instance_id=instance.id,
            action="approve",
            actor_id=2,
            to_step_id=ids["step_approved"],
        )
        assert instance.current_step_id == ids["step_approved"]
        assert instance.status == "completed"

    async def test_action_on_completed_instance_fails(self, db_session):
        """Cannot perform actions on already completed instances."""
        ids = await _create_minimal_workflow(db_session)
        svc = _exec_service(db_session)

        instance = await svc.start_instance(
            workflow_id=ids["workflow_id"],
            entity_type="test_entity", entity_id=600, created_by=1,
        )
        await svc.perform_action(
            instance_id=instance.id, action="approve", actor_id=2,
        )

        from app.core.exceptions import ValidationError
        with pytest.raises(ValidationError, match="Cannot perform action on a"):
            await svc.perform_action(
                instance_id=instance.id, action="approve", actor_id=2,
            )

    async def test_invalid_action_name(self, db_session):
        ids = await _create_minimal_workflow(db_session)
        svc = _exec_service(db_session)

        instance = await svc.start_instance(
            workflow_id=ids["workflow_id"],
            entity_type="test_entity", entity_id=700, created_by=1,
        )
        from app.core.exceptions import ValidationError

        with pytest.raises(ValidationError, match="Invalid action"):
            await svc.perform_action(
                instance_id=instance.id, action="destroy", actor_id=2,
            )

    async def test_return_action_requires_to_step(self, db_session):
        ids = await _create_minimal_workflow(db_session)
        svc = _exec_service(db_session)

        instance = await svc.start_instance(
            workflow_id=ids["workflow_id"],
            entity_type="test_entity", entity_id=800, created_by=1,
        )
        from app.core.exceptions import ValidationError

        with pytest.raises(ValidationError, match="requires a 'to_step_id'"):
            await svc.perform_action(
                instance_id=instance.id, action="return", actor_id=2,
            )


# ===========================================================================
# Role Enforcement (P14 §4) & Cancel Action (P14 §3)
# ===========================================================================


class TestRoleEnforcement:
    """Server-side role checks — the UI can never bypass authorization."""

    async def test_transition_required_role_blocks_unauthorized(self, db_session):
        """Approve requires the transition's ``required_role``."""
        ids = await _create_minimal_workflow(
            db_session, approve_role="admin"
        )
        svc = _exec_service(db_session)
        instance = await svc.start_instance(
            workflow_id=ids["workflow_id"],
            entity_type="test_entity", entity_id=810, created_by=1,
        )

        from app.core.exceptions import AuthorizationError

        # A teacher may not approve an admin-gated transition.
        with pytest.raises(AuthorizationError, match="admin"):
            await svc.perform_action(
                instance_id=instance.id, action="approve",
                actor_id=2, actor_roles=["teacher"],
            )

        # The instance is untouched.
        assert (await svc.get_instance(instance.id)).status == "active"

        # An admin may.
        instance = await svc.perform_action(
            instance_id=instance.id, action="approve",
            actor_id=3, actor_roles=["admin"],
        )
        assert instance.status == "completed"

    async def test_step_assigned_role_blocks_unauthorized(self, db_session):
        """Acting on a step requires the step's ``assigned_role``."""
        ids = await _create_minimal_workflow(
            db_session, step_role="hod"
        )
        svc = _exec_service(db_session)
        instance = await svc.start_instance(
            workflow_id=ids["workflow_id"],
            entity_type="test_entity", entity_id=820, created_by=1,
        )

        from app.core.exceptions import AuthorizationError

        with pytest.raises(AuthorizationError, match="hod"):
            await svc.perform_action(
                instance_id=instance.id, action="reject",
                actor_id=2, actor_roles=["teacher"],
            )

        instance = await svc.perform_action(
            instance_id=instance.id, action="approve",
            actor_id=3, actor_roles=["hod"],
        )
        assert instance.status == "completed"

    async def test_reject_edge_role_enforced(self, db_session):
        """A role-gated reject edge blocks unauthorized rejections too."""
        ids = await _create_minimal_workflow(db_session)
        svc = _exec_service(db_session)

        # Gate the Reject edge with a role on top of the fixture workflow.
        from app.domains.workflow.repository import WorkflowTransitionRepository
        from app.multi_tenant.models import platform_context as _pc

        t_repo = WorkflowTransitionRepository(db_session, _pc())
        edges = await t_repo.get_available_from_step(ids["step_submitted"])
        reject_edge = next(
            (e for e in edges if e.to_step_id == ids["step_rejected"]), None
        )
        assert reject_edge is not None
        reject_edge.required_role = "admin"
        await db_session.flush()

        instance = await svc.start_instance(
            workflow_id=ids["workflow_id"],
            entity_type="test_entity", entity_id=835, created_by=1,
        )

        from app.core.exceptions import AuthorizationError

        with pytest.raises(AuthorizationError, match="admin"):
            await svc.perform_action(
                instance_id=instance.id, action="reject",
                actor_id=2, actor_roles=["teacher"],
                to_step_id=ids["step_rejected"],
            )

        # With the required role, the rejection succeeds.
        instance = await svc.perform_action(
            instance_id=instance.id, action="reject",
            actor_id=3, actor_roles=["admin"],
            to_step_id=ids["step_rejected"],
        )
        assert instance.status == "cancelled"

    async def test_multi_role_user_can_act(self, db_session):
        """Users holding multiple roles pass checks against any of them."""
        ids = await _create_minimal_workflow(
            db_session, approve_role="admin"
        )
        svc = _exec_service(db_session)
        instance = await svc.start_instance(
            workflow_id=ids["workflow_id"],
            entity_type="test_entity", entity_id=830, created_by=1,
        )

        instance = await svc.perform_action(
            instance_id=instance.id, action="approve",
            actor_id=2, actor_roles=["teacher", "admin"],
        )
        assert instance.status == "completed"

    async def test_available_transitions_filtered_by_role(self, db_session):
        """Transitions the actor lacks the role for are hidden."""
        ids = await _create_minimal_workflow(
            db_session, approve_role="admin"
        )
        svc = _exec_service(db_session)
        instance = await svc.start_instance(
            workflow_id=ids["workflow_id"],
            entity_type="test_entity", entity_id=840, created_by=1,
        )

        # Teacher: only the (role-free) reject path is visible.
        teacher_view = await svc.get_available_transitions(
            instance.id, actor_roles=["teacher"]
        )
        assert len(teacher_view) == 1
        assert teacher_view[0].to_step_id == ids["step_rejected"]

        # Admin: both paths visible.
        admin_view = await svc.get_available_transitions(
            instance.id, actor_roles=["admin"]
        )
        assert len(admin_view) == 2

        # No roles passed → legacy behavior (everything visible).
        full_view = await svc.get_available_transitions(instance.id)
        assert len(full_view) == 2

    async def test_available_transitions_blocks_step_role_mismatch(self, db_session):
        """A user lacking the step's assigned_role sees no actions at all."""
        ids = await _create_minimal_workflow(
            db_session, step_role="hod"
        )
        svc = _exec_service(db_session)
        instance = await svc.start_instance(
            workflow_id=ids["workflow_id"],
            entity_type="test_entity", entity_id=845, created_by=1,
        )

        # Teacher lacks the 'hod' step role → no transitions surface.
        teacher_view = await svc.get_available_transitions(
            instance.id, actor_roles=["teacher"]
        )
        assert teacher_view == []

        # A hod sees the full action set.
        hod_view = await svc.get_available_transitions(
            instance.id, actor_roles=["hod"]
        )
        assert len(hod_view) == 2


class TestCancelAction:
    """Cancel withdraws an active request before completion (P14 §3)."""

    @pytest.fixture
    def captured(self):
        """Capture workflow-cancelled events on the global bus, then clean up."""
        captured: list = []

        async def capture(event, **kwargs):
            captured.append(event)

        event_bus.register(WorkflowCancelledEvent, capture)
        event_bus.reset_dedup()
        try:
            yield captured
        finally:
            event_bus.unregister(WorkflowCancelledEvent, capture)
            event_bus.reset_dedup()

    async def test_cancel_marks_cancelled(self, db_session):
        ids = await _create_minimal_workflow(db_session)
        svc = _exec_service(db_session)
        instance = await svc.start_instance(
            workflow_id=ids["workflow_id"],
            entity_type="test_entity", entity_id=850, created_by=1,
        )

        instance = await svc.perform_action(
            instance_id=instance.id, action="cancel",
            actor_id=1, actor_roles=["teacher"], comment="Withdrawn",
        )
        assert instance.status == "cancelled"

        # History records the withdrawal distinctly from a rejection.
        reloaded = await svc.get_instance(instance.id)
        assert [h.action for h in reloaded.history] == ["submit", "cancel"]
        assert reloaded.history[-1].comment == "Withdrawn"

    async def test_cancel_on_completed_fails(self, db_session):
        ids = await _create_minimal_workflow(db_session)
        svc = _exec_service(db_session)
        instance = await svc.start_instance(
            workflow_id=ids["workflow_id"],
            entity_type="test_entity", entity_id=860, created_by=1,
        )
        await svc.perform_action(
            instance_id=instance.id, action="approve", actor_id=2,
        )

        from app.core.exceptions import ValidationError
        with pytest.raises(ValidationError, match="Cannot perform action"):
            await svc.perform_action(
                instance_id=instance.id, action="cancel", actor_id=1,
            )

    async def test_cancel_respects_step_role(self, db_session):
        """Cancel is still gated by the current step's assigned role."""
        ids = await _create_minimal_workflow(
            db_session, step_role="hod"
        )
        svc = _exec_service(db_session)
        instance = await svc.start_instance(
            workflow_id=ids["workflow_id"],
            entity_type="test_entity", entity_id=870, created_by=1,
        )

        from app.core.exceptions import AuthorizationError
        with pytest.raises(AuthorizationError, match="hod"):
            await svc.perform_action(
                instance_id=instance.id, action="cancel",
                actor_id=2, actor_roles=["teacher"],
            )

    async def test_cancel_emits_cancelled_event(self, db_session, captured):
        """A cancelled workflow produces a workflow.cancelled domain event."""
        ids = await _create_minimal_workflow(db_session)
        svc = _exec_service(db_session)
        instance = await svc.start_instance(
            workflow_id=ids["workflow_id"],
            entity_type="test_entity", entity_id=880, created_by=1,
        )

        await svc.perform_action(
            instance_id=instance.id, action="cancel",
            actor_id=1, actor_roles=["teacher"],
        )
        assert any(isinstance(e, WorkflowCancelledEvent) for e in captured)
        event = [e for e in captured if isinstance(e, WorkflowCancelledEvent)][0]
        assert event.instance_id == instance.id
        assert event.created_by == 1


# ===========================================================================
# Available Transitions & History Tests
# ===========================================================================


class TestTransitionsAndHistory:
    async def test_available_transitions(self, db_session):
        ids = await _create_minimal_workflow(db_session)
        svc = _exec_service(db_session)

        instance = await svc.start_instance(
            workflow_id=ids["workflow_id"],
            entity_type="test_entity", entity_id=900, created_by=1,
        )

        transitions = await svc.get_available_transitions(instance.id)
        assert len(transitions) == 2
        assert any(t.to_step_id == ids["step_approved"] for t in transitions)
        assert any(t.to_step_id == ids["step_rejected"] for t in transitions)

    async def test_history_recorded(self, db_session):
        ids = await _create_minimal_workflow(db_session)
        svc = _exec_service(db_session)

        instance = await svc.start_instance(
            workflow_id=ids["workflow_id"],
            entity_type="test_entity", entity_id=950, created_by=1,
        )
        await svc.perform_action(
            instance_id=instance.id, action="approve",
            actor_id=2, comment="Approved!",
        )

        # Reload to get fresh history
        instance2 = await svc.get_instance(instance.id)
        assert len(instance2.history) == 2

        submit_event = instance2.history[0]
        assert submit_event.action == "submit"
        assert submit_event.from_step_id is None

        approve_event = instance2.history[1]
        assert approve_event.action == "approve"
        assert approve_event.actor_id == 2
        assert approve_event.comment == "Approved!"

    async def test_get_instance_by_entity(self, db_session):
        ids = await _create_minimal_workflow(db_session)
        svc = _exec_service(db_session)

        await svc.start_instance(
            workflow_id=ids["workflow_id"],
            entity_type="test_entity", entity_id=980, created_by=1,
        )

        instance = await svc.get_instance_by_entity("test_entity", 980)
        assert instance is not None
        assert instance.entity_id == 980

        missing = await svc.get_instance_by_entity("test_entity", 99999)
        assert missing is None

    async def test_list_instances(self, db_session):
        ids = await _create_minimal_workflow(db_session)
        svc = _exec_service(db_session)

        for i in range(3):
            await svc.start_instance(
                workflow_id=ids["workflow_id"],
                entity_type="list_test", entity_id=1000 + i, created_by=1,
            )

        items, total = await svc.list_instances(
            entity_type="list_test",
        )
        assert total >= 3


# ===========================================================================
# Audit & Notification Integration Tests
# ===========================================================================


class TestAuditIntegration:
    async def test_audit_recorded_on_approve(self, db_session):
        """Approval actions should produce audit entries."""
        ids = await _create_minimal_workflow(db_session)
        svc = _exec_service(db_session)

        instance = await svc.start_instance(
            workflow_id=ids["workflow_id"],
            entity_type="test_entity", entity_id=1100, created_by=1,
        )
        await svc.perform_action(
            instance_id=instance.id, action="approve", actor_id=2,
        )

        # Verify audit entries exist
        from app.domains.audit.repository import AuditLogRepository
        audit_repo = AuditLogRepository(db_session, platform_context())
        items, total = await audit_repo.list()
        audit_workflow_entries = [
            a for a in items
            if a.resource_type == "workflow"
        ]
        assert len(audit_workflow_entries) >= 1
        entry = audit_workflow_entries[-1]
        assert entry.action == "APPROVE"

    async def test_audit_recorded_on_reject(self, db_session):
        """Rejection should produce audit entries."""
        ids = await _create_minimal_workflow(db_session)
        svc = _exec_service(db_session)

        instance = await svc.start_instance(
            workflow_id=ids["workflow_id"],
            entity_type="test_entity", entity_id=1200, created_by=1,
        )
        transitions = await svc.get_available_transitions(instance.id)
        reject_t = [t for t in transitions
                    if t.to_step_id == ids["step_rejected"]][0]

        await svc.perform_action(
            instance_id=instance.id, action="reject",
            actor_id=3, to_step_id=reject_t.to_step_id,
        )

        from app.domains.audit.repository import AuditLogRepository
        audit_repo = AuditLogRepository(db_session, platform_context())
        items, total = await audit_repo.list()
        audit_workflow_entries = [
            a for a in items
            if a.resource_type == "workflow" and a.action == "UPDATE"
        ]
        # Reject records UPDATE action
        assert len(audit_workflow_entries) >= 1


# ===========================================================================
# Full Integration Test
# ===========================================================================


class TestFullWorkflowCycle:
    async def test_complete_workflow_cycle(self, db_session):
        """Full cycle: create workflow definition → start → approve → complete."""
        admin = _admin_service(db_session)
        exec_svc = _exec_service(db_session)

        # 1. Create workflow definition
        wf = await admin.create_workflow(
            name="Integration WF", code="INT_WF", entity_type="integration_test"
        )

        # 2. Create steps
        from app.domains.workflow.schemas import WorkflowStepCreate, WorkflowTransitionCreate

        step1 = await admin.create_step(WorkflowStepCreate(
            workflow_id=wf.id, name="draft", step_order=1, is_initial=True,
        ))
        step2 = await admin.create_step(WorkflowStepCreate(
            workflow_id=wf.id, name="reviewed", step_order=2,
        ))
        step3 = await admin.create_step(WorkflowStepCreate(
            workflow_id=wf.id, name="finalized", step_order=3, is_final=True,
        ))

        # 3. Create transitions
        await admin.create_transition(WorkflowTransitionCreate(
            workflow_id=wf.id, from_step_id=step1.id, to_step_id=step2.id,
        ))
        await admin.create_transition(WorkflowTransitionCreate(
            workflow_id=wf.id, from_step_id=step2.id, to_step_id=step3.id,
        ))

        # 4. Start instance
        instance = await exec_svc.start_instance(
            workflow_id=wf.id, entity_type="integration_test",
            entity_id=2000, created_by=1,
        )
        assert instance.current_step_id == step1.id

        # 5. Approve once (move from draft → reviewed)
        instance = await exec_svc.perform_action(
            instance_id=instance.id, action="approve", actor_id=2,
        )
        assert instance.current_step_id == step2.id
        assert instance.status == "active"  # not final yet

        # 6. Approve twice (move from reviewed → finalized)
        instance = await exec_svc.perform_action(
            instance_id=instance.id, action="approve", actor_id=3,
        )
        assert instance.current_step_id == step3.id
        assert instance.status == "completed"

        # 7. Verify history has 3 entries
        instance = await exec_svc.get_instance(instance.id)
        assert len(instance.history) == 3
        assert [h.action for h in instance.history] == ["submit", "approve", "approve"]
