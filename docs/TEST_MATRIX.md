# TEST_MATRIX — AI Product Orchestrator

> Verified 2026-10-20: **30 hermetic tests pass** (`uv run --with pytest python -m pytest
> workflow/tests -q` inside `agno-agentos-repo` on 52, 0.83s, no LLM/network/key). This file
> replaces the "30 tests" count with an actual per-module map, and states the coverage gap
> honestly.

## Golden Rule (unchanged, from STEP 9.6)

Nothing is "complete" without **both** tests **and** an observable, traceable execution path. See
[OBSERVABILITY.md](OBSERVABILITY.md) for the 14-point standard, [TESTING.md](TESTING.md) for the
original DoD wording.

## Test inventory (what exists, verified by `ls workflow/tests/`)

| File | What it covers | Type |
|---|---|---|
| `test_full_pipeline.py` | 13-step pipeline end-to-end on `FakeRouter` — state transitions, 17-section design assembly, quality-gate loop | hermetic E2E |
| `test_enrichment.py` | 8 enrichment docs + Document Manager 10-file bundle + doc-completeness gate | hermetic E2E |
| `test_refine.py` | refine pass re-runs only gapful docs, overwrites bundle, re-scores | hermetic E2E |
| `test_router.py` | role→model resolution, stub handling, token-ledger `LlmCall` record shape | unit |
| `test_state.py` | `state.json` round-trip, run reconstructable from disk | unit |
| `test_endpoint.py` (STEP 9, 9 tests) | `resolve_endpoint()` mode selection (external/bundled/fallback), `workflow.run endpoint` output | unit |
| `test_smoke.py` | minimal "does the engine boot and do one step" check | unit |
| `test_robustness.py` | error paths: LLM call failure mid-pipeline, malformed structured output | unit (negative) |

**Total: 30 tests, all hermetic, all CI-run. No network, no LLM, no API key — verified by
re-running them today in the deployed container.**

## Per-module coverage matrix

Legend: ✅ covered · ⚠️ covered only indirectly/partially · ❌ no test

| Module | Unit | Integration (live gateway) | Contract (Pydantic schema) | E2E | Live-verified (2026-10-20) |
|---|---|---|---|---|---|
| Pipeline engine (13 steps) | ✅ `test_full_pipeline` | ⚠️ not in-suite by design (hermetic rule) | ✅ schemas | ✅ `test_full_pipeline` | ✅ run `97dda8` (see PROJECT_STATUS §5) |
| Model router | ✅ `test_router` | ⚠️ `workflow.run routing`/`endpoint` are manual, not automated against live gateway | ✅ | ✅ | ✅ (endpoint → external, verified) |
| Product Analyst | ✅ (via full pipeline) | — | ✅ `ProductAnalysis` | ✅ | ✅ |
| Master Prompt Builder | ✅ (via full pipeline) | — | ✅ | ✅ | ✅ |
| 9 specialist tasks | ✅ (via full pipeline) | — | ✅ | ✅ | ✅ |
| Enrichment (8 docs) + Document Manager | ✅ `test_enrichment` | — | ✅ | ✅ | ✅ (8 docs in run 97dda8) |
| Critic / Refiner | ✅ (via full pipeline, `critic_results`/`patches` in state) | — | ✅ | ✅ | ✅ (present in state.json) |
| Quality Gate (computed weighted score) | ✅ (asserts score math, not just shape) | — | ✅ | ✅ | ⚠️ computed (71) but **below** 85 threshold — code works, target unmet |
| Document-completeness gate | ✅ `test_enrichment` | — | ✅ | ✅ | ⚠️ 79 vs 80 threshold — same: code works, target unmet |
| Refine pass (code) | ✅ `test_refine` | — | ✅ | ✅ | ❌ **no live run evidence** — TASK-11-1 |
| State management | ✅ `test_state` | — | ✅ | ✅ | ✅ |
| Token ledger | ✅ `test_router` (record shape) | — | ✅ | ✅ | ✅ (155,998 real tokens, 40 calls, 3 models in run 97dda8) |
| `resolve_endpoint` / LiteLLM modes | ✅ `test_endpoint` | ⚠️ live side-by-side matrix was done in STEP 9 (isolated compose projects), not re-run this audit | ✅ | — | ✅ (endpoint resolution re-verified on 7779) |
| AgentOS HTTP API (`/health`, OpenAPI) | ❌ no automated test hits the actual HTTP app | ⚠️ manual `curl` only | ✅ (OpenAPI generated) | ❌ | ✅ (manual `curl` today) |
| Docker compose (both profiles) | ❌ not a unit test by nature | ✅ `docker compose config` valid both profiles (STEP 9, containers still up today) | — | — | ✅ (containers running) |
| CI/CD pipeline itself | ❌ (a pipeline can't hermetically test its own runner) | ✅ last known green at v0.3.0 (2026-10-10); **not re-verified this audit — no GitLab API token** | — | — | ⚠️ UNVERIFIED (TASK-CI-1) |
| Observability (tracing/logging/metrics) | ❌ (code doesn't exist yet) | — | — | — | ❌ (TASK-9.7-1…4) |

## Coverage gaps (stated plainly)

1. **No HTTP-level tests** for the AgentOS API itself (`personal_agent.py`) — tests exercise
   `workflow` classes directly, not the running service's routes. A `TestClient`-based test for
   `/health` (and later `/metrics`, `/ready`) is cheap and should be added in TASK-9.7-2/3.
2. **No live-gateway integration test in CI, by design** (hermetic rule) — this is a conscious
   tradeoff, not an oversight: CI must stay "no LLM, no cost". The live matrix is a manual
   deployment-check step (documented in DEPLOYMENT.md), not automated. Acceptable as long as the
   manual step actually happens per release — it has, for v0.1.0–v0.3.0, and for this audit
   (re-verified 2026-10-20, PROJECT_STATUS §5).
3. **Refine pass has no live evidence** (code is fully tested hermetically; a real
   gateway-fed run has never been captured in storage) — TASK-11-1.
4. **CI pipeline status** can't currently be re-queried programmatically — TASK-CI-1.
5. **Everything observability-related** has no test because it has no code yet — TASK-9.7-1…4.
6. **No coverage measurement** (e.g. `pytest-cov`) is wired in anywhere — acceptable at 30
   focused tests, but if the module count keeps growing (observability module next), a coverage
   floor in CI would be the natural next control. Not blocking; P2.

## How to run

```bash
# Hermetic suite — the CI-equivalent, no LLM/network/key:
uv run --with pytest python -m pytest workflow/tests -q     # expected: 30 passed

# Exactly as GitLab CI runs it (throwaway python:3.13-slim container, on 52):
bash scripts/ci-docker.sh
```
