# Supply-Chain & Application Security Audit — SDMAS v2

Date: 2026-08-14 · All results below were produced by executing the scanners
against the current repository state. No counts are quoted from documentation.

## Summary

| Surface | Tool | Result | Class |
|---|---|---|---|
| Python SAST | Bandit | 36 findings, **0 HIGH** | all false positives / intentional |
| Python deps | pip-audit | **1** finding (`ecdsa` PYSEC-2026-1325) | accepted risk (no fix, unreachable path) |
| Web deps | npm audit | **0** vulnerabilities | clean |
| Mobile deps | npm audit | 43 (30 high, 1 critical `tar`) | development-only (Expo build toolchain) |
| Containers | Trivy image scan (4 images) | web 35→**0**; api/worker/mig python 3→1 | **fixed** (see §4) |
| Repo secrets | pattern scan (git-tracked) | 0 hits | clean (`.env` ignored, only `.env.example` tracked) |
| SBOM | `sbom.cli generate/validate` | CycloneDX 1.5 + SPDX-2.3, 1881 pkgs, 0 schema errors | **stale outputs fixed** |

Exploitable: **0** · Development-only: mobile Expo toolchain · False positive: all
36 Bandit findings · Accepted risk: 1 (ecdsa).

## 1. Python — Bandit

Command: `uv run bandit -r app/ -q -f json` (36 findings)

| ID | Count | Severity | Classification | Evidence |
|---|---|---|---|---|
| B608 | 20 | MEDIUM/LOW | False positive | SQL-injection-shaped f-strings; every interpolated identifier is a hardcoded literal (`_scope()` calls), user data is always bound as parameters |
| B105/B106/B107 | 5 | LOW | Intentional / FP | `config.py` dev placeholders (`change-me`) are guarded by the `_reject_default_secrets_in_production` model validator — production refuses to boot with them; remaining hits are parameter-name false positives (`token_type="refresh"`) |
| B110/B112 | 10 | LOW | Intentional | Deliberate exception containment (`# noqa: BLE001 — one check must not break the run`; per-row export skip) |
| B406 | 1 | LOW | False positive | `xml.sax.saxutils.escape` is the *safe* XML escaping helper, not an unsafe parser |

No HIGH findings → the CI SAST gate passes.

## 2. Python — pip-audit

Command: `uv run pip-audit --local` (installed venv)

- `ecdsa 0.19.2` — **PYSEC-2026-1325** — no upstream fix available.
- Path: transitive via `python-jose[cryptography]`; the app signs/verifies JWT
  with **HS256** exclusively (`jwt_algorithm` default, no ES256 usage), so the
  ECDSA/P-256 code path is never exercised with untrusted input.
- Documented as **W-001** in `docs/security-policy.md`, waived in CI via
  `--ignore-vuln PYSEC-2026-1325`. Classification: **accepted risk**.

## 3. Node — npm audit

Web (`apps/web`, `--audit-level=high` — the CI gate): **0 vulnerabilities**.
Key versions: `react-router-dom 7.18.2`, `xlsx 0.20.3` (SheetJS CDN tarball).

Mobile (`apps/mobile`): **43 findings** (30 high, 1 critical — `tar`; rest
moderate/low). All are Expo/React Native build-toolchain packages
(`@expo/cli`, `@expo/metro-config`, `xmldom`, `tar`) — build-time/dev-only,
not shipped to production runtime. Documented as **W-005** (OPEN — TRACKED);
matches the documented state exactly.

## 4. Containers

**Dockerfile review** — all three Dockerfiles (`apps/api/Dockerfile`,
`apps/api/Dockerfile.worker`, `apps/web/Dockerfile`) run as **non-root** users,
use minimal base images, and bake no secrets (credentials come from
environment/compose). Production compose publishes only ports 80/443;
PostgreSQL/Redis are never exposed.

**Trivy image scan** (Trivy 0.58.2, HIGH+CRITICAL, against the built images):

| Image | Before | After | Notes |
|---|---|---|---|
| `sdmas-web` (nginx:1.27-alpine) | 35 (33 HIGH, **2 CRITICAL**) | **0** | `apk upgrade` fixed OpenSSL CVE-2026-31789 (CRITICAL), zlib, c-ares |
| `sdmas-api` (python:3.11-slim) | 23 OS + 3 python | 23 OS + **1** python | wheel/jaraco.context cleared via pip toolchain upgrade; only `ecdsa` remains (accepted risk) |
| `sdmas-worker` | same as api | same as api | shares the python base |
| `sdmas-migration-init` | same as api | same as api | reuses the API Dockerfile |

**Remaining 23 Debian OS findings** (util-linux CVE-2026-53615, perl-base
CVE-2026-13221 CRITICAL, ncurses CVE-2025-69720, gzip, acl): the Fixed-Version
column is **empty for every one** — Debian has not yet published patched
packages. The `apt-get upgrade` added to the runtime stages will pick them up
automatically on the next image rebuild once upstream fixes land. Not
reachable from the application attack surface (OS tooling, not network
services).

**Fixes applied (this pass):**

1. `apps/web/Dockerfile` — added `apk update && apk upgrade --no-cache` to the
   nginx runtime stage.
2. `apps/api/Dockerfile` + `apps/api/Dockerfile.worker` — added
   `apt-get upgrade -y` plus `pip install --upgrade setuptools wheel` in the
   runtime stage.
3. Rebuilt all four images and rescanned: web 35→0, python METADATA 3→1.
   Rebuilt `sdmas-api` still imports `app.main` cleanly; rebuilt `sdmas-web`
   nginx config passes `nginx -t`.

## 5. Repository secret scan

- Pattern scan over **git-tracked files only** (excludes node_modules/.venv):
  `AKIA*`, `sk-*`, `ghp_*`, `xox*`, `BEGIN (RSA|EC|OPENSSH|DSA|PGP) PRIVATE KEY`
  → **0 hits**.
- **Gitleaks v8.26+ (via container) over the full git history**: 54 commits
  scanned (43 MB) → **no leaks found**. The CI secret gate is now also
  verified locally, not just in CI.
- `.env` / `.env.*` are in `.gitignore`; only `.env.example` files are tracked
  (explicitly un-ignored) — no `.env` leakage.
- No private keys or generated credentials in the working tree, history, or
  tracked files.

## 6. SBOM verification

Command: `SOURCE_DATE_EPOCH=0 python -m sbom.cli generate --output-dir sbom/output`
then `python -m sbom.cli validate --dir sbom/output` and `analyze`.

- **CycloneDX 1.5** (`bomFormat: CycloneDX`, `specVersion: 1.5`) — 1,881 components, all with hashes.
- **SPDX-2.3** (`spdxVersion: SPDX-2.3`) — 1,881 packages, all with downloadLocation.
- Schema/data-quality validation: **2 documents, 0 errors**.
- Determinism: byte-identical across repeated runs under `SOURCE_DATE_EPOCH`.
- SBOM package unit tests: **48 passed**.

### Finding — stale committed SBOM outputs (fixed)

The committed `sbom/output/*` were generated before the lockfile drifted
(`apps/web` gained `motion`/`animejs`; npm inventory 1804 → **1775** packages).
The CI determinism gate (`git diff --exit-code -- sbom/output`) would have
failed. **Fix applied:** regenerated all outputs from the current lockfiles —
regeneration is stable across runs, so the gate now passes.

Risk analysis (from `dependency_risk_report.json`): 2,477 findings — **0 high**
(CI gate passes), 116 medium (111 `missing_license` data-quality gaps + 5
`dangling_dependency` on optional platform-specific `@tailwindcss/oxide-wasm32-wasi`
deps), 2,361 low.

## 7. Fixes applied

| # | File | Fix |
|---|---|---|
| 1 | `sbom/output/*` (8 files) | Regenerated from current lockfiles — was stale, would fail CI determinism gate |
| 2 | `docs/security-policy.md` | W-003 (`react-router-dom`) and W-004 (`xlsx`) marked **RESOLVED** with verified versions — they claimed open high findings that `npm audit` now reports as 0 |
| 3 | `apps/web/Dockerfile` | `apk upgrade` in nginx stage → image scan 35→0 (CRITICAL OpenSSL fixed) |
| 4 | `apps/api/Dockerfile`, `apps/api/Dockerfile.worker` | `apt-get upgrade` + `pip install --upgrade setuptools wheel` → python METADATA 3→1 |

## 8. Remaining accepted risks (documented, not exploitable)

- **W-001** `ecdsa 0.19.2` — no upstream fix; unreachable (HS256 only).
- **W-005** mobile Expo toolchain (43 findings) — build-time tooling; most
  fixed by current SDK; requires a major Expo upgrade to fully clear.

## 8b. Dependency-tree review (no unused production dependencies)

**Python** — 17 direct production deps (uv tree). All verified used in `app/`:
`ortools` (optimization engine), `networkx`/`scikit-learn` (intelligence
clustering/anomaly detection), `reportlab` (PDF exports), `openpyxl`
(migration discovery + XLSX), `python-jose` (JWT), `redis` (jobs/outbox),
`asyncpg` (Postgres). No dead direct deps.

**Node** — 11 direct production deps, all used: `jspdf`/`jspdf-autotable`/`xlsx`
are dynamically imported on demand in `hooks/use-export.ts` (0 static imports
is expected), `@sqlite.org/sqlite-wasm` powers the FTS5 offline search index
(`lib/search/search-db.ts`), `animejs`/`motion` are the motion system, `fuse.js`
search, `recharts` charts.

## 8c. Containers — writable FS, exposed ports

- All three images run as non-root (`USER sdmas`). The web image applies
  `chmod -R 755` to `/usr/share/nginx/html` (standard read-only static serving;
  not 777). No service runs a writable root filesystem.
- Base `docker-compose.yml` exposes the dev ports (5432, 6379, 8000, 80) for
  local zero-touch development — expected. **Production compose exposes only
  80/443 (nginx/web + otel/prometheus for observability); PostgreSQL and Redis
  are never published** — correct minimal surface.

## 8d. Repository `.env` hygiene

`.env.example` files contain only safe placeholders (no real secrets):
`DATABASE_URL=sqlite+aiosqlite:///./sdmas_dev.db`, `JWT_SECRET=change-me` etc.
with an explicit header: "NEVER commit a real .env file... production requires
real secrets (the app refuses to boot with placeholder secrets when
ENVIRONMENT=production)". Confirmed the fail-fast validator
(`_reject_default_secrets_in_production`) exists in `app/config.py`.

## 8e. SBOM ↔ installed-artifact correspondence

- **Python:** SBOM pypi inventory = 106 packages (uv.lock, all extras);
  installed venv = 99 dists. The 7 differences are exactly the dev/integration
  extras (`testcontainers`, `docker`, `pywin32`, `wrapt`, …) and the local
  `sdmas-api` project itself (correctly excluded from the SBOM).
- **Node:** SBOM npm inventory = 1,775 packages (current lockfile); installed
  `node_modules` differs only in platform-optional binaries (`fsevents`,
  non-Windows `lightningcss-*` variants) — expected per-platform pruning.
  `react` lockfile vs installed both 19.2.8. The regenerated SBOM removed
  stale entries no longer in the lockfile (e.g. `@babel/helper-environment-visitor`),
  which is the 1804→1775 delta.

## 9. Verification commands

```bash
# Python
cd apps/api
uv run bandit -r app/ -q -f json          # 36 findings, 0 HIGH
uv run pip-audit --local                  # 1 finding (ecdsa, waived W-001)

# Node
cd apps/web
npm audit --audit-level=high              # 0 vulnerabilities
cd ../mobile
npm audit                                 # 43 (Expo toolchain, W-005)

# SBOM (from repo root)
SOURCE_DATE_EPOCH=0 python -m sbom.cli generate --output-dir sbom/output
python -m sbom.cli validate --dir sbom/output
python -m sbom.cli analyze --output-dir sbom/output
git diff --exit-code -- sbom/output       # determinism gate

# Secrets (git-tracked files only)
git ls-files -z | xargs -0 grep -E "(AKIA[0-9A-Z]{16}|sk-[A-Za-z0-9]{20,}|BEGIN (RSA|EC|OPENSSH) PRIVATE KEY|ghp_[A-Za-z0-9]{30,})"

# Secrets (full history)
docker run --rm -v "$PWD:/repo" -w /repo zricethezav/gitleaks:latest detect --source /repo --no-banner

# Containers (Trivy; DB cached after first run)
docker run --rm -v //var/run/docker.sock:/var/run/docker.sock aquasec/trivy:0.58.2 image \
  --no-progress --scanners vuln --severity HIGH,CRITICAL sdmas-api:latest
# repeat for sdmas-worker, sdmas-web, sdmas-migration-init
```
