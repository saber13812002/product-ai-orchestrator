#!/usr/bin/env bash
# Hermetic CI for a self-hosted *shell* runner (which ignores `image:`).
#
# The self-hosted runner on server 52 (tag: server52) uses the `shell`
# executor, so a Docker `image:` in .gitlab-ci.yml is NOT applied. Instead we
# reproduce the locked Python environment inside a throwaway python:3.13-slim
# container and run the SAME scripts/ci.sh body that GitHub Actions uses.
#
# HERMETIC BY DESIGN: no LiteLLM, no LLM, no API key, no network to any model.
#
# NOTE: the source is COPIED into a container-local dir (/build) before running.
# The container runs as root; if we let `uv` create .venv in the bind-mounted
# checkout, the checkout would be left with root-owned files the runner cannot
# clean between jobs. Copying keeps the runner's checkout pristine.
set -eu
cd "$(dirname "$0")/.."

IMAGE="${CI_IMAGE:-python:3.13-slim}"

echo "==> CI in container: $IMAGE  (hermetic — no LLM / LiteLLM / API key)"
docker run --rm \
  -v "$PWD:/src:ro" \
  "$IMAGE" bash -lc '
    set -eu
    # python:3.13-slim ships python+pip but NOT uv and NOT curl.
    # Install uv from PyPI (reachable on 52), no curl needed.
    python -m pip install --quiet uv
    export PATH="/usr/local/bin:$HOME/.local/bin:$PATH"
    # belt-and-suspenders: make sure no model creds leak into the CI env
    unset LITELLM_API_KEY LITELLM_BASE_URL OPENAI_API_KEY OPENAI_BASE_URL 2>/dev/null || true
    # work on a container-local copy so the (read-only) checkout is never modified
    mkdir -p /build && cp -a /src/. /build/
    cd /build
    bash scripts/ci.sh
  '
echo "==> CI PASSED"
