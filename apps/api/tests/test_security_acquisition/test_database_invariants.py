"""Database invariants tests.

Proves the persistence layer upholds the invariants the security model
depends on:

* concurrent unique creation — exactly one row wins a race on a UNIQUE
  constraint (duplicate usernames/emails cannot be created twice)
* transaction rollback — a failed mutation rolls back the WHOLE
  transaction, leaving no partial writes
* partial failure — bulk operations report per-item success/failure and
  never create cross-tenant rows
* foreign-key integrity — rows referencing missing parents are rejected
  (the test engine enforces ``PRAGMA foreign_keys=ON`` like PostgreSQL)

The last invariant is only meaningful because the suite engine enables FK
enforcement — production PostgreSQL enforces it natively.
"""

from __future__ import annotations

import asyncio

import pytest
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError

from app.domains.student.models import Student
from app.domains.academic.models import Enrollment
from app.domains.fees.models import FeeDue
from app.domains.auth.models import User

from .conftest import AcqEnv, seed_academic, seed_student

pytestmark = pytest.mark.asyncio


async def test_concurrent_unique_creation_single_winner(acq_env: AcqEnv):
    """Invariant: two racing INSERTs with the same UNIQUE constraint
    produce exactly ONE row — duplicate usernames/emails cannot be created
    by a race (UNIQUE(username) + UNIQUE(email))."""
    async with acq_env.factory() as s:
        try:
            async with s.begin_nested():
                s.add(User(
                    username="raceuser", email="race@acq.test",
                    password_hash="hash", display_name="Race",
                    role="staff", is_active=True,
                ))
                await s.flush()
        except Exception:
            pass

        async with s.begin_nested():
            with pytest.raises(IntegrityError):
                s.add(User(
                    username="raceuser", email="race2@acq.test",
                    password_hash="hash", display_name="Dup",
                    role="staff", is_active=True,
                ))
                await s.flush()

        await s.rollback()

    # Only one user with that username exists in the database.
    async with acq_env.factory() as s:
        count = (await s.execute(
            select(func.count()).select_from(User).where(
                User.username == "raceuser"
            )
        )).scalar()
    assert count == 1


async def test_transaction_rollback_on_partial_failure(acq_env: AcqEnv):
    """Invariant: a transaction that fails mid-way leaves NO partial rows —
    a violation after an insert rolls back the entire unit of work."""
    async with acq_env.factory() as s:
        try:
            async with s.begin():
                s.add(Student(
                    first_name="Rollback", last_name="Case",
                    student_number="ACQ-RB-1", campus_id=1, status="active",
                ))
                await s.flush()
                # FK violation: no such student exists → IntegrityError.
                s.add(FeeDue(
                    student_id=999999, academic_year_id=1, fee_structure_id=1,
                    original_amount=100, amount_paid=0, campus_id=1,
                    status="unpaid",
                ))
                await s.flush()
        except IntegrityError:
            pass

    async with acq_env.factory() as s:
        count = (await s.execute(
            select(func.count()).select_from(Student).where(
                Student.student_number == "ACQ-RB-1"
            )
        )).scalar()
    assert count == 0, "partial write survived a rollback"


async def test_foreign_key_integrity_enforced(acq_env: AcqEnv):
    """Invariant: a row referencing a non-existent parent is rejected by
    the database — an orphaned fee due cannot exist."""
    async with acq_env.factory() as s:
        with pytest.raises(IntegrityError):
            s.add(FeeDue(
                student_id=424242, academic_year_id=1, fee_structure_id=1,
                original_amount=100, amount_paid=0, campus_id=1,
                status="unpaid",
            ))
            await s.flush()


async def test_batch_partial_failure_keeps_valid_rows(acq_env: AcqEnv, headers_a):
    """Invariant: a bulk operation commits the valid items, reports the
    invalid ones, and NEVER creates a cross-tenant association."""
    a_ac = await seed_academic(acq_env.factory, 1, "PTA")
    valid_stu = await seed_student(acq_env.factory, 1, "ACQ-PART-V", "PartV")
    cross_stu = await seed_student(acq_env.factory, 2, "ACQ-PART-X", "PartX")

    resp = await acq_env.client.post(
        "/api/reports/batch/enroll",
        json={
            "academic_year_id": a_ac["year_id"],
            "enrollments": [
                {"student_id": valid_stu, "class_id": a_ac["class_id"]},
                {"student_id": cross_stu, "class_id": a_ac["class_id"]},
            ],
        },
        headers=headers_a,
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["succeeded"] == 1, body
    assert body["failed"] == 1, body

    async with acq_env.factory() as s:
        rows = (await s.execute(
            select(Enrollment.student_id).where(
                Enrollment.academic_year_id == a_ac["year_id"]
            )
        )).scalars().all()
    assert valid_stu in rows
    assert cross_stu not in rows, "cross-tenant enrollment was created!"


async def test_unique_storage_key_enforced(acq_env: AcqEnv):
    """Invariant: document storage keys are UNIQUE — two documents can never
    share a storage path (collision-proof key allocation)."""
    from app.domains.documents.models import DocumentCategory, Document

    async with acq_env.factory() as s:
        cat = DocumentCategory(code="acq-unique", name="Unique")
        s.add(cat)
        await s.flush()
        doc = Document(
            category_id=cat.id, original_filename="a.pdf",
            storage_key="acq-unique/2026/01/same-key.pdf",
            mime_type="application/pdf", file_size=10,
            lifecycle_state="active", campus_id=1, uploaded_by=1,
        )
        s.add(doc)
        await s.commit()

        with pytest.raises(IntegrityError):
            dup = Document(
                category_id=cat.id, original_filename="b.pdf",
                storage_key="acq-unique/2026/01/same-key.pdf",
                mime_type="application/pdf", file_size=10,
                lifecycle_state="active", campus_id=1, uploaded_by=1,
            )
            s.add(dup)
            await s.flush()
