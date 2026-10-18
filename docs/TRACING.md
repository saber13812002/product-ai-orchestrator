# Tracing

**Standard:** every run carries a unique `run_id` and a `trace_id`; all logs, agent calls,
LiteLLM calls, API calls, quality gates, and errors follow the same identifiers so one request
is reconstructable from ingress to final output.

## Current state (STEP 9.6)

- **`run_id` — ✅ present.** Minted by `workflow/state.py::new_run_id()` as
  `YYYYMMDD-HHMMSS-<6hex>`. Every run is keyed by it:
  `workflow/storage/runs/{run_id}/state.json` (+ `artifacts/`). `WorkflowState.run_id` is
  carried through the whole engine and printed in the CLI report.
- **`trace_id` — ❌ not present yet.** We have one identifier (`run_id`), but no separate
  `trace_id`, and **no cross-process propagation** between the AgentOS HTTP run (`:7777`) and
  the CLI run (`workflow.run`). Today those two paths are not linked by a shared ID.

## The target (STEP 9.7)

- Mint a `trace_id` (UUID) **alongside** `run_id` in `create_state()` (`workflow/state.py`).
  - `run_id` = human-facing, timestamped (which run, when).
  - `trace_id` = correlation id for a single request across processes/threads.
- Propagate it through the engine and into every `log_event` and every metric label
  (`{run_id, trace_id}`).
- When a run is triggered over HTTP (AgentOS), set `trace_id` from the incoming request (or
  mint one) so the HTTP layer and the pipeline share it.

See `docs/OBSERVABILITY.md` for the full standard and `docs/TESTING.md` for the matrix.
