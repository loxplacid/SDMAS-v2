from __future__ import annotations

import datetime
from datetime import timezone

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base


# ---------------------------------------------------------------------------
# Workflow — template / definition
# ---------------------------------------------------------------------------


class Workflow(Base):
    """A workflow template (e.g., 'Leave Request', 'Purchase Approval')."""
    __tablename__ = "workflows"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True
    )
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    entity_type: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="Domain entity this workflow applies to (e.g., 'leave_request', 'purchase_order')"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
        onupdate=lambda: datetime.datetime.now(timezone.utc),
    )

    steps: Mapped[list[WorkflowStep]] = relationship(
        "WorkflowStep", back_populates="workflow",
        cascade="all, delete-orphan", lazy="selectin",
        order_by="WorkflowStep.step_order",
    )
    transitions: Mapped[list[WorkflowTransition]] = relationship(
        "WorkflowTransition", back_populates="workflow",
        cascade="all, delete-orphan", lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Workflow id={self.id} name={self.name} code={self.code}>"


# ---------------------------------------------------------------------------
# WorkflowStep — a state/node in the workflow
# ---------------------------------------------------------------------------


class WorkflowStep(Base):
    """A single step (state) in a workflow, e.g. 'Manager Approval'."""
    __tablename__ = "workflow_steps"

    id: Mapped[int] = mapped_column(primary_key=True)
    workflow_id: Mapped[int] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    label: Mapped[str | None] = mapped_column(String(200), nullable=True)
    step_order: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    is_initial: Mapped[bool] = mapped_column(nullable=False, default=False)
    is_final: Mapped[bool] = mapped_column(nullable=False, default=False)
    assigned_role: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
        comment="Role required to act on this step (null = any authenticated user)"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
    )

    workflow: Mapped[Workflow] = relationship(
        "Workflow", back_populates="steps"
    )

    def __repr__(self) -> str:
        return f"<WorkflowStep id={self.id} name={self.name} order={self.step_order}>"


# ---------------------------------------------------------------------------
# WorkflowTransition — allowed edge between two steps
# ---------------------------------------------------------------------------


class WorkflowTransition(Base):
    """An allowed transition from one step to another."""
    __tablename__ = "workflow_transitions"

    id: Mapped[int] = mapped_column(primary_key=True)
    workflow_id: Mapped[int] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True
    )
    from_step_id: Mapped[int] = mapped_column(
        ForeignKey("workflow_steps.id", ondelete="CASCADE"), nullable=False
    )
    to_step_id: Mapped[int] = mapped_column(
        ForeignKey("workflow_steps.id", ondelete="CASCADE"), nullable=False
    )
    label: Mapped[str | None] = mapped_column(String(100), nullable=True)
    required_role: Mapped[str | None] = mapped_column(
        String(50), nullable=True,
        comment="Role required to perform this transition"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
    )

    workflow: Mapped[Workflow] = relationship(
        "Workflow", back_populates="transitions"
    )

    def __repr__(self) -> str:
        return f"<WorkflowTransition id={self.id} {self.from_step_id}->{self.to_step_id}>"


# ---------------------------------------------------------------------------
# WorkflowAction — side effect executed on transition
# ---------------------------------------------------------------------------


class WorkflowAction(Base):
    """A side effect executed when a step is reached (e.g., send email, webhook)."""
    __tablename__ = "workflow_actions"

    id: Mapped[int] = mapped_column(primary_key=True)
    workflow_id: Mapped[int] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True
    )
    step_id: Mapped[int] = mapped_column(
        ForeignKey("workflow_steps.id", ondelete="CASCADE"), nullable=False,
        comment="Execute this action when this step is reached"
    )
    action_type: Mapped[str] = mapped_column(
        String(50), nullable=False,
        comment="send_email | notify_user | webhook | create_record | custom"
    )
    action_config: Mapped[str | None] = mapped_column(
        Text, nullable=True,
        comment="JSON configuration for the action (template, recipients, URL, etc.)"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<WorkflowAction id={self.id} type={self.action_type}>"


# ---------------------------------------------------------------------------
# WorkflowInstance — a running instance of a workflow
# ---------------------------------------------------------------------------


class WorkflowInstance(Base):
    """A running workflow instance tied to a specific entity record."""
    __tablename__ = "workflow_instances"

    id: Mapped[int] = mapped_column(primary_key=True)
    workflow_id: Mapped[int] = mapped_column(
        ForeignKey("workflows.id", ondelete="CASCADE"), nullable=False, index=True
    )
    current_step_id: Mapped[int] = mapped_column(
        ForeignKey("workflow_steps.id", ondelete="CASCADE"), nullable=False
    )
    entity_type: Mapped[str] = mapped_column(
        String(100), nullable=False,
        comment="Polymorphic entity type (e.g., 'leave_request')"
    )
    entity_id: Mapped[int] = mapped_column(
        Integer, nullable=False,
        comment="ID of the entity record this instance belongs to"
    )
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )
    created_by: Mapped[int] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
        onupdate=lambda: datetime.datetime.now(timezone.utc),
    )

    workflow: Mapped[Workflow] = relationship("Workflow", lazy="selectin")
    current_step: Mapped[WorkflowStep] = relationship("WorkflowStep", lazy="selectin")
    history: Mapped[list[ApprovalHistory]] = relationship(
        "ApprovalHistory", back_populates="instance",
        cascade="all, delete-orphan", lazy="selectin",
        order_by="ApprovalHistory.created_at",
    )

    def __repr__(self) -> str:
        return (
            f"<WorkflowInstance id={self.id} "
            f"workflow={self.workflow_id} status={self.status}>"
        )


# ---------------------------------------------------------------------------
# ApprovalHistory — audit trail of every transition
# ---------------------------------------------------------------------------


class ApprovalHistory(Base):
    """Audit trail recording each action taken on a workflow instance."""
    __tablename__ = "approval_history"

    id: Mapped[int] = mapped_column(primary_key=True)
    instance_id: Mapped[int] = mapped_column(
        ForeignKey("workflow_instances.id", ondelete="CASCADE"),
        nullable=False, index=True
    )
    from_step_id: Mapped[int | None] = mapped_column(
        ForeignKey("workflow_steps.id", ondelete="SET NULL"), nullable=True
    )
    to_step_id: Mapped[int | None] = mapped_column(
        ForeignKey("workflow_steps.id", ondelete="SET NULL"), nullable=True
    )
    action: Mapped[str] = mapped_column(
        String(30), nullable=False,
        comment="approve | reject | return | submit | cancel"
    )
    actor_id: Mapped[int | None] = mapped_column(
        ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )
    comment: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
    )

    instance: Mapped[WorkflowInstance] = relationship(
        "WorkflowInstance", back_populates="history"
    )

    def __repr__(self) -> str:
        return (
            f"<ApprovalHistory id={self.id} "
            f"action={self.action} instance={self.instance_id}>"
        )
