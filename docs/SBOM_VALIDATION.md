# SBOM Validation

SDMAS-v2 generates software bills of materials for its Python and Node
dependencies. This document describes what is generated, how it is
validated, and the guarantees (and limits) of the process.

## Artefacts (all in `sbom/output/`)

| File | Content |
|---|---|
| `python_dependency_inventory.json` | Python packages parsed from `apps/api/uv.lock` (+ `pyproject.toml` direct-marking, optional venv augmentation) |
| `node_dependency_inventory.json` | Node packages parsed from `apps/web/package-lock.json` and `apps/mobile/package-lock.json` |
| `sbom.spdx.json` | Combined inventory as **SPDX 2.3** JSON |
| `sbom.cdx.json` | Combined inventory as **CycloneDX 1.5** JSON |
| `license_summary.json` | License distribution + unknown-license count |
| `duplicate_dependencies.json` | Multi-version and cross-project duplicates + cross-ecosystem collisions |
| `dependency_metrics.json` | Graph statistics: sizes, edges, orphans, cycles, depth |
| `dependency_risk_report.json` | Supply-chain risk findings (severity-tagged) |
| `warnings.json` | Every parse warning collected during generation |

## Pipeline

```
scripts/python_sbom.sh ─┐
scripts/node_sbom.sh  ─┼─► python -m sbom.cli generate ─► validate + analyze
```

CI (`.github/workflows/sbom_validation.yml`) runs the pipeline on every lock
file change, weekly, and enforces:

1. **Schema validity** — `python -m sbom.cli validate` checks the emitted
   SPDX 2.3 / CycloneDX 1.5 documents against the required fields,
   identifiers, licence expressions, purl syntax and reference integrity.
2. **Reproducibility** — `SOURCE_DATE_EPOCH` is pinned; generated documents
   must be byte-identical with the committed ones (`git diff --exit-code`).
   Sources are canonicalised with `Path.resolve()` so identifiers are
   invariant to path case (`apps/api/uv.lock` vs `APPS/API/uv.lock`) and
   separator style on every OS.
3. **Style gate** — `ruff check sbom/` and `ruff format --check sbom/` must
   pass (config in `sbom/pyproject.toml`); the unit test suite runs too.
4. **Risk gate** — high-severity inventory findings (non-registry origins,
   missing versions) fail the build.

## Consumer interoperability

* The CycloneDX root component (`metadata.component`) is wired into the
  `dependencies` graph (it `dependsOn` the direct installs), so
  root-traversing consumers (Dependency-Track, Grype) see a connected tree
  rather than a disconnected root.
* Cross-validated against the official SPDX 2.3 / CycloneDX 1.5 JSON
  schemas, `cyclonedx-python-lib`, `npm sbom`, `pip-audit`, and Syft
  (both as generator and as consumer of the emitted documents).

## Determinism contract

* Every list in every output is sorted; JSON keys are emitted sorted.
* `documentNamespace` (SPDX) and `serialNumber` (CycloneDX) are UUIDv5
  hashes of document *content* — identical inputs ⇒ identical identifiers.
* `creationInfo.created` / `metadata.timestamp` use `SOURCE_DATE_EPOCH`
  when set (Unix seconds → UTC). **Without it, the timestamp is the current
  wall-clock time**: the documents are then spec-compliant but not
  byte-reproducible. CI always sets it, so committed artefacts are
  reproducible.

## Known limitations (accepted, documented)

* npm lockfiles do not record dependency edges for hoisted transitive
  packages, so the Node dependency graph under-reports edges. Orphaned
  packages are reported in `dependency_metrics.json` (they remain listed as
  components — NTIA minimum elements are unaffected).
* `uv.lock` carries no license metadata; licenses are filled from installed
  `*.dist-info` when `--venv` augmentation is enabled, otherwise reported
  as `NOASSERTION` / missing (visible in `license_summary.json`).
* Recursive `-r` includes in `requirements.txt` are not followed (warning).
* `SOURCE_DATE_EPOCH` values that overflow the platform time range are
  rejected loudly (no silent fallback).
* Dependency edges are resolved by name to *all* candidate versions when a
  lock file records a constraint rather than one resolved version — the
  graph is a conservative over-approximation (reported as
  ``ambiguous_edges`` in `dependency_metrics.json`).
* Lock files larger than 200 MB are refused with a warning (resource
  exhaustion guard); a lock this size is almost certainly corrupt/hostile.

## Local validation

```bash
bash scripts/python_sbom.sh && bash scripts/node_sbom.sh
python -m sbom.cli generate --output-dir sbom/output
python -m sbom.cli validate --dir sbom/output
python -m sbom.cli analyze --output-dir sbom/output
python -m pytest sbom/tests -q
```
