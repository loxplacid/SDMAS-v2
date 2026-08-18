"""Zero-fork extension architecture — tenant-scoped repository.

Every query is built through :class:`TenantScopedRepository`, which pins
``campus_id`` at query-construction time — a caller from campus A can never
read or mutate an extension definition, version, grant, or configuration
belonging to campus B.
"""

from __future__ import annotations

from typing import Optional, Sequence

from sqlalchemy.ext.asyncio import AsyncSession

from app.multi_tenant.models import TenantContext
from app.multi_tenant.repository import TenantScopedRepository
from app.platform.extensions.models import (
    ExtensionConfig,
    ExtensionDefinition,
    ExtensionGrant,
    ExtensionVersion,
)


class ExtensionRepository(TenantScopedRepository):
    """Tenant-scoped data access for the extension system."""

    def __init__(
        self,
        session: AsyncSession,
        tenant: Optional[TenantContext] = None,
    ) -> None:
        super().__init__(session, tenant)

    # ------------------------------------------------------------------
    # Definitions
    # ------------------------------------------------------------------

    async def create_definition(self, definition: ExtensionDefinition) -> ExtensionDefinition:
        self.session.add(definition)
        await self.session.flush()
        return definition

    async def get_definition(self, definition_id: int) -> Optional[ExtensionDefinition]:
        return await self.get_by_id(ExtensionDefinition, definition_id)

    async def get_definition_or_404(self, definition_id: int) -> ExtensionDefinition:
        return await self.get_by_id_or_404(ExtensionDefinition, definition_id, resource="extension")

    async def find_by_key(self, extension_id: str) -> Optional[ExtensionDefinition]:
        query = self.scoped_query(ExtensionDefinition).where(
            ExtensionDefinition.extension_id == extension_id
        )
        result = await self.session.execute(query.limit(1))
        return result.scalars().first()

    async def list_definitions(
        self,
        *,
        status: Optional[str] = None,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[ExtensionDefinition], int]:
        extra = [ExtensionDefinition.status == status] if status else None
        return await self._list_by_tenant(
            ExtensionDefinition,
            order_by_attr="extension_id",
            skip=skip,
            limit=limit,
            extra_filters=extra,
        )

    # ------------------------------------------------------------------
    # Versions
    # ------------------------------------------------------------------

    async def create_version(self, version: ExtensionVersion) -> ExtensionVersion:
        self.session.add(version)
        await self.session.flush()
        return version

    async def get_version(self, version_id: int) -> Optional[ExtensionVersion]:
        return await self.get_by_id(ExtensionVersion, version_id)

    async def get_version_or_404(self, version_id: int) -> ExtensionVersion:
        return await self.get_by_id_or_404(
            ExtensionVersion, version_id, resource="extension version"
        )

    async def list_versions(
        self,
        definition_id: int,
        *,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[ExtensionVersion], int]:
        definition = await self.get_definition_or_404(definition_id)
        extra = [ExtensionVersion.extension_def_id == definition.id]
        return await self._list_by_tenant(
            ExtensionVersion,
            order_by_attr="version",
            skip=skip,
            limit=limit,
            extra_filters=extra,
        )

    async def find_current_version(self, definition_id: int) -> Optional[ExtensionVersion]:
        query = self.scoped_query(ExtensionVersion).where(
            ExtensionVersion.extension_def_id == definition_id,
            ExtensionVersion.is_current.is_(True),
        )
        result = await self.session.execute(query.limit(1))
        return result.scalars().first()

    # ------------------------------------------------------------------
    # Grants
    # ------------------------------------------------------------------

    async def create_grant(self, grant: ExtensionGrant) -> ExtensionGrant:
        self.session.add(grant)
        await self.session.flush()
        return grant

    async def find_grant(self, definition_id: int, permission: str) -> Optional[ExtensionGrant]:
        """The active (non-revoked) grant for ``permission``, if any."""
        query = self.scoped_query(ExtensionGrant).where(
            ExtensionGrant.extension_def_id == definition_id,
            ExtensionGrant.permission == permission,
            ExtensionGrant.revoked_at.is_(None),
        )
        result = await self.session.execute(query.limit(1))
        return result.scalars().first()

    async def find_grant_any(self, definition_id: int, permission: str) -> Optional[ExtensionGrant]:
        """Any grant row for ``permission`` (including revoked ones) — lets
        a re-grant resurrect the original row instead of colliding on the
        ``(extension_def_id, permission)`` unique constraint."""
        query = self.scoped_query(ExtensionGrant).where(
            ExtensionGrant.extension_def_id == definition_id,
            ExtensionGrant.permission == permission,
        )
        result = await self.session.execute(query.limit(1))
        return result.scalars().first()

    async def list_active_grants(self, definition_id: int) -> Sequence[ExtensionGrant]:
        query = self.scoped_query(ExtensionGrant).where(
            ExtensionGrant.extension_def_id == definition_id,
            ExtensionGrant.revoked_at.is_(None),
        )
        result = await self.session.execute(query)
        return result.scalars().all()

    async def list_grants(
        self,
        definition_id: int,
        *,
        include_revoked: bool = False,
        skip: int = 0,
        limit: int = 100,
    ) -> tuple[Sequence[ExtensionGrant], int]:
        definition = await self.get_definition_or_404(definition_id)
        extra = [ExtensionGrant.extension_def_id == definition.id]
        if not include_revoked:
            extra.append(ExtensionGrant.revoked_at.is_(None))
        return await self._list_by_tenant(
            ExtensionGrant,
            order_by_attr="permission",
            skip=skip,
            limit=limit,
            extra_filters=extra,
        )

    # ------------------------------------------------------------------
    # Configuration
    # ------------------------------------------------------------------

    async def get_config(self, definition_id: int) -> Optional[ExtensionConfig]:
        query = self.scoped_query(ExtensionConfig).where(
            ExtensionConfig.extension_def_id == definition_id
        )
        result = await self.session.execute(query.limit(1))
        return result.scalars().first()

    async def upsert_config(self, config: ExtensionConfig) -> ExtensionConfig:
        existing = await self.get_config(config.extension_def_id)
        if existing is None:
            self.session.add(config)
        else:
            existing.config = config.config
            existing.schema_version = config.schema_version
            existing.updated_by = config.updated_by
        await self.session.flush()
        return existing or config


# Re-export for callers that only need the models.
__all__ = [
    "ExtensionConfig",
    "ExtensionDefinition",
    "ExtensionGrant",
    "ExtensionRepository",
    "ExtensionVersion",
]
