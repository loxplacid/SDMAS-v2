"""Change envelope — the per-version change record (M1).

Every history version carries a ``change`` payload describing exactly what
changed: the old value, the new value, the wall-clock timestamp, the actor,
the reason, and the transaction id. This is the data structure that makes
diff visualization and audit reconstruction trivial — one row, no replay.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass
from datetime import datetime
from typing import Any, Optional

from .context import now_utc

__all__ = ["ChangeEnvelope", "CHANGE_KIND"]


class CHANGE_KIND:
    """Semantic kind of the change (mirrors audit vocabulary)."""

    CREATE = "create"
    UPDATE = "update"
    DELETE = "delete"
    UNDO = "undo"
    REDO = "redo"
    RESTORE = "restore"


@dataclass
class ChangeEnvelope:
    """Structured record of one version change.

    Attributes:
        kind: CHANGE_KIND.* value.
        old: full prior state (dict) or None on create.
        new: full new state (dict) or None on delete.
        changed_at: wall-clock timestamp of the change.
        actor_id: actor that performed the change (user/worker/system).
        reason: human-readable reason; None for automatic/trivial changes.
        txn_id: the transaction log id this change was committed with.
        valid_from / valid_to: the valid-time range of the new version.
    """

    kind: str
    old: Optional[dict[str, Any]]
    new: Optional[dict[str, Any]]
    changed_at: datetime
    actor_id: Optional[int] = None
    reason: Optional[str] = None
    txn_id: Optional[int] = None
    valid_from: Optional[datetime] = None
    valid_to: Optional[datetime] = None

    @classmethod
    def build(
        cls,
        kind: str,
        old: Optional[dict[str, Any]],
        new: Optional[dict[str, Any]],
        *,
        actor_id: Optional[int] = None,
        reason: Optional[str] = None,
        txn_id: Optional[int] = None,
        valid_from: Optional[datetime] = None,
        valid_to: Optional[datetime] = None,
        changed_at: Optional[datetime] = None,
    ) -> "ChangeEnvelope":
        """Construct an envelope with the canonical clock default."""
        return cls(
            kind=kind,
            old=old,
            new=new,
            changed_at=changed_at or now_utc(),
            actor_id=actor_id,
            reason=reason,
            txn_id=txn_id,
            valid_from=valid_from,
            valid_to=valid_to,
        )

    # ------------------------------------------------------------------
    # Serialization
    # ------------------------------------------------------------------

    def to_json(self) -> str:
        """Serialize to JSON (stored in the history ``change`` column)."""
        return json.dumps(self.to_dict(), default=_json_default)

    def to_dict(self) -> dict[str, Any]:
        """Dict form, JSON-safe."""
        data = asdict(self)
        return data

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "ChangeEnvelope":
        """Rehydrate from a dict (JSON round-trip)."""
        known = {f: data[f] for f in cls.__dataclass_fields__ if f in data}
        return cls(**known)

    @classmethod
    def from_json(cls, raw: str) -> "ChangeEnvelope":
        """Rehydrate from a JSON string."""
        return cls.from_dict(json.loads(raw))

    # ------------------------------------------------------------------
    # Diff helpers (used by the version-comparison UI, M4)
    # ------------------------------------------------------------------

    def field_diff(self) -> dict[str, dict[str, Any]]:
        """Field-level diff between old and new state.

        Returns ``{field: {"old": ..., "new": ...}}`` for every field that
        differs (plus additions/removals). ``None`` states are treated as
        "the field did not exist".
        """
        old = self.old or {}
        new = self.new or {}
        result: dict[str, dict[str, Any]] = {}
        for key in set(old) | set(new):
            if old.get(key) != new.get(key):
                result[key] = {"old": old.get(key), "new": new.get(key)}
        return result


def _json_default(obj: Any) -> Any:
    if isinstance(obj, datetime):
        return obj.isoformat()
    raise TypeError(f"Object of type {type(obj).__name__} is not JSON serializable")
