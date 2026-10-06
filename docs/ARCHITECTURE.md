# Architecture

The **AI Product Orchestrator** is a multi-agent, multi-model pipeline that turns a raw
**product brief** into a scored, multi-section **system design**, and (STEP 5) into **eight
deep, specialized technical documents** a development team can build from. It is built on
[Agno AgentOS](https://github.com/agno-agi/agno) and routes every LLM call through a single
**LiteLLM** gateway, so the code is model-agnostic and portable.

> **Deploying on a new server?** Start with [DEPLOYMENT.md](DEPLOYMENT.md).
> **Tuning knobs?** See [CONFIGURATION.md](CONFIGURATION.md).
> **The agents and their prompts?** See [AGENT_DESIGN.md](AGENT_DESIGN.md).

## High-level flow

```
                 User (product brief)
                          │
                          ▼
              ┌───────────────────────┐
              │     AgentOS runtime    │  HTTP API :7777  (health/docs/agents)
              │  + CLI (workflow.run)  │  ─────────────┐
              └────────────┬───────────┘               │
                           ▼                           ▼
              ┌───────────────────────┐      ┌────────────────────┐
              │   Engine (orchestrator)│      │  Manager → Analyst │  smoke flow
              └────────────┬───────────┘      └────────────────────┘
                           ▼
                 ModelRouter (role → real model)
                           │  all calls
                           ▼
                        LiteLLM  ──▶  Models (fast / deep / alt)
                           │
     ┌─────────────────────┴──────────────────────────────────────────┐
     ▼                                                                  ▼
 [13-STEP DESIGN PIPELINE]                              [ENRICHMENT (STEP 5)]
 Analyst → Master Prompt → Decompose → 9 Tasks →        8 Enrichment Agents
 Merge → Critic → Fix → Refine → Rebuild →              (Backend / Database / API /
 Verify → 2nd Critic → Quality Gate →                   Frontend / UX / Security /
 Final Review → 17-section Deliverable                 Testing / Deployment)
                                                        → Document Manager → 10 .md
                                                        → Document-Completeness Gate
```

## Components

| Layer | File(s) | Responsibility |
|---|---|---|
| **HTTP runtime** | `personal_agent.py` | AgentOS app on `:7777` (`/health`, `/docs`, `/agents`). Serves the `personal_agent` (a small assistant bound to the same LiteLLM gateway). |
| **CLI** | `workflow/run.py` | `smoke` / `routing` / `full` / `enrich` subcommands — the way the pipeline is driven. |
| **Orchestrator** | `workflow/engine.py` | The `Engine`: runs the 13-step pipeline + quality loop, then (if `enrich`) the STEP 14 enrichment layer. Enforces the token budget. |
| **Router** | `workflow/router.py` | Maps a **logical role** (`fast`/`deep`/`alt`/`stub`) → a **real LiteLLM model** from `config.MODEL_ROLES`. Runs the call and records an **honest token ledger** (real model + tokens read back from run metrics; stubs flagged, never mixed into "real" totals). |
| **Models** | `workflow/models.py` | Cached factory building Agno `OpenAIChat` objects bound to one LiteLLM model id. |
| **Config** | `workflow/config.py` | Single source of truth: roles→models, budgets, quality weights, per-step output caps, enrichment knobs. |
| **Schemas** | `workflow/schemas.py` | Pydantic models for every structured artifact (`TechnicalDocument`, `EnrichmentScore`, `WorkflowState`, …). |
| **Prompts** | `workflow/prompts.py` | Every role's system prompt + the central `QUALITY_RUBRIC` shared by the three judges. |
| **State** | `workflow/state.py` | `StateStore` (JSON) — persists `state.json` after **every** step under `storage/runs/{run_id}/`. |
| **Agents** | `workflow/agents/` | `Manager`, `ProductAnalyst`, the 8 `EnrichmentAgent`s, and the deterministic `DocumentManager`. |

## The 13-step design pipeline

1. **Product Analyst** — structured understanding of the brief.
2. **Master Prompt Builder** — a 13-section master design prompt.
3. **Manager (decompose)** — splits the master prompt into 9 independent tasks.
4. **Task Execution ×9** — Product/Backend/Database/API/UI-UX/Security/Test/Infra/Review.
5. **Design Merger** — merges the 9 task outputs into one coherent design draft.
6. **Critic** — finds the most blocking problems (≤5, with severity).
7. **Fix Prompt Generator** — one atomic, acceptance-tested fix per BLOCKER/HIGH issue.
8. **Refiner** — applies only those atomic fixes as targeted patches.
9. **Rebuilder** — merges patches into a new versioned design (full design, never truncated).
10. **Patch Verifier** — per-fix PASS/FAIL; a FAIL resends that one patch (max 1 retry).
11. **Second Critic** — a bounded cross-check (different role than the first critic).
12. **Quality Gate** — scores the **full** design on 11 weighted dimensions; `final_score` is
    **computed** (weighted mean), never a free LLM number.
13. **Final Reviewer** — end-to-end review → `APPROVED` / `APPROVED_WITH_NOTES` / `REJECTED`.

A corrective iteration (a bounded number, default 2 in full mode) repeats 6–12 while the gate
is under the threshold **and** budget allows. Then **STEP 13** renders the **17-section final
deliverable**.

### The quality loop (STEP 4)

The gate, the critic and the final reviewer all grade against **one shared `QUALITY_RUBRIC`**,
so they agree. The final score is a **computed weighted mean** of the 11 dimensions (weights in
`config.QUALITY_WEIGHTS`), so a score can't be faked. Key learning encoded in routing: the
**thinking** models cannot emit complete structured JSON over a large design, so all structured
judges run on `fast` (the non-thinking model), while `deep`/`alt` are still exercised on
free-text tasks — keeping the "≥3 models" rule without breaking structured output.

## Enrichment (STEP 5)

Runs **after** the design is finalized (additive — the 13 steps are untouched). Each of the
**8 enrichment agents** takes the finalized design + 17-section deliverable and writes one
deep, structured `TechnicalDocument` (Backend / Database / API / Frontend / UX / Security /
Testing / Deployment). The **deterministic Document Manager** assembles them into a 10-file
markdown bundle (`product.md`, `architecture.md` + the 8 agent docs) plus `TRACEABILITY.md`
(every decision → source + reason). A **document-completeness gate** scores all 8 documents
0–100; the overall is the engine-computed mean, compared to `ENRICH_GATE_THRESHOLD` (80).

## Multi-model routing (the portability core)

No agent ever names a model. It asks the router for a **logical role**; the router resolves it
from `config.MODEL_ROLES`, which is **env-overridable**:

```
fast → AGENT_MODEL_FAST (default qwen38-nothinking)   # high-volume, structured, no thinking
deep → AGENT_MODEL_DEEP (default qwen38)              # deep reasoning (thinking ON)
alt  → AGENT_MODEL_ALT  (default qwen38-sglang)       # alt engine (thinking ON)
stub → AGENT_MODEL_STUB (default mock-agent-v1)       # deterministic routing proof
```

All calls go through the single `LITELLM_BASE_URL`. **Swapping the entire model fleet is a
change to `.env` — no code change.**

## State & data

- Every step persists `state.json` (product analysis, design versions, scores, final review,
  the 8 technical documents, the completeness gate, and the token ledger) under
  `storage/runs/{run_id}/`.
- The rendered document bundle is written to `storage/documents/{run_id}/`.
- In the container, both live under the `/data` named volume (`WORKFLOW_RUNS_DIR` /
  `WORKFLOW_DOCUMENTS_DIR`), so runs survive restarts and updates.
