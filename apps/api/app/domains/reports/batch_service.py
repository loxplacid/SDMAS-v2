from __future__ import annotations

import datetime
from datetime import timezone
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.domains.academic.models import Enrollment
from app.domains.academic.repository import (
    AcademicYearRepository,
    ClassRepository,
    EnrollmentRepository,
    SectionRepository,
)
from app.domains.fees.models import FeeDue
from app.domains.fees.repository import (
    FeeDueRepository,
    FeeStructureRepository,
)
from app.domains.student.repository import StudentRepository


class BatchService:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session
        self.student_repo = StudentRepository(session)
        self.year_repo = AcademicYearRepository(session)
        self.class_repo = ClassRepository(session)
        self.section_repo = SectionRepository(session)
        self.enrollment_repo = EnrollmentRepository(session)
        self.fee_due_repo = FeeDueRepository(session)
        self.structure_repo = FeeStructureRepository(session)

    async def batch_enroll(
        self,
        academic_year_id: int,
        enrollments_data: list[dict],
    ) -> dict:
        year = await self.year_repo.get_by_id(academic_year_id)
        if year.status != "active":
            raise ValidationError(
                "Cannot enroll in an inactive academic year"
            )

        now = datetime.datetime.now(timezone.utc)
        results: list[dict] = []
        succeeded = 0
        failed = 0

        for item in enrollments_data:
            student_id = item.get("student_id")
            class_id = item.get("class_id")
            section_id = item.get("section_id")

            try:
                if not student_id:
                    raise ValidationError("student_id is required")

                student = await self.student_repo.get_by_id(int(student_id))
                if student.status != "active":
                    raise ValidationError(
                        f"Student {student_id} is not active"
                    )

                if not class_id:
                    raise ValidationError("class_id is required")
                cls = await self.class_repo.get_by_id(int(class_id))
                if cls.status != "active":
                    raise ValidationError(
                        f"Class {class_id} is not active"
                    )

                if section_id is not None:
                    section = await self.section_repo.get_by_id(int(section_id))
                    if section.class_id != int(class_id):
                        raise ValidationError(
                            f"Section {section_id} does not belong to class {class_id}"
                        )

                existing = await self.enrollment_repo.get_by_student_and_year(
                    student_id, academic_year_id
                )
                if existing is not None:
                    raise ConflictError(
                        f"Student {student_id} is already enrolled in academic year {academic_year_id}"
                    )

                enrollment = Enrollment(
                    student_id=student_id,
                    academic_year_id=academic_year_id,
                    class_id=class_id,
                    section_id=section_id,
                    status="active",
                    enrolled_at=now,
                    created_at=now,
                    updated_at=now,
                )
                enrollment = await self.enrollment_repo.create(enrollment)
                succeeded += 1
                results.append(
                    {
                        "student_id": student_id,
                        "success": True,
                        "enrollment_id": enrollment.id,
                        "error": None,
                    }
                )
            except (NotFoundError, ValidationError, ConflictError) as e:
                failed += 1
                results.append(
                    {
                        "student_id": student_id,
                        "success": False,
                        "enrollment_id": None,
                        "error": str(e),
                    }
                )

        return {
            "academic_year_id": academic_year_id,
            "total": len(enrollments_data),
            "succeeded": succeeded,
            "failed": failed,
            "results": results,
        }

    async def batch_create_fee_dues(
        self,
        academic_year_id: int,
        student_ids: list[int],
    ) -> dict:
        year = await self.year_repo.get_by_id(academic_year_id)
        if year.status != "active":
            raise ValidationError(
                "Cannot create fee dues for an inactive academic year"
            )

        now = datetime.datetime.now(timezone.utc)
        results: list[dict] = []
        succeeded = 0
        failed = 0

        for student_id in student_ids:
            try:
                student = await self.student_repo.get_by_id(student_id)
                if student.status != "active":
                    raise ValidationError(
                        f"Student {student_id} is not active"
                    )

                enrollment = await self.enrollment_repo.get_by_student_and_year(
                    student_id, academic_year_id
                )
                if enrollment is None:
                    raise ValidationError(
                        f"Student {student_id} is not enrolled in academic year {academic_year_id}"
                    )

                structures, _ = await self.structure_repo.list(
                    academic_year_id=academic_year_id,
                    class_id=enrollment.class_id,
                    status="active",
                    limit=10000,
                )

                if not structures:
                    raise ValidationError(
                        f"No active fee structures found for student {student_id}"
                    )

                dues_created = 0
                for fs in structures:
                    existing = await self.fee_due_repo.get_by_student_and_structure(
                        student_id, fs.id
                    )
                    if existing is not None:
                        continue

                    due = FeeDue(
                        student_id=student_id,
                        academic_year_id=academic_year_id,
                        fee_structure_id=fs.id,
                        original_amount=fs.amount,
                        amount_paid=0,
                        due_date=None,
                        status="unpaid",
                        created_at=now,
                        updated_at=now,
                    )
                    await self.fee_due_repo.create(due)
                    dues_created += 1

                succeeded += 1
                results.append(
                    {
                        "student_id": student_id,
                        "success": True,
                        "dues_created": dues_created,
                        "error": None,
                    }
                )
            except (NotFoundError, ValidationError) as e:
                failed += 1
                results.append(
                    {
                        "student_id": student_id,
                        "success": False,
                        "dues_created": 0,
                        "error": str(e),
                    }
                )

        return {
            "academic_year_id": academic_year_id,
            "total": len(student_ids),
            "succeeded": succeeded,
            "failed": failed,
            "results": results,
        }