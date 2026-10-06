"""
router.py — Model router + honest token accounting.

Design (STEP 2 requirements 2.4, 2.5):
  * Agents never pick a model by name. They ask `router` for a LOGICAL ROLE
    ("fast" / "deep" / "alt" / "stub"); the router resolves it to a REAL
    LiteLLM model from config.MODEL_ROLES. Adding Claude/GPT/DeepSeek/Anti-
    gravity/9Router later = only change config / .env.
  * ALL calls go through the single LiteLLM endpoint (config.LITELLM_BASE_URL).
  * The token ledger records the REAL model that served the request (read back
    from the run's metrics), NOT the logical role. Stub models are flagged so
    their usage is never mixed into real-model totals.
"""
from __future__ import annotations

import time
import uuid
from typing import Any, Optional, Type

from agno.agent import Agent
from pydantic import BaseModel

from . import config
from . import models as models_mod
from .schemas import LlmCall


class ModelRouter:
    """Resolves logical roles to real LiteLLM models and runs token-tracked calls."""

    def __init__(
        self,
        roles: Optional[dict[str, str]] = None,
        base_url: Optional[str] = None,
        api_key: Optional[str] = None,
        stub_models: Optional[set[str]] = None,
    ) -> None:
        self.roles = dict(roles if roles is not None else config.MODEL_ROLES)
        self.base_url = base_url or config.LITELLM_BASE_URL
        self.api_key = api_key or config.LITELLM_API_KEY
        self.stub_models = set(stub_models if stub_models is not None else config.STUB_MODELS)

    # -- role -> real model ------------------------------------------------ #
    def resolve(self, role: str) -> str:
        if role not in self.roles:
            raise KeyError(f"Unknown role '{role}'. Known roles: {list(self.roles)}")
        return self.roles[role]

    def resolutions(self) -> dict[str, str]:
        """{role: real_model} for every configured role (used by routing test)."""
        return {role: self.resolve(role) for role in self.roles}

    def is_stub(self, model: str) -> bool:
        return model in self.stub_models

    # -- model construction (cached in models.py) -------------------------- #
    def _model(self, role: str, max_tokens: Optional[int] = None):
        return models_mod.get_model(
            self.resolve(role),
            max_tokens=max_tokens,
            base_url=self.base_url,
            api_key=self.api_key,
        )

    # -- the token-tracked call -------------------------------------------- #
    def call(
        self,
        role: str,
        *,
        agent: str,
        run_id: str,
        input_text: str,
        output_schema: Optional[Type[BaseModel]] = None,
        instructions: Optional[str] = None,
        max_tokens: Optional[int] = None,
    ) -> tuple[Any, LlmCall]:
        """Run one LLM call through LiteLLM and return (content, LlmCall).

        `content` is a pydantic instance (if output_schema given) or a str.
        The returned LlmCall reflects the REAL model/provider reported back.
        `max_tokens` bounds generated output (budget control).
        """
        real = self.resolve(role)
        model = self._model(role, max_tokens=max_tokens)
        started = time.time()
        call_id = uuid.uuid4().hex[:12]

        try:
            agent_obj = Agent(
                name=agent,
                model=model,
                output_schema=output_schema,
                instructions=instructions or "",
                markdown=False,
                add_datetime_to_context=False,
            )
            out = agent_obj.run(input_text)
            finished = time.time()
            duration_ms = int((finished - started) * 1000)

            m = out.metrics
            details = (m.details or {}).get("model") or []
            served = details[0] if details else None
            real_model = getattr(served, "id", None) or real
            provider = getattr(served, "provider", None) or config.LITELLM_ROUTE_LABEL

            call = LlmCall(
                call_id=call_id,
                run_id=run_id,
                agent=agent,
                role=role,
                model=real_model,
                provider=provider,
                started_at=_iso(started),
                finished_at=_iso(finished),
                duration_ms=duration_ms,
                input_tokens=int(getattr(m, "input_tokens", 0) or 0),
                output_tokens=int(getattr(m, "output_tokens", 0) or 0),
                total_tokens=int(getattr(m, "total_tokens", 0) or 0),
                reasoning_tokens=int(getattr(m, "reasoning_tokens", 0) or 0),
                status="ok",
                is_stub=self.is_stub(real_model),
            )
            return out.content, call

        except Exception as e:  # record the failure honestly, then re-raise
            finished = time.time()
            duration_ms = int((finished - started) * 1000)
            call = LlmCall(
                call_id=call_id,
                run_id=run_id,
                agent=agent,
                role=role,
                model=real,
                provider=config.LITELLM_ROUTE_LABEL,
                started_at=_iso(started),
                finished_at=_iso(finished),
                duration_ms=duration_ms,
                input_tokens=0,
                output_tokens=0,
                total_tokens=0,
                status="error",
                error=f"{type(e).__name__}: {e}",
                is_stub=self.is_stub(real),
            )
            raise


# module-level default router
_default_router: Optional[ModelRouter] = None


def get_router() -> ModelRouter:
    global _default_router
    if _default_router is None:
        _default_router = ModelRouter()
    return _default_router


def _iso(ts: float) -> str:
    from datetime import datetime, timezone

    return datetime.fromtimestamp(ts, tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z"
