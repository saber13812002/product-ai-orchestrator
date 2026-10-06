#!/usr/bin/env bash
# ci.sh — the portable CI pipeline body.
#
# Invoked by BOTH .gitlab-ci.yml and .github/workflows/ci.yml, so the pipeline
# logic is written once and reused. Steps:
#   1. Build the Python environment from the lockfile (uv sync --frozen).
#   2. Confirm the key dependencies import.
#   3. Syntax-check the whole package (compileall).
#   4. Run the hermetic test suite (pytest).
#
# HERMETIC BY DESIGN: needs NO LiteLLM, NO LLM, NO API key, and no network to
# any model endpoint. (It only uses PyPI to install deps, like any Python CI.)
set -euo pipefail
cd "$(dirname "$0")/.."

echo "==> CI: hermetic (no LLM / no LiteLLM / no API key required)"
# Prove the pipeline does not depend on any model credentials.
unset LITELLM_API_KEY LITELLM_BASE_URL OPENAI_API_KEY OPENAI_BASE_URL 2>/dev/null || true

echo "==> [1/4] Python environment from lockfile (uv sync --frozen --no-dev)"
uv sync --frozen --no-dev

echo "==> [2/4] dependency sanity"
uv run python -c "import agno, pydantic, openai; print('   agno OK | pydantic', pydantic.__version__, '| openai', openai.__version__)"

echo "==> [3/4] syntax check (compileall workflow + entrypoint)"
uv run python -m compileall -q workflow personal_agent.py && echo "   syntax OK"

echo "==> [4/4] hermetic tests (pytest, no network to models)"
uv run --with pytest python -m pytest workflow/tests -q

echo "==> CI PASSED"
