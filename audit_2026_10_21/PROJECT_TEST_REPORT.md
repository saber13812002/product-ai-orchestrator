# گزارش تست‌های آزمایشی — ممیزی 2026-10-21

> همه تست‌ها **غیرمخرب، فقط-خواند** (به‌جز یک call واقعی 19-توکنی با مجوز ضمنی ممیزی).
> هیچ تغییری در داده/دستگاه/تاریخچه اعمال نشده است.

## جدول نتایج

| # | تست | دستور/روش | نتیجه | شواهد | توضیحات |
|---|---|---|---|---|---|
| T1 | صحت پیکربندی‌ها (YAML/Python/TOML) | `docker compose config` (هر دو profile، در STEP 9) + parse AST همه `workflow/*.py` + `personal_agent.py` | **PASS** | `ast.parse` روی همه فایل‌ها بدون خطا؛ compose هر دو profile معتبر (شواهد STEP 9 + کانتینرهای زنده) | در این ممیزی compose روی 52 با `docker compose config` مجدداً اجرا نشد (deploy-dir همان stack زنده 11h است) — شواهد معادل پذیرفته شد |
| T2 | نصب‌بودن وابستگی‌ها | اجرای تست‌ها داخل کانتینر (همان env که CI build کرده) | **PASS** | 30 تست اجرا شدند → همه وابستگی‌ها import و کار می‌کنند | `uv.lock` frozen در Dockerfile |
| T3 | قابلیت Build | image موجود از CI + md5 sync | **PASS (غیرمستقیم)** | image `ai-product-orchestrator:latest` (526MB) در حال اجرا؛ آخرین build = commit 299f1a3؛ md5 سه فایل deploy = git main | build جدید در این ممیزی انجام نشد (قانون: تغییر deployment در ممیزی ممنوع) |
| T4 | Healthcheck سرویس‌ها | `docker ps` + `curl /health` | **PASS** | هر دو کانتینر `(healthy)`؛ `{"status":"ok"}` روی 7777 و 7779 | healthcheck = process-alive فقط (I-07) |
| T5 | اتصال به پایگاه داده | لاگ startup کانتینر | **PASS** | `INFO Database ready: SqliteDb id=...`؛ `agent.db` در volume `agentos-data` | — |
| T6 | اتصال AgentOS به LiteLLM | `resolve_endpoint()` (env در کانتینر) + liveliness gateway | **PASS** | env نام‌ها: `LITELLM_API_KEY`, `LITELLM_BASE_URL` موجود؛ `:4000/health/liveliness` → 200 | mode = external (STEP 9 + AI_HANDOFF) |
| T7 | پاسخ‌گویی Endpointهای اصلی | `curl :7779/health`, `/openapi.json`, `/ready`, `/metrics` | **PASS (با یادداشت)** | `/health` 200 JSON ok؛ OpenAPI 3.1.0 با ~70 مسیر؛ **`/ready` → 404** (وجود ندارد)؛ `/metrics` → 200 ولی `{"metrics":[],...}` = endpoint JSON خالی فریم‌ورک Agno، **نه** Prometheus | یادداشت مهم برای TASK-9.7-2: `/metrics` از قبل گرفته شده است |
| T8 | یک call واقعی مدل (کم‌هزینه) | `POST :4000/v1/chat/completions`، model `qwen38-nothinking`، max_tokens=15 | **PASS** | content = `"OK"`؛ usage: **19 توکن** (17 prompt + 2 completion)، reasoning 0 | کلید از `.env` 52 خوانده شد و هرگز print نشد |
| T9 | 30 تست hermetic (عین CI) | `docker exec agno-agentos-repo uv run --with pytest python -m pytest workflow/tests -q` | **PASS** | `30 passed in 0.83s` — **اجرای مستقیم این ممیزی** | بدون LLM/شبکه/کلید |
| T10 | همگامی deploy-target با git | `md5sum` سه فایل در `/home/saber/saberprojects/...` در برابر `git show main:...` محلی | **PASS** | `engine.py c1b859…`, `config.py edcd2e…`, `README.md a41514…` — هر سه یکسان | 7779 دقیقاً git main را اجرا می‌کند |
| T11 | Sync با remote | `git status` + `git ls-remote origin refs/heads/main` | **PASS** | tree clean؛ remote main = `299f1a3` = محلی | — |
| T12 | امنیت اولیه (secret در ریپو/لاگ) | `git status --ignored`، بررسی `litellm/config.yaml`، `git log -p` محدود، sed روی logهای کانتینر | **PASS** | `.env` gitignored (و در 52 chmod 600)؛ config LiteLLM فقط `${VAR}`؛ هیچ secret در لاگ/ریپو پیدا نشد | audit-level check، نه اسکن کامل تاریخچه |
| T13 | مدیریت خطا/Timeout | بررسی کد (retry/timeout در router/engine) + `test_robustness.py` | **PASS (code-level)** | `test_robustness.py` (negative tests) در 30 تست سبز است؛ timeout در OpenAI client | test زنده «خرابی gateway» در ممیزی انجام نشد (مخرب محسوب می‌شد) |
| T14 | کوئری وضعیت CI pipeline | تلاش GitLab API | **BLOCKED** | token project-scoped وجود ندارد (در 52 و لپ‌تاپ)؛ `api/v4/projects` بدون auth → 404 | → TASK-CI-1؛ evidence غیرمستقیم: deploy در 299f1a3 و healthy |
| T15 | اجرای زنده refine با شواهد | بررسی storage (volumeهای 7777/7779) | **SKIPPED (مستند)** | هیچ run post-refine در storage نیست (یافته 2026-10-20، تکرار شد)؛ اجرای زنده در ممیزی ممنوع | → TASK-11-1 |
| T16 | restart سرور / boot after reboot | بررسی restart policy | **PASS (سخت‌افزاری)** | `restart=unless-stopped` روی هر دو کانتینر | `systemctl is-enabled docker` روی 52 در این ممیزی چک نشد — ریسک کم |
| T17 | فرم تنظیمات / ذخیره از UI | جستجوی کد | **SKIPPED (وجود ندارد)** | هیچ فرم/رابط تنظیمات اختصاصی در کد نیست؛ UI = Agno standard | نیازسنجی قبل از ساخت |

**جمع:** 12 PASS · 2 SKIPPED · 1 BLOCKED · 0 FAIL

## هزینه تست‌های واقعی

| مصرف | مقدار |
|---|---|
| 1 chat completion (`qwen38-nothinking`, max 15) | 19 توکن |
| 30 تست hermetic | 0 توکن (FakeRouter) |

## خطاهای دیده‌شده و تحلیل

| مشاهده | تفسیر | اقدام |
|---|---|---|
| `502 Bad Gateway` در لاگ runner (06:52 UTC امروز) هنگام `jobs/request` | هم‌زمان با ~11h uptime gitlab (ری‌استارت ~07:00) — احتمالاً runner چند ثانیه بعد از reboot GitLab job request کرده و 502 خورده؛ **اما** چون آخرین deploy (11h پیش) موفق بوده، pipeline شکسته نیست | TASK-CI-1: چک pipeline list + بررسی runner health |
| `content: None` برای `qwen38`/`qwen38-sglang` (یافته 10-20، تکرار) | thinking budget کل output را می‌گیرد؛ **رفتار مستند و مورد انتظار** — به همین دلیل همه کارهای structured روی `fast` است | بدون اقدام (مستند در CONFIGURATION/AGENT_DESIGN) |
| `/ready` 404 | endpoint هنوز build نشده | TASK-9.7-3 |
| `/metrics` JSON خالی | endpoint Agno (سازگار با API خودش)، نه Prometheus | TASK-9.7-2 باید تصمیم بگیرد: تغییر مسیر یا افزودن `/metrics/prometheus` (تصادف نام باید حل شود) |

## معیارهای «آزموده‌شدن» برای هر ادعا

- **پیاده‌سازی‌شده** = کد در ریپو + تست hermetic
- **تست‌شده زنده** = اجرا واقعی با خروجی ثبت‌شده (run `97dda8`؛ call T8 این ممیزی)
- **در حال اجرا** = `docker ps` + health + endpoint پاسخ‌گو
- **آماده عملیاتی** = سه مورد قبل + observability + auth/مرز شبکه + backup + CI queryable — **هنوز خیر**
