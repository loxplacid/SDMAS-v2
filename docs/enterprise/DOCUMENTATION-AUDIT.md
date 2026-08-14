# Documentation-to-Implementation Audit — SDMAS v2

Date: 2026-08-14 · Every claim below was checked against the live repository or
an executed command. Documentation was updated **only after** the underlying
implementation was verified.

## Summary

| Severity | Finding | Fix |
|---|---|---|
| P1 | `docs/SECURITY_POLICY.md` and `docs/security-policy.md` both tracked — case-collision breaks on case-insensitive checkouts and splits the policy across two names | Renamed the older one to `docs/security-policy-and-controls.md`; updated the SECURITY.md reference |
| P1 | SECURITY.md auth-allowlist incomplete — omitted `/docs`, `/redoc`, `/openapi.json`, `/billing/plans` (all verified public in `auth_gate.py`) | Corrected the list |
| P2 | Stale test counts everywhere: README "1,499/513", ARCHITECTURE "~1,100", SECURITY "61/57", TENANCY "60" — actual: 1,652 API / 520 web / 28 security-suite / 64 acquisition-suite | Updated all four docs to executed counts |
| P2 | ARCHITECTURE "41 migrations / 33 domain modules" — actual 55 migration files (single head `048`), 36 domain modules | Corrected |
| P2 | KNOWN_LIMITATIONS #8 "SQLite migration chain broken before 034" — resolved; full chain `001→048` verified on a fresh SQLite DB | Marked RESOLVED |
| P2 | KNOWN_LIMITATIONS #10 "workspace imports students only" — engine now registers `users/students/academic/attendance/fees` | Corrected |
| P2 | DEPLOYMENT "CI/CD Pipeline (Suggested)" showed a fictional workflow — repo ships a real 8-job pipeline | Replaced with the actual pipeline summary |
| P2 | CONTRIBUTING broken link to `CODE_OF_CONDUCT.md` (does not exist); claimed "Python 3.8+"; install via `requirements.txt` | Fixed: 3.11+, `uv sync`, link de-broken |
| P2 | docs/enterprise-demo.md web URL `localhost:3000` — nginx serves on port 80 | Corrected |
| P3 | DEPLOYMENT "trufflehog/git-secrets", "pip audit" — actual is Gitleaks + pip-audit | Corrected |
| P3 | DEPLOYMENT "pip install --upgrade -r requirements.txt" — canonical is `uv lock --upgrade && uv sync --frozen` | Corrected |
| P3 | docs/CI.md stale `--passWithNoTests` (removed from workflow) | Corrected |

## Verified accurate (no change needed)

| Doc | Claim | Verification |
|---|---|---|
| README | `make dev/migrate/seed` quick start | Targets exist in Makefile |
| DEPLOYMENT | Nginx 30 r/s API + 5 r/m login rate limits | `nginx.conf` `limit_req_zone` |
| DEPLOYMENT | API bound to 127.0.0.1 in production | `docker-compose.production.yml` binds `127.0.0.1:8000:8000` |
| DEPLOYMENT | `make health/metrics/logs` | Targets exist |
| SECURITY | JWT HS256, 30-min access / 7-day refresh | `app/config.py` defaults |
| SECURITY | Docs disabled in production | `main.py` `docs_url=None if is_production()` |
| SECURITY | Webhook HMAC-SHA256 + idempotency ledger | `app/domains/billing/` verified in prior audit |
| TENANCY | Structural scoping chain | `app/multi_tenant/` repository + guards |
| KNOWN_LIMITATIONS #1/#2/#3 | `.env` and `node_modules` untracked; CI wired | `git ls-files` shows neither; workflows exist |
| KNOWN_LIMITATIONS #12 | Audit middleware skips sub-50 ms ops | `_MINIMAL_LATENCY_S = 0.05` in `app/domains/audit/middleware.py` |
| enterprise-demo | Demo credentials | Match `seed_enterprise_demo.py` (`DemoPass!2026`, `apex.admin` …) |
| README links | All doc links resolve | Checked each referenced file exists |

## Notes on method

- **Test counts** are from executed runs: `uv run pytest tests -q -m "not
  integration"` → 1,652 passed + 36 deselected (29m14s); `npm test` (web) →
  520 passed / 53 files; `test_security_suite.py` → 28 collected;
  `test_security_acquisition/` → 64 collected.
- **Migration facts** are from the actual tree: 55 files in
  `apps/api/alembic/versions/` (excl. `__init__`), `alembic heads` → single
  head `048_perf_indexes`, and a fresh-DB `alembic upgrade head` on SQLite
  completed through 048 (rc=0).
- **Allowlist** read from `app/core/security/auth_gate.py` `_PUBLIC_EXACT`:
  health/ready/metrics, docs/redoc/openapi.json, auth register/login/refresh,
  `/billing/plans`, plus webhook prefixes.
- **OpenAPI**: `apps/web/openapi.json` is a committed snapshot (49 paths);
  it is regenerated on API boot and is not authoritative documentation.

## Files changed

- `README.md`, `ARCHITECTURE.md`, `SECURITY.md`, `TENANCY.md`,
  `KNOWN_LIMITATIONS.md`, `CONTRIBUTING.md`, `DEPLOYMENT.md`
- `docs/CI.md`, `docs/enterprise-demo.md`
- `docs/SECURITY_POLICY.md` → renamed `docs/security-policy-and-controls.md`

## Verification commands

```bash
# Test counts (already executed this session)
cd apps/api && uv run pytest tests -q -m "not integration"      # 1652 passed
cd apps/web && npm test                                          # 520 passed

# Migration facts
ls apps/api/alembic/versions/*.py | grep -vc __init__            # 55
cd apps/api && uv run alembic heads                              # 048_perf_indexes (head)
DATABASE_URL=sqlite+aiosqlite:////tmp/x.db uv run alembic upgrade head

# Allowlist
grep -A16 "_PUBLIC_EXACT" apps/api/app/core/security/auth_gate.py

# .env / node_modules untracked
git ls-files | grep -cE "(^|/)\.env$|node_modules"               # 0
```
