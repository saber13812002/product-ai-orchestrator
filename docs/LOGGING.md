# Logging

**Standard:** structured logging, not free text. Minimum fields per event:
`timestamp`, `run_id`, `trace_id`, `step`, `module`, `agent`, `model`, `duration_ms`,
`status`, `token_usage`, `error_type`, `error_message`. **Secrets and API keys are never
logged.**

## Current state (STEP 9.6)

- **`print()`-only.** The codebase emits output via `print(json.dumps(...))` in
  `workflow/run.py` (the CLI report) and has **no `logging`/`structlog` configuration, no
  logger hierarchy, and no structured per-step events.**
- **No `timestamp`/`step`/`module`/`duration_ms`/`status`/`error_type`** fields are emitted as
  log events. (State does store `created_at`/`updated_at`, but that's persistence metadata, not
  a log stream.)
- The one real per-call record is the **token ledger** (`LlmCall`: agent, role, model, tokens,
  status) — a structured record, but it lives in `state.json`, not a log stream.

## The target (STEP 9.7)

- Add `workflow/observability.py` with a single `log_event(**fields)` that:
  - fills `timestamp` (UTC, ISO-8601 ms) automatically;
  - merges `run_id`/`trace_id`/`step`/`module`/`agent`/`model`/`status`;
  - accepts `duration_ms` and `token_usage` where applicable;
  - **redacts** any value that looks like a credential (master key, `LITELLM_API_KEY`,
    `*_MODEL_API_KEY`) before emitting — the same no-secret rule as the rest of the repo;
  - emits JSON lines to stdout (k8s-friendly; the container runtime ships stdout).
- Wrap each engine step and each model call in a timing block that logs
  `duration_ms` + `status` (and `error_type` on failure, e.g. `model_unavailable`,
  `timeout`, `invalid_structured_output`).

See `docs/OBSERVABILITY.md` §4 and the gap list in `docs/TESTING.md` §3.
