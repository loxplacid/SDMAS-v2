from __future__ import annotations

import datetime
import logging
from datetime import timezone

from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.domains.events import publish_event
from app.domains.events.outbox import publish_durable
from app.domains.events.events import (
    AcademicYearRolloverCompletedEvent,
    AcademicYearRolloverFailedEvent,
    AcademicYearRolloverStartedEvent,
)
from app.domains.academic.models import AcademicYear, Class, Section, Enrollment
from app.domains.academic.repository import (
    AcademicYearRepository,
    ClassRepository,
    SectionRepository,
    EnrollmentRepository,
)
from app.domains.student.repository import StudentRepository
from app.multi_tenant.models import TenantContext

logger = logging.getLogger(__name__)


class RolloverService:
    def __init__(
        self,
        session: AsyncSession,
        tenant: Optional[TenantContext] = None,
    ) -> None:
        self.session = session
        self.tenant = tenant
        self.year_repo = AcademicYearRepository(session, tenant)
        self.class_repo = ClassRepository(session, tenant)
        self.section_repo = SectionRepository(session, tenant)
        self.enrollment_repo = EnrollmentRepository(session, tenant)
        self.student_repo = StudentRepository(session, tenant)

    async def preview_rollover(
        self,
        from_year_id: int,
        to_year_name: str,
        to_start_date: str,
        to_end_date: str,
    ) -> dict:
        from_year = await self.year_repo.get_by_id(from_year_id)
        if from_year is None:
            raise NotFoundError(f"Academic year {from_year_id} not found")

        existing = await self.year_repo.get_by_name(to_year_name)
        if existing is not None:
            raise ConflictError(
                f"Academic year '{to_year_name}' already exists"
            )

        classes, total_classes = await self.class_repo.list(
            year_id=from_year_id, limit=10000
        )

        sections_result = await self.session.execute(
            self.section_repo.scoped_query(Section).where(
                Section.class_id.in_([c.id for c in classes])
            )
        )
        sections = sections_result.scalars().all()

        enrollments, _ = await self.enrollment_repo.list(
            academic_year_id=from_year_id, limit=10000
        )

        class_items = [
            {"type": "class", "name": c.name, "source_id": c.id}
            for c in classes
        ]
        section_items = [
            {"type": "section", "name": s.name, "source_id": s.id}
            for s in sections
        ]

        return {
            "from_year_id": from_year_id,
            "from_year_name": from_year.name,
            "to_year_name": to_year_name,
            "classes": class_items,
            "sections": section_items,
            "enrolled_students": len(enrollments),
            "total_items": len(class_items) + len(section_items) + len(enrollments),
        }

    async def execute_rollover(
        self,
        from_year_id: int,
        to_year_name: str,
        to_start_date: str,
        to_end_date: str,
    ) -> dict:
        from_year = await self.year_repo.get_by_id(from_year_id)
        if from_year is None:
            raise NotFoundError(f"Academic year {from_year_id} not found")

        existing = await self.year_repo.get_by_name(to_year_name)
        if existing is not None:
            raise ConflictError(
                f"Academic year '{to_year_name}' already exists"
            )

        if not to_year_name.strip():
            raise ValidationError("Academic year name is required")
        if not to_start_date.strip():
            raise ValidationError("Start date is required")
        if not to_end_date.strip():
            raise ValidationError("End date is required")

        # Domain event: rollover started (non-fatal)
        try:
            await publish_event(
                AcademicYearRolloverStartedEvent(
                    previous_year_id=from_year_id,
                    new_year_name=to_year_name,
                ),
                session=self.session,
            )
        except Exception:
            logger.warning("Failed to publish rollover started event (non-fatal)", exc_info=True)

        try:
            return await self._execute_rollover_engine(
                from_year_id=from_year_id,
                to_year_name=to_year_name,
                to_start_date=to_start_date,
                to_end_date=to_end_date,
            )
        except Exception as exc:
            try:
                await publish_durable(
                    AcademicYearRolloverFailedEvent(
                        previous_year_id=from_year_id,
                        new_year_name=to_year_name,
                        error=str(exc)[:500],
                    ),
                    session=self.session,
                    event_id=f"rollover_failed:{from_year_id}:{to_year_name}",
                )
            except Exception:
                logger.warning("Failed to publish rollover failed event (non-fatal)", exc_info=True)
            raise

    async def _execute_rollover_engine(
        self,
        from_year_id: int,
        to_year_name: str,
        to_start_date: str,
        to_end_date: str,
    ) -> dict:
        now = datetime.datetime.now(timezone.utc)

        new_year = AcademicYear(
            name=to_year_name,
            start_date=datetime.date.fromisoformat(to_start_date),
            end_date=datetime.date.fromisoformat(to_end_date),
            status="active",
            created_at=now,
            updated_at=now,
        )
        new_year = await self.year_repo.create(new_year)

        classes, _ = await self.class_repo.list(
            year_id=from_year_id, limit=10000
        )

        class_id_map: dict[int, int] = {}
        classes_created = 0
        for cls in classes:
            new_class = Class(
                name=cls.name,
                academic_year_id=new_year.id,
                status="active",
                created_at=now,
                updated_at=now,
            )
            self.session.add(new_class)
            await self.session.flush()
            class_id_map[cls.id] = new_class.id
            classes_created += 1

        sections_created = 0
        section_id_map: dict[int, int] = {}
        for cls in classes:
            sec_result = await self.session.execute(
                self.section_repo.scoped_query(Section).where(
                    Section.class_id == cls.id
                )
            )
            sections = sec_result.scalars().all()
            for sec in sections:
                new_section = Section(
                    name=sec.name,
                    class_id=class_id_map[cls.id],
                    status="active",
                    created_at=now,
                    updated_at=now,
                )
                self.session.add(new_section)
                await self.session.flush()
                section_id_map[sec.id] = new_section.id
                sections_created += 1

        enrollments, _ = await self.enrollment_repo.list(
            academic_year_id=from_year_id, limit=10000
        )

        enrollments_created = 0
        for e in enrollments:
            try:
                student = await self.student_repo.get_by_id(e.student_id)
            except NotFoundError:
                continue

            new_class_id = class_id_map.get(e.class_id) if e.class_id else None
            new_section_id = section_id_map.get(e.section_id) if e.section_id else None

            new_enrollment = Enrollment(
                student_id=student.id,
                academic_year_id=new_year.id,
                class_id=new_class_id,
                section_id=new_section_id,
                status="active",
                enrolled_at=now,
                created_at=now,
                updated_at=now,
            )
            self.session.add(new_enrollment)
            enrollments_created += 1

        await self.session.flush()

        # Durable event: rollover completed -> notification + audit (worker
        # delivers it, so it survives an API crash mid-rollover).
        try:
            await publish_durable(
                AcademicYearRolloverCompletedEvent(
                    previous_year_id=from_year_id,
                    new_year_id=new_year.id,
                    new_year_name=new_year.name,
                    students_rolled=enrollments_created,
                    classes_migrated=classes_created,
                ),
                session=self.session,
                event_id=f"rollover_completed:{from_year_id}:{new_year.id}",
            )
        except Exception:
            logger.warning("Failed to publish rollover completed event (non-fatal)", exc_info=True)

        return {
            "success": True,
            "academic_year_id": new_year.id,
            "academic_year_name": new_year.name,
            "classes_created": classes_created,
            "sections_created": sections_created,
            "enrollments_created": enrollments_created,
            "message": f"Rollover to '{to_year_name}' completed: {classes_created} classes, {sections_created} sections, {enrollments_created} enrollments",
        }