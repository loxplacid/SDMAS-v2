"""Postgres performance benchmark for the hot query shapes.

Connects to the scratch ``sdmas_perf`` database (migrated to Alembic head),
seeds 100k students / 300k ledger rows, then EXPLAIN ANALYZE + times the
exact query shapes the app runs — before and after targeted indexes.

Usage: uv run python _perf_pg.py
"""
from __future__ import annotations

import asyncio
import os
import time
import traceback

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine

URL = os.environ.get(
    "PERF_DATABASE_URL", "postgresql+asyncpg://sdmas:sdmas_dev@localhost:5432/sdmas_perf"
)

STUDENT_ROWS = int(os.environ.get("PERF_STUDENTS", "100000"))
LOG_ROWS = STUDENT_ROWS * 3

SEED_STUDENTS = text(
    """
    INSERT INTO students
        (first_name, last_name, student_number, campus_id,
         email, status, date_of_birth, created_at, updated_at)
    SELECT
        'First' || i, 'Last' || i, 'STU-' || i, 1,
        'stu' || i || '@test.local',
        CASE WHEN i % 4 = 0 THEN 'withdrawn' ELSE 'active' END,
        date '2008-01-01' + (i % 4000),
        now() - (i % 365) * interval '1 day',
        now() - (i % 365) * interval '1 day'
    FROM generate_series(1, :n) AS g(i)
    """
)

SEED_LOGS = text(
    """
    INSERT INTO transaction_logs
        (transaction_type, payment_id, fee_due_id, student_id,
         amount, balance_before, balance_after, campus_id,
         reference_number, description, idempotency_key, created_at)
    SELECT
        CASE WHEN i % 5 = 0 THEN 'refund' ELSE 'payment' END,
        NULL, NULL, (i % :n) + 1,
        (i % 5000) + 100, i, i, 1,
        'REF-' || i, 'benchmark row ' || i, 'bench-' || i,
        now() - (i % 365) * interval '1 day'
    FROM generate_series(1, :m) AS g(i)
    """
)

QUERIES: list[tuple[str, str]] = [
    (
        "list_p1",
        """
        SELECT * FROM students WHERE campus_id = 1 AND status = 'active'
        ORDER BY id LIMIT 50
        """,
    ),
    (
        "list_p1_count",
        "SELECT count(*) FROM students WHERE campus_id = 1 AND status = 'active'",
    ),
    (
        "list_deep",
        """
        SELECT * FROM students WHERE campus_id = 1 AND status = 'active'
        ORDER BY id LIMIT 50 OFFSET 49950
        """,
    ),
    (
        "search",
        """
        SELECT * FROM students WHERE campus_id = 1 AND
        (first_name ILIKE '%9999%' OR last_name ILIKE '%9999%'
         OR student_number ILIKE '%9999%' OR email ILIKE '%9999%')
        ORDER BY id LIMIT 50
        """,
    ),
    (
        "search_count",
        """
        SELECT count(*) FROM students WHERE campus_id = 1 AND
        (first_name ILIKE '%9999%' OR last_name ILIKE '%9999%'
         OR student_number ILIKE '%9999%' OR email ILIKE '%9999%')
        """,
    ),
    (
        "ledger_90d",
        """
        SELECT * FROM transaction_logs WHERE campus_id = 1
        AND created_at >= now() - interval '90 days'
        ORDER BY created_at DESC LIMIT 50
        """,
    ),
    (
        "ledger_student",
        """
        SELECT * FROM transaction_logs
        WHERE campus_id = 1 AND student_id = 12345
        ORDER BY created_at DESC LIMIT 50
        """,
    ),
    (
        "dash_agg",
        """
        SELECT sum(amount), count(*) FROM payments WHERE campus_id = 1
        """,
    ),
]

INDEXES: list[str] = [
    # Ledger date-range list: campus alone still scans all campus rows for
    # the range — (campus_id, created_at) turns it into a seek + index scan.
    "CREATE INDEX IF NOT EXISTS ix_transaction_logs_campus_created "
    "ON transaction_logs (campus_id, created_at DESC)",
    # Student search: the ilike %q% pattern can only use a trigram index.
    "CREATE EXTENSION IF NOT EXISTS pg_trgm",
    "CREATE INDEX IF NOT EXISTS ix_students_trgm "
    "ON students USING gin (first_name gin_trgm_ops, last_name gin_trgm_ops, "
    "student_number gin_trgm_ops, email gin_trgm_ops)",
    # Student status filter on top of campus: composite for the count query.
    "CREATE INDEX IF NOT EXISTS ix_students_campus_status "
    "ON students (campus_id, status)",
]


async def measure(conn, label: str, sql: str, tag: str) -> None:
    """EXPLAIN (ANALYZE, BUFFERS) once and report wall time + plan detail."""
    t0 = time.perf_counter()
    plan_res = await conn.execute(text(f"EXPLAIN (ANALYZE, BUFFERS) {sql}"))
    plan_rows = plan_res.fetchall()
    wall = (time.perf_counter() - t0) * 1000
    first_line = plan_rows[0][0].split("  ")[0] if plan_rows else "?"
    # execution time is in the last line
    exec_ms = "?"
    for row in plan_rows:
        if "Execution Time:" in row[0]:
            exec_ms = row[0].split(":")[1].strip().split(" ")[0]
    print(f"  [{tag}] {label:>14}  wall={wall:8.1f}ms  exec={exec_ms}ms  {first_line}")


async def main() -> None:
    engine = create_async_engine(URL)
    try:
        async with engine.begin() as conn:
            print(f"Seeding {STUDENT_ROWS:,} students, {LOG_ROWS:,} ledger rows…")
            await conn.execute(text("TRUNCATE students, transaction_logs RESTART IDENTITY CASCADE"))
            await conn.execute(SEED_STUDENTS, {"n": STUDENT_ROWS})
            await conn.execute(SEED_LOGS, {"n": STUDENT_ROWS, "m": LOG_ROWS})
        print("Seed done. Baseline (no extra indexes):")
        async with engine.connect() as conn:
            for label, sql in QUERIES:
                await measure(conn, label, sql, "before")
        print("Applying targeted indexes…")
        async with engine.begin() as conn:
            for stmt in INDEXES:
                await conn.execute(text(stmt))
            await conn.execute(text("ANALYZE students, transaction_logs, payments, fee_dues"))
        print("After indexes:")
        async with engine.connect() as conn:
            for label, sql in QUERIES:
                await measure(conn, label, sql, "after")
    except Exception:
        traceback.print_exc()
        raise
    finally:
        await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
