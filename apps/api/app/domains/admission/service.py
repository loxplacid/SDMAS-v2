from __future__ import annotations

import datetime
import logging
from datetime import timezone
from typing import Optional, Sequence

from app.core.exceptions import ConflictError, NotFoundError, ValidationError
from app.domains.events import publish_event
from app.domains.events.events import (
    AdmissionApprovedEvent,
    AdmissionRejectedEvent,
    AdmissionSubmittedEvent,
)
from app.domains.admission.models import (
    ADMISSION_STATUS_APPLICATION_SUBMITTED,
    ADMISSION_STATUS_ENROLLED,
    ADMISSION_STATUS_FLOW,
    ADMISSION_STATUS_INQUIRY,
    ADMISSION_STATUS_REJECTED,
    ADMISSION_STATUS_STUDENT_CREATED,
    ADMISSION_VALID_STATUSES,
    VALID_ALLOCATION_STATUSES,
    VALID_DOCUMENT_VERIFICATION_STATUSES,
    VALID_INTERVIEW_STATUSES,
    VALID_MERIT_STATUSES,
    AdmissionApplication,
    AdmissionDocument,
    AdmissionInterview,
    AdmissionMeritEntry,
    AdmissionSeatAllocation,
    DOCUMENT_VERIFICATION_PENDING,
    INTERVIEW_STATUS_SCHEDULED,
    MERIT_STATUS_ACTIVE,
    ALLOCATION_STATUS_ALLOCATED,
)
from app.domains.admission.repository import (
    AdmissionApplicationRepository,
    AdmissionDocumentRepository,
    AdmissionInterviewRepository,
    AdmissionMeritEntryRepository,
    AdmissionSeatAllocationRepository,
)

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# AdmissionApplicationService
# ---------------------------------------------------------------------------


class AdmissionApplicationService:
    def __init__(self, repo: AdmissionApplicationRepository) -> None:
        self.repo = repo

    async def create(self, data) -> AdmissionApplication:
        application = AdmissionApplication(
            campus_id=data.campus_id,
            academic_year_id=data.academic_year_id,
            program_id=data.program_id,
            branch_id=data.branch_id,
            semester_id=data.semester_id,
            applicant_name=data.applicant_name.strip(),
            date_of_birth=data.date_of_birth,
            email=data.email,
            phone=data.phone,
            address=data.address,
            source=data.source or "website",
            previous_education=data.previous_education,
            entrance_score=data.entrance_score,
            status=ADMISSION_STATUS_INQUIRY,
        )
        return await self.repo.create(application)

    async def get(self, application_id: int) -> AdmissionApplication:
        return await self.repo.get_by_id(application_id)

    async def update(
        self, application_id: int, data
    ) -> AdmissionApplication:
        application = await self.repo.get_by_id(application_id)
        if application.status == ADMISSION_STATUS_REJECTED:
            raise ValidationError(
                "Cannot update a rejected application"
            )

        if data.applicant_name is not None:
            application.applicant_name = data.applicant_name.strip()
        if data.date_of_birth is not None:
            application.date_of_birth = data.date_of_birth
        if data.email is not None:
            application.email = data.email
        if data.phone is not None:
            application.phone = data.phone
        if data.address is not None:
            application.address = data.address
        if data.academic_year_id is not None:
            application.academic_year_id = data.academic_year_id
        if data.program_id is not None:
            application.program_id = data.program_id
        if data.branch_id is not None:
            application.branch_id = data.branch_id
        if data.semester_id is not None:
            application.semester_id = data.semester_id
        if data.source is not None:
            application.source = data.source
        if data.previous_education is not None:
            application.previous_education = data.previous_education
        if data.entrance_score is not None:
            application.entrance_score = data.entrance_score
        if data.remarks is not None:
            application.remarks = data.remarks

        return await self.repo.update(application)

    async def delete(self, application_id: int) -> None:
        application = await self.repo.get_by_id(application_id)
        await self.repo.delete(application)

    async def list(
        self,
        status: Optional[str] = None,
        campus_id: Optional[int] = None,
        program_id: Optional[int] = None,
        academic_year_id: Optional[int] = None,
        search: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[AdmissionApplication], int]:
        if status is not None and status not in ADMISSION_VALID_STATUSES:
            raise ValidationError(f"Invalid status filter: {status}")
        return await self.repo.list(
            status=status,
            campus_id=campus_id,
            program_id=program_id,
            academic_year_id=academic_year_id,
            search=search,
            skip=skip,
            limit=limit,
        )

    # ------------------------------------------------------------------
    # State Machine — Status Transitions
    # ------------------------------------------------------------------

    def _validate_transition(
        self, current: str, new_status: str
    ) -> None:
        """Validate that a status transition is allowed."""
        if current == new_status:
            raise ConflictError(f"Application is already in status '{current}'")

        if new_status == ADMISSION_STATUS_REJECTED:
            # Can reject from any non-terminal state
            if current == ADMISSION_STATUS_STUDENT_CREATED:
                raise ValidationError(
                    "Cannot reject an application that has already been converted to a student"
                )
            return

        if current == ADMISSION_STATUS_REJECTED:
            raise ValidationError(
                "Cannot transition a rejected application forward"
            )

        # Find the current and target positions in the flow
        try:
            current_idx = ADMISSION_STATUS_FLOW.index(current)
            target_idx = ADMISSION_STATUS_FLOW.index(new_status)
        except ValueError:
            raise ValidationError(
                f"Invalid status value: '{current}' -> '{new_status}'"
            )

        if target_idx <= current_idx:
            raise ValidationError(
                f"Cannot transition backward from '{current}' to '{new_status}'"
            )

        if target_idx > current_idx + 1:
            raise ValidationError(
                f"Cannot skip states: transition from '{current}' to "
                f"'{new_status}' requires intermediate steps"
            )

    async def transition_status(
        self, application_id: int, new_status: str, remarks: Optional[str] = None
    ) -> AdmissionApplication:
        app = await self.repo.get_by_id(application_id)
        current = app.status

        self._validate_transition(current, new_status)

        app.status = new_status
        if remarks is not None:
            app.remarks = remarks

        now = datetime.datetime.now(timezone.utc)

        # Set timestamps on specific transitions
        if new_status == ADMISSION_STATUS_FLOW[1]:  # application_submitted
            app.applied_at = now
        elif new_status == ADMISSION_STATUS_ENROLLED:  # enrolled
            app.enrolled_at = now

        updated = await self.repo.update(app)

        # Domain events for admission lifecycle (non-fatal)
        try:
            if new_status == ADMISSION_STATUS_APPLICATION_SUBMITTED:
                await publish_event(
                    AdmissionSubmittedEvent(
                        application_id=updated.id,
                        applicant_name=updated.applicant_name,
                    ),
                    session=self.repo.session,
                )
            elif new_status == ADMISSION_STATUS_ENROLLED:
                await publish_event(
                    AdmissionApprovedEvent(
                        application_id=updated.id,
                        applicant_name=updated.applicant_name,
                    ),
                    session=self.repo.session,
                )
            elif new_status == ADMISSION_STATUS_REJECTED:
                await publish_event(
                    AdmissionRejectedEvent(
                        application_id=updated.id,
                        applicant_name=updated.applicant_name,
                    ),
                    session=self.repo.session,
                )
        except Exception:
            logger.warning("Failed to publish admission event (non-fatal)", exc_info=True)

        return updated


# ---------------------------------------------------------------------------
# AdmissionDocumentService
# ---------------------------------------------------------------------------


class AdmissionDocumentService:
    def __init__(self, repo: AdmissionDocumentRepository) -> None:
        self.repo = repo

    async def create(
        self, application_id: int, data
    ) -> AdmissionDocument:
        doc = AdmissionDocument(
            application_id=application_id,
            document_type=data.document_type.strip(),
            file_name=data.file_name.strip(),
            file_url=data.file_url,
            verification_status=DOCUMENT_VERIFICATION_PENDING,
        )
        return await self.repo.create(doc)

    async def get(self, doc_id: int) -> AdmissionDocument:
        return await self.repo.get_by_id(doc_id)

    async def list_by_application(
        self, application_id: int
    ) -> Sequence[AdmissionDocument]:
        return await self.repo.list_by_application(application_id)

    async def verify(
        self, doc_id: int, verification_status: str,
        verified_by: int, remarks: Optional[str] = None,
        actor: Optional["AuditActor"] = None,
    ) -> AdmissionDocument:
        if verification_status not in VALID_DOCUMENT_VERIFICATION_STATUSES:
            raise ValidationError(
                f"Invalid verification status. Must be one of "
                f"{VALID_DOCUMENT_VERIFICATION_STATUSES}"
            )
        doc = await self.repo.get_by_id(doc_id)
        doc.verification_status = verification_status
        doc.verified_by = verified_by
        doc.verified_at = datetime.datetime.now(timezone.utc)
        if remarks is not None:
            doc.remarks = remarks
        updated = await self.repo.update(doc)

        # Audit: document verified (shares the caller's transaction).
        try:
            from app.domains.audit.service import AuditService

            audit_svc = AuditService(self.repo.session)
            await audit_svc.record(
                action="VERIFY",
                resource_type="document",
                resource_id=str(doc_id),
                actor=actor,
                details={
                    "application_id": doc.application_id,
                    "verification_status": verification_status,
                    "verified_by": verified_by,
                },
            )
        except Exception:
            logger.warning(
                "Failed to write audit entry for document verification (non-fatal)",
                exc_info=True,
            )

        return updated

    async def delete(self, doc_id: int) -> None:
        doc = await self.repo.get_by_id(doc_id)
        await self.repo.delete(doc)


# ---------------------------------------------------------------------------
# AdmissionInterviewService
# ---------------------------------------------------------------------------


class AdmissionInterviewService:
    def __init__(self, repo: AdmissionInterviewRepository) -> None:
        self.repo = repo

    async def create(
        self, application_id: int, data
    ) -> AdmissionInterview:
        interview = AdmissionInterview(
            application_id=application_id,
            scheduled_date=data.scheduled_date,
            interview_mode=data.interview_mode,
            panel_members=data.panel_members,
            status=INTERVIEW_STATUS_SCHEDULED,
        )
        return await self.repo.create(interview)

    async def get(self, interview_id: int) -> AdmissionInterview:
        return await self.repo.get_by_id(interview_id)

    async def list_by_application(
        self, application_id: int
    ) -> Sequence[AdmissionInterview]:
        return await self.repo.list_by_application(application_id)

    async def update(
        self, interview_id: int, data
    ) -> AdmissionInterview:
        interview = await self.repo.get_by_id(interview_id)

        if data.scheduled_date is not None:
            interview.scheduled_date = data.scheduled_date
        if data.interview_mode is not None:
            interview.interview_mode = data.interview_mode
        if data.panel_members is not None:
            interview.panel_members = data.panel_members
        if data.score is not None:
            interview.score = data.score
        if data.remarks is not None:
            interview.remarks = data.remarks
        if data.status is not None:
            if data.status not in VALID_INTERVIEW_STATUSES:
                raise ValidationError(
                    f"Invalid interview status. Must be one of "
                    f"{VALID_INTERVIEW_STATUSES}"
                )
            interview.status = data.status

        return await self.repo.update(interview)


# ---------------------------------------------------------------------------
# AdmissionMeritEntryService
# ---------------------------------------------------------------------------


class AdmissionMeritEntryService:
    def __init__(self, repo: AdmissionMeritEntryRepository) -> None:
        self.repo = repo

    async def create(self, data) -> AdmissionMeritEntry:
        entry = AdmissionMeritEntry(
            application_id=data.application_id,
            program_id=data.program_id,
            academic_year_id=data.academic_year_id,
            total_score=data.total_score,
            rank=data.rank,
            category=data.category,
            status=MERIT_STATUS_ACTIVE,
        )
        return await self.repo.create(entry)

    async def get(self, entry_id: int) -> AdmissionMeritEntry:
        return await self.repo.get_by_id(entry_id)

    async def list_by_program_and_year(
        self, program_id: int, academic_year_id: int
    ) -> Sequence[AdmissionMeritEntry]:
        return await self.repo.list_by_program_and_year(
            program_id, academic_year_id
        )

    async def list(
        self,
        program_id: Optional[int] = None,
        academic_year_id: Optional[int] = None,
        status: Optional[str] = None,
        campus_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[AdmissionMeritEntry], int]:
        if status is not None and status not in VALID_MERIT_STATUSES:
            raise ValidationError(f"Invalid merit status filter: {status}")
        return await self.repo.list(
            program_id=program_id,
            academic_year_id=academic_year_id,
            status=status,
            campus_id=campus_id,
            skip=skip,
            limit=limit,
        )

    async def update(self, entry_id: int, data) -> AdmissionMeritEntry:
        entry = await self.repo.get_by_id(entry_id)
        if data.total_score is not None:
            entry.total_score = data.total_score
        if data.rank is not None:
            entry.rank = data.rank
        if data.category is not None:
            entry.category = data.category
        if data.status is not None:
            entry.status = data.status
        return await self.repo.update(entry)


# ---------------------------------------------------------------------------
# AdmissionSeatAllocationService
# ---------------------------------------------------------------------------


class AdmissionSeatAllocationService:
    def __init__(self, repo: AdmissionSeatAllocationRepository) -> None:
        self.repo = repo

    async def create(self, data) -> AdmissionSeatAllocation:
        now = datetime.datetime.now(timezone.utc)
        allocation = AdmissionSeatAllocation(
            application_id=data.application_id,
            merit_entry_id=data.merit_entry_id,
            program_id=data.program_id,
            branch_id=data.branch_id,
            fee_amount=data.fee_amount,
            allocated_at=now,
            status=ALLOCATION_STATUS_ALLOCATED,
        )
        return await self.repo.create(allocation)

    async def get(self, allocation_id: int) -> AdmissionSeatAllocation:
        return await self.repo.get_by_id(allocation_id)

    async def list_by_application(
        self, application_id: int
    ) -> Sequence[AdmissionSeatAllocation]:
        return await self.repo.list_by_application(application_id)

    async def update(
        self, allocation_id: int, data
    ) -> AdmissionSeatAllocation:
        allocation = await self.repo.get_by_id(allocation_id)
        if data.fee_amount is not None:
            allocation.fee_amount = data.fee_amount
        if data.status is not None:
            if data.status not in VALID_ALLOCATION_STATUSES:
                raise ValidationError(
                    f"Invalid allocation status. Must be one of "
                    f"{VALID_ALLOCATION_STATUSES}"
                )
            if data.status == "fee_paid":
                allocation.paid_at = datetime.datetime.now(timezone.utc)
            elif data.status == "confirmed":
                allocation.enrolled_at = datetime.datetime.now(timezone.utc)
            allocation.status = data.status
        return await self.repo.update(allocation)
