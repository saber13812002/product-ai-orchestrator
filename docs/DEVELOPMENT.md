# Developer Workflow

How to clone, set up, test, branch, commit, push, and release this project.

> For running the *service*, see [DEPLOYMENT.md](DEPLOYMENT.md). For the internals, see
> [ARCHITECTURE.md](ARCHITECTURE.md) and [AGENT_DESIGN.md](AGENT_DESIGN.md).

## 1. Clone

```bash
git clone https://git.ai.ismc.ir/common/website/ai-product-orchestrator.git ai-product-orchestrator
cd ai-product-orchestrator
```

## 2. Install

The Python environment is managed by **uv** with a lockfile (`uv.lock`). Two common setups:

**In Docker (recommended — no local Python/uv needed):**

```bash
docker compose exec agno-agentos uv run python -c "import agno; print('ok')"
```

**Local (uv + Python 3.13):**

```bash
brew install uv        # or: pip install uv   (uv is a small standalone binary)
uv sync --frozen        # installs the exact locked deps into ./.venv
```

The app itself only needs a **LiteLLM gateway reachable at runtime** — but *development and
testing do not*, because the tests are hermetic.

## 3. Run tests

Tests are **hermetic** — they use a fake router, so they need **no LiteLLM, no API key, and no
model**. They live in `workflow/tests/` (not a top-level `tests/`, so they can `import workflow`).

```bash
# From the repo root (repo root is auto-added to sys.path via conftest.py):
uv run --with pytest python -m pytest workflow/tests -q

# ...or one suite:
uv run python -m workflow.tests.test_full_pipeline
uv run python -m workflow.tests.test_enrichment
```

Expected: **20 passed**. This is exactly what CI runs (see [scripts/ci.sh](../scripts/ci.sh)).

## 4. Create a branch

Work off `main` in a feature branch:

```bash
git checkout main
git pull
git checkout -b feat/<short-slug>     # e.g. feat/doc-refine-pass
```

Branch naming: `feat/...`, `fix/...`, `chore/...`, `docs/...`, `test/...`.

## 5. Commit convention

Short imperative subject (≤ ~70 chars), blank line, optional body:

```
feat: add a gap-filling enrichment refine pass

Adds a second enrichment pass that injects the doc-completeness gate's
named gaps (DDL / OpenAPI / payment / reporting) to lift document
completeness.
```

Types: `feat`, `fix`, `chore`, `docs`, `refactor`, `test`, `build`, `ci`.

Keep commits small and logical (the initial history is an example:
*initial structure → docker deployment → documentation → environment template*).

## 6. Push

```bash
git add <files>
git commit -m "feat: <summary>"
git push -u origin feat/<short-slug>
```

Open a merge/pull request against `main`. **CI runs automatically** on the branch and on the
merge request — the hermetic test job must pass before merge.

> **Never commit secrets.** `.env` (with your `LITELLM_API_KEY`) and `workflow/storage/` are
> gitignored. The only required secret is `LITELLM_API_KEY`, supplied via `.env`.

## 7. Release process

See [RELEASES.md](RELEASES.md) for the full flow. Short form:

1. Bump the version (see the versioning rules) and tag: `git tag v0.1.1`
2. Push the tag: `git push origin v0.1.1`
3. CI runs the hermetic tests on the tag; the release is created.

## 8. CI/CD (on the `server52` runner)

The GitLab pipeline (`.gitlab-ci.yml`) runs on the **self-hosted shell runner** (tag
`server52`), which **ignores Docker `image:`** — so the jobs shell out to containers
themselves:

| Job | What it does | Script |
|---|---|---|
| `test` | Hermetic tests in a throwaway `python:3.13-slim` container (no LLM/key/cost) | `scripts/ci-docker.sh` → `scripts/ci.sh` |
| `deploy` | Sync to the persistent stack dir + `docker compose up -d --build` + health-wait | `scripts/deploy-repo.sh` |

- **Trigger:** every push to `main`, every `v*` tag, every merge request, and manual
  *Run pipeline*. `deploy` is **skipped for merge requests** (never deploy from an MR).
- **Pipeline / badge:**
  <https://git.ai.ismc.ir/common/website/ai-product-orchestrator/-/pipelines>
- **GitHub Actions** (`.github/workflows/ci.yml`) runs the same `scripts/ci.sh` if the repo
  is ever mirrored to GitHub.
- The deploy target on server 52 is `/home/saber/saberprojects/ai-product-orchestrator`
  (override via `DEPLOY_DIR`); its `.env` is guarded across redeploy so live keys/ports
  survive.

## 9. Local run (without Docker)

```bash
cp .env.example .env          # fill LITELLM_BASE_URL + LITELLM_API_KEY (+ AGENT_MODEL_*)
uv run personal_agent.py     # AgentOS HTTP on :7777
# in another shell:
uv run python -m workflow.run routing
uv run python -m workflow.run full --brief "..."
```
