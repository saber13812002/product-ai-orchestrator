"""
run.py — CLI entrypoint for the workflow.

Usage (on the 52 container, from /app):
    # STEP 2 smoke flow (Manager -> Product Analyst -> persist)
    uv run python -m workflow.run smoke --brief "یک سیستم ساده مدیریت فروش ..."

    # routing table (logical role -> real model)
    uv run python -m workflow.run routing

    # STEP 3 full 13-step pipeline (TEST MODE by default: 20k budget)
    uv run python -m workflow.run full --brief "یک سیستم ساده مدیریت فروش ..."
    uv run python -m workflow.run full --brief "..." --full   # FULL MODE: 100k budget
"""
from __future__ import annotations

import argparse
import json
import sys

from .agents.manager import Manager
from .engine import Engine
from .state import get_store


def _print_smoke(state) -> None:
    tu = state.token_usage
    print(json.dumps(
        {
            "run_id": state.run_id,
            "status": state.status,
            "current_step": state.current_step,
            "product_analysis": state.product_analysis,
            "token_usage": {
                "total_tokens": tu.total_tokens,
                "real_total_tokens": tu.real_total_tokens,
                "calls": [
                    {
                        "agent": c.agent,
                        "role": c.role,
                        "model": c.model,
                        "provider": c.provider,
                        "in": c.input_tokens,
                        "out": c.output_tokens,
                        "total": c.total_tokens,
                        "reasoning": c.reasoning_tokens,
                        "status": c.status,
                        "is_stub": c.is_stub,
                    }
                    for c in tu.calls
                ],
            },
            "state_path": str(get_store().path(state.run_id)),
        },
        indent=2,
        ensure_ascii=False,
    ))


def _print_full(state) -> None:
    tu = state.token_usage
    # Honest per-model breakdown from the ledger.
    per_model: dict[str, dict[str, int]] = {}
    for c in tu.calls:
        m = per_model.setdefault(c.model, {"calls": 0, "tokens": 0})
        m["calls"] += 1
        m["tokens"] += c.total_tokens
    summary = {
        "run_id": state.run_id,
        "status": state.status,
        "current_step": state.current_step,
        "final_iteration": state.final_iteration,
        "num_design_versions": len(state.design_versions),
        "final_scores": [q.get("final_score") for q in state.quality_scores],
        "final_review": state.final_review,
        "final_sections_present": (
            {k: (len(v) if isinstance(v, str) else 0) for k, v in
             (state.final_result or {}).get("sections", {}).items()}
            if state.final_result else None
        ),
        # STEP 5 — Design Enrichment (present only when the enrich layer ran).
        "enrichment": {
            "documents_produced": len(state.technical_documents),
            "document_types": [d.get("document_type") for d in state.technical_documents],
            "documents_dir": state.documents_dir or None,
            "completeness": state.document_completeness,
        } if (state.technical_documents or state.document_completeness) else None,
        "budget": {
            "used_real_tokens": tu.real_total_tokens,
            "total_tokens_all": tu.total_tokens,
            "num_calls": len(tu.calls),
            "num_stub_calls": sum(1 for c in tu.calls if c.is_stub),
            "per_model": per_model,
        },
        "errors": state.errors,
        "state_path": str(get_store().path(state.run_id)),
    }
    print(json.dumps(summary, indent=2, ensure_ascii=False))


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(prog="workflow")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p_smoke = sub.add_parser("smoke", help="Run the STEP 2 smoke flow (Manager -> Analyst)")
    p_smoke.add_argument("--brief", required=True, help="Raw Product Brief")

    sub.add_parser("routing", help="Print the logical-role -> real-model table")

    p_full = sub.add_parser("full", help="Run the STEP 3 full 13-step pipeline")
    p_full.add_argument("--brief", required=True, help="Raw Product Brief")
    p_full.add_argument("--full", action="store_true",
                        help="FULL MODE (100k budget). Default is TEST MODE (20k).")

    p_enrich = sub.add_parser(
        "enrich",
        help="STEP 5: full 13-step pipeline + Design Enrichment (8 documents + "
             "document-completeness gate)",
    )
    p_enrich.add_argument("--brief", required=True, help="Raw Product Brief")
    p_enrich.add_argument("--budget", type=int, default=None,
                          help="Override the STEP 5 token budget "
                               "(default: config.ENRICH_TOKEN_BUDGET)")
    p_enrich.add_argument("--iterations", type=int, default=None,
                          help="Design-loop iterations (default: "
                               "config.ENRICH_MAX_ITERATIONS)")

    args = ap.parse_args(argv)

    if args.cmd == "routing":
        print(json.dumps(Engine().routing_table(), indent=2, ensure_ascii=False))
        return 0

    if args.cmd == "smoke":
        state = Manager().run_smoke(args.brief)
        _print_smoke(state)
        return 0 if state.status == "completed" else 1

    if args.cmd == "full":
        test_mode = not args.full
        state = Engine(test_mode=test_mode).run(args.brief)
        _print_full(state)
        return 0 if state.status == "completed" else 1

    if args.cmd == "enrich":
        # STEP 5: full mode (100k design profile) + the enrichment layer, under
        # the STEP 5 budget/iteration knobs (overridable on the CLI).
        engine = Engine(
            test_mode=False,
            enrich=True,
            budget=args.budget,
            max_iterations=args.iterations,
        )
        state = engine.run(args.brief)
        _print_full(state)
        return 0 if state.status == "completed" else 1

    return 2


if __name__ == "__main__":
    sys.exit(main())
