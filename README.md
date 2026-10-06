# AI Product Orchestrator

A **multi-agent, multi-model AI product design orchestrator**. Give it a product brief; it runs a
scored 13-step design pipeline and produces a 17-section system design **plus eight deep,
specialized technical documents** a development team can build from — all through a single
**LiteLLM** gateway, fully **Docker-Compose** deployable.

Built on [Agno AgentOS](https://github.com/agno-agi/agno).

## Status

| | |
|---|---|
| 🚀 **Deployment Guide** | [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) |
| 🧪 **CI** | Hermetic tests run automatically on every push & merge request — **no LLM, no API key, no cost** ([`.gitlab-ci.yml`](.gitlab-ci.yml) / [`.github/workflows/ci.yml`](.github/workflows/ci.yml)) |
| 📦 **Latest Release** | `v0.1.0` (Semantic Versioning — see [docs/RELEASES.md](docs/RELEASES.md)) |
| 🏛️ **Architecture** | [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md) |
| 🛠️ **Developing** | [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md) |

> **CI:** the pipeline builds the locked Python environment, syntax-checks the package, and runs
> the hermetic test suite (20 tests) with **no model and no network to LiteLLM**.
>
> Once the repo is pushed to a host, add a badge (placeholder below):
>
> ```
> [![](https://gitlab.com/<you>/ai-product-orchestrator/-/badges/main/pipeline.svg)](https://gitlab.com/<you>/ai-product-orchestrator/-/commits/main)
> [![](https://img.shields.io/badge/release-v0.1.0-brightgreen)](https://github.com/<you>/ai-product-orchestrator/tags)
> ```

---

> ## 🚀 Quick Start
> **For new server deployment, see:** [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)
>
> <details><summary>TL;DR</summary>
>
> ```bash
> git clone <repo-url> ai-product-orchestrator
> cd ai-product-orchestrator
> cp .env.example .env      # then fill in LITELLM_BASE_URL + LITELLM_API_KEY
> docker compose up -d
> docker compose logs -f
> ```
> </details>

---

## 📌 Documentation

- 🚀 **Deployment Guide** — [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md)
- 🏛️ **Architecture** — [docs/ARCHITECTURE.md](docs/ARCHITECTURE.md)
- ⚙️ **Configuration** — [docs/CONFIGURATION.md](docs/CONFIGURATION.md)
- 🤖 **Agent Design** — [docs/AGENT_DESIGN.md](docs/AGENT_DESIGN.md)
- 🛠️ **Developer Workflow** — [docs/DEVELOPMENT.md](docs/DEVELOPMENT.md)
- 📦 **Releases** — [docs/RELEASES.md](docs/RELEASES.md)

## Project Overview

The AI Product Orchestrator turns a natural-language **product brief** into concrete, scored,
buildable design artifacts. It runs a **13-step multi-model pipeline** (product analysis → master
prompt → 9 parallel specialist tasks → merge → a critic/fix/refine quality loop → a 17-section
final deliverable), and then an **enrichment layer** that fans out into **eight specialist
documents** (Backend, Database, API, Frontend, UX, Security, Testing, Deployment) with a
document-completeness gate and full decision traceability.

Everything is **model-agnostic**: agents resolve a *logical role* (`fast`/`deep`/`alt`) that is
mapped to a real model by name, and every call goes through **one LiteLLM endpoint**. Swap the
whole model fleet by editing `.env` — no code changes.

## Features

- **AgentOS Runtime** — Agno AgentOS HTTP service (health/docs/agents) on port 7777.
- **Multi-Model Routing** — logical roles → real models; ≥3 distinct models per run; no model
  names hardcoded in agents.
- **LiteLLM Integration** — a single OpenAI-compatible gateway for every call.
- **Product Analysis** — structured extraction of the brief (goals, users, constraints).
- **Architecture Generation** — a 13-section master design prompt.
- **Backend Design** · **Database Design** · **API Design** · **Frontend Design** — deep
  enrichment documents, each with decisions, components, risks, and implementation notes.
- **Testing Strategy** — unit / integration / API / E2E / performance / security plans.
- **Critic Loop** — targeted critic → atomic, acceptance-tested fixes → refiner → rebuild →
  patch verifier, iterating against a shared quality rubric.
- **Quality Gate** — 11-dimension weighted score (computed, not free-text); a separate
  **document-completeness gate** for the 8 enrichment documents.
- **Document Generation** — a deterministic Document Manager writes a 10-file markdown bundle +
  a traceability index (every decision → source + reason).
- **Honest Token Ledger** — real model + tokens read back from run metrics; per-model budget
  breakdown; stubs excluded from real totals.

## Architecture Diagram

```mermaid
flowchart TD
    User([User<br/>product brief])
    OS[AgentOS<br/>runtime + CLI]
    Mgr[Manager Agent]
    Rtr[Model Router<br/>role → real model]
    LLM[(LiteLLM gateway)]
    Models[Models<br/>fast · deep · alt]
    Specs[Specialist Agents<br/>9 design tasks<br/>+ 8 enrichment docs]
    Docs[Documents<br/>17-section design<br/>+ 10-file bundle]

    User --> OS
    OS --> Mgr
    Mgr --> Rtr
    Rtr --> LLM
    LLM --> Models
    Models --> Specs
    Specs --> Rtr
    Specs --> Docs
```

Conceptually:

```
User
  |
AgentOS
  |
Manager Agent
  |
Router
  |
LiteLLM
  |
Models
  |
Specialist Agents
  |
Documents
```

## Quick Start

```bash
git clone <repo-url> ai-product-orchestrator
cd ai-product-orchestrator

cp .env.example .env          # then fill in LITELLM_BASE_URL, LITELLM_API_KEY, AGENT_MODEL_*

docker compose up -d
docker compose logs -f
```

Verify it's up:

```bash
curl -s localhost:7777/health        # -> {"status":"healthy", ...}
./scripts/healthcheck.sh             # container + health + routing
```

Run a pipeline (once healthy):

```bash
docker compose exec agno-agentos uv run python -m workflow.run \
  enrich --brief "B2B sales management with CRM, customers, orders, sales reports and org roles"
```

See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for the full deployment, update, and backup guide.

## Configuration

Set your gateway and models in `.env`:

```ini
LITELLM_BASE_URL=http://172.20.1.52:4000/v1
LITELLM_API_KEY=<your-key>
AGENT_MODEL_FAST=qwen38-nothinking
AGENT_MODEL_DEEP=qwen38
AGENT_MODEL_ALT=qwen38-sglang
```

No secrets live in the repo. Full reference: [docs/CONFIGURATION.md](docs/CONFIGURATION.md).

## Repository layout

```
ai-product-orchestrator/
├── README.md
├── docker-compose.yml
├── Dockerfile
├── .env.example
├── .gitignore
├── .dockerignore
├── .gitlab-ci.yml             # GitLab CI (hermetic tests)
├── .github/workflows/ci.yml   # GitHub Actions (same scripts/ci.sh)
├── conftest.py                # pytest bootstrap (makes `workflow` importable)
├── LICENSE
├── personal_agent.py          # AgentOS HTTP entrypoint (:7777)
├── pyproject.toml / uv.lock   # Python 3.13 + agno[os,sqlite]
├── workflow/                  # the orchestrator package
│   ├── engine.py              # 13-step pipeline + enrichment
│   ├── router.py              # role→model + token ledger
│   ├── config.py              # single source of truth
│   ├── schemas.py             # Pydantic artifacts
│   ├── prompts.py             # role prompts + shared rubric
│   ├── models.py              # model factory
│   ├── state.py               # per-step state persistence
│   ├── run.py                 # CLI (smoke / routing / full / enrich)
│   ├── agents/                # Manager, ProductAnalyst, 8 enrichment, DocumentManager
│   ├── tests/                 # hermetic test suites
│   └── storage/               # runs + documents (gitignored, volume-mounted)
├── docs/                      # ARCHITECTURE / DEPLOYMENT / CONFIGURATION / AGENT_DESIGN / DEVELOPMENT / RELEASES
├── scripts/                   # install.sh / start.sh / healthcheck.sh / ci.sh
└── tests/                     # README pointing at workflow/tests (run in-container)
```

## Tests

The test suites are hermetic (a fake router — no real LLM needed) and live in
`workflow/tests/`. Run them inside the container:

```bash
docker compose exec agno-agentos uv run python -m workflow.tests.test_full_pipeline
docker compose exec agno-agentos uv run python -m workflow.tests.test_enrichment
```

## License

[MIT](LICENSE).
