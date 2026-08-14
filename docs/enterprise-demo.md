# Enterprise Demo Environment (Step 5)

A deterministic, realistic **three-tenant** demonstration environment for
evaluating SDMAS v2 without manual data configuration.

| # | Organization | Code | Kind |
|---|--------------|------|------|
| 1 | **Apex Global School** | `APX` | K-12 (Grades 1–12, two sections per class) |
| 2 | **St. Jude Public Academy** | `STJ` | Primary/Middle (Primary 1 – Grade 8) |
| 3 | **Metropolitan Institute of Tech** | `MIT` | Tertiary (BSc programmes) |

Every tenant is a real `Campus` under a real `Institution`, using the
**production tenancy mechanism** (`UserSchoolMembership` + tenant-scoped
repositories + guards). No demo shortcuts bypass tenant isolation.

---

## 1. Prerequisites

- Docker (Compose v2) — see `docs/zero-touch-deployment.md`
- No database/Redis/JWT configuration needed for the demo path

## 2. One-command startup

```bash
docker compose up --build
./enterprise demo-seed
```

or, equivalently, inside the API container / a local venv:

```bash
uv run seed --profile enterprise-demo          # full scale
uv run seed --profile enterprise-demo --scale small   # faster evaluation
```

The seeder:

1. Refuses to run against a **production** database unless
   `SDMAS_ALLOW_DEMO=1` is explicitly set.
2. Runs Alembic migrations to head.
3. Creates the three institutions/campuses, users, memberships, academic
   structure, students, attendance, fees + payments + ledger, grades,
   guardians, workflows, cases, notifications, and a summary audit event.
4. Runs the real `RiskService.recompute` per campus so risk findings are
   **generated from the seeded data by the actual engine** — not fabricated.

The seed is **deterministic** (fixed per-tenant RNG seeds) and
**idempotent** (re-running skips already-seeded tenants).

## 3. Expected services

| Service | Purpose | URL / port |
|---------|---------|------------|
| PostgreSQL | primary store | internal (5432) |
| Redis | cache / queues | internal (6379) |
| API (FastAPI) | backend | `http://localhost:8000` |
| Worker | background jobs | internal |
| Web (React / nginx) | frontend | `http://localhost:80` (nginx entry; the demo URL is `http://localhost`) |

## 4. Demo credentials (development-only)

All demo users share a single development-only password:

```
DemoPass!2026
```

| Organization | Admin | Principal | Accountant | Staff |
|--------------|-------|-----------|------------|-------|
| Apex Global School | `apex.admin` | `apex.principal` | `apex.accountant` | `apex.staff` |
| St. Jude Public Academy | `stjude.admin` | `stjude.principal` | `stjude.accountant` | `stjude.staff` |
| Metropolitan Institute of Tech | `mit.admin` | `mit.principal` | `mit.accountant` | `mit.staff` |

Teachers: `apex.teacherT01` … `apex.teacherT18`, `stjude.teacherT01` …,
`mit.teacherT01` … (12–18 per tenant depending on scale).
Parents: `apex.parent1` … `apex.parent8` (similarly per tenant).

> These credentials are **demo-only** and never appear in production
> configuration. Change the password or disable these users in any
> production deployment.

## 5. Health verification

```bash
./enterprise health
curl http://localhost:8000/health
curl http://localhost:8000/ready
```

## 6. Shutdown / Reset

```bash
./enterprise down          # stop the stack
./enterprise demo-reset    # wipe demo data + reseed (requires confirmation)
```

`demo-reset` requires an explicit interactive confirmation and is never
allowed against a production database (a `_guard` raises otherwise).

---

## 7. Evaluator walkthrough (10–15 minutes)

### 1. Login

Open `http://localhost` (nginx entry, port 80), sign in as **`apex.admin` / `DemoPass!2026`**.
The organization switcher / account menu shows **Apex Global School** and
the current role (**admin**).

### 2. Tenant context

The header shows the organization + campus context. Switch to
`stjude.admin` (or open a second browser) and confirm the context changes
to **St. Jude Public Academy**.

### 3. Dashboard

The role-aware dashboard shows institution health, enrollment, attendance,
finance, outstanding actions, and recent activity — all computed from the
seeded data by real endpoints.

### 4. Student 360

Open Students → pick a student → Student 360. You should see:

- identity + enrollment status
- attendance signal (a low-attendance student is engineered into every
  tenant)
- academic signal (grade records for Terms 1–2)
- financial state (fee dues + payments + ledger)
- risk findings, active cases, recent activity

### 5. Attendance intelligence

Students with < 70% attendance trigger the `attendance_below_threshold`
risk rule (the evaluator runs on the *current* 30-day window, so seed
relative to today). A student with a 5-day absence streak is also
engineered in.

### 6. Financial dashboard

Fees, dues, and payments exist per tenant with realistic mixes:
fully paid, partially paid, unpaid/overdue, and high-outstanding accounts.
Ledger balances chain correctly (verified by test).

### 7. Reconciliation

Each tenant has one `PaymentReconciliation` row with `status=verified`
and totals that exactly match the sum of that tenant's payments.

### 8. Operational alert

The Risk Center lists open findings per tenant — e.g. low attendance,
overdue fees, no guardian. Click a finding to open it; a demo **case**
was seeded from a risk finding to show the closed-loop (finding → case →
assignment → work).

### 9. Run a report

Reports/Report Builder run against the seeded data and produce results
immediately.

### 10. Switch tenant

Log out and sign in as **`mit.admin`**. The dataset is completely
different (tertiary programmes: BSc Computer Science, Engineering, …).
Student numbers, class names, subjects, and fee structures differ per
tenant.

### 11. Isolation verification

Attempt to reach another tenant's resource while logged in as a
different tenant — the API returns `403`/`404` (tenant-scoped queries
never leak existence). See §8 for the automated proof.

### 12. Audit trail

Administration → Audit Log shows the `SEED` audit event plus any actions
performed in-session. Each event is campus-scoped.

### 13. Migration engine

Administration → Data Migration: upload a CSV/XLSX export, auto-map,
validate, preview, execute, reconcile, and download the report — the
full Step 2 migration workspace, against this seeded tenant data.

### 14. Deployment explanation

Point to `docs/zero-touch-deployment.md` for the acquisition-grade
one-command deployment story.

---

## 8. Isolation is proven, not assumed

`apps/api/tests/test_enterprise_demo.py` proves at the **API level**:

- `test_api_tenant_isolation_students` — Apex admin sees only `APX-…`
  students; a direct GET of a St. Jude student is denied (`403/404`).
- `test_api_tenant_isolation_fees` — an Apex token cannot read St. Jude
  fee dues, and the Apex fee list never contains St. Jude dues.
- `test_api_tenant_isolation_audit` — audit-log IDs never overlap tenants.
- `test_rbac_demo_teacher_cannot_create_student` — a demo teacher is
  refused `students.create` (`403`); the admin succeeds (`201`).
- `test_finance_consistency` — fee-due paid amounts equal the sum of
  payments, ledger balances chain correctly, and reconciliation totals
  match.

The wider suite (`tests/test_multi_tenant/test_security_suite.py`,
`tests/test_tenant_isolation.py`) covers read/update/delete IDOR across
every tenant-owned surface.

## 9. Data scale (documented counts)

Scale is configurable:

| Scale | Students/class | Sections/class | Attendance window |
|-------|----------------|----------------|-------------------|
| `full` | 10–14 per tenant profile | 2 | 40 school days |
| `small` | 2–4 (used by the test suite) | 1 | 15 school days |

At `full` scale a tenant has hundreds of students, thousands of
attendance records, hundreds of fee dues + payments, and grade records
for Terms 1–2 across all subjects.

## 10. Troubleshooting

- **Seeder refuses to run** — you are pointed at a production database;
  set `SDMAS_ALLOW_DEMO=1` only if you explicitly intend it.
- **Already seeded** — the seeder is idempotent; use `demo-reset` to
  rebuild from scratch.
- **Risk findings empty** — the evaluator window is the last 30 days
  from *today*; re-seed (`demo-reset`) if the data is older than that.

## 11. Commands an acquirer can run to verify

```bash
docker compose up --build
./enterprise demo-seed
./enterprise health
# API-level isolation + RBAC + finance + intelligence tests:
cd apps/api && uv run pytest tests/test_enterprise_demo.py -q
```
