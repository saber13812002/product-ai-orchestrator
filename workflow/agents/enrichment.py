"""
agents/enrichment.py — STEP 5: the eight Design-Enrichment agents (5.2).

Each agent turns the FINALIZED overall design + final deliverable into ONE deep,
specialized technical document in the structured ``TechnicalDocument`` shape
(5.3). All eight are the SAME class instantiated with different (agent_name,
doc_type, role_prompt) — so they share routing, the token ledger, and structured
output exactly like ProductAnalyst, while each produces a distinct document.

Every one runs on ``fast`` (qwen38-nothinking): STEP 4 proved the thinking
models in this fleet cannot emit complete structured JSON over a large design,
and each enrichment agent must emit a large structured TechnicalDocument.
"""
from __future__ import annotations

from typing import Any

from .. import config, prompts
from ..router import ModelRouter, get_router
from ..schemas import TechnicalDocument


class EnrichmentAgent:
    """One STEP 5 enrichment role, behind a single ``document()`` method."""

    def __init__(
        self,
        agent_name: str,
        doc_type: str,
        role_prompt: str,
        router: ModelRouter | None = None,
        role: str | None = None,
    ) -> None:
        self.agent_name = agent_name
        self.doc_type = doc_type
        self.role_prompt = role_prompt
        self.router = router or get_router()
        # Role from the STEP 5 config (defaults to `fast` for all enrichment).
        self.role = role or config.ENRICH_AGENT_ROLES.get(agent_name, "fast")

    def document(self, source: str, run_id: str, max_tokens: int | None = None) -> tuple[Any, Any]:
        """Write this agent's technical document from the finalized design.

        ``source`` is the overall design + final deliverable the agent builds
        from. Returns (TechnicalDocument, LlmCall).
        """
        instructions = prompts.enrich_prompt(
            self.role_prompt, self.doc_type, prompts._ENRICH_DETAIL
        )
        content, call = self.router.call(
            self.role,
            agent=self.agent_name,
            run_id=run_id,
            input_text=source,
            output_schema=TechnicalDocument,
            instructions=instructions,
            max_tokens=max_tokens or config.ENRICH_DOC_MAX_OUTPUT,
        )
        return content, call


def build_enrichment_agents(router: ModelRouter | None = None) -> dict[str, EnrichmentAgent]:
    """Instantiate all eight enrichment agents (config.ENRICH_AGENTS is the
    source of truth for the agent/doc_type/file mapping)."""
    agents: dict[str, EnrichmentAgent] = {}
    for spec in config.ENRICH_AGENTS:
        name = spec["agent"]
        agents[name] = EnrichmentAgent(
            agent_name=name,
            doc_type=spec["doc_type"],
            role_prompt=prompts.ENRICH_ROLE_PROMPTS[name],
            router=router,
        )
    return agents
