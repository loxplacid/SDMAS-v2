# CI/CD Pipeline Audit — SDMAS v2

Date: 2026-08-14 · Reviewed as an acquirer's DevOps engineer would: inspect the
workflows, then run the pipeline-equivalent commands locally. No claim in this
report rests on YAML merely parsing — every step below was executed.

## Summary

| # | Severity | Finding | Status |
|---|---|---|---|
| 1 | **P1** | Bandit gate contradicted its documented policy: bandit exits 1 on *any* finding, so the "fail on HIGH only" evidence gate actually failed on every push (36 findings, 0 HIGH) | **Fixed** |
| 2 | **P1** | gitleaks-action requires a `GITLEAKS_LICENSE` secret for org repos — a fresh acquirer clone without it fails CI on setup | **Fixed** (license-free CLI) |
| 3 | **P2** | CI never built any Docker image (0 Dockerfile references) — Dockerfile regressions surfaced only at deploy time | **Fixed** (new `docker-build` job) |
| 4 | **P2** | `GATE_FAILURES` in `security-audit.sh` was dead code — initialized and checked, never populated; the CI caller also wrapped it in `\|\| true` | **Fixed** |
| 5 | **P2** | Evidence script misreported npm audit as "failed" when a vulnerable app's report was actually saved (npm exits 1 on findings) | **Fixed** |
| 6 | **P3** | Mobile `--passWithNoTests` would let a zero-test regression pass | **Fixed** |
| 7 | P3 | All actions unpinned (floating major tags) — supply-chain hygiene | Documented |
| 8 | OBS | `alembic check` unreliable here: env.py's target_metadata is curated, so autogenerate reports raw-SQL tables (txn_log, outbox) and unmapped domains as drift | Documented |

## Pipeline shape

`.github/workflows/ci.yml` (8 jobs): `api` (lint/format/mypy on changed files +
full non-integration suite), `api-integration` (testcontainers), `migrations`
(single-head + upgrade on Postgres 16), `docker-build` (new), `web` (tsc,
vitest, build, npm audit), `mobile` (tsc, jest), `security` (gitleaks + .env
guard + credential scan), `evidence` (bandit, pip-audit, SBOM, artifact
package). Plus `sbom_validation.yml` (regeneration + schema validation +
determinism gate). Correct gates: web `npm audit --audit-level=high`, SBOM
determinism `git diff --exit-code`, `alembic upgrade head` against a fresh
Postgres, test suites with no `continue-on-error`.

## Findings & fixes

### 1. P1 — Bandit gate failed on every run (fixed)

`ci.yml` evidence job ran `uv run bandit -r app -f json -o ../bandit.json -q`
with no `|| true`. Bandit exits **1 when any finding exists** (verified: 36
findings, 0 HIGH → exit 1). Under the step's `bash -e`, the documented
HIGH-only gate (checked via the JSON after) never ran — the step failed on
every push. Fixed by writing the report always and gating on the JSON count,
matching the documented policy in `docs/security-policy.md`.

### 2. P1 — gitleaks-action secret dependency (fixed)

`gitleaks/gitleaks-action@v2` requires `GITLEAKS_LICENSE` for organisation
repositories. An acquirer cloning into a new org without that secret gets a
CI failure before any scan. Replaced with the official `zricethezav/gitleaks`
container CLI — license-free, `detect --source /repo` over full history.
Verified locally: 54 commits, 43 MB, **no leaks**.

### 3. P2 — Docker images never built in CI (fixed)

`ci.yml` had zero Dockerfile references; only the Makefile built images, and
never in CI. Added a `docker-build` job (buildx + gha cache, `push: false`)
building `sdmas-api`, `sdmas-worker`, and `sdmas-web` (contexts match
`docker-compose.yml`: api context `apps/api`, web context `apps/web` — the web
Dockerfile copies `infrastructure/nginx/*` relative to its context), plus a
healthcheck-shape smoke test (`app.main` imports, `nginx -t`). The base-image
security fixes from the supply-chain audit would previously have shipped
unverified.

### 4. P2 — Dead `GATE_FAILURES` gate (fixed)

`scripts/security-audit.sh` declared `GATE_FAILURES=()` and checked it at the
end, but nothing ever appended to it, and the CI caller wrapped the script in
`|| true` — the script could not fail. Now the bandit (HIGH), pip-audit
(un-waived vulns, honouring the `PIP_AUDIT_IGNORES` list synced with CI), and
SBOM validation steps append real failures, the CI `|| true` is removed, and
the script exits non-zero when a gate is exceeded. Verified: full
`--ci-evidence-only` run passes (20-file checksums, manifest, assurance
report); the script now correctly reports `mobile: report saved`.

### 5. P2 — npm audit "failed" misreport (fixed)

The script judged npm audit by exit code, but npm exits 1 *when it finds
vulnerabilities* while still writing the JSON — so a vulnerable app was
reported "failed" even though the evidence was saved (mobile: 43 findings).
Now judged by the report file's existence.

### 6. P3 — mobile `--passWithNoTests` (fixed)

`npx jest --passWithNoTests` would let a deleted test suite pass silently.
Removed; mobile has 2 suites / 24 tests which now genuinely gate.

### 7. P3 — unpinned actions (documented)

All actions use floating major tags (`actions/checkout@v4`, `setup-python@v5`,
`setup-uv@v5`, `setup-node@v4`, `docker/*@v3/v6`). For acquisition-grade
supply-chain hygiene, pin to full-length SHAs and enable Dependabot to update
them. Not mass-pinned here to avoid a large mechanical diff without a Dependabot
config to keep them current.

### 8. OBS — `alembic check` is not a usable drift gate here

Tested `alembic check` on a freshly migrated DB: it reports hundreds of
spurious operations. Root cause: `alembic/env.py` imports a curated model set;
raw-SQL tables (`txn_log`, `outbox_events`) and unmapped domains (billing,
jobs, migration) are absent from `target_metadata`, so autogenerate treats them
as drift. Not added to CI. The migrations job's real gates — single head +
`upgrade head` against fresh Postgres — are sound.

## Local pipeline-equivalent execution (all CI commands run verbatim)

| CI step | Command | Result |
|---|---|---|
| API deps | `uv sync --frozen --extra dev` | Audited 99 packages, rc=0 |
| Migration head | `alembic heads` count | 1 head ✓ |
| API suite | `uv run pytest tests -q -m "not integration"` | **1652 passed, 36 deselected** (29m14s) |
| Web typecheck | `npx tsc --noEmit` | pass |
| Web tests | `npm test` | **520 passed / 53 files** |
| Web audit gate | `npm audit --audit-level=high` | 0 vulnerabilities |
| Mobile tests | `npx jest` | **24 passed / 2 suites** |
| SBOM generate | `python -m sbom.cli generate` (SOURCE_DATE_EPOCH=0) | 1881 pkgs, 0 errors, byte-deterministic |
| SBOM validate | `python -m sbom.cli validate` | 2 documents, 0 errors |
| Evidence package | `bash scripts/security-audit.sh --ci-evidence-only` | all gates passed, 20-file SHA256SUMS |
| Backend SAST (local) | bandit full repo | 36 findings, 0 HIGH (gate passes) |
| Python vulns | pip-audit (venv) | 1 finding — `ecdsa`, waived W-001 (gate passes) |

## Files changed

- `.github/workflows/ci.yml` — bandit gate fix, gitleaks CLI replacement, new
  `docker-build` job, evidence `|| true` removed, mobile `--passWithNoTests`
  removed.
- `scripts/security-audit.sh` — live `GATE_FAILURES` (bandit/pip-audit/SBOM),
  `PIP_AUDIT_IGNORES` synced with CI, npm audit misreport fixed, SBOM validate
  count fixed.

## Verification commands for an acquirer

```bash
# Validate workflow YAML
python -c "import yaml; yaml.safe_load(open('.github/workflows/ci.yml'))"

# Reproduce each job locally (from repo root)
cd apps/api && uv sync --frozen --extra dev
uv run pytest tests -q -m "not integration"
uv run alembic heads          # expect exactly one line

cd apps/web && npm ci && npx tsc --noEmit && npm test && npm run build
cd apps/mobile && npm ci && npx tsc --noEmit && npx jest

# Evidence + SBOM (repo root)
bash scripts/security-audit.sh
SOURCE_DATE_EPOCH=0 python -m sbom.cli generate --output-dir sbom/output
python -m sbom.cli validate --dir sbom/output
git diff --exit-code -- sbom/output   # determinism gate
```
