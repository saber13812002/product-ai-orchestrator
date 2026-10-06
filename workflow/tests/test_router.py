"""test_router.py — unit tests for the ModelRouter (no network needed).

Run:  uv run python -m workflow.tests.test_router
or:   pytest workflow/tests/test_router.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make `workflow` importable when run as a plain script.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from workflow import config
from workflow.router import ModelRouter


def test_resolve_known_roles():
    r = ModelRouter()
    assert r.resolve("fast") == "qwen38-nothinking"
    assert r.resolve("deep") == "qwen38"
    assert r.resolve("stub") == "mock-agent-v1"
    assert r.resolve("alt") == "qwen38-sglang"


def test_resolutions_has_all_roles():
    r = ModelRouter()
    res = r.resolutions()
    for role in ("fast", "deep", "alt", "stub"):
        assert role in res
        assert res[role] in config.MODEL_ROLES.values()


def test_unknown_role_raises():
    r = ModelRouter()
    try:
        r.resolve("does_not_exist")
        assert False, "expected KeyError"
    except KeyError:
        pass


def test_stub_flagging():
    r = ModelRouter()
    assert r.is_stub("mock-agent-v1") is True
    assert r.is_stub("qwen38-nothinking") is False


def test_router_respects_custom_config():
    """A custom role map must be honored (proves config-driven, not hard-coded)."""
    r = ModelRouter(roles={"fast": "claude-opus-4-8", "deep": "gpt-4o"})
    assert r.resolve("fast") == "claude-opus-4-8"
    assert r.resolve("deep") == "gpt-4o"


if __name__ == "__main__":
    fns = [v for k, v in sorted(globals().items()) if k.startswith("test_") and callable(v)]
    for fn in fns:
        fn()
        print(f"PASS {fn.__name__}")
    print(f"\n{len(fns)} router tests passed")
