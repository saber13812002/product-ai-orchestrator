# AI HANDOFF — pick up where this left off

> **Read this first if you are an AI (or a new human) taking over the project.** It is a
> single-page snapshot of the current state: what the project is, where it lives, what
> version it is, what's done (STEPS 1–9), what's open, and what STEP 10 is.

_Last updated: 2026-10-10 · Latest release: **v0.3.0** · Test suite: **30 tests** (hermetic) · CI chain: **green** (runner #1)._

## 1. What this is

The **AI Product Orchestrator**: a multi-agent, **multi-model** pipeline built on
[Agno AgentOS](https://github.com/agno-agi/agno). Give it a product **brief**; it runs a scored
**13-step design pipeline** → a **17-section system design**, then an **enrichment layer** →
**8 deep technical documents**, then a **gap-filling refine pass** that closes the specific
completeness gaps the document gate names (DDL, OpenAPI, payment/reporting, observability, UI
flows). Every LLM call goes through **one LiteLLM gateway**, and the whole thing deploys with
**Docker Compose** in two modes (External gateway, or a Bundled sidecar).

## 2. Where it lives

| Thing | Location |
|---|---|
| **Git repo** | `https://git.ai.ismc.ir/common/website/ai-product-orchestrator` (internal GitLab CE on server 52; git over `http://172.20.1.52:81`). Private. |
| **Laptop working tree** | `C:\Users\s.tabatabaei\Documents\saberprojects\server52and53\ai-product-orchestrator` |
| **Deploy target (52)** | `/home/saber/saberprojects/ai-product-orchestrator` — container `agno-agentos-repo`, port **7779** (the CI deploy target). |
| **Production (52)** | `/home/saber/agentos/` — container `agno-agentos`, port **7777**. **NOT managed by this repo — never touch it.** |
| **Per-step reports (laptop)** | `server52and53/STEP*_REPORT.md` (one level up) |

### The model-fleet servers

| Server | What it runs | Reach |
|---|---|---|
| **52** (172.20.1.52) | GitLab, CI runners, the production + deploy AgentOS instances, and the **external LiteLLM gateway** (`:4000`). | SSH alias `s52` from the laptop. |
| **53** (172.20.1.53) | The **Qwen3.8-27B model backends**: vLLM `:8000` (nothinking), vLLM `:8001` (sglang). These are what the external gateway and the bundled sidecar route to. | Via 52 (jump). |
| **117** | Unrelated AI services (BGE-M3 embeddings, Whisper) — **not** used by this orchestrator. | — |

## 3. Version & state

- **Latest release:** **v0.3.0** (Semantic Versioning — see [RELEASES.md](RELEASES.md)).
- **Package version** (`pyproject.toml`): `0.3.0` (the **git tag** is canonical).
- **Test suite:** **30 hermetic tests** (was 21 in v0.2.0; STEP 9 added 9 in
  `workflow/tests/test_endpoint.py`). No LLM, no network, no API key — this is what CI runs.
- **CI:** GitLab pipeline on the root `server52` runner (**`AI-TOOLS`, runner #1**) — hermetic
  tests → deploy `main` to 7779. **Green** (verified 2026-10-10). The broken user-mode runner
  `aio-server52` (#5) was **stopped + deactivated** (see §7) so it can no longer steal jobs.

## 4. Architecture (one paragraph)

`personal_agent.py` boots the AgentOS HTTP service (`:7777`). `workflow/run.py` is the CLI
(`smoke` / `routing` / `full` / `enrich` / `refine` / `endpoint`). The **Manager** agent decomposes
a brief into a 13-step pipeline run by `workflow/engine.py`; a **ModelRouter** maps a logical
role (`fast`/`deep`/`alt`/`stub`) to a real LiteLLM model name and records an honest token
ledger. After the design is finalized, 8 **enrichment agents** write deep documents, a
deterministic **Document Manager** assembles the 10-file bundle, and a **document-completeness
gate** scores them; the **refine pass** re-runs only the gapful documents. Full detail:
[ARCHITECTURE.md](ARCHITECTURE.md).

### Model routing (the portability core)

| Role | Default model | Thinking | Used for |
|---|---|---|---|
| `fast` | `qwen38-nothinking` | **OFF** | All structured steps (analyst, master prompt, decomposition, judges, 8 enrichment docs). **Must** reliably emit complete JSON. |
| `deep` | `qwen38` | ON | Free-text tasks (TASK-01, TASK-05) — satisfies "≥3 models". |
| `alt` | `qwen38-sglang` | ON | A second/third engine, free-text tasks. |
| `stub` | `mock-agent-v1` | — | Deterministic routing proof only; never in real totals. |

The **thinking models cannot emit structured JSON** over a large design (they spend their whole
output budget reasoning) — so all structured/judge work runs on `fast`. That's why
`workflow/config.py::TASK_MODEL_HINTS` (TASK-01→`deep`, TASK-05→`alt`) is authoritative.

### LiteLLM deployment modes (STEP 9)

One resolver — `workflow/config.py::resolve_endpoint()` — returns `(base_url, api_key)` for the
active mode; everything consumes that.

- **Mode A — External (default):** you run a LiteLLM gateway; `.env` sets `LITELLM_BASE_URL` +
  `LITELLM_API_KEY`; start with `docker compose up -d`. Legacy `OPENAI_*` names remain a fallback.
- **Mode B — Bundled sidecar:** no gateway on the server; `LITELLM_MODE=bundled` +
  `LITELLM_MASTER_KEY` + `*_MODEL_API_*` backends; start with
  `docker compose --profile bundled-litellm up -d`. The repo starts its own LiteLLM sidecar
  (`litellm/`), health-gated. **The sidecar is strictly optional** — `docker compose up -d`
  never starts it.

Full details: [LITELLM.md](LITELLM.md).

## 5. STEPS 1–10 (what's done)

| Step | What | Status |
|---|---|---|
| **1–3** | 13-step pipeline, multi-model routing, quality loop | ✅ |
| **4** | Quality-loop fix — full-context gate, computed weighted score, targeted critic, atomic fixes, patch verifier, shared rubric. Rerouted judges to `fast` (thinking models can't do structured JSON). | ✅ |
| **5** | Design enrichment — 8 deep docs + deterministic Document Manager (10 files + traceability) + document-completeness gate. | ✅ |
| **6** | Portable Docker-Compose repo; master key scrubbed to env-only. | ✅ |
| **7** | CI/CD on the `server52` runner (test → deploy); `clone_url` gotcha fixed; first green pipeline #81. Released **v0.1.0**. | ✅ |
| **8** | Gap-filling **refine pass** (`workflow.run refine`) — targeted 2nd pass re-runs only the gate's gapful docs. Live 74→82. Released **v0.2.0**. | ✅ |
| **9** | **LiteLLM deployment modes** — External (default) + Bundled sidecar; single `resolve_endpoint()`; sidecar `litellm/` with an env-rendering entrypoint (the official image doesn't expand `${VAR}` in a mounted config); health-gated startup; `workflow.run endpoint` CLI; 9 new tests (suite 30). Released **v0.3.0**. | ✅ |
| **9.5** | **CI runner repair** — the user-mode runner `aio-server52` (#5) failed every job at `prepare environment: exit status 1` and was stealing (load-balancing) jobs away from the healthy root runner #1, leaving the pipeline red and 7779 stuck on v0.2.0. Stopped #5 + deactivated it in GitLab (`active=false`); all `server52` jobs now run on #1. Real green pipeline for `main` @ v0.3.0 → 7779 auto-deployed to v0.3.0. | ✅ (this session) |

## 6. Latest tests & verification (STEP 9)

- **Hermetic CI:** 30 passed, no regression.
- **Compose valid for both profiles:** default → `[agno-agentos]`; `--profile bundled-litellm` →
  `[litellm, agno-agentos]`.
- **Live matrix (all on 52, isolated compose project `-p aio9test`/`-p aio9ext` — 7777/7779
  never touched):**
  - **A — External:** real smoke via the 52 gateway `:4000`, 441 tok, no sidecar.
  - **B — Bundled, side-by-side:** both `agno-agentos` + `litellm-sidecar` `healthy`;
    `endpoint` → `bundled` / `http://litellm:4000/v1`.
  - **C — Routing:** `fast`/`deep`/`alt` resolve; the sidecar serves
    `qwen38-nothinking` / `qwen38` / `qwen38-sglang`.
  - **D — Real agent call:** Manager → Product Analyst (fast) → **Sidecar** → raw vLLM 53:8000 →
    structured `ProductAnalysis`, 497 tok, status `completed`. **Fully self-contained**
    (sidecar → local model, no external gateway/key) — proves the sidecar is a turnkey gateway.

## 7. Open problems / watch items

- **Score ceiling ~74** on the 11-dimension design gate: the heavy dimensions are maxed, a
  5%-weight tail drags the mean. Lifting it needs a **stronger model**, not another loop
  iteration (see STEP 4 diagnosis).
- **Document completeness ~82** after the refine pass (target 85+); the refine pass gets there
  on most briefs but the tail is model-bound.
- **CI deploys `main` to 7779** on every push. The deploy target's `.env` is guarded by
  `scripts/deploy-repo.sh` (backed up / restored across redeploys), but a fresh push recreates the
  container — that's intended and fine; just be aware 7779 briefly restarts.
- **52 disk** was a watch item (~74%); the GitLab log bleed (~0.3–0.6 GB/day, no rotation) is
  still worth rotating. See the sibling memory `server52-disk-state`.

## 8. Next — STEP 10 (Helm / Kubernetes)

Package the orchestrator (and its optional bundled-LiteLLM sidecar) as a **Helm chart** so it can
be deployed to a Kubernetes cluster instead of / alongside a single Docker-Compose host. Likely
surface:

- A chart with the AgentOS deployment + optional `litellm` sidecar (mirroring the two modes).
- `ConfigMap`/`Secret` for the `.env` values (mode, endpoint, model names, master key).
- `Service`/`Ingress` for `:7777` (AgentOS) and, in bundled mode, the sidecar (keep loopback/
  internal-only).
- A `PVC` for `/data` (AgentOS state) and, if bundled, `litellm-data`.
- Reuse the existing `Dockerfile` image (no code change expected — this is a packaging step).

Confirm the target cluster + registry before starting STEP 10.

## 9. Where to read next

- **[LITELLM.md](LITELLM.md)** — the two deployment modes in depth.
- **[ARCHITECTURE.md](ARCHITECTURE.md)** — components, the 13-step pipeline, quality loop,
  enrichment, refine pass, routing.
- **[DEPLOYMENT.md](DEPLOYMENT.md)** — end-to-end install for both scenarios.
- **[CONFIGURATION.md](CONFIGURATION.md)** — the full environment-variable reference.
- **[AGENTS.md](../AGENTS.md)** — commands, CI/CD gotchas, hard rules.
- **[RELEASES.md](RELEASES.md)** — changelog + how to cut a release.

## 10. Hard rules (carry these into every change)

1. **No secrets in the repo.** `.env` is gitignored; only `.env.example` is tracked. The LiteLLM
   master key is a live credential — never print or commit it.
2. **CI stays hermetic.** No test may need network/LLM/keys.
3. **Structured output only from `fast`.**
4. **LF line endings** (`.gitattributes`).
5. **Commits end with** `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.
6. **Never recreate the production (7777) or deploy-target (7779) instances in tests** — use a
   separate compose **project** (`docker compose -p myproj ...`), not just a different
   `container_name`/port.
