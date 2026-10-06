# AI Product Orchestrator — runtime image
# Build:  docker build -t ai-product-orchestrator:latest .
#
# The whole project is copied in (the `workflow/` package is imported by
# personal_agent.py at import time), so this image runs BOTH the AgentOS
# runtime (HTTP API on :7777) and the CLI pipeline (`uv run python -m
# workflow.run ...`). The old image copied only personal_agent.py and mounted
# workflow/ separately; that fragile split is gone.
FROM python:3.13-slim

# uv: fast dependency management + reproducible lockfile install
COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    DATA_DIR=/data

WORKDIR /app

# Install locked deps first (the dependency layer stays cached across builds).
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev

# Copy the full project (personal_agent.py entrypoint + the workflow package).
COPY personal_agent.py ./
COPY workflow/ ./workflow/

# Non-root runtime user; /data is the persistent state volume (SQLite + run
# artifacts + the rendered document bundle).
RUN useradd -m -u 10001 appuser && mkdir -p /data && chown -R appuser:appuser /data /app
USER appuser

EXPOSE 7777

HEALTHCHECK --interval=30s --timeout=5s --start-period=20s --retries=3 \
  CMD python -c "import urllib.request,sys; sys.exit(0 if urllib.request.urlopen('http://127.0.0.1:7777/health',timeout=4).status==200 else 1)"

CMD ["uv", "run", "personal_agent.py"]
