"""Zero-fork extension architecture — ORM models.

Four tenant-scoped tables implement the controlled extension system:

- ``extension_definitions`` — the registry entry: stable ``extension_id``
  business key, provider metadata, lifecycle status, and the core
  compatibility range the extension requires
- ``extension_versions``    — immutable snapshots of the extension's
  *manifest* (the full declared contract: permissions, routes, events,
  config schema, migrations, frontend, policy), versioned per extension
- ``extension_grants``      — the *approved* permissions.  An extension's
  manifest may only *declare* what it needs; nothing takes effect until an
  administrator grants each declared permission.  Enabling an extension
  fails while any declared permission is un-granted — extensions cannot
  grant themselves capabilities.
- ``extension_configs``     — the extension's configuration, validated
  against the config schema declared in the manifest's current version
  before it is stored

Tenancy: every table carries ``campus_id`` (direct tenant scoping — the
multi-tenant registry classifies them ``TENANT_DIRECT`` automatically).
"""

from __future__ import annotations

import datetime

from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.infrastructure.database import Base
from app.infrastructure.types import JSONType

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

#: Definition lifecycle.
EXT_STATUS_REGISTERED = "registered"
EXT_STATUS_INSTALLED = "installed"
EXT_STATUS_DISABLED = "disabled"
EXT_STATUS_RETIRED = "retired"
EXT_STATUSES = frozenset(
    {EXT_STATUS_REGISTERED, EXT_STATUS_INSTALLED, EXT_STATUS_DISABLED, EXT_STATUS_RETIRED}
)

#: Version lifecycle.
VER_STATUS_PENDING = "pending"
VER_STATUS_ENABLED = "enabled"
VER_STATUS_DISABLED = "disabled"
VER_STATUS_SUPERSEDED = "superseded"
VER_STATUSES = frozenset(
    {VER_STATUS_PENDING, VER_STATUS_ENABLED, VER_STATUS_DISABLED, VER_STATUS_SUPERSEDED}
)


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)


class ExtensionDefinition(Base):
    """A registered extension — one row per (campus, extension_id)."""

    __tablename__ = "extension_definitions"

    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    #: Stable business key — e.g. ``transport.rfid``.
    extension_id: Mapped[str] = mapped_column(String(80), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(String(1000), nullable=True)
    provider: Mapped[str] = mapped_column(String(255), nullable=False)
    homepage: Mapped[str | None] = mapped_column(String(500), nullable=True)
    license: Mapped[str | None] = mapped_column(String(100), nullable=True)
    #: Core compatibility range of the currently installed version.
    core_compat: Mapped[str | None] = mapped_column(String(120), nullable=True)
    current_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=EXT_STATUS_REGISTERED, index=True
    )
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    __table_args__ = (
        UniqueConstraint("campus_id", "extension_id", name="uq_extension_definition_key"),
    )

    def __repr__(self) -> str:
        return f"<ExtensionDefinition id={self.id} key={self.extension_id!r} status={self.status}>"


class ExtensionVersion(Base):
    """An immutable snapshot of an extension's manifest contract."""

    __tablename__ = "extension_versions"

    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    extension_def_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("extension_definitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    #: Semantic version string (e.g. ``1.2.0``).
    version: Mapped[str] = mapped_column(String(40), nullable=False)
    #: The full declared contract — validated against the closed catalogs
    #: before this row can exist.
    manifest: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    status: Mapped[str] = mapped_column(
        String(20), nullable=False, default=VER_STATUS_PENDING, index=True
    )
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    installed_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    installed_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    created_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    created_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )

    __table_args__ = (
        UniqueConstraint("extension_def_id", "version", name="uq_extension_version_number"),
    )

    def __repr__(self) -> str:
        return f"<ExtensionVersion id={self.id} ext={self.extension_def_id} v{self.version}>"


class ExtensionGrant(Base):
    """An approved permission — the authorization gate.

    Extensions declare what they need in their manifest; each declared
    permission must be granted here by an administrator before the
    extension can be enabled.  A grant is tenant-scoped, idempotent per
    (extension, permission), and revocable; revoking a permission that an
    enabled version requires automatically disables the extension.
    """

    __tablename__ = "extension_grants"

    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    extension_def_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("extension_definitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    #: e.g. ``students.read``.
    permission: Mapped[str] = mapped_column(String(80), nullable=False)
    #: Denormalized scope (``students`` from ``students.read``) for queries.
    scope: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    granted_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    granted_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    revoked_at: Mapped[datetime.datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    __table_args__ = (
        UniqueConstraint("extension_def_id", "permission", name="uq_extension_grant_permission"),
    )

    def __repr__(self) -> str:
        return f"<ExtensionGrant id={self.id} ext={self.extension_def_id} {self.permission}>"


class ExtensionConfig(Base):
    """The extension's configuration — validated against the manifest's
    config schema before it can be stored."""

    __tablename__ = "extension_configs"

    id: Mapped[int] = mapped_column(primary_key=True)
    campus_id: Mapped[int | None] = mapped_column(
        Integer, ForeignKey("campuses.id", ondelete="SET NULL"), nullable=True, index=True
    )
    extension_def_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("extension_definitions.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    #: Validated configuration values.
    config: Mapped[dict | None] = mapped_column(JSONType, nullable=True)
    #: The manifest version whose config_schema validated these values.
    schema_version: Mapped[str | None] = mapped_column(String(40), nullable=True)
    updated_by: Mapped[int | None] = mapped_column(Integer, nullable=True)
    validated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now
    )
    updated_at: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, default=_now, onupdate=_now
    )

    __table_args__ = (
        UniqueConstraint("extension_def_id", name="uq_extension_config_one_per_extension"),
        Index("ix_extension_configs_extension", "extension_def_id"),
    )

    def __repr__(self) -> str:
        return f"<ExtensionConfig id={self.id} ext={self.extension_def_id}>"
