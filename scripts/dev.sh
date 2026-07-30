#!/usr/bin/env bash
set -euo pipefail

HOST="${HOST:-127.0.0.1}"
PORT="${1:-4173}"
ROOT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

if command -v python3 >/dev/null 2>&1; then
  PYTHON_BIN="python3"
elif command -v python >/dev/null 2>&1; then
  PYTHON_BIN="python"
else
  echo "Error: Python is required (python3 or python not found)." >&2
  exit 1
fi

echo "Serving ${ROOT_DIR} at http://${HOST}:${PORT}"
cd "$ROOT_DIR"
exec "$PYTHON_BIN" -m http.server "$PORT" --bind "$HOST"
