"""test_smoke.py — the smoke FLOW, hermetically (no network).

Uses a FakeRouter so the Manager -> ProductAnalyst -> structured output ->
persist-state path is proven without any LiteLLM call. The LIVE smoke test
(real LiteLLM call with qwen38-nothinking) is run separately via the CLI:
    uv run python -m workflow.run smoke --brief "..."

Run:  uv run python -m workflow.tests.test_smoke
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from workflow import state as state_mod
from workflow.agents.manager import Manager
from workflow.schemas import ProductAnalysis
from workflow.state import JsonStateStore, load_state


class FakeRouter:
    """Mimics ModelRouter.call, returning a fixed ProductAnalysis + an LlmCall."""

    def __init__(self):
        self.roles = {"fast": "fake-fast"}

    def resolve(self, role):
        return self.roles[role]

    def resolutions(self):
        return dict(self.roles)

    def is_stub(self, model):
        return model == "mock-agent-v1"

    def call(self, role, *, agent, run_id, input_text, output_schema, instructions):
        from workflow.schemas import LlmCall

        content = ProductAnalysis(
            product_goal="test goal",
            users=["tester"],
            use_cases=["case1"],
            features=["feat1"],
            constraints=["con1"],
            ambiguities=["amb1"],
            non_functional_requirements=["nfr1"],
        )
        call = LlmCall(
            call_id="fake", run_id=run_id, agent=agent, role=role, model="fake-fast",
            provider="fake", started_at="1", finished_at="2", duration_ms=10,
            input_tokens=10, output_tokens=20, total_tokens=30, status="ok",
        )
        return content, call


def test_smoke_flow_hermetic():
    # isolate the store
    state_mod._store = JsonStateStore(root=Path(tempfile.mkdtemp(prefix="agno_smoke_")))

    manager = Manager(router=FakeRouter())
    state = manager.run_smoke("I want a simple sales system.")

    assert state.status == "completed"
    assert state.product_analysis is not None
    assert state.product_analysis["product_goal"] == "test goal"
    assert len(state.product_analysis["features"]) == 1
    # structured output was recorded as an agent_output too
    assert len(state.agent_outputs) == 1
    assert state.agent_outputs[0].agent == "product_analyst"
    # token ledger recorded the call
    assert state.token_usage.total_tokens == 30
    # state is persisted to disk
    on_disk = load_state(state.run_id)
    assert on_disk.product_analysis == state.product_analysis
    print(f"  persisted at: {state_mod.get_store().path(state.run_id)}")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(fns)} smoke-flow test passed")
