from __future__ import annotations

import datetime
import enum

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Table,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.infrastructure.database import Base

# =====================================================================
# Association table: role ⇄ permission (many-to-many)
# =====================================================================

role_permissions = Table(
    "role_permissions",
    Base.metadata,
    Column(
        "role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True
    ),
    Column(
        "permission_id",
        Integer,
        ForeignKey("permissions.id", ondelete="CASCADE"),
        primary_key=True,
    ),
)


# =====================================================================
# Association table: user ⇄ role (many-to-many)
# =====================================================================

user_roles = Table(
    "user_roles",
    Base.metadata,
    Column("user_id", Integer, ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
    Column("role_id", Integer, ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
)


# =====================================================================
# Refresh Token (for rotation / reuse detection)
# =====================================================================


class UserSchoolMembership(Base):
    """Membership linking a user to a school (campus) within an
    organization (institution).

    A user may belong to one or more schools. Exactly one membership per
    user can be marked ``is_default`` (the active school context). The
    user's active school is also mirrored on ``users.campus_id`` for
    backward compatibility with the JWT claim and existing queries.
    """

    __tablename__ = "user_school_memberships"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "campus_id", name="uq_user_school_membership"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    campus_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(
        String(50), nullable=False, default="staff"
    )
    is_default: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        onupdate=lambda: datetime.datetime.now(datetime.timezone.utc),
    )

    user: Mapped[User] = relationship(
        "User", back_populates="school_memberships",
        foreign_keys=[user_id],
    )

    def __repr__(self) -> str:
        return (
            f"<UserSchoolMembership user={self.user_id} "
            f"campus={self.campus_id} default={self.is_default}>"
        )


class AssignmentNodeType(str, enum.Enum):
    """The organization-hierarchy node a user may be administratively
    assigned to.

    Distinct from :class:`UserSchoolMembership`, which models the active
    *school* a user operates in.  An assignment authorizes administration
    over a whole subtree of the enterprise hierarchy:

    - ``ORGANIZATION`` — organization administrator (all groups/regions/
      campuses/departments under one legal organization).
    - ``GROUP`` — school-group administrator (all regions/campuses under
      one school group).
    - ``REGION`` — region administrator (all campuses under one region).
    - ``CAMPUS`` — campus administrator (one campus).  Kept here so the
      same assignment flow can express campus-level administration
      explicitly.
    """

    ORGANIZATION = "organization"
    GROUP = "group"
    REGION = "region"
    CAMPUS = "campus"


class OrganizationAssignment(Base):
    """Administrative assignment of a user to a node of the enterprise
    organization hierarchy (organization → school group → region → campus).

    A hierarchy assignment grants cross-campus administration **within the
    assigned subtree only**.  It is the *only* sanctioned way an admin may
    operate across campuses without an explicit platform grant: the
    resolved tenant context is scoped to the subtree (see
    ``multi_tenant.dependencies.resolve_tenant_context``), and the
    repository filters every query to the subtree's campuses.  A user with
    no assignment remains strictly campus-scoped.

    Cross-subtree and cross-organization access is denied even for
    organization administrators.
    """

    __tablename__ = "organization_assignments"
    __table_args__ = (
        UniqueConstraint(
            "user_id", "node_type", "node_id", name="uq_org_assignment"
        ),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    node_type: Mapped[str] = mapped_column(
        String(20), nullable=False, default=AssignmentNodeType.CAMPUS.value
    )
    node_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    role: Mapped[str] = mapped_column(
        String(50), nullable=False, default="admin"
    )
    is_active: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        onupdate=lambda: datetime.datetime.now(datetime.timezone.utc),
    )

    def __repr__(self) -> str:
        return (
            f"<OrganizationAssignment user={self.user_id} "
            f"node={self.node_type}:{self.node_id} role={self.role}>"
        )


class RefreshToken(Base):
    """Stores a hash of each issued refresh token for rotation and
    reuse detection.

    On every token refresh:
    1. The incoming token is validated against its stored hash.
    2. The old token is marked as revoked (``replaced_by`` points to
       the new token's hash).
    3. A new token is issued and its hash is stored.

    If a revoked token is presented (reuse attack), ALL refresh tokens
    for that user are revoked (family rotation) to contain the damage.
    """

    __tablename__ = "refresh_tokens"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    token_hash: Mapped[str] = mapped_column(
        String(64), nullable=False, unique=True, index=True
    )
    expires_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, index=True
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )
    is_revoked: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=False, index=True
    )
    revoked_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    replaced_by_token_hash: Mapped[str | None] = mapped_column(
        String(64), nullable=True
    )

    def __repr__(self) -> str:
        return (
            f"<RefreshToken id={self.id} user_id={self.user_id} "
            f"revoked={self.is_revoked}>"
        )


# =====================================================================
# Permission
# =====================================================================


class Permission(Base):
    """A granular permission like ``students.create`` or ``fees.export``.

    Permissions are seeded from ``app.domains.auth.permissions.ALL_PERMISSIONS``
    and never modified at runtime (new permissions are added via code
    changes + migrations).
    """

    __tablename__ = "permissions"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(
        String(100), nullable=False, unique=True, index=True
    )
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )

    def __repr__(self) -> str:
        return f"<Permission id={self.id} code={self.code}>"


# =====================================================================
# Role (system-defined, stored in DB for mapping)
# =====================================================================


class Role(Base):
    """A named role that bundles permissions (e.g. ``admin``, ``teacher``).

    The ``code`` field matches the ``role`` field on the ``User`` model.
    Permissions are assigned via the ``role_permissions`` association table.
    Users are linked via the ``user_roles`` association table.
    """

    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(primary_key=True)
    code: Mapped[str] = mapped_column(
        String(50), nullable=False, unique=True, index=True
    )
    label: Mapped[str] = mapped_column(String(100), nullable=False)
    description: Mapped[str | None] = mapped_column(String(255), nullable=True)
    is_system: Mapped[bool] = mapped_column(
        Boolean, nullable=False, default=True,
        comment="System roles cannot be deleted or have their code changed",
    )
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )

    # M2M: permissions assigned to this role
    permissions: Mapped[list[Permission]] = relationship(
        "Permission", secondary=role_permissions, lazy="selectin",
    )

    # M2M: users assigned this role
    users: Mapped[list[User]] = relationship(
        "User", secondary=user_roles, lazy="selectin", back_populates="assigned_roles",
    )

    def __repr__(self) -> str:
        return f"<Role id={self.id} code={self.code}>"


# =====================================================================
# User
# =====================================================================


class User(Base):
    __tablename__ = "users"

    id: Mapped[int] = mapped_column(primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    username: Mapped[str] = mapped_column(String(100), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True
    )
    display_name: Mapped[str] = mapped_column(String(200), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False, default="staff")
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.datetime.now(datetime.timezone.utc),
        onupdate=lambda: datetime.datetime.now(datetime.timezone.utc),
    )

    # M2M: roles assigned to this user
    assigned_roles: Mapped[list[Role]] = relationship(
        "Role", secondary=user_roles, lazy="selectin", back_populates="users",
    )

    # School memberships (which campuses this user belongs to)
    school_memberships: Mapped[list[UserSchoolMembership]] = relationship(
        "UserSchoolMembership",
        back_populates="user",
        lazy="selectin",
        cascade="all, delete-orphan",
        foreign_keys="UserSchoolMembership.user_id",
    )

    @property
    def role_codes(self) -> list[str]:
        """Return all role codes for this user, including the primary role.

        The primary ``role`` field is always included as the first entry.
        Additional roles come from the ``assigned_roles`` M2M relationship.
        """
        codes = [self.role]
        if self.assigned_roles:
            for r in self.assigned_roles:
                if r.code not in codes:
                    codes.append(r.code)
        return codes

    @property
    def roles(self) -> list[str]:
        """Return all role codes for serialization (includes primary role).

        Mirrors the ``role_codes`` property but is named to match the
        ``UserResponse.roles`` schema field for Pydantic model_validate.
        """
        return self.role_codes

    def __repr__(self) -> str:
        return f"<User id={self.id} username={self.username} role={self.role}>"
