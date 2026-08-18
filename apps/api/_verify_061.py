"""Scratch verification for migration 061 (deleted after use)."""

import asyncio
import os
import sys

from alembic import command
from alembic.config import Config


def _cfg(db_path: str) -> Config:
    cfg = Config("alembic.ini")
    cfg.set_main_option("script_location", "alembic")
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    return cfg


def main() -> None:
    db = os.path.abspath("/tmp/ledger_verify_061.db")
    if os.path.exists(db):
        os.remove(db)
    cfg = _cfg(db)
    print("UPGRADE HEAD:", flush=True)
    command.upgrade(cfg, "head")
    print("HEADS:", command.heads(cfg), flush=True)

    import sqlite3

    con = sqlite3.connect(db)
    tables = {
        r[0]
        for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
    }
    for t in ("ledger_accounts", "accounting_periods", "journal_entries", "journal_lines"):
        print(f"TABLE {t}:", t in tables, flush=True)
        if t in tables:
            checks = [
                r[1]
                for r in con.execute(
                    "SELECT * FROM sqlite_master WHERE type='table' AND name=?",
                    (t,),
                ).fetchall()
            ]
            print("  sql_head:", (checks[0][:60] + "...") if checks else "?", flush=True)
    con.close()

    print("DOWNGRADE -> 060:", flush=True)
    command.downgrade(cfg, "060_add_migration_factory_tables")
    con = sqlite3.connect(db)
    gone = {
        r[0]
        for r in con.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name IN "
            "('ledger_accounts','accounting_periods','journal_entries','journal_lines')"
        ).fetchall()
    }
    print("REMAINING LEDGER TABLES AFTER DOWNGRADE:", sorted(gone), flush=True)
    con.close()

    print("RE-UPGRADE HEAD:", flush=True)
    command.upgrade(cfg, "head")
    print("RC_OK", flush=True)


main()
sys.exit(0)
