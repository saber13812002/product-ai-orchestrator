#!/usr/bin/env bash
# start.sh — build (first run) and start the service, then wait for health.
# Run from the repository root.
set -euo pipefail
cd "$(dirname "$0")/.."

if [ ! -f .env ]; then
  echo "ERROR: .env not found. Run ./scripts/install.sh first (or cp .env.example .env)."
  exit 1
fi

echo "==> Building image (no-op if unchanged) and starting"
docker compose up -d --build

echo "==> Waiting for /health ..."
PORT="${PORT:-7777}"
for i in $(seq 1 30); do
  if curl -sf "http://localhost:${PORT}/health" >/dev/null 2>&1; then
    echo "==> Healthy on :${PORT}"
    docker compose ps
    exit 0
  fi
  sleep 2
done

echo "==> Not healthy yet. Recent logs:"
docker compose logs --tail=40
exit 1
