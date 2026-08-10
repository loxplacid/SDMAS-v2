# SDMAS v2 — Final Acquisition Readiness Report

> **Type:** Independent acquisition-readiness audit
> **Date:** 2026-08-10
> **Commit under audit:** `6109d987c33bbb50d7542098731cb387b7ace710` (verified via `artifacts/tests/test-manifest.json`)
> **Environment used for verification:** Windows 11, Python 3.13.1 (uv), Node v24.14.1, pytest 9.1.1
> **Scope:** Zero-touch deployment · Migration engine · Security/SBOM artifacts · Enterprise docs · Three-tenant demo

This report is **evidence-based**, not marketing copy. Every claim below was produced by executing the actual repository. Where something could **not** be verified in this environment, it is explicitly marked **NOT VERIFIED** — it is not converted into a positive claim.

---

## 1. Executive Summary

SDMAS v2 is substantially **acquisition-ready at the code and architecture level**: the compose stack is coherent, exactly one Alembic head exists, the three-tenant demo is deterministic and tenant-isolated through real API-level tests, the migration engine has a tested end-to-end vertical slice, and a machine-generated security/SBOM/test evidence package exists.

However, the audit found **no CRITICAL** findings, **three HIGH** findings, and several MEDIUM/LOW gaps that an acquirer's engineering team would hit on day one:

| Severity | Count | Summary |
|---|---|---|
| CRITICAL | 0 | — |
| HIGH | 3 | CI npm-audit gate currently fails; committed SBOM outputs are stale vs. lockfiles (CI determinism gate would fail); 9 documented test failures persist in the scheduler suite |
| MEDIUM | 5 | `.env.example` advertises SQLite for local dev but the SQLite migration chain is broken; README test counts are stale; live clean-boot unverified (no Docker daemon); web npm audit has high/critical findings; full-suite runtime is slow |
| LOW | 4 | Docs contain duplicated/overlapping files; minor staleness in doc claims; mobile audit findings unaddressed; no DEMO badge by default |
| OBSERVATION | 4 | Test order-dependence in scheduler file; seed-time not measured at full scale; no container-level SBOM; integration tests require Docker |

**Bottom line:** a company's CTO can deploy, understand, test, migrate data into, verify isolation of, and operate this product from the repository alone — **after** the three HIGH findings are closed.

---

## 2. Verified Capabilities

| Capability | Status | Evidence |
|---|---|---|
| Zero-touch deployment config | VERIFIED (static) | Compose config valid, 7 services, correct healthchecks & dependency graph |
| Live clean boot | NOT VERIFIED | Docker CLI present (v29.6.2, Compose v5.3.1) but daemon not running in this environment |
| Single Alembic head | VERIFIED | `alembic heads` → `043_add_migration_projects (head)` (exactly one) |
| API boots / OpenAPI | VERIFIED | `app.main:app` imports; OpenAPI parses with **358 paths** |
| Frontend tests | VERIFIED | 516 passed / 52 files |
| Frontend typecheck | VERIFIED | `tsc --noEmit` clean |
| Three-tenant demo | VERIFIED | 14 demo tests + 107 tenant-isolation tests pass |
| Migration engine | VERIFIED | 63 migration tests pass |
| RBAC boundaries | VERIFIED + FIXED | Security suite 176 pass; students POST/PATCH guard added (Step 5) |
| Security scanners | VERIFIED | Bandit, pip-audit, npm audit, Gitleaks wired into CI + `make security-audit` |
| SBOM | VERIFIED | CycloneDX 1.5 + SPDX 2.3, schema-validated, 1,910 components each |
| Test evidence manifest | VERIFIED | `artifacts/tests/test-manifest.json` (machine-generated) |
| Documentation | VERIFIED (mostly) | All sampled documented commands exist; 2 stale counts found |

---

## 3. Deployment Verification (CHECK 1)

### What was verified

- `infrastructure/docker/docker-compose.yml` — `docker compose config` **valid**, 7 services: `postgres`, `redis`, `migration-init`, `api`, `worker`, `web`, `nginx` (reverse proxy).
- **PostgreSQL healthcheck:** `pg_isready -U sdmas` (interval 5s, retries 5) — matches the actual process. ✅
- **Redis healthcheck:** `redis-cli ping` — matches the actual process. ✅
- **migration-init:** one-shot `alembic upgrade head` with `depends_on: postgres: service_healthy`; API and worker both use `depends_on: migration-init: service_completed_successfully` — **migrations run before API/worker, once, by a dedicated job** (not per-API-replica). ✅
- **API ports** `8000:8000`, `restart: unless-stopped`.
- **Worker healthcheck:** `HEALTHCHECK NONE` with a documented rationale (it is a background process, not a web server; relies on `restart: unless-stopped`). This is the **honest** implementation Step 1 required — no fake HTTP healthcheck against a port the worker does not serve. ✅
- **Frontend Dockerfile:** multi-stage (node:20-alpine → nginx:1.27-alpine), non-root `sdmas` user, healthcheck on `/health-check`. The `COPY infrastructure/nginx/default.conf` **resolves** — the file lives at `apps/web/infrastructure/nginx/default.conf`, inside the `apps/web` build context. ✅
- **Nginx routing:** dev config serves the SPA and proxies `/api/` → `api:8000`; production config adds rate limiting, CSP, and an `upstream api_servers` block. ✅
- **Zero-touch env:** compose supplies dev defaults (`JWT_SECRET=dev-secret-do-not-use-in-production`, `DATABASE_URL`, `REDIS_URL`) — no manual env editing required for a demo boot. ✅
- **Recovery:** compose uses named volumes + `restart: unless-stopped`; repeated `alembic upgrade head` is idempotent (verified conceptually; see migration limitation below for SQLite).

### Findings

- **[MEDIUM] Live clean boot NOT VERIFIED.** Docker daemon is not running in this audit environment (`docker info` cannot connect). Static config, healthchecks, and dependency graph were verified; a real `docker compose down -v && docker compose up --build` execution must be run in a Docker-capable environment before claiming the acceptance test passed. **Do not** accept this report as proof of a live boot.

---

## 4. Database Verification (CHECK 2)

- **Exactly one head:** `alembic heads` → `043_add_migration_projects (head)`. ✅
- **Migration from empty Postgres:** CI has a dedicated `migrations` job (Postgres 16 service, `DATABASE_URL` set, runs `alembic upgrade head`); cannot be executed locally without Docker. Marked **NOT VERIFIED in this environment**, but the CI path exists and the single-head invariant is verified.
- **[MEDIUM] Fresh SQLite migration fails.** `alembic upgrade head` against `sqlite+aiosqlite://` fails at `c09b48a8d73d_create_document_tables.py` with `No support for ALTER of constraints in SQLite dialect` (document tables create FKs outside `batch_alter_table`).
  - **Mitigating fact:** this is **documented** in `KNOWN_LIMITATIONS.md` (lines 38–40) — "SQLite migration chain is broken before `034` (a non-batch ALTER in `c09b48a8d73d`); tests use `Base.metadata.create_all` on SQLite". It does **not** affect the Docker/Postgres path.
  - **Gap:** `.env.example` line 19 still says *"SQLite for local dev, PostgreSQL for production"* with no caveat, and `docs/zero-touch-deployment.md` does not mention it. A developer following `.env.example` will hit the failure.
  - **Recommended fix:** update `.env.example` comment to point SQLite users at `KNOWN_LIMITATIONS.md` or at `make dev` (Docker); optionally add a `batch_alter_table` migration for the document tables.

---

## 5. Application Verification (CHECK 3)

- **API loads:** `from app.main import app` imports cleanly. ✅
- **OpenAPI loads:** parsed schema contains **358 paths**. ✅
- **Frontend loads (build-level):** `npm test` (516 pass), `tsc --noEmit` clean, `npm run build` gate exists in CI. Browser-level load NOT VERIFIED (no running stack).
- **Authentication/tenant context:** covered by `test_auth` + `test_tenant_isolation` groups (all passing in the audit run; see §10).

---

## 6. Migration Verification (CHECK 5)

- **Suite:** `tests/test_migration_step2.py` + `tests/test_migration_workspace.py` → **63 passed** in this audit (35.36s), and the Step 3 manifest recorded the same 63/63.
- **Coverage includes:** CSV discovery, schema inference, mapping, transformation, validation (incl. duplicate/orphan detection), tenant IDOR isolation, permissions, execution, reconciliation, audit, rollback safety, resume/idempotency.
- **Demo fixture:** `apps/api/tests/fixtures/legacy_demo_migration.csv` exists for a realistic end-to-end run (upload → map → validate → execute → verify DB → verify reconciliation → verify audit).
- **Worker integration:** `app.domains.migration.import_job` is registered in `app/domains/jobs/loader.py` — imports run through the **durable jobs system**, not synchronously in HTTP. ✅
- **Finding:** none blocking. The migration domain is the strongest area of the product from an acquirer standpoint.

---

## 7. Security Verification (CHECK 6)

Actual scanner results (from committed evidence artifacts + re-execution):

| Scanner | Result | CI Gate |
|---|---|---|
| **Bandit** (Python SAST) | 32 findings — **12 LOW, 20 MEDIUM, 0 HIGH** | Fail on HIGH → **PASS** |
| **pip-audit** (Python deps) | **0 vulnerabilities** | Fail on any → **PASS** |
| **npm audit — web** | 12 findings — **4 moderate, 7 high, 1 critical** | `npm audit --audit-level=high` → **FAIL** |
| **npm audit — mobile** | 43 findings — **1 low, 11 moderate, 30 high, 1 critical** | Mobile job does not run npm audit |
| **Gitleaks** (secrets) | Wired in CI (`gitleaks-action@v2`) + `scripts/security-audit.sh` (skips gracefully if not installed locally) | CI gate |
| **.env tracking guard** | Present per CI header comment | CI gate |

### Findings

- **[HIGH] The web `npm audit` CI gate is currently red.** CI runs `npm audit --audit-level=high` (line 219) and the committed evidence (`artifacts/security/npm-audit-web.json`) shows **7 high + 1 critical** web vulnerabilities. Either the lockfile was remediated after the artifact was generated (then the artifact is stale and must be regenerated) or CI fails on the main branch. **Both states are a problem** — resolve the vulnerabilities or, if genuinely acceptable for the demo, document a severity-gate exception policy (Step 3 allows this when documented).
- **[HIGH] SBOM outputs are stale vs. current lockfiles.** `git diff --stat sbom/output` shows ~10.9k insertions (node inventory, `sbom.cdx.json`, `sbom.spdx.json`, etc. changed) — the committed SBOMs do **not** match the current `package-lock.json` (animejs/motion were added earlier). The SBOM CI workflow enforces a **determinism gate** (`SOURCE_DATE_EPOCH` pinned + diff check) — a fresh run would fail it. **Fix:** regenerate `sbom/output` from the current lockfiles and commit.
- **[MEDIUM] Bandit has 20 MEDIUM findings.** None block the gate (HIGH only), but an acquirer's security team will want them triaged. Evidence file: `artifacts/security/bandit.json`.
- **[MEDIUM] Mobile dependency debt (43 findings, 30 high).** Documented in the Step 3 report as largely Expo/React-Native toolchain awaiting upstream fixes; not gated in CI. Acceptable only if documented as a known limitation in the handoff checklist.
- **[OBSERVATION]** No container-image scan (Trivy etc.) is present. Step 3 listed it as "if available/appropriate" — flag as a recommended addition, not a defect.

---

## 8. SBOM Verification

- **Formats:** `sbom/output/sbom.cdx.json` declares **CycloneDX 1.5**; `sbom/output/sbom.spdx.json` declares **SPDX 2.3** — verified against the JSON content, not just filenames. ✅
- **Validation:** `python -m sbom.cli validate --dir sbom/output` → **2 documents, 0 errors** (schema, identifiers, licenses, PURLs, reference integrity). ✅
- **Contents:** 1,910 components/packages each (Python + Node ecosystems, hashes, PURLs, dependency relationships, licenses).
- **Determinism:** metadata timestamp pinned to epoch (reproducible-build philosophy preserved).
- **Unit tests:** `sbom/tests` → **48 passed**.
- **Finding:** **[HIGH] outputs must be regenerated and committed** (see §7) or the CI determinism gate fails on the next run.

---

## 9. Test Verification (CHECK 7)

### Machine-generated manifest (`artifacts/tests/test-manifest.json`, commit `6109d987`)

| Suite | Tests | Passed | Failed | Skipped | Duration |
|---|---|---|---|---|---|
| api-finance | 58 | 58 | 0 | 0 | 70.8s |
| api-migration | 63 | 63 | 0 | 0 | 52.1s |
| api-outbox | 68 | 59 | **9** | 0 | 33.3s |
| api-security | 176 | 176 | 0 | 0 | 329.4s |
| sbom | 48 | 48 | 0 | 0 | 6.0s |
| web | 516 | 516 | 0 | 0 | 57.6s |
| **Total** | **929** | **920** | **9** | **0** | **549.1s** |

### Independent audit re-runs (this report)

- `tests/test_migration_step2.py tests/test_migration_workspace.py` → **63 passed** ✅
- `tests/test_enterprise_demo.py tests/test_tenant_isolation.py tests/test_multi_tenant` → **107 passed** ✅
- `test_security_suite + test_academic/test_api` → **77 passed** ✅
- `test_risk + test_permissions + test_student + test_auth` → **201 passed** ✅
- `test_async_hardening + test_jobs + test_outbox` → **66 passed, 2 failed** (scheduler)
- `test_async_hardening/test_scheduler.py` isolated → **3 passed, 7 errors at setup** (import-order isolation defect, see below)
- `tests/test_scheduler.py::TestPeriodicJobs::test_billing_period_end_*` → fails with `can't compare offset-naive and offset-aware datetimes`
- Web (`npm test`) → **516 passed** (52 files) ✅
- Full CI-configured command `pytest tests -m "not integration"` → timed out at 580s after **~849 tests with zero failures** (suite is slow; see below)

### Findings

- **[HIGH] Nine tests are documented as failing and still fail.** All in `test_async_hardening/test_scheduler.py` (`TestCycleEnqueue` ×2–3, `TestPeriodicJobs` billing/communications set, plus setup errors). CI's API job runs `pytest tests -m "not integration"`, which includes this file — so **CI would be red**. Root causes observed:
  1. `test_cycle_enqueues_exactly_one_job_per_task` / `test_cycle_is_idempotent_across_scheduler_instances` — cycle-enqueue semantics.
  2. `test_billing_period_end_invoices_each_due_subscription` — naive-vs-aware datetime comparison in the billing job.
  3. Running the file in isolation produces 7 setup errors (`NoReferencedTableError: enrollments.student_id could not find table 'students'`) — **test-order/import dependency** (models registered by other test modules), not a production defect, but fragile.
  - **Recommended fix:** fix the datetime comparison, make the scheduler tests self-contained (import all models in the module), and re-run to a documented green state. If scheduling semantics are intentionally out of scope for the acquisition, mark them `xfail` with a ticket — the current state (documented-but-failing) is the worst option because CI appears red.
- **[MEDIUM] Full suite runtime is ~10+ minutes** (580s timed out before completion at ~54%). Acceptable for CI but slow for acquirer onboarding; consider splitting the scheduler tests or using `-x` in dev.
- **[OBSERVATION]** README says *"1,499 tests"* and *"513 web tests"* — actual collected count is **1,583 backend tests** (incl. integration) and **516 web tests**. Stale counts; update README.

---

## 10. Multi-Tenant Verification (CHECK 4)

- **Seed:** `uv run seed --profile enterprise-demo` creates **Apex Global School (APX)**, **St. Jude Public Academy (STJ)**, **Metropolitan Institute of Tech (MIT)** through the real `Campus`/`Institution`/`UserSchoolMembership` tenancy — no demo bypass of tenant architecture.
- **Isolation:** `tests/test_enterprise_demo.py` (14 tests) + `tests/test_tenant_isolation.py` + `tests/test_multi_tenant` (107 combined) prove at the **API level** that Tenant A cannot read/infer/alter Tenant B students, fees, audit events, or migration sessions (403/404). ✅
- **RBAC:** the Step 5 audit fixed a genuine privilege-escalation gap — `POST/PATCH /students` now enforce `students.create`/`students.update` (were unguarded). Verified no regressions (77 + 201 suites green). ✅
- **Determinism:** all timestamps anchored to the seed's anchor date; fixed RNG seeds; `--scale` and reset-guard options; idempotent re-seed. ✅
- **Demo guard:** `demo-reset` requires explicit confirmation; seeder refuses non-demo databases. ✅
- **Finding:** **[OBSERVATION]** only `small` scale is exercised in tests; full-scale seed time/row counts are documented as not yet measured on Docker (documented in `docs/enterprise-demo.md`).

---

## 11. Documentation Verification (CHECK 8)

### Commands verified against the repository (all exist)

| Documented command | Repository state |
|---|---|
| `./enterprise up / down / health / logs / test / audit / reset / migrate / demo-seed / demo-reset` | ✅ All implemented in `enterprise` |
| `docker compose -f infrastructure/docker/docker-compose.yml -p sdmas up --build --detach` | ✅ File + services valid |
| `./infrastructure/scripts/verify-health.sh` | ✅ Exists, executable |
| `make dev / migrate / seed / build / deploy / rollback / migrate-rollback / migrate-autogenerate / migrate-history / backup / restore / test / test-all / test-web / lint / format / security-audit / security-audit-offline / health / metrics / logs / ps / shell` | ✅ All targets exist |
| `uv run seed --profile enterprise-demo [--scale small]` | ✅ Wired in `scripts/seed.py` + `pyproject.toml` (`seed-enterprise-demo` entry) |
| `make security-audit` / `./enterprise audit` | ✅ Both produce the evidence package |

### Findings

- **[MEDIUM]** `README.md` test-count claims are stale (1,499 vs. 1,583 collected; 513 vs. 516 web).
- **[MEDIUM]** `.env.example` SQLite claim contradicts the known-broken SQLite migration chain (see §4).
- **[LOW]** Multiple overlapping security docs exist at different paths (`SECURITY.md`, `docs/SECURITY_POLICY.md`, `docs/security-policy.md`, `docs/security-assurance-report.md`) — an acquirer may read a stale one. Consider a single canonical pointer.
- **[LOW]** No broken file references found in the three primary delivery docs (`zero-touch-deployment.md`, `enterprise-demo.md`, `security-assurance-report.md`) — the check passed.

---

## 12. Demo Verification (CHECK 4 / CHECK 5 / §10)

- 14 demo tests pass (determinism, distinct datasets, idempotency, API tenant isolation ×3, RBAC, finance consistency, risk findings from real engine, reset guard/removal/reseed, environment completeness, demo login).
- Intelligence demo is **real**: `RiskService.recompute` generates findings from seeded conditions (low attendance, consecutive absences, overdue fees, grade decline, missing guardians) — no fabricated alerts.
- Finance demo is **internally consistent**: payments journal through the real ledger; reconciliation rows match payment sums; overdue/high-outstanding accounts engineered to trigger risk rules.
- **Gap (Step 3 reviewer finding, resolved in Step 5):** DEMO-environment indicator now exists as a header badge behind `VITE_DEMO_MODE=1` — **[OBSERVATION]** it is off by default, so a fresh demo boot does not visibly indicate "DEMO ENVIRONMENT". Document the env var in the handoff checklist (already in `apps/web/.env.example`).

---

## 13. Known Limitations

1. **Live Docker boot not executed** in this audit (daemon unavailable) — static verification only. *(MEDIUM)*
2. **9 failing scheduler tests** persist; CI API job is red until fixed or xfailed. *(HIGH)*
3. **Web npm audit** high/critical findings — gate fails; needs remediation or a documented policy. *(HIGH)*
4. **SBOM outputs stale** vs. lockfiles — determinism gate would fail on next run. *(HIGH)*
5. **SQLite `alembic upgrade` broken** before `034`; documented but `.env.example` still recommends SQLite. *(MEDIUM)*
6. **Mobile npm audit** 43 findings (30 high) unaddressed — largely Expo toolchain; must be a documented, consciously accepted limitation. *(MEDIUM)*
7. **Full CI suite runtime** >10 min; integration tests require Docker. *(MEDIUM)*
8. **No container-image scan** (Trivy) in the evidence pipeline. *(LOW)*
9. **DEMO badge off by default**; full-scale seed timing unmeasured. *(LOW)*

---

## 14. Remaining Technical Risks

| Risk | Severity | Detail |
|---|---|---|
| CI shows red on main | HIGH | The three HIGH findings each independently make CI fail (npm audit gate, SBOM determinism gate, scheduler tests). An acquirer cloning and running CI sees failure on day one. |
| Scheduler timezone bug | HIGH | `billing.period_end` compares naive vs. aware datetimes — a genuine code defect, not just a test problem. Billing jobs could misbehave in production at DST boundaries. |
| Untested clean-boot path | MEDIUM | Compose wiring is static-correct, but nothing has executed it end-to-end in this environment. |
| Stale evidence artifacts | MEDIUM | `artifacts/*` are a snapshot; any dependency change invalidates them until regenerated. |
| Mobile supply-chain debt | MEDIUM | 30 high-severity findings in the mobile tree, accepted by documentation only. |

---

## 15. Recommended Final Fixes (in priority order)

1. **[HIGH] Fix the billing timezone bug + scheduler test isolation** in `apps/api/app/domains/jobs/` and `apps/api/tests/test_async_hardening/test_scheduler.py`; re-run to green. This unblocks the CI API job and removes a genuine production defect.
2. **[HIGH] Regenerate + commit `sbom/output`** from current lockfiles; re-run `make security-audit` and commit the fresh evidence artifacts so the determinism gate passes.
3. **[HIGH] Resolve or policy-gate the web npm audit findings** (`apps/web/package-lock.json`): either upgrade the vulnerable transitive deps or add an explicit, documented severity-gate exception in CI and `docs/security-assurance-report.md`.
4. **[MEDIUM]** Fix `.env.example` SQLite wording to reference `KNOWN_LIMITATIONS.md` / Docker dev path.
5. **[MEDIUM]** Update README test counts (1,583 backend collected / 516 web).
6. **[MEDIUM]** Consolidate the duplicate security docs into one canonical file with pointers.
7. **[LOW]** Add a Trivy container-scan step to the evidence pipeline.
8. **[LOW]** Enable `VITE_DEMO_MODE=1` in the demo compose profile so the DEMO badge shows by default in demo boots.

---

## 16. Exact Verification Commands

```bash
# Static compose validation
docker compose -f infrastructure/docker/docker-compose.yml config --quiet && echo VALID
docker compose -f infrastructure/docker/docker-compose.yml config --services

# Clean boot (requires a running Docker daemon — NOT executed here)
docker compose -f infrastructure/docker/docker-compose.yml -p sdmas down -v
docker compose -f infrastructure/docker/docker-compose.yml -p sdmas up --build --detach
./enterprise health

# Database
cd apps/api && uv run alembic heads          # expect exactly one: 043_add_migration_projects (head)

# Three-tenant demo
cd apps/api && uv run seed --profile enterprise-demo --scale small
uv run pytest tests/test_enterprise_demo.py -q

# Tenant isolation + RBAC
uv run pytest tests/test_tenant_isolation.py tests/test_multi_tenant tests/test_permissions.py -q

# Migration engine
uv run pytest tests/test_migration_step2.py tests/test_migration_workspace.py -q

# Security + SBOM evidence package (regenerate + commit the artifacts)
make security-audit            # or: ./enterprise audit
PYTHONPATH=sbom python -m sbom.cli validate --dir sbom/output

# Full CI-configured test run (allow >12 min)
cd apps/api && uv run pytest tests -q -m "not integration"

# Frontend
cd apps/web && npm test && npx tsc --noEmit && npm run build
```

---

## 17. Acquisition Handoff Checklist

- [ ] Close the three HIGH findings (§15 items 1–3) so CI is green on `main`.
- [ ] Execute a **live** `docker compose down -v && up --build` on a Docker-capable machine and record health output (this audit could not).
- [ ] Regenerate and commit `artifacts/*` + `sbom/output` from the final lockfiles.
- [ ] Confirm `alembic upgrade head` from an empty **PostgreSQL** database (CI `migrations` job covers this).
- [ ] Verify demo credentials (`apex.admin` / `stjude.admin` / `mit.admin`) are dev-only and marked DEMO in the UI.
- [ ] Document the mobile npm-audit debt as a consciously accepted limitation (or remediate).
- [ ] Update README test counts and `.env.example` SQLite wording.
- [ ] Add a container-image scan to the evidence pipeline.
- [ ] Hand the evaluator `docs/enterprise-demo.md` (15-minute walkthrough) and this report.
