"""Add tenant FKs missing on assignments and guardian_links.

Revision ID: 050_add_missing_tenant_fks
Revises: 049_widen_audit_action
Create Date: 2026-08-16

The ORM models declare ``assignments.campus_id`` and
``guardian_links.campus_id`` with ``ForeignKey("campuses.id",
ondelete="SET NULL")``, but the historical migrations that created the
columns never added the database-level constraint.  Alembic autogenerate
detected both as "added foreign key" — the DB was not enforcing a tenant FK
the application layer promises.  Corrective migration adds both
constraints (verified: no orphan rows exist on production data).

SQLite needs batch_alter_table to add an FK; PostgreSQL emits a plain
ALTER TABLE.
"""


from alembic import op

revision: str = "050_add_missing_tenant_fks"
down_revision: str | None = "049_widen_audit_action"
branch_labels: str | None = None
depends_on: str | None = None


def upgrade() -> None:
    for table in ("assignments", "guardian_links"):
        with op.batch_alter_table(table) as batch:
            batch.create_foreign_key(
                f"fk_{table}_campus_id",
                "campuses",
                ["campus_id"],
                ["id"],
                ondelete="SET NULL",
            )


def downgrade() -> None:
    for table in ("assignments", "guardian_links"):
        with op.batch_alter_table(table) as batch:
            batch.drop_constraint(f"fk_{table}_campus_id", type_="foreignkey")
