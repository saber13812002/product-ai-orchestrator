# ROADMAP — AI Product Orchestrator

> Audited 2026-10-20. Priorities and dependencies below are based on the verified state in
> [PROJECT_STATUS.md](PROJECT_STATUS.md), not on the older STEP report assumptions.

## Priorities

- **P0** — blocks the product goal ("Approved Technical Documents") or breaks the CI/deploy promise.
- **P1** — required by the Golden Rule (tests + observability) before the next release.
- **P2** — valuable, not blocking.

## Tasks (execution order)

### TASK-9.7-1 — `workflow/observability.py`: trace_id + structured logging  (P0)
- **Depends on:** nothing
- **Files:** new `workflow/observability.py`; touch `workflow/engine.py`, `workflow/run.py`,
  `workflow/state.py`, `personal_agent.py` (wire `trace_id` into `LlmCall`/state; replace `print()`
  with `logging` with a consistent event schema: `run_id`, `trace_id`, `step`, `agent`, `role`,
  `model`, `status`, `duration_ms`)
- **Acceptance criteria:** every pipeline step + every LLM call emits one structured log line;
  `trace_id` (new UUID per run) propagates into `state.json` and into every `LlmCall` record; no
  `print()` remains in `workflow/*.py` (verified by `grep`)
- **Test:** hermetic — assert `trace_id` present + unique per run in a FakeRouter run; assert log
  record fields (caplog) for one full pipeline run. Must stay **LLM-free** (Golden Rule: CI stays
  hermetic).

### TASK-9.7-2 — `/metrics` Prometheus endpoint on AgentOS  (P0)
- **Depends on:** TASK-9.7-1 (duration_ms source)
- **Files:** `personal_agent.py` (mount `/metrics`), new `workflow/metrics.py` (counters:
  `runs_total`, `runs_by_status`, `llm_calls_total{model,role,status}`, `llm_tokens_total{model}`,
  `run_duration_seconds`, `step_duration_seconds{step}`; gauges: `runs_in_progress`)
- **Acceptance criteria:** `curl :7779/metrics` returns the above metric names; values change
  after a hermetic (FakeRouter) run inside the container; no secret ever in a label
- **Test:** hermetic — start app with TestClient, trigger a fake run, assert metric increments

### TASK-9.7-3 — dependency-aware `/ready`  (P1)
- **Depends on:** nothing (can go in parallel with 9.7-1/2)
- **Files:** `personal_agent.py` (add `/ready`), `workflow/config.py::resolve_endpoint()` reuse
- **Acceptance criteria:** `/ready` returns 200 only when the configured LiteLLM endpoint answers
  `/health/liveliness` within a timeout; returns 503 + JSON reason otherwise. `/health` stays
  process-alive only (no behavior change to what Docker's `healthcheck:` currently polls — verify
  `docker-compose.yml` healthcheck still targets `/health` after this change)
- **Test:** hermetic — monkeypatch the endpoint check to fail → 503; succeed → 200

### TASK-9.7-4 — Prometheus scrape job + Grafana dashboard (server 52)  (P1)
- **Depends on:** TASK-9.7-1, TASK-9.7-2 (metrics must exist and be deployed first)
- **Files (on 52, not this repo's code):** `prometheus.yml` (new job `agentos-7779`, target
  `172.20.1.52:7779`); new Grafana dashboard JSON (workflow dashboard: runs, tokens by model,
  step latency P50/P95, gate pass/fail rate)
- **Acceptance criteria:** `promtool check config` clean; `up{job="agentos-7779"} == 1`; dashboard
  renders real values after one hermetic + one real run
- **Note:** reuses the existing Prometheus/Grafana already running on 52 (see sibling infra memory
  "observability-stack-on-52") — no new infra install needed for this
- **Test:** visual + `promtool`; not part of the hermetic suite (infra-level, verified manually)

### TASK-11-1 — Live refine-pass run, with evidence  (P0)
- **Depends on:** nothing (uses existing code), but should run **after** TASK-9.7-2 so the run's
  metrics are captured, not just `state.json`
- **What:** on a **dedicated, isolated compose project** (never 7777/7779 — see AGENTS.md
  hard rule #6), run `workflow.run refine` with the same brief as run `20261006-141735-97dda8`
  (or a fresh brief), using the live external gateway. Record: run_id, before/after
  `document_completeness.overall_score`, per-doc before/after, token spend vs
  `config.REFINE_TOKEN_BUDGET` (210,000)
- **Acceptance criteria:** `overall_score` after refine ≥ the 80 gate for at least the docs that
  were gapful pre-refine (DDL/OpenAPI/observability/UI flows); evidence (state.json paths +
  scores) committed to this repo under a new `docs/evidence/` or pasted into
  [PROJECT_STATUS.md](PROJECT_STATUS.md) §4
- **Budget:** one bounded run, ~210k tokens cap — this is the ONE live, non-hermetic run allowed
  in the next working session (not during an audit)
- **Test:** n/a (this IS the live test); the hermetic `test_refine.py` already covers the code path

### TASK-11-2 — Close the score gap (design gate 85, doc gate 80)  (P1, model-dependent)
- **Depends on:** TASK-11-1 (need the post-refine baseline first)
- **What:** if TASK-11-1 still lands below 80 after refine, the documented diagnosis (STEP 4) is
  "model-bound, not loop-bound". Options, in order: (a) confirm `TASK_MODEL_HINTS` is still the
  right split now that the fleet has `Qwen3.8-27B-FP8` on both 53:8000 and 53:8001 — the `deep`
  role currently only satisfies "≥3 distinct models", it doesn't carry load for anything that
  needs structured output; (b) if a stronger/newer model is added to the LiteLLM fleet (user
  decision — new backend on 53), re-point `AGENT_MODEL_FAST` and re-run TASK-11-1's brief
- **Acceptance criteria:** a full+enrich+refine run on the live fleet reaches final_score ≥85 and
  overall doc completeness ≥80; evidence recorded
- **Open decision (user):** is a new/stronger model backend on 53 in scope, or is 71→79 "good
  enough" and the gate thresholds should be re-examined as business decisions rather than chased
  by engineering? **This needs the user's call — do not unilaterally lower `GATE_THRESHOLD` (85)
  or `ENRICH_GATE_THRESHOLD` (80).**

### TASK-10-1 — Kubernetes/Helm: DECISION (not implementation)  (P2, blocked on user)
- **Depends on:** user decisions, see [AI_HANDOFF.md](AI_HANDOFF.md) §8
- **What:** confirm (a) target cluster (k3s on 52 vs external — 52 disk is ~90% full, this is a
  hard constraint), (b) registry (enable GitLab CE `container_registry` feature vs ghcr/docker.io
  vs nothing yet). No code until both are answered.
- **Status:** NOT STARTED, deliberately deferred — do not build a Helm chart for a cluster that
  doesn't exist.

### TASK-CI-1 — Re-verify latest CI pipeline + GitLab API access  (P1, quick)
- **Depends on:** nothing
- **What:** we could not re-query the pipeline list today (no GitLab API token in
  `/etc/gitlab-runner/config.toml` or on the laptop). Either (a) create a **project-scoped**
  `read_api` CI variable/token for this project and store it as a GitLab CI/CD variable (not in
  this repo), or (b) confirm via the GitLab UI on 52 that the latest `main` pipeline is green.
  This also gives us a durable, scriptable way to verify CI in future audits.
- **Acceptance criteria:** a command (documented in AGENTS.md) that returns the latest pipeline
  id/status for this repo without manual UI clicks
- **Test:** manual one-off, then documented

## Suggested working-session order (after audit sign-off)

1. TASK-CI-1 (10 min, unblocks "is CI actually green today")
2. TASK-9.7-1 → TASK-9.7-2 → TASK-9.7-3 (one PR/branch: `feat/observability-baseline`, all
   hermetic-testable, no live infra needed)
3. TASK-11-1 (one bounded live refine run, isolated compose project, evidence captured)
4. TASK-9.7-4 (wire the now-real metrics into 52's existing Prometheus/Grafana)
5. TASK-11-2 (user decision point on model/thresholds)
6. TASK-10-1 (user decision point on k8s/registry)

Each step ships: hermetic tests green in CI, a release tag if it changes package behavior, and an
updated `PROJECT_STATUS.md` evidence row.
