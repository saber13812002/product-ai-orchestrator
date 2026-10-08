# Agent Design

The orchestrator has two kinds of participants:

- **Agent classes** (in `workflow/agents/`) — real Python objects with a name, a resolved
  model role, and a method. Used where a discrete, reusable unit of work is needed.
- **Pipeline roles** — logical roles the `Engine` drives directly via its internal `_call()`
  (a role + prompt + structured output schema + token cap). These are the 13-step pipeline and
  the quality loop. They are not separate classes because they're tightly coupled to the engine
  loop; the engine picks the role, prompt, and schema per step.

Every one of them — class or role — talks to the models **only through the `ModelRouter`**, which
resolves the logical role to a real model and records an honest token-ledger entry. No agent
ever names a model.

## Agent classes

### `Manager` (`agents/manager.py`)

The coordinator. In its public `run_smoke()` form (STEP 2) it: creates a run, dispatches the
**Product Analyst**, records the ledger entry, and persists state. In the full pipeline the
orchestration lives in the `Engine` (which internally also does the **task decomposition** as
the Manager role).

### `ProductAnalyst` (`agents/product_analyst.py`)

STEP 1. Input: a raw product brief. Output: a structured `ProductAnalysis` via Agno native
structured output (`output_schema`). Role: `fast`. Prompt: `PRODUCT_ANALYST`.

### `EnrichmentAgent` (`agents/enrichment.py`) — the 8 STEP 5 agents

One class, instantiated 8 times with a different `(agent_name, doc_type, role_prompt)`. Each turns
the finalized design + 17-section deliverable into one structured `TechnicalDocument`. Built by
`build_enrichment_agents()` from `config.ENRICH_AGENTS`. All 8 run on `fast`.

| agent_name | document_type | file |
|---|---|---|
| `backend_architect` | Backend Design Document | `backend.md` |
| `database_architect` | Database Design Document | `database.md` |
| `api_architect` | API Specification | `api.md` |
| `frontend_architect` | Frontend/UI Design Document | `frontend.md` |
| `ux_designer` | UX Specification | `ux.md` |
| `security_architect` | Security Document | `security.md` |
| `test_architect` | Testing Strategy | `testing.md` |
| `devops_architect` | Deployment Document | `devops.md` |

### `DocumentManager` (`agents/document_manager.py`) — deterministic

**No LLM.** Assembles the 8 `TechnicalDocument`s into the 10-file markdown bundle
(`product.md`, `architecture.md` + the 8 agent docs) and writes `TRACEABILITY.md` (every
decision → source + reason). Zero token cost.

## Pipeline roles (driven by the `Engine`)

| Role (config key) | Step | Model role | Output |
|---|---|---|---|
| `product_analyst` | 1 | fast | `ProductAnalysis` |
| `master_prompt_builder` | 2 | fast | 13-section master prompt |
| `manager` (decompose) | 3 | fast | 9 tasks |
| `task_executor` | 4 (×9) | fast (TASK-01=deep, TASK-05=alt) | task deliverable |
| `design_merger` | 5 | fast | merged design draft |
| `critic` | 6 | fast | ≤5 issues w/ severity |
| `fix_prompt_generator` | 7 | fast | atomic fixes + acceptance criteria |
| `refiner` | 8 | fast | targeted patches |
| `rebuilder` | 9 | fast | new versioned design (full) |
| `patch_verifier` | 4.6 | fast | per-fix PASS/FAIL |
| `second_critic` | 10 | fast | bounded cross-check |
| `quality_gate` | 11 | fast | 11-dimension scores (score computed by engine) |
| `final_reviewer` | 12 | fast | APPROVED / APPROVED_WITH_NOTES / REJECTED |
| `final_output` | 13 | fast | 17-section deliverable |
| `document_gate` | 14 (enrich) | fast | per-doc completeness (overall computed) |
| `*architect` / `*designer` | 15 (refine, ×≤3) | fast | **revised** `TechnicalDocument` (gap-filled) |
| `document_gate` | 15 (refine) | fast | per-doc completeness **re-scored** |

The ≥3-models rule is met because TASK-01 runs on `deep` and TASK-05 on `alt`, the rest on `fast`.

### The STEP 8 refine pass

In `refine` mode the eight enrichment agents are **not** all re-run. The engine reads the pass-1
completeness gate and re-runs **only** the targeted agents (≤ `REFINE_MAX_AGENTS`, chosen from the
named gaps + the lowest-scoring docs). Each targeted agent gets `prompts.refine_prompt` (not
`enrich_prompt`): its role + a "revise, don't rewrite" contract + the **named gaps** for its
document, and it receives its **own v1 document** in the input so it extends what's already correct
instead of starting over. The refined `TechnicalDocument`s replace their v1 counterparts, the
deterministic `DocumentManager` rewrites the bundle, and `document_gate` re-scores — so the
overall completeness reflects the filled gaps.

## Structured output

Agents that return structure pass a **Pydantic `output_schema`** to the router, which uses Agno
native structured output. The schemas (in `schemas.py`) are: `ProductAnalysis`, the 13-section
master prompt, the task list, `CriticResult`, the fix list, the patch list, the verification,
`EnrichmentScore`, `FinalReview`, `FinalOutput`, `TechnicalDocument`, and the `WorkflowState`.

> **Why all structured steps run on `fast`:** the thinking models (`deep`/`alt`) in this fleet
> burn their entire output budget on reasoning and return no structured content. `fast`
> (non-thinking) reliably emits complete structured JSON, so every structured-output step is
> routed to it. Free-text tasks still use `deep`/`alt` to exercise all three models.

## The shared quality rubric

The **Critic**, the **Quality Gate**, and the **Final Reviewer** all receive the same
`QUALITY_RUBRIC` (11 weighted dimensions + severity scale), so they grade one standard. The final
score is the **engine-computed weighted mean** of the gate's dimension scores — never a number the
model freely invents. This is what keeps the gate and the reviewer consistent.

## Token ledger

Every `router.call()` returns an `LlmCall` recording the **real model and provider** (read back
from the run's metrics, not the logical role), input/output/reasoning tokens, duration, and a
`is_stub` flag. The engine accumulates these into `state.token_usage`; stubs are excluded from the
"real" token total. This is what makes the per-model budget breakdown in the run summary honest.
