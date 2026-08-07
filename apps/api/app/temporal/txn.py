"""Close-open transaction manager (The Archive, M1).

A temporal write performs three statements inside the caller's
transaction:

1. **close** — copy the current open version into the history mirror with
   ``tt_to`` set to the transaction instant (updates and deletes);
2. **open** — write the new open version into the current table with
   ``tt_from`` set to the transaction instant and ``tt_to`` NULL;
3. **log** — append the ``txn_log`` row carrying the ChangeEnvelope.

The caller owns the transaction boundary: the three statements commit
together (``session.commit()``) or vanish together (rollback). The
fault-injection test proves that no partial temporal state can persist.
"""

from __future__ import annotations

import logging
from collections.abc import Callable
from datetime import datetime
from typing import Any

from sqlalchemy import delete, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.infrastructure.database import Base

from .context import now_utc
from .envelope import CHANGE_KIND, ChangeEnvelope
from .registry import TemporalError, TemporalTableRegistry, registry

logger = logging.getLogger(__name__)

Clock = Callable[[], datetime]


class TxnManager:
    """Executes close-open temporal writes and records them in txn_log."""

    def __init__(
        self,
        table_registry: TemporalTableRegistry | None = None,
        *,
        clock: Clock | None = None,
    ) -> None:
        self.registry = table_registry or registry
        self._clock: Clock = clock or now_utc

    # ------------------------------------------------------------------
    # Public write API
    # ------------------------------------------------------------------

    async def create(
        self,
        session: AsyncSession,
        table_name: str,
        values: dict[str, Any],
        *,
        actor_id: int | None = None,
        actor_type: str | None = None,
        reason: str | None = None,
        tenant_id: int | None = None,
        campus_id: int | None = None,
    ) -> int:
        """Create a row: open its first version and log a ``create`` txn."""
        return await self._commit(
            session,
            table_name,
            CHANGE_KIND.CREATE,
            row_id=None,
            values=values,
            actor_id=actor_id,
            actor_type=actor_type,
            reason=reason,
            tenant_id=tenant_id,
            campus_id=campus_id,
        )

    async def update(
        self,
        session: AsyncSession,
        table_name: str,
        row_id: int,
        values: dict[str, Any],
        *,
        actor_id: int | None = None,
        actor_type: str | None = None,
        reason: str | None = None,
        tenant_id: int | None = None,
        campus_id: int | None = None,
    ) -> int:
        """Update a row: close its open version, open a new one, log it."""
        return await self._commit(
            session,
            table_name,
            CHANGE_KIND.UPDATE,
            row_id=row_id,
            values=values,
            actor_id=actor_id,
            actor_type=actor_type,
            reason=reason,
            tenant_id=tenant_id,
            campus_id=campus_id,
        )

    async def delete(
        self,
        session: AsyncSession,
        table_name: str,
        row_id: int,
        *,
        actor_id: int | None = None,
        actor_type: str | None = None,
        reason: str | None = None,
        tenant_id: int | None = None,
        campus_id: int | None = None,
    ) -> int:
        """Delete a row: close its open version, remove it, log it."""
        return await self._commit(
            session,
            table_name,
            CHANGE_KIND.DELETE,
            row_id=row_id,
            values=None,
            actor_id=actor_id,
            actor_type=actor_type,
            reason=reason,
            tenant_id=tenant_id,
            campus_id=campus_id,
        )

    # ------------------------------------------------------------------
    # The close-open write
    # ------------------------------------------------------------------

    async def _commit(
        self,
        session: AsyncSession,
        table_name: str,
        kind: str,
        *,
        row_id: int | None,
        values: dict[str, Any] | None,
        actor_id: int | None,
        actor_type: str | None,
        reason: str | None,
        tenant_id: int | None,
        campus_id: int | None,
    ) -> int:
        spec = self.registry.require(table_name)
        if spec.current not in Base.metadata.tables:
            raise TemporalError(
                f"current table {spec.current!r} has no metadata; define the ORM model first"
            )
        current = Base.metadata.tables[spec.current]
        history = Base.metadata.tables[spec.history]
        txn_ts = self._clock()

        if kind == CHANGE_KIND.CREATE:
            row = dict(values or {})
            row[spec.tt_from] = txn_ts
            row[spec.tt_to] = None
            res = await session.execute(current.insert().values(**row))
            new_row_id = int(res.inserted_primary_key[0])
            old_state: dict[str, Any] | None = None
            new_state = row
        else:
            if row_id is None:
                raise TemporalError(f"{kind} requires a row id")
            stmt = select(current).where(current.c[spec.id_column] == row_id)
            existing = (await session.execute(stmt)).mappings().first()
            if existing is None:
                raise TemporalError(f"no row with {spec.id_column}={row_id!r} in {spec.current}")
            old_state = dict(existing)
            await self._close_version(session, spec, history, old_state, txn_ts)
            if kind == CHANGE_KIND.UPDATE:
                new_state = dict(old_state)
                new_state.update(values or {})
                new_state.pop(spec.id_column, None)  # identity is immutable
                new_state[spec.tt_from] = txn_ts
                new_state[spec.tt_to] = None
                await session.execute(
                    update(current).where(current.c[spec.id_column] == row_id).values(**new_state)
                )
                new_row_id = row_id
            elif kind == CHANGE_KIND.DELETE:
                await session.execute(delete(current).where(current.c[spec.id_column] == row_id))
                new_row_id = row_id
                new_state = None
            else:
                raise TemporalError(f"unsupported change kind {kind!r}")

        envelope = ChangeEnvelope.build(
            kind,
            old_state,
            new_state,
            actor_id=actor_id,
            reason=reason,
            changed_at=txn_ts,
        )
        txn_log = Base.metadata.tables["txn_log"]
        return await self._append_txn_log(
            session,
            txn_log,
            {
                "txn_ts": txn_ts,
                "entity_type": table_name,
                "entity_id": str(new_row_id),
                "action": kind,
                "actor_type": actor_type,
                "actor_id": actor_id,
                "reason": reason,
                "tenant_id": tenant_id,
                "campus_id": campus_id,
                "change": envelope.to_dict(),
            },
        )

    # ------------------------------------------------------------------
    # Injectable statement hooks (fault-injection seams)
    # ------------------------------------------------------------------

    async def _close_version(
        self,
        session: AsyncSession,
        spec: Any,
        history: Any,
        current_row: dict[str, Any],
        txn_ts: datetime,
    ) -> None:
        """Copy the open version into the history mirror, closed at txn_ts."""
        closed = dict(current_row)
        closed[spec.tt_to] = txn_ts
        if "entity_id" in history.c and spec.id_column in closed:
            closed["entity_id"] = closed.pop(spec.id_column)
        await session.execute(history.insert().values(**closed))

    async def _append_txn_log(
        self,
        session: AsyncSession,
        txn_log: Any,
        payload: dict[str, Any],
    ) -> int:
        """Append a txn_log row — the last statement of a close-open write."""
        res = await session.execute(txn_log.insert().values(**payload))
        return int(res.inserted_primary_key[0])
