from __future__ import annotations

import datetime
from datetime import timezone
from typing import Optional

from sqlalchemy import DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base


class Institution(Base):
    """Top-level organization (e.g., 'SDMAS School District').

    This is the **legal organization** in the enterprise hierarchy.  The
    tenant (data-isolation) unit is deliberately NOT the institution: a
    legal organization may span many school groups, regions and campuses,
    and each campus remains its own isolated tenant.  Cross-organization
    access is forbidden even for organization administrators.
    """
    __tablename__ = "institutions"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False, unique=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
        onupdate=lambda: datetime.datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<Institution id={self.id} name={self.name} code={self.code}>"


class SchoolGroup(Base):
    """A named group of regions/campuses within an organization.

    Example: "SDMAS West District" — an operating unit that groups several
    regions and their campuses under one administrator.  A school group is
    NOT a tenant unit; it is an organizational aggregation *above* the
    campus so that group administrators can operate across their group's
    campuses without leaving their organization boundary.
    """
    __tablename__ = "school_groups"

    id: Mapped[int] = mapped_column(primary_key=True)
    institution_id: Mapped[int] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
        onupdate=lambda: datetime.datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<SchoolGroup id={self.id} name={self.name} code={self.code}>"


class Region(Base):
    """A geographic region containing one or more campuses.

    A region normally belongs to a :class:`SchoolGroup`; it may also hang
    directly off an organization (``school_group_id`` is nullable) when the
    organization does not model groups.  A region is NOT a tenant unit —
    its campuses remain individual tenants.
    """
    __tablename__ = "regions"

    id: Mapped[int] = mapped_column(primary_key=True)
    school_group_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("school_groups.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    institution_id: Mapped[int] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
        onupdate=lambda: datetime.datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<Region id={self.id} name={self.name} code={self.code}>"


class Campus(Base):
    """Physical or virtual campus belonging to an Institution.

    The campus is the **tenant (data-isolation) unit** of SDMAS.  Every
    tenant-owned row carries ``campus_id`` and the multi-tenant framework
    pins all queries to it.  ``region_id`` / ``school_group_id`` are
    nullable organizational links used by group/region/organization
    administrators to operate across their subtree — they never weaken the
    per-campus isolation boundary.
    """
    __tablename__ = "campuses"

    id: Mapped[int] = mapped_column(primary_key=True)
    institution_id: Mapped[int] = mapped_column(
        ForeignKey("institutions.id", ondelete="CASCADE"), nullable=False, index=True
    )
    school_group_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("school_groups.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    region_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("regions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    address: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    phone: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    email: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
        onupdate=lambda: datetime.datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<Campus id={self.id} name={self.name} code={self.code}>"


class School(Base):
    """A school within a campus (e.g., School of Science)."""
    __tablename__ = "schools"

    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int] = mapped_column(
        ForeignKey("campuses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
        onupdate=lambda: datetime.datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<School id={self.id} name={self.name} code={self.code}>"


class Department(Base):
    """Department within a school (e.g., Computer Science Dept).

    ``campus_id`` is a denormalized reference to the department's campus
    (derived from the school chain) so department-scoped authorization and
    hierarchy resolution do not require a join through ``School``.  It is
    nullable only for legacy rows and is backfilled by migration 063.
    """
    __tablename__ = "departments"

    id: Mapped[int] = mapped_column(primary_key=True)
    school_id: Mapped[int] = mapped_column(
        ForeignKey("schools.id", ondelete="CASCADE"), nullable=False, index=True
    )
    campus_id: Mapped[Optional[int]] = mapped_column(
        ForeignKey("campuses.id", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
        onupdate=lambda: datetime.datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<Department id={self.id} name={self.name} code={self.code}>"


class Program(Base):
    """A program of study (e.g., BSc Computer Science)."""
    __tablename__ = "programs"

    id: Mapped[int] = mapped_column(primary_key=True)
    department_id: Mapped[int] = mapped_column(
        ForeignKey("departments.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    duration_years: Mapped[int] = mapped_column(Integer, nullable=False, default=4)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
        onupdate=lambda: datetime.datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<Program id={self.id} name={self.name} code={self.code}>"


class Branch(Base):
    """Specialization or track within a program (e.g., Data Science track)."""
    __tablename__ = "branches"

    id: Mapped[int] = mapped_column(primary_key=True)
    program_id: Mapped[int] = mapped_column(
        ForeignKey("programs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
        onupdate=lambda: datetime.datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<Branch id={self.id} name={self.name} code={self.code}>"


class Semester(Base):
    """Semester within a program's academic calendar."""
    __tablename__ = "semesters"

    id: Mapped[int] = mapped_column(primary_key=True)
    program_id: Mapped[int] = mapped_column(
        ForeignKey("programs.id", ondelete="CASCADE"), nullable=False, index=True
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    code: Mapped[str] = mapped_column(String(50), nullable=False)
    semester_number: Mapped[int] = mapped_column(Integer, nullable=False)
    start_date: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    end_date: Mapped[Optional[str]] = mapped_column(String(10), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default="active"
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(timezone.utc),
        onupdate=lambda: datetime.datetime.now(timezone.utc),
    )

    def __repr__(self) -> str:
        return (
            f"<Semester id={self.id} name={self.name} "
            f"code={self.code} num={self.semester_number}>"
        )
