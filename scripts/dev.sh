#!/usr/bin/env bash
# Start the Posted backend (FastAPI/uvicorn) and frontend (Expo) dev servers together.
# Usage: ./scripts/dev.sh [--web]
#   --web  also pass --web to expo so it opens the web build directly

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
CLIENT_DIR="$ROOT_DIR/apps/client"

EXPO_EXTRA_ARG=""
if [[ "${1:-}" == "--web" ]]; then
  EXPO_EXTRA_ARG="--web"
fi

command -v uv >/dev/null 2>&1 || { echo "error: 'uv' is required (https://docs.astral.sh/uv/)" >&2; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "error: 'npm' is required" >&2; exit 1; }

if [[ ! -d "$CLIENT_DIR/node_modules" ]]; then
  echo "==> Installing client dependencies (first run)..."
  (cd "$CLIENT_DIR" && npm install)
fi

PIDS=()
cleanup() {
  echo
  echo "==> Shutting down dev servers..."
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

echo "==> Starting backend (uvicorn --reload) on http://localhost:8000"
(cd "$BACKEND_DIR" && uv run uvicorn app.main:app --reload) &
PIDS+=("$!")

echo "==> Starting frontend (expo start)"
(cd "$CLIENT_DIR" && npm run start -- $EXPO_EXTRA_ARG) &
PIDS+=("$!")

# bash 3.2 (macOS default) doesn't support `wait -n`, so poll instead.
while true; do
  for pid in "${PIDS[@]}"; do
    if ! kill -0 "$pid" 2>/dev/null; then
      echo "==> Process $pid exited, shutting down the other server..."
      exit 1
    fi
  done
  sleep 1
done
