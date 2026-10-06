"""
agents/product_analyst.py — STEP 1 agent.

Input: a raw Product Brief (string).
Output: structured ProductAnalysis (pydantic), produced via Agno native
structured output (output_schema). The model is resolved through the Router
(never hard-coded) using the role configured for this agent.
"""
from __future__ import annotations

from typing import Any

from .. import config
from ..router import ModelRouter, get_router
from ..schemas import ProductAnalysis

SYSTEM_PROMPT = (
    "You are a senior Product Analyst. Given a raw product brief, extract a "
    "structured understanding. Be concrete and faithful to the brief; do not "
    "invent requirements that are not implied. If something is ambiguous, list "
    "it under ambiguities rather than guessing."
)


class ProductAnalyst:
    """Wraps the Product Analyst LLM role behind a single analyze() method."""

    agent_name = "product_analyst"

    def __init__(self, router: ModelRouter | None = None, role: str | None = None) -> None:
        self.router = router or get_router()
        self.role = role or config.AGENT_ROLES[self.agent_name]

    def analyze(self, brief: str, run_id: str) -> tuple[Any, Any]:
        """Run the analyst. Returns (ProductAnalysis, LlmCall)."""
        content, call = self.router.call(
            self.role,
            agent=self.agent_name,
            run_id=run_id,
            input_text=brief,
            output_schema=ProductAnalysis,
            instructions=SYSTEM_PROMPT,
        )
        return content, call
