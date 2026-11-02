# AGENTS.md — AI Product Orchestrator

Guide for AI coding agents (and humans) working in this repository. Read this first; the
detailed docs it points to are in `docs/`.

## What this is

A multi-agent, multi-model **AI product design orchestrator** built on [Agno AgentOS](https://github.com/agno-agi/agno).
Input: a natural-language product brief. Output: a scored 17-section system design + 8 deep
technical documents (Backend, DB, API, Frontend, UX, Security, Testing, DevOps).
All LLM calls go through **one LiteLLM gateway**, in two deployment modes: **External** (connect
to a gateway you already run — the default) or **Bundled** (a sidecar this repo starts). Both are
resolved in one place — `workflow/config.py::resolve_endpoint()`. See [LITELLM.md](docs/LITELLM.md).

## Repo identity

- **Remote:** `https://git.ai.ismc.ir/common/website/ai-product-orchestrator` (internal GitLab CE on
  server 133, port 81; git over `http://172.30.0.133:81/...`). Private. *(was server 52, migrated 2026-11-02)*
- **Deploy target (server 133):** `/home/saber/saberprojects/ai-product-orchestrator` — a
  **second** live instance, container `agno-agentos-repo`, port **7779**. The original
  production instance `agno-agentos` (port **7777**) lives at `/home/saber/agentos/` and is
  **not managed by this repo** — never touch it.
- **Working tree (laptop):** `C:\Users\s.tabatabaei\Documents\saberprojects\server52and53\ai-product-orchestrator`.
  Project reports (per-step history, decisions) live one level up in `server52and53/`
  (`STEP1_REPORT.md` … `STEP7_REPORT.md`).

## Commands (the ones that matter)

```bash
# Hermetic tests — NO LLM, NO LiteLLM, NO API key. Must always pass; this is what CI runs.
uv run --with pytest python -m pytest workflow/tests -q        # expected: 30 passed

# Or, exactly as CI runs it (throwaway python:3.13-slim container):
bash scripts/ci-docker.sh

# Run the service locally (needs a .env with LITELLM_* + AGENT_MODEL_*):
cp .env.example .env
uv run personal_agent.py                                      # AgentOS HTTP on :7777

# Start (live container) — two modes (see docs/LITELLM.md):
#   docker compose up -d                              # Mode A — external gateway (default)
#   docker compose --profile bundled-litellm up -d    # Mode B — bundled LiteLLM sidecar

# Run a pipeline in the live container (on 52):
docker compose exec agno-agentos uv run python -m workflow.run full  --brief "..."
docker compose exec agno-agentos uv run python -m workflow.run enrich --brief "..."
docker compose exec agno-agentos uv run python -m workflow.run refine --brief "..."
docker compose exec agno-agentos uv run python -m workflow.run endpoint   # which mode / URL AgentOS resolved
#   `refine` = `enrich` + a targeted 2nd pass that re-runs only the doc-completeness
#   gate's gapful documents (DDL / OpenAPI / payment / observability / ...) to lift
#   completeness. It uses a larger budget (config.REFINE_TOKEN_BUDGET) by default.
#   `endpoint` prints the resolved LITELLM mode + base URL + whether a key is configured
#   (never the key). `routing` prints the role → real-model table.
```

## Hard rules (do not break these)

1. **No secrets in the repo.** `.env` is gitignored; only `.env.example` is tracked. The LiteLLM
   master key is a live credential — it exists only in `.env` files on server 133
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

## CI/CD (GitLab, self-hosted on server 133)

- **The project is served by the healthy root runner** **`AI-TOOLS`** (runner #1) — root systemd
  service `gitlab-runner`, config `/etc/gitlab-runner/config.toml`. All `server52` jobs run on it.
  **Do NOT (re)start `aio-server52` (runner #5):** it is a user-mode shell runner (user `saber`,
  config `/home/saber/gitlab-runner-aio/config.toml`, log `.../runner.log`) that **failed every job
  at `prepare environment: exit status 1`** (see below) and was **stopped + deactivated in GitLab on
  2026-10-10** (`Ci::Runner.find(5).update!(active: false)`). It is redundant now that #1 is healthy.
  If it is ever reactivated it will race #1 for jobs and turn the pipeline red again.
- **Jobs are tagged `server52`** in `.gitlab-ci.yml` (ordinary tag matching; do not depend on
  `run_untagged_jobs`).
- **Shell runners ignore `image:`** — the `test` job spawns its own `python:3.13-slim`
  container (`scripts/ci-docker.sh`), which runs `scripts/ci.sh` on a **container-local copy**
  of the source (container runs as root; never let it write into the checkout).
- **CRITICAL GOTCHA — `clone_url`:** GitLab's `external_url` is the public
  `https://git.ai.ismc.ir` (port 443), which **server 133 itself cannot reach** (it resolves to
  a public IP). Every runner on 52 therefore carries
  `clone_url = "http://172.30.0.133:81"` in its `[[runners]]` block, else the job dies in
  `Getting source` with `Failed to connect to git.ai.ismc.ir port 443`. (Fixed on all runners
  2026-10-08; first green pipeline `#81` verified that day. If a job fails with the port-443
  error again, a new runner was likely registered without `clone_url`.)
- **Deploy** (`scripts/deploy-repo.sh`) syncs the checkout to the deploy target and runs
  `docker compose up -d --build` + health-wait on port 7779. It **guards the deploy target's
  `.env`** across redeploys (backs it up, restores it). The deploy target dir
  (`/home/saber/saberprojects/ai-product-orchestrator`) is **root-owned and file-synced** (not a
  git clone) — that's why the `deploy` job runs fine on the root runner #1.
- **CI/CD gotcha — a broken user-mode runner was stealing jobs (STEP 9.5, fixed 2026-10-10):**
  the user-mode `aio-server52` (runner #5) failed **every** job at
  `prepare environment: exit status 1` (~13 ms, **before** the job script ran) — both `test` and
  `deploy`. Because it had `run_untagged_jobs=true` + `check_interval=0` and shared the
  `server52` tag with the healthy root runner #1, GitLab **load-balanced** jobs between the two and
  every job that landed on #5 died, so the pipeline was flaky/red and 7779 never auto-redeployed.
  Fix (no sudo): **stopped the process** and **deactivated it in GitLab**
  (`Ci::Runner.find(5).update!(active: false)`) so all `server52` jobs run deterministically on #1.
  Verified: pipeline for `main` @ `v0.3.0` went green (test 30 passed → deploy 7779 healthy).
  The exact `prepare environment` cause is in the job **trace** in GitLab (the runner log only shows
  the generic hint); it is specific to #5's user-mode shell-prep context and does not affect #1.
- **Reboot note:** runner #1 is a root systemd service (`gitlab-runner`) and restarts automatically.
  **Do NOT** relaunch the user-mode runner #5 after a reboot (it is disabled on purpose — see above);
  #1 alone serves this project.

## Key locations

| What | Where |
|---|---|
| Pipeline engine (13 steps + enrichment) | `workflow/engine.py` |
| Single source of truth (models, thresholds, weights) | `workflow/config.py` |
| Role prompts + shared quality rubric | `workflow/prompts.py` |
| Hermetic test suites | `workflow/tests/` |
| CI entry (container) | `scripts/ci-docker.sh` → `scripts/ci.sh` |
| CI deploy | `scripts/deploy-repo.sh` |
| Bundled LiteLLM sidecar (Mode B) | `litellm/config.yaml` (routing template, no secrets) + `litellm/entrypoint.sh` (renders `${VAR}` from env at start) |
| Docs | `docs/` (ARCHITECTURE, DEPLOYMENT, CONFIGURATION, AGENT_DESIGN, DEVELOPMENT, RELEASES, LITELLM, AI_HANDOFF) |
| Per-step project history (laptop only) | `../STEP*_REPORT.md` |

> **Compose project-isolation gotcha (learned the hard way):** Docker Compose identifies a
> container by its `(project_name, service)` label, **not** `container_name`. Starting a second
> stack with the same project name + service `agno-agentos` (even with a different
> `container_name`/port) will **recreate/destroy** the first. Always run an isolated test with a
> **separate compose project**: `docker compose -p myproj --profile bundled-litellm up -d`. The
> deploy target `agno-agentos-repo` (7779) and the production `agno-agentos` (7777) must never
> be touched by tests.
