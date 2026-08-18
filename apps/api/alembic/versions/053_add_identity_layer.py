"""Add canonical identity layer tables.

Revision ID: 053_add_identity_layer
Revises: 052_add_outbox_canonical_fields
Create Date: 2026-08-17

Adds the canonical identity foundation (app/platform/identities):

- ``canonical_people``    — one canonical record per real-world person,
  referencing existing Student/Teacher/Guardian/User rows by
  ``entity_type`` + ``entity_id`` (soft references, no FK — canonical
  people survive entity deletion).
- ``external_identities`` — identifiers from external systems (legacy ERP,
  biometric, RFID, transport, external orgs) with confidence + status,
  unique per (campus, source_system, external_id).
- ``identity_aliases``    — alternate names/identifiers for a person.
- ``identity_matches``    — deterministic match proposals with confidence,
  evidence, and manual review state.
- ``identity_merges``     — merge operations (source → target) with
  before/after snapshots.
- ``identity_history``    — append-only audit trail.

Tenancy: every table carries ``campus_id`` (direct tenant scoping), so the
multi-tenant registry classifies all six as tenant-owned and the scoped
repository pins every query to the caller's campus.
"""

import sqlalchemy as sa

from alembic import op

revision: str = "053_add_identity_layer"
down_revision: str | None = "052_add_outbox_canonical_fields"
branch_labels: str | None = None
depends_on: str | None = None


def _json_type():
    """JSONB on PostgreSQL, JSON elsewhere — mirrors the model JSONType."""
    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        from sqlalchemy.dialects.postgresql import JSONB

        return JSONB()
    return sa.JSON()


def upgrade() -> None:
    op.create_table(
        "canonical_people",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "campus_id",
            sa.Integer(),
            sa.ForeignKey("campuses.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("entity_type", sa.String(50), nullable=False, server_default="user"),
        sa.Column("entity_id", sa.Integer(), nullable=True),
        sa.Column("first_name", sa.String(100), nullable=False, server_default=""),
        sa.Column("last_name", sa.String(100), nullable=False, server_default=""),
        sa.Column("date_of_birth", sa.Date(), nullable=True),
        sa.Column("email", sa.String(255), nullable=True),
        sa.Column("phone", sa.String(50), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_canonical_people_campus_id", "canonical_people", ["campus_id"])
    op.create_index("ix_canonical_people_entity_id", "canonical_people", ["entity_id"])
    op.create_index("ix_canonical_people_status", "canonical_people", ["status"])
    op.create_index(
        "ix_canonical_people_campus_entity",
        "canonical_people",
        ["campus_id", "entity_type", "entity_id"],
    )

    op.create_table(
        "external_identities",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "campus_id",
            sa.Integer(),
            sa.ForeignKey("campuses.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "canonical_person_id",
            sa.Integer(),
            sa.ForeignKey("canonical_people.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("source_system", sa.String(50), nullable=False),
        sa.Column("external_id", sa.String(128), nullable=False),
        sa.Column("external_name", sa.String(255), nullable=True),
        sa.Column("confidence", sa.Float(), nullable=False, server_default="1.0"),
        sa.Column("status", sa.String(20), nullable=False, server_default="active"),
        sa.Column("verified_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "campus_id", "source_system", "external_id", name="uq_external_identity_source_id"
        ),
    )
    op.create_index("ix_external_identities_campus_id", "external_identities", ["campus_id"])
    op.create_index(
        "ix_external_identities_canonical_person_id",
        "external_identities",
        ["canonical_person_id"],
    )
    op.create_index("ix_external_identities_status", "external_identities", ["status"])

    op.create_table(
        "identity_aliases",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "campus_id",
            sa.Integer(),
            sa.ForeignKey("campuses.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "canonical_person_id",
            sa.Integer(),
            sa.ForeignKey("canonical_people.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("alias_type", sa.String(30), nullable=False, server_default="name"),
        sa.Column("alias_value", sa.String(255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default="1"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_identity_aliases_campus_id", "identity_aliases", ["campus_id"])
    op.create_index(
        "ix_identity_aliases_canonical_person_id", "identity_aliases", ["canonical_person_id"]
    )
    op.create_index(
        "ix_identity_aliases_person_type_value",
        "identity_aliases",
        ["canonical_person_id", "alias_type", "alias_value"],
    )

    op.create_table(
        "identity_matches",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "campus_id",
            sa.Integer(),
            sa.ForeignKey("campuses.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "person_a_id",
            sa.Integer(),
            sa.ForeignKey("canonical_people.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "person_b_id",
            sa.Integer(),
            sa.ForeignKey("canonical_people.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("matched_by", sa.String(80), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("evidence", _json_type(), nullable=True),
        sa.Column("status", sa.String(20), nullable=False, server_default="pending"),
        sa.Column("reviewed_by", sa.Integer(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.UniqueConstraint(
            "person_a_id", "person_b_id", "matched_by", name="uq_identity_match_pair_rule"
        ),
    )
    op.create_index("ix_identity_matches_campus_id", "identity_matches", ["campus_id"])
    op.create_index("ix_identity_matches_person_a_id", "identity_matches", ["person_a_id"])
    op.create_index("ix_identity_matches_person_b_id", "identity_matches", ["person_b_id"])
    op.create_index("ix_identity_matches_status", "identity_matches", ["status"])

    op.create_table(
        "identity_merges",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "campus_id",
            sa.Integer(),
            sa.ForeignKey("campuses.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "source_person_id",
            sa.Integer(),
            sa.ForeignKey("canonical_people.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "target_person_id",
            sa.Integer(),
            sa.ForeignKey("canonical_people.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("reason", sa.String(500), nullable=False, server_default=""),
        sa.Column("status", sa.String(20), nullable=False, server_default="completed"),
        sa.Column("performed_by", sa.Integer(), nullable=True),
        sa.Column(
            "performed_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
        sa.Column("before_snapshot", _json_type(), nullable=True),
        sa.Column("after_snapshot", _json_type(), nullable=True),
    )
    op.create_index("ix_identity_merges_campus_id", "identity_merges", ["campus_id"])
    op.create_index("ix_identity_merges_source_person_id", "identity_merges", ["source_person_id"])
    op.create_index("ix_identity_merges_target_person_id", "identity_merges", ["target_person_id"])
    op.create_index("ix_identity_merges_status", "identity_merges", ["status"])

    op.create_table(
        "identity_history",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "campus_id",
            sa.Integer(),
            sa.ForeignKey("campuses.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "canonical_person_id",
            sa.Integer(),
            sa.ForeignKey("canonical_people.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("action", sa.String(30), nullable=False),
        sa.Column("actor_id", sa.Integer(), nullable=True),
        sa.Column("details", _json_type(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_identity_history_campus_id", "identity_history", ["campus_id"])
    op.create_index(
        "ix_identity_history_canonical_person_id",
        "identity_history",
        ["canonical_person_id"],
    )
    op.create_index("ix_identity_history_action", "identity_history", ["action"])
    op.create_index("ix_identity_history_created_at", "identity_history", ["created_at"])


def downgrade() -> None:
    op.drop_table("identity_history")
    op.drop_table("identity_merges")
    op.drop_table("identity_matches")
    op.drop_table("identity_aliases")
    op.drop_table("external_identities")
    op.drop_table("canonical_people")
