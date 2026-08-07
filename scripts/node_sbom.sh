#!/usr/bin/env bash
# Generates the Node dependency inventory SBOM artefact for SDMAS-v2
# (apps/web + apps/mobile package-lock.json files).
#
# Usage:  bash scripts/node_sbom.sh
#
# Deterministic when SOURCE_DATE_EPOCH is set (see docs/SBOM_VALIDATION.md).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# shellcheck source=scripts/_sbom_common.sh
source "$ROOT/scripts/_sbom_common.sh"
resolve_python "$ROOT"

cd "$ROOT"
"$PY" -m sbom.cli node-inventory \
  --lock apps/web/package-lock.json \
  --lock apps/mobile/package-lock.json \
  -o sbom/output/node_dependency_inventory.json

echo "node SBOM inventory written to sbom/output/node_dependency_inventory.json"
