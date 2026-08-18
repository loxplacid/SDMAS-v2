"""Add canonical envelope fields to outbox_events.

Revision ID: 052_add_outbox_canonical_fields
Revises: 051_add_missing_model_indexes
Create Date: 2026-08-17

The canonical event envelope (app/platform/events/envelope.py) requires
every durable event to carry its schema version, causation chain, and
producer source.  The outbox is the durable event store, so it gains the
three canonical fields alongside the existing envelope columns:

- ``event_version``  — schema version of the event type (default 1)
- ``causation_id``   — id of the event that caused this one (traceability)
- ``source``         — producer label (api / worker / scheduler / system)

All columns are nullable-safe with sensible defaults at the model level so
existing rows and legacy producers remain valid.
"""

import sqlalchemy as sa

from alembic import op

revision: str = "052_add_outbox_canonical_fields"
down_revision: str | None = "051_add_missing_model_indexes"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.add_column(
        "outbox_events",
        sa.Column("event_version", sa.Integer(), nullable=False, server_default="1"),
    )
    op.add_column(
        "outbox_events",
        sa.Column("causation_id", sa.String(64), nullable=True),
    )
    op.add_column(
        "outbox_events",
        sa.Column("source", sa.String(32), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("outbox_events", "source")
    op.drop_column("outbox_events", "causation_id")
    op.drop_column("outbox_events", "event_version")
