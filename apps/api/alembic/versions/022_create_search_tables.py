"""create_search_tables_and_fts_infrastructure

Revision ID: e7f3a2b1c0d9
Revises: d29e45f87a2c
Create Date: 2026-07-31 05:00:00.000000
"""
from __future__ import annotations

from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "e7f3a2b1c0d9"
down_revision: Union[str, None] = "d29e45f87a2c"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # ── Search history table ─────────────────────────────────────────────
    op.create_table(
        "search_history",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("user_id", sa.Integer(), nullable=False),
        sa.Column("query", sa.String(length=500), nullable=False),
        sa.Column("entity_type", sa.String(length=50), nullable=True,
                  comment="Filtered entity type, or null for all"),
        sa.Column("result_count", sa.Integer(), nullable=False, server_default=sa.text("0")),
        sa.Column("campus_id", sa.Integer(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), nullable=False,
                  server_default=sa.text("(CURRENT_TIMESTAMP)")),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["campus_id"], ["campuses.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        op.f("ix_search_history_user_id"), "search_history", ["user_id"], unique=False
    )
    op.create_index(
        op.f("ix_search_history_user_created"),
        "search_history",
        ["user_id", sa.text("created_at DESC")],
        unique=False,
        postgresql_using="btree",
    )

    # ── PostgreSQL full-text search preparation ───────────────────────────
    #
    # These operations are PostgreSQL-specific and will be skipped on
    # SQLite (dev/test).  The ``searchable_content`` materialised view
    # and GIN indexes are the foundation for migrating from ILIKE-based
    # search to full ``tsvector`` / ``tsquery`` ranking later.
    #
    # Steps to activate PG FTS (when ready):
    #   1. CREATE EXTENSION IF NOT EXISTS pg_trgm (already done below)
    #   2. CREATE EXTENSION IF NOT EXISTS unaccent
    #   3. Run the ``searchable_content`` materialised view (commented)
    #   4. Create GIN indexes on the tsvector columns
    #   5. Replace ILIKE queries in ``search/service.py`` with
    #      ``websearch_to_tsquery`` / ``ts_rank`` queries

    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        # Enable trigram extension for fuzzy matching (SIMILARITY)
        op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
        op.execute("CREATE EXTENSION IF NOT EXISTS unaccent")

        # GIN index for trigram-based ILIKE speedup on frequently searched
        # text columns.  These indexes dramatically accelerate patterns
        # like ``WHERE col ILIKE '%search%'``.
        op.create_index(
            "ix_students_first_name_trgm",
            "students",
            [sa.text("first_name gin_trgm_ops")],
            postgresql_using="gin",
        )
        op.create_index(
            "ix_students_last_name_trgm",
            "students",
            [sa.text("last_name gin_trgm_ops")],
            postgresql_using="gin",
        )
        op.create_index(
            "ix_students_student_number_trgm",
            "students",
            [sa.text("student_number gin_trgm_ops")],
            postgresql_using="gin",
        )
        op.create_index(
            "ix_teachers_first_name_trgm",
            "teachers",
            [sa.text("first_name gin_trgm_ops")],
            postgresql_using="gin",
        )
        op.create_index(
            "ix_teachers_last_name_trgm",
            "teachers",
            [sa.text("last_name gin_trgm_ops")],
            postgresql_using="gin",
        )
        op.create_index(
            "ix_teachers_employee_number_trgm",
            "teachers",
            [sa.text("employee_number gin_trgm_ops")],
            postgresql_using="gin",
        )
        op.create_index(
            "ix_classes_name_trgm",
            "classes",
            [sa.text("name gin_trgm_ops")],
            postgresql_using="gin",
        )
        op.create_index(
            "ix_sections_name_trgm",
            "sections",
            [sa.text("name gin_trgm_ops")],
            postgresql_using="gin",
        )
        op.create_index(
            "ix_notifications_title_trgm",
            "notifications",
            [sa.text("title gin_trgm_ops")],
            postgresql_using="gin",
        )
        op.create_index(
            "ix_documents_filename_trgm",
            "documents",
            [sa.text("original_filename gin_trgm_ops")],
            postgresql_using="gin",
        )
        op.create_index(
            "ix_fee_types_name_trgm",
            "fee_types",
            [sa.text("name gin_trgm_ops")],
            postgresql_using="gin",
        )

        # ── Future FTS preparation (commented, uncomment when ready) ─────
        #
        # -- Add tsvector columns to each searchable table:
        # ALTER TABLE students ADD COLUMN search_vector tsvector
        #   GENERATED ALWAYS AS (
        #     setweight(to_tsvector('english', coalesce(first_name, '')), 'A') ||
        #     setweight(to_tsvector('english', coalesce(last_name, '')), 'A') ||
        #     setweight(to_tsvector('english', coalesce(student_number, '')), 'B') ||
        #     setweight(to_tsvector('english', coalesce(email, '')), 'C')
        #   ) STORED;
        #
        # CREATE INDEX ix_students_search_vector ON students USING GIN(search_vector);
        #
        # -- Repeat for teachers, classes, sections, fee_types,
        # -- notifications, documents with their respective columns.
        #
        # -- Query example (once tsvector columns exist):
        # SELECT * FROM students
        # WHERE search_vector @@ websearch_to_tsquery('english', 'john 2024')
        # ORDER BY ts_rank(search_vector, websearch_to_tsquery('english', 'john 2024')) DESC;


def downgrade() -> None:
    conn = op.get_bind()
    if conn.dialect.name == "postgresql":
        op.drop_index("ix_students_first_name_trgm", table_name="students")
        op.drop_index("ix_students_last_name_trgm", table_name="students")
        op.drop_index("ix_students_student_number_trgm", table_name="students")
        op.drop_index("ix_teachers_first_name_trgm", table_name="teachers")
        op.drop_index("ix_teachers_last_name_trgm", table_name="teachers")
        op.drop_index("ix_teachers_employee_number_trgm", table_name="teachers")
        op.drop_index("ix_classes_name_trgm", table_name="classes")
        op.drop_index("ix_sections_name_trgm", table_name="sections")
        op.drop_index("ix_notifications_title_trgm", table_name="notifications")
        op.drop_index("ix_documents_filename_trgm", table_name="documents")
        op.drop_index("ix_fee_types_name_trgm", table_name="fee_types")
        op.execute("DROP EXTENSION IF EXISTS pg_trgm")
        op.execute("DROP EXTENSION IF EXISTS unaccent")

    op.drop_index(
        op.f("ix_search_history_user_created"), table_name="search_history"
    )
    op.drop_index(
        op.f("ix_search_history_user_id"), table_name="search_history"
    )
    op.drop_table("search_history")
