from __future__ import annotations

import datetime
import logging
from datetime import timezone
from typing import Optional, Sequence

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.domains.audit.constants import APPROVE, UPDATE, WORKFLOW
from app.domains.audit.service import AuditService
from app.domains.events import publish_event
from app.domains.events.events import (
    WorkflowApprovedEvent,
    WorkflowRejectedEvent,
    WorkflowSubmittedEvent,
)
from app.domains.workflow.models import (
    ApprovalHistory,
    Workflow,
    WorkflowAction,
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

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# Workflow Admin Service — manage definitions
# ---------------------------------------------------------------------------


class WorkflowAdminService:
    """Admin service: create/update workflow templates, steps, transitions."""

    def __init__(
        self,
        workflow_repo: WorkflowRepository,
        step_repo: WorkflowStepRepository,
        transition_repo: WorkflowTransitionRepository,
        action_repo: WorkflowActionRepository,
    ) -> None:
        self.workflow_repo = workflow_repo
        self.step_repo = step_repo
        self.transition_repo = transition_repo
        self.action_repo = action_repo

    # ── Workflow CRUD ──

    async def create_workflow(self, name: str, code: str, entity_type: str, description: Optional[str] = None) -> Workflow:
        existing = await self.workflow_repo.get_by_code(code)
        if existing is not None:
            raise ConflictError(f"Workflow with code '{code}' already exists")
        wf = Workflow(name=name, code=code, entity_type=entity_type, description=description)
        return await self.workflow_repo.create(wf)

    async def get_workflow(self, workflow_id: int) -> Workflow:
        return await self.workflow_repo.get_by_id(workflow_id)

    async def get_workflow_by_code(self, code: str) -> Workflow:
        wf = await self.workflow_repo.get_by_code(code)
        if wf is None:
            raise NotFoundError(f"Workflow with code '{code}' not found")
        return wf

    async def list_workflows(
        self, status: Optional[str] = None, entity_type: Optional[str] = None,
        skip: int = 0, limit: int = 100,
    ) -> tuple[Sequence[Workflow], int]:
        return await self.workflow_repo.list(
            status=status, entity_type=entity_type, skip=skip, limit=limit,
        )

    async def update_workflow(self, workflow_id: int, **kwargs) -> Workflow:
        wf = await self.workflow_repo.get_by_id(workflow_id)
        for key, value in kwargs.items():
            if value is not None and hasattr(wf, key):
                setattr(wf, key, value)
        return await self.workflow_repo.update(wf)

    async def delete_workflow(self, workflow_id: int) -> None:
        wf = await self.workflow_repo.get_by_id(workflow_id)
        await self.workflow_repo.delete(wf)

    # ── Steps ──

    async def create_step(self, data) -> WorkflowStep:
        wf = await self.workflow_repo.get_by_id(data.workflow_id)
        if wf is None:
            raise NotFoundError(f"Workflow with id {data.workflow_id} not found")
        step = WorkflowStep(
            workflow_id=data.workflow_id,
            name=data.name,
            label=data.label,
            step_order=data.step_order,
            is_initial=data.is_initial,
            is_final=data.is_final,
            assigned_role=data.assigned_role,
        )
        return await self.step_repo.create(step)

    async def update_step(self, step_id: int, data) -> WorkflowStep:
        step = await self.step_repo.get_by_id(step_id)
        if data.name is not None:
            step.name = data.name
        if data.label is not None:
            step.label = data.label
        if data.step_order is not None:
            step.step_order = data.step_order
        if data.is_initial is not None:
            step.is_initial = data.is_initial
        if data.is_final is not None:
            step.is_final = data.is_final
        if data.assigned_role is not None:
            step.assigned_role = data.assigned_role
        return await self.step_repo.update(step)

    async def delete_step(self, step_id: int) -> None:
        step = await self.step_repo.get_by_id(step_id)
        await self.step_repo.delete(step)

    # ── Transitions ──

    async def create_transition(self, data) -> WorkflowTransition:
        wf = await self.workflow_repo.get_by_id(data.workflow_id)
        if wf is None:
            raise NotFoundError(f"Workflow with id {data.workflow_id} not found")
        # Validate both steps belong to the same workflow
        from_step = await self.step_repo.get_by_id(data.from_step_id)
        to_step = await self.step_repo.get_by_id(data.to_step_id)
        if from_step.workflow_id != data.workflow_id or to_step.workflow_id != data.workflow_id:
            raise ValidationError("Both steps must belong to the same workflow")
        t = WorkflowTransition(
            workflow_id=data.workflow_id,
            from_step_id=data.from_step_id,
            to_step_id=data.to_step_id,
            label=data.label,
            required_role=data.required_role,
        )
        return await self.transition_repo.create(t)

    async def delete_transition(self, transition_id: int) -> None:
        t = await self.transition_repo.get_by_id(transition_id)
        await self.transition_repo.delete(t)

    # ── Actions ──

    async def create_action(self, data) -> WorkflowAction:
        wf = await self.workflow_repo.get_by_id(data.workflow_id)
        if wf is None:
            raise NotFoundError(f"Workflow with id {data.workflow_id} not found")
        await self.step_repo.get_by_id(data.step_id)  # validate step exists
        action = WorkflowAction(
            workflow_id=data.workflow_id,
            step_id=data.step_id,
            action_type=data.action_type,
            action_config=data.action_config,
        )
        return await self.action_repo.create(action)

    async def delete_action(self, action_id: int) -> None:
        action = await self.action_repo.get_by_id(action_id)
        await self.action_repo.delete(action)

    # ── Full definition ──

    async def get_workflow_definition(self, workflow_id: int) -> dict:
        wf = await self.workflow_repo.get_by_id(workflow_id)
        steps = await self.step_repo.list_by_workflow(workflow_id)
        transitions = await self.transition_repo.list_by_workflow(workflow_id)
        actions = await self.action_repo.list_by_workflow(workflow_id)
        return {
            "workflow": wf,
            "steps": list(steps),
            "transitions": list(transitions),
            "actions": list(actions),
        }


# ---------------------------------------------------------------------------
# Workflow Execution Service — run instances through workflows
# ---------------------------------------------------------------------------


class WorkflowExecutionService:
    """
    Generic, dynamic workflow execution engine.
    No hardcoded step logic. All workflows driven by DB configuration.
    """

    def __init__(
        self,
        instance_repo: WorkflowInstanceRepository,
        workflow_repo: WorkflowRepository,
        step_repo: WorkflowStepRepository,
        transition_repo: WorkflowTransitionRepository,
        action_repo: WorkflowActionRepository,
        history_repo: ApprovalHistoryRepository,
    ) -> None:
        self.instance_repo = instance_repo
        self.workflow_repo = workflow_repo
        self.step_repo = step_repo
        self.transition_repo = transition_repo
        self.action_repo = action_repo
        self.history_repo = history_repo

    # ── Start a new workflow instance ──

    async def start_instance(
        self, workflow_id: int, entity_type: str, entity_id: int,
        created_by: Optional[int] = None,
    ) -> WorkflowInstance:
        wf = await self.workflow_repo.get_by_id(workflow_id)
        if wf.status != "active":
            raise ValidationError(f"Workflow '{wf.name}' is not active")

        # Lock to one active instance per entity
        existing = await self.instance_repo.get_by_entity(entity_type, entity_id)
        if existing is not None:
            raise ConflictError(
                f"An active workflow instance already exists for "
                f"{entity_type} #{entity_id}"
            )

        initial_step = await self.step_repo.get_initial_step(workflow_id)
        if initial_step is None:
            raise ValidationError(
                f"Workflow '{wf.name}' has no initial step defined"
            )

        now = datetime.datetime.now(timezone.utc)
        instance = WorkflowInstance(
            workflow_id=workflow_id,
            current_step_id=initial_step.id,
            entity_type=entity_type,
            entity_id=entity_id,
            status="active",
            created_by=created_by,
            created_at=now,
            updated_at=now,
        )
        instance = await self.instance_repo.create(instance)

        # Record initial submission in history
        history = ApprovalHistory(
            instance_id=instance.id,
            from_step_id=None,
            to_step_id=initial_step.id,
            action="submit",
            actor_id=created_by,
            comment="Workflow instance started",
        )
        await self.history_repo.create(history)

        return instance

    # ── Perform a transition ──

    async def perform_action(
        self,
        instance_id: int,
        action: str,
        actor_id: Optional[int] = None,
        comment: Optional[str] = None,
        to_step_id: Optional[int] = None,
    ) -> WorkflowInstance:
        instance = await self.instance_repo.get_by_id(instance_id)

        if instance.status != "active":
            raise ValidationError(
                f"Cannot perform action on a {instance.status} workflow instance"
            )

        allowed_actions = {"approve", "reject", "return", "submit"}
        if action not in allowed_actions:
            raise ValidationError(
                f"Invalid action '{action}'. Must be one of {allowed_actions}"
            )

        current_step = instance.current_step

        if action == "approve":
            transitions = await self.transition_repo.get_available_from_step(
                current_step.id
            )
            if not transitions:
                raise ValidationError(
                    f"No transitions available from step '{current_step.name}'"
                )

            # If to_step_id specified, find matching transition; otherwise use first
            if to_step_id is not None:
                matching = [t for t in transitions if t.to_step_id == to_step_id]
                if not matching:
                    raise ValidationError(
                        f"No transition from step {current_step.id} to step {to_step_id}"
                    )
                transition = matching[0]
            else:
                transition = transitions[0]

            # Move to the target step.  Assign the relationship (not just
            # the FK) so ``instance.current_step`` is never stale within
            # the same session — important for chained transitions.
            target_step = await self.step_repo.get_by_id(transition.to_step_id)
            instance.current_step = target_step
            instance.updated_at = datetime.datetime.now(timezone.utc)

            if target_step.is_final:
                instance.status = "completed"

        elif action == "reject":
            # Reject always terminates the instance as cancelled, moving
            # to the designated step (if any) for record-keeping.
            if to_step_id is not None:
                target_step = await self.step_repo.get_by_id(to_step_id)
                instance.current_step = target_step
            instance.status = "cancelled"
            instance.updated_at = datetime.datetime.now(timezone.utc)

        elif action == "return":
            if to_step_id is None:
                raise ValidationError(
                    "Return action requires a 'to_step_id' (the step to return to)"
                )
            # Validate the target step exists
            target_step = await self.step_repo.get_by_id(to_step_id)
            if target_step.workflow_id != instance.workflow_id:
                raise ValidationError("Target step does not belong to this workflow")
            instance.current_step = target_step
            instance.updated_at = datetime.datetime.now(timezone.utc)

        elif action == "submit":
            # Submit from initial step — just ensure we're on the right step
            if not current_step.is_initial:
                raise ValidationError("Can only submit from the initial step")
            transitions = await self.transition_repo.get_available_from_step(
                current_step.id
            )
            if not transitions:
                raise ValidationError("No forward transitions available from current step")
            transition = transitions[0]
            target_step = await self.step_repo.get_by_id(transition.to_step_id)
            instance.current_step = target_step
            instance.updated_at = datetime.datetime.now(timezone.utc)

        instance = await self.instance_repo.update(instance)

        # Record in history
        history = ApprovalHistory(
            instance_id=instance.id,
            from_step_id=current_step.id,
            to_step_id=instance.current_step_id,
            action=action,
            actor_id=actor_id,
            comment=comment,
        )
        await self.history_repo.create(history)

        # Reload the history collection so the in-memory instance reflects
        # the new entry.  The relationship is selectin-loaded at fetch time
        # and would otherwise be stale within the same session.
        await self.history_repo.session.refresh(
            instance, attribute_names=["history"]
        )

        # Fire audit entry
        try:
            audit_svc = AuditService(self.history_repo.session)
            await audit_svc.record(
                action=APPROVE if action == "approve" else UPDATE,
                resource_type=WORKFLOW,
                resource_id=str(instance_id),
                user_id=actor_id,
                details={
                    "instance_id": instance_id,
                    "entity_type": instance.entity_type,
                    "entity_id": instance.entity_id,
                    "action": action,
                    "from_step_id": current_step.id,
                    "to_step_id": instance.current_step_id,
                    "instance_status": instance.status,
                    "comment": comment,
                },
            )
            await self.history_repo.session.flush()
        except Exception:
            logger.warning("Failed to write audit entry for workflow action (non-fatal)", exc_info=True)

        # Fire standard workflow domain event.  The notification side is
        # produced by the ``WorkflowApprovedEvent`` handler registered on the
        # domain event bus (single source of truth for notifications).
        try:
            step_name = instance.current_step.name if instance.current_step else ""
            from app.domains.events.events import DomainEvent as _DomainEvent

            event: _DomainEvent
            if action == "approve":
                event = WorkflowApprovedEvent(
                    instance_id=instance.id,
                    workflow_id=instance.workflow_id,
                    entity_type=instance.entity_type,
                    entity_id=instance.entity_id,
                    step_name=step_name,
                    status=instance.status,
                    actor_id=actor_id,
                    created_by=instance.created_by,
                    comment=comment,
                )
            elif action == "reject":
                event = WorkflowRejectedEvent(
                    instance_id=instance.id,
                    workflow_id=instance.workflow_id,
                    entity_type=instance.entity_type,
                    entity_id=instance.entity_id,
                    step_name=step_name,
                    status=instance.status,
                    actor_id=actor_id,
                    created_by=instance.created_by,
                    comment=comment,
                )
            else:
                event = WorkflowSubmittedEvent(
                    instance_id=instance.id,
                    workflow_id=instance.workflow_id,
                    entity_type=instance.entity_type,
                    entity_id=instance.entity_id,
                    created_by=actor_id,
                )
            await publish_event(event, session=self.history_repo.session)
        except Exception:
            logger.warning("Failed to dispatch workflow domain event (non-fatal)", exc_info=True)

        return instance

    # ── Get available transitions for the current step ──

    async def get_available_transitions(
        self, instance_id: int
    ) -> list[AvailableTransition]:
        instance = await self.instance_repo.get_by_id(instance_id)
        transitions = await self.transition_repo.get_available_from_step(
            instance.current_step_id
        )
        result = []
        for t in transitions:
            to_step = await self.step_repo.get_by_id(t.to_step_id)
            result.append(
                AvailableTransition(
                    transition_id=t.id,
                    from_step_id=t.from_step_id,
                    to_step_id=t.to_step_id,
                    label=t.label,
                    to_step_name=to_step.name,
                    to_step_label=to_step.label,
                    required_role=t.required_role,
                )
            )
        return result

    # ── Get instance (detail) ──

    async def get_instance(self, instance_id: int) -> WorkflowInstance:
        return await self.instance_repo.get_by_id(instance_id)

    async def get_instance_by_entity(
        self, entity_type: str, entity_id: int
    ) -> WorkflowInstance | None:
        return await self.instance_repo.get_by_entity(entity_type, entity_id)

    async def list_instances(
        self,
        status: Optional[str] = None,
        entity_type: Optional[str] = None,
        created_by: Optional[int] = None,
        workflow_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[WorkflowInstance], int]:
        return await self.instance_repo.list(
            status=status,
            entity_type=entity_type,
            created_by=created_by,
            workflow_id=workflow_id,
            skip=skip,
            limit=limit,
        )
