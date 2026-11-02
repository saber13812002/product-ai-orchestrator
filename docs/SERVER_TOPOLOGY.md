# Server Topology — AI Product Orchestrator

> **Authoritative address map.** This document is the single source of truth for every server
> address, port, and operational path this project touches. If an address appears elsewhere in
> the repo and conflicts with this file, **this file wins** — report the conflict.
>
> **Last updated: 2026-11-02** (after the 52→133 migration).

## The 52→133 Migration (2026-11-02)

The server previously known as **52** (172.20.1.52) was **migrated to 133** (172.30.0.133,
hostname `AI-TOOLS`) on 2026-11-02. All infrastructure that ran on 52 now runs on 133. The old
address `172.20.1.52` is **dead** — nothing is listening there.

| What was on 52 | Now on 133 |
|---|---|
| GitLab CE (`:81`) | GitLab CE (`:81`) — container `gitlab` (postgres:14, redis:7) |
| CI Runner `aio-server52` (#5, tag `server52`) | Same runner, same config — **but `url`/`clone_url` still point to dead `http://172.20.1.52:81`** (needs re-point) |
| CI Runner `9router-ci-server52` (project 51) | Same — **`url` still points to dead `http://172.20.1.52:81/`** (needs re-point) |
| AgentOS Production (`:7777`) | AgentOS Production (`:7777`) — container `agno-agentos` |
| AgentOS Deploy target (`:7779`) | AgentOS Deploy target (`:7779`) — container `agno-agentos-repo` |
| LiteLLM external gateway (`:4000`) | LiteLLM external gateway (`:4000`) |
| Prometheus + Grafana (shared) | Same stack on 133 (bound to stale `172.20.1.52` in some configs — separate follow-up) |
| v0.3.0 deploy | Deploy target at `/home/saber/saberprojects/ai-product-orchestrator` |

**What did NOT migrate:** the model backends on 53 (172.20.1.53) and any unrelated AI services
on 117. See the model-fleet table below.

## Current Address Map (verified 2026-11-02)

| Service | Address | Port | Notes |
|---|---|---|---|
| **GitLab CE** | `172.30.0.133` | `81` | Container `gitlab`. Project 28 = this repo. Web: `http://172.30.0.133:81/common/website/ai-product-orchestrator` |
| **AgentOS (Production)** | `172.30.0.133` | `7777` | Container `agno-agentos`. **NOT managed by this repo — never touch.** |
| **AgentOS (Deploy target)** | `172.30.0.133` | `7779` | Container `agno-agentos-repo`. CI deploys `main` here. |
| **LiteLLM external gateway** | `172.30.0.133` | `4000` | The gateway AgentOS uses. `LITELLM_BASE_URL=http://172.30.0.133:4000/v1` |
| **Git clone URL** | `172.30.0.133` | `81` | `http://172.30.0.133:81/common/website/ai-product-orchestrator.git` |
| **Model backends (Qwen3.8-27B-FP8)** | `172.20.1.53` | `8000` / `8001` | vLLM `:8000` (nothinking), vLLM `:8001` (sglang). Reachable from 133. |
| **Unrelated AI (BGE-M3, Whisper)** | `172.20.1.117` | — | **Not used by this orchestrator.** |

## SSH Access

| Server | How to reach | User |
|---|---|---|
| **133** (172.30.0.133) | Direct from VM | `saber@172.30.0.133` |
| **53** (172.20.1.53) | Via 133 jump | `ssh jump53` (from 133) |

## CI / GitLab Runner Status (2026-11-02)

| Runner | ID | Name | Tag | Executor | `url` / `clone_url` | Status |
|---|---|---|---|---|---|---|
| `aio-server52` | 5 | `aio-server52` | `server52` | shell | `http://172.20.1.52:81` (DEAD) | **Broken** — points to dead 52; needs re-point to `http://172.30.0.133:81` |
| `9router-ci-server52` | — | `9router-ci-server52` | (untagged, `run_untagged_jobs=true`) | shell | `http://172.20.1.52:81/` (DEAD) | **Broken** — serves project 51 (9router); needs re-point |

**Both runners are registered on 133's GitLab** (systemd `gitlab-runner.service` is active) but
their `url`/`clone_url` fields still point to the dead `172.20.1.52:81`. Until these are
re-pointed, **CI is non-functional** for any project on 133's GitLab.

**Important:** the runner config files live at:
- `/home/saber/gitlab-runner-aio/config.toml` (runner `aio-server52`, project 28)
- `/home/saber/.gitlab-runner/config.toml` (runner `9router-ci-server52`, project 51)

**Do not edit these files without a backup and separate user approval** — the runners may be
shared between projects, and changing a shared runner's `url`/`clone_url` affects all projects
attached to it.

## Old Address Reference (Category B — historical)

These are the **old** addresses that were used before the migration. They are preserved here for
historical reference only. **Do not use any of these addresses operationally.**

| Old address | What it was | Status |
|---|---|---|
| `172.20.1.52:81` | GitLab CE (before migration) | **DEAD** |
| `172.20.1.52:7777` | AgentOS Production (before migration) | **DEAD** |
| `172.20.1.52:7779` | AgentOS Deploy target (before migration) | **DEAD** |
| `172.20.1.52:4000` | LiteLLM external gateway (before migration) | **DEAD** |
| `http://172.20.1.52:81/common/website/ai-product-orchestrator.git` | Git clone URL (before migration) | **DEAD** |

## What is OUT of scope for this repo

The following services are **entirely outside the scope** of the AI Product Orchestrator
repository. They exist on the same infrastructure but are managed by other projects/repos:

- **ASR (Automatic Speech Recognition)** — `asr.ismc.ir` (external Django app, 185.208.180.203)
- **Whisper** — whisper-persian-v4 on 188.80:8002; local proxies on 133
- **Voice Bot** — the live ASR voice bot on 53 (`/home/saber/asr-bot-test/bot.py`)
- **9router** — Docker `decolua/9router:0.5.109`, LAN-only `:20128` (on 133)
- **Prometheus / Grafana shared stack** — the shared observability stack on 133 (some targets
  still reference stale `172.20.1.52` — separate follow-up, not this repo's scope)
