#!/usr/bin/env bash
# Deploy the pushed commit to the persistent stack directory on this server,
# then `docker compose up -d --build` from there.
#
# Runs on the self-hosted *shell* runner (tag: server52), which checks out the
# repo into $CI_PROJECT_DIR and runs as root (has docker + curl). We copy that
# fresh checkout into DEPLOY_DIR (the persistent stack home, so `docker compose`
# always runs from the same path the manual workflow uses) and build+up there.
#
# Idempotent: only changed images rebuild; the named volume `agentos-data` is
# never touched. `.env` (holding LITELLM_API_KEY / PORT / CONTAINER_NAME) is
# backed up and restored across the copy so redeploy never wipes live config.
set -eu
DEPLOY_DIR="${DEPLOY_DIR:-/home/saber/saberprojects/ai-product-orchestrator}"
SRC="${CI_PROJECT_DIR:-$PWD}"   # runner's fresh checkout of the pushed commit

if [ ! -f "$SRC/docker-compose.yml" ]; then
  echo "ERROR: $SRC does not look like the repo (no docker-compose.yml)" >&2; exit 1
fi

mkdir -p "$DEPLOY_DIR"

echo "==> guard .env, sync $SRC -> $DEPLOY_DIR"
[ -f "$DEPLOY_DIR/.env" ] && cp "$DEPLOY_DIR/.env" /tmp/.env.deploy-backup || true
# wipe tracked content (not .env — already backed up; .git absent anyway)
find "$DEPLOY_DIR" -mindepth 1 -maxdepth 1 ! -name '.env' -exec rm -rf {} +
# copy the fresh checkout (exclude .git; checkout has no .env to preserve)
cd "$SRC"
tar --exclude=.git -cf - . | (cd "$DEPLOY_DIR" && tar -xf -)

# first-run: if there was no .env at all, seed from the template
if [ ! -f "$DEPLOY_DIR/.env" ]; then
  cp "$DEPLOY_DIR/.env.example" "$DEPLOY_DIR/.env"; chmod 600 "$DEPLOY_DIR/.env"
  echo "NOTE: seeded .env from .env.example — set LITELLM_API_KEY/PORT/CONTAINER_NAME."
elif [ -f /tmp/.env.deploy-backup ]; then
  cp /tmp/.env.deploy-backup "$DEPLOY_DIR/.env"; rm -f /tmp/.env.deploy-backup; chmod 600 "$DEPLOY_DIR/.env"
fi

cd "$DEPLOY_DIR"
echo "==> build + up (persistent dir)"
docker compose up -d --build

# health-wait (port from .env, default 7777)
PORT=$(grep -E '^PORT=' .env | cut -d= -f2 || true); PORT="${PORT:-7777}"
ok=0
for i in $(seq 1 60); do
  if curl -fsS "http://localhost:${PORT}/health" >/dev/null 2>&1; then
    ok=1; echo "==> healthy after $((i*3))s (port $PORT)"; break
  fi
  sleep 3
done
[ "$ok" = "1" ] || { echo "health check FAILED on :$PORT" >&2; exit 1; }
echo "==> DEPLOY OK (port $PORT)"
