from __future__ import annotations

import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, field_validator


# ---------------------------------------------------------------------------
# Workflow
# ---------------------------------------------------------------------------


class WorkflowCreate(BaseModel):
    name: str
    code: str
    description: Optional[str] = None
    entity_type: str

    @field_validator("name")
    @classmethod
    def name_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Name cannot be empty")
        return v.strip()

    @field_validator("code")
    @classmethod
    def code_not_empty(cls, v: str) -> str:
        if not v.strip():
            raise ValueError("Code cannot be empty")
        return v.strip().upper()


class WorkflowUpdate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    entity_type: Optional[str] = None
    status: Optional[str] = None


class WorkflowResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    code: str
    description: Optional[str] = None
    entity_type: str
    status: str
    created_at: datetime.datetime
    updated_at: datetime.datetime


# ---------------------------------------------------------------------------
# WorkflowStep
# ---------------------------------------------------------------------------


class WorkflowStepCreate(BaseModel):
    workflow_id: int
    name: str
    label: Optional[str] = None
    step_order: int = 0
    is_initial: bool = False
    is_final: bool = False
    assigned_role: Optional[str] = None


class WorkflowStepUpdate(BaseModel):
    name: Optional[str] = None
    label: Optional[str] = None
    step_order: Optional[int] = None
    is_initial: Optional[bool] = None
    is_final: Optional[bool] = None
    assigned_role: Optional[str] = None


class WorkflowStepResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    workflow_id: int
    name: str
    label: Optional[str] = None
    step_order: int
    is_initial: bool
    is_final: bool
    assigned_role: Optional[str] = None
    created_at: datetime.datetime


# ---------------------------------------------------------------------------
# WorkflowTransition
# ---------------------------------------------------------------------------


class WorkflowTransitionCreate(BaseModel):
    workflow_id: int
    from_step_id: int
    to_step_id: int
    label: Optional[str] = None
    required_role: Optional[str] = None


class WorkflowTransitionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    workflow_id: int
    from_step_id: int
    to_step_id: int
    label: Optional[str] = None
    required_role: Optional[str] = None
    created_at: datetime.datetime


# ---------------------------------------------------------------------------
# WorkflowAction
# ---------------------------------------------------------------------------


class WorkflowActionCreate(BaseModel):
    workflow_id: int
    step_id: int
    action_type: str
    action_config: Optional[str] = None


class WorkflowActionResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    workflow_id: int
    step_id: int
    action_type: str
    action_config: Optional[str] = None
    created_at: datetime.datetime


# ---------------------------------------------------------------------------
# WorkflowInstance
# ---------------------------------------------------------------------------


class WorkflowInstanceCreate(BaseModel):
    workflow_id: int
    entity_type: str
    entity_id: int


class WorkflowInstanceResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    workflow_id: int
    current_step_id: int
    entity_type: str
    entity_id: int
    status: str
    created_by: Optional[int] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime


class WorkflowInstanceDetailResponse(BaseModel):
    """Full instance detail including workflow, step, history."""
    model_config = ConfigDict(from_attributes=True)
    id: int
    workflow_id: int
    current_step_id: int
    entity_type: str
    entity_id: int
    status: str
    created_by: Optional[int] = None
    created_at: datetime.datetime
    updated_at: datetime.datetime
    workflow: Optional[WorkflowResponse] = None
    history: list[ApprovalHistoryResponse] = []


# ---------------------------------------------------------------------------
# Workflow Action Request
# ---------------------------------------------------------------------------


class WorkflowActionRequest(BaseModel):
    action: str  # approve | reject | return | submit
    comment: Optional[str] = None
    to_step_id: Optional[int] = None  # for 'return' — which step to return to


# ---------------------------------------------------------------------------
# ApprovalHistory
# ---------------------------------------------------------------------------


class ApprovalHistoryResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    instance_id: int
    from_step_id: Optional[int] = None
    to_step_id: Optional[int] = None
    action: str
    actor_id: Optional[int] = None
    comment: Optional[str] = None
    created_at: datetime.datetime


# ---------------------------------------------------------------------------
# Full workflow definition (for admin)
# ---------------------------------------------------------------------------


class WorkflowDefinition(BaseModel):
    """Complete workflow definition including steps and transitions."""
    workflow: WorkflowResponse
    steps: list[WorkflowStepResponse] = []
    transitions: list[WorkflowTransitionResponse] = []
    actions: list[WorkflowActionResponse] = []


# ---------------------------------------------------------------------------
# Available transition for user
# ---------------------------------------------------------------------------


class AvailableTransition(BaseModel):
    transition_id: int
    from_step_id: int
    to_step_id: int
    label: Optional[str] = None
    to_step_name: str
    to_step_label: Optional[str] = None
    required_role: Optional[str] = None
