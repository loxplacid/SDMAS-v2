# Test System Baseline — SDMAS v2

Status: **CURRENT** · Measured: 2026-08-17 (commit `main` working tree) · Method: **executed runs**, not documentation claims

This is the measurable baseline for the SDMAS v2 test system. Every number
below comes from an actual run on this machine (Windows host, bash shell,
Python 3.11 via `uv`, Node for the web app). The goal: future feature work can
be measured against a known-good starting point, and a new engineer can run
exactly the commands in §5 to reproduce the state.

---

## 1. Inventory

| Suite | Location | Command | Needs Docker |
|---|---|---|---|
| Backend unit + security + async | `apps/api/tests/` (109 test files, 26 dirs) | `uv run pytest tests -m "not integration"` | no |
| Backend integration (PostgreSQL/Testcontainers) | `apps/api/tests/test_integration.py` (36 tests) | `uv run pytest tests -m integration` | **yes** |
| Backend migration validation | — | `uv run alembic heads` / `upgrade head` | no (SQLite OK) |
| Frontend unit (vitest) | `apps/web/src/__tests__/` (51 files) | `npm test` | no |
| Frontend build | — | `npm run build` | no |
| Lint/type (changed files, CI) | — | `uv run ruff check/format`, `uv run mypy` | no |

Backend test suites by directory (all part of the unit run):

`test_academic` (156), `test_async_hardening` (34), `test_attendance` (66),
`test_audit` (58), `test_auth` (77), `test_cases` (41), `test_class_360` (6),
`test_command_center` (25), `test_data_quality` (20), `test_fees` (121),
`test_finance_security` (80), `test_intelligence` (22), `test_jobs` (15),
`test_migration_*` (84), `test_multi_tenant` (113), `test_notification*` (68),
`test_notifications` (17), `test_optimization` (25), `test_outbox` (27),
`test_report_cards` (13), `test_reports` (86), `test_risk` (36),
`test_rbac_router_enforcement` (44), `test_security_acquisition` (67),
`test_simulation` (52), `test_student` (92), `test_temporal` (13),
`test_tenant_isolation` (9), `test_timeline` (20), `test_workflow` (35),
plus standalone files (`test_config` 25, `test_cors` 5, `test_database` 7,
`test_domain_boundaries` 4, `test_domain_events` 36, `test_enterprise_demo` 14,
`test_health` 6, `test_permissions` 28, `test_proxy` 14,
`test_schema_integrity` 6, `test_communications_context` 23, `test_audit_trail` 29,
`test_audit_action_width` 3, `test_teacher_360` 4).

---

## 2. Measured results (this machine, 2026-08-17)

### Backend unit suite — `-m "not integration"`

| Metric | Value |
|---|---|
| Collected | **1,726** |
| Passed | **1,726** |
| Failed | **0** |
| Skipped | **0** |
| Errors | **0** |
| Integration tests deselected | 36 |
| Total wall time | ≈ 26 min (largest: `test_multi_tenant` 6m10s, `test_enterprise_demo` 4m13s, `test_security_acquisition` 3m21s, `test_rbac_router_enforcement` 2m50s, `test_auth` 1m51s) |

Collection is clean: `pytest --collect-only` reports **1,726/1,762 collected,
36 deselected, 0 errors** — no import failures, no broken fixtures.

### Backend integration suite — `-m integration` (NOT RUN this session)

36 tests in `tests/test_integration.py` require PostgreSQL via Testcontainers.
**Not executed on this machine** because the Docker daemon is unavailable
(`docker version` times out). These run in CI's `api-integration` job
(`uv sync --frozen --all-extras && uv run pytest tests -q -m integration`).
This is a known environment-specific limitation, not a test failure.

### Frontend — vitest

| Metric | Value |
|---|---|
| Test files | 51 |
| Passed | **475** |
| Failed | 0 |
| Duration | ≈ 51s |

`npm run build` — **success** (≈ 25s, PWA `generateSW`, 199 precache entries).

### Static checks

| Check | Scope | Result |
|---|---|---|
| `ruff check` (changed files, CI) | changed files only | clean (gated in CI) |
| `ruff check` (full tree) | `app tests scripts` | **1,197 pre-existing errors** (500 E501, 327 F401, 196 I001, 55 W292, 33 F841, …) — pre-existing, not CI-gating; CI lints only changed files |
| `ruff format --check` (full tree) | `app tests scripts` | 280 files would be reformatted (pre-existing) |
| `tsc --noEmit` (web) | `apps/web` | clean |
| `alembic heads` | — | single head `051_add_missing_model_indexes` (verified in migration baseline) |

---

## 3. Test infrastructure findings (this session)

### Fixed — Makefile `test*` targets used bare `python` instead of `uv`

`Makefile` test/lint targets ran `python -m pytest` and `ruff` directly,
while CI and all docs use `uv run`. On a clean machine with only the `uv`
environment, `make test` would fail with `ModuleNotFoundError: pytest`.
**Fixed** (`Makefile`): `test`, `test-all`, `test-api`, `test-integration`,
`lint` now use `uv run` — identical to the CI commands in `.github/workflows/ci.yml`.

### Fixed — stale test counts in README

README advertised "1,652 tests" (backend) and "520 tests" (web).
Measured reality: **1,726** backend unit + **475** web. Updated README to the
measured numbers and pointed at this baseline.

### Characterized, not fixed (pre-existing)

- Full-tree `ruff` debt (1,197 errors) exists but CI intentionally gates on
  changed files only — consistent with the repo's incremental-lint policy.
  Not a release blocker; fixing the full tree is a separate cleanup task.
- Backend suite wall time is dominated by setup-heavy adversarial/security
  suites (`test_multi_tenant`, `test_enterprise_demo`). This is slow, not broken.

---

## 4. Known environment-specific failures / caveats

| Item | Status |
|---|---|
| Integration tests (36, Testcontainers/PostgreSQL) | not run — Docker daemon unavailable on this machine; runs in CI |
| `make` binary | not installed on this host (Git Bash); Makefile verified by invoking its underlying `uv run` commands directly |
| Windows path handling | nginx configs report LF→CRLF warnings on checkout; harmless |
| Full-tree ruff/format | pre-existing debt; CI unaffected (changed-file scope) |

---

## 5. Repeatable verification commands

### Backend (unit/security/async, no Docker)

```bash
cd apps/api
uv run pytest tests -q -m "not integration"          # full unit suite
uv run pytest tests/test_health.py -q                 # smoke subset
uv run pytest --collect-only -q -m "not integration"  # collection/import check
```

### Backend (integration — requires Docker)

```bash
cd apps/api
uv sync --frozen --all-extras
uv run pytest tests -q -m integration
```

### Backend migrations

```bash
cd apps/api
uv run alembic heads          # expect: exactly one head
uv run alembic upgrade head   # idempotent
```

### Frontend

```bash
cd apps/web
npm test          # vitest (475 tests)
npm run build     # production build
npx tsc --noEmit  # typecheck
```

### Static checks (CI-equivalent, changed files)

```bash
cd apps/api
uv run ruff check <changed files>
uv run ruff format --check <changed files>
uv run mypy --no-incremental <changed files> --follow-imports=skip
```

### Makefile shortcuts (fixed to use `uv`)

```bash
make test          # backend unit suite
make test-all      # full backend suite incl. integration (needs Docker)
make test-web      # frontend vitest
make lint          # ruff check + format check
```

---

## 6. Baseline for future feature work

- **Backend:** a new feature must keep the unit suite green (1,726 passed,
  0 failed) and add tests for its own behavior. Run the affected domain suite
  first (see inventory §1), then the full unit suite.
- **Frontend:** keep vitest green (475 passed) and `npm run build` succeeding.
- **Integration:** changes touching PostgreSQL behavior should add a
  `-m integration` test; it will run in CI's Docker job.
- **Migration changes:** must keep `alembic heads` at exactly one head and
  `upgrade head` idempotent (see `docs/architecture/CURRENT_STATE.md`).

---

## 7. Related documents

- `docs/architecture/CURRENT_STATE.md` — migration/schema baseline
- `docs/architecture/DATA_MODEL.md` — schema inventory
- `docs/architecture/DOMAIN_CONTRACTS.md` — enforced by `test_domain_boundaries.py`
- `docs/enterprise/CI-CD-AUDIT.md` — pipeline audit (prior session)
- `.github/workflows/ci.yml` — the authoritative CI test commands
