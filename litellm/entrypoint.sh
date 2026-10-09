#!/bin/sh
# ==========================================================================
# STEP 9 — bundled LiteLLM sidecar startup: render config from env, then run.
#
# Why this exists: the official LiteLLM image does NOT expand ${VAR}
# placeholders inside a mounted config file. Verified on the build used here
# (ghcr.io/berriai/litellm:main-latest): with `api_base: ${FAST_MODEL_API_BASE}`
# the proxy failed every call with
#   InvalidUrlClientError: /$%7BFAST_MODEL_API_BASE%7D/chat/completions
# (the placeholder, URL-encoded, used as the literal URL). So the template's
# ${VAR} values must be substituted from the process environment before
# LiteLLM reads the file.
#
# What this does: expands every ${NAME} in the template with the current env
# (undefined -> empty), writes a rendered config, and execs the gateway on it.
# Uses only python3 + the litellm CLI (both present in the image) so it stays
# portable across LiteLLM versions.
#
#   LITELLM_CONFIG_TEMPLATE  in-container path of the mounted template
#   LITELLM_CONFIG_OUT       in-container path of the rendered config
#   "$@"                     the gateway args (e.g. --port 4000)
# ==========================================================================
set -e

TEMPLATE="${LITELLM_CONFIG_TEMPLATE:-/app/config.template.yaml}"
OUT="${LITELLM_CONFIG_OUT:-/tmp/litellm.config.rendered.yaml}"

python3 - "$TEMPLATE" "$OUT" <<'PY'
import os, re, sys

def repl(m):
    return os.environ.get(m.group(1), "")

tpl = open(sys.argv[1], "r", encoding="utf-8").read()
out = re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", repl, tpl)
open(sys.argv[2], "w", encoding="utf-8").write(out)
PY

exec litellm --config "$OUT" "$@"
