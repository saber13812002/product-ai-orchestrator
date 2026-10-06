"""
agents/manager.py — Manager / coordinator agent (STEP 2 scope).

Current responsibility (2.6) — intentionally NARROW, does NOT run the full
product-design / critic-loop pipeline yet:
  * receive a request (Product Brief)
  * create a run (run_id + initial state)
  * determine the next step
  * dispatch the Product Analyst for STEP 1
  * persist the resulting state

In later steps the Manager becomes the full orchestrator (STEP 3+). The public
`run_smoke()` method is the STEP 2 smoke flow:
    Manager -> Product Analyst -> structured ProductAnalysis -> persist state.
"""
from __future__ import annotations

from typing import Optional

from .. import config
from ..router import ModelRouter, get_router
from ..schemas import AgentOutput, ProductAnalysis, WorkflowState
from ..state import create_state, load_state, record_call, save_state
from .product_analyst import ProductAnalyst

STEP_PRODUCT_UNDERSTANDING = "STEP1_product_understanding"


class Manager:
    """STEP 2 Manager: create a run, dispatch Product Analyst, persist state."""

    def __init__(
        self,
        router: Optional[ModelRouter] = None,
        analyst: Optional[ProductAnalyst] = None,
    ) -> None:
        self.router = router or get_router()
        self.analyst = analyst or ProductAnalyst(router=self.router)

    def next_step(self, state: WorkflowState) -> str:
        """Determine the next step for a given state (STEP 2 only knows STEP 1)."""
        if state.product_analysis is None:
            return STEP_PRODUCT_UNDERSTANDING
        # STEP 2 stops here; future steps extend this mapping.
        return "idle (STEP 2 core only)"

    def start_run(self, brief: str, run_id: Optional[str] = None) -> WorkflowState:
        """Create (and persist) a fresh run state for a Product Brief."""
        state = create_state(original_input=brief, run_id=run_id)
        state.status = "running"
        state.current_step = self.next_step(state)
        save_state(state)
        return state

    def dispatch_product_analyst(self, run_id: str) -> WorkflowState:
        """Run STEP 1 (Product Analyst) for an existing run and persist its output."""
        state = load_state(run_id)
        state.current_step = STEP_PRODUCT_UNDERSTANDING
        save_state(state)

        analysis, call = self.analyst.analyze(state.original_input, run_id=run_id)

        # Honest ledger entry (real model reported back by the router).
        record_call(state, call)

        # Record the structured output.
        analysis_dict: dict = (
            analysis.model_dump(mode="json") if isinstance(analysis, ProductAnalysis) else analysis
        )
        state.product_analysis = analysis_dict
        state.agent_outputs.append(
            AgentOutput(
                agent="product_analyst",
                role=self.analyst.role,
                model=call.model,
                content=analysis_dict,
                tokens={"input": call.input_tokens, "output": call.output_tokens, "total": call.total_tokens},
                duration_ms=call.duration_ms,
                status=call.status,
            )
        )

        state.status = "completed"
        state.current_step = "STEP1_done"
        save_state(state)
        return state

    def run_smoke(self, brief: str, run_id: Optional[str] = None) -> WorkflowState:
        """The full STEP 2 smoke flow in one call."""
        state = self.start_run(brief, run_id=run_id)
        return self.dispatch_product_analyst(state.run_id)
