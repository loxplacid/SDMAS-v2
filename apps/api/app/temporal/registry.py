"""Temporal table registry (The Archive, M1).

A versioned *current* table keeps only the open version of each row; every
closed version lives in a *history* mirror. This module maps a current
table to its mirror and version-column conventions, and can materialize
the mirror's DDL.

History mirrors are created at registration time and ride along with
``Base.metadata.create_all`` (tests today; the domain-enablement
migrations of M2 emit the same DDL for production).
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import Column, Index, Integer, Table, text

from app.infrastructure.database import Base

DEFAULT_ID_COLUMN = "id"
DEFAULT_TT_FROM = "tt_from"
DEFAULT_TT_TO = "tt_to"


class TemporalError(Exception):
    """Raised when the temporal engine is asked to do something invalid."""


@dataclass(frozen=True)
class TemporalTableSpec:
    """Conventions for one versioned table pair.

    Attributes:
        current: name of the live table (open versions only).
        history: name of the history mirror (closed versions).
        id_column: identity column of the current table.
        tt_from / tt_to: transaction-time window column names.
    """

    current: str
    history: str
    id_column: str = DEFAULT_ID_COLUMN
    tt_from: str = DEFAULT_TT_FROM
    tt_to: str = DEFAULT_TT_TO


def tt_range_index_definition(
    table_name: str,
    tt_from: str,
    tt_to: str,
    *,
    dialect: str,
) -> tuple[str, list, dict]:
    """Dialect-aware version-range index definition (migration contract).

    PostgreSQL gets a GiST index over ``tstzrange(tt_from, tt_to)`` so
    AS-OF point lookups are index-bound; every other dialect gets the
    composite btree fallback. Domain-enablement migrations (M2) emit the
    same DDL the engine documents here.
    """
    if dialect == "postgresql":
        return (
            f"ix_{table_name}_tt_gist",
            [text(f"tstzrange({tt_from}, {tt_to})")],
            {"postgresql_using": "gist"},
        )
    return f"ix_{table_name}_tt", [tt_from, tt_to], {}


class TemporalTableRegistry:
    """Maps current table names to their temporal specs."""

    def __init__(self) -> None:
        self._specs: dict[str, TemporalTableSpec] = {}

    def register(
        self,
        current: str,
        *,
        history: str | None = None,
        id_column: str = DEFAULT_ID_COLUMN,
        tt_from: str = DEFAULT_TT_FROM,
        tt_to: str = DEFAULT_TT_TO,
        build_history: bool = True,
    ) -> TemporalTableSpec:
        """Register a current table as temporal (idempotent).

        When ``build_history`` is true the history mirror is materialized
        into ``Base.metadata`` immediately — call this after the ORM
        model is defined.
        """
        existing = self._specs.get(current)
        if existing is not None:
            return existing
        spec = TemporalTableSpec(
            current=current,
            history=history or f"{current}_history",
            id_column=id_column,
            tt_from=tt_from,
            tt_to=tt_to,
        )
        self._specs[current] = spec
        if build_history:
            build_history_table(spec)
        return spec

    def get(self, current: str) -> TemporalTableSpec | None:
        return self._specs.get(current)

    def require(self, current: str) -> TemporalTableSpec:
        spec = self._specs.get(current)
        if spec is None:
            raise TemporalError(
                f"table {current!r} is not registered as temporal; "
                "call TemporalTableRegistry.register() first"
            )
        return spec


def build_history_table(spec: TemporalTableSpec) -> Table:
    """Materialize the history mirror for ``spec`` into ``Base.metadata``.

    The mirror is the current table plus a surrogate PK: the business id
    becomes the ``entity_id`` column (it repeats across versions) and
    every closed version carries the ``[tt_from, tt_to)`` window. Unique
    constraints are dropped (history legitimately holds repeated business
    keys) and a portable btree index covers the version range on every
    dialect — the GiST form is emitted by the domain migrations (M2).
    """
    existing = Base.metadata.tables.get(spec.history)
    if existing is not None:
        return existing
    if spec.current not in Base.metadata.tables:
        raise TemporalError(
            f"current table {spec.current!r} is not registered with "
            "Base.metadata; define the ORM model before registering it "
            "as temporal"
        )
    current = Base.metadata.tables[spec.current]
    columns: list[Column] = []
    for col in current.columns:
        name = "entity_id" if col.primary_key and col.name == spec.id_column else col.name
        # Columns are built fresh (Column.copy() is deprecated since 1.4
        # and would leave the demoted PK keyed under its old name).
        # Foreign keys are intentionally not carried over here: production
        # history mirrors are created by the M2 domain migrations, which
        # emit FK constraints explicitly; this builder serves create_all
        # paths (tests/dev) where fixtures carry no relationships.
        cloned = Column(
            name,
            col.type,
            nullable=col.nullable,
            default=col.default,
            server_default=col.server_default,
            comment=col.comment,
        )
        columns.append(cloned)
    columns.insert(0, Column("id", Integer, primary_key=True, autoincrement=True))
    return Table(
        spec.history,
        Base.metadata,
        *columns,
        Index(f"ix_{spec.history}_tt", spec.tt_from, spec.tt_to),
    )


registry = TemporalTableRegistry()
