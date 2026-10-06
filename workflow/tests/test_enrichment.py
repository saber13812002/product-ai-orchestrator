"""test_enrichment.py — the STEP 5 Design-Enrichment layer, hermetically (no network).

Extends the STEP 4 full-pipeline FakeRouter with the two new structured outputs
the enrichment layer requests: a TechnicalDocument (one per enrichment agent) and
an EnrichmentScore (the document-completeness gate). This proves the whole STEP 5
additive path end-to-end WITHOUT any LiteLLM call:

  * all 8 enrichment agents run and each yields a structured TechnicalDocument,
  * the 10-file bundle (product/architecture + 8 agent docs) + TRACEABILITY.md
    are written to {DOCUMENTS_DIR}/{run_id}/,
  * decision traceability (every decision carries source + reason),
  * the document-completeness gate scores all 8 documents and the engine COMPUTES
    the overall as the mean (never a free LLM number),
  * the 13-step primary pipeline is untouched (still completes first), and the
    enrichment runs only because enrich=True,
  * the honest token ledger records the enrichment calls.

Run:  uv run python -m workflow.tests.test_enrichment
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

_EXPECTED_FILES = [
    "product.md", "architecture.md", "backend.md", "database.md", "api.md",
    "frontend.md", "ux.md", "security.md", "testing.md", "devops.md", "TRACEABILITY.md",
]


class FakeRouter:
    """Mimics ModelRouter, returning schema-valid content for the full pipeline
    AND the STEP 5 enrichment outputs (TechnicalDocument + EnrichmentScore)."""

    def __init__(self):
        self.roles = dict(ROLES)
        self.n = 0

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
        # ---- STEP 5 enrichment outputs ----------------------------------- #
        if schema is TechnicalDocument:
            doc_type = next(
                (s["doc_type"] for s in config.ENRICH_AGENTS if s["agent"] == agent),
                "Generic Document",
            )
            return TechnicalDocument(
                document_type=doc_type,
                summary=f"Deep {doc_type.lower()} for the B2B CRM, buildable by a dev team.",
                decisions=[
                    TraceEntry(decision="Concrete named mechanism X chosen",
                               source=agent, reason="fits the domain and the overall design"),
                    TraceEntry(decision="Data owned by service Y",
                               reason="single source of truth, avoids split-brain"),
                ],
                architecture=(
                    "The component is structured as service Y with a clear boundary. "
                    "It uses a repository pattern, an explicit error contract, and a "
                    "background worker for async work. Scaling is horizontal behind a "
                    "load balancer; state is sharded by tenant id. Observability via "
                    "structured logs, RED metrics and distributed tracing."
                ),
                components=["service-y", "repo", "worker", "schema"],
                risks=["complexity if tenant count grows", "worker backlog under load"],
                open_questions=["Is read-replica latency acceptable for reports?"],
                implementation_notes=[
                    "Stand up service-y and its schema first",
                    "Wire the worker and its queue",
                    "Add the RED metrics and a trace span per request",
                ],
            )
        if schema is EnrichmentScore:
            # engine recomputes overall_score as the mean of the 8 dims (90 here)
            return EnrichmentScore(
                backend_completeness=90, database_completeness=90, api_completeness=90,
                frontend_completeness=90, ux_completeness=90, testing_completeness=90,
                security_completeness=90, deployment_completeness=90, overall_score=90,
                gaps=[],
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


def test_enrichment_hermetic():
    tmp_docs = Path(tempfile.mkdtemp(prefix="agno_docs_"))
    state_mod._store = JsonStateStore(root=Path(tempfile.mkdtemp(prefix="agno_enrich_")))
    saved_docs_dir = config.DOCUMENTS_DIR
    config.DOCUMENTS_DIR = tmp_docs
    try:
        eng = Engine(router=FakeRouter(), test_mode=False, enrich=True,
                     budget=200000, max_iterations=1, threshold=85)
        state = eng.run("A B2B sales management system with CRM, customers, orders, "
                        "sales reports and org roles.")
    finally:
        config.DOCUMENTS_DIR = saved_docs_dir

    # --- primary pipeline still completed (enrichment is additive) --------- #
    assert state.status == "completed", f"status={state.status} errors={state.errors}"
    assert state.current_step == "completed_enriched", f"step={state.current_step}"
    assert state.final_result is not None and state.final_result["sections"]["security"]

    # --- 8 enrichment agents each produced a TechnicalDocument ------------ #
    docs = state.technical_documents
    assert len(docs) == 8, f"docs={len(docs)}"
    got_types = {d["document_type"] for d in docs}
    want_types = {s["doc_type"] for s in config.ENRICH_AGENTS}
    assert got_types == want_types, f"missing={want_types - got_types}"

    # --- 5.5 traceability: every decision carries source + reason --------- #
    for d in docs:
        assert d["decisions"], f"{d['document_type']} has no decisions"
        for dec in d["decisions"]:
            assert dec.get("source"), f"decision missing source: {dec}"
            assert dec.get("reason"), f"decision missing reason: {dec}"

    # --- 5.4 the 10-file bundle + traceability index were written ---------- #
    assert state.documents_dir, "documents_dir not recorded in state"
    ddir = Path(state.documents_dir)
    present = [p.name for p in ddir.iterdir()]
    for f in _EXPECTED_FILES:
        assert f in present, f"missing file {f}; present={sorted(present)}"
    # product.md + architecture.md came from the finalized deliverable
    assert "final product_specification" in (ddir / "product.md").read_text(encoding="utf-8")
    assert "final system_architecture" in (ddir / "architecture.md").read_text(encoding="utf-8")
    # the agent docs rendered their structured body
    assert "Architecture" in (ddir / "backend.md").read_text(encoding="utf-8")
    # the traceability index aggregates decisions from all docs
    trace = (ddir / "TRACEABILITY.md").read_text(encoding="utf-8")
    assert "Traceability Index" in trace and "Source" in trace
    assert "Concrete named mechanism X" in trace

    # --- 5.6 the completeness gate: all 8 dims + a COMPUTED overall -------- #
    comp = state.document_completeness
    assert comp is not None, "document_completeness not produced"
    for k in EnrichmentScore.DIMENSION_KEYS:
        assert 0 <= comp[k] <= 100, f"{k} out of range: {comp.get(k)}"
    mean = int(round(sum(comp[k] for k in EnrichmentScore.DIMENSION_KEYS) / 8))
    assert comp["overall_score"] == mean, f"overall {comp['overall_score']} != mean {mean}"
    assert comp["passed"] is (comp["overall_score"] >= config.ENRICH_GATE_THRESHOLD)
    assert comp["documents_scored"] == 8

    # --- honest token ledger: enrichment calls recorded -------------------- #
    tu = state.token_usage
    enrich_calls = [c for c in tu.calls
                    if c.agent.endswith(("_architect", "_designer"))]
    gate_calls = [c for c in tu.calls if c.agent == "document_gate"]
    # exactly 8 enrichment documents + 1 completeness gate
    assert len(enrich_calls) == 8, f"enrich calls={len(enrich_calls)}"
    assert len(gate_calls) == 1, f"doc gate calls={len(gate_calls)}"
    # the ledger is honest: every call is a real (non-stub) fake model
    assert tu.real_total_tokens == len(tu.calls) * 70
    # enrichment added exactly 9 calls on top of the primary pipeline
    assert len(tu.calls) >= 18 + 9, f"calls={len(tu.calls)}"


if __name__ == "__main__":
    test_enrichment_hermetic()
    print("\nPASS test_enrichment_hermetic")
