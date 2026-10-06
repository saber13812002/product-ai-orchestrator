#!/usr/bin/env bash
# install.sh — pre-flight checks + first-time setup.
# Run from the repository root.
set -euo pipefail

cd "$(dirname "$0")/.."

echo "==> Checking prerequisites"
command -v docker >/dev/null 2>&1 || { echo "ERROR: docker not found. Install Docker Engine first."; exit 1; }
docker compose version >/dev/null 2>&1 || { echo "ERROR: 'docker compose' plugin not found."; exit 1; }
echo "    docker:      $(docker --version)"
echo "    compose:     $(docker compose version --short 2>/dev/null || echo n/a)"

# Create .env from the template if absent (never overwrite an existing one).
if [ -f .env ]; then
  echo "==> .env already exists — leaving it untouched."
else
  cp .env.example .env
  echo "==> Created .env from .env.example — EDIT IT before starting."
fi

echo
echo "==> Next steps:"
echo "    1. Edit .env  (set LITELLM_BASE_URL, LITELLM_API_KEY, AGENT_MODEL_*)"
echo "    2. ./scripts/start.sh"
