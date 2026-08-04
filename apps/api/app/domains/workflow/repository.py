from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.core.exceptions import NotFoundError
from app.domains.workflow.models import (
    Workflow,
    WorkflowStep,
    WorkflowTransition,
    WorkflowAction,
    WorkflowInstance,
    ApprovalHistory,
)
from app.multi_tenant.models import TenantContext
from app.multi_tenant.repository import TenantScopedRepository


class _WorkflowRepo(TenantScopedRepository):
    """Base for workflow repositories.

    ``Workflow`` / steps / transitions / actions are platform data and are
    never filtered; ``WorkflowInstance`` (campus-tagged) and
    ``ApprovalHistory`` (parent-scoped) ARE filtered — automatically, via
    the tenancy registry, at query construction time.
    """

    def __init__(self, session: AsyncSession, tenant: Optional[TenantContext] = None) -> None:
        super().__init__(session, tenant)


# ---------------------------------------------------------------------------
# WorkflowRepository
# ---------------------------------------------------------------------------


class WorkflowRepository(_WorkflowRepo):
    def __init__(self, session: AsyncSession, tenant: Optional[TenantContext] = None) -> None:
        super().__init__(session, tenant)

    async def get_by_id(self, workflow_id: int) -> Workflow:
        result = await self.session.execute(
            self.scoped_query(Workflow)
            .options(selectinload(Workflow.steps), selectinload(Workflow.transitions))
            .where(Workflow.id == workflow_id)
        )
        wf = result.scalar_one_or_none()
        if wf is None:
            raise NotFoundError(f"Workflow with id {workflow_id} not found")
        return wf

    async def get_by_code(self, code: str) -> Workflow | None:
        result = await self.session.execute(
            self.scoped_query(Workflow)
            .options(selectinload(Workflow.steps), selectinload(Workflow.transitions))
            .where(Workflow.code == code)
        )
        return result.scalar_one_or_none()

    async def get_by_entity_type(self, entity_type: str) -> list[Workflow]:
        result = await self.session.execute(
            self.scoped_query(Workflow)
            .where(Workflow.entity_type == entity_type, Workflow.status == "active")
            .order_by(Workflow.name)
        )
        return list(result.scalars().all())

    async def list(
        self,
        status: Optional[str] = None,
        entity_type: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[Workflow], int]:
        query = self.scoped_query(Workflow)
        count_query = self.scoped_count(Workflow)

        if status is not None:
            query = query.where(Workflow.status == status)
            count_query = count_query.where(Workflow.status == status)
        if entity_type is not None:
            query = query.where(Workflow.entity_type == entity_type)
            count_query = count_query.where(Workflow.entity_type == entity_type)

        query = query.offset(skip).limit(limit).order_by(Workflow.name)

        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        result = await self.session.execute(query)
        items = result.scalars().all()

        return items, total

    async def create(self, workflow: Workflow) -> Workflow:
        self.session.add(workflow)
        await self.session.flush()
        return workflow

    async def update(self, workflow: Workflow) -> Workflow:
        await self.session.flush()
        return workflow

    async def delete(self, workflow: Workflow) -> None:
        await self.session.delete(workflow)


# ---------------------------------------------------------------------------
# WorkflowStepRepository
# ---------------------------------------------------------------------------


class WorkflowStepRepository(_WorkflowRepo):
    def __init__(self, session: AsyncSession, tenant: Optional[TenantContext] = None) -> None:
        super().__init__(session, tenant)

    async def get_by_id(self, step_id: int) -> WorkflowStep:
        result = await self.session.execute(
            self.scoped_query(WorkflowStep).where(WorkflowStep.id == step_id)
        )
        step = result.scalar_one_or_none()
        if step is None:
            raise NotFoundError(f"WorkflowStep with id {step_id} not found")
        return step

    async def get_initial_step(self, workflow_id: int) -> WorkflowStep | None:
        result = await self.session.execute(
            self.scoped_query(WorkflowStep).where(
                WorkflowStep.workflow_id == workflow_id,
                WorkflowStep.is_initial == True,
            )
        )
        return result.scalar_one_or_none()

    async def list_by_workflow(self, workflow_id: int) -> Sequence[WorkflowStep]:
        result = await self.session.execute(
            self.scoped_query(WorkflowStep)
            .where(WorkflowStep.workflow_id == workflow_id)
            .order_by(WorkflowStep.step_order)
        )
        return result.scalars().all()

    async def create(self, step: WorkflowStep) -> WorkflowStep:
        self.session.add(step)
        await self.session.flush()
        return step

    async def update(self, step: WorkflowStep) -> WorkflowStep:
        await self.session.flush()
        return step

    async def delete(self, step: WorkflowStep) -> None:
        await self.session.delete(step)


# ---------------------------------------------------------------------------
# WorkflowTransitionRepository
# ---------------------------------------------------------------------------


class WorkflowTransitionRepository(_WorkflowRepo):
    def __init__(self, session: AsyncSession, tenant: Optional[TenantContext] = None) -> None:
        super().__init__(session, tenant)

    async def get_by_id(self, transition_id: int) -> WorkflowTransition:
        result = await self.session.execute(
            self.scoped_query(WorkflowTransition).where(
                WorkflowTransition.id == transition_id
            )
        )
        t = result.scalar_one_or_none()
        if t is None:
            raise NotFoundError(
                f"WorkflowTransition with id {transition_id} not found"
            )
        return t

    async def get_available_from_step(
        self, step_id: int
    ) -> Sequence[WorkflowTransition]:
        result = await self.session.execute(
            self.scoped_query(WorkflowTransition).where(
                WorkflowTransition.from_step_id == step_id
            )
        )
        return result.scalars().all()

    async def list_by_workflow(
        self, workflow_id: int
    ) -> Sequence[WorkflowTransition]:
        result = await self.session.execute(
            self.scoped_query(WorkflowTransition)
            .where(WorkflowTransition.workflow_id == workflow_id)
        )
        return result.scalars().all()

    async def create(
        self, transition: WorkflowTransition
    ) -> WorkflowTransition:
        self.session.add(transition)
        await self.session.flush()
        return transition

    async def delete(self, transition: WorkflowTransition) -> None:
        await self.session.delete(transition)


# ---------------------------------------------------------------------------
# WorkflowActionRepository
# ---------------------------------------------------------------------------


class WorkflowActionRepository(_WorkflowRepo):
    def __init__(self, session: AsyncSession, tenant: Optional[TenantContext] = None) -> None:
        super().__init__(session, tenant)

    async def get_by_id(self, action_id: int) -> WorkflowAction:
        result = await self.session.execute(
            self.scoped_query(WorkflowAction).where(WorkflowAction.id == action_id)
        )
        action = result.scalar_one_or_none()
        if action is None:
            raise NotFoundError(
                f"WorkflowAction with id {action_id} not found"
            )
        return action

    async def get_by_step(self, step_id: int) -> Sequence[WorkflowAction]:
        result = await self.session.execute(
            self.scoped_query(WorkflowAction).where(WorkflowAction.step_id == step_id)
        )
        return result.scalars().all()

    async def list_by_workflow(
        self, workflow_id: int
    ) -> Sequence[WorkflowAction]:
        result = await self.session.execute(
            self.scoped_query(WorkflowAction).where(
                WorkflowAction.workflow_id == workflow_id
            )
        )
        return result.scalars().all()

    async def create(self, action: WorkflowAction) -> WorkflowAction:
        self.session.add(action)
        await self.session.flush()
        return action

    async def delete(self, action: WorkflowAction) -> None:
        await self.session.delete(action)


# ---------------------------------------------------------------------------
# WorkflowInstanceRepository
# ---------------------------------------------------------------------------


class WorkflowInstanceRepository(_WorkflowRepo):
    def __init__(self, session: AsyncSession, tenant: Optional[TenantContext] = None) -> None:
        super().__init__(session, tenant)

    async def get_by_id(self, instance_id: int) -> WorkflowInstance:
        result = await self.session.execute(
            self.scoped_query(WorkflowInstance)
            .options(
                selectinload(WorkflowInstance.workflow),
                selectinload(WorkflowInstance.current_step),
                selectinload(WorkflowInstance.history),
            )
            .where(WorkflowInstance.id == instance_id)
        )
        instance = result.scalar_one_or_none()
        if instance is None:
            raise NotFoundError(
                f"WorkflowInstance with id {instance_id} not found"
            )
        return instance

    async def get_by_entity(
        self, entity_type: str, entity_id: int
    ) -> WorkflowInstance | None:
        result = await self.session.execute(
            self.scoped_query(WorkflowInstance)
            .options(
                selectinload(WorkflowInstance.workflow),
                selectinload(WorkflowInstance.current_step),
                selectinload(WorkflowInstance.history),
            )
            .where(
                WorkflowInstance.entity_type == entity_type,
                WorkflowInstance.entity_id == entity_id,
                WorkflowInstance.status == "active",
            )
        )
        return result.scalar_one_or_none()

    async def list(
        self,
        status: Optional[str] = None,
        entity_type: Optional[str] = None,
        created_by: Optional[int] = None,
        workflow_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[WorkflowInstance], int]:
        query = self.scoped_query(WorkflowInstance)
        count_query = self.scoped_count(WorkflowInstance)

        if status is not None:
            query = query.where(WorkflowInstance.status == status)
            count_query = count_query.where(WorkflowInstance.status == status)
        if entity_type is not None:
            query = query.where(WorkflowInstance.entity_type == entity_type)
            count_query = count_query.where(
                WorkflowInstance.entity_type == entity_type
            )
        if created_by is not None:
            query = query.where(WorkflowInstance.created_by == created_by)
            count_query = count_query.where(
                WorkflowInstance.created_by == created_by
            )
        if workflow_id is not None:
            query = query.where(WorkflowInstance.workflow_id == workflow_id)
            count_query = count_query.where(
                WorkflowInstance.workflow_id == workflow_id
            )

        query = query.offset(skip).limit(limit).order_by(
            WorkflowInstance.created_at
        )

        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        result = await self.session.execute(query)
        items = result.scalars().all()

        return items, total

    async def create(self, instance: WorkflowInstance) -> WorkflowInstance:
        self.session.add(instance)
        await self.session.flush()
        return instance

    async def update(
        self, instance: WorkflowInstance
    ) -> WorkflowInstance:
        await self.session.flush()
        return instance


# ---------------------------------------------------------------------------
# ApprovalHistoryRepository
# ---------------------------------------------------------------------------


class ApprovalHistoryRepository(_WorkflowRepo):
    def __init__(self, session: AsyncSession, tenant: Optional[TenantContext] = None) -> None:
        super().__init__(session, tenant)

    async def list_by_instance(
        self, instance_id: int
    ) -> Sequence[ApprovalHistory]:
        result = await self.session.execute(
            self.scoped_query(ApprovalHistory)
            .where(ApprovalHistory.instance_id == instance_id)
            .order_by(ApprovalHistory.created_at)
        )
        return result.scalars().all()

    async def create(self, entry: ApprovalHistory) -> ApprovalHistory:
        self.session.add(entry)
        await self.session.flush()
        return entry
