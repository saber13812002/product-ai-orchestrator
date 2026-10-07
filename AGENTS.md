# AGENTS.md — AI Product Orchestrator

Guide for AI coding agents (and humans) working in this repository. Read this first; the
detailed docs it points to are in `docs/`.

## What this is

A multi-agent, multi-model **AI product design orchestrator** built on [Agno AgentOS](https://github.com/agno-agi/agno).
Input: a natural-language product brief. Output: a scored 17-section system design + 8 deep
technical documents (Backend, DB, API, Frontend, UX, Security, Testing, DevOps).
All LLM calls go through **one LiteLLM gateway** (default `http://172.20.1.52:4000/v1`).

## Repo identity

- **Remote:** `https://git.ai.ismc.ir/common/website/ai-product-orchestrator` (internal GitLab CE on
  server 52, port 81; git over `http://172.20.1.52:81/...`). Private.
- **Deploy target (server 52):** `/home/saber/saberprojects/ai-product-orchestrator` — a
  **second** live instance, container `agno-agentos-repo`, port **7779**. The original
  production instance `agno-agentos` (port **7777**) lives at `/home/saber/agentos/` and is
  **not managed by this repo** — never touch it.
- **Working tree (laptop):** `C:\Users\s.tabatabaei\Documents\saberprojects\server52and53\ai-product-orchestrator`.
  Project reports (per-step history, decisions) live one level up in `server52and53/`
  (`STEP1_REPORT.md` … `STEP7_REPORT.md`).

## Commands (the ones that matter)

```bash
# Hermetic tests — NO LLM, NO LiteLLM, NO API key. Must always pass; this is what CI runs.
uv run --with pytest python -m pytest workflow/tests -q        # expected: 20 passed

# Or, exactly as CI runs it (throwaway python:3.13-slim container):
bash scripts/ci-docker.sh

# Run the service locally (needs a .env with LITELLM_* + AGENT_MODEL_*):
cp .env.example .env
uv run personal_agent.py                                      # AgentOS HTTP on :7777

# Run a pipeline in the live container (on 52):
docker compose exec agno-agentos uv run python -m workflow.run full  --brief "..."
docker compose exec agno-agentos uv run python -m workflow.run enrich --brief "..."
```

## Hard rules (do not break these)

1. **No secrets in the repo.** `.env` is gitignored; only `.env.example` is tracked. The LiteLLM
   master key is a live credential — it exists only in `.env` files on server 52
   (`/home/saber/agentos/.env`, and the deploy target's `.env`). Never print or commit it.
2. **CI is hermetic by design.** `workflow/tests/` use a `FakeRouter`. Never make a test need
   network/LLM/keys, or the CI promise ("no LLM, no API key, no cost") is broken.
3. **Git line endings are LF.** `.gitattributes` forces `eol=lf` (the repo was created on
   Windows with `core.autocrlf=true`; without this, `git archive`/CI checkouts emit CRLF and
   `set -euo pipefail` dies in bash). Don't remove it.
4. **Structured output only from the `fast` role.** The deep/alt models on the LiteLLM fleet
   (qwen38 thinking models) burn their entire output budget on reasoning and return empty
   content when asked for JSON. All judges / structured agents must run on `fast`
   (`qwen38-nothinking`). This is why `TASK_MODEL_HINTS` in `workflow/config.py` is
   authoritative.
5. **Git commits** end with: `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.
6. **Branch/commit style** per `docs/DEVELOPMENT.md`: `feat/|fix/|chore/|docs/|test/` branches,
   imperative subjects, MR → CI green → merge to `main`. Releases: annotated `vX.Y.Z` tags
   (`docs/RELEASES.md`).

## CI/CD (GitLab, self-hosted on server 52)

- **Two `shell`-executor runners serve this project, both tagged `server52`:**
  - **`AI-TOOLS`** (runner #1, root, systemd service `gitlab-runner`, config
    `/etc/gitlab-runner/config.toml`) — the group runner that usually picks up jobs.
  - **`aio-server52`** (runner #5, user `saber`, user-mode, config
    `/home/saber/gitlab-runner-aio/config.toml`, log `.../runner.log`).
- **Jobs are tagged `server52`** in `.gitlab-ci.yml` (ordinary tag matching; do not depend on
  `run_untagged_jobs`).
- **Shell runners ignore `image:`** — the `test` job spawns its own `python:3.13-slim`
  container (`scripts/ci-docker.sh`), which runs `scripts/ci.sh` on a **container-local copy**
  of the source (container runs as root; never let it write into the checkout).
- **CRITICAL GOTCHA — `clone_url`:** GitLab's `external_url` is the public
  `https://git.ai.ismc.ir` (port 443), which **server 52 itself cannot reach** (it resolves to
  a public IP). Both runners therefore need
  `clone_url = "http://172.20.1.52:81"` in their `[[runners]]` block, else every job dies in
  `Getting source` with `Failed to connect to git.ai.ismc.ir port 443`. (Fixed on runner #5 on
  2026-10-07; runner #1 needs the same edit — requires sudo.)
- **Deploy** (`scripts/deploy-repo.sh`) syncs the checkout to the deploy target and runs
  `docker compose up -d --build` + health-wait on port 7779. It **guards the deploy target's
  `.env`** across redeploys (backs it up, restores it).
- **Reboot note:** runner #5 is user-mode (no sudo → no systemd). If 52 reboots, relaunch it:
  `setsid nohup /usr/local/bin/gitlab-runner run --config /home/saber/gitlab-runner-aio/config.toml \
   > /home/saber/gitlab-runner-aio/runner.log 2>&1 &`

## Key locations

| What | Where |
|---|---|
| Pipeline engine (13 steps + enrichment) | `workflow/engine.py` |
| Single source of truth (models, thresholds, weights) | `workflow/config.py` |
| Role prompts + shared quality rubric | `workflow/prompts.py` |
| Hermetic test suites | `workflow/tests/` |
| CI entry (container) | `scripts/ci-docker.sh` → `scripts/ci.sh` |
| CI deploy | `scripts/deploy-repo.sh` |
| Docs | `docs/` (ARCHITECTURE, DEPLOYMENT, CONFIGURATION, AGENT_DESIGN, DEVELOPMENT, RELEASES) |
| Per-step project history (laptop only) | `../STEP*_REPORT.md` |
