"""test_robustness.py — structured-output robustness (no network).

Covers the behavior that saved the first live run: when the model hits its
output cap mid-JSON, Agno returns a raw truncated STRING. The engine must (a)
salvage complete fields via _repair_json + _ensure_structured, or (b) raise
StepFailed cleanly — it must NEVER store a raw string in a dict-typed state
field (which corrupts the persisted state and crashes the final reload).

Run:  uv run python -m workflow.tests.test_robustness
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from workflow.engine import StepFailed, _ensure_structured, _repair_json
from workflow.schemas import MasterPrompt


def test_repair_json_flat_object():
    # Truncated mid-key: "database" started but its value never closed.
    truncated = ('{"product_architecture": "PA", "backend_architecture": "BA",'
                 ' "database": "dat')
    repaired = _repair_json(truncated)
    import json
    d = json.loads(repaired)
    assert d["product_architecture"] == "PA"
    assert d["backend_architecture"] == "BA"
    assert "database" not in d  # partial member dropped


def test_repair_json_balanced_unchanged():
    import json
    ok = '{"a": "x", "b": ["1", "2"]}'
    assert json.loads(_repair_json(ok)) == json.loads(ok)


def test_repair_nested_truncated():
    # Nested array truncated; repair must close the array before the object.
    truncated = '{"tasks": [{"id": "1"}, {"id": "2"}, {"id"'
    import json
    d = json.loads(_repair_json(truncated))
    assert d["tasks"][0]["id"] == "1"
    assert d["tasks"][1]["id"] == "2"


def test_ensure_structured_recovers_master_prompt():
    # A realistic truncated 13-field master prompt: 5 complete sections,
    # "database" cut off. Engine must recover the 5 good sections.
    truncated = (
        '{"product_architecture": "s1", "backend_architecture": "s2",'
        ' "frontend_architecture": "s3", "ui_ux_architecture": "s4",'
        ' "database": "dat'
    )
    mp = _ensure_structured(truncated, MasterPrompt)
    assert isinstance(mp, MasterPrompt)
    assert mp.product_architecture == "s1"
    assert mp.backend_architecture == "s2"
    assert mp.ui_ux_architecture == "s4"
    assert mp.database == ""  # truncated section defaults to empty, NOT a crash


def test_ensure_structured_passes_through_instance():
    mp = MasterPrompt(product_architecture="x")
    assert _ensure_structured(mp, MasterPrompt) is mp


def test_ensure_structured_raises_on_unrecoverable():
    # Nonsense that is not JSON at all -> StepFailed (not a crash, not a string)
    try:
        _ensure_structured("this is not json at all", MasterPrompt)
    except StepFailed:
        return
    raise AssertionError("expected StepFailed")


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(fns)} robustness tests passed")
