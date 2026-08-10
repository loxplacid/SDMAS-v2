# SDMAS v2 — Evidence Artifacts

This directory holds the **machine-generated due-diligence evidence package**.

## Structure

| Path | Content |
|---|---|
| `artifacts/security/` | Scanner outputs: `bandit.json`, `pip-audit.json`, `npm-audit-web.json`, `npm-audit-mobile.json` |
| `artifacts/sbom/` | CycloneDX 1.5 + SPDX 2.3 SBOM documents (copied from `sbom/output/`) |
| `artifacts/tests/` | JUnit XML per suite + `test-manifest.json` (real counts, real results) |
| `artifacts/architecture/` | Architecture/tenancy/authorization documentation snapshots |
| `artifacts/release/` | Release metadata (empty until a release is cut) |
| `artifacts/SHA256SUMS` | SHA-256 of every artifact file |
| `artifacts/artifact-manifest.json` | Artifact → digest manifest (immutable record) |

## Regenerating

```bash
make security-audit          # full package (all scanners + tests)
make security-audit-offline  # skip network-dependent scanners
./enterprise audit           # same as make security-audit
```

Every number in the evidence package comes from a tool that actually ran —
nothing is fabricated. The generated `docs/security-assurance-report.md`
distinguishes VERIFIED / NOT VERIFIED / NOT APPLICABLE / KNOWN LIMITATION.

**Note:** do not commit large binary scanner logs. The generators are
deterministic and CI regenerates the package on every run; commit only the
summaries, the manifest, and this README.
