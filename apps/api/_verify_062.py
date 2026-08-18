"""Scratch verifier for migration 062 — upgrade + downgrade round-trip on fresh SQLite."""

import asyncio
import os
import sys

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:////tmp/ext_verify_062.db")

from sqlalchemy import create_engine, inspect, text  # noqa: E402


def main() -> None:
    db = "/tmp/ext_verify_062.db"
    engine = create_engine(f"sqlite:///{db}")

    with engine.connect() as conn:
        conn.execute(text("DROP TABLE IF EXISTS alembic_version"))
        conn.commit()
    engine.dispose()

    # --- upgrade ---
    import alembic.config
    from alembic import command

    cfg = alembic.config.Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db}")
    command.upgrade(cfg, "head")
    print("UPGRADE OK")

    insp = inspect(engine)
    tables = set(insp.get_table_names())
    for t in ("system_exceptions", "system_exception_events", "exception_sla_configs"):
        assert t in tables, f"missing table {t}"
    print("TABLES:", [t for t in ("system_exceptions", "system_exception_events", "exception_sla_configs")])

    # --- downgrade ---
    command.downgrade(cfg, "061_add_ledger_tables")
    insp = inspect(engine)
    tables = set(insp.get_table_names())
    assert "system_exceptions" not in tables
    print("DOWNGRADE OK")

    # --- re-upgrade ---
    command.upgrade(cfg, "head")
    print("RE-UPGRADE OK")


if __name__ == "__main__":
    sys.exit(main())
