# Releases

This project uses **Semantic Versioning** — `Major.Minor.Patch`.

| Bump | When |
|---|---|
| **Major** (`vX.0.0`) | Breaking changes (CLI args, `.env` variable names, config schema, state format). |
| **Minor** (`v0.Y.0`) | New features, additive changes, new docs — backward compatible. |
| **Patch** (`v0.1.Z`) | Bug fixes, dependency/security bumps — backward compatible. |

The current line is `v0.3.x` (early 0.x: treat Minor as "feature", Patch as "fix"; no stability
guarantees yet).

## Changelog (recent)

### v0.3.0 — LiteLLM deployment modes (External + Bundled sidecar)
- **Two LiteLLM deployment modes, one code path.** Mode A (external, the default) connects to a
  LiteLLM gateway you already run; Mode B (bundled) starts the repo's own **LiteLLM sidecar** via
  `docker compose --profile bundled-litellm up -d` — for a fresh server with no gateway. The
  sidecar is strictly optional; `docker compose up -d` is unchanged.
- **Single resolution point** (`workflow/config.py::resolve_endpoint()`): mode selection lives in
  one place; `personal_agent.py` and the model factory/router all consume its result. Legacy
  `OPENAI_*` names remain an external-mode fallback.
- **Bundled sidecar** (`litellm/`): a secrets-free routing template (`config.yaml`) + a startup
  renderer (`entrypoint.sh`). The renderer expands `${VAR}` from the environment at container
  start because the official image does not expand placeholders in a mounted config (verified on
  `main-latest`). Routes the three logical models to any OpenAI-compatible backend (vLLM, SGLang,
  TGI, OpenAI-compatible), with a per-role `_API_BASE` / `_API_KEY` / `_API_MODEL`.
- **Health-gated startup** (bundled): `depends_on: litellm {condition: service_healthy,
  required: false}` — Mode A has no dependency on the internal service; Mode B waits for the
  sidecar to be healthy before serving model calls.
- **New CLI:** `workflow.run endpoint` (prints the resolved mode, base URL, and whether a key is
  configured — never the key itself).
- **9 new hermetic tests** (`workflow/tests/test_endpoint.py`) covering both modes, the legacy
  fallback, and URL validation. Suite is now **30 tests** (was 21).
- **Security:** no secrets in the repo; sidecar master key from `.env`; sidecar UI/API on
  `127.0.0.1` only; no extra database service.
- **Docs:** new [LITELLM.md](LITELLM.md) and [AI_HANDOFF.md](AI_HANDOFF.md); DEPLOYMENT /
  CONFIGURATION / README updated for both modes.

### v0.2.0 — gap-filling refine pass
- **New `refine` run mode** (CLI: `workflow.run refine --brief "..."`): runs the enrichment
  layer plus a targeted 2nd pass that re-runs only the documents the completeness gate named as
  gapful (DDL / OpenAPI / payment / reporting / observability / UI flows), overwrites the 10-file
  bundle, and re-scores. Lifts document completeness from a single pass's ~79 toward 85+
  (measured live: 74 → 82, `passed` flipped to true).
- New knobs in `workflow/config.py`: `REFINE_TOKEN_BUDGET`, `REFINE_MAX_AGENTS`,
  `REFINE_SELF_DOC_CHARS`, `REFINE_DOC_MAX_OUTPUT`, `REFINE_GAP_KEYWORDS`.
- New hermetic test suite `workflow/tests/test_refine.py` (suite is now **21 tests**).
- Docs updated (README / AGENTS / ARCHITECTURE / CONFIGURATION / DEVELOPMENT).

### v0.1.0 — portable repo + CI/CD
- Docker-Compose portable package, master key scrubbed (env-only), hermetic CI/CD on the
  self-hosted `server52` GitLab runner (test → deploy), `AGENTS.md`, LF line endings.

## Creating a release

```bash
git checkout main
git pull
git tag v0.1.1                       # choose the next version
git push origin v0.1.1
```

Pushing the `v*` tag triggers CI to run the hermetic test job against the exact tagged commit
(both the GitLab and GitHub pipelines run on tags). A green tag = a releasable version.

On GitLab you can then create a formal **Release** (UI → Releases → New → select the tag, add
release notes). On GitHub, `gh release create v0.1.1 --notes "..."`.

## Version source of truth

The **git tag** is the canonical version (what CI and consumers use). The package version in
`pyproject.toml` is informational; bump it to match when convenient but the tag is authoritative.

## Release checklist

- [ ] On `main`, up to date with the latest.
- [ ] CI green on the commit (hermetic tests pass).
- [ ] No secrets in the tree (`.env`, `storage/`, logs excluded — see `.gitignore`).
- [ ] `docs/DEPLOYMENT.md` still accurate for a fresh server.
- [ ] Tag created and pushed (`vA.B.C`).
