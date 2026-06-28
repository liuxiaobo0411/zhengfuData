#!/usr/bin/env bash
set -euo pipefail

OUTPUT=""

while [[ $# -gt 0 ]]; do
  case "$1" in
    --output)
      OUTPUT="$2"
      shift 2
      ;;
    -h|--help)
      cat <<'USAGE'
Usage: scripts/export-deployment-package.sh [options]

Options:
  --output PATH  Output zip file path or output directory.
USAGE
      exit 0
      ;;
    *)
      echo "Unknown argument: $1" >&2
      exit 2
      ;;
  esac
done

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "${SCRIPT_DIR}/.." && pwd)"
cd "$PROJECT_ROOT"

if [[ -n "${PYTHON:-}" ]]; then
  PYTHON_BIN="$PYTHON"
elif [[ -x "$PROJECT_ROOT/.venv/bin/python" ]]; then
  PYTHON_BIN="$PROJECT_ROOT/.venv/bin/python"
elif command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
else
  echo "Python not found. Create .venv or set PYTHON=/path/to/python." >&2
  exit 1
fi

ARGS=(-m app.cli export-deployment-package)
if [[ -n "$OUTPUT" ]]; then
  ARGS+=(--output "$OUTPUT")
fi

"$PYTHON_BIN" "${ARGS[@]}"
