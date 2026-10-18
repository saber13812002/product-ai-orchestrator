# Health Checks

**Standard:** a health check for every service — AgentOS, LiteLLM, model backend,
database/storage, API, worker, (STEP 10) k8s pod. Health must not be only "process alive";
where feasible it probes key dependencies.

## Current state (STEP 9.6)

| Service | Endpoint | What it actually checks | Gap |
|---|---|---|---|
| **AgentOS** | `GET :7777/health` | Agno/AgentOS built-in — **process alive** (server responds) | Does **not** probe the LiteLLM gateway or the SQLite DB. |
| **LiteLLM (bundled sidecar)** | `GET :4000/health/liveliness` | LiteLLM built-in — **process alive**; model backends are validated **lazily on first call** | Liveliness ≠ readiness; a dead model backend still reports alive until called. |
| **Model backends (53:8000/8001)** | — | No health check from the orchestrator side | Not probed at all; a down backend only surfaces as a failed call. |
| **DB / storage** | — | None | SQLite file at `/data/agent.db` is not probed for writability. |
| **`scripts/healthcheck.sh`** | — | `docker compose ps` + `curl /health` + a routing print | A good **operator** check; still leans on process-alive `/health`. |

## The target

Split into **liveness** vs **readiness** (what k8s probes will call in STEP 10):

- **Liveness** — "is the process up?" → keep AgentOS `/health` / LiteLLM `/health/liveliness`.
- **Readiness** — "can it actually do work?" → add a `/ready` on AgentOS that checks:
  - the resolved LiteLLM endpoint is **reachable** (`resolve_endpoint()` base URL answers);
  - the DB file / storage dir is **writable** (`/data`);
  - (optional) one model role resolves to a name the gateway serves.
- **Dependency-aware `/health`** — for operators, `healthcheck.sh` should call `/ready`, not
  just `/health`.
- **Helm (STEP 10):** `livenessProbe` → `/health`, `readinessProbe` → `/ready`,
  `startupProbe` for the slow AgentOS boot.

See `docs/OBSERVABILITY.md` §5.
