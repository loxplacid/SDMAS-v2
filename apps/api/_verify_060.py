"""Scratch verification: migration 060 upgrade + downgrade on isolated SQLite."""
import asyncio
import os

os.environ.setdefault("DATABASE_URL", "sqlite+aiosqlite:///ext_verify_060.db")
os.environ.setdefault("AUDIT_CHAIN_SECRET", "test-secret")

if os.path.exists("ext_verify_060.db"):
    os.remove("ext_verify_060.db")

from alembic import command
from alembic.config import Config
from sqlalchemy import inspect as sa_inspect
from sqlalchemy.ext.asyncio import create_async_engine


def run(cfg: Config, fn, *args) -> None:
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        fn(cfg, *args)
    finally:
        loop.close()


def main() -> None:
    cfg = Config("alembic.ini")
    cfg.set_main_option("sqlalchemy.url", "sqlite+aiosqlite:///ext_verify_060.db")

    run(cfg, command.upgrade, "059_add_extension_tables")
    engine = create_async_engine("sqlite+aiosqlite:///ext_verify_060.db")

    async def check_pre() -> None:
        async with engine.connect() as conn:

            def _inspect(sync_conn) -> None:
                insp = sa_inspect(sync_conn)
                cols = {c["name"] for c in insp.get_columns("migration_projects")}
                assert "profile" not in cols, "pre-060 schema has profile column!"
                assert "migration_snapshots" not in [
                    t for t in insp.get_table_names()
                ], "pre-060 has migration_snapshots!"

            await conn.run_sync(_inspect)
            print("pre-060: no factory columns, no snapshots table")

    asyncio.run(check_pre())
    asyncio.run(engine.dispose())

    run(cfg, command.upgrade, "head")

    async def check_post() -> None:
        async with engine.connect() as conn:

            def _inspect(sync_conn) -> None:
                insp = sa_inspect(sync_conn)
                cols = {c["name"] for c in insp.get_columns("migration_projects")}
                for col in ("profile", "identity_match", "mapping_versions",
                            "verification", "approval", "cutover"):
                    assert col in cols, f"missing {col}"
                assert "migration_snapshots" in insp.get_table_names()
                snap_cols = {c["name"] for c in insp.get_columns("migration_snapshots")}
                assert {"id", "campus_id", "project_id", "kind", "summary", "payload"} <= snap_cols

            await conn.run_sync(_inspect)
            print("post-060: 6 factory columns + migration_snapshots present")

    asyncio.run(check_post())
    asyncio.run(engine.dispose())

    run(cfg, command.downgrade, "059_add_extension_tables")

    async def check_down() -> None:
        async with engine.connect() as conn:

            def _inspect(sync_conn) -> None:
                insp = sa_inspect(sync_conn)
                cols = {c["name"] for c in insp.get_columns("migration_projects")}
                assert "profile" not in cols, "profile survived downgrade"
                assert "migration_snapshots" not in insp.get_table_names()

            await conn.run_sync(_inspect)
            print("downgrade: factory columns + snapshots dropped")

    asyncio.run(check_down())
    asyncio.run(engine.dispose())
    print("MIGRATION 060 VERIFIED")


if __name__ == "__main__":
    main()
