# Deployment Guide

Deploy the AI Product Orchestrator on a clean Linux server with **Docker Compose**. One service;
the code is baked into the image; all state lives in a Docker volume.

> **Quick start:** [`cp .env.example .env`](#3-configure-the-environment) → `docker compose up -d`.
> The full walkthrough is below.

## Requirements

- **Linux server** (x86_64 or arm64).
- **Docker Engine** ≥ 20.10 and the **`docker compose`** plugin (`docker compose version`).
- **Network access to a LiteLLM gateway.** This repo does **not** run LiteLLM — it talks to one
  you already have (or will have). The container must be able to reach `LITELLM_BASE_URL` (e.g.
  `http://172.20.1.52:4000/v1`). If LiteLLM runs on the same host, that host IP / its container
  name works; from a different host use its routable address.
- **Git** (for the recommended clone-based install) — or just the repository files.

> **A note on the gateway:** point `LITELLM_BASE_URL` at a gateway that actually serves the model
> names you configure (`AGENT_MODEL_FAST/DEEP/ALT`). The defaults assume a Qwen3.8-27B fleet
> (`qwen38-nothinking`, `qwen38`, `qwen38-sglang`) served by LiteLLM; change them for any other
> fleet. The pipeline needs a **non-thinking** `fast` model that reliably emits complete
> structured JSON, and a **thinking** `deep`/`alt` pair (see [CONFIGURATION.md](CONFIGURATION.md)).

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

Edit `.env` (do **not** commit it — it's gitignored):

```ini
# Required — your LiteLLM gateway
LITELLM_BASE_URL=http://172.20.1.52:4000/v1
LITELLM_API_KEY=<your-litellm-master-or-virtual-key>

# Model names as served by your gateway (defaults shown are the reference Qwen fleet)
AGENT_MODEL_FAST=qwen38-nothinking
AGENT_MODEL_DEEP=qwen38
AGENT_MODEL_ALT=qwen38-sglang

# Optional
PORT=7777
```

If you only use the HTTP API (the `personal_agent` assistant) and not the pipeline, the model
names are optional — the API uses `AGENT_MODEL_FAST` as its default agent model.

## 4. Start the containers

```bash
docker compose up -d
```

This builds the image on first run and starts the `agno-agentos` service. Follow the startup:

```bash
docker compose logs -f
```

## First health check

```bash
docker ps                                  # agno-agentos should be Up (health: starting → healthy)
curl -s http://localhost:7777/health       # -> {"status":"healthy", ...}
```

The container also has a built-in `HEALTHCHECK` that hits `/health`, so `docker ps` will report
`health: healthy` once it's up (a few seconds of `starting` is normal). Confirm routing sees your
gateway's models:

```bash
docker compose exec agno-agentos uv run python -m workflow.run routing
```

That prints the logical-role → real-model table resolved from your `.env`.

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

Configs to keep alongside: your `.env` (secrets — store it in your secrets manager) and any custom
`docker-compose.yml` edits.

## Operations cheat-sheet

| Task | Command |
|---|---|
| Start | `docker compose up -d` |
| Stop (keep volume) | `docker compose down` |
| Stop + delete volume (data loss) | `docker compose down -v` |
| Logs | `docker compose logs -f` |
| Status | `docker ps` |
| Shell into container | `docker compose exec agno-agentos sh` |
| Rebuild image | `docker compose build` |
| Update | `git pull && docker compose build && docker compose up -d` |
| Health | `curl -s localhost:7777/health` |
