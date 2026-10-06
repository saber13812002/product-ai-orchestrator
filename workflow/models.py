"""
models.py — LLM model factory.

Builds (and caches) the raw Agno `OpenAIChat` model instances that point at the
single LiteLLM endpoint. Kept separate from `router.py` so that:
  * models.py  = HOW to construct a model object for a real model id
  * router.py  = WHICH model id a logical role resolves to + token accounting

The OpenAI-compatible path is used because LiteLLM exposes an OpenAI-compatible
`/v1/chat/completions` for every model (Qwen, and later Claude/GPT/DeepSeek).
"""
from __future__ import annotations

from typing import Optional

from agno.models.openai.chat import OpenAIChat

from . import config


def build_model(
    model_id: str,
    *,
    base_url: Optional[str] = None,
    api_key: Optional[str] = None,
    temperature: float = 0.0,
    max_tokens: Optional[int] = None,
) -> OpenAIChat:
    """Build an OpenAI-compatible Agno model bound to one LiteLLM model id.

    `max_tokens` caps generated output (-> max_completion_tokens), used to keep
    each pipeline step compact within the run's token budget.
    """
    kwargs = dict(
        id=model_id,
        api_key=api_key or config.LITELLM_API_KEY,
        base_url=base_url or config.LITELLM_BASE_URL,
        temperature=temperature,
    )
    if max_tokens:
        kwargs["max_completion_tokens"] = max_tokens
    return OpenAIChat(**kwargs)


# Cache: one model object per (real model id, base_url). Capped calls build a
# fresh model with the cap (cache key includes the cap so they don't collide).
_MODEL_CACHE: dict[str, OpenAIChat] = {}


def get_model(model_id: str, *, max_tokens: Optional[int] = None, **kwargs) -> OpenAIChat:
    """Cached model factory used by the router."""
    base = kwargs.get("base_url") or config.LITELLM_BASE_URL
    key = f"{model_id}@{base}|max={max_tokens}"
    if key not in _MODEL_CACHE:
        _MODEL_CACHE[key] = build_model(model_id, max_tokens=max_tokens, **kwargs)
    return _MODEL_CACHE[key]
