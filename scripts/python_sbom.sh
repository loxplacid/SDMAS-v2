#!/usr/bin/env bash
# Generates the Python dependency inventory SBOM artefact for SDMAS-v2.
#
# Usage:  bash scripts/python_sbom.sh [--venv]
#   --venv   additionally augment the inventory from the installed virtualenv
#            (adds license metadata + checksums from *.dist-info)
#
# Deterministic when SOURCE_DATE_EPOCH is set (see docs/SBOM_VALIDATION.md).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/_sbom_common.sh
source "$ROOT/scripts/_sbom_common.sh"
resolve_python "$ROOT"

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
