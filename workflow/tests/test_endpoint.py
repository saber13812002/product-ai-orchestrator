"""test_endpoint.py — hermetic tests for the STEP 9 LiteLLM endpoint/mode resolver.

The resolver (`workflow.config.resolve_endpoint`) is the ONLY place mode
selection happens. These tests pin both modes hermetically — NO LiteLLM, NO LLM,
NO network, NO API key — so CI keeps its "no model, no cost" promise.

Run:  uv run python -m workflow.tests.test_endpoint
or:   pytest workflow/tests/test_endpoint.py
"""
from __future__ import annotations

import sys
from pathlib import Path

# Make `workflow` importable when run as a plain script.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from workflow import config


def test_external_mode_resolves_from_external_env(monkeypatch):
    """Mode A: LITELLM_BASE_URL + LITELLM_API_KEY are used verbatim."""
    monkeypatch.setenv("LITELLM_BASE_URL", "http://172.20.1.52:4000/v1")
    monkeypatch.setenv("LITELLM_API_KEY", "ext-key")
    base_url, api_key = config.resolve_endpoint(mode="external")
    assert base_url == "http://172.20.1.52:4000/v1"
    assert api_key == "ext-key"


def test_external_mode_falls_back_to_legacy_openai(monkeypatch):
    """Legacy OPENAI_* names still work in external mode (unchanged behavior)."""
    monkeypatch.delenv("LITELLM_BASE_URL", raising=False)
    monkeypatch.delenv("LITELLM_API_KEY", raising=False)
    monkeypatch.setenv("OPENAI_BASE_URL", "http://10.0.0.5:4000/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "legacy-key")
    base_url, api_key = config.resolve_endpoint(mode="external")
    assert base_url == "http://10.0.0.5:4000/v1"
    assert api_key == "legacy-key"


def test_external_mode_prefers_litellm_over_openai(monkeypatch):
    """LITELLM_* wins over the legacy OPENAI_* fallback when both are set."""
    monkeypatch.setenv("LITELLM_BASE_URL", "http://litellm-primary/v1")
    monkeypatch.setenv("LITELLM_API_KEY", "primary")
    monkeypatch.setenv("OPENAI_BASE_URL", "http://legacy/v1")
    monkeypatch.setenv("OPENAI_API_KEY", "legacy")
    base_url, api_key = config.resolve_endpoint(mode="external")
    assert base_url == "http://litellm-primary/v1"
    assert api_key == "primary"


def test_bundled_mode_resolves_to_sidecar(monkeypatch):
    """Mode B: the sidecar URL + LITELLM_MASTER_KEY are used (not the external vars)."""
    # Make sure the external vars CANNOT leak into bundled resolution.
    monkeypatch.setenv("LITELLM_BASE_URL", "http://should-not-be-used/v1")
    monkeypatch.setenv("LITELLM_API_KEY", "ext-key")
    monkeypatch.setenv("LITELLM_MASTER_KEY", "bundled-master-key")
    base_url, api_key = config.resolve_endpoint(mode="bundled")
    assert base_url == "http://litellm:4000/v1"
    assert api_key == "bundled-master-key"


def test_bundled_url_is_overridable(monkeypatch):
    """A non-compose deployment can repoint the bundled sidecar URL."""
    monkeypatch.setenv("LITELLM_MASTER_KEY", "k")
    monkeypatch.setenv("LITELLM_BUNDLED_URL", "http://127.0.0.1:9000/v1")
    base_url, _ = config.resolve_endpoint(mode="bundled")
    assert base_url == "http://127.0.0.1:9000/v1"


def test_bundled_mode_missing_key_yields_empty(monkeypatch):
    """Bundled with no master key set -> empty key (composer still boots via
    healthcheck; the gateway rejects unauthenticated calls), not a crash."""
    monkeypatch.delenv("LITELLM_MASTER_KEY", raising=False)
    base_url, api_key = config.resolve_endpoint(mode="bundled")
    assert base_url == "http://litellm:4000/v1"
    assert api_key == ""


def test_default_mode_is_external(monkeypatch):
    """With no LITELLM_MODE set, resolution behaves exactly as the old external code."""
    monkeypatch.delenv("LITELLM_MODE", raising=False)
    assert config.LITELLM_MODE == "external"
    monkeypatch.setenv("LITELLM_BASE_URL", "http://ext/v1")
    monkeypatch.setenv("LITELLM_API_KEY", "k")
    base_url, api_key = config.resolve_endpoint()  # default mode
    assert base_url == "http://ext/v1"
    assert api_key == "k"


def test_endpoint_warning_for_non_v1_url(monkeypatch):
    """A base URL that does not end with /v1 emits a warning (helps avoid a
    class of silent 404s) but does NOT raise."""
    import warnings
    monkeypatch.delenv("LITELLM_API_KEY", raising=False)
    monkeypatch.setenv("LITELLM_BASE_URL", "http://172.20.1.52:4000")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        base_url, _ = config.resolve_endpoint(mode="external")
    assert base_url == "http://172.20.1.52:4000"
    assert any("/v1" in str(w.message) for w in caught)


def test_no_trailing_slash_still_warns(monkeypatch):
    """A bare gateway URL with a trailing slash but no /v1 also warns."""
    import warnings
    monkeypatch.setenv("LITELLM_BASE_URL", "http://172.20.1.52:4000/")
    with warnings.catch_warnings(record=True) as caught:
        warnings.simplefilter("always")
        config.resolve_endpoint(mode="external")
    assert any("/v1" in str(w.message) for w in caught)
