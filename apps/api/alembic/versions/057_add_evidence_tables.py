"""Add enterprise evidence tables.

Revision ID: 057_add_evidence_tables
Revises: 056_add_policy_tables
Create Date: 2026-08-17

Adds the enterprise evidence foundation (app/platform/evidence):

- ``evidence_packages``   — a claim bundled with its supporting evidence
  (stable ``package_key``, unique per campus)
- ``evidence_items``      — claims/assertions (*what was claimed*), with
  the policy version that applied
- ``evidence_references`` — pointers to external supporting data
  (audit, files, migration runs, reports, source records, policy
  evaluations) — referenced, never copied
- ``evidence_snapshots``  — immutable captures of supporting data and
  calculations, with a SHA-256 content hash
- ``evidence_hashes``     — a per-package hash chain over snapshots and
  items; replaying it detects any tampering (*has it changed?*)
- ``evidence_approvals``  — approval trail (*who approved it*)

Runtime application-level storage; the build-time ``scripts/evidence/``
tool (JUnit manifests + artifact checksums) remains separate and reuses
the same SHA-256 conventions.

JSON columns use the dialect-aware helper (JSONB on PostgreSQL, JSON
elsewhere) mirroring the model ``JSONType`` decorator.  Every table carries
``campus_id`` (direct tenant scoping).
"""

from __future__ import annotations

import sqlalchemy as sa

from alembic import op

revision: str = "057_add_evidence_tables"
down_revision: str | None = "056_add_policy_tables"
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
        "evidence_packages",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "campus_id",
            sa.Integer(),
            sa.ForeignKey("campuses.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("package_key", sa.String(200), nullable=False),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("claim", sa.String(2000), nullable=False),
        sa.Column("status", sa.String(20), nullable=False, server_default="draft"),
        sa.Column("metadata_json", _json_type(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column("approved_by", sa.Integer(), nullable=True),
        sa.Column("approved_at", sa.DateTime(timezone=True), nullable=True),
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
        sa.UniqueConstraint("campus_id", "package_key", name="uq_evidence_package_key"),
    )
    op.create_index("ix_evidence_packages_campus_id", "evidence_packages", ["campus_id"])
    op.create_index("ix_evidence_packages_status", "evidence_packages", ["status"])

    op.create_table(
        "evidence_items",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "campus_id",
            sa.Integer(),
            sa.ForeignKey("campuses.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "package_id",
            sa.Integer(),
            sa.ForeignKey("evidence_packages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("item_type", sa.String(30), nullable=False, server_default="claim"),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("statement", sa.String(4000), nullable=False),
        sa.Column("entity_type", sa.String(80), nullable=True),
        sa.Column("entity_id", sa.String(200), nullable=True),
        sa.Column("policy_id", sa.String(200), nullable=True),
        sa.Column("policy_version", sa.Integer(), nullable=True),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_evidence_items_campus_id", "evidence_items", ["campus_id"])
    op.create_index("ix_evidence_items_package_id", "evidence_items", ["package_id"])
    op.create_index("ix_evidence_items_item_type", "evidence_items", ["item_type"])

    op.create_table(
        "evidence_references",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "campus_id",
            sa.Integer(),
            sa.ForeignKey("campuses.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "package_id",
            sa.Integer(),
            sa.ForeignKey("evidence_packages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "item_id",
            sa.Integer(),
            sa.ForeignKey("evidence_items.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("ref_type", sa.String(30), nullable=False, server_default="audit"),
        sa.Column("reference", sa.String(512), nullable=False),
        sa.Column("checksum", sa.String(128), nullable=True),
        sa.Column("note", sa.String(1000), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_evidence_references_campus_id", "evidence_references", ["campus_id"])
    op.create_index(
        "ix_evidence_references_package_id",
        "evidence_references",
        ["package_id"],
    )
    op.create_index("ix_evidence_references_ref_type", "evidence_references", ["ref_type"])
    op.create_index(
        "ix_evidence_references_pkg_type_ref",
        "evidence_references",
        ["package_id", "ref_type", "reference"],
    )

    op.create_table(
        "evidence_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "campus_id",
            sa.Integer(),
            sa.ForeignKey("campuses.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "package_id",
            sa.Integer(),
            sa.ForeignKey("evidence_packages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "item_id",
            sa.Integer(),
            sa.ForeignKey("evidence_items.id", ondelete="CASCADE"),
            nullable=True,
        ),
        sa.Column("kind", sa.String(20), nullable=False, server_default="result"),
        sa.Column("label", sa.String(255), nullable=False),
        sa.Column("content", _json_type(), nullable=True),
        sa.Column("calculation", _json_type(), nullable=True),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("created_by", sa.Integer(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_evidence_snapshots_campus_id", "evidence_snapshots", ["campus_id"])
    op.create_index("ix_evidence_snapshots_package_id", "evidence_snapshots", ["package_id"])
    op.create_index("ix_evidence_snapshots_kind", "evidence_snapshots", ["kind"])

    op.create_table(
        "evidence_hashes",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "campus_id",
            sa.Integer(),
            sa.ForeignKey("campuses.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "package_id",
            sa.Integer(),
            sa.ForeignKey("evidence_packages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("target_type", sa.String(20), nullable=False),
        sa.Column("target_id", sa.Integer(), nullable=False),
        sa.Column("digest", sa.String(64), nullable=False),
        sa.Column("prev_hash", sa.String(64), nullable=False),
        sa.Column("hash_value", sa.String(64), nullable=False),
        sa.Column("chain_index", sa.Integer(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_evidence_hashes_campus_id", "evidence_hashes", ["campus_id"])
    op.create_index("ix_evidence_hashes_package_id", "evidence_hashes", ["package_id"])
    op.create_index("ix_evidence_hashes_hash_value", "evidence_hashes", ["hash_value"])

    op.create_table(
        "evidence_approvals",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column(
            "campus_id",
            sa.Integer(),
            sa.ForeignKey("campuses.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column(
            "package_id",
            sa.Integer(),
            sa.ForeignKey("evidence_packages.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("decision", sa.String(20), nullable=False),
        sa.Column("approver_id", sa.Integer(), nullable=True),
        sa.Column("comment", sa.String(1000), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.text("now()"),
        ),
    )
    op.create_index("ix_evidence_approvals_campus_id", "evidence_approvals", ["campus_id"])
    op.create_index(
        "ix_evidence_approvals_package_id",
        "evidence_approvals",
        ["package_id"],
    )


def downgrade() -> None:
    op.drop_table("evidence_approvals")
    op.drop_table("evidence_hashes")
    op.drop_table("evidence_snapshots")
    op.drop_table("evidence_references")
    op.drop_table("evidence_items")
    op.drop_table("evidence_packages")
