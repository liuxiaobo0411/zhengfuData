#!/usr/bin/env bash
set -euo pipefail

SOURCE_LIMIT=2
DAILY_LIMIT=2
SKIP_SOURCE_VALIDATION=false
SKIP_DAILY_CRAWL=false
SKIP_V2=false

while [[ $# -gt 0 ]]; do
  case "$1" in
    --source-limit)
      SOURCE_LIMIT="$2"
      shift 2
      ;;
    --daily-limit)
      DAILY_LIMIT="$2"
      shift 2
      ;;
    --skip-source-validation)
      SKIP_SOURCE_VALIDATION=true
      shift
      ;;
    --skip-daily-crawl)
      SKIP_DAILY_CRAWL=true
      shift
      ;;
    --skip-v2)
      SKIP_V2=true
      shift
      ;;
    -h|--help)
      cat <<'USAGE'
Usage: scripts/run-local-acceptance.sh [options]

Options:
  --source-limit N              Number of enabled sections to validate, default 2.
  --daily-limit N               Number of enabled sections to crawl, default 2.
  --skip-source-validation      Skip external source validation.
  --skip-daily-crawl            Skip daily crawl sample.
  --skip-v2                     Skip V2 knowledge-base acceptance.
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

ARGS=(
  -m app.cli local-acceptance-check
  --source-limit "$SOURCE_LIMIT"
  --daily-limit "$DAILY_LIMIT"
)

if [[ "$SKIP_SOURCE_VALIDATION" == true ]]; then
  ARGS+=(--skip-source-validation)
fi
if [[ "$SKIP_DAILY_CRAWL" == true ]]; then
  ARGS+=(--skip-daily-crawl)
fi
if [[ "$SKIP_V2" == true ]]; then
  ARGS+=(--skip-v2)
fi

"$PYTHON_BIN" "${ARGS[@]}"
