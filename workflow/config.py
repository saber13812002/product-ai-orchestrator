"""
config.py — Central, config-driven configuration for the Multi-Model Product Orchestrator.

Design rule (STEP 2 requirement 2.2):
    NO agent hard-codes a model name. Every agent resolves its model through
    `router.ModelRouter` using a LOGICAL ROLE defined here in MODEL_ROLES.
    Later, when Claude / GPT / DeepSeek / Antigravity / 9Router become available,
    only this file (and optionally .env) changes — the engine is untouched.

STEP 3: AGENT_ROLES now maps every pipeline role to a logical model role.
    * The 3 distinct models used across the pipeline are:
        fast = qwen38-nothinking (vLLM, no thinking)
        deep = qwen38            (vLLM, thinking)
        alt  = qwen38-sglang     (SGLang engine)
      -> 3 different LiteLLM models, satisfying ">= 3 different models".
    * The Second Critic is deliberately on a DIFFERENT role than the (first)
      Critic (fast vs deep) per the STEP 10 requirement.
"""
from __future__ import annotations

import os
from pathlib import Path

# --------------------------------------------------------------------------- #
# Logical role -> real LiteLLM model name
# --------------------------------------------------------------------------- #
# The models this pipeline routes to, by logical role. The defaults are the
# reference fleet (Qwen3.8-27B served through LiteLLM); override ANY of them via
# env (AGENT_MODEL_FAST / _DEEP / _ALT / _STUB) when deploying to a different
# fleet — no code change needed. "stub" is a deterministic mock used only to
# prove routing, never mixed into "real" token totals (see STUB_MODELS).
MODEL_ROLES: dict[str, str] = {
    "fast": os.getenv("AGENT_MODEL_FAST", "qwen38-nothinking"),  # high volume, structured, no thinking
    "deep": os.getenv("AGENT_MODEL_DEEP", "qwen38"),            # deep reasoning (thinking ON)
    "alt":  os.getenv("AGENT_MODEL_ALT", "qwen38-sglang"),      # alt engine (thinking ON)
    "stub": os.getenv("AGENT_MODEL_STUB", "mock-agent-v1"),     # deterministic routing stub
}

# Models whose token usage must NOT be mixed into "real" token totals.
STUB_MODELS: set[str] = {"mock-agent-v1"}

# --------------------------------------------------------------------------- #
# LiteLLM endpoint (single gateway for ALL model calls) — STEP 9
#
# All model calls go through ONE LiteLLM endpoint. Two deployment modes,
# resolved in ONE place (no scattered hard-codes):
#   * Mode A — EXTERNAL (default): the gateway is not run by this repo. Point
#     LITELLM_BASE_URL at your own gateway (env) and supply LITELLM_API_KEY.
#     No hardcoded key or server URL on purpose (the old in-tree defaults were
#     a credential leak and a fleet-specific address).
#   * Mode B — BUNDLED: the repo's own LiteLLM sidecar (compose profile
#     `bundled-litellm`) serves the gateway; the AgentOS container reaches it
#     at http://litellm:4000/v1 over the compose network, authenticating with
#     the sidecar's master key (LITELLM_MASTER_KEY).
# Legacy OPENAI_* names stay honored as an external-mode fallback so existing
# deployments that were never updated keep working unchanged.
#
# `resolve_endpoint()` is the single source of truth for (base_url, api_key);
# `personal_agent.py` and `models.py`/`router.py` all consume its result, so a
# mode switch is a .env change, never a code change.
# --------------------------------------------------------------------------- #
# Where the bundled sidecar lives from the AgentOS container's point of view
# (service name + port of the `litellm` compose service). Overridable for
# non-compose deployments of the two containers.
BUNDLED_LITELLM_URL: str = os.getenv("LITELLM_BUNDLED_URL", "http://litellm:4000/v1")
LITELLM_MODE: str = os.getenv("LITELLM_MODE", "external").strip().lower()


def resolve_endpoint(mode: Optional[str] = None) -> tuple[str, str]:
    """Resolve the (base_url, api_key) every model call goes through.

    The ONLY place mode selection happens (STEP 9.6) — agents, the model
    factory and the router all consume the result, never the raw env vars:
      * mode `bundled`  -> BUNDLED_LITELLM_URL (default http://litellm:4000/v1,
        the compose service name) + LITELLM_MASTER_KEY.
      * mode `external` (default) -> LITELLM_BASE_URL + LITELLM_API_KEY, with
        the legacy OPENAI_* names as fallback (unchanged for existing deployments).

    `mode` defaults to the LITELLM_MODE env value; tests pass it explicitly so
    both modes are verifiable hermetically (the mode is otherwise read once at
    import, like every other config value).
    """
    mode = (mode or LITELLM_MODE or "external").strip().lower()
    if mode == "bundled":
        base_url = os.getenv("LITELLM_BUNDLED_URL", BUNDLED_LITELLM_URL)
        api_key = os.getenv("LITELLM_MASTER_KEY", "")
    else:
        base_url = os.getenv("LITELLM_BASE_URL", os.getenv("OPENAI_BASE_URL", ""))
        api_key = os.getenv("LITELLM_API_KEY", os.getenv("OPENAI_API_KEY", ""))
    # Normalization aid (warn, don't fail): our contract is a /v1 base URL.
    if base_url and not base_url.rstrip("/").endswith("/v1"):
        import warnings
        warnings.warn(
            f"LITELLM endpoint {base_url!r} does not end with /v1 — the "
            "orchestrator expects an OpenAI-compatible /v1 base URL."
        )
    return base_url, api_key


# Module-level resolution: the existing names stay (models.py/router.py consume
# them), but their VALUES now come from the resolver, so external mode behaves
# exactly as before and bundled mode points at the sidecar.
LITELLM_BASE_URL: str
LITELLM_API_KEY: str
LITELLM_BASE_URL, LITELLM_API_KEY = resolve_endpoint()
LITELLM_ROUTE_LABEL: str = "litellm"  # every call is routed through LiteLLM

# --------------------------------------------------------------------------- #
# Storage
# --------------------------------------------------------------------------- #
WORKFLOW_HOME: Path = Path(__file__).resolve().parent
RUNS_DIR: Path = os.getenv("WORKFLOW_RUNS_DIR", str(WORKFLOW_HOME / "storage" / "runs"))

# --------------------------------------------------------------------------- #
# Role mapping per pipeline agent (STEP 3)
#
# Budget-aware routing (learned from the first live run): the "deep" and "alt"
# models run with THINKING ON, so they spend a large share of their output cap
# on reasoning tokens before any visible content is produced. A big structured
# output (e.g. the 13-section master prompt) therefore gets truncated if it is
# routed to a thinking model with a small cap.
#
#   * Big / high-volume / reliability-critical structured steps -> "fast"
#     (qwen38-nothinking): every output token is real content, JSON is complete.
#   * Genuine deep-reasoning steps (critic, final reviewer) -> "deep", with a
#     roomier cap so thinking + content both fit.
#   * The Refiner + one alt task -> "alt" (SGLang engine) to demonstrate the
#     third engine; given a generous cap so SGLang's thinking has room.
# --------------------------------------------------------------------------- #
AGENT_ROLES: dict[str, str] = {
    "product_analyst":       "fast",   # STEP 1 — small structured JSON
    "master_prompt_builder": "fast",   # STEP 2 — big JSON; nothinking keeps it complete
    "manager":               "fast",   # STEP 3 (task decomposition)
    "task_executor":         "fast",   # STEP 4 (default; per-task override below)
    "design_merger":         "fast",   # STEP 5
    "critic":                "fast",   # STEP 6 — checklist critic; nothinking = token-frugal
    "fix_prompt_generator":  "fast",   # STEP 7
    "refiner":               "fast",   # STEP 8 — mechanical patch applier; nothinking so
                                       #   every token is content (SGLang/alt over-thinks
                                       #   and truncates the patch list). SGLang is still
                                       #   exercised via TASK-05, so the 3-model rule holds.
    "rebuilder":             "fast",   # STEP 9
    "patch_verifier":        "fast",   # STEP 4.6 — checks each patch vs acceptance criteria
    # STEP 4.9 — evidence-based reroute. The second critic and the final
    # reviewer both need STRUCTURED JSON (CriticResult / FinalReview) over the
    # FULL design. Live probing in this fleet showed the THINKING qwen38 variants
    # (deep=qwen38, alt=qwen38-sglang) cannot emit that JSON: they burn their
    # entire output budget on reasoning and return no content (deep@8000 and
    # alt@4200 both -> None, 148s / 59s). Only fast=qwen38-nothinking reliably
    # emits complete structured JSON (every fast call in the pipeline does). So
    # both judges run on fast. The >=3-models rule still holds (deep= TASK-01,
    # alt = TASK-05, fast = the rest); the engine is untouched, only routing.
    "second_critic":         "fast",   # STEP 10 — reliable structured critic (see above)
    "quality_gate":          "fast",   # STEP 11
    "final_reviewer":        "fast",   # STEP 12 — reliable structured reviewer (see above)
    "final_output":          "fast",   # STEP 13 — big JSON; nothinking keeps it complete
}

# Per-task model assignment for STEP 4. This is AUTHORITATIVE (config-driven
# routing — the decomposer's own `assigned_model` field is only a fallback for a
# task_id not listed here). Keeping exactly ONE deep task + ONE alt task and the
# rest on the token-cheap nothinking `fast` is what makes a 20k test run fit,
# while still exercising all 3 live models.
TASK_MODEL_HINTS: dict[str, str] = {
    "TASK-01": "deep",   # Product Architecture — one deep-reasoning task
    "TASK-02": "fast",   # Backend Architecture
    "TASK-03": "fast",   # Database Design
    "TASK-04": "fast",   # API Design
    "TASK-05": "alt",    # UI/UX Design — one SGLang-engine task (3rd model)
    "TASK-06": "fast",   # Security
    "TASK-07": "fast",   # Test Plan
    "TASK-08": "fast",   # Infrastructure
    "TASK-09": "fast",   # Review
}

# --------------------------------------------------------------------------- #
# Budget & quality gate
# --------------------------------------------------------------------------- #
# The run() entrypoint selects TEST_MODE or full mode. Knobs below are the
# TEST-MODE defaults (first execution). Full mode raises these.
# TEST_MODE is the default mode for Engine() when test_mode isn't passed in.
TEST_MODE: bool = True
TEST_TOKEN_BUDGET: int = 20000
TEST_MAX_ITERATIONS: int = 2
TEST_MIN_MODELS: int = 3

FULL_TOKEN_BUDGET: int = 100000
# STEP 4.9 — iterations are a BUDGET knob, NOT a quality bar (the 85 threshold
# below is unchanged). Measured: one full quality-loop iteration (critic +
# fixgen + refiner + rebuild + verifier + 2nd-critic + gate) re-reads the
# (growing) full design ~5x, so it costs ~32-34k tokens. 3 iterations therefore
# overshoot the 100k budget and die before the final review/output (observed:
# 101,516 tokens, budget_exhausted at ITER3 verify). 2 iterations + a bounded
# cross-check fits ~90k, leaving room for the final reviewer + 17-section output
# to always complete and report honestly.
FULL_MAX_ITERATIONS: int = 2

GATE_THRESHOLD: int = 85

# Reserve held back from the budget so the final-output step can always start.
BUDGET_RESERVE: int = 500

# --------------------------------------------------------------------------- #
# STEP 4 — Quality Rubric (single source of truth, shared by Critic, Gate and
# Final Reviewer). `final_score` is COMPUTED as the weighted mean of these
# dimension scores (weights must sum to 1.0) — it is never a free LLM number.
# The suggested weighting from the STEP 4 brief is used verbatim (sums to 1.0):
#   Security + Architecture are weighted highest (15% each) because this is a
#   multi-tenant SaaS where tenant isolation and structural soundness dominate;
#   the delivery dimensions (backend/db/api/testing/deployment) are 10% each;
#   the polish dimensions (observability/product/ui/consistency) are 5% each.
# --------------------------------------------------------------------------- #
QUALITY_WEIGHTS: dict[str, float] = {
    "architecture_score": 0.15,
    "backend_score":      0.10,
    "database_score":     0.10,
    "api_score":          0.10,
    "security_score":     0.15,
    "testing_score":      0.10,
    "deployment_score":   0.10,
    "observability_score": 0.05,
    "product_score":      0.05,
    "ui_score":           0.05,
    "consistency_score":  0.05,
}

# The 11 scored dimensions (order is cosmetic; keys must match QUALITY_WEIGHTS).
QUALITY_DIMENSIONS: list[str] = [
    "architecture_score", "backend_score", "database_score", "api_score",
    "security_score", "testing_score", "deployment_score", "observability_score",
    "product_score", "ui_score", "consistency_score",
]

# A critic issue is "actionable" (the fix loop chases it) only at these
# severities. MEDIUM/LOW are recorded but not turned into fixes, so each
# iteration closes real defects instead of re-chasing 8 broad nits (the
# baseline treadmill). Cap on how many issues the critic may report.
ACTIONABLE_SEVERITIES: tuple[str, ...] = ("BLOCKER", "HIGH")
MAX_CRITIC_ISSUES: int = 5

# STEP 4.2 — the Quality Gate (and critics) review the FULL design. The design
# in this fleet is ~2.8k tokens, far inside the Qwen3-27B window (~32k). This
# guard is the ceiling we refuse to exceed before we fall back to a
# prioritized (important-sections-first) view rather than a blind truncation.
QWEN3_MODEL_CONTEXT_WINDOW: int = 32768
GATE_MAX_INPUT_TOKENS: int = 24000          # ~0.73 of the window
CHARS_PER_TOKEN: float = 4.0                # measured ~4.4 for `fast` (conservative)

# STEP 4.9 — the SECOND critic is a cross-check, not the authoritative scorer
# (the full-context Quality Gate below is what scores and drives the loop). It
# re-reads the whole design every iteration, which is the single biggest avoidable
# input cost. Bounding its view (section-aware, important sections first — never
# a blind head-truncation, per 4.2) to ~15k chars (~3.7k tokens) cuts the loop's
# re-reading cost materially without compromising the gate, which still sees the
# FULL design.
SECOND_CRITIC_MAX_INPUT_TOKENS: int = 4000

# --------------------------------------------------------------------------- #
# Per-step MAX COMPLETION TOKENS (output caps), per MODE.
#   * TEST profile (20k budget): frugal — keeps a single quality-gate iteration
#     within budget so the budget-enforcement smoke test can complete.
#   * FULL profile (100k budget): roomy — substantive design drafts + a full
#     17-section finale, and headroom for the loop to run 2-3 iterations.
# The Engine selects the profile from its test_mode flag.
#
# STEP 4 (rebuild cap): the baseline run hit output_tokens==2600 on EVERY rebuild
# (the design grew to ~12.5k chars ≈ 2,850 tokens, larger than its own cap) and
# truncated the tail every iteration. The rebuild must emit the FULL design, so
# its cap must exceed the design's token size. Raised 2600 -> 5000 (~22k chars)
# so no rebuild can truncate a ~2.8k-token design.
# --------------------------------------------------------------------------- #
STEP_MAX_OUTPUT_TEST: dict[str, int] = {
    "product_analysis": 700,
    "master_prompt": 2200,
    "task_decomposition": 1800,
    "task_exec": 300,
    "merge": 1400,
    "critic": 2200,
    "second_critic": 3000,
    "fixgen": 600,
    "refine": 1500,
    "rebuild": 3000,
    "verify": 700,
    "gate": 500,
    "final_review": 1800,
    "final_output": 2400,
}
STEP_MAX_OUTPUT_FULL: dict[str, int] = {
    "product_analysis": 900,
    "master_prompt": 3200,
    "task_decomposition": 2400,
    "task_exec": 600,
    # The initial merge was capped at 2600 in the live run (out=2600, exactly its
    # cap) — the design v1 it produced (~2.8k tokens) was not given room to be
    # comprehensive. 4000 (~18k chars) lets the FULL-mode merge emit a complete
    # design so the Quality Gate reviews a whole, not a capped, draft.
    "merge": 4000,
    "critic": 2600,
    # STEP 4.9 fix — the second critic runs on `deep` (qwen38, THINKING ON).
    # For a thinking model the output cap must hold BOTH its reasoning tokens
    # (~1400-1800) AND the JSON it must emit. Sharing the fast first-critic's
    # 2600 left it ~2600 tokens of pure reasoning and NO content (out=2600,
    # Raw output NoneType -> run failed at ITER1_STEP10). 4200 = ~1800 thinking
    # + ~2400 for the targeted-issue JSON (larger than the first critic's needs
    # since it must re-list every remaining issue after a fix pass).
    "second_critic": 4200,
    "fixgen": 900,
    "refine": 2400,
    "rebuild": 5000,
    "verify": 900,
    "gate": 800,
    # Final reviewer is `deep` (thinking) over the FULL design; its FinalReview
    # JSON is small but reasoning over the whole design needs headroom. 4000
    # keeps thinking + verdict from colliding with the output cap.
    "final_review": 4000,
    "final_output": 4500,
}
# Alias for any direct reader; the Engine uses _profile() to pick per mode.
STEP_MAX_OUTPUT: dict[str, int] = STEP_MAX_OUTPUT_TEST
DEFAULT_MAX_OUTPUT: int = 1000

# Cap on how many CHARS of prior design context is re-sent to a loop step.
# Re-sending the full design to every loop step is the biggest INPUT cost, so it
# is truncated in the loop. The FINAL review + FINAL output always get the full
# design (they must judge/emit the whole thing). Mode-aware: FULL mode is roomy.
CONTEXT_RESEND_CHARS_TEST: int = 1200
CONTEXT_RESEND_CHARS_FULL: int = 4000
# Per-task excerpt length sent to the Merger (full task output is kept in state).
MERGE_TASK_EXCERPT_CHARS_TEST: int = 400
MERGE_TASK_EXCERPT_CHARS_FULL: int = 900

# --------------------------------------------------------------------------- #
# The 13 master-prompt sections (STEP 2) and 17 final-output sections (STEP 13)
# --------------------------------------------------------------------------- #
MASTER_PROMPT_SECTIONS: list[str] = [
    "product_architecture", "backend_architecture", "frontend_architecture",
    "ui_ux_architecture", "database", "api", "authn_authz", "security",
    "observability", "testing_strategy", "deployment", "scalability",
    "failure_scenarios",
]

FINAL_OUTPUT_SECTIONS: list[str] = [
    "product_specification", "system_architecture", "component_architecture",
    "ui_architecture", "backend_architecture", "database_schema",
    "erd_description", "api_specification", "authentication", "authorization",
    "security", "test_strategy", "infrastructure", "deployment", "monitoring",
    "risks", "open_questions",
]

# --------------------------------------------------------------------------- #
# STEP 5 — Design Enrichment
#
# A NEW layer that runs AFTER the design is finalized (after the quality-gate
# loop + final review) and turns the single overall design into 8 DEEP,
# specialized technical documents a dev team can build from. It does NOT touch
# steps 1-13 (the existing 13-step pipeline is preserved verbatim); it consumes
# the best design version (s.design_versions[-1]) and the final output.
#
#   Design vX -> [8 Enrichment Agents] -> Technical Documents
#             -> Document Manager (writes /documents/{run_id}/*.md)
#             -> Document-Completeness Quality Gate (per-doc + overall)
#
# BUDGET (5.8): no new model, no new provider — all 8 agents run on `fast`
# (qwen38-nothinking). STEP 4 proved the thinking models cannot emit complete
# structured JSON over a large design, and these agents must emit a large
# structured TechnicalDocument. Priority: document QUALITY > number of design
# iterations — so the enrichment run uses FEWER design-loop iterations to free
# budget for the (token-heavy) document pass, under an explicit, larger budget.
# --------------------------------------------------------------------------- #

# All 8 enrichment agents + the completeness gate run on `fast` (see above: the
# structured-output-safe model in this fleet). The >=3-model rule is already met
# in the design loop (deep=TASK-01, alt=TASK-05) — enrichment adds no new models.
ENRICH_AGENT_ROLES: dict[str, str] = {
    "backend_architect":  "fast",
    "database_architect": "fast",
    "api_architect":      "fast",
    "frontend_architect": "fast",
    "ux_designer":        "fast",
    "security_architect": "fast",
    "test_architect":     "fast",
    "devops_architect":   "fast",
    "document_gate":      "fast",   # the 5.6 document-completeness gate
}

# The 8 enrichment agents, in build order. agent_name -> (document_type, md_file).
# The Document Manager writes these 8 PLUS product.md (from the final product
# spec) and architecture.md (from the final system architecture) = 10 files.
ENRICH_AGENTS: list[dict[str, str]] = [
    {"agent": "backend_architect",  "doc_type": "Backend Design Document",     "file": "backend.md"},
    {"agent": "database_architect", "doc_type": "Database Design Document",    "file": "database.md"},
    {"agent": "api_architect",      "doc_type": "API Specification",           "file": "api.md"},
    {"agent": "frontend_architect", "doc_type": "Frontend/UI Design Document", "file": "frontend.md"},
    {"agent": "ux_designer",        "doc_type": "UX Specification",            "file": "ux.md"},
    {"agent": "security_architect", "doc_type": "Security Document",           "file": "security.md"},
    {"agent": "test_architect",     "doc_type": "Testing Strategy",            "file": "testing.md"},
    {"agent": "devops_architect",   "doc_type": "Deployment Document",         "file": "devops.md"},
]

# Where the rendered document bundle is written (5.4). Under the store root so
# it lives alongside the run's state.json and survives the container.
DOCUMENTS_DIR: Path = os.getenv("WORKFLOW_DOCUMENTS_DIR", str(WORKFLOW_HOME / "storage" / "documents"))

# How many CHARS of the overall design + final output each enrichment agent sees
# as its "source of truth". The design is ~2.8k tokens (~11k chars) and the
# final 17-section output is comparable; each agent needs the whole design to
# write a faithful deep document, so we send the full design + the final output
# (far inside the 32k window). Capped here for safety.
ENRICH_SOURCE_CHARS: int = 30000

# Per-document output caps (FULL mode). Each TechnicalDocument is a large
# structured JSON: an `architecture` body of real depth + decisions + components
# + risks + open_questions + implementation_notes. ~2400-2800 tokens (~10-11k
# chars) is enough for a genuinely actionable document; nothinking emits every
# token as content so it stays complete. The doc gate output is small.
ENRICH_DOC_MAX_OUTPUT: int = 2600
ENRICH_GATE_MAX_OUTPUT: int = 900

# The NEW document-completeness gate (5.6). Each of the 8 documents is scored
# 0-100 on completeness/actionability; the OVERALL is the equal-weighted mean
# (computed by the engine, never a free LLM number) and compared to this
# threshold. Equal weights: the brief asks for a separate per-doc score + an
# overall, without privileging one document over another.
ENRICH_GATE_THRESHOLD: int = 80

# STEP 5 run budget. The design loop (1 iteration, per 5.8 "quality > iterations")
# costs ~40-50k; the 8 documents at ~3-4k input + ~2.6k output each ≈ 50-65k;
# the final output + reviews ≈ 15k. 160k gives comfortable headroom for all of
# it while keeping the ledger honest. (A budget knob — the 85 design-gate and
# 80 doc-gate thresholds are untouched.)
ENRICH_TOKEN_BUDGET: int = 160000
ENRICH_MAX_ITERATIONS: int = 1   # design-loop iterations: free budget for the docs

# --------------------------------------------------------------------------- #
# STEP 8 — Gap-filling "refine" pass (2nd enrichment pass)
#
# The `refine` run mode runs the SAME 13-step pipeline + the SAME first
# enrichment pass, then — BEFORE the run ends — does one targeted 2nd pass that
# re-runs only the enrichment agents the document-completeness gate flagged as
# gapful (DDL / OpenAPI / payment / reporting / UI flows / observability / ...),
# injecting each agent's named gaps + its own v1 document so it FILLS the holes
# instead of rewriting from scratch. The refined documents replace the v1 ones,
# the 10-file bundle is rewritten, and the doc-completeness gate is re-run. This
# is purely additive on top of `enrich` and never touches the 13-step primary
# pipeline. Measured live: pass-1 overall 79; the refine pass targets 85+.
# --------------------------------------------------------------------------- #

# Run budget for a `refine` run = the enrichment budget (design loop + 1st
# document pass, ~156k) PLUS headroom for the 2nd targeted pass (up to
# REFINE_MAX_AGENTS re-runs, each re-reading the source + emitting a full doc,
# plus one more completeness gate). 210k keeps the ledger honest with room.
REFINE_TOKEN_BUDGET: int = 210000

# How many of the 8 documents the refine pass may re-run, at most. The gate
# names specific gaps, but we also widen the target to the N lowest-scoring
# documents (so a gap the gate describes in prose still reaches its doc).
REFINE_MAX_AGENTS: int = 3

# Characters of the targeted agent's OWN v1 document we feed back to it as the
# "here is what you wrote, fill these holes" context. The v1 architecture body
# is the centerpiece; a few thousand chars is plenty to preserve it and extend.
REFINE_SELF_DOC_CHARS: int = 8000

# Per-gap routing: keyword (lowercase) -> enrichment agent names. A named gap
# from the gate is matched (FIRST match wins, so agents are ordered
# most-specific-first) against these substrings. Keep the terms DISCRIMINATING
# (not bare generic words like "table"/"log"/"service", which cross-match the
# wrong agent). Covers the recurring STEP 5 gaps: DDL (database), exact OpenAPI
# (api), payment/reporting (backend), UI flows (frontend+ux), observability
# (devops+backend), test plans (test), threat model (security), DR/backup
# (devops), caching/queue (backend).
REFINE_GAP_KEYWORDS: dict[str, list[str]] = {
    "database_architect": [
        "ddl", "schema", "migration", "index", "erd", "partition", "constraint",
        "primary key", "foreign key", "table definition",
    ],
    "api_architect": [
        "openapi", "swagger", "endpoint", "api spec", "request/response",
        "payload", "rate limit", "versioning",
    ],
    "frontend_architect": [
        "ui flow", "user flow", "page flow", "component tree", "state management",
        "routing", "responsive",
    ],
    "ux_designer": [
        "wireframe", "user journey", "persona", "empty state", "error state",
        "interaction", "usability",
    ],
    "test_architect": [
        "test case", "test plan", "e2e", "unit test", "integration test",
        "acceptance criterion", "test coverage",
    ],
    "devops_architect": [
        "observability", "monitoring", "logging", "alerting", "tracing",
        "disaster recovery", "rollback", "backup",
    ],
    "security_architect": [
        "threat model", "owasp", "authz", "authn", "secret management",
        "audit log", "encryption", "rbac", "vulnerability",
    ],
    "backend_architect": [
        "payment", "billing", "reporting", "queue", "worker", "caching",
        "service boundary", "domain model", "error handling",
    ],
}

# Refine-pass per-document output cap: slightly larger than the first pass so
# a gap-fill (e.g. a real DDL block or a 6-endpoint OpenAPI table) has room to
# add substance without being truncated mid-document.
REFINE_DOC_MAX_OUTPUT: int = 3000

