# SDMAS v2 — Security Gate Policy & Accepted-Risk Register

This document defines the **automated security gates** enforced by CI and the
evidence pipeline (`make security-audit` / `./enterprise audit`), and records
**accepted risks** (waivers) with justification.  It is the policy companion
to `docs/security-assurance-report.md`, which records the machine-generated
evidence.

## Automated gates

| Gate | Tool | Fails when | Enforcement |
|---|---|---|---|
| SAST (Python) | Bandit | any HIGH-severity finding | `ci.yml` `evidence` job + `scripts/security-audit.sh` |
| Python dependency scan | pip-audit | any *un-waived* known vulnerability | `ci.yml` `evidence` job |
| Web dependency audit | npm audit | high/critical findings | `ci.yml` `web` job (`--audit-level=high`) |
| Secret scanning | Gitleaks + pattern scan | live-credential patterns or tracked `.env` | `ci.yml` `security` job |
| SBOM schema | `sbom.cli validate` | schema/data-quality violations | `ci.yml` `evidence` + `sbom_validation.yml` |
| SBOM determinism | `git diff --exit-code` | regenerated output differs from committed | `sbom_validation.yml` |
| Tests | pytest / vitest | suite failures | `ci.yml` api/web jobs + evidence manifest |

Policy: low/medium findings are **recorded, not gating**.  HIGH findings and
un-waived vulnerabilities block the build.  Waivers are added to the register
below with an owner, date, and justification; they are re-reviewed on every
dependency refresh.

## Accepted-risk register

| ID | Package | Finding | Justification | Owner | Status |
|---|---|---|---|---|---|
| W-001 | `ecdsa 0.19.2` | PYSEC-2026-1325 | No upstream fix available. Transitive via `python-jose[cryptography]`; not exposed to untrusted input paths. Waived in CI via `--ignore-vuln`. Re-review on next dependency refresh. | Security | OPEN |
| W-002 | `cryptography 49.0.0` | CVE-2026-69247 (fix 50.0.0) | **RESOLVED** — bumped to 50.0.0 in `uv.lock` (verified with `pip-audit`). | Security | RESOLVED |
| W-003 | web `react-router-dom` | high (transitive via `react-router`) | **RESOLVED** — at 7.18.2 (`^7.0.0`); `npm audit` reports 0 vulnerabilities for the web app. | Frontend | RESOLVED |
| W-004 | web `xlsx` | high | **RESOLVED** — bumped to 0.20.3 (SheetJS CDN tarball); `npm audit` reports 0 vulnerabilities for the web app. | Frontend | RESOLVED |
| W-005 | mobile (Expo toolchain) | 43 findings (30 high, 1 critical) | Expo/React Native build-chain findings; most fixed by SDK 57.0.11 which is current. Many are dev-time only. | Mobile | OPEN — TRACKED |

## Process

1. CI runs all gates on every push/PR.
2. A failing gate blocks merge until fixed or a waiver is added here.
3. `make security-audit` regenerates the evidence package + assurance report
   from the actual scanner outputs — it never fabricates results.
4. Waivers are reviewed weekly (the SBOM workflow runs on a schedule).

## Compliance note

Nothing in this document or the assurance report is a claim of regulatory
compliance (GDPR, SOC 2, HIPAA).  Compliance requires an independent legal/
audit assessment; this repository provides the *technical controls and
evidence* such an assessment would evaluate.
