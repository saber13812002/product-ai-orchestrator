"""
schemas.py — Pydantic models for State, structured agent outputs, and the token ledger.

Two concerns live here:
  1. *Workflow State* (persisted to storage/runs/{run_id}/state.json)
  2. *Structured agent outputs* (e.g. Product Analyst's analysis) used as Agno
     `output_schema` for native structured output.
"""
from __future__ import annotations

from typing import Any, ClassVar, Literal, Optional

from pydantic import BaseModel, Field, model_validator

# =========================================================================== #
# 1. Structured agent outputs
# =========================================================================== #
class ProductAnalysis(BaseModel):
    """STEP 1 — structured output of the Product Analyst agent."""

    product_goal: str = Field(description="The product's core goal in one or two sentences.")
    users: list[str] = Field(description="Primary user personas / roles.")
    use_cases: list[str] = Field(description="Concrete use cases the product must support.")
    features: list[str] = Field(description="Required features.")
    constraints: list[str] = Field(description="Explicit constraints (technical, business, regulatory).")
    ambiguities: list[str] = Field(description="Points in the brief that are ambiguous and need clarification.")
    non_functional_requirements: list[str] = Field(
        description="Non-functional requirements: performance, security, availability, scalability, etc."
    )


class MasterPrompt(BaseModel):
    """STEP 2 — the master design prompt, 13 sections."""

    product_architecture: str = ""
    backend_architecture: str = ""
    frontend_architecture: str = ""
    ui_ux_architecture: str = ""
    database: str = ""
    api: str = ""
    authn_authz: str = ""
    security: str = ""
    observability: str = ""
    testing_strategy: str = ""
    deployment: str = ""
    scalability: str = ""
    failure_scenarios: str = ""


class Task(BaseModel):
    """STEP 3 — one decomposed task."""

    task_id: str = Field(description="e.g. TASK-01")
    objective: str
    context: str
    input: str
    expected_output: str
    assigned_model: str = Field(description="logical role: fast/deep/alt")
    dependencies: list[str] = Field(default_factory=list)
    token_budget: int = 0


class TaskList(BaseModel):
    tasks: list[Task]


class CriticIssue(BaseModel):
    """STEP 4.4 — one targeted, prioritized problem found by the Critic.

    The loop chases only BLOCKER/HIGH (see config.ACTIONABLE_SEVERITIES);
    MEDIUM/LOW are recorded for the reviewer but never spawn a fix, so each
    iteration closes real defects instead of re-chasing 8 broad nits.
    """

    id: str = Field(default="", description="e.g. ISS-01")
    severity: Literal["BLOCKER", "HIGH", "MEDIUM", "LOW"] = "MEDIUM"
    section: str = Field(default="", description="the design section the problem is in")
    description: str = Field(description="the concrete problem, stated precisely")


class CriticResult(BaseModel):
    """STEP 6 / 10 — critic output (STEP 4: targeted, <= config.MAX_CRITIC_ISSUES issues)."""

    score: int = Field(ge=0, le=100, description="coarse overall estimate (the Gate is authoritative)")
    issues: list[CriticIssue] = Field(default_factory=list)
    missing_items: list[str] = Field(default_factory=list)
    recommendations: list[str] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _coerce_issues(cls, data: Any) -> Any:
        """A model may return issues as plain strings or the legacy dict shape.
        Normalize each to a CriticIssue so the engine can rely on .severity/.section."""
        if not isinstance(data, dict):
            return data
        raw = data.get("issues")
        if not isinstance(raw, list):
            return data
        norm = []
        for i, item in enumerate(raw, start=1):
            if isinstance(item, CriticIssue):
                norm.append(item)
            elif isinstance(item, dict):
                norm.append(CriticIssue(
                    id=item.get("id") or f"ISS-{i:02d}",
                    severity=item.get("severity", "HIGH"),
                    section=item.get("section", ""),
                    description=item.get("description") or item.get("problem") or str(item),
                ))
            else:
                norm.append(CriticIssue(id=f"ISS-{i:02d}", severity="HIGH",
                                         section="", description=str(item)))
        data["issues"] = norm
        return data


class FixPrompt(BaseModel):
    """STEP 7 / 4.5 — ONE atomic corrective prompt for ONE critic issue.

    Every fix carries `acceptance_criteria` — the checklist the Patch Verifier
    (STEP 4.6) checks the rebuilt design against. Without criteria a fix is
    unverifiable and cannot be confirmed closed.
    """

    id: str = Field(description="fix id, e.g. FIX-001")
    severity: Literal["BLOCKER", "HIGH", "MEDIUM", "LOW"] = "HIGH"
    target_section: str = Field(description="the exact design section to change")
    problem: str = Field(description="what is wrong, in one sentence")
    required_change: str = Field(description="the precise, minimal change to make")
    acceptance_criteria: list[str] = Field(
        default_factory=list,
        description="concrete, checkable statements that must be TRUE after the fix",
    )
    prompt: str = ""  # back-compat alias; refiner reads required_change||prompt

    @model_validator(mode="before")
    @classmethod
    def _defaults(cls, data: Any) -> Any:
        """Backfill id / severity and accept the legacy single-field fix shape."""
        if not isinstance(data, dict):
            return data
        data.setdefault("id", "")
        data.setdefault("severity", "HIGH")
        data.setdefault("acceptance_criteria", [])
        # legacy shape had no required_change but a `prompt`; carry it across
        if not data.get("required_change") and data.get("prompt"):
            data["required_change"] = data["prompt"]
        return data


class FixPromptList(BaseModel):
    fix_prompts: list[FixPrompt]


class Patch(BaseModel):
    """STEP 8 — one patch that fixes a specific defective part (not a rewrite)."""

    id: str = Field(description="patch id, e.g. PATCH-001")
    fix_id: str = Field(default="", description="the FIX-### this patch implements")
    section: str = Field(description="the design section being patched")
    patch: str = Field(description="the corrective content for that section")
    acceptance_criteria: list[str] = Field(default_factory=list, description="mirrored from its fix")


class PatchList(BaseModel):
    patches: list[Patch]


class PatchCheck(BaseModel):
    """STEP 4.6 — verification of ONE patch against its acceptance criteria."""

    fix_id: str
    status: Literal["PASS", "FAIL", "MISSING"]
    evidence: str = Field(default="", description="quote/pointer showing the fix is present, or why it is not")


class PatchVerification(BaseModel):
    """STEP 4.6 — per-fix verdicts returned by the Patch Verifier."""

    checks: list[PatchCheck] = Field(default_factory=list)
    overall_pass: bool = False


class QualityScores(BaseModel):
    """STEP 11 / 4.3 — quality-gate scoring, section-level.

    The 11 dimensions are scored by the Gate over the FULL design. `final_score`
    is NOT trusted from the model — the engine COMPUTES it as the weighted mean
    of these dimensions using config.QUALITY_WEIGHTS (and overrides the field).
    `blocking_issues` are the specific, must-fix problems (mirrored by severity);
    `improvement_targets` are the lowest-scoring dimensions to raise next.
    """

    architecture_score: int = Field(ge=0, le=100)
    backend_score: int = Field(ge=0, le=100)
    database_score: int = Field(ge=0, le=100)
    api_score: int = Field(ge=0, le=100)
    security_score: int = Field(ge=0, le=100)
    testing_score: int = Field(ge=0, le=100)
    deployment_score: int = Field(ge=0, le=100)
    observability_score: int = Field(ge=0, le=100)
    product_score: int = Field(ge=0, le=100)
    ui_score: int = Field(ge=0, le=100)
    consistency_score: int = Field(ge=0, le=100)
    final_score: int = Field(ge=0, le=100, description="MUST equal the weighted mean of the dimensions (engine enforces)")
    blocking_issues: list[str] = Field(default_factory=list, description="must-fix problems (BLOCKER/HIGH) that keep the gate from passing")
    improvement_targets: list[str] = Field(default_factory=list, description="lowest-scoring dimensions to raise in the next iteration")


class FinalReview(BaseModel):
    """STEP 12 / 4.8 — final reviewer verdict using the SAME rubric as the Gate.

    Only a `blocking_issue` justifies REJECTED. Minor gaps must not reject —
    they are APPROVED_WITH_NOTES. This is what stops the baseline's mismatch
    (Gate 82 / Reviewer REJECTED on unrelated grounds).
    """

    verdict: Literal["APPROVED", "APPROVED_WITH_NOTES", "REJECTED"]
    blocking_issues: list[str] = Field(default_factory=list, description="the specific blocking problems, if any (empty when not REJECTED)")
    notes: list[str] = Field(default_factory=list, description="minor gaps / recommendations (do NOT justify rejection)")
    reason: str = ""


class FinalOutput(BaseModel):
    """STEP 13 — the 17-section final deliverable."""

    product_specification: str = ""
    system_architecture: str = ""
    component_architecture: str = ""
    ui_architecture: str = ""
    backend_architecture: str = ""
    database_schema: str = ""
    erd_description: str = ""
    api_specification: str = ""
    authentication: str = ""
    authorization: str = ""
    security: str = ""
    test_strategy: str = ""
    infrastructure: str = ""
    deployment: str = ""
    monitoring: str = ""
    risks: str = ""
    open_questions: str = ""


# =========================================================================== #
# 1b. STEP 5 — Design Enrichment (structured technical documents)
# =========================================================================== #
class TraceEntry(BaseModel):
    """STEP 5.5 — one traceable design decision: the decision, where it came
    from (which enrichment agent produced it) and the reason it was made."""

    decision: str = Field(description="the decision, e.g. 'PostgreSQL was chosen as the write store'")
    source: str = Field(default="", description="which agent decided it, e.g. 'backend_architect'")
    reason: str = Field(default="", description="why, e.g. 'transactional consistency for orders'")


class TechnicalDocument(BaseModel):
    """STEP 5.3 — the STRUCTURED output of one enrichment agent (5.2).

    The exact document shape the STEP 5 brief specifies: a document_type, a
    short summary, the list of decisions (each traceable via TraceEntry), the
    core architecture prose, named components, risks, open questions, and
    implementation notes. This is what the Document Manager renders into a
    `.md` file and what the document-completeness gate scores.
    """

    document_type: str = Field(description="e.g. 'Backend Design Document'")
    summary: str = Field(default="", description="2-4 sentence overview of the document")
    decisions: list[TraceEntry] = Field(default_factory=list, description="key decisions, each with source+reason")
    architecture: str = Field(default="", description="the main technical body (the deep detail)")
    components: list[str] = Field(default_factory=list, description="named components / elements")
    risks: list[str] = Field(default_factory=list, description="technical risks / trade-offs")
    open_questions: list[str] = Field(default_factory=list, description="items still undecided")
    implementation_notes: list[str] = Field(default_factory=list, description="concrete build notes for the dev team")

    # The eight enrichment agents map to these document_type values.
    DOCUMENT_TYPES: ClassVar[list[str]] = [
        "Backend Design Document", "Database Design Document", "API Specification",
        "Frontend/UI Design Document", "UX Specification", "Security Document",
        "Testing Strategy", "Deployment Document",
    ]


class EnrichmentScore(BaseModel):
    """STEP 5.6 — the NEW document-completeness Quality Gate output.

    The pipeline is scored per-document (each 0-100 on how complete/actionable
    it is for a dev team) plus an overall. The engine COMPUTES the overall as
    the weighted mean (never a free LLM number) and enforces it, mirroring the
    STEP 4 gate. `overall_score` is the weighted mean the gate compares against
    the threshold.
    """

    backend_completeness: int = Field(ge=0, le=100)
    database_completeness: int = Field(ge=0, le=100)
    api_completeness: int = Field(ge=0, le=100)
    frontend_completeness: int = Field(ge=0, le=100)
    ux_completeness: int = Field(ge=0, le=100)
    testing_completeness: int = Field(ge=0, le=100)
    security_completeness: int = Field(ge=0, le=100)
    deployment_completeness: int = Field(ge=0, le=100)
    overall_score: int = Field(ge=0, le=100, description="engine-enforced weighted mean of the 8 dims")
    gaps: list[str] = Field(default_factory=list, description="the most important completeness gaps")

    DIMENSION_KEYS: ClassVar[list[str]] = [
        "backend_completeness", "database_completeness", "api_completeness",
        "frontend_completeness", "ux_completeness", "testing_completeness",
        "security_completeness", "deployment_completeness",
    ]


# =========================================================================== #
# 2. Token ledger
# =========================================================================== #
class LlmCall(BaseModel):
    """One LLM invocation, recorded verbatim for honest accounting.

    `model` is the REAL underlying model reported back (via run metrics), not a
    logical role — the ledger must reflect what actually served the request.
    Stub-model calls (e.g. mock-agent-v1) are recorded too but flagged so they
    can be excluded from real-model totals.
    """

    call_id: str
    run_id: str
    agent: str                       # e.g. "product_analyst"
    role: str                        # logical role, e.g. "fast"
    model: str                       # real LiteLLM model id reported back
    provider: str                    # provider reported back (e.g. "OpenAI Chat" / litellm label)
    started_at: str
    finished_at: str
    duration_ms: int
    input_tokens: int
    output_tokens: int
    total_tokens: int
    reasoning_tokens: int = 0
    status: Literal["ok", "error"]
    error: Optional[str] = None
    is_stub: bool = False            # True when model in config.STUB_MODELS


class TokenUsage(BaseModel):
    """Aggregate token usage for a run, with per-call detail."""

    calls: list[LlmCall] = Field(default_factory=list)
    total_input_tokens: int = 0
    total_output_tokens: int = 0
    total_tokens: int = 0
    # Excluding stubs — the honest "real model" number.
    real_total_tokens: int = 0
    real_input_tokens: int = 0
    real_output_tokens: int = 0


# =========================================================================== #
# 3. Output container (generic) for any agent that returns JSON
# =========================================================================== #
class AgentOutput(BaseModel):
    """Generic structured output wrapper stored in state.agent_outputs."""

    agent: str
    role: str
    model: str
    content: Any
    tokens: Optional[dict[str, int]] = None
    duration_ms: Optional[int] = None
    status: Literal["ok", "error"] = "ok"
    error: Optional[str] = None


# =========================================================================== #
# 4. Workflow State (persisted after EVERY step, not just the end)
# =========================================================================== #
RunStatus = Literal[
    "created", "running", "completed", "failed", "budget_exhausted"
]


class WorkflowState(BaseModel):
    """The single source of truth for a workflow run. Persisted to disk after each step."""

    run_id: str
    status: RunStatus = "created"
    created_at: str
    updated_at: str
    original_input: str = ""
    current_step: str = ""

    product_analysis: Optional[dict[str, Any]] = None
    master_prompt: Optional[dict[str, Any]] = None
    tasks: list[dict[str, Any]] = Field(default_factory=list)

    agent_outputs: list[AgentOutput] = Field(default_factory=list)
    design_versions: list[dict[str, Any]] = Field(default_factory=list)

    critic_results: list[dict[str, Any]] = Field(default_factory=list)
    fix_prompts: list[dict[str, Any]] = Field(default_factory=list)
    patches: list[dict[str, Any]] = Field(default_factory=list)

    quality_scores: list[dict[str, Any]] = Field(default_factory=list)
    patch_verifications: list[dict[str, Any]] = Field(default_factory=list)
    design_integrity: list[dict[str, Any]] = Field(default_factory=list)

    final_review: Optional[dict[str, Any]] = None
    final_result: Optional[dict[str, Any]] = None
    final_iteration: int = 0

    # -- STEP 5: Design Enrichment ----------------------------------------- #
    # The structured technical documents produced by the 8 enrichment agents
    # (each a TechnicalDocument as a dict), plus the document-completeness
    # gate score, plus where the rendered .md bundle was written.
    technical_documents: list[dict[str, Any]] = Field(default_factory=list)
    document_completeness: Optional[dict[str, Any]] = None
    documents_dir: str = ""   # absolute path of /documents/{run_id}/ once written

    # -- STEP 8: gap-filling refine pass ------------------------------------ #
    # The subset of documents re-run by the 2nd (refine) pass, plus a small
    # before/after report of the completeness gate (which overall the refine
    # pass lifted it from and to). `technical_documents` is left as the 1st-pass
    # output; `document_completeness` is OVERWRITTEN with the post-refine gate
    # so downstream consumers see the final score.
    refined_documents: list[dict[str, Any]] = Field(default_factory=list)
    refinement_report: Optional[dict[str, Any]] = None

    token_usage: TokenUsage = Field(default_factory=TokenUsage)
    errors: list[str] = Field(default_factory=list)

    # -- helpers ------------------------------------------------------------ #
    def recalc_token_totals(self) -> None:
        """Recompute aggregate token totals from the per-call ledger."""
        tu = self.token_usage
        tu.total_input_tokens = sum(c.input_tokens for c in tu.calls)
        tu.total_output_tokens = sum(c.output_tokens for c in tu.calls)
        tu.total_tokens = sum(c.total_tokens for c in tu.calls)
        real = [c for c in tu.calls if not c.is_stub]
        tu.real_input_tokens = sum(c.input_tokens for c in real)
        tu.real_output_tokens = sum(c.output_tokens for c in real)
        tu.real_total_tokens = sum(c.total_tokens for c in real)

    def used_real_tokens(self) -> int:
        """Tokens consumed by real (non-stub) models — the budget meter."""
        self.recalc_token_totals()
        return self.token_usage.real_total_tokens
