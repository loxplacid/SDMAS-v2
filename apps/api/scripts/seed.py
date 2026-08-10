"""
SDMAS database seed script.

Usage:
    uv run seed            # Seed with existing DB
    uv run seed --drop     # Drop SQLite DB and re-seed from scratch

This script:
    1. Runs all Alembic migrations (creates tables if needed)
    2. Seeds an admin user
    3. Creates sample data: academic year, classes, sections, teachers, students, fees, attendance
"""

import argparse
import asyncio
import os
import random
import subprocess
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import bcrypt
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

# Ensure the app package is importable
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.config import settings
from app.domains.academic.models import AcademicYear, Class, Section, Subject, Teacher, Term
from app.domains.attendance.models import AttendanceRecord
from app.domains.auth.models import User
from app.domains.fees.models import FeeType, FeeStructure, FeeDue
from app.domains.student.models import Student
from app.domains.workflow.models import Workflow, WorkflowStep, WorkflowTransition
from app.infrastructure.database import create_engine_and_factory


# ═══════════════════════════════════════════════
# 1. Run Alembic migrations
# ═══════════════════════════════════════════════

async def run_migrations() -> None:
    """Run all pending Alembic migrations via subprocess (avoids nested event loop issues)."""
    print("  >> Running Alembic migrations...")
    api_dir = Path(__file__).resolve().parent.parent
    proc = await asyncio.create_subprocess_exec(
        sys.executable, "-m", "alembic", "upgrade", "head",
        cwd=str(api_dir),
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    if stdout:
        for line in stdout.decode().strip().split("\n"):
            print(f"       {line}")
    if stderr:
        for line in stderr.decode().strip().split("\n"):
            if "INFO" in line or "Running" in line:
                print(f"       {line}")
    if proc.returncode != 0:
        print(f"  [FAIL] Migration failed with code {proc.returncode}")
        if stderr:
            print(stderr.decode())
        sys.exit(proc.returncode)
    print("  [OK] Migrations complete")


# ═══════════════════════════════════════════════
# 2. Seed admin user
# ═══════════════════════════════════════════════

async def seed_admin_user(session: AsyncSession) -> None:
    """Create the admin user if it doesn't exist."""
    result = await session.execute(select(User).where(User.username == "admin"))
    if result.scalar_one_or_none():
        print("  >> Admin user already exists, skipping")
        return

    password = "password123"
    password_hash = bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")

    session.add(User(
        email="admin@sdmas.local",
        username="admin",
        password_hash=password_hash,
        display_name="Administrator",
        role="admin",
        is_active=True,
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    ))
    await session.flush()
    print(f"  [OK] Admin user created (admin / {password})")


# ═══════════════════════════════════════════════
# 3. Seed sample data
# ═══════════════════════════════════════════════

async def seed_sample_data(session: AsyncSession) -> None:
    """Create sample academic data for development and testing."""

    # Check if data already exists
    result = await session.execute(select(AcademicYear).limit(1))
    if result.scalar_one_or_none():
        print("  >> Sample data already exists, skipping")
        return

    # -- Academic Year --
    year = AcademicYear(
        name="2025-2026",
        start_date=date(2025, 9, 1),
        end_date=date(2026, 6, 30),
        status="active",
    )
    session.add(year)
    await session.flush()
    year_id = year.id

    # -- Terms --
    terms = [
        Term(name="Term 1", academic_year_id=year_id, start_date=date(2025, 9, 1), end_date=date(2025, 12, 20), status="active"),
        Term(name="Term 2", academic_year_id=year_id, start_date=date(2026, 1, 10), end_date=date(2026, 4, 10), status="active"),
        Term(name="Term 3", academic_year_id=year_id, start_date=date(2026, 4, 20), end_date=date(2026, 6, 30), status="active"),
    ]
    session.add_all(terms)
    await session.flush()

    # -- Classes --
    classes = [
        Class(name="Grade 9", academic_year_id=year_id, status="active"),
        Class(name="Grade 10", academic_year_id=year_id, status="active"),
        Class(name="Grade 11", academic_year_id=year_id, status="active"),
    ]
    session.add_all(classes)
    await session.flush()
    grade9_id, grade10_id, grade11_id = [c.id for c in classes]

    # -- Sections --
    sections = [
        Section(name="Grade 9 - Section A", class_id=grade9_id, status="active"),
        Section(name="Grade 9 - Section B", class_id=grade9_id, status="active"),
        Section(name="Grade 10 - Section A", class_id=grade10_id, status="active"),
        Section(name="Grade 11 - Section A", class_id=grade11_id, status="active"),
    ]
    session.add_all(sections)
    await session.flush()

    # -- Subjects --
    subjects = [
        Subject(name="Mathematics", code="MATH", description="Mathematics", status="active"),
        Subject(name="English", code="ENG", description="English Language", status="active"),
        Subject(name="Science", code="SCI", description="General Science", status="active"),
        Subject(name="History", code="HIST", description="World History", status="active"),
    ]
    session.add_all(subjects)
    await session.flush()

    # -- Teachers --
    teachers = [
        Teacher(first_name="Alice", last_name="Johnson", employee_number="T001", email="alice@sdmas.local", status="active"),
        Teacher(first_name="Bob", last_name="Smith", employee_number="T002", email="bob@sdmas.local", status="active"),
    ]
    session.add_all(teachers)
    await session.flush()

    # -- Students --
    students = [
        Student(first_name="Emma", last_name="Williams", student_number="S001", email="emma@sdmas.local", status="active"),
        Student(first_name="James", last_name="Brown", student_number="S002", email="james@sdmas.local", status="active"),
        Student(first_name="Sophia", last_name="Davis", student_number="S003", email="sophia@sdmas.local", status="active"),
        Student(first_name="Oliver", last_name="Miller", student_number="S004", email="oliver@sdmas.local", status="active"),
        Student(first_name="Ava", last_name="Wilson", student_number="S005", email="ava@sdmas.local", status="active"),
    ]
    session.add_all(students)
    await session.flush()
    student_ids = [s.id for s in students]

    # -- Fee Types --
    fee_types = [
        FeeType(name="Tuition", description="Monthly tuition fee", status="active"),
        FeeType(name="Library", description="Library access fee", status="active"),
        FeeType(name="Sports", description="Sports and athletics", status="active"),
    ]
    session.add_all(fee_types)
    await session.flush()

    # -- Fee Structures --
    structures = [
        FeeStructure(academic_year_id=year_id, class_id=grade9_id, fee_type_id=fee_types[0].id, amount=50000, frequency="monthly", status="active"),
        FeeStructure(academic_year_id=year_id, class_id=grade9_id, fee_type_id=fee_types[1].id, amount=5000, frequency="termly", status="active"),
        FeeStructure(academic_year_id=year_id, class_id=grade10_id, fee_type_id=fee_types[0].id, amount=55000, frequency="monthly", status="active"),
        FeeStructure(academic_year_id=year_id, class_id=grade11_id, fee_type_id=fee_types[0].id, amount=60000, frequency="monthly", status="active"),
    ]
    session.add_all(structures)
    await session.flush()

    # -- Fee Dues --
    for sid in student_ids[:3]:
        for fs in structures:
            amount = fs.amount
            paid = random.choice([0, amount // 2, amount])
            due_status = "paid" if paid >= amount else ("partially_paid" if paid > 0 else "unpaid")
            session.add(FeeDue(
                student_id=sid, academic_year_id=year_id, fee_structure_id=fs.id,
                original_amount=amount, amount_paid=paid, due_date=date(2025, 10, 15),
                status=due_status,
            ))
    await session.flush()

    # -- Attendance Records --
    statuses = ["present", "present", "present", "present", "absent", "late", "excused"]
    sec9a_id = sections[0].id
    for sid in student_ids:
        for day_offset in range(30):
            d = date(2025, 9, 1) + timedelta(days=day_offset)
            if d.weekday() >= 5:
                continue  # Skip weekends
            session.add(AttendanceRecord(
                student_id=sid, academic_year_id=year_id,
                class_id=grade9_id, section_id=sec9a_id,
                attendance_date=d, status=random.choice(statuses),
            ))
    await session.flush()

    print("  [OK] Sample data created:")
    print(f"       - 1 academic year (2025-2026)")
    print(f"       - 3 terms")
    print(f"       - 3 classes, 4 sections")
    print(f"       - 4 subjects")
    print(f"       - 2 teachers, 5 students")
    print(f"       - 3 fee types, 4 structures")
    print(f"       - ~120 attendance records")


# ═══════════════════════════════════════════════
# 4. Main entry point
# ═══════════════════════════════════════════════

async def seed(drop_first: bool = False) -> None:
    """Run the full seed pipeline."""

    # Drop database if requested
    if drop_first and "sqlite" in str(settings.database_url):
        db_path = str(settings.database_url).replace("sqlite+aiosqlite:///", "")
        if os.path.exists(db_path):
            os.remove(db_path)
            print(f"  >> Removed existing database: {db_path}")

    # Run migrations
    await run_migrations()

    # Seed data
    engine, factory = create_engine_and_factory(str(settings.database_url))
    async with factory() as session:
        await seed_admin_user(session)
        await seed_sample_data(session)
        await session.commit()

    await engine.dispose()
    print()
    print("[OK] Seed complete!")
    print()
    print("  Login credentials:")
    print("    Admin:   admin / password123")
    print()
    print("  API running at: http://localhost:8000")
    print("  Docs at:       http://localhost:8000/docs")


def main() -> None:
    parser = argparse.ArgumentParser(description="SDMAS database seed tool")
    parser.add_argument("--drop", action="store_true", help="Drop database before seeding (SQLite only)")
    parser.add_argument(
        "--profile",
        choices=("default", "enterprise-demo"),
        default="default",
        help="Seed profile (enterprise-demo creates three isolated demo tenants)",
    )
    parser.add_argument(
        "--reset", action="store_true",
        help="With --profile enterprise-demo: wipe demo data before reseeding",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="With --profile enterprise-demo: bypass the reset confirmation guard",
    )
    parser.add_argument(
        "--scale", choices=("full", "small"), default="full",
        help="With --profile enterprise-demo: dataset scale",
    )
    parser.add_argument(
        "--no-risk", action="store_true",
        help="With --profile enterprise-demo: skip the risk-engine recompute",
    )
    args = parser.parse_args()

    if args.profile == "enterprise-demo":
        from scripts.seed_enterprise_demo import _guard, _run

        _guard(reset=args.reset, force=args.force)
        asyncio.run(_run(reset=args.reset, scale=args.scale, run_risk=not args.no_risk))
        return

    asyncio.run(seed(drop_first=args.drop))


if __name__ == "__main__":
    main()
