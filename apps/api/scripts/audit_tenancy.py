"""Audit every SQLAlchemy model and classify its tenancy.

Outputs a table of:
  model, table, scope (tenant_direct / tenant_parent / platform),
  campus key, institution key, FKs, unique constraints, indexes.

Run:  python scripts/audit_tenancy.py
"""

from __future__ import annotations

import importlib
import sys
from collections import defaultdict

from sqlalchemy import inspect as sa_inspect

# Import the full app metadata via the alembic env module list.
from app.infrastructure.database import Base
from app.multi_tenant import registry

# Every model module registered in alembic/env.py (single source of truth
# for what the schema contains).
MODEL_MODULES = [
    "app.domains.academic.models",
    "app.domains.admission.models",
    "app.domains.attendance.models",
    "app.domains.attendance_intelligence.models",
    "app.domains.leave.models",
    "app.domains.workflow.models",
    "app.domains.institution.models",
    "app.domains.notifications.models",
    "app.domains.auth.models",
    "app.domains.fees.models",
    "app.domains.student.models",
    "app.domains.academic_ops.models",
    "app.domains.school_finance.models",
    "app.domains.report_builder.models",
    "app.domains.documents.models",
    "app.domains.communications.models",
    "app.domains.parent.models",
    "app.domains.search.models",
    "app.domains.student_portal.models",
    "app.domains.audit.models",
    "app.domains.billing.models",
    "app.domains.jobs.models",
    "app.domains.risk.models",
    "app.domains.reports.models",
    "app.domains.migration.models",
]

for mod in MODEL_MODULES:
    try:
        importlib.import_module(mod)
    except Exception as exc:  # noqa: BLE001
        print(f"!! failed to import {mod}: {exc}", file=sys.stderr)

SCOPE_LABEL = {
    registry.TENANT_DIRECT: "tenant_direct",
    registry.TENANT_PARENT: "tenant_parent",
    registry.PLATFORM: "platform",
}


def main() -> None:
    rows = []
    tables = {t.name: t for t in Base.metadata.tables.values()}
    for model in sorted(
        (m.class_ for m in Base.registry.mappers if m.class_ is not None and getattr(m.class_, "__tablename__", None)),
        key=lambda c: c.__tablename__,
    ):
        mapper = tables[model.__tablename__]
        scope = SCOPE_LABEL[registry.tenant_scope_of(model)]
        cols = {c.name: c for c in mapper.columns}
        campus_key = "campus_id" if "campus_id" in cols else "-"
        inst_key = "institution_id" if "institution_id" in cols else "-"
        fks = ",".join(sorted({fk.target_fullname for c in mapper.columns for fk in c.foreign_keys}))
        uniques = ",".join(sorted((c.name or "(unnamed)") for c in mapper.constraints if c.__class__.__name__ == "UniqueConstraint"))
        idxs = ",".join(sorted(i.name or "(col)" for i in mapper.indexes))
        rows.append((mapper.name, scope, campus_key, inst_key, fks, uniques, idxs))

    print(f"{'TABLE':<34}{'SCOPE':<16}{'CAMPUS':<10}{'INST':<10}UNIQUES / INDEXES")
    print("-" * 140)
    by_scope = defaultdict(list)
    for table, scope, campus_key, inst_key, fks, uniques, idxs in rows:
        print(f"{table:<34}{scope:<16}{campus_key:<10}{inst_key:<10}{uniques} | {idxs}")
        by_scope[scope].append(table)

    print()
    for scope in ("tenant_direct", "tenant_parent", "platform"):
        print(f"{scope.upper()} ({len(by_scope[scope])}):")
        print("  " + ", ".join(by_scope[scope]))
        print()


if __name__ == "__main__":
    main()
