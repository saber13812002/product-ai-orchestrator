# LiteLLM Deployment Modes

How the orchestrator reaches its models. There are **two deployment modes** and the difference
is one compose flag plus a few `.env` values — the application code is identical in both.

```
Mode A — External (default)            Mode B — Bundled sidecar
─────────────────────────────────      ─────────────────────────────────
  AgentOS                                  AgentOS
     │                                        │
     ▼                                        ▼
 your existing LiteLLM  ◄── you             the sidecar THIS REPO starts
 (e.g. http://host:4000)   already run       (compose profile bundled-litellm)
     │                                        │
     ▼                                        ▼
 your backends / models               your backends / models
```

Both modes route every model call through **one LiteLLM endpoint**, and both resolve that
endpoint in **exactly one place**: `workflow/config.py::resolve_endpoint()`. Switching modes is
a `.env` change — never a code change.

| | Mode A — External | Mode B — Bundled |
|---|---|---|
| Who runs LiteLLM | you | this repo (the `litellm` sidecar service) |
| Start command | `docker compose up -d` | `docker compose --profile bundled-litellm up -d` |
| Set in `.env` | `LITELLM_BASE_URL`, `LITELLM_API_KEY` | `LITELLM_MODE=bundled`, `LITELLM_MASTER_KEY`, `*_MODEL_API_*` |
| Endpoint AgentOS uses | your `LITELLM_BASE_URL` | `http://litellm:4000/v1` (the compose service name) |
| Extra containers | none | one (the sidecar) |

> **The sidecar is strictly optional.** `docker compose up -d` (Mode A) never starts it. The
> sidecar only appears when you opt in with `--profile bundled-litellm`. If you already run a
> LiteLLM gateway, **use Mode A** — do not also bring up the sidecar.

---

## Mode A — External LiteLLM (default)

You already have a LiteLLM proxy running somewhere (on this host or another). Point the
orchestrator at it and supply a key.

```bash
cp .env.example .env
# in .env:
#   LITELLM_MODE=external            # (the default — you can leave this unset)
#   LITELLM_BASE_URL=http://172.30.0.133:4000/v1
#   LITELLM_API_KEY=<your-key>
#   AGENT_MODEL_FAST=qwen38-nothinking
#   AGENT_MODEL_DEEP=qwen38
#   AGENT_MODEL_ALT=qwen38-sglang
docker compose up -d
```

The gateway must actually **serve** the model names you set in `AGENT_MODEL_*`. Verify:

```bash
docker compose exec agno-agentos uv run python -m workflow.run endpoint   # -> mode: external
docker compose exec agno-agentos uv run python -m workflow.run routing
```

## Mode B — Bundled LiteLLM sidecar

On a fresh server with **no pre-existing LiteLLM**, this repo can bring up its own gateway as a
sidecar. It routes the orchestrator's three logical models to **any** OpenAI-compatible backend
(vLLM, SGLang, TGI, OpenAI-compatible inference servers, or the real OpenAI/Anthropic APIs).

```bash
cp .env.example .env
# in .env:
#   LITELLM_MODE=bundled
#   LITELLM_MASTER_KEY=sk-$(openssl rand -hex 32)   # generate one
#   # backends the sidecar routes to (one per role):
#   FAST_MODEL_API_BASE=http://<your-vllm>:8000/v1
#   FAST_MODEL_API_MODEL=<model-id-that-backend-serves>
#   DEEP_MODEL_API_BASE=http://<your-vllm>:8000/v1
#   DEEP_MODEL_API_MODEL=<model-id>
#   ALT_MODEL_API_BASE=http://<your-sglang>:8001/v1
#   ALT_MODEL_API_MODEL=<model-id>
#   AGENT_MODEL_FAST=qwen38-nothinking   # the name AgentOS calls the model by
#   AGENT_MODEL_DEEP=qwen38
#   AGENT_MODEL_ALT=qwen38-sglang
docker compose --profile bundled-litellm up -d
```

Now **two** containers run: `agno-agentos` and `litellm-sidecar`. AgentOS reaches the sidecar
over the compose network at `http://litellm:4000/v1` and authenticates with `LITELLM_MASTER_KEY`
— both of which `resolve_endpoint()` picks up automatically in `bundled` mode. The sidecar's own
host port defaults to **4100 on 127.0.0.1 only** (for humans to reach its UI/API); it never
collides with an external gateway on 4000 and is never exposed publicly.

```bash
docker ps                                            # both "healthy"
docker compose exec agno-agentos uv run python -m workflow.run endpoint   # -> mode: bundled, base_url: http://litellm:4000/v1
curl -s -H "Authorization: Bearer $LITELLM_MASTER_KEY" http://127.0.0.1:4100/v1/models
```

### How the sidecar is wired (and why)

The sidecar is a **transparent alias layer**: it exposes each model under the *same name AgentOS
sends* (`AGENT_MODEL_*`) and forwards it to a real backend. `litellm/config.yaml` is a **template
with no secrets** — every backend URL/key/model-id is `${VAR}`-driven from `.env`.

**Why the startup renderer (`litellm/entrypoint.sh`):** the official LiteLLM image does **not**
expand `${VAR}` placeholders inside a *mounted* config file. Verified on
`ghcr.io/berriai/litellm:main-latest` — with `api_base: ${FAST_MODEL_API_BASE}` the proxy failed
every call with `InvalidUrlClientError: /$%7BFAST_MODEL_API_BASE%7D/chat/completions` (the
placeholder, URL-encoded, used as the literal URL). So the compose service mounts the template and
`entrypoint.sh`, and the entrypoint expands every `${VAR}` from the environment and hands the
rendered file to LiteLLM before starting. This keeps the config fully env-driven (no per-fleet
values or secrets committed) without relying on a LiteLLM config-env behavior that changed
between versions.

---

## Configuration reference

All variables are documented in [`.env.example`](../.env.example). The ones that matter:

| Variable | Mode | Meaning |
|---|---|---|
| `LITELLM_MODE` | A/B | `external` (default) or `bundled`. |
| `LITELLM_BASE_URL` | A | Your gateway's `/v1` URL. |
| `LITELLM_API_KEY` | A | Your gateway's master/virtual key. |
| `LITELLM_MASTER_KEY` | B | The sidecar's master key. **Generate one; never commit it.** AgentOS authenticates to the sidecar with this same value. |
| `LITELLM_PORT` | B | Host port (127.0.0.1) for the sidecar UI/API. Default `4100`. |
| `LITELLM_CONTAINER_NAME` | B | Rename the sidecar if the name is taken. |
| `AGENT_MODEL_FAST/DEEP/ALT` | A/B | The model **names AgentOS calls** (must be served by the gateway, A; or exposed by the sidecar, B). |
| `FAST/DEEP/ALT_MODEL_API_BASE` | B | The backend's `/v1` URL for that role. |
| `FAST/DEEP/ALT_MODEL_API_KEY` | B | The backend's key (leave empty for local no-auth servers — a `dummy` placeholder is used, which the backend ignores). |
| `FAST/DEEP/ALT_MODEL_API_MODEL` | B | The model **id that backend actually serves**. Defaults to the matching `AGENT_MODEL_*`; set it only when the backend serves a different/ugly id. |

### Model mapping (the name that must match)

AgentOS resolves `role → model` from `AGENT_MODEL_*` and calls the gateway **with that name**.
So:

- **Mode A:** your gateway must list `qwen38-nothinking`, `qwen38`, `qwen38-sglang` (or whatever
  you set).
- **Mode B:** the sidecar exposes `model_name: ${FAST_MODEL}` (= `AGENT_MODEL_FAST`), so it
  serves exactly those names. The sidecar then forwards each to `*_MODEL_API_BASE` using the
  backend's real id `*_MODEL_API_MODEL`.

One set of `AGENT_MODEL_*` names drives both containers — change a name once and both follow.

### Local / OpenAI-compatible models

Any OpenAI-compatible `/v1` endpoint works as a backend:

- **vLLM / SGLang / TGI** on your network — set `*_MODEL_API_BASE` to `http://<host>:<port>/v1`.
- **No-auth local servers** — leave `*_MODEL_API_KEY` empty (a `dummy` key is used because the
  OpenAI client refuses a blank key; the backend ignores it).
- **A backend whose model id differs from the name** (e.g. a raw Qwen vLLM serving
  `/models/Qwen3.8-27B-FP8`) — set `*_MODEL_API_MODEL` to that id.

#### The reference Qwen fleet (thinking models)

The reference backends (`53:8000` vLLM, `53:8001`) serve a **thinking** Qwen
(`Qwen3.8-27B-FP8`). A thinking model burns its output budget on reasoning and returns *no*
structured content — so the structured `fast` role must run with thinking **off**. `litellm/
config.yaml` has a ready-to-uncomment block for the reference fleet:

```yaml
      # extra_body:
      #   chat_template_kwargs:
      #     enable_thinking: false
```

Uncomment it for the reference Qwen backends so `fast` returns complete JSON. Remove it for
backends that are already no-thinking, or that reject unknown params (e.g. the real OpenAI API).
`deep`/`alt` keep thinking on (they run free-text tasks, not structured steps).

---

## Health checks

| What | Check |
|---|---|
| AgentOS container | built-in `HEALTHCHECK` on `/health`; `docker ps` shows `health: healthy`. |
| Sidecar process | its `healthcheck` hits `/health/liveliness` (200 = process up; **model backends are validated lazily on first call**). |
| Endpoint resolution | `... workflow.run endpoint` prints the mode + base URL + whether a key is configured (never the key). |

**Startup ordering:** in bundled mode the `agno-agentos` service has
`depends_on: litellm: {condition: service_healthy, required: false}`. `required: false` (compose
v2.20+) means: *wait for the sidecar to be healthy only if it's actually starting* — so **Mode A
has no dependency on any internal service**, and Mode B never fires model calls before the
sidecar is ready.

## Troubleshooting

| Symptom | Likely cause | Fix |
|---|---|---|
| `model_not_found` in bundled mode | The sidecar exposes a different name than `AGENT_MODEL_*` (e.g. you renamed `AGENT_MODEL_FAST` but the gateway still expects the old one). | Keep the `AGENT_MODEL_*` names consistent; the sidecar alias follows them. Check `... /v1/models` on the sidecar. |
| `InvalidUrlClientError: /$%7B...%7D/...` | The config template wasn't rendered (you're not using the repo's `entrypoint.sh`, or you bypassed compose). | Start via `docker compose --profile bundled-litellm` so `entrypoint.sh` renders the config. |
| `AuthenticationError ... api_key must be set` | A backend has an empty `api_key` and the OpenAI client refused to boot. | Leave the backend `_API_KEY` empty — the compose file injects a `dummy` placeholder (the backend ignores it). |
| `fast` returns no JSON / empty content | A **thinking** model is serving the structured role. | Use a no-thinking model for `fast`, or enable the `enable_thinking: false` block for the reference Qwen fleet. |
| Sidecar won't boot | `LITELLM_MASTER_KEY` is empty. | Recent LiteLLM refuses to start with an empty master key — generate one. |
| Bundled test clobbered another instance | Two compose projects share the same project name + service. | Run isolated tests with a **separate compose project** (`docker compose -p myproj ...`), not just a different `container_name`/port. |

## Security

- **No secrets in the repo.** `litellm/config.yaml` has none; every key is injected from `.env`
  at runtime. Only `.env.example` is tracked; `.env` is gitignored.
- **The sidecar master key is a live credential** — generate it (`echo "sk-$(openssl rand -hex 32)"`),
  keep it in `.env`, never print or commit it. AgentOS and the sidecar share it only in-process.
- **UI/admin is loopback-only.** The sidecar port is published on `127.0.0.1` only, so the UI and
  admin API are not reachable from the network.
- **Least privilege, isolated state.** The sidecar's state (optional sqlite for spend logs /
  virtual keys) lives in its own `litellm-data` volume, separate from AgentOS's `agentos-data`.
  No extra database service is pulled in — this is a turnkey gateway, not a new platform.

## See also

- [DEPLOYMENT.md](DEPLOYMENT.md) — the two end-to-end deployment scenarios.
- [CONFIGURATION.md](CONFIGURATION.md) — the full environment-variable reference.
- `.env.example` — the annotated variable template.
