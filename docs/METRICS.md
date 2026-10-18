# Metrics

**Standard:** metrics for every module — requests, success/failure, latency, **P50/P95/P99**,
agent execution time, model latency, tokens, error rate, quality score, queue/worker status,
health status, and (infra) CPU/RAM/GPU.

## Current state (STEP 9.6)

- **The token ledger is a real metric source.** `WorkflowState.token_usage.calls` holds one
  `LlmCall` per model call with `agent`, `role`, `model`, `provider`, `input/output/reasoning/
  total` tokens, `status`, and `is_stub`. That gives us **tokens, model, and call status** — but
  it is stored in `state.json`, **not exposed as a scrapeable metric**.
- **No latency.** Nothing records how long a call or a step took, so there is no
  `duration_ms` and therefore no P50/P95/P99.
- **No `/metrics` endpoint.** The AgentOS app exposes `/health`, `/docs`, `/agents`, and the
  OpenAPI surface — **no Prometheus endpoint**.
- **No quality-score series over time.** `state.quality_scores` and
  `state.document_completeness` are per-run values; they're never aggregated into a gauge.

## The target (STEP 9.7) — a `/metrics` endpoint on the AgentOS app

Prometheus text format, minimum series:

| Metric | Type | Labels | Source |
|---|---|---|---|
| `orchestrator_run_total` | counter | `status` (completed / failed / budget_exhausted) | run completion |
| `orchestrator_step_duration_seconds` | histogram | `step` | per-step timing (new) |
| `orchestrator_model_call_duration_seconds` | histogram | `model`, `role` | per-call timing (new) |
| `orchestrator_tokens_total` | counter | `model`, `role`, `direction` (in/out/reasoning) | token ledger |
| `orchestrator_model_call_total` | counter | `model`, `role`, `status` | token ledger |
| `orchestrator_step_errors_total` | counter | `step`, `error_type` | structured errors (new) |
| `orchestrator_last_quality_score` | gauge | `run_id` | `state.quality_scores` |
| `orchestrator_last_doc_completeness` | gauge | `run_id` | `state.document_completeness` |
| `orchestrator_runs_active` | gauge | — | in-flight runs |

Prometheus/Grafana wiring (scrape + dashboards) is **STEP 10** (ServiceMonitor + the Workflow
Dashboard in `docs/GRAFANA.md`). Until then the ledger + `/metrics` already make the app
scrapeable.

See `docs/OBSERVABILITY.md` §6.
