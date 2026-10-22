# معماری فعلی — AI Product Orchestrator (AgentOS)

> استخراج‌شده از کد و پیکربندی واقعی (2026-10-21)، نه از مستندات. مرجع تکمیلی: `docs/ARCHITECTURE.md`.

## دیاگرام کلی (واقعیتِ 2026-10-21)

```mermaid
flowchart TD
    subgraph USER["لایه کاربر"]
        CLI[CLI: workflow.run<br/>smoke|routing|full|enrich|refine|endpoint]
        HTTPC[HTTP client / UI استاندارد Agno]
    end

    subgraph S52["سرور 52 (172.20.1.52)"]
        subgraph AG1["agno-agentos :7777 — PRODUCTION (خارج از ریپو)"]
            OS1[AgentOS runtime<br/>personal_agent.py + workflow/]
        end
        subgraph AG2["agno-agentos-repo :7779 — CI deploy target"]
            OS2[AgentOS runtime<br/>= git main بایت‌به‌بایت]
        end
        GL[GitLab CE :81<br/>+ gitlab-runner service (tag server52)]
        GW[LiteLLM gateway :4000<br/>container learn-lite-llm-litellm-1<br/>17+ model alias]
        VOL[(volume: agentos-data<br/>agent.db + /data/runs + /data/documents)]
        IMG[ai-product-orchestrator:latest<br/>526MB]
    end

    subgraph S53["سرور 53 (172.20.1.53) — backends مدل"]
        V1[vLLM :8000<br/>Qwen3.8-27B-FP8 (nothinking)]
        V2[vLLM/SGLang :8001<br/>Qwen3.8-27B-FP8]
    end

    CLI --> OS1 & OS2
    HTTPC --> OS1 & OS2
    OS1 & OS2 <--> VOL
    OS1 & OS2 -- "OpenAI-compatible<br/>resolve_endpoint()" --> GW
    GW --> V1
    GW --> V2
    GL -- "test→deploy (7779)" --> IMG --> AG2
```

## اجزای تک‌به‌تک (وضعیت واقعی)

| جزء | تکنولوژی | وضعیت |
|---|---|---|
| **Backend/Framework** | Python 3.13، Agno AgentOS (FastAPI)، `agno[os,sqlite]` + `openai` | واقعی و زنده |
| **Agent engine** | `workflow/engine.py` (61KB): 13-step pipeline + enrichment + refine؛ agents در `workflow/agents/` | واقعی، تست‌شده، run واقعی موجود |
| **Model routing** | `workflow/router.py` + `config.py`: نقش‌های logical `fast/deep/alt/stub` → model name؛ `TASK_MODEL_HINTS` تعیین می‌کند کدام TASK روی کدام نقش | واقعی، تست‌شده |
| **LiteLLM** | یک endpoint واحد: Mode A خارجی (52:4000) — فعال؛ Mode B sidecar (`litellm/` profile) — کد کامل، در 52 deploy نیست | Mode A واقعی و زنده |
| **Database** | SQLite (`agno.db.sqlite.SqliteDb`) برای sessions/memories AgentOS در `agent.db`؛ state pipeline در JSON (`/data/runs/<run_id>/state.json`)؛ documents در `/data/documents/` | واقعی و persistent روی volume |
| **API** | (1) API کامل Agno AgentOS (~70 مسیر: agents/sessions/traces/metrics-JSON/knowledge/…)؛ (2) CLI `workflow.run`؛ (3) **endpoint سفارشی برای brief→artifacts وجود ندارد** — pipeline فقط از CLI اجرا می‌شود | واقعی؛ (3) گپ |
| **Authentication** | **هیچ authی در سطح اپ روی 7777/7779** — دسترسی شبکه‌ای (LAN 172.20.1.x). LiteLLM gateway با Bearer key. GitLab private. | گپ امنیتی (I-03) |
| **Configuration** | `.env` (19 کلید، chmod 600 در 52)؛ `resolve_endpoint()` single-source؛ `.env.example` در ریپو؛ deploy script env را backup/restore می‌کند | واقعی و درست |
| **Monitoring/Logging** | **نیمه‌فاقد:** logهای structlog نیست — `print()` در engine؛ run-report داخل state.json؛ token ledger؛ `/health` process-alive؛ `/metrics` = JSON خالی فریم‌ورک Agno (نه Prometheus)؛ **بدون** trace_id، بدون Prometheus job، بدون Grafana dash | گپ اصلی (I-02) |
| **Reverse proxy / Gateway شبکه‌ای** | برای API اپ: **ندارد** (مستقیم 0.0.0.0:7777/7779). GitLab روی 81 مستقیم. | قابل قبول در LAN داخلی |
| **Deployment pipeline** | GitLab CI (`.gitlab-ci.yml`): push main/tag/MR → `ci-docker.sh` (تست 30تایی در کانتینر موقت) → `deploy-repo.sh` (sync به /home/saber/saberprojects/ai-product-orchestrator + `docker compose up -d --build` + health-wait) | واقعی و سبز (آخرین deploy موفق = commit 299f1a3) |
| **K8s/Helm** | فقط کشف (STEP 10): no cluster، no registry داخلی، disk 52 ~90% | **فقط در مستندات / تصمیم‌نشده** |

## جریان کامل یک درخواست (از ورود تا پاسخ)

```
1. کاربر: docker compose exec agno-agentos-repo uv run python -m workflow.run enrich --brief "..."
2. run.py → config.resolve_endpoint() → (http://172.20.1.52:4000/v1, LITELLM_API_KEY از .env)
3. state.py → ساخت /data/runs/<run_id>/state.json (run_id جدید)
4. engine.py: Manager agent → 13-step pipeline:
   هر step → ModelRouter (نقش fast/deep/alt از TASK_MODEL_HINTS)
            → OpenAI client → POST /v1/chat/completions به LiteLLM 52:4000
            → LiteLLM → 53:8000/8001 (Qwen3.8-27B-FP8) → response
            → ثبت LlmCall (model, tokens, status) در state.json (token ledger)
5. خروجی‌ها: ProductAnalysis (Pydantic) → Master Prompt (13 section) → 9 TASK متخصص
   → merge → critic/fix/refine loop → quality gate (11 بُعد وزن‌دار → final_score)
   → 17-section design
6. Enrichment: 8 آژنت تخصصی → 8 سند عمیق → Document Manager → bundle 10 فایل + traceability index
   → document-completeness gate (score 0-100)
7. (اختیاری) refine pass: فقط اسناد gapful را دوباره اجرا + re-score
8. state.json نهایی: status, final_score, doc scores, LlmCall list, gaps
```

**جریان HTTP AgentOS** (برای آژنت ساده): `POST /agents/personal_agent/runs` → OpenAIChat → همان LiteLLM → پاسخ. این مسیر جدا از pipeline است و فقط یک آژنت ساده personal assistant می‌دارد.

## واقعیت در مقابل مستندات

| مورد | واقعی | ناقص | فقط مستند |
|---|---|---|---|
| pipeline + agents + gates | ✅ | (scoreها به threshold نمی‌رسند) | — |
| LiteLLM Mode A | ✅ | — | — |
| LiteLLM Mode B sidecar | ✅ کد/تست | در 52 deploy نیست | — |
| state/ledger/DB | ✅ | — | — |
| CI/CD | ✅ | pipeline list queryable نیست | — |
| observability | — | ✅ (کلاً نیست) | ✅ (استاندارد 14-نقطه‌ای) |
| auth/RBAC | — | ✅ (Agno service-accounts هست ولی بی‌استفاده) | — |
| فرم تنظیمات/داشبورد | — | ✅ | بخشی در مستندات قدیمی‌تر (STEP) |
| k8s/Helm | — | — | ✅ |
