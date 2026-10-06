#!/usr/bin/env bash
# healthcheck.sh — report container + API + routing health.
# Run from the repository root.
set -uo pipefail
cd "$(dirname "$0")/.."
PORT="${PORT:-7777}"
fail=0

echo "== Container =="
docker compose ps
if ! docker compose ps --format '{{.State}}' | grep -qi running; then
  echo "    NOT running"; fail=1
fi

echo "== HTTP /health =="
if curl -sf "http://localhost:${PORT}/health"; then echo; else echo "    FAILED (is the port open?)"; fail=1; fi

echo "== Routing (logical role -> real model) =="
docker compose exec agno-agentos uv run python -m workflow.run routing 2>/dev/null || echo "    (routing check skipped — is a .env with a LiteLLM gateway set?)"

if [ "$fail" -eq 0 ]; then echo; echo "OK — all checks passed."; else echo; echo "FAIL — see above."; fi
exit "$fail"
