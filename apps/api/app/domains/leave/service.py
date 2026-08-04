from __future__ import annotations

from typing import Optional, Sequence

from app.core.exceptions import ValidationError
from app.domains.leave.models import LEAVE_TYPES, LeaveRequest
from app.domains.leave.repository import LeaveRequestRepository
from app.domains.workflow.repository import (
    WorkflowInstanceRepository,
    WorkflowRepository,
)
from app.domains.workflow.service import WorkflowExecutionService


class LeaveRequestService:
    """
    LeaveRequest business logic.
    When a leave is created, automatically starts a Workflow Engine instance
    with entity_type="leave_request" and entity_id=leave.id.
    """

    WORKFLOW_CODE = "LEAVE_REQUEST"

    def __init__(
        self,
        repo: LeaveRequestRepository,
        workflow_svc: WorkflowExecutionService,
        workflow_repo: WorkflowRepository,
        instance_repo: WorkflowInstanceRepository,
    ) -> None:
        self.repo = repo
        self.workflow_svc = workflow_svc
        self.workflow_repo = workflow_repo
        self.instance_repo = instance_repo

    async def create(
        self, user_id: int, data
    ) -> LeaveRequest:
        # Parse dates
        try:
            start = data.start_date
            end = data.end_date
            from datetime import datetime
            start_dt = datetime.strptime(start, "%Y-%m-%d")
            end_dt = datetime.strptime(end, "%Y-%m-%d")
            duration = (end_dt - start_dt).days + 1
            if duration < 1:
                raise ValueError
        except (ValueError, TypeError):
            raise ValidationError(
                "Invalid dates. Ensure end_date >= start_date and format is YYYY-MM-DD"
            )

        leave = LeaveRequest(
            user_id=user_id,
            leave_type=data.leave_type,
            start_date=start,
            end_date=end,
            reason=data.reason,
            duration_days=duration,
        )
        leave = await self.repo.create(leave)

        # Start workflow engine instance
        wf = await self.workflow_repo.get_by_code(self.WORKFLOW_CODE)
        if wf is not None:
            instance = await self.workflow_svc.start_instance(
                workflow_id=wf.id,
                entity_type="leave_request",
                entity_id=leave.id,
                created_by=user_id,
            )
            leave.workflow_instance_id = instance.id
            leave = await self.repo.update(leave)

        return leave

    async def get(self, leave_id: int) -> LeaveRequest:
        return await self.repo.get_by_id(leave_id)

    async def get_allow_legacy_owner(
        self, leave_id: int, user_id: int
    ) -> LeaveRequest:
        """Tenant-scoped fetch that also lets the owner of an untagged
        (legacy) request through.  Cross-tenant rows are never returned.
        """
        return await self.repo.get_by_id_allow_legacy_owner(leave_id, user_id)

    async def update(self, leave_id: int, data) -> LeaveRequest:
        leave = await self.repo.get_by_id(leave_id)
        if leave.workflow_instance_id is not None:
            # Check if workflow is still active before allowing edits
            instance = await self.instance_repo.get_by_id(leave.workflow_instance_id)
            if instance.status == "active":
                raise ValidationError(
                    "Cannot edit a leave request while the workflow is active"
                )

        if data.leave_type is not None:
            leave.leave_type = data.leave_type
        if data.start_date is not None:
            leave.start_date = data.start_date
        if data.end_date is not None:
            leave.end_date = data.end_date
        if data.reason is not None:
            leave.reason = data.reason

        # Recalculate duration
        if data.start_date is not None or data.end_date is not None:
            from datetime import datetime
            start_dt = datetime.strptime(leave.start_date, "%Y-%m-%d")
            end_dt = datetime.strptime(leave.end_date, "%Y-%m-%d")
            leave.duration_days = (end_dt - start_dt).days + 1

        return await self.repo.update(leave)

    async def list(
        self,
        user_id: Optional[int] = None,
        leave_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[LeaveRequest], int]:
        return await self.repo.list(
            user_id=user_id,
            leave_type=leave_type,
            skip=skip,
            limit=limit,
        )

    async def get_workflow_status(self, leave_id: int) -> dict | None:
        """Get the workflow status for a leave request."""
        leave = await self.repo.get_by_id(leave_id)
        if not leave.workflow_instance_id:
            return None
        instance = await self.instance_repo.get_by_id(leave.workflow_instance_id)
        if not instance:
            return None
        return {
            "instance_id": instance.id,
            "status": instance.status,
            "current_step_id": instance.current_step_id,
            "current_step_name": instance.current_step.name if instance.current_step else None,
            "current_step_label": instance.current_step.label if instance.current_step else None,
            "history": [
                {
                    "id": h.id,
                    "action": h.action,
                    "actor_id": h.actor_id,
                    "comment": h.comment,
                    "created_at": h.created_at.isoformat(),
                }
                for h in (instance.history or [])
            ],
        }
