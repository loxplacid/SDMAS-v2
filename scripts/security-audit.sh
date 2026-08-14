#!/usr/bin/env bash
# =============================================================================
# SDMAS v2 — Security Audit & Due-Diligence Evidence Package
# =============================================================================
# Generates the complete acquisition-grade verification/evidence package:
#
#   artifacts/
#     security/    bandit.json, pip-audit.json, npm-audit-{web,mobile}.json
#     sbom/        CycloneDX 1.5 + SPDX 2.3 documents (copied from sbom/output)
#     tests/       JUnit XML + test-manifest.json (real counts, real results)
#     architecture/  ARCHITECTURE.md / TENANCY.md / AUTHORIZATION.md (copies)
#     SHA256SUMS   sha-256 of every artifact
#     artifact-manifest.json
#
#   docs/security-assurance-report.md   (VERIFIED / NOT VERIFIED /
#                                       NOT APPLICABLE / KNOWN LIMITATION)
#
# The report never fabricates compliance claims — every number comes from a
# tool that actually ran.
#
# Usage:  bash scripts/security-audit.sh
#         make security-audit
#         ./enterprise audit
#         bash scripts/security-audit.sh --ci-evidence-only   # skip test
#             phase (CI runs suites in separate jobs); scanners + SBOM +
#             checksums + report only
#
# Gate policy (see docs/security-policy.md):
#   * Bandit      — fail on HIGH severity findings
#   * pip-audit   — fail when the python dependency scan reports any
#                   vulnerability (network-dependent; skipped offline)
#   * npm audit   — informational (recorded, not gating) in the local run;
#                   CI enforces high/critical via the existing web job
#   * SBOM        — schema validation + determinism gate (existing CI job)
# =============================================================================
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ARTIFACTS="${ROOT}/artifacts"
SEC_DIR="${ARTIFACTS}/security"
SBOM_OUT="${ARTIFACTS}/sbom"
TESTS_DIR="${ARTIFACTS}/tests"
ARCH_DIR="${ARTIFACTS}/architecture"

# Allow local runs to skip network-dependent tools (pip-audit / npm audit).
SKIP_NETWORK="${SKIP_NETWORK:-0}"
# CI mode: skip the pytest/vitest phase (CI runs those in dedicated jobs).
CI_EVIDENCE_ONLY=0
if [ "${1:-}" = "--ci-evidence-only" ]; then
  CI_EVIDENCE_ONLY=1
fi

# Gate failures are collected and reported at the end; the full evidence
# package is always generated, and the script exits non-zero when a gate is
# exceeded so CI can fail the build.
GATE_FAILURES=()

# Accepted-risk waivers (docs/security-policy.md). Kept in sync with the
# pip-audit invocation in .github/workflows/ci.yml (evidence job).
PIP_AUDIT_IGNORES=(--ignore-vuln PYSEC-2026-1325)

mkdir -p "${SEC_DIR}" "${SBOM_OUT}" "${TESTS_DIR}" "${ARCH_DIR}"

echo "================================================================"
echo "  SDMAS v2 — Security Audit & Due-Diligence Evidence"
echo "  root: ${ROOT}"
echo "================================================================"

# ── 1. Environment + provenance ──────────────────────────────────────
COMMIT="$(git -C "${ROOT}" rev-parse HEAD 2>/dev/null || echo unknown)"
echo ""
echo "[1/8] Provenance: commit ${COMMIT}"

# ── 2. Secret scanning ───────────────────────────────────────────────
echo ""
echo "[2/8] Secret scanning"
if command -v gitleaks >/dev/null 2>&1; then
  echo "  running gitleaks..."
  gitleaks git --path "${ROOT}" --redact --exit-code 0 2>&1 | tail -5 \
    || echo "  gitleaks found issues (see CI for the gating run)"
else
  echo "  gitleaks not installed — CI (.github/workflows/ci.yml security job)"
  echo "  runs the gating Gitleaks + hardcoded-credential scans."
fi

# ── 3. Bandit (Python SAST) ──────────────────────────────────────────
echo ""
echo "[3/8] Bandit (Python static analysis)"
if command -v uvx >/dev/null 2>&1; then
  # bandit exits non-zero when findings exist — the report is still written
  # and the gate is decided after inspection.
  # bandit exits non-zero when findings exist — the report is still written
  # and the gate is decided after inspection.
  uvx bandit -r "${ROOT}/apps/api/app" -f json -o "${SEC_DIR}/bandit.json" -q 2>/dev/null || true
  BANDIT_JSON="${SEC_DIR}/bandit.json" python - <<'PYEOF' || BANDIT_HIGH=1
import json, collections, os
bandit_json = os.environ["BANDIT_JSON"]
try:
    d = json.load(open(bandit_json, encoding="utf-8"))
except Exception:
    print("  bandit: no report produced")
else:
    rs = d.get("results", [])
    counts = collections.Counter((r["issue_severity"], r["issue_confidence"]) for r in rs)
    high = [r for r in rs if r["issue_severity"] == "HIGH"]
    print(f"  bandit: {len(rs)} findings, {len(high)} HIGH")
    for (sev, conf), n in sorted(counts.items()):
        print(f"    {sev}/{conf}: {n}")
    if high:
        raise SystemExit(1)
PYEOF
  if [ "${BANDIT_HIGH:-0}" = "1" ]; then
    GATE_FAILURES+=("bandit HIGH findings — fix or waive via docs/security-policy.md")
  fi
else
  echo "  uvx not available — bandit skipped"
fi

# ── 4. pip-audit (Python dependency vulnerabilities) ─────────────────
echo ""
echo "[4/8] pip-audit (Python dependencies)"
if [ "${SKIP_NETWORK}" = "1" ] || ! command -v uvx >/dev/null 2>&1; then
  echo "  skipped (offline mode / uvx unavailable)"
else
  (cd "${ROOT}/apps/api" && uv export --format requirements-txt --no-dev \
    -o "${SEC_DIR}/req_audit.txt" 2>/dev/null || true)
  grep -v '^-e \|^file://' "${SEC_DIR}/req_audit.txt" > "${SEC_DIR}/req_clean.txt" || true
  # pip-audit exits 1 when vulnerabilities are found — that is exactly the
  # output this evidence package must keep.  Treat it as failed only when
  # no report file was actually produced.
  uvx pip-audit -r "${SEC_DIR}/req_clean.txt" --format json \
    -o "${SEC_DIR}/pip-audit.json" "${PIP_AUDIT_IGNORES[@]}" 2>/dev/null || true
  if [ -s "${SEC_DIR}/pip-audit.json" ]; then
    echo "  pip-audit completed (see artifacts/security/pip-audit.json)"
    PIP_AUDIT_JSON="${SEC_DIR}/pip-audit.json" python - <<'PYEOF' || PIP_AUDIT_VULNS=1
import json, os
vulns = [dep for dep in json.load(open(os.environ["PIP_AUDIT_JSON"]))["dependencies"] if dep.get("vulns")]
if vulns:
    print(f"  pip-audit: {len(vulns)} vulnerable package(s) — see docs/security-policy.md waivers")
    raise SystemExit(1)
print("  pip-audit: no un-waived vulnerabilities")
PYEOF
    if [ "${PIP_AUDIT_VULNS:-0}" = "1" ]; then
      GATE_FAILURES+=("pip-audit found vulnerable packages — fix or waive via docs/security-policy.md")
    fi
  else
    echo "  pip-audit failed or timed out (network) — recorded in report as NOT VERIFIED"
  fi
  rm -f "${SEC_DIR}/req_audit.txt" "${SEC_DIR}/req_clean.txt"
fi

# ── 5. npm audit (frontend) ──────────────────────────────────────────
echo ""
echo "[5/8] npm audit (web + mobile)"
if [ "${SKIP_NETWORK}" = "1" ]; then
  echo "  skipped (offline mode)"
else
  for app in web mobile; do
    if [ -d "${ROOT}/apps/${app}" ]; then
      # npm audit exits non-zero when it FINDS vulnerabilities — the JSON
      # report is still written.  Judge by the report file, not the exit
      # code, or every vulnerable app is misreported as "failed".
      (cd "${ROOT}/apps/${app}" && npm audit --json \
        > "${SEC_DIR}/npm-audit-${app}.json" 2>/dev/null || true)
      if [ -s "${SEC_DIR}/npm-audit-${app}.json" ]; then
        echo "  ${app}: report saved"
      else
        echo "  ${app}: npm audit failed (no lockfile or network)"
      fi
    fi
  done
fi

# ── 6. SBOM ──────────────────────────────────────────────────────────
echo ""
echo "[6/8] SBOM (CycloneDX 1.5 + SPDX 2.3)"
if command -v "${ROOT}/scripts/python_sbom.sh" >/dev/null 2>&1 || [ -x "${ROOT}/scripts/python_sbom.sh" ]; then
  bash "${ROOT}/scripts/python_sbom.sh" >/dev/null 2>&1 || true
  bash "${ROOT}/scripts/node_sbom.sh" >/dev/null 2>&1 || true
  (cd "${ROOT}" && SOURCE_DATE_EPOCH=0 python -m sbom.cli generate \
    --output-dir sbom/output >/dev/null 2>&1) || true
  if (cd "${ROOT}" && python -m sbom.cli validate --dir sbom/output \
      > "${SBOM_OUT}/validate.txt" 2>&1); then
    CLEAN=$(grep -c "0 error(s)" "${SBOM_OUT}/validate.txt" 2>/dev/null || echo 0)
    echo "  validate: ${CLEAN} document(s) clean"
  else
    echo "  validate: FAILED — see ${SBOM_OUT}/validate.txt"
    GATE_FAILURES+=("SBOM schema/data-quality validation failed")
  fi
  cp -f "${ROOT}"/sbom/output/sbom.cdx.json "${SBOM_OUT}/" 2>/dev/null || true
  cp -f "${ROOT}"/sbom/output/sbom.spdx.json "${SBOM_OUT}/" 2>/dev/null || true
  cp -f "${ROOT}"/sbom/output/python_dependency_inventory.json "${SBOM_OUT}/" 2>/dev/null || true
  cp -f "${ROOT}"/sbom/output/node_dependency_inventory.json "${SBOM_OUT}/" 2>/dev/null || true
else
  echo "  SBOM scripts not found — skipped"
fi

# ── 7. Test evidence (real counts) ───────────────────────────────────
# The default run executes the *named evidence suites* (bounded, fast):
# security, finance, outbox/jobs, migration, frontend, sbom.  They are
# independent (each writes its own junit file) and run in parallel so the
# wall time is the slowest suite, not the sum.  Set RUN_FULL_API=1 to also
# run the entire API non-integration suite.  Integration tests
# (Docker/Testcontainers) are never run here.  CI passes
# --ci-evidence-only and runs the suites in its own jobs.
if [ "${CI_EVIDENCE_ONLY}" = "1" ]; then
  echo ""
  echo "[7/8] Test evidence — skipped (CI runs suites in dedicated jobs)"
  echo "      (--ci-evidence-only)"
else
  echo ""
  echo "[7/8] Test evidence (suites in parallel)"
  # Never mix junit files from a previous run into this run's manifest:
  # evidence must be provably from this invocation.
  rm -f "${TESTS_DIR}"/*.xml
run_api() { # run_api <junit-file> <args...>
  local file="$1"
  shift
  (cd "${ROOT}/apps/api" && timeout 540 uv run pytest "$@" -q \
    --junitxml="${file}" 2>&1 | tail -1)
}

pids=()
if [ "${RUN_FULL_API:-0}" = "1" ]; then
  run_api "${TESTS_DIR}/api-unit.xml" tests/ -m "not integration" &
  pids+=($!)
fi

# Security-focused evidence suites (explicitly named).
run_api "${TESTS_DIR}/api-security.xml" \
  tests/test_security_acquisition/ tests/test_multi_tenant/ tests/test_permissions.py &
pids+=($!)
run_api "${TESTS_DIR}/api-finance.xml" tests/test_finance_security/ &
pids+=($!)
run_api "${TESTS_DIR}/api-outbox.xml" \
  tests/test_outbox/ tests/test_async_hardening/ tests/test_jobs/ &
pids+=($!)
run_api "${TESTS_DIR}/api-migration.xml" \
  tests/test_migration_step2.py tests/test_migration_workspace.py &
pids+=($!)

# SBOM package tests (fast, parallel-safe).
(cd "${ROOT}/sbom" && timeout 120 python -m pytest tests -q \
  --junitxml="${TESTS_DIR}/sbom.xml" 2>&1 | tail -1) &
pids+=($!)

for pid in "${pids[@]}"; do wait "$pid" || true; done

# Frontend (junit reporter built into vitest).  Run *after* the API suites
# complete: vitest keyboard/async tests are timing-sensitive, and running
# them while the CPU-heavy security suite is still hammering cores produced
# a flaky failure in verification.
if [ -d "${ROOT}/apps/web/node_modules" ]; then
  (cd "${ROOT}/apps/web" && timeout 300 npx vitest run \
    --reporter=junit --outputFile="${TESTS_DIR}/web.xml" 2>&1 | tail -1) || true
fi

# Assemble the machine-readable manifest.
(cd "${ROOT}" && PYTHONPATH=scripts python -m evidence.cli test-manifest \
  --junit-dir artifacts/tests --out artifacts/tests/test-manifest.json) || true
fi

# ── 8. Checksums + assurance report ──────────────────────────────────
echo ""
echo "[8/8] Checksums + assurance report"
(cd "${ROOT}" && PYTHONPATH=scripts python -m evidence.cli checksums --dir artifacts) || true
(cd "${ROOT}" && PYTHONPATH=scripts python -m evidence.cli report --artifacts artifacts) || true

echo ""
echo "================================================================"
echo "  Evidence package complete."
echo "  → artifacts/SHA256SUMS"
echo "  → artifacts/tests/test-manifest.json"
echo "  → docs/security-assurance-report.md"
echo "================================================================"

# ── Gate summary (fail CI when a gate is exceeded) ────────────────────
if [ "${#GATE_FAILURES[@]}" -gt 0 ]; then
  echo ""
  echo "GATE FAILURES:"
  for g in "${GATE_FAILURES[@]}"; do echo "  ✗ $g"; done
  exit 1
fi
echo ""
echo "All gates passed."