# PROJECT_STATUS — verified audit snapshot

> **Audited: 2026-10-20 (live, with real evidence)** · Repo: `main @ 3f4fe2e` · Release: **v0.3.0**
>
> This is a **handover/audit snapshot**: every claim below was re-verified on the live servers on
> 2026-10-20, not copied from the old STEP reports. Where a claim could NOT be verified, it is
> marked as such — we do not pass undocumented items as green.

## 1. Executive status (5 lines)

The **AI Product Orchestrator** (repo `common/website/ai-product-orchestrator`, v0.3.0) is a
multi-agent, multi-model design pipeline: product brief → 13-step scored pipeline → 17-section
design + 8 deep technical documents, with a critic/fix/refine loop and a gap-filling refine pass.
**It works end-to-end today**: a real full+enrich run on the production container (run
`20261006-141735-97dda8`) completed with **40 real LLM calls, 155,998 real tokens, 3 distinct
models, 0 errors**, final design score **71** and document completeness **79/100** — meaning the
quality/document gates (thresholds 85/80) are **not being met**, and the gap pass has **no
evidence of ever being run live** (no post-80 runs exist in storage). The hermetic test suite
(**30 tests**) re-ran green in the deployed container on 2026-10-20; the live gateway
(`172.30.0.133:4000`) and all three role models (`qwen38-nothinking`/`qwen38`/`qwen38-sglang`)
were re-verified reachable on 53 (`Qwen3.8-27B-FP8`). Remaining work is concentrated in two
areas: **observability build-out** (trace_id, structured logging, `/metrics`, Prometheus/Grafana —
the STEP 9.6 "Golden Rule" baseline) and **hitting the quality gates** (score 71 vs 85,
completeness 79 vs 80) plus an evidence-backed live refine-pass run.

## 2. Phase/STEP progress (measured, 2026-10-20)

| STEP | Goal | Implemented | Tested | Progress | Open issues | Status |
|---|---|---|---|---:|---|---|
| 1 | 13-step pipeline scaffold | yes | yes (hermetic) | 100% | — | DONE |
| 2 | Multi-model routing (roles) | yes | yes | 100% | — | DONE |
| 3 | Quality loop (critic/fix/refine) | yes | yes | 100% | — | DONE |
| 4 | Quality-loop hardening (computed weighted score, targeted critic, atomic fixes, patch verifier, shared rubric; judges on `fast`) | yes | yes | 100% | — | DONE |
| 5 | Design enrichment: 8 deep docs + Document Manager + doc-completeness gate | yes | yes | 100% | — | DONE |
| 6 | Portable Docker-Compose repo; secrets scrubbed to env | yes | yes | 100% | — | DONE |
| 7 | CI/CD on server52 runner (test→deploy); clone_url fix; v0.1.0 | yes | yes (green #81, 2026-10-08) | 100% | latest pipeline re-verified only by deploy-target sync (no GitLab API token available to query pipeline list) | DONE (pipeline list UNVERIFIED today) |
| 8 | Gap-filling refine pass (`workflow.run refine`); v0.2.0 | yes | yes (hermetic) | 100% code | **no live refine-run evidence in storage** (old claim "74→82" is doc-only) | PARTIAL (code DONE, live E2E UNVERIFIED) |
| 9 | LiteLLM deployment modes (External default + Bundled sidecar), 9 new tests, v0.3.0 | yes | yes (30 tests green 2026-10-20; live side-by-side matrix from STEP 9 report, re-confirmed containers up) | 100% | — | DONE |
| 9.5 | CI runner repair (broken runner #5 deactivated; all jobs on #1) | yes | yes (pipeline green at v0.3.0, 2026-10-10) | 100% | — | DONE |
| 9.6 | Golden Rule codified: TESTING.md + OBSERVABILITY.md 14-point standard + honest gap list | yes | n/a (docs) | 100% | the observability **build** it defined is not started | DONE (as docs) |
| 9.7 | Observability build: `trace_id`, structured logging, `duration_ms`, `/metrics`, dependency-aware `/ready` | **no** | no | 0% | nothing started | NOT STARTED |
| 10 | Helm / Kubernetes packaging | no (discovery only) | no | ~10% (discovery done: no k8s cluster, no internal registry on 52/53/117) | target cluster + registry undecided | NOT STARTED |
| 11 | Hit the quality gates: final ≥85, doc completeness ≥80 with a **live, evidenced** refine pass | no | no | ~20% (thresholds exist; refine code exists; scores are 71/79 in the latest real run) | model-bound ceiling noted in STEP 4; no stronger model on the fleet today | NOT STARTED |

**Progress is measured against the stated acceptance criteria of each step (tests passing, live
evidence, or a shipped release), not against "code was written".**

## 3. Module audit (verified 2026-10-20)

Legend: ✅ = verified with evidence this audit · 📄 = only in prior docs, re-verified as code
exists but no live evidence · ❌ = confirmed missing · ⚠️ = partial.

| Module | Code | Unit/Hermetic | Integration (live) | Contract | E2E | Health | Structured logs | Global trace | Metrics | Grafana | Docs | Live-verified |
|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Manager / Orchestrator (`workflow/engine.py`, `agents/manager.py`) | ✅ | ✅ | ✅ | — | ✅ (run 97dda8, 40 calls, 0 errors) | ⚠️ process-alive only | ❌ print() | ❌ no trace_id | ❌ | ❌ | ✅ | ✅ |
| Model Router / LiteLLM integration (`workflow/router.py`, `config.py::resolve_endpoint`) | ✅ | ✅ (test_router, test_endpoint) | ✅ (endpoint → external, key_configured true) | ⚠️ via Pydantic schemas | ✅ | ✅ (gateway liveliness) | ❌ | ❌ | ⚠️ honest token ledger only | ❌ | ✅ | ✅ |
| Product Analyst (`agents/product_analyst.py`) | ✅ | ✅ | ✅ (in run 97dda8) | ✅ Pydantic `ProductAnalysis` | ✅ | — | ❌ | ❌ | ⚠️ | ❌ | ✅ | ✅ |
| Master Prompt Builder | ✅ | ✅ | ✅ | ✅ | ✅ | — | ❌ | ❌ | ⚠️ | ❌ | ✅ | ✅ |
| Task Decomposition (9 specialist tasks) | ✅ | ✅ | ✅ | ✅ | ✅ | — | ❌ | ❌ | ⚠️ | ❌ | ✅ | ✅ |
| Specialist Agents (enrichment ×8, `agents/enrichment.py`, `document_manager.py`) | ✅ | ✅ | ✅ (8 docs produced in run 97dda8, completeness 79) | ✅ | ✅ | — | ❌ | ❌ | ⚠️ | ❌ | ✅ | ✅ |
| Critic / Refiner | ✅ | ✅ | ✅ (critic_results, fix_prompts, patches in state.json) | ✅ | ✅ | — | ❌ | ❌ | ⚠️ | ❌ | ✅ | ✅ |
| Quality Gate (11-dimension weighted, computed) | ✅ | ✅ | ✅ (final_score 71 in latest run) | ✅ | ⚠️ passes code, **does not reach threshold 85** | — | ❌ | ❌ | ⚠️ | ❌ | ✅ | ✅ |
| Document Generation (10-file bundle + traceability) | ✅ | ✅ | ✅ (`technical_documents` in state.json) | ✅ | ⚠️ completeness 79 < gate 80 | — | ❌ | ❌ | ⚠️ | ❌ | ✅ | ✅ |
| State Management (`state.py`, per-run `state.json`) | ✅ | ✅ (test_state) | ✅ (11 runs on prod, 1 latest) | ✅ | ✅ | — | — | ⚠️ run_id yes, trace_id no | ⚠️ | ❌ | ✅ | ✅ |
| Token Ledger (`LlmCall` records, honest real/stub split) | ✅ | ✅ | ✅ (155,998 real tokens, 40 calls, 3 models, 0 errors) | ✅ | ✅ | — | — | ❌ | ⚠️ stored in state.json only, no /metrics | ❌ | ✅ | ✅ |
| API / AgentOS (`personal_agent.py`, :7777/:7779) | ✅ | — | ✅ (both `/health` → ok, 2026-10-20) | ✅ OpenAPI | ✅ | ⚠️ process-alive only | ❌ | ❌ | ❌ | ❌ | ✅ | ✅ |
| Docker / CI/CD (compose, Dockerfile, `.gitlab-ci.yml`, scripts/) | ✅ | ✅ (compose valid both profiles — STEP 9, re-confirmed containers up) | ✅ (7779 running, source byte-identical to git main) | — | ✅ (deploy via CI, last known green at v0.3.0) | ✅ | — | — | — | — | ✅ | ✅ (pipeline list itself UNVERIFIED — no API token) |
| Observability (tracing/logging/metrics/dashboards) | ❌ | ❌ | ❌ | — | — | ⚠️ | ❌ | ❌ | ❌ | ❌ | ✅ (the 14-point standard doc) | ❌ |

**Honest read:** the pipeline itself is real and works (verified live, with numbers above).
Everything in the observability column is genuinely absent in code — the `grep`-level check on
`workflow/*.py`, `personal_agent.py` confirms no `trace_id`, no `logging` module import, no
`/metrics` route. This matches the STEP 9.6 baseline finding exactly; nothing has been built
since.

## 4. Product-goal attainment (the actual target, not the pipeline mechanics)

Target: **Product Brief → Master Prompt → Multi-Agent Execution → Multi-Model Review → Critic →
Fix Prompts → Refiner → Quality Gate → Approved Technical Documents.**

Measured against the latest real run (`20261006-141735-97dda8`, prod container, 2026-10-06):

| Deliverable | Produced | Reviewed (multi-model) | Versioned | **Approved (gate passed)** |
|---|---|---|---|---|
| Product Specification (17-section design, `product_specification` section) | ✅ | ✅ (3 models) | ✅ (design_versions, version 3) | ❌ final_score 71 < 85 |
| Architecture (section) | ✅ | ✅ | ✅ | ❌ (part of 71) |
| Database / ERD / DDL | ✅ produced | ✅ | ✅ | ❌ — completeness 79, DDL gaps **named** by the gate ("Missing concrete database schema definitions (DDL)...") |
| API / OpenAPI | ✅ produced | ✅ | ✅ | ❌ — OpenAPI gaps **named** ("Lack of detailed API endpoint specifications (OpenAPI/Swagger)...") |
| Backend Master Prompt / Design Doc | ✅ | ✅ | ✅ | ⚠️ doc completeness 85 (this one alone is ≥80) |
| Frontend / UI / UX Master Prompt / Docs | ✅ | ✅ | ✅ | ⚠️ frontend 80 / UX 70 (UX below 80) |
| Unit / Integration / E2E Test Specifications | ✅ | ✅ | ✅ | ⚠️ testing 75 (below 80) |
| Security | ✅ | ✅ | ✅ | ✅ security 80 (meets 80) |
| Deployment / Observability | ✅ | ✅ | ✅ | ⚠️ deployment 85 / observability 40 (observability badly below) |

**"Produced" vs "Approved":** every document is produced, versioned, and reviewed by 3 models —
but **none of the two overall gates (design ≥85, document-completeness ≥80) are passed** in the
only full run we have evidence for. The refine pass, which exists specifically to close the named
gaps (DDL, OpenAPI, payment/reporting, observability, UI flows), **has no live run evidence** —
the only storage runs found are pre-refine (Oct 5–6). So the honest status of the end goal is:
**the machine runs, the documents are real and traceable, but "Approved Technical Documents" is
not yet achieved, and we have no evidence the refine pass works on a real, current gateway.**

## 5. Evidence log (what this audit actually checked, 2026-10-20)

| Check | Method | Result |
|---|---|---|
| Repo identity | `git log`/`git ls-remote origin HEAD` locally + remote `http://172.30.0.133:81/...` | local `main` = remote `HEAD` = `3f4fe2e`; clean tree |
| Deploy target in sync | `md5sum` of `workflow/engine.py`, `workflow/config.py`, `README.md` on 52 vs local main | **identical** — 7779 is running exactly git `main` |
| Containers | `docker ps` on 52 | `agno-agentos` (7777, prod, up 2w, healthy), `agno-agentos-repo` (7779, deploy target, up 9d, healthy) |
| Health | `curl :7777/health`, `:7779/health` | both `{"status":"ok"}` |
| Resolved endpoint (7779) | `workflow.run endpoint` | mode `external`, `http://172.30.0.133:4000/v1`, key configured (never printed) |
| Gateway | `:4000/health/liveliness` + `/v1/models` (17 models listed) | up |
| Model smoke (1 call each, ≤15 tokens) | real chat completion via gateway | `qwen38-nothinking` → "OK" (19 tok); `qwen38`/`qwen38-sglang` → empty content, 72 tok (thinking budget consumed — **expected, documented behavior**, why structured work runs on `fast` only) |
| Backends on 53 | `:8000/v1/models`, `:8001/v1/models` | both 200, both `Qwen3.8-27B-FP8` |
| Hermetic tests | `uv run --with pytest python -m pytest workflow/tests -q` inside `agno-agentos-repo` | **30 passed in 0.83s** |
| Real E2E run | `state.json` of run `20261006-141735-97dda8` (prod volume) | status `completed`, 40 real calls, 155,998 real tokens, 3 models, 0 non-ok calls, final_score 71, doc completeness 79, gaps named |
| GitLab CI pipeline list | attempted GitLab API with runner token, then (post-audit) pushed the docs-only commit `378ea5b` itself | **no token found** → could not re-query the pipeline *list* directly, **but the push itself triggered a full green cycle, observed live at 12:55 UTC**: test job passed (30/30), image rebuilt, `agno-agentos-repo` recreated + healthy, new docs file present on the deploy target. CI is therefore green **today**, re-verified by side effect. The *durable, queryable* pipeline-status check is still missing → TASK-CI-1. |
| Storage on 7779 deploy target | `find` in compose volume | **empty** — no runs have ever been executed on the 7779/deploy-target instance (only on prod 7777); noted, not a defect |
| Secrets | none printed at any point; gateway key read into a shell variable only, never echoed | ✅ |

## 6. Where the old reports and reality agree / diverge

**Agree (re-confirmed live):** repo/CI/deploy pipeline structure, 30-test hermetic suite, dual
LiteLLM modes, dual 7777/7779 instances, "thinking models can't emit structured JSON" (just
reproduced live: `qwen38` returned `content: None`, 72 reasoning tokens on a 15-token request),
and — after the docs-only push of this very audit — **the CI→deploy pipeline end-to-end is green
right now** (pipeline triggered by commit `378ea5b`, test job passed, 7779 rebuilt + healthy).

**Diverge / could not re-verify:**
- **Latest CI pipeline green** — last documented green is 2026-10-10 (v0.3.0). No GitLab API
  token was available to re-query this today; the deploy target is provably at `3f4fe2e`/v0.3.0
  and healthy, which is consistent with "deploy succeeded" but does not re-prove the pipeline
  itself. → mark **UNVERIFIED**, re-check by pushing a docs-only commit (next task) or by opening
  GitLab UI.
- **STEP 8 "74→82" refine gain** — no live run in storage shows a post-refine score; treat as
  documented-but-not-currently-evidenced.
- **STEP 9.6 gap list** — fully re-confirmed accurate: no `trace_id`, no `logging` module, no
  `/metrics`, no Prometheus/Grafana wiring in this repo, health is process-alive only.

## 7. Immediate next STEP (recommended)

**STEP 9.7 — Observability build** (see [ROADMAP.md](ROADMAP.md), TASK-9.7-1…4). Rationale: it is
the codified Golden Rule, it is already scoped and doc'd (14-point standard in
[OBSERVABILITY.md](OBSERVABILITY.md)), it is additive (no behavior change to the pipeline), and
its outputs (trace_id, duration_ms, /metrics) are **prerequisites** for properly measuring whether
the quality gates (STEP 11) can be reached — without per-step latency/trace, we cannot tell if the
71-score ceiling is prompt-bound, model-bound, or iteration-bound.
