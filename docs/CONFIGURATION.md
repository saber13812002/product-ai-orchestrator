# Configuration

All configuration is **environment-driven**. There are no secrets and no server-specific
addresses baked into the code — the repo ships defaults that are safe to run from, and every
real value comes from `.env`.

## Environment variables

The single source of truth for the container is your `.env` (see
[`.env.example`](../.env.example)). The variables the application actually reads:

| Variable | Required | Default | Meaning |
|---|---|---|---|
| `LITELLM_BASE_URL` | ✅ | *(empty — you must set it)* | Base URL of your LiteLLM gateway, e.g. `http://172.20.1.52:4000/v1`. |
| `LITELLM_API_KEY` | ✅ | *(empty)* | The LiteLLM master / virtual key. **Never commit it.** |
| `AGENT_MODEL_FAST` | ⬜ | `qwen38-nothinking` | Logical `fast` role — high-volume, structured, **no thinking**. Must reliably emit complete structured JSON. |
| `AGENT_MODEL_DEEP` | ⬜ | `qwen38` | Logical `deep` role — deep reasoning (**thinking ON**). |
| `AGENT_MODEL_ALT` | ⬜ | `qwen38-sglang` | Logical `alt` role — a second/third engine. |
| `AGENT_MODEL_STUB` | ⬜ | `mock-agent-v1` | Deterministic stub used only to prove routing. |
| `PORT` | ⬜ | `7777` | Host port the HTTP API is published on. |
| `DATABASE_URL` | ⬜ | *(runtime default `/data`)* | Reserved for a storage override; the AgentOS SQLite store defaults to the volume. |

### Legacy aliases

`OPENAI_BASE_URL` and `OPENAI_API_KEY` are still honored as a **fallback** (the config reads
`LITELLM_*` first, then `OPENAI_*`). The `docker-compose.yml` also derives the AgentOS
personal-agent variables from the canonical ones, so a single `.env` drives both the HTTP API
and the pipeline:

```
OPENAI_BASE_URL  <- LITELLM_BASE_URL
OPENAI_API_KEY   <- LITELLM_API_KEY
AGENT_MODEL_ID   <- AGENT_MODEL_FAST
```

> **Why the fallbacks exist:** earlier deployments set only the `OPENAI_*` names. New
> deployments should use the `LITELLM_*` / `AGENT_MODEL_*` names — they're clearer.

## In-container storage paths

| Variable | Default (in container) | Notes |
|---|---|---|
| `DATA_DIR` | `/data` | AgentOS SQLite store location. |
| `WORKFLOW_RUNS_DIR` | `/data/runs` | Where `state.json` per run is written. |
| `WORKFLOW_DOCUMENTS_DIR` | `/data/documents` | Where the rendered document bundle is written. |

The compose file sets all three to live under the `/data` named volume so state survives
restarts and image updates. (The code's own default, when run outside the container, is
`workflow/storage/...` next to the package.)

## Pipeline knobs (in `workflow/config.py`)

These are **code-level** defaults, not secrets. Change them in `config.py` if you need to; they
do not affect portability.

| Group | Key knobs |
|---|---|
| **Budgets** | `TEST_TOKEN_BUDGET=20000`, `FULL_TOKEN_BUDGET=100000`, `ENRICH_TOKEN_BUDGET=160000`, `REFINE_TOKEN_BUDGET=210000`, `BUDGET_RESERVE=500`. |
| **Iterations** | `TEST_MAX_ITERATIONS`, `FULL_MAX_ITERATIONS=2`, `ENRICH_MAX_ITERATIONS=1` — budget knobs, not quality bars. |
| **Quality gate** | `GATE_THRESHOLD=85` (design), `ENRICH_GATE_THRESHOLD=80` (documents). |
| **Quality weights** | `QUALITY_WEIGHTS` — 11 dimensions summing to 1.0; the final score is their weighted mean. |
| **Critic** | `MAX_CRITIC_ISSUES=5`, `ACTIONABLE_SEVERITIES=("BLOCKER","HIGH")`. |
| **Per-step output caps** | `STEP_MAX_OUTPUT_TEST` / `STEP_MAX_OUTPUT_FULL` — keep each step within budget. |
| **Enrichment** | `ENRICH_AGENTS` (the 8 agent→doc→file map), `ENRICH_DOC_MAX_OUTPUT`, `ENRICH_SOURCE_CHARS`. |
| **Refine pass (STEP 8)** | `REFINE_TOKEN_BUDGET=210000` (budget for the 2nd gap-filling pass), `REFINE_MAX_AGENTS=3` (how many docs to re-run), `REFINE_SELF_DOC_CHARS=8000` (how much of each agent's v1 doc it feeds back), `REFINE_DOC_MAX_OUTPUT=3000`, `REFINE_GAP_KEYWORDS` (per-gap → agent routing). |

## Choosing your model fleet

The pipeline is model-agnostic; you just need a LiteLLM gateway that serves the model names you
configure. Two properties matter (learned from live runs):

1. **`fast` must be a non-thinking model that reliably returns complete structured JSON.** The
   reference fleet uses `qwen38-nothinking` (thinking disabled). Structured steps (master prompt,
   task decomposition, judges, the 8 enrichment documents) all run here.
2. **`deep`/`alt` may be thinking models** — they're used on free-text tasks (TASK-01, TASK-05)
   to satisfy the "≥3 distinct models" rule. Thinking models burn output budget on reasoning, so
   they are **not** routed to structured-output steps.

To deploy on a totally different fleet, change only the four `AGENT_MODEL_*` values in `.env` —
no code changes. Verify with `docker compose exec agno-agentos uv run python -m workflow.run routing`.

## Security

- **No secrets in the repo.** The only required secret is `LITELLM_API_KEY`, supplied via `.env`,
  which is gitignored. The old version carried a hardcoded default key — that was removed as part
  of packaging.
- **Least privilege:** the container runs as a non-root user (`appuser`, uid 10001).
- **Volume isolation:** all mutable state is in the named volume; the image is read-only.
