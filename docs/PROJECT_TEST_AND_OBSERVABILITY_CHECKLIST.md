# PROJECT_TEST_AND_OBSERVABILITY_CHECKLIST — living tracker

> **Living document** — update this file in the SAME commit as any work that touches a row.
> Baseline: 2026-10-21 re-audit (evidence in [`../audit_2026_10_21/`](../audit_2026_10_21/)).
>
> Rules (per the Golden Rule, STEP 9.6):
> - A ✅ requires **evidence**: a passing test name, a command + output, or a run_id — not a claim.
> - A module-level pass is **never** counted as system approval. "Approved" = quality gates passed
>   on a real run with evidence committed to `docs/evidence/`.
> - Statuses: ✅ done+evidenced · 🟡 partial · ❌ not started · ⛔ blocked (on whom/what).

## A. Tests

| # | Item | Status | Evidence (file / command / run) | Acceptance criterion |
|---|---|---|---|---|
| A1 | Unit tests — all `workflow/` modules | ✅ | 30/30 hermetic green, **re-run 2026-10-21 in-container** (`uv run --with pytest python -m pytest workflow/tests -q` → `30 passed in 0.83s`); files: `workflow/tests/test_{router,state,smoke,robustness,full_pipeline,enrichment,refine,endpoint}.py` | every module has ≥1 direct unit test; suite stays LLM-free |
| A2 | Integration tests (live gateway) | 🟡 | manual live matrix in STEP 9 (isolated compose projects); **not automated**; 1 re-verified call 2026-10-21 (19 tokens) | an opt-in live smoke test exists (tagged `live`, excluded from CI) and the manual per-release matrix is run + recorded |
| A3 | Contract tests (Pydantic schemas) | ✅ | asserted inside `test_full_pipeline` / `test_enrichment` / `test_router` (schemas validated per artifact) | every artifact (ProductAnalysis, design, docs, state) round-trips through its schema in a test |
| A4 | E2E for the full workflow | ✅ (hermetic) / 🟡 (live) | hermetic E2E: `test_full_pipeline.py`, `test_enrichment.py`, `test_refine.py`; live E2E: run `20261006-141735-97dda8` (40 calls, 155,998 tokens, 0 errors) — **but gates NOT passed** | hermetic E2E green in CI **and** one real run reaching both quality gates with evidence in `docs/evidence/` |
| A5 | HTTP-level tests (AgentOS app) | ❌ | none — TEST_MATRIX gap #1; manual `curl` only (2026-10-21: `/health` 200) | `TestClient` test(s) hit `/health` (+ `/ready`, `/metrics/prometheus` when built) and run in CI |
| A6 | Refine pass — live run with stored evidence | ❌ | `test_refine.py` green (code path); **no live refine run in storage** (verified 2026-10-20 AND 2026-10-21) | TASK-11-1: one bounded live run (~210k tokens cap, isolated compose project, never 7777/7779) with before/after scores committed to `docs/evidence/` — **requires user approval for the token spend** |
| A7 | Quality gate + final approval of documents | 🟡 | gate code works (computed 11-dimension score); latest real run: **71 < 85** and **79 < 80** | a real run reaches final_score ≥ 85 AND doc completeness ≥ 80 (or thresholds re-decided by user — not unilaterally lowered), evidence committed |
| A8 | Coverage measurement | ❌ | none wired (no `pytest-cov`) | coverage floor in CI (e.g. `--cov-fail-under`), baseline recorded |

## B. Observability

| # | Item | Status | Evidence | Acceptance criterion |
|---|---|---|---|---|
| B1 | Global `run_id` | ✅ | `workflow/state.py` — per-run `state.json`, 11 runs in prod volume | every run is reconstructable from disk (`test_state.py`) |
| B2 | Global `trace_id` (per run, in every LlmCall + state) | ❌ | grep 2026-10-21: no `trace_id` anywhere in `workflow/*.py` / `personal_agent.py` | TASK-9.7-1: unique UUID per run, present in `state.json` and every `LlmCall`; hermetic test asserts presence + uniqueness |
| B3 | Structured logging (no `print()` in `workflow/*.py`) | ❌ | grep 2026-10-21: engine uses `print()`; no `import logging` | TASK-9.7-1: `workflow/observability.py` + consistent event schema (`run_id`, `trace_id`, `step`, `agent`, `role`, `model`, `status`, `duration_ms`); `grep -c "print(" workflow/*.py` = 0; caplog test |
| B4 | `duration_ms` per step / per LLM call | ❌ | not recorded anywhere | part of TASK-9.7-1; asserted in a hermetic test |
| B5 | Prometheus metrics endpoint | ❌ | **`/metrics` on 7779 is Agno's built-in JSON endpoint** (`{"metrics":[],"updated_at":null}`) — NOT Prometheus (verified 2026-10-21) | TASK-9.7-2: dedicated Prometheus endpoint (path must not collide with Agno's, e.g. `/metrics/prometheus`) with `runs_total`, `runs_by_status`, `llm_calls_total{model,role,status}`, `llm_tokens_total{model}`, `run_duration_seconds`, `step_duration_seconds{step}`; no secrets in labels; hermetic TestClient test |
| B6 | `/health` (process-alive) | ✅ | Docker HEALTHCHECK → `:7777/health` 200 (both instances, verified 2026-10-21) | unchanged; stays the Docker healthcheck target |
| B7 | `/ready` (dependency-aware) | ❌ | `curl :7779/ready` → **404** (verified 2026-10-21) | TASK-9.7-3: 200 only when the configured LiteLLM endpoint answers `/health/liveliness` in-time; 503 + JSON reason otherwise; hermetic monkeypatch test |
| B8 | Prometheus scrape job (server 52) | ❌ | no job `agentos-7779` in `prometheus.yml` | TASK-9.7-4: `promtool check config` clean; `up{job="agentos-7779"} == 1` |
| B9 | Grafana dashboard (full agent path: runs, tokens by model, step latency P50/P95, gate pass/fail) | ❌ | no dashboard for this project (existing 52 dashboards cover host/litellm only) | TASK-9.7-4: dashboard renders real values after one hermetic + one real run |

## C. Per-run reporting

| # | Item | Status | Evidence | Acceptance criterion |
|---|---|---|---|---|
| C1 | Token report per run (real vs stub, per model) | ✅ | `LlmCall` ledger in `state.json`; run `97dda8`: 155,998 real tokens / 40 calls / 3 models, stubs excluded | every completed run's report separates real/stub and breaks down by model |
| C2 | Time report per run / per step | ❌ | no durations recorded | part of TASK-9.7-1 (`duration_ms`) |
| C3 | Error report per run (which step/call failed, why) | 🟡 | `LlmCall.status` recorded; error handling in `test_robustness.py` (negative tests) | one structured error event per failure with `trace_id` + step + model (depends on B2/B3) |

## D. Refine & final approval (the product goal)

| # | Item | Status | Evidence | Acceptance criterion |
|---|---|---|---|---|
| D1 | Live refine pass with evidence | ❌ | see A6 | see A6 (TASK-11-1, needs user go-ahead for ~210k tokens) |
| D2 | "Approved Technical Documents" achieved | ❌ | run `97dda8`: produced ✅, reviewed ✅, versioned ✅, **approved ❌** (71/79) | A7 + D1 both green, evidence committed |
| D3 | Evidence store | ❌ | no `docs/evidence/` dir | `docs/evidence/` exists and holds at least the TASK-11-1 run artifacts (state.json excerpts + scores) |

## E. Docs & handoff

| # | Item | Status | Evidence | Acceptance criterion |
|---|---|---|---|---|
| E1 | README = current real state | ✅ (this commit) | README top block now links the 2026-10-21 audit bundle + this checklist | README updated in the same commit as any state change |
| E2 | AI_HANDOFF = current real state | ✅ (this commit) | `docs/AI_HANDOFF.md` §0 "2026-10-21 re-audit" + refreshed header | same rule as E1 |
| E3 | Audit bundle committed | ✅ (this commit) | `audit_2026_10_21/` (4 files) added to git | committed + linked from README/AI_HANDOFF |
| E4 | CI pipeline status queryable | ⛔ blocked on token | no GitLab API token anywhere (52 + laptop); runner 502s at 06:52 UTC 2026-10-21 uninvestigated | TASK-CI-1: project-scoped `read_api` token as CI variable + documented query command in AGENTS.md; 502 investigated |

## Execution order (after this commit)

1. **E4 / TASK-CI-1** — unblocks "is CI green today" (10 min, needs a GitLab token from the user)
2. **B2→B3→B4→B5→B7** on branch `feat/observability-baseline` (TASK-9.7-1..3, all hermetic)
3. **A5** HTTP tests land with B5/B7 (same branch)
4. **D1 / TASK-11-1** — the ONE bounded live refine run (user-approved budget)
5. **B8→B9** — Prometheus + Grafana (TASK-9.7-4)
6. **A7 / D2 / D3** — score-gap closure (user decision: stronger model vs thresholds)
