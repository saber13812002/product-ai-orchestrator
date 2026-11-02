# AI HANDOFF — pick up where this left off

> **Read this first if you are an AI (or a new human) taking over the project.** It is a
> single-page snapshot of the current state: what the project is, where it lives, what
> version it is, what's done (STEPS 1–9), what's open, and what STEP 10 is.

_Last updated: **2026-11-02 (STEP 1 baseline finalization — see §0a; ⚠️ server 52 was DOWN at
audit time, so all 52-side state is UNVERIFIED this round)** ·
Previous: 2026-10-21 (re-audit, live re-verification — state unchanged since 2026-10-20) ·
Latest release: **v0.3.0** · `main` = `299f1a3` (local; **remote HEAD unverified — 52 down**) ·
Test suite: **30 tests** (hermetic) · **Golden Rule (tests + observability) codified in STEP 9.6** ·
**Full verified audit: [PROJECT_STATUS.md](PROJECT_STATUS.md)** ·
**2026-10-21 audit bundle (4 reports): [../audit_2026_10_21/](../audit_2026_10_21/)** ·
**Work order: [ROADMAP.md](ROADMAP.md)** · **Test map: [TEST_MATRIX.md](TEST_MATRIX.md)** ·
**Living test/observability checklist: [PROJECT_TEST_AND_OBSERVABILITY_CHECKLIST.md](PROJECT_TEST_AND_OBSERVABILITY_CHECKLIST.md)**._

### 0a. 2026-11-02 — STEP 1: project baseline finalization (decision history / done / remaining)

This section is the authoritative record for the "prepare to start Observability (STEP 2) + first
real product Workflow run" baseline pass. **Per the Golden Rule, every claim below was re-verified
from the real Git and server state — nothing was assumed unchanged** (and that check surfaced two
material changes: the local repo moved, and server 52 went down).

**Decision history (who decided what, and why):**

| Date | Decision | Rationale / authority |
|---|---|---|
| 2026-10-20 | Audit first; no code changes; 4 report files | User audit prompt; Golden Rule |
| 2026-10-21 | Commit the re-audit bundle on a **separate `docs/` branch** + create **MR !1** (not a direct main commit) | User: "independent docs branch … no merge/deploy this stage"; MR keeps main clean |
| 2026-10-21 | Do **not** merge MR !1 without explicit user approval | User: "بدون تأیید صریح من Merge نکن" |
| 2026-11-02 | Baseline finalization must verify **real** Git + server state, not assume it | User STEP 1: "فرض نکن هنوز تغییر نکرده‌اند" |
| 2026-11-02 | **No merge, no direct main commit, no Production change, 7777/7779 untouched, no expensive LLM test** | User STEP 1 hard constraints (still in force) |
| 2026-11-02 | **Block STEP 2 (Observability) on user restoring server 52** | 52 is down → cannot push, merge, run full CI, or verify deploy; doing STEP 2 blind violates Golden Rule |

**What was DONE and verified this session (2026-11-02) — with evidence:**

| # | Check | Method | Result |
|---|---|---|---|
| 1 | Local repo location | `find` + `git` | **MOVED** from `server52and53/ai-product-orchestrator` to **`rag/rag-support/ai-product-orchestrator`** (old path gone). All work now done from the new path. |
| 2 | Local `main` | `git rev-parse main` | `299f1a3` (matches 2026-10-21 record) |
| 3 | Local docs branch | `git rev-parse docs/audit-baseline-2026-10-21` | `44d3223` (1 commit ahead of main) |
| 4 | Working tree | `git status --short` | clean |
| 5 | Remote GitLab (52:81) | `git fetch`, `/dev/tcp` probe | **UNREACHABLE** — 52 down (see #8). Local `origin/*` refs are the **stale local mirror**, not live remote state. |
| 6 | MR !1 / pipeline / GitLab API | gitlab-rails (needs 52) | **UNVERIFIED — 52 down.** MR !1 was last known open + pipeline 202 green on 2026-10-21. |
| 7 | Secret scan + `git diff --check` (docs branch) | `grep` over the 4 reports/README/AI_HANDOFF + `git diff main..docs` | **0 secrets**; `git diff --check` **clean** (exit 0); diff is **purely additive** (587 + / 9 −) |
| 8 | Hermetic tests (local) | `pytest` on the agno-free modules (`test_state`, `test_endpoint`) | **15 passed in 0.37s.** The other 6 modules import `agno`, which **cannot install on this laptop** (32-bit Python 3.14 → no wheels for `pyyaml`/`greenlet`, needs MSVC). **Full 30/30 therefore re-runs only in the 52 container (down) or in CI.** |
| 9 | Doc cross-links (docs branch) | `grep` over README/AGENTS/AI_HANDOFF | **All 4 audit reports + Roadmap + Test Matrix + living checklist linked** from README, AI_HANDOFF, and (as §9 refs) — consistent. |
| 10 | CI deploy blast-radius | read `.gitlab-ci.yml` | `deploy` runs **only** on `main` / a tag / manual web trigger — **never from an MR or the docs branch**. So **merging MR !1 will rebuild+restart 7779**; an MR pipeline only runs the `test` stage. |

**Server 52 status (the blocker):** at 2026-11-02 ~13:26–13:35 UTC, **52 (172.20.1.52) is
completely unreachable** — SSH :22 and Git :81 both time out from the laptop, **and** from 53
(which is itself up: `ssh jump53` OK). 53 also reports **no route to 52** on :22/:81/:4000/:7777/
:7779/:9090. This is a network/host outage on 52, not a laptop problem. **Consequently, none of
this could be verified today:** live remote `HEAD`, MR !1 existence/state, pipeline status,
7777/7779 health, the deploy target, or the md5 sync-vs-main check. **Everything 52-side is
marked UNVERIFIED, not assumed green.**

**Remaining work (in order, to reach "ready for STEP 2 + first Workflow run"):**

1. **Restore server 52 reachability** (user infra — power/network). Re-run: `git fetch`, MR !1 +
   pipeline check (gitlab-rails), 7777/7779 `docker ps` + `/health`, deploy-target md5 vs main,
   and the **full 30-test in-container** hermetic run.
2. **User merges MR !1** (docs baseline → main). *Note #10: this triggers a 7779 rebuild — confirm
   52 is stable + user accepts the 7779 restart before merging.*
3. **`feat/observability-baseline`** (STEP 2 / ROADMAP TASK-9.7-1…3): `workflow/observability.py`
   (trace_id + structured logging + duration_ms), independent Prometheus `/metrics` (separate path
   from Agno's JSON one), dependency-aware `/ready`, all hermetic-tested. Separate MR; no merge
   without approval.
4. **TASK-11-1** — one bounded, isolated (never 7777/7779) live refine run with before/after
   evidence; **needs its own budget approval** (~210k-token cap).
5. **TASK-9.7-4** — Prometheus job + Grafana dashboard on 52 (reuses the existing 52 stack).
6. Open user decisions unchanged: model/threshold (85/80 gates) and Helm/K8s + registry (TASK-11-2,
   TASK-10-1).

### 0. 2026-10-21 re-audit (what changed / what didn't)

**State is unchanged** from the 2026-10-20 audit — everything below was re-verified live on
2026-10-21 (evidence, not claims):

| Item | 2026-10-20 | 2026-10-21 re-check |
|---|---|---|
| `main` / deploy target | `299f1a3` / byte-identical | ✅ same — md5 of 3 files = `git show main` |
| 7777 / 7779 | both healthy | ✅ both healthy (up ~11h each) |
| 30 hermetic tests | green | ✅ **re-run in-container: 30 passed in 0.83s** |
| Gateway :4000 + model call | live, 1 call | ✅ liveliness 200; 1 call: `qwen38-nothinking` → "OK", **19 tokens** |
| Refine pass live evidence | none | ❌ still none (storage unchanged) |
| Observability in code | 0% (grep) | ✅ still 0% (grep re-run) |
| GitLab pipeline list | not queryable | ❌ still not queryable (no token) |

**New findings from the 2026-10-21 audit:**
1. **`/ready` → 404** on 7779 (endpoint not built — TASK-9.7-3).
2. **`/metrics` exists but is Agno's built-in JSON endpoint** (`{"metrics":[],"updated_at":null}`),
   **not Prometheus** — TASK-9.7-2 must pick a separate path (e.g. `/metrics/prometheus`) or
   replace it; the name collision is documented in the audit's test report.
3. **GitLab stack (gitlab/postgres/redis) restarted ~07:00 UTC 2026-10-21** (uptime ~11h at audit
   time); runner logged `502 Bad Gateway` on `jobs/request` at 06:52 UTC — consistent with the
   restart window; last deploy (the `299f1a3` docs push) succeeded 11h earlier, so CI is believed
   intact, **to be confirmed in TASK-CI-1**.
4. **No custom settings form / admin UI exists** — the only UI is Agno's standard one. Whether a
   settings form is in scope is an open user decision (stage 4 of the audit roadmap).

**Where the 2026-10-21 audit bundle lives:** repo-root [`audit_2026_10_21/`](../audit_2026_10_21/)
— `PROJECT_STATUS_REPORT.md` (executive dashboard + 12 sections), `PROJECT_ARCHITECTURE.md`
(mermaid + request flow), `PROJECT_TEST_REPORT.md` (17 tests, 12 PASS / 2 SKIPPED / 1 BLOCKED),
`PROJECT_ISSUES_AND_ROADMAP.md` (11 issues, 6-stage roadmap, 6 open user decisions).

## 1. What this is

The **AI Product Orchestrator**: a multi-agent, **multi-model** pipeline built on
[Agno AgentOS](https://github.com/agno-agi/agno). Give it a product **brief**; it runs a scored
**13-step design pipeline** → a **17-section system design**, then an **enrichment layer** →
**8 deep technical documents**, then a **gap-filling refine pass** that closes the specific
completeness gaps the document gate names (DDL, OpenAPI, payment/reporting, observability, UI
flows). Every LLM call goes through **one LiteLLM gateway**, and the whole thing deploys with
**Docker Compose** in two modes (External gateway, or a Bundled sidecar).

## 2. Where it lives

| Thing | Location |
|---|---|
| **Git repo** | `https://git.ai.ismc.ir/common/website/ai-product-orchestrator` (internal GitLab CE on server 52; git over `http://172.20.1.52:81`). Private. |
| **Laptop working tree** | `C:\Users\s.tabatabaei\Documents\saberprojects\server52and53\ai-product-orchestrator` |
| **Deploy target (52)** | `/home/saber/saberprojects/ai-product-orchestrator` — container `agno-agentos-repo`, port **7779** (the CI deploy target). |
| **Production (52)** | `/home/saber/agentos/` — container `agno-agentos`, port **7777**. **NOT managed by this repo — never touch it.** |
| **Per-step reports (laptop)** | `server52and53/STEP*_REPORT.md` (one level up) |

### The model-fleet servers

| Server | What it runs | Reach |
|---|---|---|
| **52** (172.20.1.52) | GitLab, CI runners, the production + deploy AgentOS instances, and the **external LiteLLM gateway** (`:4000`). | SSH alias `s52` from the laptop. |
| **53** (172.20.1.53) | The **Qwen3.8-27B model backends**: vLLM `:8000` (nothinking), vLLM `:8001` (sglang). These are what the external gateway and the bundled sidecar route to. | Via 52 (jump). |
| **117** | Unrelated AI services (BGE-M3 embeddings, Whisper) — **not** used by this orchestrator. | — |

## 3. Version & state

- **Latest release:** **v0.3.0** (Semantic Versioning — see [RELEASES.md](RELEASES.md)).
- **Package version** (`pyproject.toml`): `0.3.0` (the **git tag** is canonical).
- **Test suite:** **30 hermetic tests** (was 21 in v0.2.0; STEP 9 added 9 in
  `workflow/tests/test_endpoint.py`). No LLM, no network, no API key — this is what CI runs.
- **CI:** GitLab pipeline on the root `server52` runner (**`AI-TOOLS`, runner #1**) — hermetic
  tests → deploy `main` to 7779. **Green** (verified 2026-10-10). The broken user-mode runner
  `aio-server52` (#5) was **stopped + deactivated** (see §7) so it can no longer steal jobs.

## 4. Architecture (one paragraph)

`personal_agent.py` boots the AgentOS HTTP service (`:7777`). `workflow/run.py` is the CLI
(`smoke` / `routing` / `full` / `enrich` / `refine` / `endpoint`). The **Manager** agent decomposes
a brief into a 13-step pipeline run by `workflow/engine.py`; a **ModelRouter** maps a logical
role (`fast`/`deep`/`alt`/`stub`) to a real LiteLLM model name and records an honest token
ledger. After the design is finalized, 8 **enrichment agents** write deep documents, a
deterministic **Document Manager** assembles the 10-file bundle, and a **document-completeness
gate** scores them; the **refine pass** re-runs only the gapful documents. Full detail:
[ARCHITECTURE.md](ARCHITECTURE.md).

### Model routing (the portability core)

| Role | Default model | Thinking | Used for |
|---|---|---|---|
| `fast` | `qwen38-nothinking` | **OFF** | All structured steps (analyst, master prompt, decomposition, judges, 8 enrichment docs). **Must** reliably emit complete JSON. |
| `deep` | `qwen38` | ON | Free-text tasks (TASK-01, TASK-05) — satisfies "≥3 models". |
| `alt` | `qwen38-sglang` | ON | A second/third engine, free-text tasks. |
| `stub` | `mock-agent-v1` | — | Deterministic routing proof only; never in real totals. |

The **thinking models cannot emit structured JSON** over a large design (they spend their whole
output budget reasoning) — so all structured/judge work runs on `fast`. That's why
`workflow/config.py::TASK_MODEL_HINTS` (TASK-01→`deep`, TASK-05→`alt`) is authoritative.

### LiteLLM deployment modes (STEP 9)

One resolver — `workflow/config.py::resolve_endpoint()` — returns `(base_url, api_key)` for the
active mode; everything consumes that.

- **Mode A — External (default):** you run a LiteLLM gateway; `.env` sets `LITELLM_BASE_URL` +
  `LITELLM_API_KEY`; start with `docker compose up -d`. Legacy `OPENAI_*` names remain a fallback.
- **Mode B — Bundled sidecar:** no gateway on the server; `LITELLM_MODE=bundled` +
  `LITELLM_MASTER_KEY` + `*_MODEL_API_*` backends; start with
  `docker compose --profile bundled-litellm up -d`. The repo starts its own LiteLLM sidecar
  (`litellm/`), health-gated. **The sidecar is strictly optional** — `docker compose up -d`
  never starts it.

Full details: [LITELLM.md](LITELLM.md).

## 5. STEPS 1–10 (what's done)

| Step | What | Status |
|---|---|---|
| **1–3** | 13-step pipeline, multi-model routing, quality loop | ✅ |
| **4** | Quality-loop fix — full-context gate, computed weighted score, targeted critic, atomic fixes, patch verifier, shared rubric. Rerouted judges to `fast` (thinking models can't do structured JSON). | ✅ |
| **5** | Design enrichment — 8 deep docs + deterministic Document Manager (10 files + traceability) + document-completeness gate. | ✅ |
| **6** | Portable Docker-Compose repo; master key scrubbed to env-only. | ✅ |
| **7** | CI/CD on the `server52` runner (test → deploy); `clone_url` gotcha fixed; first green pipeline #81. Released **v0.1.0**. | ✅ |
| **8** | Gap-filling **refine pass** (`workflow.run refine`) — targeted 2nd pass re-runs only the gate's gapful docs. Live 74→82. Released **v0.2.0**. | ✅ |
| **9** | **LiteLLM deployment modes** — External (default) + Bundled sidecar; single `resolve_endpoint()`; sidecar `litellm/` with an env-rendering entrypoint (the official image doesn't expand `${VAR}` in a mounted config); health-gated startup; `workflow.run endpoint` CLI; 9 new tests (suite 30). Released **v0.3.0**. | ✅ |
| **9.5** | **CI runner repair** — the user-mode runner `aio-server52` (#5) failed every job at `prepare environment: exit status 1` and was stealing (load-balancing) jobs away from the healthy root runner #1, leaving the pipeline red and 7779 stuck on v0.2.0. Stopped #5 + deactivated it in GitLab (`active=false`); all `server52` jobs now run on #1. Real green pipeline for `main` @ v0.3.0 → 7779 auto-deployed to v0.3.0. | ✅ (this session) |
| **9.6** | **Testing & Observability Baseline + the Golden Rule.** Codified the permanent rule — *nothing is complete without BOTH tests AND an observable/traceable execution path* — into the repo: new `docs/TESTING.md` (Test Matrix + Definition of Done), `docs/OBSERVABILITY.md` (the 14-point standard + honest gap list), plus `TRACING`/`LOGGING`/`HEALTHCHECKS`/`METRICS`/`GRAFANA`/`CI_CD`. README links all of them; the rule is stated up top. **Baseline finding (honest):** we have `run_id` + an honest per-call token ledger + per-step state persistence + a CLI run-report + 30 hermetic tests — but **no `trace_id`, no `logging` module (everything is `print()`), no duration/latency, no `/metrics`, no Prometheus/Grafana, and health is process-alive only.** No code changes in this step (measure first, build second). | ✅ (this session) |

## 6. Latest tests & verification (STEP 9)

- **Hermetic CI:** 30 passed, no regression.
- **Compose valid for both profiles:** default → `[agno-agentos]`; `--profile bundled-litellm` →
  `[litellm, agno-agentos]`.
- **Live matrix (all on 52, isolated compose project `-p aio9test`/`-p aio9ext` — 7777/7779
  never touched):**
  - **A — External:** real smoke via the 52 gateway `:4000`, 441 tok, no sidecar.
  - **B — Bundled, side-by-side:** both `agno-agentos` + `litellm-sidecar` `healthy`;
    `endpoint` → `bundled` / `http://litellm:4000/v1`.
  - **C — Routing:** `fast`/`deep`/`alt` resolve; the sidecar serves
    `qwen38-nothinking` / `qwen38` / `qwen38-sglang`.
  - **D — Real agent call:** Manager → Product Analyst (fast) → **Sidecar** → raw vLLM 53:8000 →
    structured `ProductAnalysis`, 497 tok, status `completed`. **Fully self-contained**
    (sidecar → local model, no external gateway/key) — proves the sidecar is a turnkey gateway.

## 7. Open problems / watch items

- **Score ceiling ~74** on the 11-dimension design gate: the heavy dimensions are maxed, a
  5%-weight tail drags the mean. Lifting it needs a **stronger model**, not another loop
  iteration (see STEP 4 diagnosis).
- **Document completeness ~82** after the refine pass (target 85+); the refine pass gets there
  on most briefs but the tail is model-bound.
- **CI deploys `main` to 7779** on every push. The deploy target's `.env` is guarded by
  `scripts/deploy-repo.sh` (backed up / restored across redeploys), but a fresh push recreates the
  container — that's intended and fine; just be aware 7779 briefly restarts.
- **52 disk** was a watch item (~74%); the GitLab log bleed (~0.3–0.6 GB/day, no rotation) is
  still worth rotating. See the sibling memory `server52-disk-state`.

## 7. Observability baseline (STEP 9.6 — the Golden Rule)

**The rule (now permanent for this repo and all future projects):** no module, agent, API,
pipeline, or deployment is **complete** without **both** tests **and** an observable, traceable
execution path. Full 14-point standard → [OBSERVABILITY.md](OBSERVABILITY.md); the Test Matrix +
Definition of Done → [TESTING.md](TESTING.md).

**What we already have (genuine):**
- `run_id` (`YYYYMMDD-HHMMSS-<6hex>`) keys every run's `state.json` + artifacts.
- A **honest per-call token ledger** (`LlmCall`: model, role, in/out/reasoning tokens, status,
  is_stub) — a real metric source, currently stored only in `state.json`.
- Per-step state persistence (run reconstructable from disk) + a CLI **run report**
  (summary, steps, per-model tokens, quality scores, errors, final status).
- 30 hermetic tests (no LLM/network/key); Pydantic schemas as data contracts; AgentOS OpenAPI.
- Two process-alive health endpoints: AgentOS `/health`, LiteLLM `/health/liveliness`.

**What's missing (the build — STEP 9.7 → 10):**
- ❌ `trace_id` + cross-process propagation (AgentOS HTTP run vs CLI run not linked).
- ❌ a `logging` module / structured per-step events (everything is `print()`).
- ❌ duration/latency per step and per call (so no P50/P95/P99).
- ❌ a `/metrics` (Prometheus) endpoint; ❌ Prometheus + Grafana (incl. the Workflow Dashboard).
- 🟡 health is process-alive only — no dependency-aware `/ready` (LiteLLM/DB probe).
- ❌ CI Lint/Contract/Security stages and a post-deploy smoke run (current CI = test→deploy+health-wait, green & reliable).

**Sequencing:** the baseline (this step) is *documentation + matrix only* — no code. The build is
**STEP 9.7** (`workflow/observability.py`: `trace_id` + structured logging + `duration_ms`;
`/metrics`; dependency-aware `/ready`), then **STEP 10 (Helm/K8s)** ships readiness/liveness
probes, a Prometheus ServiceMonitor, Grafana dashboards, resource metrics, and a post-deploy
smoke **from the start**.

## 8. Next — STEP 10 (Helm / Kubernetes)

Package the orchestrator (and its optional bundled-LiteLLM sidecar) as a **Helm chart** so it can
be deployed to a Kubernetes cluster instead of / alongside a single Docker-Compose host. Likely
surface:

- A chart with the AgentOS deployment + optional `litellm` sidecar (mirroring the two modes).
- `ConfigMap`/`Secret` for the `.env` values (mode, endpoint, model names, master key).
- `Service`/`Ingress` for `:7777` (AgentOS) and, in bundled mode, the sidecar (keep loopback/
  internal-only).
- A `PVC` for `/data` (AgentOS state) and, if bundled, `litellm-data`.
- Reuse the existing `Dockerfile` image (no code change expected — this is a packaging step).

### Discovery results (2026-10-10 — read before implementing)

A read-only discovery pass on server 52 found **no existing Kubernetes cluster and no existing
internal Docker registry**. Consequences for the plan:

- **No k8s on 52** (and no reachable one on 53/117): `kubectl`/`helm`/`k3s` not installed, no
  `~/.kube/`, no k8s systemd service, 6443/6444 closed on 53/117. The only container runtime is
  `containerd` backing Docker. → STEP 10 must either (a) build the chart now + a local single-node
  test cluster (e.g. `k3s` on 52, pending disk decision), or (b) target a cluster to be provisioned.
- **No internal registry**: no Harbor/registry container; **GitLab CE 16.3.9 `container_registry`
  feature is OFF** (default off in CE 16; enabling it requires `feature_flags enable
  container_registry` + `gitlab-ctl reconfigure`, an admin-side change) — this is the cleanest
  internal option (`registry.git.ai.ismc.ir`-style URL) if the user wants it. The DNS names
  `harbor.ai.ismc.ir` / `registry.ai.ismc.ir` resolve (80.191.92.189) but serve **no** registry
  (aPanel/Next.js vhost, 308 redirect). 53:8083 is OpenCSG (a model hub SPA, **not** OCI).
- **52 CAN reach public registries** (`registry-1.docker.io`, `ghcr.io`, `quay.io` :443 open;
  `docker pull` OK) → pushing to ghcr/docker.io is technically possible (needs an account/token),
  but public hosting of internal app images is a user decision.
- **Image** `ai-product-orchestrator:latest` is **~546 MB**; 52 disk is **~90% full (52G free)** —
  pushing 1–2 more images is fine, but a large local registry/cluster would need the disk
  cleanup/rotation watch item addressed first.
- **Suggested image naming** (for whichever registry):
  `<registry>/ai-product-orchestrator:0.3.0` and `<registry>/litellm-sidecar:<pinned>` (or reuse
  the official LiteLLM image for the sidecar — preferred, no build needed).

**Decision needed before implementation: (1) target cluster (provision k3s on 52 vs external),
(2) registry (enable GitLab CE registry vs public ghcr vs a new local registry).**

## 8a. 2026-10-20 handover audit — what changed in the picture

A full, evidence-based audit (live server checks, no code changes) was performed on 2026-10-20.
Full detail: [PROJECT_STATUS.md](PROJECT_STATUS.md). Headlines:

- **Repo, deploy, and tests all re-confirmed real:** local `main` = remote `HEAD` = `3f4fe2e`;
  7779's deployed source is **byte-identical (md5)** to git `main`; `agno-agentos` (7777, prod)
  and `agno-agentos-repo` (7779, deploy target) both healthy; **30/30 hermetic tests pass**
  re-run in the deployed container; live gateway `:4000` + all three role models
  (`qwen38-nothinking`/`qwen38`/`qwen38-sglang`) re-verified, backed by `Qwen3.8-27B-FP8` on 53.
- **A real full+enrich run exists and was inspected** (prod, run `20261006-141735-97dda8`):
  40 real LLM calls, **155,998 real tokens**, 3 distinct models, 0 errors, final design score
  **71**, document completeness **79/100**, with the gate **naming** the specific gaps
  (missing DDL, missing exact OpenAPI, weak observability/UI flows). This is the single most
  important artifact for calibrating what "Approved Technical Documents" still requires.
- **The quality gates are NOT being met by the pipeline as configured** (71 < 85 design gate,
  79 < 80 document gate). This is consistent with the old STEP 4 "model-bound ceiling" note —
  it was never going to close with another loop iteration on the current fleet.
- **The refine pass has no live-run evidence in storage** (all prod runs are pre-refine, Oct
  5–6). The STEP 8 "74→82" figure is a documented claim, not re-verified. **Do not treat the
  refine pass as proven on a current gateway until TASK-11-1 is done.**
- **7779 (deploy target) has an empty storage volume** — no runs have ever executed there, only
  on 7777 (prod). Not a defect, but means "the deployed instance" and "the instance with
  evidence" are different machines; keep that straight when reporting.
- **GitLab CI pipeline list could not be re-queried** (no API token in
  `/etc/gitlab-runner/config.toml`, none on the laptop). Treat "CI green today" as
  last-known-good (v0.3.0, 2026-10-10), not re-verified — TASK-CI-1 fixes this.
- **Nothing in the observability gap list (STEP 9.7) has been built since** — re-confirmed by
  direct grep of `workflow/*.py`: no `trace_id`, no `logging` import, no `/metrics`.

**Net: the machine is real, deployed, tested, and works — but the end goal
("Approved Technical Documents") is not yet met, and the next real work is the observability
build (STEP 9.7) plus one evidenced live refine run (STEP 11), in that order. Full task list
with acceptance criteria: [ROADMAP.md](ROADMAP.md).**

## 9. Where to read next

- **[LITELLM.md](LITELLM.md)** — the two deployment modes in depth.
- **[ARCHITECTURE.md](ARCHITECTURE.md)** — components, the 13-step pipeline, quality loop,
  enrichment, refine pass, routing.
- **[DEPLOYMENT.md](DEPLOYMENT.md)** — end-to-end install for both scenarios.
- **[CONFIGURATION.md](CONFIGURATION.md)** — the full environment-variable reference.
- **[AGENTS.md](../AGENTS.md)** — commands, CI/CD gotchas, hard rules.
- **[RELEASES.md](RELEASES.md)** — changelog + how to cut a release.
- **Golden Rule / observability (STEP 9.6):** [TESTING.md](TESTING.md) (matrix + DoD),
  [OBSERVABILITY.md](OBSERVABILITY.md) (14-point standard + gap list), [TRACING.md](TRACING.md),
  [LOGGING.md](LOGGING.md), [HEALTHCHECKS.md](HEALTHCHECKS.md), [METRICS.md](METRICS.md),
  [GRAFANA.md](GRAFANA.md), [CI_CD.md](CI_CD.md).

## 10. Hard rules (carry these into every change)

1. **No secrets in the repo.** `.env` is gitignored; only `.env.example` is tracked. The LiteLLM
   master key is a live credential — never print or commit it.
2. **CI stays hermetic.** No test may need network/LLM/keys.
3. **Structured output only from `fast`.**
4. **LF line endings** (`.gitattributes`).
5. **Commits end with** `Co-Authored-By: Claude Opus 5 <noreply@anthropic.com>`.
6. **Never recreate the production (7777) or deploy-target (7779) instances in tests** — use a
   separate compose **project** (`docker compose -p myproj ...`), not just a different
   `container_name`/port.

## 11. Next-chat checkpoint prompt (self-contained)

Copy-paste this into a new session to hand the project off:

```
PROJECT HANDOFF — AI Product Orchestrator (start here, read docs/AI_HANDOFF.md + docs/PROJECT_STATUS.md first)

REPO: https://git.ai.ismc.ir/common/website/ai-product-orchestrator
  - git remote (works from laptop + server 52): http://172.20.1.52:81/common/website/ai-product-orchestrator.git
  - Current commit on main: 3f4fe2e — verified identical to remote HEAD on 2026-10-20. Do not assume
    you're starting from a clean slate: a full evidence-based audit was completed 2026-10-20 and is
    recorded in docs/PROJECT_STATUS.md, docs/ROADMAP.md, docs/TEST_MATRIX.md.
  - Releases: v0.1.0 (STEP 7), v0.2.0 (STEP 8), v0.3.0 (STEP 9) — v0.3.0 is current.

SERVERS:
  - 52 (172.20.1.52): GitLab CE, CI runner (root, #1 "AI-TOOLS"), two AgentOS instances:
      * agno-agentos  -> port 7777, PRODUCTION, /home/saber/agentos/ — NOT managed by this repo, never touch
      * agno-agentos-repo -> port 7779, CI deploy target, /home/saber/saberprojects/ai-product-orchestrator
    Verified 2026-10-20: both healthy; 7779 source is byte-identical (md5) to git main @ 3f4fe2e.
  - 53 (172.20.1.53): model backends — Qwen3.8-27B-FP8 vLLM on :8000 (nothinking) and :8001 (sglang).
    Reachable from 52. SSH: `ssh -p 22 saber@172.20.1.52` (port 22, NOT the s52 alias/2222 which is aPanel's
    separate instance); 53 via `ssh jump53`.
  - LiteLLM external gateway (the one AgentOS uses): container learn-lite-llm-litellm-1 on 52, :4000,
    17 models registered. LITELLM_BASE_URL=http://172.20.1.52:4000/v1. Never print its master key.
    NOTE: do not confuse with litellm-personal (separate project, :4101) — that is a different LiteLLM
    instance used by other ismc projects, not this one.

MODEL ROUTING (verified working 2026-10-20):
  fast=qwen38-nothinking (ALL structured/judge work — the thinking models below return empty content,
  confirmed live, so this split is load-bearing, not a preference)
  deep=qwen38, alt=qwen38-sglang (free-text tasks only, satisfies "≥3 distinct models")

WHAT WORKS (evidence, 2026-10-20):
  - 30/30 hermetic tests pass (no LLM/network/key) — re-run inside the deployed container.
  - Real full+enrich pipeline run on prod (run 20261006-141735-97dda8): completed, 40 real LLM calls,
    155,998 real tokens, 3 models, 0 errors. Final design score 71, document completeness 79/100.
  - Docker compose deploys both LiteLLM modes (external default, bundled sidecar optional profile).

WHAT IS NOT TRUE YET (do not let old reports convince you otherwise):
  - Quality gates are NOT met: design gate needs 85 (we're at 71), document-completeness gate needs 80
    (we're at 79). The refine pass (which exists specifically to close named gaps: DDL, OpenAPI,
    observability, UI flows) has NO live-run evidence in storage — the STEP 8 "74→82" number is
    documented, not re-verified.
  - No trace_id, no structured logging, no /metrics, no Prometheus/Grafana wired to THIS app
    (STEP 9.7, entirely unbuilt — the Golden Rule's observability half).
  - CI pipeline "green" was last verified 2026-10-10 (v0.3.0); it could NOT be re-queried 2026-10-20
    (no GitLab API token anywhere we looked). Do not claim CI is green today without re-checking.

OPEN DECISIONS (user's call, do not decide unilaterally):
  1. Is a stronger/newer model backend in scope on 53, or are the 85/80 gate thresholds to be
     reconsidered as a business decision? (Affects STEP 11.)
  2. STEP 10 (Helm/K8s): target cluster? (52 has ~90% disk full — a k3s install there is a real
     disk decision) and image registry? (GitLab CE container_registry feature is OFF, or public
     ghcr/docker.io.)

FIRST TASKS (in order, see docs/ROADMAP.md for acceptance criteria):
  TASK-CI-1 (quick): get a GitLab API token for this project so pipeline status is re-queryable.
  TASK-9.7-1..3: build workflow/observability.py (trace_id + structured logging + /metrics + /ready),
    all hermetic-testable, one branch feat/observability-baseline.
  TASK-11-1: ONE bounded live refine-pass run on an isolated compose project (never 7777/7779),
    capture before/after completeness scores as evidence.
  Then TASK-9.7-4 (Prometheus job + Grafana dashboard on 52, reusing the existing observability stack).

HARD RULES (repeat from AGENTS.md — non-negotiable):
  No secrets in repo. CI stays hermetic (no LLM/network/keys in tests). Structured output only from
  `fast`. LF line endings (.gitattributes). Never recreate 7777 or 7779 in a test — separate compose
  project name, not just a new port. No full/paid workflow runs during an audit or docs session.
```
