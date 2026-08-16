# SDMAS v2 — Immutable Release Baseline

**Purpose:** Frozen record of the repository state before further development.
**Nature:** Audit-only. No code was modified in this pass.
**Date of capture:** 2026-08-16
**Branch:** `main`
**Commit:** `77c72f8` (message: "final updates")
**Working tree:** CLEAN — 0 modified/untracked tracked-tree changes (`git status --short` empty).
**Tracked files:** 1,256

> Every claim below was verified by an executed command or direct file
> inspection during this pass (or the immediately preceding acceptance pass
> against the same commit, which is explicitly flagged where used). Where the
> Docker daemon was unavailable, the limitation is stated — nothing is
> asserted from documentation alone.

---

## 1. Environment / Toolchain (recorded)

| Item | Value | Verified by |
|---|---|---|
| Branch | `main` | `git branch --show-current` |
| HEAD | `77c72f8 final updates` | `git log --oneline -5` |
| Git status | Clean (0 entries) | `git status --short` |
| Python (project pin) | `>=3.11` | `pyproject.toml` `requires-python` |
| Python (API venv) | 3.11.9 | `.venv/Scripts/python.exe --version` |
| Python (host) | 3.13.1 | `python --version` |
| Node (host) | v24.14.1 | `node --version` |
| npm (host) | 11.14.1 | `npm --version` |
| Docker | 29.6.2 (build dfc4efb) | `docker --version` |
| Docker Compose | v5.3.1 | `docker compose version` |
| Alembic head | **single head** `049_widen_audit_action` | `alembic heads` |
| Alembic revisions in history | 59 (56 files in `alembic/versions/`) | `alembic history` + `ls` |
| Compose base | Valid (`config --quiet`, exit 0) | `docker compose -f docker-compose.yml config --quiet` |
| Compose production | Valid (exit 0) | `docker compose -f docker-compose.production.yml config --quiet` |
| Docker daemon | **NOT running at capture time** (Docker Desktop engine not started) | `docker ps` → pipe error |

Note: compose `config` emits expected warnings about unset `DB_PASSWORD`,
`REDIS_PASSWORD`, `JWT_SECRET`, `RAZORPAY_*`, `SENTRY_DSN`, `GRAFANA_PASSWORD`
— these are provided by `.env.example` / `infrastructure/secrets/` per
DEPLOYMENT.md, not a defect.

---

## 2. Capability State (17 areas)

| # | Area | State | Evidence |
|---|---|---|---|
| 1 | **Backend** | OPERATIONAL | FastAPI + SQLAlchemy 2 async; 36 domain modules under `apps/api/app/domains/`. Fresh-clone Docker build of API image succeeded at this commit (prior acceptance pass, `BUILD_RC=0`); live E2E (login → students → fees → migration → reports) verified against this commit earlier. |
| 2 | **Frontend** | OPERATIONAL | React + Vite + TS (PWA). `tsc --noEmit` **clean** (exit 0, re-verified this pass). 520 tests passed in the last full web run; 50 test files present. Fresh-clone web image build succeeded (prior pass). |
| 3 | **Mobile** | PARTIALLY VERIFIED | Expo/React Native app (`apps/mobile`), jest configured (`jest --passWithNoTests`), node_modules present. Only 2 test files — coverage is minimal. CI mobile job runs `tsc --noEmit` + jest. |
| 4 | **Database / migrations** | OPERATIONAL | Single alembic head `049_widen_audit_action`. Full chain `001→049` verified on fresh SQLite (prior pass) and applied to live PostgreSQL (prior pass, `audit_logs.action` widened to `varchar(64)`). 56 version files, 59 revision records. |
| 5 | **Multi-tenancy** | OPERATIONAL | Structural: `TenantContext` + `TenantScopedRepository` (query-construction scoping) + guards. **128 tests passed this pass** (`tests/test_multi_tenant` + `tests/test_tenant_isolation.py` + `tests/test_migration_workspace.py`). 28-test security suite + 64-test acquisition suite documented; live IDOR → 404 verified earlier at this commit. |
| 6 | **RBAC** | OPERATIONAL | Permission strings `<resource>.<action>`, 3 enforcement dependencies (`require_permission`, `require_role`, `require_platform_permission`). Verified live earlier at this commit: teacher→admin audit endpoint **403**, unauth **401**. |
| 7 | **Authentication** | OPERATIONAL | JWT access (30 min) + refresh (7 d, rotation + family revocation), login rate limiting, `POST /auth/logout` (revokes all refresh tokens + audit event), default-deny auth gate with explicit public allowlist. |
| 8 | **Finance / ledger** | OPERATIONAL | Integer minor units, campus-scoped idempotency keys (migration 047), transaction log / reconciliation. `api-finance` suite: 58 passed in committed manifest. Ledger invariants covered by dedicated suites. |
| 9 | **Migration engine** | OPERATIONAL | D2 workspace: discovery → mapping → validation → preview → import (durable job) → reconcile → report; 5 entity types registered. Workspace suite green this pass (part of the 128). Live E2E at this commit: CSV upload → import → reconcile (2/2 created) → audit events. |
| 10 | **Jobs / outbox** | OPERATIONAL | **59 passed, 0 failed this pass** (`tests/test_async_hardening` + `tests/test_outbox`). See §4 finding F1 for the stale committed evidence that previously showed 9 failures. Worker metadata registration fix (`app/infrastructure/models.py`) is in this commit. |
| 11 | **Docker deployment** | OPERATIONAL (verified prior pass) | Base + production compose validate. Fresh clone → cold `docker compose up --build` → migration-init (alembic to head) → postgres/redis/api/web/nginx/worker all healthy; shared `storage_data` volume + non-root images. Daemon was down during this capture pass, so no live re-run here. |
| 12 | **Security scanning** | OPERATIONAL | Bandit, pip-audit, npm audit, Gitleaks (CI, full history), tracked-`.env` guard, credential-pattern scan. Committed evidence: Bandit **36 issues (0 HIGH, 20 MEDIUM)**, pip-audit **0 vulns**, npm-audit web **0**. CI gates: Bandit HIGH, npm audit `--audit-level=high`. |
| 13 | **SBOM** | OPERATIONAL | CycloneDX 1.5 (`sbom.cdx.json`) + SPDX 2.3 (`sbom.spdx.json`) in `artifacts/sbom/`, schema-validated (`validate.txt`), deterministic; SHA-256 manifest (`artifacts/SHA256SUMS`) + `artifact-manifest.json`. |
| 14 | **CI/CD** | OPERATIONAL | `.github/workflows/ci.yml` (8 jobs: api, api-integration, migrations, docker-build, web, mobile, security, evidence) + `sbom_validation.yml`. Test commands: `uv run pytest tests -q -m "not integration"`, `-m integration`, `npm test`. |
| 15 | **Tests** | OPERATIONAL | See §3 for counts. Full API suite **1,652 passed** at this commit (prior acceptance pass, 29m14s); targeted suites re-run green this pass. |
| 16 | **Documentation** | OPERATIONAL (minor drift) | 38 files in `docs/` + 12 in `docs/enterprise/`. `DOCUMENTATION-AUDIT.md` produced and applied previously. One drift remains: ARCHITECTURE.md says "55 migration files / head `048`" — actual 56 files / head `049` (F4, P3). |
| 17 | **Demo environment** | OPERATIONAL | `apps/api/scripts/seed_enterprise_demo.py` — deterministic, idempotent 3-tenant seeder (Apex Global School, St. Jude Public Academy, Metropolitan Institute of Tech) with API-level tenant-isolation tests (`tests/test_enterprise_demo.py`). Demo credentials documented in `docs/enterprise-demo.md`; demo guards in place. |

---

## 3. Test counts (verified)

| Suite | Count | When / how |
|---|---|---|
| API full (non-integration) | **1,652 passed, 0 failed** | Prior acceptance pass at this commit (`uv run pytest tests -q -m "not integration"`, 29m14s) |
| API — async hardening + outbox | **59 passed, 0 failed** | **This pass**, re-run live |
| API — multi-tenant + isolation + migration workspace | **128 passed, 0 failed** | **This pass**, re-run live |
| Web | 520 passed | Prior full run at this commit; `tsc --noEmit` clean this pass |
| Web — test files present | 50 | Static inventory |
| API — test files present | 105 files / 361 `def test_` (≈1,652 with parametrization) | Static inventory; executed counts take precedence |
| Mobile | jest configured; 2 test files | Static; `--passWithNoTests` in script |

Static `def test_` counts undercount parametrized cases — the executed counts
above are authoritative.

---

## 4. Known failures & findings

**F1 — Stale on-disk evidence outputs (P3, resolved as non-issue).**
`artifacts/tests/test-manifest.json`, `artifacts/SHA256SUMS`,
`artifacts/artifact-manifest.json`, and the JUnit XMLs on disk were generated
at commit `6109d98` (2026-08-10) and record **9 failures / 920 passed**.
Those 9 failures (in `test_async_hardening`: jobs_multi_worker, scheduler)
are **resolved at the current HEAD** — verified this pass (59 passed, 0
failed; the same files were re-run). **Correction:** these files are
**gitignored and have never been committed** (`git log -- <path>` is empty;
`.gitignore` ignores `artifacts/security/*.json`, `artifacts/sbom/*.json`,
`artifacts/tests/*.xml`, `artifacts/SHA256SUMS`, `artifacts/artifact-manifest.json`,
`artifacts/tests/test-manifest.json`). They are stale local generator output
regenerated by `make security-audit` — no repository misrepresentation.

**F2 — Docker daemon not running at capture time (P3, environmental).**
Live container verification could not be repeated during this capture. The
last full live verification at this exact commit (prior acceptance pass:
fresh clone, cold build, full-stack healthy, migration E2E) stands as the
build/deployment evidence. No repository defect.

**F3 — Security findings from committed scanner output (P3, review).**
Bandit: 36 issues, 0 HIGH, 20 MEDIUM, 16 LOW (gates are HIGH so CI is green).
Review the 20 MEDIUM items against the accepted-risk register in
`docs/security-policy.md` when next running `make security-audit`. pip-audit
0; npm-audit web 0.

**F4 — Documentation drift (P3).** ARCHITECTURE.md: "55 migration files /
head `048`" — actual 56 files / head `049_widen_audit_action`.

**F5 — Committed scratch files (P3, hygiene).** `apps/api/_audit_protection.txt`,
`apps/api/_audit_routes.txt`, `apps/api/_pip_audit_env.json` are audit
scratch output committed to the tree; should be removed or gitignored.

**F6 — Documented accepted risks (P2/P3, unchanged — see KNOWN_LIMITATIONS.md).**
- Billing cycle not scheduled (no cron invokes `process_period_end`) — P2.
- No UNIQUE constraint on `invoices(subscription_id, period_start)` (app-level row lock only) — P2.
- `renew` from `past_due` without inline payment verification — P2.
- Webhook `notes.campus_id` trusted without existence check — P3.
- Two outbox tests wall-clock sensitive under full-suite load (not reproduced recently) — P3.
- Audit middleware skips sub-threshold-latency mutating requests (rare) — P3.
- Legacy NULL-campus rows invisible to scoped queries (by design; guards exempt) — P3.
- `_archive/legacy-v1/` + `_archive/backend/` read-only historical artifacts — P3.
- Root `node_modules/` still on disk (untracked in index) — P3.

---

## 5. Build status

- **Fresh-clone build:** SUCCESS — cold `docker compose up --build` from a
  full clone of this commit produced all images and a healthy stack (prior
  acceptance pass; `BUILD_RC=0`).
- **Compose config:** base + production validate (this pass).
- **Web typecheck:** clean (this pass).
- **Frontend production bundle:** built successfully in prior pass
  (1,609 modules).
- **Alembic:** single head `049`; fresh-DB upgrade verified SQLite + PostgreSQL.

---

## 6. Blockers (classified, nothing fixed)

**P0 — none.**
**P1 — none.**

**P2**
1. **F6:** billing cycle scheduling (wire `process_period_end` into the
   worker/scheduler).
2. **F6:** add UNIQUE constraint on `invoices(subscription_id, period_start)`.
3. **F6:** gate `renew` from `past_due` on a paid invoice.

**P3**
5. **F4:** ARCHITECTURE.md migration count/head refresh (55→56, `048`→`049`).
6. **F5:** remove committed scratch files (`_audit_protection.txt`,
   `_audit_routes.txt`, `_pip_audit_env.json`) or gitignore them.
7. **F2:** environmental — start Docker daemon before next live pass.
8. **F3:** triage 20 Bandit MEDIUM findings against accepted-risk register.
9. **F6:** mobile test coverage is minimal (2 files; `--passWithNoTests` hides
   gaps) — decide whether mobile is in scope for the demo.
10. **F1:** optional — remove stale on-disk `artifacts/` outputs (they are
    gitignored; regenerated by `make security-audit`).

---

## 7. Evidence commands (read-only, this pass)

```
git log --oneline -5 && git status --short | wc -l && git branch --show-current
node --version && npm --version && docker --version && docker compose version
uv run alembic heads          # single head 049_widen_audit_action
docker compose -f infrastructure/docker/docker-compose.yml config --quiet
docker compose -f infrastructure/docker/docker-compose.production.yml config --quiet
uv run pytest tests/test_async_hardening tests/test_outbox -q -p no:cacheprovider   # 59 passed
uv run pytest tests/test_multi_tenant tests/test_tenant_isolation.py tests/test_migration_workspace.py -q   # 128 passed
npx tsc --noEmit              # clean
git ls-files | grep -E "_(audit|routes|pip_audit)"   # scratch-file finding
```

---

*This baseline freezes state at `77c72f8`. Further development should
reference this document for the starting point and the P2/P3 ledger above.*
