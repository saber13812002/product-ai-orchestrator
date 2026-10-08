"""test_refine.py — the STEP 8 gap-filling refine pass, hermetically (no network).

Extends the STEP 5 enrichment FakeRouter to model BOTH enrichment passes:
  * 1st pass: each agent yields a (deliberately thin) TechnicalDocument and the
    completeness gate returns LOW scores on three documents + NAMED gaps (DDL /
    OpenAPI / payment).
  * 2nd (refine) pass: the SAME three agents are re-run and return REVISED
    documents (tagged so the test can prove the bundle was overwritten), and the
    gate returns HIGH scores.

This proves the whole STEP 8 path end-to-end WITHOUT any LiteLLM call:
  * the 13-step primary pipeline + 1st enrichment pass still complete first,
  * the refine pass picks exactly the gapful documents (keyword-mapped gaps +
    the lowest-scoring docs),
  * the refined documents REPLACE the v1 ones in the bundle,
  * the completeness gate is RE-RUN and the engine records a before/after report,
  * the honest token ledger records both passes' calls.

Run:  uv run python -m workflow.tests.test_refine
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from workflow import config, state as state_mod
from workflow.engine import Engine
from workflow.schemas import (
    CriticResult,
    EnrichmentScore,
    FinalOutput,
    FinalReview,
    LlmCall,
    MasterPrompt,
    ProductAnalysis,
    QualityScores,
    Task,
    TaskList,
    TechnicalDocument,
    TraceEntry,
)
from workflow.state import JsonStateStore

ROLES = {"fast": "fake-fast", "deep": "fake-deep", "alt": "fake-alt", "stub": "mock-agent-v1"}

# The three documents the 1st-pass gate flags as gapful (low score + a named gap
# that keyword-maps to each of these agents).
_GAP_DOCS = {
    "database_architect": "Database DDL and table definitions are missing",
    "api_architect": "The API lacks an exact OpenAPI endpoint table",
    "backend_architect": "No payment flow is described in the backend",
}
_REFINED_TYPES = {
    "Database Design Document", "API Specification", "Backend Design Document",
}
_UNCHANGED_FILES = ["frontend.md", "ux.md", "testing.md", "security.md", "devops.md"]


class FakeRouter:
    """Mimics ModelRouter for the FULL pipeline + BOTH enrichment passes.

    Per-agent TechnicalDocument calls are counted: the 1st is a thin v1 doc, any
    later call is a REVISED doc (so the refine pass's overwrite is observable).
    EnrichmentScore calls are counted: 1st = low + named gaps, 2nd = high.
    """

    def __init__(self):
        self.roles = dict(ROLES)
        self.n = 0
        self.doc_calls: dict[str, int] = {}
        self.gate_calls = 0

    def resolve(self, role):
        return self.roles[role]

    def resolutions(self):
        return dict(self.roles)

    def is_stub(self, model):
        return model in {"mock-agent-v1"}

    def call(self, role, *, agent, run_id, input_text,
             output_schema=None, instructions=None, max_tokens=None):
        self.n += 1
        model = self.roles.get(role, "fake-fast")
        call = LlmCall(
            call_id=f"c{self.n:03d}", run_id=run_id, agent=agent, role=role,
            model=model, provider="fake", started_at="1", finished_at="2",
            duration_ms=5, input_tokens=40, output_tokens=30, total_tokens=70,
            status="ok", is_stub=self.is_stub(model),
        )
        return self._content(output_schema, agent), call

    def _content(self, schema, agent):
        # ---- STEP 5 / STEP 8 enrichment documents ------------------------ #
        if schema is TechnicalDocument:
            doc_type = next(
                (s["doc_type"] for s in config.ENRICH_AGENTS if s["agent"] == agent),
                "Generic Document",
            )
            refined = self.doc_calls.get(agent, 0) >= 1  # 2nd call = refine pass
            self.doc_calls[agent] = self.doc_calls.get(agent, 0) + 1
            arch = (
                f"The component is structured as service Y with a clear boundary. "
                "It uses a repository pattern, an explicit error contract, and a "
                "background worker for async work. Scaling is horizontal behind a "
                "load balancer; state is sharded by tenant id. Observability via "
                "structured logs, RED metrics and distributed tracing."
            )
            # the REVISED doc carries a marker so the test can prove the bundle
            # file was overwritten with the refined content.
            if refined:
                arch = ("REVISED: " + _GAP_DOCS.get(
                    agent, "strengthened").upper() + " now covered. " + arch)
            return TechnicalDocument(
                document_type=doc_type,
                summary=f"{'Revised ' if refined else ''}{doc_type} for the B2B CRM.",
                decisions=[
                    TraceEntry(decision=("Refined mechanism" if refined else "Concrete named mechanism X chosen"),
                               source=agent, reason="fits the domain and the overall design"),
                ],
                architecture=arch,
                components=["service-y", "repo", "worker", "schema"],
                risks=["complexity if tenant count grows"],
                open_questions=["Is read-replica latency acceptable for reports?"],
                implementation_notes=["Stand up service-y and its schema first"],
            )
        if schema is EnrichmentScore:
            self.gate_calls += 1
            if self.gate_calls == 1:
                # 1st pass: three gapful docs low, the rest solid. overall 78 < 80.
                return EnrichmentScore(
                    backend_completeness=62, database_completeness=60,
                    api_completeness=58, frontend_completeness=90,
                    ux_completeness=88, testing_completeness=85,
                    security_completeness=90, deployment_completeness=90,
                    overall_score=78,
                    gaps=list(_GAP_DOCS.values()),
                )
            # 2nd (refine) pass: everything high. overall 92 >= 80.
            return EnrichmentScore(
                backend_completeness=92, database_completeness=92,
                api_completeness=92, frontend_completeness=90,
                ux_completeness=88, testing_completeness=85,
                security_completeness=90, deployment_completeness=90,
                overall_score=92, gaps=[],
            )
        # ---- primary 13-step pipeline (mirrors test_full_pipeline) -------- #
        if schema is None:
            return "## Design Draft vN\n- api: deprecation policy\n- other\n"
        if schema is ProductAnalysis:
            return ProductAnalysis(product_goal="g", users=["u"], use_cases=["c"],
                                   features=["f"], constraints=["k"],
                                   ambiguities=["a"], non_functional_requirements=["n"])
        if schema is MasterPrompt:
            d = {s: "directive for " + s for s in [
                "product_architecture", "backend_architecture", "frontend_architecture",
                "ui_ux_architecture", "database", "api", "authn_authz", "security",
                "observability", "testing_strategy", "deployment", "scalability",
                "failure_scenarios"]}
            return MasterPrompt(**d)
        if schema is TaskList:
            return TaskList(tasks=[
                Task(task_id=f"TASK-{i:02d}", objective=f"task {i}",
                     context="ctx", input="in", expected_output="out",
                     assigned_model="fast", dependencies=[], token_budget=200)
                for i in range(1, 10)
            ])
        if schema is CriticResult:
            return CriticResult(score=90, issues=[], missing_items=[], recommendations=[])
        if schema is QualityScores:
            return QualityScores(architecture_score=90, backend_score=90, database_score=90,
                                 api_score=90, security_score=90, testing_score=90,
                                 deployment_score=90, observability_score=90, product_score=90,
                                 ui_score=90, consistency_score=90, final_score=90,
                                 blocking_issues=[], improvement_targets=[])
        if schema is FinalReview:
            return FinalReview(verdict="APPROVED", blocking_issues=[], notes=[],
                               reason="meets the rubric")
        if schema is FinalOutput:
            d = {s: "final " + s for s in [
                "product_specification", "system_architecture", "component_architecture",
                "ui_architecture", "backend_architecture", "database_schema",
                "erd_description", "api_specification", "authentication", "authorization",
                "security", "test_strategy", "infrastructure", "deployment", "monitoring",
                "risks", "open_questions"]}
            return FinalOutput(**d)
        raise ValueError(f"FakeRouter got unhandled schema {schema!r}")


def test_refine_hermetic():
    tmp_docs = Path(tempfile.mkdtemp(prefix="agno_refinedocs_"))
    state_mod._store = JsonStateStore(root=Path(tempfile.mkdtemp(prefix="agno_refine_")))
    saved_docs_dir = config.DOCUMENTS_DIR
    config.DOCUMENTS_DIR = tmp_docs
    try:
        eng = Engine(router=FakeRouter(), test_mode=False, refine=True,
                     budget=300000, max_iterations=1, threshold=85)
        state = eng.run("A B2B sales management system with CRM, customers, orders, "
                        "sales reports and org roles.")
    finally:
        config.DOCUMENTS_DIR = saved_docs_dir

    # --- primary pipeline + 1st enrichment pass still completed first ------ #
    assert state.status == "completed", f"status={state.status} errors={state.errors}"
    assert state.current_step == "completed_refined", f"step={state.current_step}"

    # --- 8 documents in total, of which exactly 3 were RE-refined ---------- #
    assert len(state.technical_documents) == 8, f"docs={len(state.technical_documents)}"
    refined_types = {d["document_type"] for d in state.refined_documents}
    assert refined_types == _REFINED_TYPES, f"refined={refined_types}"
    assert len(state.refined_documents) == 3, f"n_refined={len(state.refined_documents)}"

    # the refined documents replaced the v1 ones in the final bundle
    merged_types = {d["document_type"] for d in state.technical_documents}
    assert merged_types == {s["doc_type"] for s in config.ENRICH_AGENTS}

    # --- the bundle was overwritten with the refined (REVISED) content ----- #
    ddir = Path(state.documents_dir)
    for agent, gap in _GAP_DOCS.items():
        fname = next(s["file"] for s in config.ENRICH_AGENTS if s["agent"] == agent)
        text = (ddir / fname).read_text(encoding="utf-8")
        assert "REVISED:" in text, f"{fname} was not overwritten by the refine pass"
    # untouched documents still show the v1 body (no REVISED marker)
    for fname in _UNCHANGED_FILES:
        assert "REVISED:" not in (ddir / fname).read_text(encoding="utf-8"), \
            f"{fname} should be unchanged"
    # product.md / architecture.md still came from the finalized deliverable
    assert "final product_specification" in (ddir / "product.md").read_text(encoding="utf-8")

    # --- the completeness gate was RE-RUN and OVERWROTE the score ---------- #
    comp = state.document_completeness
    assert comp is not None
    # The engine COMPUTES overall as the mean of the 8 dims (never the LLM's
    # reported number): 92,92,92,90,88,85,90,90 -> mean 90. Post-refine, not 78.
    assert comp["overall_score"] == 90, f"overall={comp['overall_score']}"
    assert comp["passed"] is True

    # --- the before/after refinement report is recorded -------------------- #
    rep = state.refinement_report
    assert rep is not None, "refinement_report not produced"
    assert rep["before_overall"] == 78, f"before={rep.get('before_overall')}"
    assert rep["after_overall"] == 90, f"after={rep.get('after_overall')}"
    assert set(rep["targets"]) == set(_GAP_DOCS), f"targets={rep.get('targets')}"
    # the named gaps were routed to the right agents
    assert any("DDL" in g for g in rep["gaps_by_agent"]["database_architect"])
    assert any("OpenAPI" in g for g in rep["gaps_by_agent"]["api_architect"])
    assert any("payment" in g.lower() for g in rep["gaps_by_agent"]["backend_architect"])

    # --- honest token ledger: BOTH passes' calls recorded ------------------ #
    tu = state.token_usage
    # 8 (1st-pass docs) + 3 (refined docs) = 11 enrichment document calls
    doc_calls = [c for c in tu.calls if c.agent.endswith(("_architect", "_designer"))]
    assert len(doc_calls) == 11, f"enrich doc calls={len(doc_calls)}"
    # the completeness gate ran twice (1st pass + refine pass)
    gate_calls = [c for c in tu.calls if c.agent == "document_gate"]
    assert len(gate_calls) == 2, f"gate calls={len(gate_calls)}"
    assert tu.real_total_tokens == len(tu.calls) * 70


if __name__ == "__main__":
    test_refine_hermetic()
    print("\nPASS test_refine_hermetic")
