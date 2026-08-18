"""Zero-fork extension architecture — Pydantic schemas (API contract)."""

from __future__ import annotations

import datetime
from typing import Any, Optional

from pydantic import BaseModel, ConfigDict, Field

from app.platform.extensions.models import (
    EXT_STATUSES,
    VER_STATUSES,
)
from app.platform.extensions.registry import (
    PERMISSION_ACTIONS,
    PERMISSION_SCOPES,
)

# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------


class ExtensionIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")

    extension_id: str = Field(min_length=3, max_length=80, pattern=r"^[a-z][a-z0-9._-]{2,79}$")
    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=500)
    provider: str = Field(min_length=1, max_length=255)
    homepage: Optional[str] = Field(default=None, max_length=500)
    license: Optional[str] = Field(default=None, max_length=100)
    #: Semantic version of the extension itself.
    version: str = Field(min_length=1, max_length=40)
    #: Core compatibility range, e.g. ``>=0.1.0,<1.0.0``.
    core_compat: str = Field(min_length=1, max_length=120)


# ---------------------------------------------------------------------------
# Declared capabilities
# ---------------------------------------------------------------------------


class PermissionRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    permission: str = Field(min_length=1, max_length=80)
    reason: Optional[str] = Field(default=None, max_length=500)


class RouteDeclaration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    method: str = Field(min_length=3, max_length=8)
    path: str = Field(min_length=1, max_length=500)
    description: Optional[str] = Field(default=None, max_length=500)


class EventSubscription(BaseModel):
    model_config = ConfigDict(extra="forbid")

    subscribe: str = Field(min_length=1, max_length=120)
    handler: str = Field(min_length=1, max_length=255)


class FrontendRegistration(BaseModel):
    model_config = ConfigDict(extra="forbid")

    entrypoint: str = Field(min_length=1, max_length=255)
    routes: list[dict[str, Any]] = Field(default_factory=list)
    menu: list[dict[str, Any]] = Field(default_factory=list)


class PolicyRequirement(BaseModel):
    model_config = ConfigDict(extra="forbid")

    scope: str = Field(min_length=1, max_length=40)
    policy_id: Optional[str] = Field(default=None, max_length=200)


class ExtensionManifest(BaseModel):
    """The full declared contract of an extension version.

    ``extra="forbid"`` everywhere — an unknown section or field is a
    contract violation, not something to silently ignore.
    """

    model_config = ConfigDict(extra="forbid")

    identity: ExtensionIdentity
    permissions: list[PermissionRequirement] = Field(default_factory=list)
    routes: list[RouteDeclaration] = Field(default_factory=list)
    events: list[EventSubscription] = Field(default_factory=list)
    config_schema: Optional[dict[str, Any]] = None
    migrations: list[str] = Field(default_factory=list)
    frontend: Optional[FrontendRegistration] = None
    policy: Optional[PolicyRequirement] = None


# ---------------------------------------------------------------------------
# Lifecycle operations
# ---------------------------------------------------------------------------


class ExtensionRegister(BaseModel):
    model_config = ConfigDict(extra="forbid")

    extension_id: str = Field(min_length=3, max_length=80, pattern=r"^[a-z][a-z0-9._-]{2,79}$")
    name: str = Field(min_length=1, max_length=255)
    description: Optional[str] = Field(default=None, max_length=1000)
    provider: str = Field(min_length=1, max_length=255)
    homepage: Optional[str] = Field(default=None, max_length=500)
    license: Optional[str] = Field(default=None, max_length=100)
    created_by: Optional[int] = None


class ExtensionVersionPublish(BaseModel):
    model_config = ConfigDict(extra="forbid")

    manifest: ExtensionManifest
    created_by: Optional[int] = None


class ExtensionEnable(BaseModel):
    model_config = ConfigDict(extra="forbid")

    version_id: Optional[int] = None
    actor_user_id: Optional[int] = None


class GrantCreate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    permission: str = Field(min_length=1, max_length=80)
    granted_by: Optional[int] = None


class ConfigUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")

    config: dict[str, Any]
    updated_by: Optional[int] = None


# ---------------------------------------------------------------------------
# Reads
# ---------------------------------------------------------------------------


class ExtensionDefinitionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campus_id: Optional[int] = None
    extension_id: str
    name: str
    description: Optional[str] = None
    provider: str
    homepage: Optional[str] = None
    license: Optional[str] = None
    core_compat: Optional[str] = None
    current_version: Optional[str] = None
    status: str
    created_by: Optional[int] = None
    created_at: datetime.datetime


class ExtensionVersionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campus_id: Optional[int] = None
    extension_def_id: int
    version: str
    manifest: Optional[dict[str, Any]] = None
    status: str
    is_current: bool
    installed_by: Optional[int] = None
    installed_at: Optional[datetime.datetime] = None
    created_by: Optional[int] = None
    created_at: datetime.datetime


class ExtensionGrantRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campus_id: Optional[int] = None
    extension_def_id: int
    permission: str
    scope: str
    granted_by: Optional[int] = None
    granted_at: datetime.datetime
    revoked_at: Optional[datetime.datetime] = None


class ExtensionConfigRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    campus_id: Optional[int] = None
    extension_def_id: int
    config: Optional[dict[str, Any]] = None
    schema_version: Optional[str] = None
    updated_by: Optional[int] = None
    validated_at: datetime.datetime


class ExtensionCompatibility(BaseModel):
    """Result of a core-compatibility check against an extension range."""

    extension_id: str
    declared_range: Optional[str] = None
    core_version: str
    satisfied: bool


__all__ = [
    "ExtensionIdentity",
    "PermissionRequirement",
    "RouteDeclaration",
    "EventSubscription",
    "FrontendRegistration",
    "PolicyRequirement",
    "ExtensionManifest",
    "ExtensionRegister",
    "ExtensionVersionPublish",
    "ExtensionEnable",
    "GrantCreate",
    "ConfigUpdate",
    "ExtensionDefinitionRead",
    "ExtensionVersionRead",
    "ExtensionGrantRead",
    "ExtensionConfigRead",
    "ExtensionCompatibility",
    "EXT_STATUSES",
    "VER_STATUSES",
    "PERMISSION_SCOPES",
    "PERMISSION_ACTIONS",
]
