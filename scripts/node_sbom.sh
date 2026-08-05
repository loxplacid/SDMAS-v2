#!/usr/bin/env bash
# Generates the Node dependency inventory SBOM artefact for SDMAS-v2
# (apps/web + apps/mobile package-lock.json files).
#
# Usage:  bash scripts/node_sbom.sh
#
# Deterministic when SOURCE_DATE_EPOCH is set (see docs/SBOM_VALIDATION.md).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

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

cd "$ROOT"
"$PY" -m sbom.cli node-inventory \
  --lock apps/web/package-lock.json \
  --lock apps/mobile/package-lock.json \
  -o sbom/output/node_dependency_inventory.json

echo "node SBOM inventory written to sbom/output/node_dependency_inventory.json"
