# Testing & Observability — the Golden Rule

> **The Golden Rule (this project, and all future projects):** no module, agent, API,
> pipeline, or deployment is **complete** unless it has **both** tests **and** an
> observable, traceable execution path. "Code written" is **not** done.

This document is the permanent **Definition of Done** and the **Test Matrix** for this
repository. It is the baseline established in **STEP 9.6** (2026-10-11) and the standard
**STEP 10 (Helm/K8s)** must ship from the start.

The full 14-point standard lives in `docs/OBSERVABILITY.md`. This file is the **matrix** and
the **per-step test status**.

---

## 1. The 14-point Golden Rule (summary)

1. **Per-step tests** — unit, integration, contract, E2E, regression, smoke, failure/recovery.
2. **Full-workflow test** — `Input → Manager → Agents → LiteLLM → Model → Structured Output →
   Critic → Refiner → Quality Gate → Documents → Final Result`. Each step shows: input,
   output, duration, which model/agent, tokens, PASS/FAIL, and the step that errored.
3. **Global trace** — every run has a unique `run_id` (and ideally `trace_id`); all logs,
   agent calls, LiteLLM calls, API calls, gates, and errors follow it. One request is
   reconstructable end-to-end.
4. **Structured logging** — not free text. Min fields: `timestamp`, `run_id`, `trace_id`,
   `step`, `module`, `agent`, `model`, `duration_ms`, `status`, `token_usage`, `error_type`,
   `error_message`. **Secrets/keys are never logged.**
5. **Health checks** — AgentOS, LiteLLM, model backend, DB/storage, API, worker, (future) k8s
   pod. Not just "process alive" — check key dependencies where possible.
6. **Metrics** — requests, success/failure, latency, P50/P95/P99, agent exec time, model
   latency, tokens, error rate, quality score, queue/worker, health, (infra) CPU/RAM/GPU.
7. **Prometheus + Grafana** — App/AgentOS/LiteLLM → metrics → Prometheus → Grafana.
8. **Grafana Workflow Dashboard** — Manager→Analyst→Decomposition→Specialists→Critic→Refiner→
   Gate→Docs→Final Review; per step: count, latency, error, tokens, score, status.
9. **Reports** — every run extractable: summary, steps, agents, models, tokens, quality
   scores, errors, docs generated, total duration, final status.
10. **CI quality gate** — no merge/release without tests. Pipeline: Lint→Unit→Integration→
    Contract→E2E/Smoke→Security→Build→Deploy→Health Check. Keep hermetic.
11. **In-repo docs** — `TESTING.md`, `OBSERVABILITY.md`, `TRACING.md`, `LOGGING.md`,
    `HEALTHCHECKS.md`, `METRICS.md`, `GRAFANA.md`, `CI_CD.md`, `AI_HANDOFF.md`; linked from
    README.
12. **Test Matrix in Git** — this file. No module left without a status.
13. **Definition of Done** — code + unit test + integration + log + trace + health (if
    needed) + metric + diagnosable error + documented + CI-tested + (if important) in Grafana.
14. **AI_HANDOFF** — updated every step with what's present and what's missing.

---

## 2. Definition of Done (mandatory)

A feature is **Done** only when ALL of these hold:

- [ ] Code is present.
- [ ] Unit test covers its main logic.
- [ ] Integration test covers how it connects to neighbors (where applicable).
- [ ] It **logs** structured events (run_id + step + status).
- [ ] It is **traceable** by `run_id`/`trace_id`.
- [ ] It has a **health** check (where it's a service).
- [ ] It emits **metrics** (count + latency + tokens + errors).
- [ ] Its **failure is diagnosable** (distinct error_type, not a generic traceback).
- [ ] It is **documented** in the relevant `docs/` file.
- [ ] **CI runs it** (hermetic where possible).
- [ ] (If user-facing/important) it is **visible in Grafana**.

---

## 3. The Test Matrix (the core deliverable of STEP 9.6)

Status legend: ✅ present · 🟡 partial/exists-but-incomplete · ❌ missing.

| Module / Service | Unit | Integration | E2E | Contract | Failure/Recovery | Health | Metrics | Structured Log | Trace (`run_id`/`trace_id`) | Dashboard |
|---|---|---|---|---|---|---|---|---|---|---|
| `workflow/state.py` (StateStore, run_id) | ✅ | 🟡 | ❌ | 🟡 (Pydantic) | ❌ | — | ❌ | ❌ (persist only) | ✅ `run_id` | — |
| `workflow/schemas.py` (Pydantic artifacts) | ✅ | — | — | ✅ (schema = contract) | ❌ | — | — | — | — | — |
| `workflow/config.py` (resolve_endpoint, roles) | ✅ | — | — | — | ❌ | — | — | — | — | — |
| `workflow/router.py` (role→model, token ledger) | ✅ | 🟡 | ❌ | 🟡 | ❌ | — | 🟡 (ledger only) | ❌ | 🟡 (via state) | — |
| `workflow/models.py` (OpenAIChat factory) | ❌ | 🟡 (smoke) | ❌ | — | ❌ | — | — | — | — | — |
| `workflow/prompts.py` (roles + rubric) | 🟡 (string) | — | — | — | — | — | — | — | — | — |
| `workflow/engine.py` (13-step + enrich + refine) | 🟡 (full_pipeline) | ✅ (full) | ❌ (no live E2E in CI) | 🟡 | 🟡 (budget halt) | — | 🟡 (per-step in state) | ❌ | ✅ `run_id` | ❌ |
| `agents/manager.py` | ✅ (smoke) | ✅ | ❌ | — | ❌ | — | — | — | ✅ | — |
| `agents/product_analyst.py` | ✅ (smoke) | ✅ | ❌ | 🟡 (output_schema) | ❌ | — | — | — | ✅ | — |
| `agents/enrichment.py` (8 docs) | ✅ (enrichment) | ✅ | ❌ | 🟡 | ❌ | — | — | — | ✅ | — |
| `agents/document_manager.py` (deterministic) | ✅ | ✅ | ❌ | 🟡 (10-file bundle) | ❌ | — | — | — | ✅ | — |
| `personal_agent.py` (AgentOS HTTP `:7777`) | ❌ | 🟡 | ❌ | 🟡 (OpenAPI) | ❌ | 🟡 (`/health` = alive only) | ❌ | ❌ | ❌ | — |
| `litellm/` sidecar (entrypoint + config) | ❌ | 🟡 (compose config) | 🟡 (live matrix) | — | ❌ | 🟡 (`/health/liveliness`) | ❌ | ❌ | — | — |
| **CI/CD pipeline** | ✅ (30 hermetic) | — | 🟡 (deploy health-wait) | — | ❌ | 🟡 (health-wait only) | ❌ | — | — | — |

**Read the gaps honestly:**
- **Trace:** we have `run_id` (timestamped, unique) but **no `trace_id`** and no
  cross-process propagation (the AgentOS HTTP run and the CLI run don't share an ID yet).
- **Logging:** everything is `print()`. **No `logging` module, no structured fields.**
- **Metrics:** the **token ledger** (`LlmCall`) is a real, per-call record — that is a genuine
  metric source (tokens, model, status) — but it is **not exposed** as Prometheus, and there is
  **no latency/duration** recorded per step or per call.
- **Health:** AgentOS `/health` and the LiteLLM `/health/liveliness` are **process-alive
  only**; neither checks the model backend or the DB.
- **E2E:** there is no *live* E2E in CI (by design — CI is hermetic). Live E2E is manual only.
- **Grafana/Prometheus:** **none exist yet** for this app.

---

## 4. What STEP 9.6 added (this baseline, 2026-10-11)

- **`docs/TESTING.md`** (this file) — the matrix + DoD.
- **`docs/OBSERVABILITY.md`** — the full 14-point standard + the metrics/tracing/logging design
  and the concrete gap list.
- **README** links to both; the Golden Rule is stated up top.
- **`docs/AI_HANDOFF.md`** — STEP 9.6 row + "what tests/observability exist" + "what's missing".
- **No code changes** — this is a *baseline* (measure first, build second). The build is
  STEP 9.7 (structured logging + trace_id + `/metrics`) and is folded into STEP 10.

## 5. Roadmap to full compliance (not yet built — pending the STEP 10 order)

| Next | What | Why first |
|---|---|---|
| **9.7a** | `workflow/observability.py`: structured-logging helper + `trace_id` minted alongside `run_id`; every engine step logs `{run_id, trace_id, step, agent, model, duration_ms, status, tokens, error_type}`. | Unlocks #3/#4; prerequisite for #6. |
| **9.7b** | `/metrics` (Prometheus text format) on the AgentOS app: per-step count/latency/tokens/errors + run status. | Unlocks #6/#7. |
| **9.7c** | Dependency-aware `/health` (checks LiteLLM endpoint + DB reachability). | Upgrades #5. |
| **10** | Helm chart: readiness/liveness probes, ServiceMonitor, Grafana workflow dashboard, resource metrics, post-deploy smoke. | #5–#8 at the platform layer. |
| **10+** | Prometheus + Grafana instances (or reuse an existing fleet's), dashboards #7/#8. | The visual layer. |
