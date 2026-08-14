"""create institution hierarchy tables (Multi-Campus support)

Revision ID: 010_create_institution_hierarchy
Revises: 009_create_device_tokens
Create Date: 2026-07-29
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "010_create_institution_hierarchy"
down_revision: Union[str, None] = "009_create_device_tokens"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ------------------------------------------------------------------
    # Institution
    # ------------------------------------------------------------------
    op.create_table(
        "institutions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("code", name="uq_institution_code"),
    )

    # ------------------------------------------------------------------
    # Campus
    # ------------------------------------------------------------------
    op.create_table(
        "campuses",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("institution_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("address", sa.Text(), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["institution_id"], ["institutions.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_campuses_institution_id", "campuses", ["institution_id"])

    # ------------------------------------------------------------------
    # School
    # ------------------------------------------------------------------
    op.create_table(
        "schools",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("campus_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["campus_id"], ["campuses.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_schools_campus_id", "schools", ["campus_id"])

    # ------------------------------------------------------------------
    # Department
    # ------------------------------------------------------------------
    op.create_table(
        "departments",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("school_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["school_id"], ["schools.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_departments_school_id", "departments", ["school_id"])

    # ------------------------------------------------------------------
    # Program
    # ------------------------------------------------------------------
    op.create_table(
        "programs",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("department_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("duration_years", sa.Integer(), nullable=False, server_default="4"),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["department_id"], ["departments.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_programs_department_id", "programs", ["department_id"])

    # ------------------------------------------------------------------
    # Branch
    # ------------------------------------------------------------------
    op.create_table(
        "branches",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("program_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["program_id"], ["programs.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_branches_program_id", "branches", ["program_id"])

    # ------------------------------------------------------------------
    # Semester
    # ------------------------------------------------------------------
    op.create_table(
        "semesters",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("program_id", sa.Integer(), nullable=False),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("code", sa.String(50), nullable=False),
        sa.Column("semester_number", sa.Integer(), nullable=False),
        sa.Column("start_date", sa.String(10), nullable=True),
        sa.Column("end_date", sa.String(10), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(
            ["program_id"], ["programs.id"], ondelete="CASCADE"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_semesters_program_id", "semesters", ["program_id"])

    # Ensure we have a default institution for backward compatibility.
    # Portability: `INSERT OR IGNORE` and `datetime('now')` are SQLite-only;
    # `ON CONFLICT DO NOTHING` + `CURRENT_TIMESTAMP` work on PostgreSQL and
    # SQLite >= 3.24 alike.
    op.execute(
        sa.text(
            "INSERT INTO institutions (id, name, code, status, created_at, updated_at) "
            "VALUES (1, 'Default Institution', 'DEFAULT', 'active', "
            "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) "
            "ON CONFLICT (id) DO NOTHING"
        )
    )
    op.execute(
        sa.text(
            "INSERT INTO campuses (id, institution_id, name, code, status, created_at, updated_at) "
            "VALUES (1, 1, 'Main Campus', 'MAIN', 'active', "
            "CURRENT_TIMESTAMP, CURRENT_TIMESTAMP) "
            "ON CONFLICT (id) DO NOTHING"
        )
    )

    # Explicit-ID inserts do NOT advance PostgreSQL sequences, so the next
    # default-ID insert (e.g. the enterprise demo seeder) would collide with
    # id=1. Resync the sequences after seeding. SQLite autoincrement handles
    # this implicitly and needs no action.
    if op.get_bind().dialect.name == "postgresql":
        op.execute(
            sa.text(
                "SELECT setval(pg_get_serial_sequence('institutions', 'id'), "
                "(SELECT COALESCE(MAX(id), 1) FROM institutions))"
            )
        )
        op.execute(
            sa.text(
                "SELECT setval(pg_get_serial_sequence('campuses', 'id'), "
                "(SELECT COALESCE(MAX(id), 1) FROM campuses))"
            )
        )


def downgrade() -> None:
    op.drop_table("semesters")
    op.drop_table("branches")
    op.drop_table("programs")
    op.drop_table("departments")
    op.drop_table("schools")
    op.drop_table("campuses")
    op.drop_table("institutions")
