#!/usr/bin/env python3
"""Standalone tamper-evident audit chain verifier.

Detects modification, deletion, and reordering of the audit log by
replaying the per-campus cryptographic chain (TASK 13).  This is an
*independent* verifier: it runs outside the API process, reads the
database directly, and shares only the pure verification core
(``app.platform.cryptography.verifier``) with the write path.

Usage (from the repository root):

    cd apps/api && uv run python ../../scripts/audit_verify.py
    cd apps/api && uv run python ../../scripts/audit_verify.py --campus 1
    cd apps/api && uv run python ../../scripts/audit_verify.py --json
    cd apps/api && AUDIT_CHAIN_SECRET=... uv run python ../../scripts/audit_verify.py

Environment:
    DATABASE_URL       the database to verify — the app's canonical async
                       form (``sqlite+aiosqlite:///...`` or
                       ``postgresql+asyncpg://...``) or the sync form;
                       defaults to the app's configured URL
    AUDIT_CHAIN_SECRET when set, HMAC signatures are verified too

Exit codes:
    0  chain verified (no critical findings)
    1  chain integrity broken (critical findings)
    2  usage / connection error
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from app.platform.cryptography.verifier import ChainVerification

# Make the app package importable regardless of the script's cwd.
_REPO_ROOT = Path(__file__).resolve().parents[1]
_API_DIR = _REPO_ROOT / "apps" / "api"
if str(_API_DIR) not in sys.path:
    sys.path.insert(0, str(_API_DIR))

from sqlalchemy import create_engine, select  # noqa: E402
from sqlalchemy.orm import Session  # noqa: E402

# NOTE: app modules are imported lazily inside main() AFTER DATABASE_URL is
# normalized — importing them at module level would trigger app.config
# validation before the URL is ready.

SEVERITY_ORDER = {"critical": 0, "warning": 1, "info": 2}


def _to_sync_url(url: str) -> str:
    """The sync driver URL used by this script's own engine."""
    if url.startswith("sqlite+aiosqlite:///"):
        return url.replace("sqlite+aiosqlite:///", "sqlite:///", 1)
    if url.startswith("postgresql+asyncpg://"):
        return "postgresql+psycopg2://" + url.split("://", 1)[1]
    return url


def _to_async_url(url: str) -> str:
    """The canonical async form the app config expects."""
    if url.startswith("sqlite:///"):
        return url.replace("sqlite:///", "sqlite+aiosqlite:///", 1)
    if url.startswith("postgresql+psycopg2://") or url.startswith("postgresql://"):
        return "postgresql+asyncpg://" + url.split("://", 1)[1]
    return url


def _load_rows(engine, models, campus_id: int | None):
    """Load ORM rows via a Session (plain Connection does not hydrate
    ORM entities — ``scalars()`` would fall back to the first column)."""
    AuditLog, AuditChainEntry, AuditChainCheckpoint = models
    with Session(engine) as session:
        if campus_id is None:
            audit_cond = AuditLog.campus_id.is_(None)
            entry_cond = AuditChainEntry.campus_id.is_(None)
            cp_cond = AuditChainCheckpoint.campus_id.is_(None)
        else:
            audit_cond = AuditLog.campus_id == campus_id
            entry_cond = AuditChainEntry.campus_id == campus_id
            cp_cond = AuditChainCheckpoint.campus_id == campus_id
        audit_rows = list(session.execute(select(AuditLog).where(audit_cond)).scalars())
        entries = list(
            session.execute(
                select(AuditChainEntry)
                .where(entry_cond)
                .order_by(AuditChainEntry.chain_index)
            ).scalars()
        )
        checkpoints = list(
            session.execute(
                select(AuditChainCheckpoint)
                .where(cp_cond)
                .order_by(AuditChainCheckpoint.up_to_chain_index)
            ).scalars()
        )
    return audit_rows, entries, checkpoints


def _distinct_campuses(engine, models) -> list[int | None]:
    """Every campus with chain entries or audit rows, plus the platform
    chain (``None``) when present."""
    AuditLog, AuditChainEntry, AuditChainCheckpoint = models
    campuses: set[int | None] = set()
    with Session(engine) as session:
        for model in (AuditChainEntry, AuditChainCheckpoint):
            for (value,) in session.execute(select(model.campus_id).distinct()):
                campuses.add(value)
        for (value,) in session.execute(select(AuditLog.campus_id).distinct()):
            campuses.add(value)
    return sorted(campuses, key=lambda c: (c is None, c))


def _human_report(result: ChainVerification, secret: bool) -> str:
    lines: list[str] = []
    lines.append("=" * 64)
    lines.append(
        "AUDIT CHAIN VERIFICATION - campus "
        f"{result.campus_id if result.campus_id is not None else '(platform)'}"
    )
    lines.append("=" * 64)
    lines.append(f"entries: {result.entries}   checkpoints: {result.checkpoints}")
    lines.append(f"uncovered audit rows (not chained): {result.uncovered_audit_rows}")
    lines.append(
        "signatures checked: "
        f"{'yes' if secret else 'no (set AUDIT_CHAIN_SECRET to verify HMAC)'}"
    )
    lines.append(
        f"verdict: {'OK - chain intact' if result.chain_ok else 'BROKEN - tampering detected'}"
    )
    lines.append("")
    if result.findings:
        for f in sorted(
            result.findings, key=lambda f: (SEVERITY_ORDER[f.severity], f.chain_index or 0)
        ):
            where = f"  [entry #{f.chain_index}]" if f.chain_index is not None else ""
            lines.append(f"  [{f.severity.upper()}] {f.code}{where}: {f.message}")
    else:
        lines.append("  no findings")
    lines.append("=" * 64)
    return "\n".join(lines)


def _json_result(result: ChainVerification, secret: bool) -> dict:
    return {
        "campus_id": result.campus_id,
        "chain_ok": result.chain_ok,
        "signatures_checked": secret,
        "entries": result.entries,
        "checkpoints": result.checkpoints,
        "uncovered_audit_rows": result.uncovered_audit_rows,
        "findings": [
            {
                "severity": f.severity,
                "code": f.code,
                "chain_index": f.chain_index,
                "message": f.message,
            }
            for f in result.findings
        ],
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--campus", type=int, default=None, help="verify only this campus chain")
    parser.add_argument(
        "--platform", action="store_true", help="verify the platform chain (campus NULL)"
    )
    parser.add_argument("--json", action="store_true", help="machine-readable JSON output")
    parser.add_argument("--database-url", default=None, help="override DATABASE_URL")
    args = parser.parse_args(argv)

    if args.platform and args.campus is not None:
        print("--platform and --campus are mutually exclusive", file=sys.stderr)
        return 2
    campus_id = None if args.platform else args.campus

    database_url = args.database_url or os.getenv("DATABASE_URL")
    if not database_url:
        # Fall back to the app's configured URL (zero-touch default).  The
        # app config must validate, so normalize to the canonical async form
        # first.
        try:
            os.environ["DATABASE_URL"] = "postgresql+asyncpg://unused"
            from app.config import settings

            database_url = str(settings.database_url)
        except Exception as exc:  # pragma: no cover
            print(f"DATABASE_URL not set and app config unavailable: {exc}", file=sys.stderr)
            return 2

    # The app's ORM models import app.config, which validates DATABASE_URL in
    # its canonical async form — normalize before importing them.
    async_url = _to_async_url(database_url)
    os.environ["DATABASE_URL"] = async_url
    try:
        from app.domains.audit.models import AuditLog
        from app.platform.cryptography.models import (
            AuditChainCheckpoint,
            AuditChainEntry,
        )
        from app.platform.cryptography.verifier import verify_chain

        models = (AuditLog, AuditChainEntry, AuditChainCheckpoint)
    except Exception as exc:  # pragma: no cover
        print(f"failed to import verification core: {exc}", file=sys.stderr)
        return 2

    secret = os.getenv("AUDIT_CHAIN_SECRET") or None
    try:
        engine = create_engine(_to_sync_url(async_url))
        if args.campus is not None or args.platform:
            targets = [campus_id]
        else:
            targets = _distinct_campuses(engine, models)
    except Exception as exc:
        print(f"failed to read the database: {exc}", file=sys.stderr)
        return 2

    results: list[ChainVerification] = []
    try:
        for target in targets:
            audit_rows, entries, checkpoints = _load_rows(engine, models, target)
            results.append(
                verify_chain(
                    entries=entries,
                    checkpoints=checkpoints,
                    audit_rows=audit_rows,
                    campus_id=target,
                    secret=secret,
                )
            )
    except Exception as exc:
        print(f"failed to read the database: {exc}", file=sys.stderr)
        return 2

    if args.json:
        print(json.dumps([_json_result(r, secret is not None) for r in results], indent=2))
    else:
        for result in results:
            print(_human_report(result, secret is not None))

    return 0 if all(r.chain_ok for r in results) else 1


if __name__ == "__main__":
    raise SystemExit(main())
