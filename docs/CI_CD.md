# CI/CD

**Standard:** no merge/release without tests. Pipeline: `Lint → Unit → Integration → Contract →
E2E/Smoke → Security → Build → Deploy → Health Check`. Keep it **hermetic** — no paid model,
no network to LiteLLM.

## Current state (STEP 9.6)

`.gitlab-ci.yml` (self-hosted `server52` runner) runs two stages:

| Stage | Job | What it does | Status vs standard |
|---|---|---|---|
| `test` | `test` | `scripts/ci-docker.sh` → throwaway `python:3.13-slim`, runs the **30 hermetic tests** | ✅ Unit/Integration (hermetic). **No separate Lint / Contract / Security stages.** |
| `deploy` | `deploy` | `scripts/deploy-repo.sh` → sync + `docker compose up -d --build` + **health-wait on 7779** | 🟡 Build + Deploy + a **health-wait** (process-alive). **No post-deploy smoke run.** |

- **Hermetic — ✅ the core promise holds.** CI needs no LLM, no LiteLLM, no API key, no cost.
- **`clone_url` gotcha** — every runner on 52 must carry `clone_url = "http://172.20.1.52:81"`
  (public `git.ai.ismc.ir:443` is unreachable from 52). See `AGENTS.md`.
- **Serving runner** — the healthy **root runner `AI-TOOLS` (#1)**; the broken user-mode runner
  #5 is stopped + deactivated. See `AGENTS.md` and the STEP 9.5 report.

## Gaps vs the 14-point standard (the CI quality gate, point 10)

| Stage | Status | Plan |
|---|---|---|
| **Lint** | ❌ | Add a `ruff`/`pyflakes` job (fast, hermetic) before `test`. |
| **Unit** | ✅ | in `test`. |
| **Integration** | ✅ | `test_full_pipeline`, `test_enrichment`, `test_refine` (FakeRouter). |
| **Contract** | 🟡 | Add a job that validates the Pydantic schemas + OpenAPI surface don't drift (hermetic). |
| **E2E/Smoke** | 🟡 | Post-deploy: hit `/ready` and run a hermetic smoke via the deploy job (no paid model). |
| **Security** | ❌ | Secret-scan job (no `LITELLM_API_KEY`/master key in the tree) — cheap, hermetic. |
| **Build** | ✅ | `docker compose ... --build` in deploy. |
| **Deploy** | ✅ | `deploy-repo.sh`. |
| **Health Check** | 🟡 | Upgrade health-wait to call `/ready` (dependency-aware) once it exists. |

The additions above are **STEP 10** scope (CI is part of the platform). The **current pipeline is
green and reliable** (verified STEP 9.5); these are extensions, not a broken baseline.

See `docs/OBSERVABILITY.md` §10 and `AGENTS.md` for the runner/clone_url details.
