#!/usr/bin/env bash
# Start the Posted backend (FastAPI/uvicorn) and frontend (Expo) dev servers together.
# Usage: ./scripts/dev.sh [--web] [--no-tunnel]
#   --web        also pass --web to expo so it opens the web build directly
#   --no-tunnel  skip the Cloudflare Quick Tunnel (Schwab OAuth callback) even if cloudflared is installed

set -euo pipefail

ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BACKEND_DIR="$ROOT_DIR/backend"
CLIENT_DIR="$ROOT_DIR/apps/client"
ENV_FILE="$ROOT_DIR/.env"

EXPO_EXTRA_ARG=""
SKIP_TUNNEL=""
for arg in "$@"; do
  case "$arg" in
    --web) EXPO_EXTRA_ARG="--web" ;;
    --no-tunnel) SKIP_TUNNEL="1" ;;
  esac
done

command -v uv >/dev/null 2>&1 || { echo "error: 'uv' is required (https://docs.astral.sh/uv/)" >&2; exit 1; }
command -v npm >/dev/null 2>&1 || { echo "error: 'npm' is required" >&2; exit 1; }

if [[ ! -d "$CLIENT_DIR/node_modules" ]]; then
  echo "==> Installing client dependencies (first run)..."
  (cd "$CLIENT_DIR" && npm install)
fi

PIDS=()
CLOUDFLARED_PID=""
cleanup() {
  echo
  echo "==> Shutting down dev servers..."
  for pid in "${PIDS[@]}"; do
    kill "$pid" 2>/dev/null || true
  done
  if [[ -n "$CLOUDFLARED_PID" ]]; then
    kill "$CLOUDFLARED_PID" 2>/dev/null || true
  fi
  wait 2>/dev/null || true
}
trap cleanup EXIT INT TERM

# --- Schwab OAuth callback tunnel ---
# Schwab requires a public HTTPS redirect_uri; a Cloudflare Quick Tunnel exposes
# the local backend for that. Quick Tunnel URLs are random and change on every
# start (there's no way to pin one without a named tunnel on a domain you
# control), so this rewrites SCHWAB_REDIRECT_URI in .env on every run. You still
# have to paste the printed URL into Schwab's Developer Portal app settings
# yourself each time — Schwab validates the callback against what's registered
# there, and this script has no way to update that for you.
if [[ -z "$SKIP_TUNNEL" ]] && command -v cloudflared >/dev/null 2>&1 && [[ -f "$ENV_FILE" ]]; then
  echo "==> Starting Cloudflare Quick Tunnel for the Schwab OAuth callback..."
  TUNNEL_LOG="$(mktemp "${TMPDIR:-/tmp}/posted-cloudflared.XXXXXX")"
  cloudflared tunnel --url http://localhost:8000 &> "$TUNNEL_LOG" &
  CLOUDFLARED_PID="$!"

  TUNNEL_URL=""
  for i in $(seq 1 30); do
    TUNNEL_URL="$(grep -o 'https://[a-zA-Z0-9-]*\.trycloudflare\.com' "$TUNNEL_LOG" 2>/dev/null | head -1 || true)"
    [[ -n "$TUNNEL_URL" ]] && break
    sleep 1
  done

  if [[ -z "$TUNNEL_URL" ]]; then
    echo "warning: could not get a Quick Tunnel URL in time — continuing without updating SCHWAB_REDIRECT_URI (log: $TUNNEL_LOG)" >&2
  else
    REDIRECT_URI="$TUNNEL_URL/api/v1/connections/schwab/callback"
    if grep -q '^SCHWAB_REDIRECT_URI=' "$ENV_FILE"; then
      sed -i.bak "s|^SCHWAB_REDIRECT_URI=.*|SCHWAB_REDIRECT_URI=$REDIRECT_URI|" "$ENV_FILE"
      rm -f "$ENV_FILE.bak"
    else
      printf '\nSCHWAB_REDIRECT_URI=%s\n' "$REDIRECT_URI" >> "$ENV_FILE"
    fi
    echo "==> Schwab redirect URI: $REDIRECT_URI"
    echo "    >>> Paste this into Schwab's Developer Portal app settings before connecting. <<<"
  fi
elif [[ -z "$SKIP_TUNNEL" ]] && ! command -v cloudflared >/dev/null 2>&1; then
  echo "==> cloudflared not found — skipping Schwab OAuth tunnel (install: brew install cloudflared)"
fi

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
  if [[ -n "$CLOUDFLARED_PID" ]] && ! kill -0 "$CLOUDFLARED_PID" 2>/dev/null; then
    echo "==> Cloudflare tunnel exited unexpectedly — the Schwab OAuth callback will fail until this is restarted"
    CLOUDFLARED_PID=""
  fi
  sleep 1
done
