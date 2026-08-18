"""Tamper-evident audit chain — application service.

- ``append_for_audit`` — add a chain entry for one audit event (idempotent
  per audit log; non-fatal failures are logged, never fail the caller)
- ``checkpoint`` — sign the chain state up to the current head
- ``verify`` — run the pure verifier over the caller's campus chain
- ``verify_platform`` — verify the platform chain (campus_id NULL)

Writes are keyed by the *audit event's* campus (a platform write that
records a campus-scoped event chains into that campus's chain); reads are
tenant-scoped through the repository.
"""

from __future__ import annotations

import datetime
import logging
from typing import Optional

from sqlalchemy.ext.asyncio import AsyncSession

from app.domains.audit.models import AuditLog
from app.multi_tenant.models import TenantContext
from app.platform.cryptography.chain import (
    chain_hash,
    checkpoint_state_hash,
    hmac_sign,
    payload_digest,
)
from app.platform.cryptography.models import (
    AuditChainCheckpoint,
    AuditChainEntry,
)
from app.platform.cryptography.repository import AuditChainRepository
from app.platform.cryptography.verifier import ChainVerification, verify_chain

logger = logging.getLogger(__name__)


class AuditChainService:
    """Tamper-evident chain operations (one tenant per instance)."""

    def __init__(
        self,
        session: AsyncSession,
        tenant: Optional[TenantContext] = None,
        secret: Optional[str] = None,
    ) -> None:
        self.session = session
        self.tenant = tenant
        self.repo = AuditChainRepository(session, tenant)
        self.secret = secret

    # ------------------------------------------------------------------
    # Append
    # ------------------------------------------------------------------

    async def append_for_audit(
        self, entry: AuditLog, secret: Optional[str] = None
    ) -> Optional[AuditChainEntry]:
        """Add the chain entry covering one audit event.

        Idempotent: an audit log has at most one chain entry (unique
        ``audit_log_id``) — re-appending returns the existing entry.

        **Non-fatal by design**: the audit event itself must never be lost
        because chaining failed.  Failures are logged and ``None`` is
        returned; the verifier reports such rows as uncovered.
        """
        existing = await self.repo.entry_for_audit(entry.id)
        if existing is not None:
            return existing
        campus_id = entry.campus_id
        last = await self.repo.last_entry(campus_id)
        prev_hash = last.current_hash if last is not None else ""
        index = last.chain_index + 1 if last is not None else 0
        payload = payload_digest(entry)
        current = chain_hash(prev_hash, payload, campus_id, index)
        sig = hmac_sign(current, secret if secret is not None else self.secret)
        chain_entry = AuditChainEntry(
            campus_id=campus_id,
            audit_log_id=entry.id,
            chain_index=index,
            prev_hash=prev_hash,
            payload_hash=payload,
            current_hash=current,
            signature=sig,
        )
        try:
            return await self.repo.create_entry(chain_entry)
        except Exception:  # pragma: no cover - defensive
            logger.exception(
                "audit chain append failed for audit_log_id=%s (non-fatal)",
                entry.id,
            )
            return None

    async def append_for_audit_ids(
        self, audit_ids: list[int], actor: Optional[object] = None
    ) -> int:
        """Backfill chain entries for existing audit rows (one per row).

        Used to chain rows that were recorded before the chain was enabled
        or whose append previously failed.  Returns the number appended.
        """
        from sqlalchemy import select

        appended = 0
        for audit_id in audit_ids:
            result = await self.session.execute(select(AuditLog).where(AuditLog.id == audit_id))
            row = result.scalars().first()
            if row is None:
                continue
            if await self.repo.entry_for_audit(audit_id) is None:
                if await self.append_for_audit(row) is not None:
                    appended += 1
        return appended

    # ------------------------------------------------------------------
    # Checkpoints
    # ------------------------------------------------------------------

    async def checkpoint(
        self,
        campus_id: int | None = None,
        created_by: Optional[int] = None,
        secret: Optional[str] = None,
    ) -> AuditChainCheckpoint:
        """Sign the chain state up to the current head for a campus."""
        target_campus = (
            campus_id if campus_id is not None else (self.tenant.campus_id if self.tenant else None)
        )
        entries = await self.repo.list_entries(target_campus)
        if not entries:
            raise ValueError("cannot checkpoint an empty chain")
        head_index = entries[-1].chain_index
        state_hash = checkpoint_state_hash([e.current_hash for e in entries])
        sig = hmac_sign(
            f"{state_hash}|{target_campus if target_campus is not None else ''}|{head_index}",
            secret if secret is not None else self.secret,
        )
        return await self.repo.create_checkpoint(
            AuditChainCheckpoint(
                campus_id=target_campus,
                up_to_chain_index=head_index,
                state_hash=state_hash,
                signature=sig,
                created_by=created_by,
            )
        )

    # ------------------------------------------------------------------
    # Verification
    # ------------------------------------------------------------------

    async def verify(self, secret: Optional[str] = None) -> ChainVerification:
        """Verify the caller's campus chain (tenant-scoped)."""
        return await self._verify_campus(
            self.tenant.campus_id if self.tenant else None,
            secret=secret,
        )

    async def verify_campus(
        self, campus_id: int | None, secret: Optional[str] = None
    ) -> ChainVerification:
        """Verify an explicit campus chain (platform readers)."""
        return await self._verify_campus(campus_id, secret=secret)

    async def _verify_campus(
        self, campus_id: int | None, secret: Optional[str] = None
    ) -> ChainVerification:
        from sqlalchemy import select

        entries = await self.repo.list_entries(campus_id)
        checkpoints = await self.repo.list_checkpoints(campus_id)
        result = await self.session.execute(select(AuditLog).where(AuditLog.campus_id == campus_id))
        audit_rows = list(result.scalars().all())
        return verify_chain(
            entries=entries,
            checkpoints=checkpoints,
            audit_rows=audit_rows,
            campus_id=campus_id,
            secret=secret if secret is not None else self.secret,
        )


def _now() -> datetime.datetime:
    return datetime.datetime.now(datetime.timezone.utc)
