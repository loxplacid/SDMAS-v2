"""Performance benchmark: hot queries at 1k/10k/100k scale.

Creates a scratch SQLite DB from the app models, bulk-seeds students and
transaction logs, and times the exact query shapes the app runs (student
list/count/search, ledger list, dashboard aggregates). Output is a table of
milliseconds per scale — evidence for the performance audit.

Usage: uv run python _perf_bench.py [rows]  (default: 1k, 10k, 100k)
"""
from __future__ import annotations

import asyncio
import os
import sys
import tempfile
import time
import traceback

from sqlalchemy import text
from sqlalchemy.ext.asyncio import create_async_engine


async def build_schema(engine) -> None:
    import app.main  # noqa: F401  (registers every model with Base.metadata)
    from app.infrastructure.database import Base

    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


async def seed(engine, n: int) -> None:
    """Bulk-insert n students (campus 1) and n*3 transaction logs."""
    import datetime

    students = [
        (
            f"First{i}", f"Last{i}", f"STU-{i}", 1,
            f"stu{i}@test.local",
            "withdrawn" if i % 4 == 0 else "active",
            f"2008-01-{(i % 28) + 1:02d}",
            (datetime.datetime.utcnow() - datetime.timedelta(days=i % 365)).isoformat(),
            (datetime.datetime.utcnow() - datetime.timedelta(days=i % 365)).isoformat(),
        )
        for i in range(1, n + 1)
    ]
    logs = [
        (
            "refund" if i % 5 == 0 else "payment",
            None, None,
            (i % n) + 1,
            (i % 5000) + 100,
            i, i,
            1,
            f"REF-{i}",
            f"benchmark row {i}",
            f"bench-{i}",
            (datetime.datetime.utcnow() - datetime.timedelta(days=i % 365)).isoformat(),
        )
        for i in range(1, n * 3 + 1)
    ]
    log_rows = logs

    async with engine.begin() as conn:
        await conn.execute(
            text(
                "INSERT INTO students (first_name, last_name, student_number, "
                "campus_id, email, status, date_of_birth, created_at, updated_at) "
                "VALUES (:f, :l, :num, 1, :email, :status, :dob, :created, :updated)"
            ),
            [
                {"f": s[0], "l": s[1], "num": s[2], "email": s[4], "status": s[5],
                 "dob": s[6], "created": s[7], "updated": s[8]}
                for s in students
            ],
        )
        await conn.execute(
            text(
                "INSERT INTO transaction_logs (transaction_type, payment_id, "
                "fee_due_id, student_id, amount, balance_before, balance_after, "
                "campus_id, reference_number, description, idempotency_key, "
                "created_at) VALUES (:t, NULL, NULL, :sid, :amt, :bb, :ba, 1, "
                ":ref, :desc, :key, :created)"
            ),
            [
                {"t": lg[0], "sid": lg[3], "amt": lg[4], "bb": lg[5], "ba": lg[6],
                 "ref": lg[8], "desc": lg[9], "key": lg[10], "created": lg[11]}
                for lg in log_rows
            ],
        )


async def bench(engine, n: int) -> dict[str, float]:
    out: dict[str, float] = {}
    async with engine.connect() as conn:
        # 1. Student list (page 1) + count — the /students endpoint
        t0 = time.perf_counter()
        await conn.execute(
            text(
                "SELECT * FROM students WHERE campus_id = 1 AND status = 'active' "
                "ORDER BY id LIMIT 50"
            )
        )
        await conn.execute(
            text(
                "SELECT count(*) FROM students WHERE campus_id = 1 AND status = 'active'"
            )
        )
        out["student_list_p1"] = (time.perf_counter() - t0) * 1000

        # 2. Student list deep page (page 500)
        t0 = time.perf_counter()
        await conn.execute(
            text(
                "SELECT * FROM students WHERE campus_id = 1 AND status = 'active' "
                "ORDER BY id LIMIT 50 OFFSET 24950"
            )
        )
        out["student_list_p500"] = (time.perf_counter() - t0) * 1000

        # 3. Student search — the ilike %q% pattern from repository.search
        t0 = time.perf_counter()
        await conn.execute(
            text(
                "SELECT * FROM students WHERE campus_id = 1 AND "
                "(first_name LIKE '%9999%' OR last_name LIKE '%9999%' "
                "OR student_number LIKE '%9999%' OR email LIKE '%9999%') "
                "ORDER BY id LIMIT 50"
            )
        )
        await conn.execute(
            text(
                "SELECT count(*) FROM students WHERE campus_id = 1 AND "
                "(first_name LIKE '%9999%' OR last_name LIKE '%9999%' "
                "OR student_number LIKE '%9999%' OR email LIKE '%9999%')"
            )
        )
        out["student_search"] = (time.perf_counter() - t0) * 1000

        # 4. Ledger list — campus + date range, newest first
        t0 = time.perf_counter()
        await conn.execute(
            text(
                "SELECT * FROM transaction_logs WHERE campus_id = 1 "
                "AND created_at >= datetime('now', '-90 days') "
                "ORDER BY created_at DESC LIMIT 50"
            )
        )
        out["ledger_list_90d"] = (time.perf_counter() - t0) * 1000

        # 5. Dashboard aggregates — payments + fee_dues sums by campus
        t0 = time.perf_counter()
        await conn.execute(
            text("SELECT sum(amount), count(*) FROM payments WHERE campus_id = 1")
        )
        await conn.execute(
            text(
                "SELECT sum(original_amount), sum(amount_paid) FROM fee_dues "
                "WHERE campus_id = 1"
            )
        )
        out["dashboard_agg"] = (time.perf_counter() - t0) * 1000
    return out


async def main() -> None:
    sizes = [int(x) for x in sys.argv[1:]] or [1_000, 10_000, 100_000]
    print(f"{'scale':>10} | " + " | ".join(_LABELS.values()))
    for n in sizes:
        fd, path = tempfile.mkstemp(suffix=".db")
        os.close(fd)
        os.remove(path)
        engine = create_async_engine(f"sqlite+aiosqlite:///{path}")
        try:
            await build_schema(engine)
            await seed(engine, n)
            results = await bench(engine, n)
            row = f"{n:>9,} | "
            for key in _LABELS:
                row += f"{results[key]:>10.1f} | "
            print(row)
            # Query plans for the two hottest shapes at this size
            async with engine.connect() as conn:
                for label, sql in _PLANS.items():
                    res = await conn.execute(text(f"EXPLAIN QUERY PLAN {sql}"))
                    rows = [r[3] for r in res.fetchall()]
                    print(f"  PLAN [{label}] @ {n:,}: " + " | ".join(rows))
        except Exception:
            traceback.print_exc()
        finally:
            await engine.dispose()
            try:
                if os.path.exists(path):
                    os.remove(path)
            except OSError:
                pass


_LABELS = {
    "student_list_p1": "list_p1",
    "student_list_p500": "list_p500",
    "student_search": "search",
    "ledger_list_90d": "ledger_90d",
    "dashboard_agg": "dash_agg",
}

_PLANS = {
    "student_search": (
        "SELECT * FROM students WHERE campus_id = 1 AND "
        "(first_name LIKE '%9999%' OR last_name LIKE '%9999%' "
        "OR student_number LIKE '%9999%' OR email LIKE '%9999%') "
        "ORDER BY id LIMIT 50"
    ),
    "ledger_list": (
        "SELECT * FROM transaction_logs WHERE campus_id = 1 "
        "AND created_at >= datetime('now', '-90 days') "
        "ORDER BY created_at DESC LIMIT 50"
    ),
}


if __name__ == "__main__":
    asyncio.run(main())
