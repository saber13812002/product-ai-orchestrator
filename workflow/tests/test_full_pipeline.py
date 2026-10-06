"""test_full_pipeline.py — the FULL 13-step pipeline (STEP 4), hermetically (no network).

Uses a FakeRouter that returns schema-valid content for every schema the engine
requests — including the STEP 4 additions: a targeted CriticResult (one HIGH
issue), atomic fixes with acceptance criteria, a Patch, a PatchVerification,
section-level QualityScores (final_score recomputed by the engine), and a
FinalReview. This proves the whole improved orchestration end-to-end — step
transitions, the quality-gate loop, the patch verifier, the deterministic
integrity check, computed weighted final score, budget accounting, and state
persistence — WITHOUT any LiteLLM call. The LIVE run is separate.

Run:  uv run python -m workflow.tests.test_full_pipeline
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from workflow import state as state_mod
from workflow.engine import Engine, _compute_final
from workflow.schemas import (
    CriticIssue,
    CriticResult,
    FinalOutput,
    FinalReview,
    LlmCall,
    MasterPrompt,
    Patch,
    PatchCheck,
    PatchList,
    PatchVerification,
    ProductAnalysis,
    QualityScores,
    Task,
    TaskList,
)
from workflow.state import JsonStateStore, load_state

ROLES = {"fast": "fake-fast", "deep": "fake-deep", "alt": "fake-alt", "stub": "mock-agent-v1"}

_DESIGN = "## Design Draft vN\n- api: Add API deprecation policy: v2 endpoint added, v1 marked deprecated.\n- other section\n"


class FakeRouter:
    """Mimics ModelRouter: resolves roles and returns schema-valid content."""

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
        if schema is None:
            # fixgen (raw JSON) or rebuild (raw markdown) — disambiguate by agent
            if agent == "fix_prompt_generator":
                return ('{"fix_prompts":[{"id":"FIX-001","severity":"HIGH",'
                        '"target_section":"api","problem":"weak api versioning",'
                        '"required_change":"add a deprecation policy",'
                        '"acceptance_criteria":["api section states a deprecation policy"],'
                        '"prompt":"add a deprecation policy"}]}')
            return _DESIGN
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
            # STEP 4.4 — a single targeted HIGH issue (the loop chases it)
            return CriticResult(score=70,
                                issues=[CriticIssue(id="ISS-01", severity="HIGH",
                                                    section="api",
                                                    description="weak api versioning")],
                                missing_items=[], recommendations=[])
        if schema is PatchList:
            return PatchList(patches=[Patch(id="PATCH-001", fix_id="FIX-001", section="api",
                                            patch="Add API deprecation policy: v2 endpoint added, v1 marked deprecated.",
                                            acceptance_criteria=["api section states a deprecation policy"])])
        if schema is PatchVerification:
            return PatchVerification(checks=[PatchCheck(fix_id="FIX-001", status="PASS",
                                                        evidence="api section now states a deprecation policy")],
                                     overall_pass=True)
        if schema is QualityScores:
            # 11 section-level dimensions; engine recomputes final_score (90 here)
            return QualityScores(architecture_score=90, backend_score=90, database_score=90,
                                 api_score=90, security_score=90, testing_score=90,
                                 deployment_score=90, observability_score=90, product_score=90,
                                 ui_score=90, consistency_score=90, final_score=90,
                                 blocking_issues=[], improvement_targets=["ui_score"])
        if schema is FinalReview:
            return FinalReview(verdict="APPROVED_WITH_NOTES",
                               blocking_issues=[], notes=["ui could be richer"],
                               reason="meets the rubric with only minor notes")
        if schema is FinalOutput:
            d = {s: "final " + s for s in [
                "product_specification", "system_architecture", "component_architecture",
                "ui_architecture", "backend_architecture", "database_schema",
                "erd_description", "api_specification", "authentication", "authorization",
                "security", "test_strategy", "infrastructure", "deployment", "monitoring",
                "risks", "open_questions"]}
            return FinalOutput(**d)
        raise ValueError(f"FakeRouter got unhandled schema {schema!r}")


def test_full_pipeline_hermetic():
    state_mod._store = JsonStateStore(root=Path(tempfile.mkdtemp(prefix="agno_full_")))
    eng = Engine(router=FakeRouter(), test_mode=True,
                 budget=20000, max_iterations=2, threshold=85)
    state = eng.run("A simple B2B sales / CRM system for field teams.")

    # --- outcome --------------------------------------------------------- #
    assert state.status == "completed", f"status={state.status} errors={state.errors}"
    assert state.product_analysis is not None
    assert state.master_prompt is not None
    assert len(state.tasks) == 9, f"tasks={len(state.tasks)}"
    assert len(state.design_versions) >= 1
    # quality-gate loop ran; the engine COMPUTED final_score from the 11 dims
    assert len(state.quality_scores) == 1, f"gate iterations={len(state.quality_scores)}"
    gs = state.quality_scores[0]
    assert gs["final_score"] == 90, f"computed final={gs['final_score']}"
    assert gs["passed"] is True
    # final_score is the weighted mean (assert the engine, not the model, set it)
    assert _compute_final(gs) == gs["final_score"]
    # STEP 4.6 — the patch verifier ran and recorded per-fix PASS
    assert len(state.patch_verifications) >= 1, "patch verifier did not run"
    assert state.patch_verifications[0]["overall_pass"] is True
    # STEP 4.7 — the deterministic integrity check ran and recorded a result
    assert len(state.design_integrity) >= 1, "integrity check did not run"
    assert "sections_before" in state.design_integrity[0]
    # STEP 4.5 — the fix carried acceptance criteria
    assert state.fix_prompts and state.fix_prompts[0].get("acceptance_criteria"), "fix lacks acceptance criteria"
    # final review (APPROVED_WITH_NOTES is a pass) + final output present
    assert state.final_review and state.final_review["verdict"] in ("APPROVED", "APPROVED_WITH_NOTES")
    assert state.final_result is not None
    assert state.final_result["sections"]["security"].startswith("final security")
    # --- honest token ledger --------------------------------------------- #
    tu = state.token_usage
    # 22 calls: 1 analyst + 1 master + 1 decompose + 9 tasks + 1 merge
    #           + 7 loop(critic,fixgen,refine,rebuild,verifier,2nd-critic,gate)
    #           + 1 final review + 1 final output
    assert len(tu.calls) == 22, f"calls={len(tu.calls)}"
    assert tu.real_total_tokens == 22 * 70, f"real_total={tu.real_total_tokens}"
    assert tu.total_tokens == tu.real_total_tokens  # no stubs used
    # --- persistence ------------------------------------------------------ #
    on_disk = load_state(state.run_id)
    assert on_disk.final_result == state.final_result
    assert on_disk.token_usage.real_total_tokens == tu.real_total_tokens

    models = {c.model for c in tu.calls}
    print(f"  run_id={state.run_id}  status={state.status}")
    print(f"  calls={len(tu.calls)}  real_tokens={tu.real_total_tokens}  "
          f"versions={len(state.design_versions)}  gate_iters={len(state.quality_scores)}")
    print(f"  final_score(computed)={gs['final_score']}  passed={gs['passed']}")
    print(f"  patch_verifications={len(state.patch_verifications)}  "
          f"integrity_checks={len(state.design_integrity)}")
    print(f"  distinct models used: {sorted(models)}")
    print(f"  persisted at: {state_mod.get_store().path(state.run_id)}")


if __name__ == "__main__":
    test_full_pipeline_hermetic()
    print("\nPASS test_full_pipeline_hermetic")
