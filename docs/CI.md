# CI/CD

SDMAS-v2 ships a GitHub Actions pipeline in `.github/workflows/ci.yml`.

## Pipeline

| Job | Checks | Notes |
|---|---|---|
| `api` | ruff lint + format + mypy (changed files), full pytest suite (`-m "not integration"`) | SQLite in-memory, no services needed |
| `api-integration` | `-m integration` (Testcontainers) | Requires Docker-in-Docker on the runner |
| `migrations` | single-head check + `alembic upgrade head` | Runs against a PostgreSQL 16 service container (the chain cannot run on SQLite) |
| `web` | `npm ci`, `tsc --noEmit`, vitest, production build, `npm audit --audit-level=high` | Lockfile: `apps/web/package-lock.json` |
| `mobile` | `npm ci`, `tsc --noEmit`, jest | Lockfile: `apps/mobile/package-lock.json` |
| `security` | Gitleaks scan, `.env`-tracked guard, hardcoded-credential grep | Values are redacted in output |

## Design decisions

* **Lockfile-first.** Python uses `uv sync --frozen` against `apps/api/uv.lock`; web/mobile use `npm ci`. CI never installs from loose ranges.
* **Lint/format/type checks are scoped to changed files.** The repository carries
  significant pre-existing lint debt (762 app + 431 test ruff findings when this
  workflow was introduced; mypy has 166 pre-existing errors). Gating the whole
  tree would fail every PR on legacy code. Instead CI **fails on new violations**
  in files a change touches, which is the correct boundary for an in-flight
  hardening project. Full-repo cleanup is tracked separately in
  `docs/SECRETS.md` and the hardening backlog.
* **Migration validation uses PostgreSQL**, mirroring production. The migration
  chain deliberately does not run on SQLite (documented limitation).
* **CI uses test-only credentials.** No production secrets are needed or stored
  in the workflow. `GITLEAKS_LICENSE` is an optional repository secret used only
  by the Gitleaks action itself.
* **Integration tests are opt-in.** They need Docker-in-Docker and are not part
  of the fast default path.

## Running the same checks locally

```bash
# API
cd apps/api
uv sync --frozen --extra dev
uv run ruff check <changed-files>
uv run ruff format --check <changed-files>
uv run mypy --no-incremental <changed-files> --follow-imports=skip
uv run pytest tests -q -m "not integration"

# Migration validation (needs a PostgreSQL)
DATABASE_URL=postgresql+asyncpg://sdmas:sdmas_dev@localhost:5432/sdmas uv run alembic heads
DATABASE_URL=postgresql+asyncpg://sdmas:sdmas_dev@localhost:5432/sdmas uv run alembic upgrade head

# Web
cd apps/web && npm ci && npx tsc --noEmit && npm test && npm run build && npm audit --audit-level=high

# Mobile
cd apps/mobile && npm ci && npx tsc --noEmit && npx jest --passWithNoTests
```

## Adding a new backend dependency

1. Add the requirement to `apps/api/pyproject.toml`.
2. Run `uv lock` and commit `apps/api/uv.lock`.
3. CI installs from the lockfile, so the resolved version is what gets tested.

## Adding a new frontend dependency

1. `npm install <pkg>` (web or mobile) — this updates `package-lock.json`.
2. Commit the lockfile.
3. `npm audit --audit-level=high` must stay clean for the new dependency.
