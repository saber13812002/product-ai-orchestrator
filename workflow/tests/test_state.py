"""test_state.py — state lifecycle + token ledger (no network needed).

Run:  uv run python -m workflow.tests.test_state
or:   pytest workflow/tests/test_state.py
"""
from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from workflow import state as state_mod
from workflow.schemas import LlmCall, TokenUsage, WorkflowState
from workflow.state import JsonStateStore, create_state, load_state, new_run_id, record_call, save_state


def _store() -> JsonStateStore:
    return JsonStateStore(root=Path(tempfile.mkdtemp(prefix="agno_state_")))


def test_create_and_persist():
    st = _store()
    # Point the module store at an isolated dir so we don't pollute real runs.
    state_mod._store = st
    s = create_state("a raw brief")
    assert s.run_id
    assert s.status == "created"
    assert s.original_input == "a raw brief"
    assert (st.path(s.run_id)).exists()
    reloaded = st.load(s.run_id)
    assert reloaded.run_id == s.run_id


def test_save_load_roundtrip():
    st = _store()
    s = WorkflowState(
        run_id="test-roundtrip",
        created_at="now",
        updated_at="now",
        original_input="hello",
    )
    st.save(s)
    loaded = st.load("test-roundtrip")
    assert loaded.run_id == "test-roundtrip"
    assert loaded.original_input == "hello"


def test_list_runs():
    st = _store()
    st.save(WorkflowState(run_id="run-a", created_at="1", updated_at="1"))
    st.save(WorkflowState(run_id="run-b", created_at="2", updated_at="2"))
    runs = st.list_runs()
    assert "run-a" in runs and "run-b" in runs
    assert runs == sorted(runs, reverse=True)  # newest first (lexicographic)


def test_token_totals_recalc():
    s = WorkflowState(run_id="tk", created_at="1", updated_at="1")
    c1 = LlmCall(
        call_id="c1", run_id="tk", agent="a", role="fast", model="qwen38-nothinking",
        provider="OpenAI Chat", started_at="1", finished_at="2", duration_ms=100,
        input_tokens=10, output_tokens=20, total_tokens=30, status="ok",
    )
    c2 = LlmCall(
        call_id="c2", run_id="tk", agent="a", role="stub", model="mock-agent-v1",
        provider="stub", started_at="3", finished_at="4", duration_ms=50,
        input_tokens=5, output_tokens=5, total_tokens=10, status="ok", is_stub=True,
    )
    s.token_usage.calls = [c1, c2]
    s.recalc_token_totals()
    tu = s.token_usage
    assert tu.total_tokens == 40          # includes stub
    assert tu.real_total_tokens == 30     # excludes stub
    assert tu.real_input_tokens == 10
    assert tu.real_output_tokens == 20


def test_record_call_persists():
    """record_call must append to ledger and (when persist=True) hit the backend."""
    # point module store at a temp dir
    tmp = Path(tempfile.mkdtemp(prefix="agno_rec_"))
    state_mod._store = JsonStateStore(root=tmp)
    s = WorkflowState(run_id="rec", created_at="1", updated_at="1")
    record_call(
        s,
        LlmCall(
            call_id="x", run_id="rec", agent="a", role="fast", model="qwen38-nothinking",
            provider="OpenAI Chat", started_at="1", finished_at="2", duration_ms=1,
            input_tokens=1, output_tokens=2, total_tokens=3, status="ok",
        ),
        persist=True,
    )
    loaded = state_mod.load_state("rec")
    assert len(loaded.token_usage.calls) == 1
    assert loaded.token_usage.total_tokens == 3
    assert (tmp / "rec" / "state.json").exists()


def test_new_run_id_format():
    rid = new_run_id()
    assert len(rid.split("-")) == 3  # YYYYMMDD-HHMMSS-hex6
    assert len(rid.split("-")[-1]) == 6


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(fns)} state tests passed")
