#!/usr/bin/env bash
# Shared helpers for the SBOM wrapper scripts (sourced, not executed).
#
# Resolves the project Python interpreter deterministically:
#   1. the project virtualenv (Windows or POSIX layout);
#   2. the $PYTHON environment variable;
#   3. python3 / python from PATH.
# Sets $PY; exits 1 with a message when no interpreter is found.
set -euo pipefail

resolve_python() {
  local root="$1"
  if [[ -x "$root/apps/api/.venv/Scripts/python.exe" ]]; then
    PY="$root/apps/api/.venv/Scripts/python.exe"
  elif [[ -x "$root/apps/api/.venv/bin/python" ]]; then
    PY="$root/apps/api/.venv/bin/python"
  elif [[ -n "${PYTHON:-}" ]]; then
    PY="$PYTHON"
  else
    PY="$(command -v python3 || command -v python || true)"
  fi

  if [[ -z "$PY" ]]; then
    echo "error: no Python interpreter found" >&2
    exit 1
  fi
}
