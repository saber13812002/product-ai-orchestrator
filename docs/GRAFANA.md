# Grafana

**Standard:** `App / AgentOS / LiteLLM → metrics → Prometheus → Grafana`. This app must have a
**dedicated Workflow Dashboard** showing the whole pipeline, plus the standard dashboards.

## Current state (STEP 9.6)

- **No Prometheus and no Grafana exist for this app.** The token ledger and (future) `/metrics`
  are the data sources; the visualization layer has not been built.
- The nearest thing today is the **CLI JSON report** (`workflow.run ... `) and the per-run
  `state.json` — a per-run snapshot, not a live dashboard.

## What we will build (STEP 10, once a Prometheus/Grafana instance is chosen)

Reuse an existing fleet Prometheus/Grafana if one exists on the LAN (52/53); otherwise stand up
a minimal pair. The app must be **scrapeable first** (STEP 9.7 `/metrics`), which is the
prerequisite.

### Dashboards (minimum)

1. **System Overview** — run rate, active runs, error rate, overall health, tokens/min.
2. **Agent Workflow** — the dedicated workflow dashboard (§8 below).
3. **Model / LiteLLM** — per-model call count, latency, tokens, error rate (fast/deep/alt);
   LiteLLM gateway health.
4. **Quality Gate** — `orchestrator_last_quality_score` over time, doc-completeness over time,
   pass/fail by run.
5. **API** — AgentOS request count/latency/errors on `:7777`.
6. **Errors** — `orchestrator_step_errors_total` by `step` and `error_type`; failure/recovery
   events.
7. **Infrastructure** — CPU/RAM of the pod/host (k8s layer, STEP 10).
8. **CI/CD** — pipeline success rate + last-deploy health (GitLab metrics).
9. **Kubernetes** (STEP 10+) — pod restarts, probe failures, resource usage.

### 8. The dedicated Workflow Dashboard (the signature one)

One row per pipeline node, each showing **count, latency, error, tokens, score, status**:

```
Manager → Product Analyst → Decomposition → Specialists → Critic
        → Refiner → Quality Gate → Document Generation → Final Review
```

- **count** — `orchestrator_step_duration_seconds_count{step}`
- **latency** — P50/P95 of `orchestrator_step_duration_seconds{step}`
- **error** — `orchestrator_step_errors_total{step}`
- **tokens** — `orchestrator_tokens_total` summed for that step's agents/roles
- **score** — `orchestrator_last_quality_score` / `orchestrator_last_doc_completeness`
- **status** — derived (green = no recent errors, red = errors)

The dashboard JSON is committed to `grafana/dashboards/` in the repo (STEP 10) so it is
reproducible and version-controlled — not only a live-panel artifact.

See `docs/OBSERVABILITY.md` §7–8 and `docs/METRICS.md` for the exact series names.
