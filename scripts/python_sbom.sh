#!/usr/bin/env bash
# Generates the Python dependency inventory SBOM artefacts for SDMAS-v2.
#
# Usage:  bash scripts/python_sbom.sh [--venv]
#   --venv   additionally augment the inventory from the installed virtualenv
#            (adds license metadata + checksums from *.dist-info)
#
# Deterministic when SOURCE_DATE_EPOCH is set (see docs/SBOM_VALIDATION.md).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# Resolve a Python interpreter: prefer the project venv, then PYTHON env,
# then python3/python.
if [[ -x "$ROOT/apps/api/.venv/Scripts/python.exe" ]]; then
  PY="$ROOT/apps/api/.venv/Scripts/python.exe"
elif [[ -x "$ROOT/apps/api/.venv/bin/python" ]]; then
  PY="$ROOT/apps/api/.venv/bin/python"
elif [[ -n "${PYTHON:-}" ]]; then
  PY="$PYTHON"
else
  PY="$(command -v python3 || command -v python)"
fi

if [[ -z "$PY" ]]; then
  echo "error: no Python interpreter found" >&2
  exit 1
fi

VENV_FLAG=()
if [[ "${1:-}" == "--venv" ]]; then
  VENV_FLAG=(--venv)
fi

cd "$ROOT"
"$PY" -m sbom.cli python-inventory \
  --lock apps/api/uv.lock \
  -o sbom/output/python_dependency_inventory.json \
  "${VENV_FLAG[@]}"

echo "python SBOM inventory written to sbom/output/python_dependency_inventory.json"
