from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import NotFoundError
from app.domains.admission.models import (
    AdmissionApplication,
    AdmissionDocument,
    AdmissionInterview,
    AdmissionMeritEntry,
    AdmissionSeatAllocation,
)


# ---------------------------------------------------------------------------
# AdmissionApplicationRepository
# ---------------------------------------------------------------------------


class AdmissionApplicationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, application_id: int) -> AdmissionApplication:
        result = await self.session.execute(
            select(AdmissionApplication).where(
                AdmissionApplication.id == application_id
            )
        )
        app = result.scalar_one_or_none()
        if app is None:
            raise NotFoundError(
                f"Admission application with id {application_id} not found"
            )
        return app

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
        query = select(AdmissionApplication)
        count_query = select(func.count(AdmissionApplication.id))

        if status is not None:
            query = query.where(AdmissionApplication.status == status)
            count_query = count_query.where(AdmissionApplication.status == status)
        if campus_id is not None:
            query = query.where(AdmissionApplication.campus_id == campus_id)
            count_query = count_query.where(
                AdmissionApplication.campus_id == campus_id
            )
        if program_id is not None:
            query = query.where(AdmissionApplication.program_id == program_id)
            count_query = count_query.where(
                AdmissionApplication.program_id == program_id
            )
        if academic_year_id is not None:
            query = query.where(
                AdmissionApplication.academic_year_id == academic_year_id
            )
            count_query = count_query.where(
                AdmissionApplication.academic_year_id == academic_year_id
            )
        if search:
            like = f"%{search}%"
            query = query.where(
                AdmissionApplication.applicant_name.ilike(like)
                | AdmissionApplication.email.ilike(like)
                | AdmissionApplication.phone.ilike(like)
            )
            count_query = count_query.where(
                AdmissionApplication.applicant_name.ilike(like)
                | AdmissionApplication.email.ilike(like)
                | AdmissionApplication.phone.ilike(like)
            )

        query = query.offset(skip).limit(limit).order_by(AdmissionApplication.id)

        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        result = await self.session.execute(query)
        items = result.scalars().all()

        return items, total

    async def create(
        self, application: AdmissionApplication
    ) -> AdmissionApplication:
        self.session.add(application)
        await self.session.flush()
        return application

    async def update(
        self, application: AdmissionApplication
    ) -> AdmissionApplication:
        await self.session.flush()
        return application

    async def delete(self, application: AdmissionApplication) -> None:
        await self.session.delete(application)


# ---------------------------------------------------------------------------
# AdmissionDocumentRepository
# ---------------------------------------------------------------------------


class AdmissionDocumentRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, doc_id: int) -> AdmissionDocument:
        result = await self.session.execute(
            select(AdmissionDocument).where(AdmissionDocument.id == doc_id)
        )
        doc = result.scalar_one_or_none()
        if doc is None:
            raise NotFoundError(
                f"Admission document with id {doc_id} not found"
            )
        return doc

    async def list_by_application(
        self, application_id: int
    ) -> Sequence[AdmissionDocument]:
        result = await self.session.execute(
            select(AdmissionDocument)
            .where(AdmissionDocument.application_id == application_id)
            .order_by(AdmissionDocument.created_at)
        )
        return result.scalars().all()

    async def create(self, document: AdmissionDocument) -> AdmissionDocument:
        self.session.add(document)
        await self.session.flush()
        return document

    async def update(self, document: AdmissionDocument) -> AdmissionDocument:
        await self.session.flush()
        return document

    async def delete(self, document: AdmissionDocument) -> None:
        await self.session.delete(document)


# ---------------------------------------------------------------------------
# AdmissionInterviewRepository
# ---------------------------------------------------------------------------


class AdmissionInterviewRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, interview_id: int) -> AdmissionInterview:
        result = await self.session.execute(
            select(AdmissionInterview).where(
                AdmissionInterview.id == interview_id
            )
        )
        interview = result.scalar_one_or_none()
        if interview is None:
            raise NotFoundError(
                f"Admission interview with id {interview_id} not found"
            )
        return interview

    async def list_by_application(
        self, application_id: int
    ) -> Sequence[AdmissionInterview]:
        result = await self.session.execute(
            select(AdmissionInterview)
            .where(AdmissionInterview.application_id == application_id)
            .order_by(AdmissionInterview.created_at)
        )
        return result.scalars().all()

    async def create(
        self, interview: AdmissionInterview
    ) -> AdmissionInterview:
        self.session.add(interview)
        await self.session.flush()
        return interview

    async def update(
        self, interview: AdmissionInterview
    ) -> AdmissionInterview:
        await self.session.flush()
        return interview


# ---------------------------------------------------------------------------
# AdmissionMeritEntryRepository
# ---------------------------------------------------------------------------


class AdmissionMeritEntryRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, entry_id: int) -> AdmissionMeritEntry:
        result = await self.session.execute(
            select(AdmissionMeritEntry).where(
                AdmissionMeritEntry.id == entry_id
            )
        )
        entry = result.scalar_one_or_none()
        if entry is None:
            raise NotFoundError(
                f"Admission merit entry with id {entry_id} not found"
            )
        return entry

    async def list_by_program_and_year(
        self, program_id: int, academic_year_id: int
    ) -> Sequence[AdmissionMeritEntry]:
        result = await self.session.execute(
            select(AdmissionMeritEntry)
            .where(
                AdmissionMeritEntry.program_id == program_id,
                AdmissionMeritEntry.academic_year_id == academic_year_id,
            )
            .order_by(AdmissionMeritEntry.rank)
        )
        return result.scalars().all()

    async def list(
        self,
        program_id: Optional[int] = None,
        academic_year_id: Optional[int] = None,
        status: Optional[str] = None,
        campus_id: Optional[int] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[AdmissionMeritEntry], int]:
        query = select(AdmissionMeritEntry)
        count_query = select(func.count(AdmissionMeritEntry.id))

        if program_id is not None:
            query = query.where(AdmissionMeritEntry.program_id == program_id)
            count_query = count_query.where(
                AdmissionMeritEntry.program_id == program_id
            )
        if academic_year_id is not None:
            query = query.where(
                AdmissionMeritEntry.academic_year_id == academic_year_id
            )
            count_query = count_query.where(
                AdmissionMeritEntry.academic_year_id == academic_year_id
            )
        if status is not None:
            query = query.where(AdmissionMeritEntry.status == status)
            count_query = count_query.where(
                AdmissionMeritEntry.status == status
            )
        # Merit entries inherit tenancy from their parent application.
        if campus_id is not None:
            query = query.join(
                AdmissionApplication,
                AdmissionMeritEntry.application_id == AdmissionApplication.id,
            ).where(AdmissionApplication.campus_id == campus_id)
            count_query = count_query.join(
                AdmissionApplication,
                AdmissionMeritEntry.application_id == AdmissionApplication.id,
            ).where(AdmissionApplication.campus_id == campus_id)

        query = query.offset(skip).limit(limit).order_by(AdmissionMeritEntry.rank)

        total_result = await self.session.execute(count_query)
        total = total_result.scalar() or 0

        result = await self.session.execute(query)
        items = result.scalars().all()

        return items, total

    async def create(
        self, entry: AdmissionMeritEntry
    ) -> AdmissionMeritEntry:
        self.session.add(entry)
        await self.session.flush()
        return entry

    async def update(
        self, entry: AdmissionMeritEntry
    ) -> AdmissionMeritEntry:
        await self.session.flush()
        return entry


# ---------------------------------------------------------------------------
# AdmissionSeatAllocationRepository
# ---------------------------------------------------------------------------


class AdmissionSeatAllocationRepository:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, allocation_id: int) -> AdmissionSeatAllocation:
        result = await self.session.execute(
            select(AdmissionSeatAllocation).where(
                AdmissionSeatAllocation.id == allocation_id
            )
        )
        alloc = result.scalar_one_or_none()
        if alloc is None:
            raise NotFoundError(
                f"Admission seat allocation with id {allocation_id} not found"
            )
        return alloc

    async def list_by_application(
        self, application_id: int
    ) -> Sequence[AdmissionSeatAllocation]:
        result = await self.session.execute(
            select(AdmissionSeatAllocation)
            .where(AdmissionSeatAllocation.application_id == application_id)
            .order_by(AdmissionSeatAllocation.created_at)
        )
        return result.scalars().all()

    async def create(
        self, allocation: AdmissionSeatAllocation
    ) -> AdmissionSeatAllocation:
        self.session.add(allocation)
        await self.session.flush()
        return allocation

    async def update(
        self, allocation: AdmissionSeatAllocation
    ) -> AdmissionSeatAllocation:
        await self.session.flush()
        return allocation
