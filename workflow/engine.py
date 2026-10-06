"""
engine.py — Multi-Model Product Orchestrator (STEP 3: full 13-step pipeline).

Flow:
    1 ProductAnalyst -> 2 MasterPromptBuilder -> 3 Manager(decompose) ->
    4 TaskExecutors(multi-model) -> 5 Merger(DesignDraft v1) ->
    [Quality-Gate Loop, max N iterations]:
        6 Critic -> 7 FixPromptGenerator -> 8 Refiner -> 9 Rebuilder(vN) ->
        10 SecondCritic -> 11 QualityGate (final>=threshold? break : loop)
    12 FinalReviewer(APPROVED/REJECTED) -> [1 iteration if REJECTED] ->
    13 FinalOutput(17 sections)

Design:
  * Orchestrates Agno Agents directly (via the Router), NOT the AgentOS HTTP
    run endpoint. Gives precise control over the pipeline, per-step persistence,
    the quality-gate loop, and per-call token accounting.
  * Budget enforcement: before each LLM call the engine checks whether the
    estimate fits within the run budget (with a reserve for the final step).
    If not, it marks the run `budget_exhausted` and finalizes gracefully.
  * State persisted after EVERY step. Token ledger is honest (real model read
    from run metrics; stubs excluded from real totals).

The existing AgentOS service on :7777 is untouched.
"""
from __future__ import annotations

import json as _jsonmod
from typing import Any, Optional

from pydantic import BaseModel

from . import config, prompts
from .agents.product_analyst import ProductAnalyst
from .agents.enrichment import build_enrichment_agents
from .agents.document_manager import DocumentManager
from .router import ModelRouter
from .schemas import (
    AgentOutput,
    CriticResult,
    EnrichmentScore,
    FinalOutput,
    FinalReview,
    MasterPrompt,
    PatchList,
    PatchVerification,
    ProductAnalysis,
    QualityScores,
    TaskList,
    TechnicalDocument,
    WorkflowState,
)
from .state import create_state, get_store, load_state, record_call, save_state


class BudgetExhausted(Exception):
    def __init__(self, step: str):
        self.step = step
        super().__init__(f"budget exhausted at {step}")


class StepFailed(Exception):
    """A pipeline step produced unusable output (e.g. truncated structured JSON)."""


class Engine:
    def __init__(
        self,
        router: Optional[ModelRouter] = None,
        *,
        budget: Optional[int] = None,
        max_iterations: Optional[int] = None,
        threshold: Optional[int] = None,
        test_mode: Optional[bool] = None,
        enrich: bool = False,
    ) -> None:
        self.test_mode = bool(test_mode) if test_mode is not None else config.TEST_MODE
        # STEP 5 — the enrichment run is a distinct profile: it runs the SAME
        # 13-step pipeline but with FEWER design-loop iterations (doc quality >
        # iterations) under a LARGER budget to fit the 8-document pass. When
        # `enrich` is set and no explicit budget/iterations are given, use the
        # STEP 5 knobs (they override the full-mode defaults only in that case).
        self.enrich = bool(enrich)
        budget_default = config.TEST_TOKEN_BUDGET if self.test_mode else (
            config.ENRICH_TOKEN_BUDGET if self.enrich else config.FULL_TOKEN_BUDGET
        )
        iter_default = config.TEST_MAX_ITERATIONS if self.test_mode else (
            config.ENRICH_MAX_ITERATIONS if self.enrich else config.FULL_MAX_ITERATIONS
        )
        self.budget = budget if budget is not None else budget_default
        self.max_iterations = max_iterations if max_iterations is not None else iter_default
        self.threshold = threshold if threshold is not None else config.GATE_THRESHOLD
        self.reserve = config.BUDGET_RESERVE
        # Mode-aware profiles: frugal for the 20k budget smoke test, roomy for
        # the 100k full run (substantive drafts + headroom for the loop).
        self._caps = config.STEP_MAX_OUTPUT_TEST if self.test_mode else config.STEP_MAX_OUTPUT_FULL
        self._context_chars = (config.CONTEXT_RESEND_CHARS_TEST if self.test_mode
                               else config.CONTEXT_RESEND_CHARS_FULL)
        self._merge_chars = (config.MERGE_TASK_EXCERPT_CHARS_TEST if self.test_mode
                             else config.MERGE_TASK_EXCERPT_CHARS_FULL)
        # STEP 4.4 — how many (targeted) issues the critic may report per pass.
        self.max_issues = config.MAX_CRITIC_ISSUES
        self.router = router or ModelRouter()
        self.analyst = ProductAnalyst(router=self.router)
        # STEP 5 — the enrichment agents are lazily built only when used, so a
        # normal (non-enrich) run never instantiates them. (Named `_cache` so it
        # does not shadow the _enrich_agents() method of the same base name.)
        self._enrich_agents_cache: Optional[dict] = None

    # -- mode-aware accessors -------------------------------------------- #
    def _cap(self, step: str, max_tokens: Optional[int] = None) -> int:
        return max_tokens or self._caps.get(step, config.DEFAULT_MAX_OUTPUT)

    def _context(self, text: str) -> str:
        """Bounded context for loop steps (critic/refiner see a truncated design)."""
        return _short(text, self._context_chars)

    def _gate_context(self, text: str) -> str:
        """STEP 4.2 — the FULL design for the Quality Gate and the critics, with a
        context-window guard. The design in this fleet is ~2.8k tokens, far inside
        the Qwen3-27B window, so in practice this returns the design in full. Only
        if the design ever exceeded the guard do we fall back — and to a
        section-aware prioritized view (important sections first), NOT a blind
        head-truncation, so no important section is silently dropped.
        """
        budget_chars = int(config.GATE_MAX_INPUT_TOKENS * config.CHARS_PER_TOKEN)
        if len(text) <= budget_chars:
            return text
        return _prioritized_view(text, budget_chars)

    def _second_critic_context(self, text: str) -> str:
        """STEP 4.9 — bounded, section-aware view for the CROSS-CHECK second
        critic only. It is not the scorer (the full-context Quality Gate is), so
        we cap the design it re-reads to cut the loop's biggest avoidable input
        cost. Section-aware (important sections first), never a blind head-trunc.
        """
        budget_chars = int(config.SECOND_CRITIC_MAX_INPUT_TOKENS * config.CHARS_PER_TOKEN)
        if len(text) <= budget_chars:
            return text
        return _prioritized_view(text, budget_chars)

    def _instr(self, step: str, template: str, **kw) -> str:
        """Format a prompt template, injecting the mode-aware {detail} directive."""
        return template.format(detail=prompts.detail(step, self.test_mode), **kw)

    # ===================================================================== #
    # Budget guard
    # ===================================================================== #
    def _headroom(self, state: WorkflowState) -> int:
        return self.budget - state.used_real_tokens()

    def _fits(self, state: WorkflowState, est: int) -> bool:
        return self._headroom(state) >= max(est, 0)

    def _call(
        self,
        state: WorkflowState,
        *,
        role: str,
        agent: str,
        step: str,
        input_text: str,
        schema: Optional[type] = None,
        instructions: Optional[str] = None,
        max_tokens: Optional[int] = None,
    ):
        cap = self._cap(step, max_tokens)
        # Soft pre-check: reserve keeps the final step reachable.
        est = cap + 800  # cap (output) + rough input allowance
        if not self._fits(state, est):
            state.status = "budget_exhausted"
            state.current_step = f"budget_exhausted@{step}"
            state.errors.append(
                f"budget_exhausted at {step}: headroom={self._headroom(state)} < est={est} "
                f"(used={state.used_real_tokens()}/{self.budget})"
            )
            save_state(state)
            raise BudgetExhausted(step)

        content, call = self.router.call(
            role,
            agent=agent,
            run_id=state.run_id,
            input_text=input_text,
            output_schema=schema,
            instructions=instructions,
            max_tokens=cap,
        )
        # Record the call FIRST: it genuinely consumed these tokens, even if the
        # output below turns out unusable. This keeps the ledger honest.
        record_call(state, call)
        # Guarantee a proper typed value for structured steps. Agno returns a raw
        # STRING when its JSON parser gives up (e.g. model hit max_tokens
        # mid-object); we repair/validate so one truncated field can't corrupt
        # the whole run, and raise StepFailed if it's truly unrecoverable.
        if schema is not None:
            content = _ensure_structured(content, schema)
        state.agent_outputs.append(
            AgentOutput(
                agent=agent,
                role=role,
                model=call.model,
                content=(content.model_dump() if hasattr(content, "model_dump") else content),
                tokens={"input": call.input_tokens, "output": call.output_tokens, "total": call.total_tokens},
                duration_ms=call.duration_ms,
                status=call.status,
            )
        )
        save_state(state)
        return content

    def _role(self, name: str) -> str:
        return config.AGENT_ROLES.get(name, "fast")

    # ===================================================================== #
    # Steps 1-5 (build the initial Design Draft v1)
    # ===================================================================== #
    def _step1(self, s: WorkflowState) -> None:
        s.current_step = "STEP1_product_understanding"
        save_state(s)
        analysis, call = self.analyst.analyze(s.original_input, run_id=s.run_id)
        record_call(s, call)
        s.product_analysis = (
            analysis.model_dump() if isinstance(analysis, ProductAnalysis) else analysis
        )
        s.agent_outputs.append(
            AgentOutput(agent="product_analyst", role=self.analyst.role, model=call.model,
                        content=s.product_analysis,
                        tokens={"input": call.input_tokens, "output": call.output_tokens, "total": call.total_tokens})
        )
        save_state(s)

    def _step2(self, s: WorkflowState) -> None:
        s.current_step = "STEP2_master_prompt"
        save_state(s)
        mp = self._call(
            s, role=self._role("master_prompt_builder"), agent="master_prompt_builder",
            step="master_prompt", input_text=_json(s.product_analysis),
            schema=MasterPrompt, instructions=self._instr("master_prompt", prompts.MASTER_PROMPT_BUILDER),
        )
        s.master_prompt = mp.model_dump() if isinstance(mp, MasterPrompt) else mp
        save_state(s)

    def _step3(self, s: WorkflowState) -> None:
        s.current_step = "STEP3_task_decomposition"
        save_state(s)
        tl = self._call(
            s, role=self._role("manager"), agent="manager",
            step="task_decomposition", input_text=_json(s.master_prompt),
            schema=TaskList, instructions=prompts.MANAGER_TASK_DECOMPOSITION,
        )
        tasks = tl.tasks if isinstance(tl, TaskList) else (tl.get("tasks") or [])
        s.tasks = [t.model_dump() if hasattr(t, "model_dump") else t for t in tasks]
        save_state(s)

    def _step4(self, s: WorkflowState) -> dict[str, str]:
        s.current_step = "STEP4_multi_model_execution"
        save_state(s)
        outputs: dict[str, str] = {}
        for t in s.tasks:
            tid = t.get("task_id", "")
            role = config.TASK_MODEL_HINTS.get(tid) or t.get("assigned_model") or "fast"
            role = _safe_role(self.router, role)
            section = t.get("objective", "")
            ctx = (t.get("context", "") or "")[:400]
            prompt = (
                f"TASK {tid}: {section}\nContext: {ctx}\n"
                f"Expected output: {t.get('expected_output', '')}\nProduce the deliverable."
            )
            content = self._call(
                s, role=role, agent=f"task_{tid}", step="task_exec",
                input_text=prompt, instructions=self._instr("task_exec", prompts.TASK_EXECUTOR, section=section),
                max_tokens=min(int(t.get("token_budget") or self._cap("task_exec")),
                               self._cap("task_exec")),
            )
            outputs[tid] = _text(content)
            save_state(s)
        return outputs

    def _step5(self, s: WorkflowState, task_outputs: dict[str, str]) -> None:
        s.current_step = "STEP5_merge"
        save_state(s)
        body = "\n\n".join(
            f"### {tid}\n{_short(txt, self._merge_chars)}"
            for tid, txt in task_outputs.items()
        )
        draft = self._call(
            s, role=self._role("design_merger"), agent="design_merger",
            step="merge", input_text=body, instructions=self._instr("merge", prompts.DESIGN_MERGER),
        )
        s.design_versions.append({"version": 1, "content": _text(draft), "built_from": "tasks"})
        save_state(s)

    # ===================================================================== #
    # Quality-gate loop (steps 6-11), max N iterations  [STEP 4: improved]
    # ===================================================================== #
    def _quality_gate_loop(self, s: WorkflowState) -> None:
        for it in range(1, self.max_iterations + 1):
            current = s.design_versions[-1]["content"] if s.design_versions else ""
            if not current:
                return

            # STEP 6 — targeted Critic (FULL design + shared rubric)
            s.current_step = f"ITER{it}_STEP6_critic"
            save_state(s)
            crit = self._call(
                s, role=self._role("critic"), agent="critic", step="critic",
                input_text=self._gate_context(current), schema=CriticResult,
                instructions=prompts.judge_prompt(prompts.CRITIC, self.test_mode,
                                                  max_issues=self.max_issues),
            )
            crit_d = _crit_dict(crit)
            s.critic_results.append({"iteration": it, "model": "critic", **crit_d})
            save_state(s)
            actionable = self._actionable(crit_d)

            # STEP 7-9 — fixes -> patches -> rebuild, only when there is
            # something BLOCKER/HIGH to close (else skip the rebuild: it would
            # just re-emit the same design and waste tokens).
            fixes: list[dict] = []
            patch_d: list[dict] = []
            if actionable:
                s.current_step = f"ITER{it}_STEP7_fixgen"
                save_state(s)
                fixes = self._run_fixgen(s, it, current, actionable)
                if fixes:
                    s.current_step = f"ITER{it}_STEP8_refiner"
                    save_state(s)
                    patch_d = self._run_refiner(s, it, current, fixes)
                if patch_d:
                    s.current_step = f"ITER{it}_STEP9_rebuild"
                    save_state(s)
                    old = current
                    self._run_rebuild(s, patch_d)
                    # STEP 4.7 — Design Integrity Check (deterministic)
                    self._integrity_check(s, it, old, s.design_versions[-1]["content"], patch_d)
                    # STEP 4.6 — Patch Verifier (+ at most 1 retry per failing patch)
                    self._verify_patches(s, it, fixes, patch_d)

            # STEP 10 — Second Critic (different model; FULL design + rubric).
            # It is a CROSS-CHECK, not the gate: the fast Quality Gate below is
            # the authoritative scorer that drives the loop, so this opinion is
            # recorded for the report but its rare truncation must not fail a run
            # (STEP 4.9 — the deep/thinking second-critic can overflow its output
            # budget on reasoning; a step="second_critic" cap gives it room).
            s.current_step = f"ITER{it}_STEP10_second_critic"
            save_state(s)
            try:
                crit2 = self._call(
                    s, role=self._role("second_critic"), agent="second_critic", step="second_critic",
                    input_text=self._second_critic_context(s.design_versions[-1]["content"]),
                    schema=CriticResult,
                    instructions=prompts.judge_prompt(prompts.CRITIC, self.test_mode,
                                                      max_issues=self.max_issues),
                )
            except StepFailed as e:
                s.errors.append(
                    f"second_critic(iter{it}) non-fatal: {e} — recorded, continuing to the gate"
                )
                crit2_d = {"issues": [], "degraded": True}
            else:
                crit2_d = _crit_dict(crit2)
            s.critic_results.append({"iteration": it, "model": "second_critic", **crit2_d})
            save_state(s)

            # STEP 11 — Quality Gate (FULL design; final_score COMPUTED, not free)
            s.current_step = f"ITER{it}_STEP11_quality_gate"
            save_state(s)
            qs = self._run_gate(s, it)
            if qs["passed"]:
                break  # quality gate met

    # -- STEP 4 loop helpers ------------------------------------------------ #
    def _actionable(self, crit_d: dict) -> list[dict]:
        """BLOCKER/HIGH issues only, capped at `max_issues` (the loop chases these)."""
        out = []
        for iss in crit_d.get("issues", []):
            if not isinstance(iss, dict):
                continue
            sev = (iss.get("severity") or "HIGH").upper()
            if sev in config.ACTIONABLE_SEVERITIES:
                out.append({"id": iss.get("id", ""), "severity": sev,
                            "section": iss.get("section", ""),
                            "description": iss.get("description", "")})
            if len(out) >= self.max_issues:
                break
        return out

    def _run_fixgen(self, s, it, current, actionable):
        fix = self._call(
            s, role=self._role("fix_prompt_generator"), agent="fix_prompt_generator", step="fixgen",
            input_text=_json({"actionable_issues": actionable, "design": self._context(current)}),
            schema=None, instructions=prompts.FIX_PROMPT_GENERATOR,
        )
        fixes = [f for f in _parse_fixlist(fix)
                 if (f.get("severity", "HIGH").upper()) in config.ACTIONABLE_SEVERITIES]
        fixes = fixes[:self.max_issues]
        s.fix_prompts.extend(fixes)
        save_state(s)
        return fixes

    def _run_refiner(self, s, it, current, fixes):
        pl = self._call(
            s, role=self._role("refiner"), agent="refiner", step="refine",
            input_text=_json({"fix_prompts": fixes, "design": self._context(current)}),
            schema=PatchList, instructions=prompts.REFINER,
        )
        patches = pl.patches if isinstance(pl, PatchList) else (pl.get("patches") or [])
        patch_d = [p.model_dump() if hasattr(p, "model_dump") else p for p in patches]
        # Backfill fix_id by position (one patch per fix, in order) so the Patch
        # Verifier can match each check to its fix even if the model omits it.
        for i, p in enumerate(patch_d):
            if not p.get("fix_id") and i < len(fixes):
                p["fix_id"] = fixes[i].get("id", "")
        s.patches.extend(patch_d)
        save_state(s)
        return patch_d

    def _run_rebuild(self, s, patch_d) -> None:
        current = s.design_versions[-1]["content"]
        newv = len(s.design_versions) + 1
        rebuilt = self._call(
            s, role=self._role("rebuilder"), agent="rebuilder", step="rebuild",
            input_text=_json({"design": current, "patches": patch_d}),
            schema=None, instructions=self._instr("rebuild", prompts.REBUILDER),
        )
        s.design_versions.append(
            {"version": newv, "content": _text(rebuilt), "built_from": f"v{newv-1}+patches"})
        save_state(s)

    # STEP 4.6 — verify each patch's acceptance criteria; retry only the
    # FAILING patches once (never restart the whole workflow).
    def _verify_patches(self, s, it, fixes, patch_d) -> None:
        ver = self._verify(s, s.design_versions[-1]["content"], patch_d)
        s.patch_verifications.append(ver)
        fail_ids = {c.get("fix_id") for c in ver.get("checks", []) if c.get("status") != "PASS"}
        if not fail_ids:
            return
        # 1 retry: re-refine only the failing fixes, rebuild on top, re-verify.
        failing = [f for f in fixes if f.get("id") in fail_ids]
        base = s.design_versions[-1]["content"]
        pl = self._call(
            s, role=self._role("refiner"), agent="refiner", step="refine",
            input_text=_json({"fix_prompts": failing, "design": self._context(base)}),
            schema=PatchList, instructions=prompts.REFINER,
        )
        patches = pl.patches if isinstance(pl, PatchList) else (pl.get("patches") or [])
        re_patch_d = [p.model_dump() if hasattr(p, "model_dump") else p for p in patches]
        if re_patch_d:
            s.patches.extend(re_patch_d)
            rebuilt = self._call(
                s, role=self._role("rebuilder"), agent="rebuilder", step="rebuild",
                input_text=_json({"design": base, "patches": re_patch_d}),
                schema=None, instructions=self._instr("rebuild", prompts.REBUILDER),
            )
            s.design_versions[-1]["content"] = _text(rebuilt)
            s.design_versions[-1]["built_from"] += "+verify_retry"
            self._integrity_check(s, it, base, s.design_versions[-1]["content"], re_patch_d)
            ver2 = self._verify(s, s.design_versions[-1]["content"], re_patch_d)
            s.patch_verifications.append(ver2)
        save_state(s)

    def _verify(self, s, design, patches) -> dict:
        checks_input = [{
            "fix_id": p.get("fix_id") or p.get("id", ""),
            "section": p.get("section", ""),
            "acceptance_criteria": p.get("acceptance_criteria") or [],
        } for p in patches]
        if not checks_input:
            return {"iteration": None, "checks": [], "overall_pass": True, "note": "no patches"}
        ver = self._call(
            s, role=self._role("patch_verifier"), agent="patch_verifier", step="verify",
            input_text=_json({"design": self._gate_context(design), "patches": checks_input}),
            schema=PatchVerification, instructions=prompts.PATCH_VERIFIER,
        )
        ver_d = ver.model_dump() if isinstance(ver, PatchVerification) else ver
        return ver_d

    # STEP 4.7 — deterministic Design Integrity Check after a rebuild.
    def _integrity_check(self, s, it, old, new, patches) -> dict:
        import re
        hb = set(re.findall(r"^#{1,4}\s+(.+?)\s*$", old, re.M))
        ha = set(re.findall(r"^#{1,4}\s+(.+?)\s*$", new, re.M))
        lost = sorted(hb - ha)
        applied, missing = [], []
        for p in patches:
            sig = _signature(p.get("patch", ""))
            (applied if (sig and sig.lower() in new.lower()) else missing).append(
                p.get("id") or p.get("fix_id") or "")
        shrink = len(new) < len(old) * 0.9
        result = {
            "iteration": it, "sections_before": len(hb), "sections_after": len(ha),
            "sections_lost": lost[:12], "patches_applied": applied, "patches_missing": missing,
            "size_before": len(old), "size_after": len(new), "shrank": shrink,
            "ok": bool(not lost and not missing and not shrink),
        }
        s.design_integrity.append(result)
        save_state(s)
        return result

    def _run_gate(self, s, it) -> dict:
        design = s.design_versions[-1]["content"]
        qs = self._call(
            s, role=self._role("quality_gate"), agent="quality_gate", step="gate",
            input_text=self._gate_context(design), schema=QualityScores,
            instructions=prompts.judge_prompt(prompts.QUALITY_GATE, self.test_mode),
        )
        qs_d = _clamp_scores(_scores_dict(qs))
        final = _compute_final(qs_d)
        qs_d["final_score"] = final
        if not qs_d.get("improvement_targets"):
            dims = [(k, v) for k, v in qs_d.items() if k.endswith("_score") and k != "final_score"]
            qs_d["improvement_targets"] = [k for k, _ in sorted(dims, key=lambda kv: kv[1])[:2]]
        qs_d["iteration"] = it
        qs_d["passed"] = final >= self.threshold
        s.quality_scores.append(qs_d)
        save_state(s)
        return qs_d

    # ===================================================================== #
    # Step 12 (final review) + 13 (final output)
    # ===================================================================== #
    def _step12(self, s: WorkflowState) -> bool:
        s.current_step = "STEP12_final_review"
        save_state(s)
        design = s.design_versions[-1]["content"] if s.design_versions else ""
        rev = self._call(
            s, role=self._role("final_reviewer"), agent="final_reviewer",
            step="final_review", input_text=design,   # FULL design — must judge the whole thing
            schema=FinalReview, instructions=prompts.judge_prompt(prompts.FINAL_REVIEWER, self.test_mode),
        )
        rev_d = rev.model_dump() if isinstance(rev, FinalReview) else rev
        s.final_review = rev_d
        save_state(s)
        # Both APPROVED and APPROVED_WITH_NOTES pass; only REJECTED triggers a
        # corrective iteration (matches STEP 4.8: reject only on a blocking issue).
        return rev_d.get("verdict") in ("APPROVED", "APPROVED_WITH_NOTES")

    def _step13(self, s: WorkflowState) -> None:
        s.current_step = "STEP13_final_output"
        save_state(s)
        design = s.design_versions[-1]["content"] if s.design_versions else ""
        fo = self._call(
            s, role=self._role("final_output"), agent="final_output",
            step="final_output", input_text=design,   # FULL design — emit the whole deliverable
            schema=FinalOutput, instructions=self._instr("final_output", prompts.FINAL_OUTPUT),
        )
        fo_d = fo.model_dump() if isinstance(fo, FinalOutput) else fo
        s.final_result = {
            "iteration": s.final_iteration,
            "version": s.design_versions[-1]["version"] if s.design_versions else 0,
            "final_score": (s.quality_scores[-1].get("final_score") if s.quality_scores else None),
            "sections": fo_d,
        }
        save_state(s)

    # ===================================================================== #
    # STEP 14 — Design Enrichment (5.2-5.6). NEW layer, fully additive:
    # the 13-step pipeline above is untouched. This runs on the FINALIZED
    # design + final deliverable, produces 8 deep structured documents,
    # writes the 10-file bundle (5.4), and scores per-doc completeness (5.6).
    # ===================================================================== #
    def _enrich_agents(self) -> dict:
        if self._enrich_agents_cache is None:
            self._enrich_agents_cache = build_enrichment_agents(router=self.router)
        return self._enrich_agents_cache

    def _enrich_source(self, s: WorkflowState) -> str:
        """The source of truth each enrichment agent deepens: the FINAL design
        (kept whole) + the final deliverable, capped as a safety net. The design
        goes first so it is never the part that gets cut."""
        design = s.design_versions[-1]["content"] if s.design_versions else ""
        fo = (s.final_result or {}).get("sections", {}) or {}
        final_text = _json(fo) if fo else ""
        return _short(f"{design}\n\n=== FINAL DELIVERABLE (17 sections) ===\n{final_text}",
                      config.ENRICH_SOURCE_CHARS)

    def _step14_enrichment(self, s: WorkflowState) -> None:
        """Run the 8 enrichment agents + Document Manager + completeness gate.

        Best-effort: budget exhaustion here is NON-FATAL (the primary design
        deliverable already completed). We write whatever documents we produced
        and score the ones we have.
        """
        agents = self._enrich_agents()
        source = self._enrich_source(s)

        s.current_step = "STEP14_enrichment"
        save_state(s)
        docs: list[TechnicalDocument] = []
        for spec in config.ENRICH_AGENTS:
            name = spec["agent"]
            agent = agents[name]   # the 8 agents are the source of truth for role/prompt
            # Honest pre-check: this call really re-reads the (large) source.
            est = config.ENRICH_DOC_MAX_OUTPUT + int(len(source) / config.CHARS_PER_TOKEN)
            if not self._fits(s, est):
                s.errors.append(f"enrichment stopped at {name}: budget "
                                f"headroom {self._headroom(state=s)} < est {est}")
                break
            s.current_step = f"STEP14_enrich_{name}"
            save_state(s)
            try:
                doc = self._call(
                    s, role=agent.role, agent=name,
                    step="enrich_doc", input_text=source, schema=TechnicalDocument,
                    instructions=prompts.enrich_prompt(
                        agent.role_prompt, agent.doc_type, prompts._ENRICH_DETAIL),
                    max_tokens=config.ENRICH_DOC_MAX_OUTPUT,
                )
            except BudgetExhausted:
                break
            if not isinstance(doc, TechnicalDocument):
                s.errors.append(f"enrich_{name}: unusable output, skipped")
                continue
            # 5.5 — make the decision's source explicit and traceable.
            for d in doc.decisions:
                if not d.source:
                    d.source = name
            if agent.doc_type not in (doc.document_type or ""):
                doc.document_type = agent.doc_type
            docs.append(doc)
            save_state(s)

        # Persist the structured documents (5: state includes the produced docs).
        s.technical_documents = [d.model_dump() for d in docs]
        save_state(s)

        # 5.4 — Document Manager writes the 10-file bundle + traceability index.
        if docs:
            s.current_step = "STEP14_document_manager"
            fo = (s.final_result or {}).get("sections", {}) or {}
            dm = DocumentManager(s.run_id)
            try:
                ddir = dm.write(
                    docs,
                    product_spec=fo.get("product_specification", ""),
                    system_architecture=fo.get("system_architecture", ""),
                )
                s.documents_dir = str(ddir)
            except Exception as e:  # noqa: BLE001 - writing files must not fail the run
                s.errors.append(f"document_manager write failed: {type(e).__name__}: {e}")
            save_state(s)

        # 5.6 — the NEW document-completeness Quality Gate (per-doc + overall).
        if docs:
            s.current_step = "STEP14_doc_gate"
            save_state(s)
            gate_est = config.ENRICH_GATE_MAX_OUTPUT + int(
                len(self._doc_gate_input(docs)) / config.CHARS_PER_TOKEN)
            if self._fits(s, gate_est):
                try:
                    s.document_completeness = self._run_doc_gate(s, docs)
                except BudgetExhausted:
                    s.errors.append("doc_gate skipped: budget exhausted")
            else:
                s.errors.append("doc_gate skipped: insufficient budget headroom")
            save_state(s)

    def _doc_gate_input(self, docs: list[TechnicalDocument]) -> str:
        """A per-document digest the completeness gate scores: type, summary,
        structural counts, and a substantive sample of each document's body —
        enough to judge real completeness without a 20k-token re-read."""
        per_doc = 7000
        blocks = []
        for d in docs:
            body = (d.architecture or "")[:per_doc]
            blocks.append(
                f"### {d.document_type}\n"
                f"summary: {d.summary}\n"
                f"decisions: {len(d.decisions)} | components: {len(d.components)} | "
                f"risks: {len(d.risks)} | open_questions: {len(d.open_questions)} | "
                f"implementation_notes: {len(d.implementation_notes)}\n"
                f"architecture (sample):\n{body}"
            )
        return "\n\n".join(blocks)

    def _run_doc_gate(self, s: WorkflowState, docs: list[TechnicalDocument]) -> dict:
        """5.6 — score each document's completeness; the overall is COMPUTED as
        the equal-weighted mean (never a free LLM number)."""
        raw = self._call(
            s, role=config.ENRICH_AGENT_ROLES.get("document_gate", "fast"),
            agent="document_gate", step="enrich_gate",
            input_text=self._doc_gate_input(docs), schema=EnrichmentScore,
            instructions=prompts.ENRICH_DOCUMENT_GATE,
            max_tokens=config.ENRICH_GATE_MAX_OUTPUT,
        )
        score_d = raw.model_dump() if isinstance(raw, EnrichmentScore) else dict(raw)
        dims = {k: _clamp01(score_d.get(k)) for k in EnrichmentScore.DIMENSION_KEYS}
        overall = int(round(sum(dims.values()) / len(dims))) if dims else 0
        score_d.update(dims)
        score_d["overall_score"] = overall
        score_d["passed"] = overall >= config.ENRICH_GATE_THRESHOLD
        score_d["documents_scored"] = len(docs)
        score_d.setdefault("gaps", [])
        s.document_completeness = score_d
        save_state(s)
        return score_d

    # ===================================================================== #
    # run()
    # ===================================================================== #
    def run(self, brief: str, run_id: Optional[str] = None) -> WorkflowState:
        s = create_state(brief, run_id=run_id)
        s.status = "running"
        try:
            self._step1(s)
            self._step2(s)
            self._step3(s)
            task_outputs = self._step4(s)
            self._step5(s, task_outputs)

            # Quality-gate loop
            self._quality_gate_loop(s)
            s.final_iteration = len(s.quality_scores)

            # Final review (+ 1 corrective iteration if REJECTED)
            approved = self._step12(s)
            if not approved and s.status != "budget_exhausted" and self._design_versions_have_room(s):
                # one corrective iteration: critic -> fixgen -> refiner -> rebuild
                # A correction that truncates/fails is non-fatal: keep the current
                # design and proceed to the final output rather than crashing.
                try:
                    self._corrective_iteration(s)
                    self._step12(s)
                except (BudgetExhausted, StepFailed):
                    pass

            self._step13(s)
            if s.status != "budget_exhausted":
                s.status = "completed"
                s.current_step = "completed"

            # STEP 14 — Design Enrichment (5.2-5.6). NEW additive layer: turns
            # the finalized design into 8 deep documents + a completeness gate.
            # Runs only when `enrich` is set; NON-FATAL (the 17-section design
            # deliverable above already completed), so a hiccup here can never
            # break the primary 13-step pipeline. Enrichment is additive, so a
            # budget hit DURING it (which _call writes as status=budget_exhausted
            # before raising) must not retroactively re-mark the whole run — we
            # restored the "completed" status the primary deliverable earned.
            if self.enrich and s.status == "completed" and s.design_versions:
                pre_status = s.status
                try:
                    self._step14_enrichment(s)
                except BudgetExhausted:
                    pass  # marked + persisted in _call; docs so far are kept
                except Exception as e:  # noqa: BLE001
                    s.errors.append(f"enrichment (non-fatal): {type(e).__name__}: {e}")
                if pre_status == "completed":
                    s.status = "completed"
                    s.current_step = "completed_enriched" if s.technical_documents else "completed"
                save_state(s)
        except BudgetExhausted:
            pass  # already marked + persisted in _call
        except StepFailed as e:
            s.status = "failed"
            s.errors.append(str(e))
        except Exception as e:  # noqa: BLE001 - record and finalize
            s.status = "failed"
            s.errors.append(f"{type(e).__name__}: {e}")
        save_state(s)
        return get_store().load(s.run_id)

    def _design_versions_have_room(self, s: WorkflowState) -> bool:
        return self._fits(s, self._cap("rebuild") + 800)

    def _corrective_iteration(self, s: WorkflowState) -> None:
        current = s.design_versions[-1]["content"] if s.design_versions else ""
        it = s.final_iteration
        s.current_step = "FINAL_corrective_iteration"
        save_state(s)
        crit = self._call(s, role=self._role("critic"), agent="critic", step="critic",
                          input_text=self._gate_context(current), schema=CriticResult,
                          instructions=prompts.judge_prompt(prompts.CRITIC, self.test_mode,
                                                            max_issues=self.max_issues))
        crit_d = _crit_dict(crit)
        s.critic_results.append({"iteration": it, "model": "critic_final", **crit_d})
        save_state(s)
        actionable = self._actionable(crit_d)
        fixes = self._run_fixgen(s, it, current, actionable) if actionable else []
        if not fixes:
            return
        patch_d = self._run_refiner(s, it, current, fixes)
        if not patch_d:
            return
        old = current
        self._run_rebuild(s, patch_d)
        self._integrity_check(s, it, old, s.design_versions[-1]["content"], patch_d)
        self._verify_patches(s, it, fixes, patch_d)

    # convenience
    def routing_table(self) -> dict[str, str]:
        return self.router.resolutions()


# ========================================================================= #
# helpers
# ========================================================================= #
def _json(obj: Any) -> str:
    import json

    return json.dumps(obj, ensure_ascii=False)


def _text(content: Any) -> str:
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if hasattr(content, "model_dump"):
        import json

        return json.dumps(content.model_dump(), ensure_ascii=False)
    return str(content)


def _short(text: str, limit: Optional[int] = None) -> str:
    """Truncate to `limit` chars; a `None` limit means no truncation (full text)."""
    if limit is None or len(text) <= limit:
        return text
    return text[:limit] + "\n[...truncated...]"


def _clamp_scores(d: dict[str, Any]) -> dict[str, Any]:
    """Clamp every dimension score (and final) into [0, 100], defaulting to 0."""
    for k in config.QUALITY_DIMENSIONS + ["final_score"]:
        try:
            d[k] = max(0, min(100, int(d.get(k, 0))))
        except (TypeError, ValueError):
            d[k] = 0
    return d


def _clamp01(v: Any) -> int:
    """STEP 5.6 — clamp a completeness score into [0, 100], defaulting to 0."""
    try:
        return max(0, min(100, int(v)))
    except (TypeError, ValueError):
        return 0


def _scores_dict(qs: Any) -> dict[str, Any]:
    """Normalize a QualityScores (or dict) to a plain dict for storage."""
    if isinstance(qs, dict):
        return dict(qs)
    if hasattr(qs, "model_dump"):
        return qs.model_dump()
    return dict(qs)


def _compute_final(d: dict[str, Any]) -> int:
    """STEP 4.3 — final_score is the WEIGHTED MEAN of the dimension scores.

    This is what the gate actually compares against the threshold — never a free
    LLM number. Weights come from config.QUALITY_WEIGHTS and are renormalized
    over the dimensions present, so a partial/legacy score dict still computes.
    """
    num = 0.0
    den = 0.0
    for dim, w in config.QUALITY_WEIGHTS.items():
        if dim in d:
            num += w * d[dim]
            den += w
    return int(round(num / den)) if den else 0


def _crit_dict(crit: Any) -> dict[str, Any]:
    """Normalize a CriticResult to a dict with `issues` as a list of issue dicts."""
    d = crit.model_dump() if hasattr(crit, "model_dump") else dict(crit)
    if not isinstance(d.get("issues"), list):
        d["issues"] = []
    return d


def _signature(text: str) -> str:
    """A short, distinctive fingerprint of a patch (for the integrity check)."""
    t = " ".join(text.lower().split())
    return t[:48]


def _prioritized_view(text: str, budget_chars: int) -> str:
    """SECTION-AWARE fallback when the design is bigger than the gate budget.

    We split on markdown headers and keep the important sections first (the
    security / database / api / consistency / testing sections that carry the
    most weight) rather than blind head-truncation that would silently drop the
    tail. In practice the design (~2.8k tokens) is far under the budget, so this
    is a safety net, not the common path.
    """
    import re

    lines = text.splitlines()
    parts: list[tuple[str, list[str]]] = []
    cur_hdr, cur = "", []
    for ln in lines:
        if re.match(r"^#{1,4}\s+", ln):
            if cur_hdr or cur:
                parts.append((cur_hdr, cur))
            cur_hdr, cur = ln, []
        else:
            cur.append(ln)
    if cur_hdr or cur:
        parts.append((cur_hdr, cur))
    priority = ("security", "auth", "database", "data", "api", "test",
                "observ", "deployment", "consistency", "tenant")
    def rank(p):
        h = p[0].lower()
        return min((i for i, k in enumerate(priority) if k in h), default=len(priority))
    ordered = sorted(parts, key=rank)
    out, used = [], 0
    for hdr, body in ordered:
        chunk = (hdr + "\n" + "\n".join(body)).strip()
        if not chunk:
            continue
        if used + len(chunk) + 2 > budget_chars:
            room = budget_chars - used
            if room > 120:
                out.append(chunk[:room])
            break
        out.append(chunk)
        used += len(chunk) + 2
    return "\n\n".join(out) + "\n\n[...prioritized: important sections first...]"


def _safe_role(router: ModelRouter, role: str) -> str:
    return role if role in router.roles else "fast"


def _parse_fixlist(content: Any) -> list[dict[str, Any]]:
    """Parse a fix-prompt-list output (raw JSON string, no schema) into atomic fixes.

    Each fix is normalized to the STEP 4.5 shape: id, severity, target_section,
    problem, required_change, acceptance_criteria (list), prompt. Accepts the new
    fields and the legacy (problem/prompt/target_section) shape so a model that
    ignores the new prompt still yields usable fixes.
    """
    import json

    data = content
    if isinstance(data, str):
        txt = data.strip()
        if txt.startswith("```"):
            txt = txt.strip("`")
            if txt.startswith("json"):
                txt = txt[4:]
            txt = txt.strip()
        # Try the raw text, then a best-effort repair (fixgen can hit its cap
        # mid-JSON); keep the first candidate that parses. Only if BOTH fail do
        # we fall back to a single coarse fix (prose input), never a silently
        # truncated list.
        data = None
        for candidate in (txt, _repair_json(txt)):
            try:
                data = json.loads(candidate)
                break
            except Exception:  # noqa: BLE001
                data = None
        if not isinstance(data, (dict, list)):
            data = {"fix_prompts": [{"id": "FIX-001", "problem": txt[:200],
                                     "required_change": txt, "target_section": ""}]}
    if isinstance(data, dict):
        lst = data.get("fix_prompts") or data.get("fixes") or []
    elif isinstance(data, list):
        lst = data
    else:
        lst = []
    out = []
    for i, item in enumerate(lst[:12], start=1):
        if not isinstance(item, dict):
            continue
        criteria = item.get("acceptance_criteria") or []
        if isinstance(criteria, str):
            criteria = [criteria]
        required = item.get("required_change") or item.get("prompt") or ""
        # STEP 4.5 — a fix is unusable without a change AND checkable criteria;
        # this also drops a trailing fix the model cut off mid-JSON (recovered
        # complete fixes above stay). Keeping such a fix would send an empty
        # patch and fail its own verification.
        if not required.strip() or not [c for c in criteria if str(c).strip()]:
            continue
        out.append({
            "id": item.get("id") or f"FIX-{i:03d}",
            "severity": (item.get("severity") or "HIGH").upper(),
            "target_section": item.get("target_section", ""),
            "problem": item.get("problem", ""),
            "required_change": required,
            "acceptance_criteria": criteria,
            "prompt": required,
        })
    return out


def _ensure_structured(content: Any, schema: type) -> Any:
    """Coerce raw model output into a validated `schema` instance.

    Agno returns a pydantic instance when its JSON parsing succeeds and a raw
    STRING when it fails (typically because the model hit max_tokens mid-object
    and the JSON is unterminated). We try, in order: pass through, parse the
    (possibly ```-fenced) JSON directly, then attempt to *repair* a truncated
    object. If all fail, we raise StepFailed so the run fails gracefully with a
    clear message rather than storing a string in a dict-typed state field.
    """
    if isinstance(content, schema):
        return content
    if isinstance(content, BaseModel):
        content = content.model_dump()
    if isinstance(content, dict):
        return schema.model_validate(content)
    if isinstance(content, str):
        txt = content.strip()
        if txt.startswith("```"):
            txt = txt.strip("`")
            if txt[:4].lower() == "json":
                txt = txt[4:]
            txt = txt.strip()
        for candidate in (txt, _repair_json(txt)):
            try:
                return schema.model_validate_json(candidate)
            except Exception:  # noqa: BLE001 - try the next candidate
                continue
    raise StepFailed(
        f"structured output could not be produced for {schema.__name__} "
        f"(model likely truncated at the output cap; try raising STEP_MAX_OUTPUT "
        f"or shortening the prompt). Raw output was {type(content).__name__}."
    )


def _repair_json(txt: str) -> str:
    """Best-effort repair of a truncated JSON value (model hit max_tokens
    mid-output). We try a series of candidate cut points — each position just
    after a completed `}`/`]` or a closed string — closing still-open brackets,
    and return the LONGEST prefix that actually parses. `json.loads` is the
    source of truth, so a dangling key (e.g. a truncated ``{"id"``) is simply
    rejected and we fall back to the previous complete value. Returns the input
    unchanged if it is already balanced or nothing is salvageable."""
    txt = txt.strip()
    if txt.startswith("```"):
        txt = txt.strip("`")
        if txt[:4].lower() == "json":
            txt = txt[4:]
        txt = txt.strip()
    if txt[:1] not in "{[":
        return txt

    # Already valid? Return as-is.
    try:
        _jsonmod.loads(txt)
        return txt
    except Exception:  # noqa: BLE001 - truncated, attempt repair
        pass

    n = len(txt)
    # Candidate value-end positions (inclusive): right after a '}'/']', after a
    # closed string, or just before a ',' (a value that ends at the comma).
    cuts: list[int] = []
    in_str = False
    esc = False
    for i, ch in enumerate(txt):
        if in_str:
            if esc:
                esc = False
            elif ch == "\\":
                esc = True
            elif ch == '"':
                in_str = False
                cuts.append(i)  # a closed string (key or value; validate)
            continue
        if ch == '"':
            in_str = True
        elif ch in "}]":
            cuts.append(i)
        elif ch == "," and i > 0:
            cuts.append(i - 1)  # value ended just before this comma

    def closers_for(prefix: str) -> str:
        st: list[str] = []
        ins = False
        e = False
        for c in prefix:
            if ins:
                if e:
                    e = False
                elif c == "\\":
                    e = True
                elif c == '"':
                    ins = False
            else:
                if c == '"':
                    ins = True
                elif c in "{[":
                    st.append(c)
                elif c in "}]":
                    if st:
                        st.pop()
        return "".join("}" if x == "{" else "]" for x in reversed(st))

    for cut in sorted(cuts, reverse=True):  # longest prefix first
        prefix = txt[: cut + 1].rstrip()
        if prefix.endswith(","):
            prefix = prefix[:-1].rstrip()
        cand = prefix + closers_for(prefix)
        try:
            _jsonmod.loads(cand)
            return cand
        except Exception:  # noqa: BLE001 - this cut is invalid, try shorter
            continue
    return txt  # nothing salvageable
