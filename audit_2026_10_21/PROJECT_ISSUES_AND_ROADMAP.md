# مشکلات، ریسک‌ها و نقشه راه تکمیل — ممیزی 2026-10-21

## ۱. فهرست مشکلات (طبقه‌بندی‌شده)

| شناسه | سطح | محل | شواهد | علت محتمل | تأثیر | راه‌حل پیشنهادی | اولویت/وابستگی |
|---|---|---|---|---|---|---|---|
| **I-01** | **High** | quality gates | run واقعی `97dda8`: final_score 71 < 85، doc completeness 79 < 80؛ gateها gapها را نام می‌برند (DDL/OpenAPI/observability/UI) | model-bound ceiling (Qwen3.8-27B-FP8 برای design task) + refine pass بی‌شواهد | هدف محصول «Approved Technical Documents» تحقق نیافته | TASK-11-1 (شواهد زنده refine) سپس TASK-11-2 (تصمیم: مدل قوی‌تر یا بازتعریف threshold) | P0 — بدون وابستگی |
| **I-02** | **High** | observability | `grep` در `workflow/*.py`+`personal_agent.py`: بدون `trace_id`، بدون `import logging`، بدون Prometheus؛ لاگ‌ها `print()` | build شروع نشده (STEP 9.7 = 0%) | بدون trace/latency/metrics نمی‌توان سقف score را تشخیص داد (prompt-bound؟ model-bound؟) و تولید قابل‌audit نیست | TASK-9.7-1..4 (branch `feat/observability-baseline`) | P0/P1 — خودِ STANDARD در OBSERVABILITY.md نوشته شده |
| **I-03** | Medium | امنیت دسترسی | 7777/7779 روی `0.0.0.0` بدون auth؛ Anyone با دسترسی LAN 172.20.1.x می‌تواند agent اجرا کند | معماری فعلی فقط شبکه داخلی است | اجرای agent = مصرف توکن/مدل؛ بدون rate limit یا user binding | (a) مرز شبکه (firewall/VLAN) و/یا (b) reverse proxy با auth (مثلاً Caddy/Nginx) جلوی API — تصمیم کاربر | P1 — مستقل |
| **I-04** | Medium | CI observability | GitLab API token وجود ندارد؛ `jobs/request` 502 در 06:52 امروز در لاگ runner | runner بدون token project-scoped؛ 502 هم‌زمان با reboot gitlab | نمی‌توان بدون UI بگوییم «pipeline سبز است» | TASK-CI-1: ایجاد token `read_api` project-scoped (CI variable، نه در ریپو) + دستور کوئری در AGENTS.md | P1 — بدون وابستگی (10 دقیقه) |
| **I-05** | Medium | تست | هیچ تست خودکار HTTP برای `personal_agent.py`/AgentOS API وجود ندارد (TEST_MATRIX gap #1) | تست‌ها مستقیم کلاس‌های workflow را می‌زنند، نه FastAPI app | regression در routing HTTP (مثلاً تغییر path) به CI نمی‌رسد | TestClient-based test برای `/health` (+ بعداً `/ready`, `/metrics`) در TASK-9.7-2/3 | P2 — با I-02 |
| **I-06** | Medium | استقرار | production 7777 (`/home/saber/agentos/`) خارج از ریپو/CI است؛ image متفاوت (`agno-agentos:latest` 545MB vs `ai-product-orchestrator:latest` 526MB) | 7777 «never touch» (قانون سخت AGENTS.md) | دو نسخه مستقل؛ runهای واقعی فقط روی 7777؛ deploy جدید فقط روی 7779 می‌رود | تصمیم: 7777 را هم زیر CI بیاوریم (port 7777، compose جدا) یا مستندسازی کنیم که 7777 legacy است و target جدید 7779 است | P1 — تصمیم کاربر |
| **I-07** | Low | healthcheck | Docker HEALTHCHECK فقط process-alive (`/health`)؛ `/ready` dependency-aware نیست | TASK-9.7-3 شروع نشده | restart زودهنگام وقتی gateway پایین است | TASK-9.7-3 (با حفظ `/health` برای Docker healthcheck) | P1 — با I-02 |
| **I-08** | Low | backup | volume `agentos-data` (11 run + documents) بدون backup رسمی | deploy-repo.sh volume را untouched نگه می‌دارد ولی backup می‌کند | از دست دادن اسناد/runهای واقعی در خرابی disk | cron ساده `docker run --rm -v ai-product-orchestrator_agentos-data:/data -v /backup:/b alpine tar czf /b/agentos-$(date +%F).tar.gz -C /data .` — تصمیم کاربر | P2 — مستقل |
| **I-09** | Low | زیرساخت | gitlab + postgres + redis ~11h uptime (reboot 07:00 UTC امروز)؛ خطای 502 runner | علت reboot در این ممیزی بررسی نشد (دسترسی به log Rails/`journalctl` محدود بود) | اگر reboot مکرر باشد → ریسک CI | بررسی `journalctl -u docker`/logهای gitlab در جلسه بعد | P2 |
| **I-10** | Low | نظم ریپو | فایل‌های `_*.py` (15+ فایل probe/patch/verify) در ریشه `saberprojects` (خارج ریپو) | کارهای exploratory جلسات قبلی | شلوغی، نه ریسک ریپو | جابجایی به `server52and53/scripts-archive/` یا حذف | P2 — مستقل |
| **I-11** | Low | Git practice | فقط branch `main`؛ بدون dev/ops split | کار سریع روی پروژه واحد | ریسک کم (CI gate دارد) ولی برای multi-developer ضعیف است | اختیاری: branch protection + MR workflow در GitLab | P2 |

**Critical: هیچ موردی یافت نشد.** (secret در ریپو/لاگ نبود؛ دسترسی‌ها LAN-internal؛ بدون داده حساس personal)

## ۲. نقشه راه 6-مرحله (با خروجی قابل‌اندازه‌گیری)

### مرحله ۱ — رفع بحرانی و تثبیت زیرساخت
| کار | خروجی قابل‌اندازه‌گیری | معیار پذیرش |
|---|---|---|
| TASK-CI-1 (I-04, I-09) | token project-scoped + دستور کوئری pipeline در AGENTS.md | `curl` با token آخرین pipeline id/status را برمی‌گرداند؛ خطای 502 runner ردیه/حل می‌شود |
| بررسی علت reboot gitlab + restart policyهای همه containerها | یک پاراگراف در PROJECT_STATUS | `docker ps` همه healthy + `systemctl is-enabled docker` = enabled |

**معیار پذیرش مرحله:** «آیا CI سبز است؟» بدون کلیک در UI پاسخ‌پذیر است.

### مرحله ۲ — Git، Docker، تنظیمات محیطی
| کار | خروجی | معیار پذیرش |
|---|---|---|
| branch `feat/observability-baseline` + MR (نه مستقیم main) | 2 commit + MR باز | CI روی MR سبز |
| `systemctl is-enabled docker` + backup ساده volume (I-08) | cron entry + یک backup موفق | `ls /backup/agentos-*.tar.gz` ≥ 1 |

### مرحله ۳ — AgentOS + LiteLLM + DB (ساخت observability)
| کار | خروجی | معیار پذیرش |
|---|---|---|
| TASK-9.7-1: `workflow/observability.py` (trace_id + structured logging) | هر LlmCall/step یک log ساختاریافته؛ `trace_id` در state.json | `grep -c "print(" workflow/*.py` = 0؛ تست hermetic trace_id unique |
| TASK-9.7-2: `/metrics` Prometheus (تصادف نام با endpoint Agno حل شود) | `curl :7779/metrics/prometheus` (یا تغییر path) با `runs_total`, `llm_calls_total{model,role,status}`, `llm_tokens_total{model}`, `run_duration_seconds` | بعد از یک FakeRouter run، مقادیر تغییر می‌کنند |
| TASK-9.7-3: `/ready` dependency-aware | 200 فقط وقتی gateway `liveliness` پاسخ بدهد؛ 503 + دلیل JSON | تست hermetic monkeypatch |

**معیار پذیرش مرحله:** هر سه endpoint با تست hermetic سبز در CI + deploy روی 7779.

### مرحله ۴ — فرم مدیریت تنظیمات
> **نقشه‌برداری وضعیت:** هیچ فرم مدیریت/داشبورد اختصاصی وجود ندارد؛ UI = Agno standard. این مرحله **اول نیازسنجی** می‌خواهد:

| گزینه | شرح | تصمیم |
|---|---|---|
| A | حفظ Agno standard UI + فقط `/ready`,`/metrics` + docs | کمترین کار؛ برای internal |
| B | فرم تنظیمات کوچک (base URL، modelها، test-connection) که به `config.py`/`.env` می‌نویسد | می‌خواهد env در runtime reload شود (اکنون restart لازم است) |
| C | داشبورد کامل وضعیت (runs، scores، tokens) روی `/metrics` | با TASK-9.7-4 (Grafana) می‌آید — احتمالاً A+Grafana کافی است |

**پیشنهاد:** گزینه A + Grafana (TASK-9.7-4)؛ فرم B فقط اگر کاربر صریحاً بخواهد.

**معیار پذیرش مرحله:** تصمیم ثبت‌شده در ROADMAP + (اگر B) فرم با تست.

### مرحله ۵ — امکانات، API و امنیت
| کار | خروجی | معیار پذیرش |
|---|---|---|
| TASK-11-1: یک اجرای زنده refine (compose project جدا، هرگز 7777/7779) | state.json + score قبل/بعد + token spend ≤ 210k | `overall_score` پس refine ≥ 80 برای اسناد gapful؛ شواهد در `docs/evidence/` |
| auth مرز شبکه (I-03) — به انتخاب کاربر | firewall rule و/یا reverse proxy با basic-auth/Token | بدون دسترسی LAN، curl از بیرون 7779 fail می‌شود |
| endpoint API برای pipeline (اختیاری) | `POST /runs {brief}` → run id → `GET /runs/{id}` | تست integration |

**معیار پذیرش مرحله:** «Approved Technical Documents» برای یک brief واقعی (score ≥ 85 / completeness ≥ 80) — یا threshold بازتعریف‌شده با تصمیم کاربر.

### مرحله ۶ — تست یکپارچه، مستندسازی، انتشار
| کار | خروجی | معیار پذیرش |
|---|---|---|
| TASK-9.7-4: Prometheus job `agentos-7779` + Grafana dashboard | `up{job="agentos-7779"}==1`؛ dash با ارزش‌های واقعی | promtool check config + اسکرین‌شات dash |
| TEST_MATRIX به‌روزرسانی + coverage floor (اختیاری) | فایل به‌روز | matrix بدون «❌» غیرموجه |
| Release **v0.4.0** + tag + PROJECT_STATUS به‌روز | tag + pipeline سبز روی tag | deploy 7779 با v0.4.0 |

## ۳. ترتیب اجرایی پیشنهادی (جلسه‌های بعد)

```
جلسه 1:  مرحله ۱ (CI-1 + زیرساخت)  + شروع branch observability
جلسه 2:  مرحله ۳ کامل (9.7-1..3)   + MR + merge
جلسه 3:  TASK-11-1 (refine زنده، ~210k توکن) + TASK-9.7-4
جلسه 4:  تصمیم‌های کاربر (auth، فرم، 7777، k8s) + v0.4.0
```

## ۴. تصمیم‌های باز که منتظر کاربر است

1. **مدل قوی‌تر روی 53** vs **بازتعریف threshold 85/80** (TASK-11-2) — کاهش یک‌طرفه threshold ممنوع
2. **k8s/Helm:** cluster هدف (disk 52 ~90%!) + registry (GitLab container_registry خاموش است)
3. **7777 production:** زیر CI بیاید یا legacy بماند (I-06)
4. **فرم مدیریت:** گزینه A/B/C (مرحله ۴)
5. **auth مرز شبکه** (I-03): firewall فقط یا reverse proxy با auth
6. **backup volume** (I-08): کجا و چه فرکانسی
