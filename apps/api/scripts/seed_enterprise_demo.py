"""
SDMAS v2 — Enterprise Demo Seeder (Step 5).

Creates three completely isolated demo organizations with realistic,
deterministic data:

    1. Apex Global School             (APX) — K-12
    2. St. Jude Public Academy        (STJ) — primary/middle
    3. Metropolitan Institute of Tech (MIT) — tertiary

Usage:
    uv run seed --profile enterprise-demo
    uv run python -m scripts.seed_enterprise_demo [--reset] [--scale full|small]
    ./enterprise demo-seed
    ./enterprise demo-reset

Safety:
    * Refuses to run against a production database unless
      ``SDMAS_ALLOW_DEMO=1`` is set.
    * ``--reset`` additionally requires ``--force`` (or interactive
      confirmation) and is never allowed in production.
    * Demo users use a single documented development-only password
      (``DemoPass!2026``).  These credentials are demo-only and are not
      used anywhere in production configuration.

Design:
    * Deterministic — every value derives from a fixed per-tenant RNG seed;
      the only input that moves is the attendance/fee date anchor (defaults
      to today so the risk engine has a live 30-day window to evaluate).
    * Idempotent — a tenant whose campus code already exists is skipped, so
      re-running is a no-op.
    * Real intelligence — after seeding, ``RiskService.recompute`` runs per
      campus, so findings are generated *from the seeded data* by the real
      engine rather than fabricated.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import random
import subprocess
import sys
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

# Ensure the app package is importable when run as ``python -m scripts...``
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.domains.academic.models import (
    AcademicYear,
    Class,
    Enrollment,
    Section,
    Subject,
    Teacher,
    Term,
)
from app.domains.academic_ops.models import GradeRecord
from app.domains.attendance.models import AttendanceRecord
from app.domains.audit.service import AuditService
from app.domains.auth.models import User, UserSchoolMembership
from app.domains.auth.security import hash_password
from app.domains.cases.models import (
    CASE_EVENT_ASSIGNED,
    CASE_EVENT_CREATED,
    CASE_SOURCE_MANUAL,
    CASE_SOURCE_RISK_FINDING,
    Case,
    CaseEvent,
)
from app.domains.fees.models import FeeDue, FeeStructure, FeeType, Payment
from app.domains.institution.models import Campus, Institution
from app.domains.notifications.models import Notification
from app.domains.parent.models import Guardian
from app.domains.risk.models import RiskFinding
from app.domains.risk.service import RiskService
from app.domains.school_finance.models import (
    PaymentMethod,
    PaymentReconciliation,
    TransactionLog,
)
from app.domains.school_finance.service import TransactionLogService
from app.domains.student.models import Student
from app.domains.workflow.models import (
    ApprovalHistory,
    Workflow,
    WorkflowInstance,
    WorkflowStep,
    WorkflowTransition,
)
from app.infrastructure.database import create_engine_and_factory

# =====================================================================
# Demo constants
# =====================================================================

DEMO_PASSWORD = "DemoPass!2026"
DEMO_CODES = ("APX", "STJ", "MIT")

DEMO_BANNER = """
  ╔══════════════════════════════════════════════════════════════════╗
  ║                        DEMO ENVIRONMENT                          ║
  ║  Data below is synthetic and created for evaluation only.        ║
  ║  Never run the demo seeder against a production database.        ║
  ╚══════════════════════════════════════════════════════════════════╝
"""

# Statuses used by the attendance domain (mirrors scripts/seed.py).
ATTENDANCE_STATUSES = ("present", "present", "present", "present", "absent", "late", "excused")


# =====================================================================
# Tenant profiles
# =====================================================================


@dataclass(frozen=True)
class TenantProfile:
    code: str
    org_name: str
    org_code: str
    campus_name: str
    address: str
    phone: str
    email: str
    user_prefix: str  # demo username prefix, e.g. "apex" → apex.admin
    grades: tuple[str, ...]
    subjects: tuple[tuple[str, str], ...]  # (name, code)
    teacher_count: int
    # per-class student count for ``full`` scale (``small`` divides by 4).
    students_per_class: int
    sections_per_class: int
    fee_types: tuple[tuple[str, str, int], ...]  # (name, frequency, amount_paise)
    rng_seed: int = field(default=0)


# Frequencies: "annual" | "termly" | "monthly".
TENANT_PROFILES: tuple[TenantProfile, ...] = (
    TenantProfile(
        code="APX",
        org_name="Apex Global School",
        org_code="APEX",
        campus_name="Apex Global School",
        address="1 Apex Avenue, Kilimani, Nairobi",
        phone="+254-700-111-222",
        email="info@apex-global.example",
        user_prefix="apex",
        grades=("Grade 1", "Grade 2", "Grade 3", "Grade 4", "Grade 5",
                "Grade 6", "Grade 7", "Grade 8", "Grade 9", "Grade 10",
                "Grade 11", "Grade 12"),
        subjects=(
            ("Mathematics", "MATH"),
            ("English", "ENG"),
            ("Science", "SCI"),
            ("History", "HIST"),
            ("Geography", "GEO"),
            ("Computer Studies", "CS"),
        ),
        teacher_count=18,
        students_per_class=12,
        sections_per_class=2,
        fee_types=(
            ("Tuition", "annual", 3_600_000),   # ₹36,000 paise → ₹36,000
            ("Transport", "annual", 960_000),   # ₹9,600
            ("Library", "annual", 480_000),     # ₹4,800
        ),
        rng_seed=1001,
    ),
    TenantProfile(
        code="STJ",
        org_name="St. Jude Public Academy",
        org_code="STJUDE",
        campus_name="St. Jude Public Academy",
        address="14 Hope Street, Mombasa Road, Nairobi",
        phone="+254-700-333-444",
        email="office@stjude-academy.example",
        user_prefix="stjude",
        grades=("Primary 1", "Primary 2", "Primary 3", "Primary 4",
                "Primary 5", "Primary 6", "Grade 7", "Grade 8"),
        subjects=(
            ("Mathematics", "MATH"),
            ("English", "ENG"),
            ("Science & Technology", "SCI"),
            ("Kiswahili", "SWA"),
            ("Social Studies", "SOC"),
        ),
        teacher_count=12,
        students_per_class=10,
        sections_per_class=2,
        fee_types=(
            ("Tuition", "annual", 2_400_000),   # ₹24,000
            ("Transport", "annual", 720_000),   # ₹7,200
            ("Uniform", "annual", 240_000),     # ₹2,400
        ),
        rng_seed=2002,
    ),
    TenantProfile(
        code="MIT",
        org_name="Metropolitan Institute of Tech",
        org_code="METRO",
        campus_name="Metropolitan Institute of Tech",
        address="88 Innovation Drive, Westlands, Nairobi",
        phone="+254-700-555-666",
        email="registrar@metro-tech.example",
        user_prefix="mit",
        grades=("BSc Computer Science", "BSc Electrical Eng.",
                "BSc Mechanical Eng.", "BSc Civil Eng."),
        subjects=(
            ("Programming Fundamentals", "PROG"),
            ("Data Structures", "DS"),
            ("Digital Electronics", "DIGI"),
            ("Thermodynamics", "THERMO"),
            ("Calculus", "CALC"),
            ("Technical Writing", "TECHW"),
        ),
        teacher_count=14,
        students_per_class=14,
        sections_per_class=2,
        fee_types=(
            ("Semester Tuition", "termly", 4_800_000),  # ₹48,000/term
            ("Laboratory", "termly", 1_200_000),        # ₹12,000/term
            ("Hostel", "termly", 2_400_000),            # ₹24,000/term
        ),
        rng_seed=3003,
    ),
)

# Demo user accounts: ``role -> username suffix``.
DEMO_USER_ROLES: tuple[tuple[str, str], ...] = (
    ("admin", "admin"),
    ("principal", "principal"),
    ("accountant", "accountant"),
    ("staff", "staff"),
)


def _school_days(end: date, count: int) -> list[date]:
    """Return the last ``count`` weekdays ending on/before ``end``."""
    days: list[date] = []
    cursor = end
    while len(days) < count:
        if cursor.weekday() < 5:  # Mon–Fri
            days.append(cursor)
        cursor -= timedelta(days=1)
    days.reverse()
    return days


# =====================================================================
# Per-tenant seeding
# =====================================================================


async def _seed_identity(
    session: AsyncSession,
    profile: TenantProfile,
) -> tuple[Institution, Campus]:
    """Create (or fetch) the Institution + Campus for a tenant."""
    institution = (
        await session.execute(
            select(Institution).where(Institution.code == profile.org_code)
        )
    ).scalar_one_or_none()
    if institution is None:
        institution = Institution(
            name=profile.org_name,
            code=profile.org_code,
            status="active",
        )
        session.add(institution)
        await session.flush()

    campus = (
        await session.execute(
            select(Campus).where(Campus.code == profile.code)
        )
    ).scalar_one_or_none()
    if campus is None:
        campus = Campus(
            institution_id=institution.id,
            name=profile.campus_name,
            code=profile.code,
            address=profile.address,
            phone=profile.phone,
            email=profile.email,
            status="active",
        )
        session.add(campus)
        await session.flush()
    return institution, campus


async def _seed_users(
    session: AsyncSession,
    profile: TenantProfile,
    campus: Campus,
    rng: random.Random,
    scale: str,
) -> dict[str, User]:
    """Create demo users + memberships for a tenant.  Returns by role key."""
    user_prefix = profile.user_prefix
    users: dict[str, User] = {}

    def make_user(username: str, display_name: str, role: str) -> User:
        user = User(
            username=username,
            email=f"{username}@{profile.org_code.lower()}.demo",
            password_hash=hash_password(DEMO_PASSWORD),
            display_name=display_name,
            role=role,
            campus_id=campus.id,
            is_active=True,
        )
        session.add(user)
        return user

    for role, suffix in DEMO_USER_ROLES:
        username = f"{user_prefix}.{suffix}"
        existing = (
            await session.execute(select(User).where(User.username == username))
        ).scalar_one_or_none()
        if existing is not None:
            users[role] = existing
            continue
        user = make_user(username, f"{profile.campus_name} {role.title()}", role)
        await session.flush()
        session.add(
            UserSchoolMembership(
                user_id=user.id,
                campus_id=campus.id,
                role=role,
                is_default=True,
                is_active=True,
            )
        )
        users[role] = user

    # Teachers.
    teacher_count = profile.teacher_count if scale == "full" else max(2, profile.teacher_count // 4)
    teacher_pool = [f"T{n:02d}" for n in range(1, teacher_count + 1)]
    for tnum in teacher_pool:
        username = f"{user_prefix}.teacher{tnum}"
        existing = (
            await session.execute(select(User).where(User.username == username))
        ).scalar_one_or_none()
        if existing is not None:
            continue
        user = make_user(username, f"{profile.campus_name} Teacher {tnum}", "teacher")
        await session.flush()
        session.add(
            UserSchoolMembership(
                user_id=user.id,
                campus_id=campus.id,
                role="teacher",
                is_default=True,
                is_active=True,
            )
        )

    # Parents (guardians) — a fixed pool reused across students.
    parent_count = 8 if scale == "full" else 3
    for pnum in range(1, parent_count + 1):
        username = f"{user_prefix}.parent{pnum}"
        existing = (
            await session.execute(select(User).where(User.username == username))
        ).scalar_one_or_none()
        if existing is not None:
            continue
        user = make_user(
            username,
            f"{profile.campus_name} Parent {pnum}",
            "parent",
        )
        await session.flush()
        session.add(
            UserSchoolMembership(
                user_id=user.id,
                campus_id=campus.id,
                role="parent",
                is_default=True,
                is_active=True,
            )
        )
    await session.flush()
    return users


async def _seed_academic(
    session: AsyncSession,
    profile: TenantProfile,
    campus: Campus,
    anchor: date,
    scale: str,
) -> dict[str, Any]:
    """Academic year, terms, classes, sections, subjects, teachers."""
    prefix = profile.code

    year_name = f"{anchor.year}-{anchor.year + 1} ({prefix})"
    year = (
        await session.execute(select(AcademicYear).where(AcademicYear.name == year_name))
    ).scalar_one_or_none()
    if year is None:
        year = AcademicYear(
            name=year_name,
            start_date=date(anchor.year, 8, 1),
            end_date=date(anchor.year + 1, 6, 30),
            campus_id=campus.id,
            status="active",
        )
        session.add(year)
        await session.flush()

        term_defs = (
            ("Term 1", f"{anchor.year}-08-01", f"{anchor.year}-11-30"),
            ("Term 2", f"{anchor.year}-12-01", f"{anchor.year + 1}-03-31"),
            ("Term 3", f"{anchor.year + 1}-04-01", f"{anchor.year + 1}-06-30"),
        )
        for name, start, end in term_defs:
            session.add(
                Term(
                    name=name,
                    academic_year_id=year.id,
                    campus_id=campus.id,
                    start_date=start,
                    end_date=end,
                    status="active",
                )
            )
        await session.flush()

    terms = {
        t.name: t
        for t in (
            await session.execute(
                select(Term).where(Term.academic_year_id == year.id)
            )
        ).scalars()
    }

    existing_classes = {
        c.name: c
        for c in (
            await session.execute(
                select(Class).where(Class.campus_id == campus.id)
            )
        ).scalars()
    }
    existing_sections: dict[int, list[Section]] = {}
    for s in (
        await session.execute(
            select(Section).where(Section.campus_id == campus.id)
        )
    ).scalars():
        existing_sections.setdefault(s.class_id, []).append(s)

    classes: list[Class] = []
    sections: dict[int, list[Section]] = {}
    for grade in profile.grades:
        class_name = f"{grade} ({prefix})"
        cls = existing_classes.get(class_name)
        if cls is None:
            cls = Class(
                name=class_name,
                academic_year_id=year.id,
                campus_id=campus.id,
                status="active",
            )
            session.add(cls)
            existing_classes[class_name] = cls
            await session.flush()
        classes.append(cls)
        sections.setdefault(cls.id, [])

    await session.flush()
    # Sections are created per class on first run (idempotent thereafter).
    sections_per_class = (
        profile.sections_per_class if scale == "full" else 1
    )
    for cls in classes:
        if sections[cls.id]:
            continue
        if cls.id in existing_sections:
            sections[cls.id] = existing_sections[cls.id]
            continue
        for idx in range(1, sections_per_class + 1):
            sec = Section(
                name=f"{cls.name} - Section {chr(64 + idx)}",
                class_id=cls.id,
                campus_id=campus.id,
                status="active",
            )
            session.add(sec)
            sections[cls.id].append(sec)
    await session.flush()

    subjects: dict[str, Subject] = {}
    for subj_name, subj_code in profile.subjects:
        full_name = f"{subj_name} ({prefix})"
        full_code = f"{prefix}-{subj_code}"
        subj = (
            await session.execute(
                select(Subject).where(Subject.code == full_code)
            )
        ).scalar_one_or_none()
        if subj is None:
            subj = Subject(
                name=full_name,
                code=full_code,
                description=f"{subj_name} — {profile.campus_name}",
                campus_id=campus.id,
                status="active",
            )
            session.add(subj)
            await session.flush()
        subjects[subj_code] = subj

    teachers: list[Teacher] = []
    teacher_usernames = (
        await session.execute(
            select(User).where(
                User.campus_id == campus.id,
                User.role == "teacher",
            )
        )
    ).scalars().all()
    for idx, user in enumerate(teacher_usernames, start=1):
        employee_number = f"{prefix}-T{idx:03d}"
        teacher = (
            await session.execute(
                select(Teacher).where(Teacher.employee_number == employee_number)
            )
        ).scalar_one_or_none()
        if teacher is None:
            teacher = Teacher(
                first_name=f"{profile.code} Teacher",
                last_name=f"{idx:02d}",
                employee_number=employee_number,
                email=user.email,
                campus_id=campus.id,
                status="active",
            )
            session.add(teacher)
            await session.flush()
        teachers.append(teacher)

    await session.flush()
    return {
        "year": year,
        "terms": terms,
        "classes": classes,
        "sections": sections,
        "subjects": subjects,
        "teachers": teachers,
    }


async def _seed_students(
    session: AsyncSession,
    profile: TenantProfile,
    campus: Campus,
    academic: dict[str, Any],
    rng: random.Random,
    students_per_class: int,
) -> list[tuple[Student, Enrollment]]:
    """Students + enrollments.  Returns [(student, enrollment)]."""
    prefix = profile.code
    year = academic["year"]
    # Deterministic enrollment timestamp (anchor-based, not ``now()``).
    enrolled_at = datetime.combine(year.start_date, datetime.min.time(), tzinfo=timezone.utc)
    first_names = ("Amina", "Brian", "Chloe", "Daniel", "Esther", "Felix",
                   "Grace", "Hassan", "Ivy", "James", "Khadija", "Liam",
                   "Mary", "Noah", "Olivia", "Peter", "Quincy", "Ruth",
                   "Samuel", "Tina", "Umar", "Vera", "William", "Zainab")
    last_names = ("Abdullahi", "Banda", "Chen", "Diallo", "Ekwensi", "Ferguson",
                  "Githinji", "Hassan", "Ibrahim", "Juma", "Kariuki", "Lopez",
                  "Mwangi", "Nakamura", "Otieno", "Patel", "Quinn", "Reyes",
                  "Singh", "Toure", "Ukwu", "Vargas", "Wafula", "Zulu")

    rows: list[tuple[Student, Enrollment]] = []
    seq = 1
    # Bulk-prefetch existing students/enrollments once (avoid N+1 selects).
    existing_students = {
        s.student_number: s
        for s in (
            await session.execute(
                select(Student).where(Student.campus_id == campus.id)
            )
        ).scalars()
    }
    existing_enrollments = {
        (e.student_id, e.academic_year_id): e
        for e in (
            await session.execute(
                select(Enrollment).where(Enrollment.campus_id == campus.id)
            )
        ).scalars()
    }

    for cls in academic["classes"]:
        sections = academic["sections"][cls.id]
        for sec in sections:
            for _ in range(students_per_class):
                student_number = f"{prefix}-{year.name[:4]}-{seq:04d}"
                existing = existing_students.get(student_number)
                if existing is None:
                    first = first_names[rng.randrange(len(first_names))]
                    last = last_names[rng.randrange(len(last_names))]
                    existing = Student(
                        first_name=first,
                        last_name=last,
                        student_number=student_number,
                        campus_id=campus.id,
                        email=f"{first.lower()}.{last.lower()}@{profile.org_code.lower()}.demo",
                        date_of_birth=date(
                            rng.randrange(2006, 2019), rng.randrange(1, 13), rng.randrange(1, 28)
                        ),
                        status="active",
                    )
                    session.add(existing)
                    existing_students[student_number] = existing
                    await session.flush()
                enrollment = existing_enrollments.get((existing.id, year.id))
                if enrollment is None:
                    enrollment = Enrollment(
                        student_id=existing.id,
                        academic_year_id=year.id,
                        class_id=cls.id,
                        section_id=sec.id,
                        campus_id=campus.id,
                        status="active",
                        enrolled_at=enrolled_at,
                    )
                    session.add(enrollment)
                    existing_enrollments[(existing.id, year.id)] = enrollment
                    await session.flush()
                rows.append((existing, enrollment))
                seq += 1
    await session.flush()
    return rows


async def _seed_attendance(
    session: AsyncSession,
    profile: TenantProfile,
    campus: Campus,
    academic: dict[str, Any],
    students: list[tuple[Student, Enrollment]],
    anchor: date,
    rng: random.Random,
    school_days: int,
) -> None:
    """Attendance for the last ``school_days`` weekdays ending at ``anchor``.

    Deterministically engineers a low-attendance student (≈55% present) and
    one student with 5+ consecutive absences so the risk engine has real
    signal to detect.
    """
    year = academic["year"]
    days = _school_days(anchor, school_days)

    # Bulk-prefetch existing attendance keys for this campus (avoid N+1).
    existing_keys = {
        (r.student_id, r.attendance_date, r.section_id)
        for r in (
            await session.execute(
                select(AttendanceRecord).where(
                    AttendanceRecord.campus_id == campus.id
                )
            )
        ).scalars()
    }

    for idx, (student, enrollment) in enumerate(students):
        section = next(
            (s for s in academic["sections"][enrollment.class_id] if s.id == enrollment.section_id),
            academic["sections"][enrollment.class_id][0],
        )
        # Engineer low attendance: every 17th student (by index) is present
        # only ~55% of the time.
        low_attendance = idx % 17 == 0
        # Engineer a consecutive-absence streak on one student.
        streak_student = idx == 5

        streak_run = 0
        for day in days:
            if low_attendance:
                status = "present" if rng.random() < 0.55 else "absent"
            elif streak_student and streak_run < 5:
                status = "absent"
                streak_run += 1
            else:
                status = ATTENDANCE_STATUSES[rng.randrange(len(ATTENDANCE_STATUSES))]
            key = (student.id, day.isoformat(), section.id)
            if key in existing_keys:
                continue
            existing_keys.add(key)
            session.add(
                AttendanceRecord(
                    student_id=student.id,
                    campus_id=campus.id,
                    academic_year_id=year.id,
                    class_id=enrollment.class_id,
                    section_id=section.id,
                    attendance_date=day.isoformat(),
                    status=status,
                )
            )
    await session.flush()


async def _seed_fees(
    session: AsyncSession,
    profile: TenantProfile,
    campus: Campus,
    academic: dict[str, Any],
    students: list[tuple[Student, Enrollment]],
    anchor: date,
    rng: random.Random,
) -> list[FeeDue]:
    """Fee types, structures, dues, payments and an immutable ledger.

    Payment records are journaled through ``TransactionLogService.record``
    so each student's running balance chain is consistent with the sum of
    their payments.  Deterministically engineers overdue + high-outstanding
    students for the finance risk rules.
    """
    prefix = profile.code
    year = academic["year"]
    payer = await _payer_user(session, campus)

    # ── Fee types ────────────────────────────────────────────────────
    fee_types: dict[str, FeeType] = {}
    for ft_name, frequency, amount in profile.fee_types:
        full_name = f"{ft_name} ({prefix})"
        ft = (
            await session.execute(select(FeeType).where(FeeType.name == full_name))
        ).scalar_one_or_none()
        if ft is None:
            ft = FeeType(
                name=full_name,
                description=f"{ft_name} — {profile.campus_name}",
                campus_id=campus.id,
                status="active",
            )
            session.add(ft)
            await session.flush()
        fee_types[ft_name] = (ft, frequency, amount)

    # ── Fee structures per class (bulk-prefetched) ────────────────────
    existing_structures = {
        (s.academic_year_id, s.class_id, s.fee_type_id): s
        for s in (
            await session.execute(
                select(FeeStructure).where(FeeStructure.campus_id == campus.id)
            )
        ).scalars()
    }
    structures: dict[int, list[FeeStructure]] = {}
    for cls in academic["classes"]:
        structures[cls.id] = []
        for ft_name, (ft, frequency, amount) in fee_types.items():
            key = (year.id, cls.id, ft.id)
            structure = existing_structures.get(key)
            if structure is None:
                structure = FeeStructure(
                    academic_year_id=year.id,
                    class_id=cls.id,
                    fee_type_id=ft.id,
                    campus_id=campus.id,
                    amount=amount,
                    frequency=frequency,
                    status="active",
                )
                session.add(structure)
                existing_structures[key] = structure
                await session.flush()
            structures[cls.id].append(structure)
    await session.flush()

    # ── Payment methods ──────────────────────────────────────────────
    method_codes = {
        "CASH": "Cash",
        "CARD": "Card",
        "BANK": "Bank Transfer",
        "UPI": "UPI / Mobile",
    }
    for code, name in method_codes.items():
        full_code = f"{prefix}-{code}"
        existing = (
            await session.execute(select(PaymentMethod).where(PaymentMethod.code == full_code))
        ).scalar_one_or_none()
        if existing is None:
            session.add(
                PaymentMethod(
                    name=name,
                    code=full_code,
                    description=f"{name} — {profile.campus_name}",
                    is_active=True,
                    requires_reference=(code == "BANK"),
                    campus_id=campus.id,
                )
            )
    await session.flush()

    # ── Dues + payments (existing dues bulk-prefetched) ───────────────
    existing_dues = {
        (d.student_id, d.fee_structure_id): d
        for d in (
            await session.execute(
                select(FeeDue).where(FeeDue.campus_id == campus.id)
            )
        ).scalars()
    }
    existing_payment_due_ids = {
        p.fee_due_id
        for p in (
            await session.execute(
                select(Payment).where(Payment.campus_id == campus.id)
            )
        ).scalars()
    }
    dues: list[FeeDue] = []
    tx_svc = TransactionLogService(session)
    method_keys = list(method_codes.keys())
    payment_seq = 1

    def due_date_for(idx: int, overdue: bool) -> date:
        """Deterministic due date — overdue students get a 60-day due date."""
        lag = 60 if (overdue and idx % 2) else 15
        return anchor - timedelta(days=lag)

    for idx, (student, enrollment) in enumerate(students):
        overdue_student = idx % 13 == 0
        high_outstanding = idx % 29 == 0
        for structure in structures[enrollment.class_id]:
            original = structure.amount
            due = existing_dues.get((student.id, structure.id))

            due_date = due_date_for(idx, overdue_student)

            if high_outstanding:
                paid = 0
            elif overdue_student:
                # Overdue: 0–40% paid → fees_overdue / fees_overdue_duration.
                paid = int(original * rng.choice((0.0, 0.3, 0.4)))
            else:
                roll = rng.random()
                if roll < 0.5:
                    paid = original                     # fully paid
                elif roll < 0.8:
                    paid = int(original * 0.5)          # partially paid
                else:
                    paid = 0                            # unpaid / pending

            if due is None:
                status = (
                    "paid" if paid >= original
                    else "partially_paid" if paid > 0 else "unpaid"
                )
                due = FeeDue(
                    student_id=student.id,
                    academic_year_id=year.id,
                    fee_structure_id=structure.id,
                    original_amount=original,
                    campus_id=campus.id,
                    amount_paid=paid,
                    due_date=due_date.isoformat(),
                    status=status,
                )
                session.add(due)
                existing_dues[(student.id, structure.id)] = due
                await session.flush()
            else:
                paid = due.amount_paid
            dues.append(due)

            # Journal payments for this due (idempotent by receipt number).
            if paid > 0 and due.id not in existing_payment_due_ids:
                existing_payment_due_ids.add(due.id)
                method = method_keys[rng.randrange(len(method_keys))]
                receipt_number = f"{prefix}-RCPT-{payment_seq:05d}"
                payment = Payment(
                    student_id=student.id,
                    fee_due_id=due.id,
                    campus_id=campus.id,
                    amount=paid,
                    payment_date=(anchor - timedelta(days=rng.randrange(3, 40))).isoformat(),
                    payment_method=method,
                    receipt_number=receipt_number,
                    idempotency_key=f"demo:{prefix}:pay:{payment_seq}",
                    status="completed",
                    refunded_amount=0,
                )
                session.add(payment)
                await session.flush()
                await tx_svc.record(
                    transaction_type="payment",
                    student_id=student.id,
                    amount=paid,
                    payment_id=payment.id,
                    fee_due_id=due.id,
                    reference_number=receipt_number,
                    idempotency_key=f"demo:{prefix}:tx:{payment_seq}",
                    description=f"Fee payment for {profile.campus_name}",
                    campus_id=campus.id,
                    recorded_by=payer.id if payer else None,
                )
                payment_seq += 1

    await session.flush()

    # ── One visible reconciliation scenario per tenant ───────────────
    reconciled = (
        await session.execute(
            select(PaymentReconciliation).where(
                PaymentReconciliation.campus_id == campus.id,
            )
        )
    ).scalar_one_or_none()
    if reconciled is None:
        totals = (
            await session.execute(
                select(
                    func.count(Payment.id),
                    func.coalesce(func.sum(Payment.amount), 0),
                ).where(Payment.campus_id == campus.id)
            )
        ).one()
        session.add(
            PaymentReconciliation(
                reconciliation_date=anchor,
                total_amount=int(totals[1] or 0),
                total_count=int(totals[0] or 0),
                status="verified",
                notes=f"Demo reconciliation — {profile.campus_name}",
                reconciled_by=payer.id if payer else None,
                campus_id=campus.id,
            )
        )
    await session.flush()
    return dues


async def _payer_user(session: AsyncSession, campus: Campus) -> User | None:
    """The tenant's accountant user, used as the recorded actor."""
    return (
        await session.execute(
            select(User).where(
                User.campus_id == campus.id,
                User.role == "accountant",
            )
        )
    ).scalar_one_or_none()


async def _seed_grades(
    session: AsyncSession,
    profile: TenantProfile,
    campus: Campus,
    academic: dict[str, Any],
    students: list[tuple[Student, Enrollment]],
    rng: random.Random,
) -> None:
    """Grade records for terms 1–2 → academic risk signal.

    Deterministically engineers low performers (avg < 40%) and one declining
    performer (drop ≥ 10 pts between terms).
    """
    subjects = list(academic["subjects"].values())
    terms = academic["terms"]
    terms_for_grades = [terms["Term 1"], terms["Term 2"]]

    existing_grades = {
        (g.enrollment_id, g.subject_id, g.term_id)
        for g in (
            await session.execute(
                select(GradeRecord).where(GradeRecord.campus_id == campus.id)
            )
        ).scalars()
    }

    for idx, (student, enrollment) in enumerate(students):
        low_performer = idx % 23 == 0
        decliner = idx % 31 == 0
        for subject in subjects:
            for term in terms_for_grades:
                if (enrollment.id, subject.id, term.id) in existing_grades:
                    continue
                existing_grades.add((enrollment.id, subject.id, term.id))
                if low_performer:
                    marks = rng.randrange(22, 40)
                elif decliner and term == terms["Term 2"]:
                    marks = rng.randrange(30, 45)
                elif decliner:
                    marks = rng.randrange(65, 85)
                else:
                    marks = rng.randrange(55, 98)
                grade = (
                    "A" if marks >= 75
                    else "B" if marks >= 60
                    else "C" if marks >= 45 else "D"
                )
                session.add(
                    GradeRecord(
                        enrollment_id=enrollment.id,
                        subject_id=subject.id,
                        term_id=term.id,
                        marks_obtained=float(marks),
                        max_marks=100,
                        grade=grade,
                        grade_point=float(max(0, (marks - 40) / 10)),
                        campus_id=campus.id,
                        status="active",
                    )
                )
    await session.flush()


async def _seed_guardians(
    session: AsyncSession,
    profile: TenantProfile,
    campus: Campus,
    students: list[tuple[Student, Enrollment]],
) -> None:
    """Link most students to a parent user via ``guardian_links``.

    Every 41st student is deliberately left without a guardian so the
    ``operational_no_guardian`` risk rule fires on real data.
    """
    parents = (
        await session.execute(
            select(User).where(
                User.campus_id == campus.id,
                User.role == "parent",
            )
        )
    ).scalars().all()
    if not parents:
        return
    existing_student_ids = {
        g.student_id
        for g in (
            await session.execute(
                select(Guardian).where(Guardian.campus_id == campus.id)
            )
        ).scalars()
    }
    for idx, (student, _enrollment) in enumerate(students):
        if idx % 41 == 0:
            continue
        if student.id in existing_student_ids:
            continue
        existing_student_ids.add(student.id)
        session.add(
            Guardian(
                user_id=parents[idx % len(parents)].id,
                student_id=student.id,
                relationship="parent",
                is_primary=True,
                campus_id=campus.id,
            )
        )
    await session.flush()


async def _seed_workflows(
    session: AsyncSession,
    profile: TenantProfile,
    campus: Campus,
) -> None:
    """Leave-request workflow definition + a couple of live instances."""
    prefix = profile.code
    code = f"{prefix}-leave-request"
    workflow = (
        await session.execute(select(Workflow).where(Workflow.code == code))
    ).scalar_one_or_none()
    if workflow is None:
        workflow = Workflow(
            name=f"Leave Request ({prefix})",
            code=code,
            description=f"Two-step approval leave workflow — {profile.campus_name}",
            entity_type="leave_request",
            status="active",
        )
        session.add(workflow)
        await session.flush()

        steps = {}
        for order, (name, initial, final) in enumerate(
            (
                ("Submitted", True, False),
                ("HOD Approval", False, False),
                ("Principal Approval", False, False),
                ("Complete", False, True),
            )
        ):
            step = WorkflowStep(
                workflow_id=workflow.id,
                name=name,
                label=name,
                step_order=order,
                is_initial=initial,
                is_final=final,
                assigned_role="staff" if order <= 1 else "principal",
            )
            session.add(step)
            steps[name] = step
        await session.flush()

        transitions = (
            ("Submitted", "HOD Approval", "submit", None),
            ("HOD Approval", "Principal Approval", "approve", "principal"),
            ("HOD Approval", "Submitted", "return", None),
            ("Principal Approval", "Complete", "approve", "principal"),
            ("Principal Approval", "Submitted", "return", None),
        )
        for from_name, to_name, label, role in transitions:
            session.add(
                WorkflowTransition(
                    workflow_id=workflow.id,
                    from_step_id=steps[from_name].id,
                    to_step_id=steps[to_name].id,
                    label=label,
                    required_role=role,
                )
            )
        await session.flush()
    else:
        steps = {
            s.name: s
            for s in (
                await session.execute(
                    select(WorkflowStep).where(WorkflowStep.workflow_id == workflow.id)
                )
            ).scalars()
        }

    # A couple of instances for the demo.
    requester = (
        await session.execute(
            select(User).where(
                User.campus_id == campus.id,
                User.role.in_(("staff", "teacher")),
            )
        )
    ).scalars().first()

    existing_instances = (
        await session.execute(
            select(func.count(WorkflowInstance.id)).where(
                WorkflowInstance.campus_id == campus.id,
                WorkflowInstance.workflow_id == workflow.id,
            )
        )
    ).scalar_one() or 0

    if requester is not None and existing_instances == 0:
        for idx in range(2):
            current = "HOD Approval" if idx == 0 else "Complete"
            instance = WorkflowInstance(
                workflow_id=workflow.id,
                current_step_id=steps[current].id,
                campus_id=campus.id,
                entity_type="leave_request",
                entity_id=idx + 1,
                status="active" if idx == 0 else "completed",
                created_by=requester.id,
            )
            session.add(instance)
            await session.flush()
            session.add(
                ApprovalHistory(
                    instance_id=instance.id,
                    from_step_id=steps["Submitted"].id,
                    to_step_id=steps["HOD Approval"].id,
                    action="submit",
                    actor_id=requester.id,
                    comment=f"Demo leave request {idx + 1}",
                )
            )
    await session.flush()


async def _seed_cases(
    session: AsyncSession,
    profile: TenantProfile,
    campus: Campus,
    students: list[tuple[Student, Enrollment]],
    anchor: date,
) -> None:
    """A couple of operational cases — one manual, one from a risk finding."""
    prefix = profile.code
    # Deterministic deadlines (anchor-based, not ``now()``).
    midnight = datetime.combine(anchor, datetime.min.time(), tzinfo=timezone.utc)
    due_soon = midnight + timedelta(days=3)
    due_later = midnight + timedelta(days=5)
    existing_cases = (
        await session.execute(
            select(func.count(Case.id)).where(Case.campus_id == campus.id)
        )
    ).scalar_one() or 0
    if existing_cases > 0:
        return

    admin = (
        await session.execute(
            select(User).where(
                User.campus_id == campus.id,
                User.role == "admin",
            )
        )
    ).scalar_one_or_none()
    assignee = (
        await session.execute(
            select(User).where(
                User.campus_id == campus.id,
                User.role.in_(("staff", "teacher")),
            )
        )
    ).scalars().first()
    student, enrollment = students[0]

    manual = Case(
        case_number=f"{prefix}-2026-0001",
        campus_id=campus.id,
        title="Review transport route safety",
        description="Demo case — verify the new transport route before term starts.",
        case_type="operational",
        priority="medium",
        status="open",
        source_type=CASE_SOURCE_MANUAL,
        student_id=student.id,
        created_by=admin.id if admin else None,
        assigned_to=assignee.id if assignee else None,
        due_at=due_later,
        version=1,
    )
    session.add(manual)
    await session.flush()
    session.add(
        CaseEvent(
            case_id=manual.id,
            event_seq=1,
            event_type=CASE_EVENT_CREATED,
            actor_id=admin.id if admin else None,
            actor_name=admin.display_name if admin else None,
            message="Case created (demo)",
        )
    )

    finding = (
        await session.execute(
            select(RiskFinding).where(
                RiskFinding.campus_id == campus.id,
                RiskFinding.status == "open",
            )
        )
    ).scalars().first()
    if finding is not None:
        from_risk = Case(
            case_number=f"{prefix}-2026-0002",
            campus_id=campus.id,
            title=f"Act on risk: {finding.rule_code}",
            description=finding.reason,
            case_type=finding.category,
            priority="high" if finding.severity == "critical" else finding.severity,
            status="open",
            source_type=CASE_SOURCE_RISK_FINDING,
            source_id=finding.id,
            student_id=finding.student_id,
            created_by=admin.id if admin else None,
            assigned_to=assignee.id if assignee else None,
            due_at=due_soon,
            version=1,
        )
        session.add(from_risk)
        await session.flush()
        session.add(
            CaseEvent(
                case_id=from_risk.id,
                event_seq=1,
                event_type=CASE_EVENT_CREATED,
                actor_id=admin.id if admin else None,
                actor_name=admin.display_name if admin else None,
                message=f"Case created from risk finding #{finding.id}",
            )
        )
        if assignee is not None:
            session.add(
                CaseEvent(
                    case_id=from_risk.id,
                    event_seq=2,
                    event_type=CASE_EVENT_ASSIGNED,
                    actor_id=admin.id if admin else None,
                    actor_name=admin.display_name if admin else None,
                    message=f"Assigned to {assignee.display_name}",
                )
            )
    await session.flush()


async def _seed_notifications_and_audit(
    session: AsyncSession,
    profile: TenantProfile,
    campus: Campus,
    counts: dict[str, int],
) -> None:
    """Seed a few notifications and one summary audit event per tenant."""
    admin = (
        await session.execute(
            select(User).where(
                User.campus_id == campus.id,
                User.role == "admin",
            )
        )
    ).scalar_one_or_none()

    if admin is not None:
        existing = (
            await session.execute(
                select(func.count(Notification.id)).where(
                    Notification.campus_id == campus.id,
                    Notification.type == "demo",
                )
            )
        ).scalar_one() or 0
        if existing == 0:
            session.add(
                Notification(
                    user_id=admin.id,
                    type="demo",
                    title="Demo environment ready",
                    message=f"{profile.campus_name} seeded with synthetic evaluation data.",
                    campus_id=campus.id,
                )
            )

    audit_svc = AuditService(session)
    await audit_svc.record(
        action="SEED",
        resource_type="demo",
        resource_id=str(campus.id),
        user_id=admin.id if admin else None,
        username=admin.username if admin else None,
        details={"campus": profile.campus_name, "counts": counts},
        campus_id=campus.id,
    )
    await session.flush()


# =====================================================================
# Reset (delete demo data)
# =====================================================================

async def reset_demo_data(session: AsyncSession) -> dict[str, int]:
    """Delete all rows belonging to the demo campuses.  Returns counts.

    Deletion is explicit and dependency-ordered.  Child tables that carry
    no ``campus_id`` (case events, workflow steps/transitions/history) are
    removed through their campus-scoped parents — SQLite can otherwise
    reuse primary keys and collide with stale children on reseed.
    """
    campuses = (
        await session.execute(
            select(Campus).where(Campus.code.in_(DEMO_CODES))
        )
    ).scalars().all()
    campus_ids = [c.id for c in campuses]
    deleted: dict[str, int] = {}
    if not campus_ids:
        return deleted

    async def _run(q, name: str) -> None:
        result = await session.execute(q)
        if result.rowcount:
            deleted[name] = result.rowcount

    # ── Child rows without campus_id, via campus-scoped parents ────────
    case_ids = select(Case.id).where(Case.campus_id.in_(campus_ids))
    await _run(delete(CaseEvent).where(CaseEvent.case_id.in_(case_ids)), "case_events")

    workflow_ids = select(Workflow.id).where(
        Workflow.code.in_([f"{c}-leave-request" for c in DEMO_CODES])
    )
    instance_ids = select(WorkflowInstance.id).where(
        WorkflowInstance.campus_id.in_(campus_ids)
    )
    await _run(
        delete(ApprovalHistory).where(ApprovalHistory.instance_id.in_(instance_ids)),
        "approval_history",
    )
    await _run(
        delete(WorkflowTransition).where(WorkflowTransition.workflow_id.in_(workflow_ids)),
        "workflow_transitions",
    )
    await _run(
        delete(WorkflowStep).where(WorkflowStep.workflow_id.in_(workflow_ids)),
        "workflow_steps",
    )
    await _run(
        delete(WorkflowInstance).where(WorkflowInstance.campus_id.in_(campus_ids)),
        "workflow_instances",
    )
    await _run(delete(Workflow).where(Workflow.id.in_(workflow_ids)), "workflows")

    # ── Campus-scoped tables (dependency order) ────────────────────────
    for model in (
        PaymentReconciliation,
        Payment,
        TransactionLog,
        FeeDue,
        FeeStructure,
        FeeType,
        PaymentMethod,
        GradeRecord,
        AttendanceRecord,
        Enrollment,
        Guardian,
        Student,
        Case,
        RiskFinding,
        Notification,
        Teacher,
        Section,
        Subject,
        Class,
        Term,
        AcademicYear,
    ):
        await _run(delete(model).where(model.campus_id.in_(campus_ids)), model.__tablename__)

    # ── Identity ───────────────────────────────────────────────────────
    await _run(
        delete(UserSchoolMembership).where(
            UserSchoolMembership.campus_id.in_(campus_ids)
        ),
        "user_school_memberships",
    )
    await _run(delete(User).where(User.campus_id.in_(campus_ids)), "users")
    await _run(delete(Campus).where(Campus.id.in_(campus_ids)), "campuses")
    await _run(
        delete(Institution).where(
            Institution.code.in_([p.org_code for p in TENANT_PROFILES])
        ),
        "institutions",
    )
    await session.flush()
    deleted["campuses"] = len(campus_ids)
    return deleted


# =====================================================================
# Top-level seeding
# =====================================================================


async def seed_enterprise_demo(
    session: AsyncSession,
    *,
    reset: bool = False,
    scale: str = "full",
    run_risk: bool = True,
    anchor_date: date | None = None,
) -> dict[str, Any]:
    """Seed the three demo tenants.

    Returns a summary of per-tenant counts.  Idempotent: tenants whose
    campus already exists are skipped.
    """
    anchor = anchor_date or date.today()
    summary: dict[str, Any] = {"tenants": {}, "reset": reset}
    if reset:
        summary["deleted"] = await reset_demo_data(session)

    for profile in TENANT_PROFILES:
        campus = (
            await session.execute(
                select(Campus).where(Campus.code == profile.code)
            )
        ).scalar_one_or_none()
        if campus is not None:
            # Idempotency: already seeded in a previous run.
            counts = await _count_tenant(session, campus)
            summary["tenants"][profile.code] = {"skipped": True, "counts": counts}
            continue

        rng = random.Random(profile.rng_seed)
        _institution, campus = await _seed_identity(session, profile)
        users = await _seed_users(session, profile, campus, rng, scale)
        academic = await _seed_academic(session, profile, campus, anchor, scale)

        students_per_class = (
            profile.students_per_class
            if scale == "full"
            else max(2, profile.students_per_class // 4)
        )
        students = await _seed_students(
            session, profile, campus, academic, rng, students_per_class
        )
        school_days = 40 if scale == "full" else 15
        await _seed_attendance(
            session, profile, campus, academic, students, anchor, rng, school_days
        )
        await _seed_fees(session, profile, campus, academic, students, anchor, rng)
        await _seed_grades(session, profile, campus, academic, students, rng)
        await _seed_guardians(session, profile, campus, students)
        await _seed_workflows(session, profile, campus)
        await _seed_cases(session, profile, campus, students, anchor)

        counts = await _count_tenant(session, campus)
        summary["tenants"][profile.code] = {"skipped": False, "counts": counts}

        if run_risk:
            admin = users.get("admin")
            try:
                risk = RiskService(session)
                await risk.recompute(
                    campus.id,
                    actor_user_id=admin.id if admin else None,
                )
                summary["tenants"][profile.code]["risk"] = (
                    await session.execute(
                        select(func.count(RiskFinding.id)).where(
                            RiskFinding.campus_id == campus.id,
                            RiskFinding.status == "open",
                        )
                    )
                ).scalar_one() or 0
            except Exception as exc:  # noqa: BLE001 — demo must not hard-fail
                summary["tenants"][profile.code]["risk_error"] = str(exc)

        await _seed_notifications_and_audit(session, profile, campus, counts)
        await session.flush()

    await session.commit()
    return summary


async def _count_tenant(session: AsyncSession, campus: Campus) -> dict[str, int]:
    """Row counts for one tenant (for reporting + idempotency checks)."""
    counts: dict[str, int] = {}
    for name, model in (
        ("students", Student),
        ("teachers", Teacher),
        ("attendance", AttendanceRecord),
        ("fee_dues", FeeDue),
        ("payments", Payment),
        ("grade_records", GradeRecord),
        ("risk_findings", RiskFinding),
        ("cases", Case),
        ("workflows", WorkflowInstance),
        ("users", User),
    ):
        counts[name] = (
            await session.execute(
                select(func.count(model.id)).where(model.campus_id == campus.id)
            )
        ).scalar_one() or 0
    return counts


# =====================================================================
# Migrations + CLI
# =====================================================================


async def run_migrations() -> None:
    """Run Alembic migrations via subprocess (mirrors scripts/seed.py)."""
    api_dir = Path(__file__).resolve().parent.parent
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "alembic", "upgrade", "head",
        cwd=str(api_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if proc.returncode != 0:
        print(f"  [FAIL] Migration failed with code {proc.returncode}")
        if stderr:
            print(stderr.decode())
        sys.exit(proc.returncode)


def _guard(reset: bool, force: bool) -> None:
    """Refuse demo seeding against production / accidental resets."""
    if settings.environment == "production" and os.environ.get("SDMAS_ALLOW_DEMO") != "1":
        raise SystemExit(
            "Refusing to seed demo data in production. "
            "Set SDMAS_ALLOW_DEMO=1 only if you explicitly intend this."
        )
    if reset and not force:
        raise SystemExit(
            "Refusing to reset demo data without --force. "
            "This deletes all rows belonging to the demo campuses."
        )


async def _run(reset: bool, scale: str, run_risk: bool) -> None:
    print(DEMO_BANNER)
    await run_migrations()
    engine, factory = create_engine_and_factory(str(settings.database_url))
    async with factory() as session:
        summary = await seed_enterprise_demo(
            session, reset=reset, scale=scale, run_risk=run_risk
        )
    await engine.dispose()

    print("\n[OK] Enterprise demo seed complete!")
    print(f"  Reset applied: {summary.get('reset', False)}")
    if summary.get("deleted"):
        print(f"  Deleted rows:  {sum(summary['deleted'].values())}")
    for code, info in summary["tenants"].items():
        if info.get("skipped"):
            print(f"  {code}: already seeded — skipped")
            continue
        counts = info["counts"]
        risk = info.get("risk")
        print(
            f"  {code}: {counts.get('students', 0)} students, "
            f"{counts.get('attendance', 0)} attendance records, "
            f"{counts.get('payments', 0)} payments, "
            f"{counts.get('risk_findings', 0)} risk findings"
            + (f" ({risk} open)" if risk is not None else "")
        )
    print("\n  Demo credentials (development-only):")
    for profile in TENANT_PROFILES:
        print(f"    {profile.code.lower()}.admin / {DEMO_PASSWORD}")
    print("\n  Reset with:  uv run seed --profile enterprise-demo --reset --force")
    print("               ./enterprise demo-reset")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="SDMAS enterprise demo seeder (three isolated tenants)"
    )
    parser.add_argument("--reset", action="store_true", help="Wipe demo data, then reseed")
    parser.add_argument("--force", action="store_true", help="Skip the reset confirmation guard")
    parser.add_argument(
        "--scale", choices=("full", "small"), default="full",
        help="Dataset scale (small is used by the test-suite)",
    )
    parser.add_argument(
        "--no-risk", action="store_true",
        help="Skip the risk-engine recompute (useful for fast tests)",
    )
    args = parser.parse_args()
    _guard(reset=args.reset, force=args.force)
    asyncio.run(_run(reset=args.reset, scale=args.scale, run_risk=not args.no_risk))


if __name__ == "__main__":
    main()
