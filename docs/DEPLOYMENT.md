# Deployment Guide

Deploy the AI Product Orchestrator on a clean Linux server with **Docker Compose**. One service by
default; the code is baked into the image; all state lives in a Docker volume.

There are **two deployment scenarios**, differing only in who runs the LiteLLM gateway. Full
details, configuration, and troubleshooting are in **[LITELLM.md](LITELLM.md)**.

| | Scenario 1 — You already have a LiteLLM gateway | Scenario 2 — Bundled sidecar (fresh server, no gateway) |
|---|---|---|
| Start | `docker compose up -d` | `docker compose --profile bundled-litellm up -d` |
| `.env` | `LITELLM_BASE_URL`, `LITELLM_API_KEY` | `LITELLM_MODE=bundled`, `LITELLM_MASTER_KEY`, `*_MODEL_API_*` |
| Containers | `agno-agentos` | `agno-agentos` **+ `litellm-sidecar`** |

> **Quick start (Scenario 1):** [`cp .env.example .env`](#3-configure-the-environment) →
> `docker compose up -d`. The full walkthrough is below.

## Requirements

- **Linux server** (x86_64 or arm64).
- **Docker Engine** ≥ 20.10 and the **`docker compose`** plugin (`docker compose version`). For
  bundled mode (Scenario 2) you also need **compose v2.20+** (the sidecar's health-dependency uses
  `depends_on … required: false`). Check with `docker compose version`.
- **Model access.** Either:
  - **Scenario 1 (external):** network access to a LiteLLM gateway you already run
    (`LITELLM_BASE_URL`, e.g. `http://172.30.0.133:4000/v1`).
  - **Scenario 2 (bundled):** the sidecar the repo starts needs network access to your model
    backends (vLLM / SGLang / OpenAI-compatible servers).
- **Git** (for the recommended clone-based install) — or just the repository files.

> **A note on the models:** whatever gateway you use must serve the model names you configure
> (`AGENT_MODEL_FAST/DEEP/ALT`). The defaults assume a Qwen3.8-27B fleet
> (`qwen38-nothinking`, `qwen38`, `qwen38-sglang`). The pipeline needs a **non-thinking** `fast`
> model that reliably emits complete structured JSON, and a **thinking** `deep`/`alt` pair
> (see [CONFIGURATION.md](CONFIGURATION.md) and [LITELLM.md](LITELLM.md)).

## 1. Clone the repository

```bash
git clone <repo-url> ai-product-orchestrator
cd ai-product-orchestrator
```

## 2. Create the environment file

```bash
cp .env.example .env
```

## 3. Configure the environment

Edit `.env` (do **not** commit it — it's gitignored). Pick the block for your scenario.

### Scenario 1 — you already have a LiteLLM gateway

```ini
# LITELLM_MODE=external            # (default — you can leave this unset)
# Required — your LiteLLM gateway
LITELLM_BASE_URL=http://172.30.0.133:4000/v1
LITELLM_API_KEY=<your-litellm-master-or-virtual-key>

# Model names as served by your gateway (defaults shown are the reference Qwen fleet)
AGENT_MODEL_FAST=qwen38-nothinking
AGENT_MODEL_DEEP=qwen38
AGENT_MODEL_ALT=qwen38-sglang

# Optional
PORT=7777
```

### Scenario 2 — bundled sidecar (no gateway on this server)

```ini
LITELLM_MODE=bundled
# Generate one:  echo "sk-$(openssl rand -hex 32)"  — never commit it
LITELLM_MASTER_KEY=sk-<your-generated-sidecar-key>
# Optional: host port (127.0.0.1) for the sidecar UI/API. Default 4100.
#LITELLM_PORT=4100

# The backends the sidecar routes each role to (any OpenAI-compatible /v1 endpoint)
FAST_MODEL_API_BASE=http://<your-vllm>:8000/v1
FAST_MODEL_API_MODEL=<model-id-that-backend-serves>
DEEP_MODEL_API_BASE=http://<your-vllm>:8000/v1
DEEP_MODEL_API_MODEL=<model-id>
ALT_MODEL_API_BASE=http://<your-sglang>:8001/v1
ALT_MODEL_API_MODEL=<model-id>

# The model names AgentOS calls (the sidecar exposes these same names)
AGENT_MODEL_FAST=qwen38-nothinking
AGENT_MODEL_DEEP=qwen38
AGENT_MODEL_ALT=qwen38-sglang

# Optional
PORT=7777
```

> **`_API_KEY` for local no-auth backends:** leave it empty — the compose file injects a `dummy`
> placeholder (the OpenAI client refuses a blank key, and the no-auth backend ignores it anyway).
> **Reference Qwen fleet:** the `fast` role needs thinking off — uncomment the
> `enable_thinking: false` block in `litellm/config.yaml`. See [LITELLM.md](LITELLM.md#the-reference-qwen-fleet-thinking-models).

If you only use the HTTP API (the `personal_agent` assistant) and not the pipeline, the model
names are optional — the API uses `AGENT_MODEL_FAST` as its default agent model.

## 4. Start the containers

**Scenario 1 (external):**

```bash
docker compose up -d          # starts only agno-agentos
```

**Scenario 2 (bundled sidecar):**

```bash
docker compose --profile bundled-litellm up -d   # starts agno-agentos + litellm-sidecar
```

This builds the image on first run. Follow the startup:

```bash
docker compose logs -f
```

> **Do not mix the two.** If you already run a LiteLLM gateway, use Scenario 1 — don't also start
> the sidecar (you'd have two gateways and a port collision).

## First health check

```bash
docker ps                                  # agno-agentos (+ litellm-sidecar in Scenario 2) -> Up (health: starting → healthy)
curl -s http://localhost:7777/health       # -> {"status":"healthy", ...}
```

The container also has a built-in `HEALTHCHECK` that hits `/health`, so `docker ps` will report
`health: healthy` once it's up (a few seconds of `starting` is normal). In Scenario 2 the sidecar
has its own healthcheck, so both rows should read `healthy`. Confirm the endpoint and routing:

```bash
docker compose exec agno-agentos uv run python -m workflow.run endpoint   # -> mode: external|bundled
docker compose exec agno-agentos uv run python -m workflow.run routing
```

`endpoint` tells you which mode and base URL AgentOS resolved (external → your gateway; bundled →
`http://litellm:4000/v1`) and whether a key is configured. `routing` prints the logical-role →
real-model table resolved from your `.env`.

## Run a pipeline (optional)

```bash
# 13-step design pipeline (TEST mode, ~20k tokens)
docker compose exec agno-agentos uv run python -m workflow.run full --brief "B2B sales CRM with customers, orders and org roles"

# + Design Enrichment (8 deep documents + completeness gate)
docker compose exec agno-agentos uv run python -m workflow.run enrich --brief "B2B sales CRM with customers, orders and org roles"
```

Output and the token ledger are printed to the console; `state.json` and the document bundle are
written to the `agentos-data` volume under `/data/runs/{run_id}/` and `/data/documents/{run_id}/`.

## Update procedure

To deploy a newer version:

```bash
git pull
docker compose build          # rebuild the image with the new code
docker compose up -d          # recreate the container (state in the volume is preserved)
```

`restart: unless-stopped` keeps the container running across reboots.

## Backup

What to back up (all of it lives in the `agentos-data` volume, unless you use the host bind-mount):

| Data | Location | Why back it up |
|---|---|---|
| Pipeline state | `/data/runs/{run_id}/state.json` | Full run history: designs, scores, ledger |
| Document bundle | `/data/documents/{run_id}/*.md` | The rendered technical documents |
| AgentOS SQLite | `/data/agent.db` | The AgentOS runtime's own store |

**Named volume** (default):

```bash
docker run --rm -v ai-product-orchestrator_agentos-data:/data -v "$PWD/backup":/out alpine \
  tar czf /out/agentos-data-backup.tar.gz -C /data .
```

**Host bind-mount** (if you enabled `./workflow/storage:/data` in `docker-compose.yml`):

```bash
tar czf agentos-storage-backup.tar.gz workflow/storage/
```

> **Bundled sidecar (Scenario 2):** the sidecar's own state lives in the `litellm-data` volume
> (`ai-product-orchestrator_litellm-data`). It's optional — empty until you enable spend logs or
> virtual keys — so there's usually nothing to back up, but if you have, back it up the same way
> (substitute the volume name in the command above).

Configs to keep alongside: your `.env` (secrets — store it in your secrets manager) and any custom
`docker-compose.yml` edits.

## Operations cheat-sheet

| Task | Command |
|---|---|
| Start (external) | `docker compose up -d` |
| Start (bundled sidecar) | `docker compose --profile bundled-litellm up -d` |
| Stop (keep volume) | `docker compose down` (add `--profile bundled-litellm` in Scenario 2 to also stop the sidecar) |
| Stop + delete volume (data loss) | `docker compose down -v` |
| Logs | `docker compose logs -f` |
| Status | `docker ps` |
| Endpoint/mode | `docker compose exec agno-agentos uv run python -m workflow.run endpoint` |
| Routing table | `docker compose exec agno-agentos uv run python -m workflow.run routing` |
| Shell into container | `docker compose exec agno-agentos sh` |
| Sidecar UI/API (bundled) | `http://127.0.0.1:${LITELLM_PORT:-4100}` (loopback only) |
| Rebuild image | `docker compose build` |
| Update | `git pull && docker compose build && docker compose up -d` (add `--profile bundled-litellm` in Scenario 2) |
| Health | `curl -s localhost:7777/health` |

> **Deploying a new version in bundled mode:** always pass the same profile you started with,
> otherwise compose will only manage the services for the profiles you name.
