"""create temporal txn_log (The Archive, M1)

The engine-level transaction ledger for close-open temporal writes. The
history *mirror* tables land with the domain-enablement migrations (M2);
this migration establishes the ledger and the dialect-aware index
conventions the mirrors will use.

Revision ID: create_temporal_txn_log
Revises: merge_multi_tenant_heads
Create Date: 2026-08-07
"""

from __future__ import annotations

from typing import Sequence, Union

import sqlalchemy as sa

from alembic import op

revision: str = "create_temporal_txn_log"
down_revision: Union[str, None] = "merge_multi_tenant_heads"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _json_type():
    """JSONB on PostgreSQL, JSON elsewhere — mirrors the model TypeDecorator."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import JSONB

        return JSONB()
    return sa.JSON()


def _tt_range_index(op, table_name, tt_from="tt_from", tt_to="tt_to"):
    """Dialect-aware version-range index for history mirrors (M2+).

    PostgreSQL: GiST over ``tstzrange(tt_from, tt_to)`` — AS-OF point
    lookups are index-bound. Other dialects: composite btree fallback.
    Domain-enablement migrations call this for each new mirror table.
    """
    if op.get_bind().dialect.name == "postgresql":
        op.create_index(
            f"ix_{table_name}_tt_gist",
            table_name,
            [sa.text(f"tstzrange({tt_from}, {tt_to})")],
            postgresql_using="gist",
        )
    else:
        op.create_index(f"ix_{table_name}_tt", table_name, [tt_from, tt_to])


def upgrade() -> None:
    op.create_table(
        "txn_log",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("txn_ts", sa.DateTime(timezone=True), nullable=False),
        sa.Column("entity_type", sa.String(length=100), nullable=False),
        sa.Column("entity_id", sa.String(length=100), nullable=False),
        sa.Column("action", sa.String(length=20), nullable=False),
        sa.Column("actor_type", sa.String(length=20), nullable=True),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("reason", sa.Text(), nullable=True),
        sa.Column("tenant_id", sa.Integer(), nullable=True),
        sa.Column("campus_id", sa.Integer(), nullable=True),
        sa.Column("change", _json_type(), nullable=True),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_txn_log_entity", "txn_log", ["entity_type", "entity_id", "txn_ts"])
    op.create_index("ix_txn_log_ts", "txn_log", ["txn_ts"])
    op.create_index("ix_txn_log_actor", "txn_log", ["actor_id"])
    op.create_index("ix_txn_log_tenant", "txn_log", ["tenant_id", "campus_id"])


def downgrade() -> None:
    op.drop_index("ix_txn_log_tenant", table_name="txn_log")
    op.drop_index("ix_txn_log_actor", table_name="txn_log")
    op.drop_index("ix_txn_log_ts", table_name="txn_log")
    op.drop_index("ix_txn_log_entity", table_name="txn_log")
    op.drop_table("txn_log")
