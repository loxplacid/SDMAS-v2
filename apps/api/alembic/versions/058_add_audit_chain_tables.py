"""Add tamper-evident audit chain tables.

Revision ID: 058_add_audit_chain_tables
Revises: 057_add_evidence_tables
Create Date: 2026-08-17

Adds the tamper-evident audit chain (app/platform/cryptography):

- ``audit_chain_entries``    — one per audit event: prev_hash (the link),
  payload_hash (canonical SHA-256 of the event content), current_hash
  (binds prev + payload + campus + index), and an HMAC signature
- ``audit_chain_checkpoints`` — periodic signed state hashes covering the
  chain up to a point, so even a deleted tail is detectable

Chains are **per campus** — every link binds the campus id, so a tamper
in one tenant can never break another tenant's chain.  ``audit_log_id`` is
unique (one chain entry per event, idempotent append).  Signatures are
HMAC-SHA256 with ``AUDIT_CHAIN_SECRET`` (development default with a
warning; production must set a real secret).

Both tables carry ``campus_id`` (direct tenant scoping).
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "058_add_audit_chain_tables"
down_revision: str | None = "057_add_evidence_tables"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    op.create_table(
        "audit_chain_entries",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "campus_id",
            sa.Integer(),
            sa.ForeignKey("campuses.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "audit_log_id",
            sa.Integer(),
            sa.ForeignKey("audit_logs.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chain_index", sa.Integer(), nullable=False),
        sa.Column("prev_hash", sa.String(64), nullable=False),
        sa.Column("payload_hash", sa.String(64), nullable=False),
        sa.Column("current_hash", sa.String(64), nullable=False),
        sa.Column("signature", sa.String(64), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint("audit_log_id", name="uq_audit_chain_entry_audit_log"),
    )
    op.create_index("ix_audit_chain_entries_campus_id", "audit_chain_entries", ["campus_id"])
    op.create_index(
        "ix_audit_chain_entries_audit_log_id",
        "audit_chain_entries",
        ["audit_log_id"],
    )
    op.create_index(
        "ix_audit_chain_entries_current_hash",
        "audit_chain_entries",
        ["current_hash"],
    )
    op.create_index(
        "ix_audit_chain_campus_index",
        "audit_chain_entries",
        ["campus_id", "chain_index"],
    )

    op.create_table(
        "audit_chain_checkpoints",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "campus_id",
            sa.Integer(),
            sa.ForeignKey("campuses.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("up_to_chain_index", sa.Integer(), nullable=False),
        sa.Column("state_hash", sa.String(64), nullable=False),
        sa.Column("signature", sa.String(64), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index(
        "ix_audit_chain_checkpoints_campus_id",
        "audit_chain_checkpoints",
        ["campus_id"],
    )
    op.create_index(
        "ix_audit_chain_checkpoint_campus_index",
        "audit_chain_checkpoints",
        ["campus_id", "up_to_chain_index"],
    )


def downgrade() -> None:
    op.drop_table("audit_chain_checkpoints")
    op.drop_table("audit_chain_entries")
