"""Schema-integrity regression tests.

Guards the defects found during the PostgreSQL/Alembic audit:

1. ``alembic/env.py`` imported only a hand-maintained subset of domains,
   so ``alembic autogenerate``/``alembic check`` reported every table of
   the unlisted domains (audit_logs, jobs, outbox_events, plans,
   subscriptions, risk_*, migration_*, …) as "to be dropped".  The fix:
   ``app/infrastructure.models`` is the complete registration site and
   ``env.py`` imports it.  Test: every table created by any migration
   must exist in ``Base.metadata`` after importing the site.
2. Models that live outside a domain's ``models.py`` (``outbox_events``,
   ``txn_log``, ``notification_preferences``) were invisible too.
3. The DB was missing two model-declared tenant FKs
   (``assignments.campus_id``, ``guardian_links.campus_id``) and two
   model-declared indexes (``migration_projects.job_id``,
   ``refresh_tokens.is_revoked``).  Corrective migrations 050/051 add
   them; tests assert the models declare the FKs and the corrective
   migrations still exist and target the right objects.
4. Alembic must always have exactly one canonical head.
"""

from __future__ import annotations

import re
from pathlib import Path

from alembic.config import Config
from alembic.script import ScriptDirectory

from app.infrastructure.database import Base

API_ROOT = Path(__file__).resolve().parents[1]
VERSIONS_DIR = API_ROOT / "alembic" / "versions"
ALEMBIC_INI = API_ROOT / "alembic.ini"

# Importing the central site registers every model (side effect).
import app.infrastructure.models  # noqa: F401,E402


def _migration_created_tables() -> set[str]:
    """Every table name any migration creates via op/batch create_table."""
    tables: set[str] = set()
    pat = re.compile(r"(?:op|batch)\.create_table\(\s*[\"']([A-Za-z_][A-Za-z0-9_]*)")
    for path in VERSIONS_DIR.glob("*.py"):
        text = path.read_text(encoding="utf-8")
        tables.update(pat.findall(text))
    return tables


def _alembic_heads() -> list[str]:
    cfg = Config(str(ALEMBIC_INI))
    script = ScriptDirectory.from_config(cfg)
    return list(script.get_heads())


def test_single_canonical_alembic_head() -> None:
    """There must be exactly one alembic head (no divergence)."""
    heads = _alembic_heads()
    assert len(heads) == 1, f"expected 1 alembic head, got {heads}"
    assert heads[0] == "063_add_enterprise_hierarchy"


def test_all_migration_tables_registered_in_metadata() -> None:
    """Every table created by any migration must be visible to Base.metadata.

    Regression for the env.py bug that made alembic check/autogenerate
    report ~15 domains' tables as "to be dropped".
    """
    created = _migration_created_tables()
    assert len(created) > 50, f"sanity: expected many tables, got {len(created)}"
    missing = sorted(t for t in created if t not in Base.metadata.tables)
    assert not missing, (
        "tables created by migrations but missing from Base.metadata "
        f"(check app/infrastructure/models.py imports): {missing}"
    )


def test_non_models_modules_registered() -> None:
    """Models defined outside their domain's models.py are registered."""
    for table in ("outbox_events", "txn_log", "notification_preferences"):
        assert table in Base.metadata.tables, (
            f"{table} missing from Base.metadata — import its defining module "
            "in app/infrastructure/models.py"
        )


def test_tenant_fks_declared_on_assignments_and_guardian_links() -> None:
    """Model-level tenant FKs must target campuses with ON DELETE SET NULL.

    The DB previously lacked these constraints (corrective migration 050
    adds them); the models must keep declaring them so autogenerate can
    detect any future drift.
    """
    for table_name in ("assignments", "guardian_links"):
        table = Base.metadata.tables[table_name]
        fk = table.c.campus_id.foreign_keys
        assert len(fk) == 1, f"{table_name}.campus_id should have exactly 1 FK"
        col_fk = next(iter(fk))
        assert col_fk.column.table.name == "campuses", (
            f"{table_name}.campus_id should reference campuses"
        )
        assert col_fk.ondelete == "SET NULL", (
            f"{table_name}.campus_id FK should be ON DELETE SET NULL"
        )


def test_corrective_migrations_050_and_051_present() -> None:
    """The corrective migrations must exist and target the right objects."""
    v050 = (VERSIONS_DIR / "050_add_missing_tenant_fks.py").read_text(encoding="utf-8")
    assert 'revision: str = "050_add_missing_tenant_fks"' in v050
    assert 'down_revision: str | None = "049_widen_audit_action"' in v050
    assert 'for table in ("assignments", "guardian_links"):' in v050
    assert "batch.create_foreign_key" in v050
    assert 'f"fk_{table}_campus_id"' in v050

    v051 = (VERSIONS_DIR / "051_add_missing_model_indexes.py").read_text(encoding="utf-8")
    assert 'revision: str = "051_add_missing_model_indexes"' in v051
    assert 'down_revision: str | None = "050_add_missing_tenant_fks"' in v051
    assert "ix_migration_projects_job_id" in v051
    assert "ix_refresh_tokens_is_revoked" in v051


def test_model_declares_indexes_covered_by_migration_051() -> None:
    """migration_projects.job_id and refresh_tokens.is_revoked keep
    index=True so future drift is detectable."""
    migration_projects = Base.metadata.tables["migration_projects"]
    refresh_tokens = Base.metadata.tables["refresh_tokens"]
    assert any(idx.columns.keys() == ["job_id"] for idx in migration_projects.indexes), (
        "migration_projects.job_id must keep its index declaration"
    )
    assert any(idx.columns.keys() == ["is_revoked"] for idx in refresh_tokens.indexes), (
        "refresh_tokens.is_revoked must keep its index declaration"
    )
