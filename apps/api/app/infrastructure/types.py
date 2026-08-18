"""Shared infrastructure SQLAlchemy type decorators.

``JSONType`` is the canonical JSON column type for both PostgreSQL (JSONB)
and SQLite (text-based JSON).  It previously lived in
``app.domains.jobs.models`` and was copied into ``app.domains.events.outbox``
and imported cross-domain by ``billing.models`` / ``migration.models`` —
consolidating it here removes the duplicated implementations and the
``billing -> jobs`` cross-domain import edge.
"""

from __future__ import annotations

import json
from typing import Any, Callable

from sqlalchemy import TypeDecorator
from sqlalchemy.dialects.postgresql import JSONB


class _JSON(TypeDecorator):
    """Portable JSON — JSONB on PostgreSQL, JSON on every other dialect."""

    impl = JSONB

    # The type's only state is the optional ``json_default`` callable
    # (stable per instance), so compiled-statement cache keys are safe.
    cache_ok = True

    def __init__(
        self,
        json_default: Callable[[Any], Any] | None = None,
    ) -> None:
        self._json_default = json_default
        super().__init__()

    def load_dialect_impl(self, dialect):
        if dialect.name == "postgresql":
            from sqlalchemy.dialects.postgresql import JSONB as _PG_JSONB

            return dialect.type_descriptor(_PG_JSONB())
        from sqlalchemy import JSON as _SA_JSON

        return dialect.type_descriptor(_SA_JSON())

    def process_bind_param(self, value: Any, dialect) -> str | None:
        if value is not None:
            return json.dumps(value, default=self._json_default)
        return None

    def process_result_value(self, value: Any, dialect) -> Any:
        if isinstance(value, str):
            return json.loads(value)
        return value


JSONType = _JSON
