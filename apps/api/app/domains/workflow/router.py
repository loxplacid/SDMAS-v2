from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.pagination import Page, PaginationParams
from app.domains.auth.dependencies import get_current_user, require_role
from app.domains.auth.models import User
from app.domains.workflow.repository import (
    ApprovalHistoryRepository,
    WorkflowActionRepository,
    WorkflowInstanceRepository,
    WorkflowRepository,
    WorkflowStepRepository,
    WorkflowTransitionRepository,
)
from app.domains.workflow.schemas import (
    AvailableTransition,
    WorkflowActionCreate,
    WorkflowActionResponse,
    WorkflowActionRequest,
    WorkflowCreate,
    WorkflowDefinition,
    WorkflowInstanceCreate,
    WorkflowInstanceDetailResponse,
    WorkflowInstanceResponse,
    WorkflowResponse,
    WorkflowStepCreate,
    WorkflowStepResponse,
    WorkflowStepUpdate,
    WorkflowTransitionCreate,
    WorkflowTransitionResponse,
    WorkflowUpdate,
)
from app.domains.workflow.service import (
    WorkflowAdminService,
    WorkflowExecutionService,
)
from app.infrastructure.database import get_session
from app.multi_tenant.dependencies import require_tenant_context
from app.multi_tenant.models import TenantContext

router = APIRouter(prefix="/api/workflows", tags=["workflows"])


# ---------------------------------------------------------------------------
# Dependencies
# ---------------------------------------------------------------------------


async def get_admin_service(
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(require_tenant_context),
) -> WorkflowAdminService:
    return WorkflowAdminService(
        workflow_repo=WorkflowRepository(session, tenant),
        step_repo=WorkflowStepRepository(session, tenant),
        transition_repo=WorkflowTransitionRepository(session, tenant),
        action_repo=WorkflowActionRepository(session, tenant),
    )


async def get_execution_service(
    session: AsyncSession = Depends(get_session),
    tenant: TenantContext = Depends(require_tenant_context),
) -> WorkflowExecutionService:
    return WorkflowExecutionService(
        instance_repo=WorkflowInstanceRepository(session, tenant),
        workflow_repo=WorkflowRepository(session, tenant),
        step_repo=WorkflowStepRepository(session, tenant),
        transition_repo=WorkflowTransitionRepository(session, tenant),
        action_repo=WorkflowActionRepository(session, tenant),
        history_repo=ApprovalHistoryRepository(session, tenant),
    )


# ===================================================================
# WORKFLOW DEFINITION — Admin CRUD
# ===================================================================


@router.post(
    "",
    response_model=WorkflowResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_workflow(
    data: WorkflowCreate,
    service: WorkflowAdminService = Depends(get_admin_service),
    _current_user: User = Depends(require_role("admin")),
) -> WorkflowResponse:
    wf = await service.create_workflow(
        name=data.name,
        code=data.code,
        entity_type=data.entity_type,
        description=data.description,
    )
    return WorkflowResponse.model_validate(wf)


@router.get("/{workflow_id}", response_model=WorkflowDefinition)
async def get_workflow(
    workflow_id: int,
    service: WorkflowAdminService = Depends(get_admin_service),
    _current_user: User = Depends(get_current_user),
) -> dict:
    return await service.get_workflow_definition(workflow_id)


@router.get("", response_model=Page[WorkflowResponse])
async def list_workflows(
    pagination: PaginationParams = Depends(),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    entity_type: Optional[str] = Query(default=None, alias="entity_type"),
    service: WorkflowAdminService = Depends(get_admin_service),
    _current_user: User = Depends(get_current_user),
) -> Page[WorkflowResponse]:
    items, total = await service.list_workflows(
        status=status_filter,
        entity_type=entity_type,
        skip=pagination.offset,
        limit=pagination.limit,
    )
    return Page.create(
        items=[WorkflowResponse.model_validate(i) for i in items],
        total=total,
        page=pagination.page,
        size=pagination.size,
    )


@router.patch("/{workflow_id}", response_model=WorkflowResponse)
async def update_workflow(
    workflow_id: int,
    data: WorkflowUpdate,
    service: WorkflowAdminService = Depends(get_admin_service),
    _current_user: User = Depends(require_role("admin")),
) -> WorkflowResponse:
    wf = await service.update_workflow(
        workflow_id,
        name=data.name,
        description=data.description,
        entity_type=data.entity_type,
        status=data.status,
    )
    return WorkflowResponse.model_validate(wf)


@router.delete("/{workflow_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_workflow(
    workflow_id: int,
    service: WorkflowAdminService = Depends(get_admin_service),
    _current_user: User = Depends(require_role("admin")),
) -> None:
    await service.delete_workflow(workflow_id)


# ===================================================================
# STEPS
# ===================================================================


@router.post(
    "/steps",
    response_model=WorkflowStepResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_step(
    data: WorkflowStepCreate,
    service: WorkflowAdminService = Depends(get_admin_service),
    _current_user: User = Depends(require_role("admin")),
) -> WorkflowStepResponse:
    step = await service.create_step(data)
    return WorkflowStepResponse.model_validate(step)


@router.patch("/steps/{step_id}", response_model=WorkflowStepResponse)
async def update_step(
    step_id: int,
    data: WorkflowStepUpdate,
    service: WorkflowAdminService = Depends(get_admin_service),
    _current_user: User = Depends(require_role("admin")),
) -> WorkflowStepResponse:
    step = await service.update_step(step_id, data)
    return WorkflowStepResponse.model_validate(step)


@router.delete("/steps/{step_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_step(
    step_id: int,
    service: WorkflowAdminService = Depends(get_admin_service),
    _current_user: User = Depends(require_role("admin")),
) -> None:
    await service.delete_step(step_id)


# ===================================================================
# TRANSITIONS
# ===================================================================


@router.post(
    "/transitions",
    response_model=WorkflowTransitionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_transition(
    data: WorkflowTransitionCreate,
    service: WorkflowAdminService = Depends(get_admin_service),
    _current_user: User = Depends(require_role("admin")),
) -> WorkflowTransitionResponse:
    t = await service.create_transition(data)
    return WorkflowTransitionResponse.model_validate(t)


@router.delete(
    "/transitions/{transition_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_transition(
    transition_id: int,
    service: WorkflowAdminService = Depends(get_admin_service),
    _current_user: User = Depends(require_role("admin")),
) -> None:
    await service.delete_transition(transition_id)


# ===================================================================
# ACTIONS
# ===================================================================


@router.post(
    "/actions",
    response_model=WorkflowActionResponse,
    status_code=status.HTTP_201_CREATED,
)
async def create_action(
    data: WorkflowActionCreate,
    service: WorkflowAdminService = Depends(get_admin_service),
    _current_user: User = Depends(require_role("admin")),
) -> WorkflowActionResponse:
    action = await service.create_action(data)
    return WorkflowActionResponse.model_validate(action)


@router.delete(
    "/actions/{action_id}",
    status_code=status.HTTP_204_NO_CONTENT,
)
async def delete_action(
    action_id: int,
    service: WorkflowAdminService = Depends(get_admin_service),
    _current_user: User = Depends(require_role("admin")),
) -> None:
    await service.delete_action(action_id)


# ===================================================================
# INSTANCES — Execution (Authenticated users)
# ===================================================================


@router.post(
    "/instances",
    response_model=WorkflowInstanceResponse,
    status_code=status.HTTP_201_CREATED,
)
async def start_workflow(
    data: WorkflowInstanceCreate,
    service: WorkflowExecutionService = Depends(get_execution_service),
    current_user: User = Depends(get_current_user),
) -> WorkflowInstanceResponse:
    instance = await service.start_instance(
        workflow_id=data.workflow_id,
        entity_type=data.entity_type,
        entity_id=data.entity_id,
        created_by=current_user.id,
    )
    return WorkflowInstanceResponse.model_validate(instance)


@router.get(
    "/instances/{instance_id}",
    response_model=WorkflowInstanceDetailResponse,
)
async def get_instance(
    instance_id: int,
    service: WorkflowExecutionService = Depends(get_execution_service),
    _current_user: User = Depends(get_current_user),
) -> dict:
    instance = await service.get_instance(instance_id)
    return {
        "id": instance.id,
        "workflow_id": instance.workflow_id,
        "current_step_id": instance.current_step_id,
        "entity_type": instance.entity_type,
        "entity_id": instance.entity_id,
        "status": instance.status,
        "created_by": instance.created_by,
        "created_at": instance.created_at,
        "updated_at": instance.updated_at,
        "workflow": WorkflowResponse.model_validate(instance.workflow)
        if instance.workflow
        else None,
        "history": [
            {
                "id": h.id,
                "instance_id": h.instance_id,
                "from_step_id": h.from_step_id,
                "to_step_id": h.to_step_id,
                "action": h.action,
                "actor_id": h.actor_id,
                "comment": h.comment,
                "created_at": h.created_at,
            }
            for h in (instance.history or [])
        ],
    }


@router.get("/instances", response_model=Page[WorkflowInstanceResponse])
async def list_instances(
    pagination: PaginationParams = Depends(),
    status_filter: Optional[str] = Query(default=None, alias="status"),
    entity_type: Optional[str] = Query(default=None, alias="entity_type"),
    workflow_id: Optional[int] = Query(default=None, alias="workflow_id"),
    service: WorkflowExecutionService = Depends(get_execution_service),
    _current_user: User = Depends(get_current_user),
) -> Page[WorkflowInstanceResponse]:
    items, total = await service.list_instances(
        status=status_filter,
        entity_type=entity_type,
        workflow_id=workflow_id,
        skip=pagination.offset,
        limit=pagination.limit,
    )
    return Page.create(
        items=[WorkflowInstanceResponse.model_validate(i) for i in items],
        total=total,
        page=pagination.page,
        size=pagination.size,
    )


@router.get(
    "/instances/by-entity/{entity_type}/{entity_id}",
    response_model=WorkflowInstanceDetailResponse | None,
)
async def get_instance_by_entity(
    entity_type: str,
    entity_id: int,
    service: WorkflowExecutionService = Depends(get_execution_service),
    _current_user: User = Depends(get_current_user),
) -> dict | None:
    instance = await service.get_instance_by_entity(entity_type, entity_id)
    if instance is None:
        return None
    return {
        "id": instance.id,
        "workflow_id": instance.workflow_id,
        "current_step_id": instance.current_step_id,
        "entity_type": instance.entity_type,
        "entity_id": instance.entity_id,
        "status": instance.status,
        "created_by": instance.created_by,
        "created_at": instance.created_at,
        "updated_at": instance.updated_at,
        "workflow": WorkflowResponse.model_validate(instance.workflow)
        if instance.workflow
        else None,
        "history": [
            {
                "id": h.id,
                "instance_id": h.instance_id,
                "from_step_id": h.from_step_id,
                "to_step_id": h.to_step_id,
                "action": h.action,
                "actor_id": h.actor_id,
                "comment": h.comment,
                "created_at": h.created_at,
            }
            for h in (instance.history or [])
        ],
    }


@router.get(
    "/instances/{instance_id}/transitions",
    response_model=list[AvailableTransition],
)
async def get_available_transitions(
    instance_id: int,
    service: WorkflowExecutionService = Depends(get_execution_service),
    current_user: User = Depends(get_current_user),
) -> list[AvailableTransition]:
    return await service.get_available_transitions(
        instance_id,
        actor_roles=current_user.role_codes,
    )


@router.post(
    "/instances/{instance_id}/actions",
    response_model=WorkflowInstanceResponse,
)
async def perform_action(
    instance_id: int,
    data: WorkflowActionRequest,
    service: WorkflowExecutionService = Depends(get_execution_service),
    current_user: User = Depends(get_current_user),
) -> WorkflowInstanceResponse:
    instance = await service.perform_action(
        instance_id=instance_id,
        action=data.action,
        actor_id=current_user.id,
        comment=data.comment,
        to_step_id=data.to_step_id,
        actor_roles=current_user.role_codes,
    )
    return WorkflowInstanceResponse.model_validate(instance)
