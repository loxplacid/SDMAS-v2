from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import Page, PaginationParams
from app.domains.auth.dependencies import get_current_user
from app.domains.auth.models import User
from app.domains.leave.repository import LeaveRequestRepository
from app.domains.leave.schemas import (
    LeaveRequestCreate,
    LeaveRequestDetailResponse,
    LeaveRequestResponse,
    LeaveRequestUpdate,
)
from app.domains.leave.service import LeaveRequestService
from app.domains.workflow.repository import (
    ApprovalHistoryRepository,
    WorkflowActionRepository,
    WorkflowInstanceRepository,
    WorkflowRepository,
    WorkflowStepRepository,
    WorkflowTransitionRepository,
)
from app.domains.workflow.service import WorkflowExecutionService
from app.infrastructure.database import get_session
from app.multi_tenant.dependencies import get_optional_tenant
from app.multi_tenant.guards import assert_tenant_scope_or_owner, inject_campus
from app.multi_tenant.models import TenantContext

router = APIRouter(prefix="/api/leave", tags=["leave"])


async def get_leave_service(
    session: AsyncSession = Depends(get_session),
) -> LeaveRequestService:
    return LeaveRequestService(
        repo=LeaveRequestRepository(session),
        workflow_svc=WorkflowExecutionService(
            instance_repo=WorkflowInstanceRepository(session),
            workflow_repo=WorkflowRepository(session),
            step_repo=WorkflowStepRepository(session),
            transition_repo=WorkflowTransitionRepository(session),
            action_repo=WorkflowActionRepository(session),
            history_repo=ApprovalHistoryRepository(session),
        ),
        workflow_repo=WorkflowRepository(session),
        instance_repo=WorkflowInstanceRepository(session),
    )


@router.post(
    "",
    response_model=LeaveRequestResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_leave(
    data: LeaveRequestCreate,
    service: LeaveRequestService = Depends(get_leave_service),
    current_user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_optional_tenant),
) -> LeaveRequestResponse:
    leave = await service.create(user_id=current_user.id, data=data)
    inject_campus(leave, tenant)
    return LeaveRequestResponse.model_validate(leave)


@router.get("/{leave_id}", response_model=LeaveRequestDetailResponse)
async def get_leave(
    leave_id: int,
    service: LeaveRequestService = Depends(get_leave_service),
    _current_user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_optional_tenant),
) -> dict:
    leave = await service.get(leave_id)
    assert_tenant_scope_or_owner(
        leave, tenant, _current_user.id, resource="leave request"
    )
    wf_status = await service.get_workflow_status(leave_id)
    return {
        "id": leave.id,
        "user_id": leave.user_id,
        "leave_type": leave.leave_type,
        "start_date": leave.start_date,
        "end_date": leave.end_date,
        "reason": leave.reason,
        "duration_days": leave.duration_days,
        "workflow_instance_id": leave.workflow_instance_id,
        "created_at": leave.created_at,
        "updated_at": leave.updated_at,
        "workflow_status": wf_status["status"] if wf_status else None,
        "workflow_current_step": wf_status["current_step_name"] if wf_status else None,
    }


@router.get("", response_model=Page[LeaveRequestResponse])
async def list_leave(
    pagination: PaginationParams = Depends(),
    leave_type: Optional[str] = Query(default=None, alias="leave_type"),
    service: LeaveRequestService = Depends(get_leave_service),
    current_user: User = Depends(get_current_user),
) -> Page[LeaveRequestResponse]:
    items, total = await service.list(
        user_id=current_user.id,
        leave_type=leave_type,
        skip=pagination.offset,
        limit=pagination.limit,
    )
    return Page.create(
        items=[LeaveRequestResponse.model_validate(i) for i in items],
        total=total,
        page=pagination.page,
        size=pagination.size,
    )


@router.patch("/{leave_id}", response_model=LeaveRequestResponse)
async def update_leave(
    leave_id: int,
    data: LeaveRequestUpdate,
    service: LeaveRequestService = Depends(get_leave_service),
    _current_user: User = Depends(get_current_user),
    tenant: TenantContext = Depends(get_optional_tenant),
) -> LeaveRequestResponse:
    existing = await service.get(leave_id)
    assert_tenant_scope_or_owner(
        existing, tenant, _current_user.id, resource="leave request"
    )
    leave = await service.update(leave_id, data)
    return LeaveRequestResponse.model_validate(leave)
