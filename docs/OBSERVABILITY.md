# Observability — the 14-point standard (and where we stand)

This is the **full statement** of the project's observability standard (the "Golden Rule" —
nothing is complete without tests **and** an observable, traceable execution path).
`docs/TESTING.md` holds the **matrix + DoD**; this file holds the **standard itself** and the
**honest gap list** that STEP 9.7/10 must close.

---

## The 14 points

1. **Per-step testing.** Unit (every module/class/agent/logic), Integration (module↔module),
   Contract (APIs + schemas), E2E (the real user path), Regression (old features stay working),
   Smoke (every deploy), and **Failure/Recovery** (timeout, model unavailable, DB error,
   LiteLLM down, network, dependency).

2. **Whole-workflow test.** `Input → Manager → Agents → LiteLLM → Model → Structured Output →
   Critic → Refiner → Quality Gate → Documents → Final Result` must be testable end to end.
   For each step, record: the input, the output, the duration, which model/agent ran, the
   tokens consumed, the PASS/FAIL result, and which step errored.

3. **Global trace.** Every run carries a unique `run_id` and ideally a `trace_id`. All logs,
   agent calls, LiteLLM calls, API calls, quality gates, and errors follow the same identifier
   so **one request is reconstructable from ingress to final output**.

4. **Structured logging.** Not free text. Minimum fields:
   `timestamp`, `run_id`, `trace_id`, `step`, `module`, `agent`, `model`, `duration_ms`,
   `status`, `token_usage`, `error_type`, `error_message`. **Secrets and API keys are never
   logged** (the same rule that keeps the master key out of the repo).

5. **Health checks** for every service: AgentOS, LiteLLM, model backend, database/storage,
   API, worker, and (STEP 10) the k8s pod. Health must not be "process alive" — it should
   probe key dependencies where feasible.

6. **Metrics** for every module: requests, success/failure, latency, **P50/P95/P99**, agent
   execution time, model latency, tokens, error rate, quality score, queue/worker status,
   health status, and (at the infra layer) CPU/RAM/GPU.

7. **Prometheus + Grafana.** Standard path: `App / AgentOS / LiteLLM → metrics → Prometheus →
   Grafana`. Minimum dashboards: System Overview, Agent Workflow, Model/LiteLLM, Quality Gate,
   API, Errors, Infrastructure, CI/CD, (STEP 10+) Kubernetes.

8. **Grafana Workflow Dashboard** — one dedicated dashboard showing the whole workflow:
   `Manager → Product Analyst → Decomposition → Specialists → Critic → Refiner → Quality Gate →
   Document Generation → Final Review`. Per step: count, latency, error, tokens, score, status.

9. **Reports.** Every run must yield an extractable report: Run Summary, Steps, Agents, Models,
   Token Usage, Quality Scores, Errors, Documents Generated, Total Duration, Final Status.
   *(We already emit this as the CLI JSON summary + `state.json` — see gap list.)*

10. **CI quality gate.** No merge/release without tests. Pipeline:
    `Lint → Unit → Integration → Contract → E2E/Smoke → Security → Build → Deploy → Health
    Check`. Keep it **hermetic** — no paid model, no network to LiteLLM.

11. **Documentation in Git.** Every path documented: `TESTING.md`, `OBSERVABILITY.md`,
    `TRACING.md`, `LOGGING.md`, `HEALTHCHECKS.md`, `METRICS.md`, `GRAFANA.md`, `CI_CD.md`,
    `AI_HANDOFF.md`; all linked from the README.

12. **Test Matrix in Git.** `Module | Unit | Integration | E2E | Health | Metrics | Logs |
    Trace | Dashboard`. No module may remain without a status (see `docs/TESTING.md` §3).

13. **Definition of Done.** "Code written" ≠ Done. Done = code + unit test + integration +
    log + trace + health (if needed) + metric + diagnosable error + documented + CI-tested +
    (if important) in Grafana.

14. **AI_HANDOFF every step.** State: what tests were added, which modules still have
    incomplete tests, which metrics/dashboards exist, which trace/logs were added, what
    observability problems remain, and the next step.

---

## STEP 10 (Helm/K8s) must ship these from the start — not bolt on

`readinessProbe` · `livenessProbe` · `metrics endpoint` · `structured logs` ·
`trace_id`/`run_id` propagation · **Prometheus ServiceMonitor** (or equivalent) · Grafana
dashboards · resource metrics · deployment health · **smoke test after deployment**.

> **Principle:** monitoring and testing are not a final project phase. From here on they are
> part of the **design of every module**.

---

## Where we actually stand (STEP 9.6 honest audit, 2026-10-11)

**Already present (genuine, not nominal):**
- ✅ **`run_id`** — `workflow/state.py::new_run_id()` → `YYYYMMDD-HHMMSS-<6hex>`, unique, and
  every state path is keyed by it (`storage/runs/{run_id}/state.json`).
- ✅ **Token ledger** — `LlmCall` per call (agent, role, model, provider, in/out/reasoning
  tokens, status, is_stub) in `WorkflowState.token_usage`. This is a real **per-call metric
  source** (model, tokens, status).
- ✅ **Per-step state persistence** — state saved after every step, so the run is reconstructable
  from disk.
- ✅ **Run report** — `workflow/run.py::_print_full` emits run summary, steps, final scores,
    per-model token breakdown, errors, state path. (Point 9 is substantially met, as JSON on
    stdout + `state.json`.)
- ✅ **Hermetic tests** — 30 tests, no LLM/network/key (CI promise holds).
- ✅ **Contract-ish** — Pydantic schemas (`ProductAnalysis`, `WorkflowState`, `LlmCall`,
  `TechnicalDocument`, …) define the data contracts; AgentOS exposes OpenAPI.
- ✅ **Two health endpoints** — AgentOS `/health`, LiteLLM `/health/liveliness`.

**Missing / incomplete (the work STEP 9.7 → 10 must do):**
- ❌ **`trace_id`** — none. `run_id` exists but there is no separate `trace_id` and no
  cross-process propagation between the AgentOS HTTP run and the CLI run.
- ❌ **`logging` module / structured logs** — the codebase uses `print()`; there is no
  `logging`/`structlog`, no `timestamp`/`step`/`module`/`duration_ms`/`status`/`error_type`
  fields, no log routing.
- ❌ **Duration/latency** — nothing records how long a step or a call took (no
  `duration_ms`, no P50/P95/P99).
- ❌ **`/metrics` endpoint** — no Prometheus endpoint; the token ledger is not exposed as a
  scrapeable metric.
- ❌ **Prometheus / Grafana** — none for this app.
- 🟡 **Health depth** — both health endpoints are process-alive only; they do not probe the
  model backend, the LiteLLM gateway, or the DB.
- ❌ **readiness/liveness probes** — nothing in compose yet (k8s will need them in STEP 10).
- ❌ **CI stages beyond test→deploy** — no lint, no contract, no smoke-after-deploy stage in
  `.gitlab-ci.yml`.
- 🟡 **Failure/Recovery tests** — the engine halts on budget exhaustion (a recovery path), but
  there is no dedicated test for model-unavailable / LiteLLM-down / DB-error / timeout.
- 🟡 **Live E2E in CI** — none by design (CI is hermetic); live E2E is manual only.

## Design intent for the build (what "done" looks like)

- **`workflow/observability.py`** — one place that (a) mints `trace_id` next to `run_id`,
  (b) provides `log_event({...})` that emits structured JSON with the §4 fields and **redacts
  anything that looks like a key**, and (c) records `duration_ms` around each engine step and
  each model call.
- **`/metrics`** — a FastAPI/Starlette route on the AgentOS app exposing Prometheus text:
  `orchestrator_run_total{status}`, `orchestrator_step_duration_seconds{step}`,
  `orchestrator_tokens_total{model,role}`, `orchestrator_step_errors_total{step,error_type}`,
  `orchestrator_last_quality_score`.
- **Dependency-aware `/health`** — `/health` (liveness, alive) + `/ready` (readiness: LiteLLM
  endpoint reachable + DB file writable), mirroring what k8s probes will call.
- **Grafana Workflow Dashboard** — fed by the per-step metrics, showing the §8 node chain with
  count/latency/error/tokens/score/status per node.
