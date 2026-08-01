from __future__ import annotations

import logging
from typing import Any, Optional, Sequence

from sqlalchemy.exc import IntegrityError

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.domains.audit.constants import CREATE, DELETE, STUDENT, UPDATE
from app.domains.audit.service import AuditService
from app.domains.audit.utils import build_diff, safe_details
from app.domains.events import publish_event
from app.domains.events.context import get_actor_user_id
from app.domains.events.events import (
    StudentCreatedEvent,
    StudentStatusChangedEvent,
    StudentUpdatedEvent,
)
from app.domains.student.models import Student
from app.domains.student.repository import StudentRepository
from app.domains.student.schemas import (
    EMAIL_REGEX,
    VALID_STATUSES,
    StudentCreate,
    StudentUpdate,
)

logger = logging.getLogger(__name__)


class StudentService:
    def __init__(self, repository: StudentRepository) -> None:
        self.repository = repository

    async def _audit(
        self,
        action: str,
        resource_id: str | None,
        user_id: int | None = None,
        username: str | None = None,
        details: dict[str, Any] | None = None,
    ) -> None:
        """Record an audit entry in fire-and-forget fashion.

        Falls back to the actor stamped on the event context (set by the
        tenant middleware for the current request) so audit entries carry
        the acting user even when the caller does not pass one.
        """
        try:
            svc = AuditService(self.repository.session)
            await svc.record(
                user_id=user_id if user_id is not None else get_actor_user_id(),
                username=username,
                action=action,
                resource_type=STUDENT,
                resource_id=resource_id,
                details=safe_details(details),
            )
            await self.repository.session.flush()
        except Exception:
            logger.warning("Failed to write audit entry (non-fatal)", exc_info=True)

    async def _publish_status_changed(
        self, student_id: int, from_status: str, to_status: str
    ) -> None:
        """Publish a StudentStatusChangedEvent (non-fatal).

        The synchronous UPDATE audit (written by the caller) is the source of
        truth; this event is published for future subscribers (catalog
        completeness) — no handler is registered for it in the initial
        handler set.
        """
        try:
            await publish_event(
                StudentStatusChangedEvent(
                    student_id=student_id,
                    from_status=from_status,
                    to_status=to_status,
                ),
                session=self.repository.session,
            )
        except Exception:
            logger.warning("Failed to publish StudentStatusChangedEvent (non-fatal)", exc_info=True)

    async def create_student(self, data: StudentCreate) -> Student:
        existing = await self.repository.get_by_student_number(data.student_number)
        if existing is not None:
            raise ConflictError(
                f"Student with number {data.student_number} already exists"
            )

        student = Student(
            first_name=data.first_name,
            last_name=data.last_name,
            student_number=data.student_number,
            email=data.email,
            date_of_birth=data.date_of_birth,
            status="active",
        )
        try:
            created = await self.repository.create(student)
        except IntegrityError:
            raise ConflictError(
                f"Student with number {data.student_number} already exists"
            )

        await self._audit(
            action=CREATE,
            resource_id=str(created.id),
            details={
                "student_number": created.student_number,
                "first_name": created.first_name,
                "last_name": created.last_name,
            },
        )

        # Domain event: StudentCreated -> audit event (non-fatal)
        try:
            await publish_event(
                StudentCreatedEvent(
                    student_id=created.id,
                    student_number=created.student_number,
                    full_name=f"{created.first_name} {created.last_name}".strip(),
                    email=created.email,
                ),
                session=self.repository.session,
            )
        except Exception:
            logger.warning("Failed to publish StudentCreatedEvent (non-fatal)", exc_info=True)

        return created

    async def get_student(self, student_id: int) -> Student:
        return await self.repository.get_by_id(student_id)

    async def find_by_student_number(self, student_number: str) -> Student:
        student = await self.repository.get_by_student_number(student_number)
        if student is None:
            raise NotFoundError(
                f"Student with number {student_number} not found"
            )
        return student

    async def update_student(
        self, student_id: int, data: StudentUpdate
    ) -> Student:
        student = await self.repository.get_by_id(student_id)
        # Snapshot column values before mutating so build_diff can compare correctly
        # (avoids SQLAlchemy deep-copy issues with lazy-loaded relationships)
        before_snapshot = {
            c.name: getattr(student, c.name)
            for c in student.__table__.columns
        }

        if data.first_name is not None:
            student.first_name = data.first_name
        if data.last_name is not None:
            student.last_name = data.last_name
        if data.email is not None:
            student.email = data.email
        if data.status is not None:
            student.status = data.status
        if data.date_of_birth is not None:
            student.date_of_birth = data.date_of_birth

        try:
            after = await self.repository.update(student)
        except IntegrityError:
            raise ConflictError("Duplicate student number")

        diff = build_diff(before_snapshot, after)
        if diff:
            await self._audit(
                action=UPDATE,
                resource_id=str(student_id),
                details=diff,
            )
            # Domain event: StudentUpdated.  The synchronous audit above is
            # the source of truth; this event is published for future
            # subscribers (catalog completeness) — no handler is registered
            # for it in the initial handler set. (non-fatal)
            try:
                await publish_event(
                    StudentUpdatedEvent(
                        student_id=student_id,
                        changes=diff,
                    ),
                    session=self.repository.session,
                )
            except Exception:
                logger.warning("Failed to publish StudentUpdatedEvent (non-fatal)", exc_info=True)
        return after

    async def delete_student(self, student_id: int) -> None:
        student = await self.repository.get_by_id(student_id)
        snapshot = {
            "student_number": student.student_number,
            "first_name": student.first_name,
            "last_name": student.last_name,
            "status": student.status,
        }
        await self.repository.delete(student)

        await self._audit(
            action=DELETE,
            resource_id=str(student_id),
            details=snapshot,
        )

    async def deactivate_student(self, student_id: int) -> Student:
        student = await self.repository.get_by_id(student_id)
        if student.status == "inactive":
            raise ConflictError(
                f"Student with id {student_id} is already inactive"
            )
        student.status = "inactive"
        updated = await self.repository.update(student)

        await self._audit(
            action=UPDATE,
            resource_id=str(student_id),
            details={"before": {"status": "active"}, "after": {"status": "inactive"}},
        )
        await self._publish_status_changed(student_id, "active", "inactive")
        return updated

    async def reactivate_student(self, student_id: int) -> Student:
        student = await self.repository.get_by_id(student_id)
        if student.status == "active":
            raise ConflictError(
                f"Student with id {student_id} is already active"
            )
        student.status = "active"
        updated = await self.repository.update(student)

        await self._audit(
            action=UPDATE,
            resource_id=str(student_id),
            details={"before": {"status": "inactive"}, "after": {"status": "active"}},
        )
        await self._publish_status_changed(student_id, "inactive", "active")
        return updated

    async def list_students(
        self,
        status: Optional[str] = None,
        campus_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[Student], int]:
        if status is not None and status not in VALID_STATUSES:
            raise ValidationError(f"Invalid status filter: {status}")
        return await self.repository.list(status=status, campus_id=campus_id, skip=skip, limit=limit)

    async def search_students(
        self,
        query: str,
        campus_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[Student], int]:
        if not query or not query.strip():
            raise ValidationError("Search query is required")
        return await self.repository.search(query.strip().lower(), skip=skip, limit=limit)