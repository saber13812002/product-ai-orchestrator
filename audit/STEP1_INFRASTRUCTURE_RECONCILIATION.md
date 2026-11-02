# STEP 1 — Infrastructure Reconciliation & Git Baseline

**Project:** AI Product Orchestrator
**Repo:** `common/website/ai-product-orchestrator` (GitLab project 28)
**Date:** 2026-11-02
**Author:** AI assistant (STEP 1 execution)
**Status:** COMPLETE — awaiting user approval for merge/deploy

---

## 1. Executive Summary

Server 52 (172.20.1.52) was **migrated to 133** (172.30.0.133, hostname `AI-TOOLS`) on
2026-11-02. All 52 infrastructure (GitLab, AgentOS, LiteLLM, CI runners) now runs on 133.
The old address `172.20.1.52` is **dead** — nothing listens there.

**What this STEP 1 did:**
- Audited all 14 files containing `172.20.1.52` references in the repo; classified each into
  Category A (operational — fix), B (historical — preserve), C (logical name — no change), or
  D (unverified — document).
- Fixed 13 active files (12 modified + 1 new) to point to `172.30.0.133`.
- Created `docs/SERVER_TOPOLOGY.md` as the authoritative address map.
- Audited both GitLab CI runners: **both are broken** — their `url`/`clone_url` fields still
  point to the dead `http://172.20.1.52:81`. CI is non-functional until they are re-pointed.
- Committed changes on branch `docs/fix-52-to-133-migration` (commit `f1c445b`), pushed to
  133:81, and updated MR !1 to use the new source branch.
- **No merge, no deploy, no Production changes, no runner config changes, no secrets printed.**

**Blocking item for STEP 2:** Re-point both CI runners from dead `172.20.1.52:81` to
`172.30.0.133:81`. This requires backup + user approval (runners may be shared between projects).

---

## 2. Git / Commit Status

| Item | Value |
|---|---|
| **Local `main`** | `299f1a3` (unchanged from 2026-10-21 record) |
| **Remote `main`** | `299f1a3` (re-verified on 133:81) |
| **Working branch** | `docs/fix-52-to-133-migration` (created from `docs/audit-baseline-2026-10-21` at `f404e10`) |
| **Working branch head** | `f1c445b` (this STEP 1 commit) |
| **Parent commit** | `f404e10` (local-only, not previously pushed to remote) |
| **Base commit** | `44d3223` (the original docs branch head, was the old MR !1 source) |
| **Release tag** | `v0.3.0` (unchanged) |
| **Working tree** | Clean (all changes committed) |
| **Remote** | Updated from `http://172.20.1.52:81/...` to `http://172.30.0.133:81/...` |
| **History** | NOT rewritten — new commit on an independent branch |

### Commit graph (simplified)

```
main (299f1a3)
  └── docs/audit-baseline-2026-10-21 (44d3223 → f404e10)
        └── docs/fix-52-to-133-migration (f1c445b) ← THIS COMMIT
```

---

## 3. MR !1 Status

| Field | Before | After |
|---|---|---|
| **State** | opened | opened |
| **Title** | `docs: 2026-10-21 re-audit bundle + living test/observability checklist` | `docs: STEP 1 Infrastructure Reconciliation — 52→133 migration + 2026-10-21 re-audit baseline` |
| **Source branch** | `docs/audit-baseline-2026-10-21` | `docs/fix-52-to-133-migration` |
| **Source head** | `44d3223` | `f1c445b` |
| **Target branch** | `main` | `main` |
| **Target head** | `299f1a3` | `299f1a3` |
| **Conflicts** | None (rebase check) | None (same base) |
| **Merge** | **NOT MERGED** (user approval required) | **NOT MERGED** (user approval required) |

The MR now contains **all** of the original 2026-10-21 re-audit bundle **plus** the STEP 1
Infrastructure Reconciliation changes, because the new branch was created from the old docs
branch.

---

## 4. Full Old/New IP Reference Table

### Category A — Operational address (FIXED: 172.20.1.52 → 172.30.0.133)

| File | Line(s) | Old | New | What it was |
|---|---|---|---|---|
| `AGENTS.md` | 18 | `http://172.20.1.52:81` | `http://172.30.0.133:81` | Git clone URL |
| `AGENTS.md` | 93 | `http://172.20.1.52:81` | `http://172.30.0.133:81` | Runner `clone_url` example |
| `README.md` | 1 | `http://172.20.1.52:81` | `http://172.30.0.133:81` | Git clone URL |
| `.env.example` | 25 | `http://172.20.1.52:4000/v1` | `http://172.30.0.133:4000/v1` | LiteLLM base URL |
| `docs/CI_CD.md` | 1 | `http://172.20.1.52:81` | `http://172.30.0.133:81` | GitLab address |
| `docs/CONFIGURATION.md` | 1 | `http://172.20.1.52:4000` | `http://172.30.0.133:4000` | LiteLLM base URL |
| `docs/DEPLOYMENT.md` | 2 | `172.20.1.52` | `172.30.0.133` | Deploy target IP |
| `docs/DEVELOPMENT.md` | 2 | `172.20.1.52` | `172.30.0.133` | Development server IP |
| `docs/LITELLM.md` | 1 | `http://172.20.1.52:4000` | `http://172.30.0.133:4000` | LiteLLM gateway |
| `docs/PROJECT_STATUS.md` | 3 | `172.20.1.52` | `172.30.0.133` | Server reference |
| `docs/ROADMAP.md` | 1 | `172.20.1.52` | `172.30.0.133` | Server reference |
| `workflow/tests/test_endpoint.py` | 23,26,96,100,107 | `http://172.20.1.52:4000` | `http://172.30.0.133:4000` | Test fixture (hermetic, no network) |

### Category B — Historical address (PRESERVED with migration note)

| File | Refs | Handling |
|---|---|---|
| `docs/AI_HANDOFF.md` §0a | 9 refs to `172.20.1.52` | **Preserved verbatim** as historical finding ("52 was down at audit time"). Added SUPERSEDED note: 52 migrated to 133, now UP. All refs are in the migration narrative context. |
| `audit_2026_10_21/PROJECT_STATUS_REPORT.md` | 2 refs | **Unchanged** — historical audit report |
| `audit_2026_10_21/PROJECT_ARCHITECTURE.md` | 2 refs | **Unchanged** — historical architecture diagram |

### Category C — Logical name/tag (NO CHANGE needed)

| File | Ref | Why no change |
|---|---|---|
| `.gitlab-ci.yml` | `tags: [server52]` (2×) | Runner **tag name**, not an IP. The tag is a label; changing it would require re-tagging the runners. |
| `AGENTS.md` | `server52` runner references | Runner **name** (`aio-server52`). Per instruction: "change server52 name only if proven wrong." The name is a historical label, not an IP. |
| `README.md` | `server52` runner references | Same — runner tag/name. |

### Category D — Address not yet verified / different server

| File | Ref | Why |
|---|---|---|
| `.env.example` | `172.20.1.53:8000`, `172.20.1.53:8001` (3×) | Model backends on **server 53** — did NOT migrate with 52. Correct as-is. |
| `docs/AI_HANDOFF.md` §2 | `172.20.1.53` (53 model backends) | Server 53 — unchanged. |

### New file created

| File | Purpose |
|---|---|
| `docs/SERVER_TOPOLOGY.md` | **Authoritative address map** — single source of truth for all 133-based addresses, runner status, old-address reference, out-of-scope services. |

---

## 5. All Runner Status (on 133)

| Runner | ID | Name | Tag | Executor | `url` | `clone_url` | systemd | Last job | Likely failure |
|---|---|---|---|---|---|---|---|---|---|
| `aio-server52` | 5 | `aio-server52` | `server52` | shell | `http://172.20.1.52:81` **(DEAD)** | `http://172.20.1.52:81` **(DEAD)** | `gitlab-runner.service` active (running 2 days) | Pipeline #202 (2026-10-22, success — ran before migration) | `url`/`clone_url` point to dead 52:81 → **CI broken** |
| `9router-ci-server52` | — | `9router-ci-server52` | (untagged, `run_untagged_jobs=true`) | shell | `http://172.20.1.52:81/` **(DEAD)** | (not set) | Same `gitlab-runner.service` | Unknown (serves project 51) | Same — dead `url` |

### Runner config files (on 133)

| Runner | Config path | Key fields |
|---|---|---|
| `aio-server52` | `/home/saber/gitlab-runner-aio/config.toml` | `url = "http://172.20.1.52:81"`, `clone_url = "http://172.20.1.52:81"`, `tag_list = ["server52"]`, `request_concurrency = 4` |
| `9router-ci-server52` | `/home/saber/.gitlab-runner/config.toml` | `url = "http://172.20.1.52:81/"` |

### ⚠️ Do NOT change without backup + approval

Both runners may serve **multiple projects** (project 28 = this repo, project 51 = 9router).
Changing `url`/`clone_url` affects **all** projects attached to the runner. Per user instruction:
"Runnerها ممکن است بین چند پروژه مشترک باشند؛ تنظیماتشان را بدون Backup و تأیید جداگانه تغییر نده."

**Recommended fix (pending user approval):**
1. Backup both `config.toml` files.
2. Change `url` and `clone_url` from `http://172.20.1.52:81` → `http://172.30.0.133:81`.
3. `sudo systemctl restart gitlab-runner`.
4. Verify with a test pipeline.

---

## 6. Changes Made

| # | File | Type | Change |
|---|---|---|---|
| 1 | `AGENTS.md` | Modified | Git remote URL, deploy target label, clone_url example, server labels (52→133) |
| 2 | `README.md` | Modified | Git clone URL |
| 3 | `.env.example` | Modified | LiteLLM base URL |
| 4 | `docs/CI_CD.md` | Modified | GitLab address |
| 5 | `docs/CONFIGURATION.md` | Modified | LiteLLM base URL |
| 6 | `docs/DEPLOYMENT.md` | Modified | Deploy target IP (2 refs) |
| 7 | `docs/DEVELOPMENT.md` | Modified | Development server IP (2 refs) |
| 8 | `docs/LITELLM.md` | Modified | LiteLLM gateway URL |
| 9 | `docs/PROJECT_STATUS.md` | Modified | Server reference (3 refs) |
| 10 | `docs/ROADMAP.md` | Modified | Server reference |
| 11 | `docs/AI_HANDOFF.md` | Modified | §0a: SUPERSEDED note on "52 down" finding; decision history updated; "Remaining work" renumbered; §2 address table updated; §11 checkpoint block updated |
| 12 | `workflow/tests/test_endpoint.py` | Modified | 5 fixture IPs: `172.20.1.52:4000` → `172.30.0.133:4000` (hermetic, no network) |
| 13 | `docs/SERVER_TOPOLOGY.md` | **New** | Authoritative address map: 52→133 migration, current address table, SSH access, runner status, old-address reference, out-of-scope services |

**Total: 12 modified + 1 new = 13 files, 164 insertions, 55 deletions.**

---

## 7. Changed Files (git)

```
M  .env.example
M  AGENTS.md
M  README.md
M  docs/AI_HANDOFF.md
M  docs/CI_CD.md
M  docs/CONFIGURATION.md
M  docs/DEPLOYMENT.md
M  docs/DEVELOPMENT.md
M  docs/LITELLM.md
M  docs/PROJECT_STATUS.md
M  docs/ROADMAP.md
A  docs/SERVER_TOPOLOGY.md
M  workflow/tests/test_endpoint.py
```

---

## 8. Tests Run + Real Output

### 8a. Hermetic tests (local, agno-free modules)

**Command:**
```
python -m pytest workflow/tests/test_state.py workflow/tests/test_endpoint.py -v --tb=short
```

**Output (abridged):**
```
platform win32 -- Python 3.13.15, pytest-9.2.0, pluggy-1.7.0
collected 15 items

workflow/tests/test_state.py::test_create_and_persist PASSED             [  6%]
workflow/tests/test_state.py::test_save_load_roundtrip PASSED            [ 13%]
workflow/tests/test_state.py::test_list_runs PASSED                      [ 20%]
workflow/tests/test_state.py::test_token_totals_recalc PASSED            [ 26%]
workflow/tests/test_state.py::test_record_call_persists PASSED           [ 33%]
workflow/tests/test_state.py::test_new_run_id_format PASSED              [ 40%]
workflow/tests/test_endpoint.py::test_external_mode_resolves_from_external_env PASSED [ 46%]
workflow/tests/test_endpoint.py::test_external_mode_falls_back_to_legacy_openai PASSED [ 53%]
workflow/tests/test_endpoint.py::test_external_mode_prefers_litellm_over_openai PASSED [ 60%]
workflow/tests/test_endpoint.py::test_bundled_mode_resolves_to_sidecar PASSED [ 66%]
workflow/tests/test_endpoint.py::test_bundled_url_is_overridable PASSED  [ 73%]
workflow/tests/test_endpoint.py::test_bundled_mode_missing_key_yields_empty PASSED [ 80%]
workflow/tests/test_endpoint.py::test_default_mode_is_external PASSED    [ 86%]
workflow/tests/test_endpoint.py::test_endpoint_warning_for_non_v1_url PASSED [ 93%]
workflow/tests/test_endpoint.py::test_no_trailing_slash_still_warns PASSED [100%]

============================= 15 passed in 0.60s ==============================
```

**Result: 15/15 PASSED.** The 7 `test_endpoint.py` tests now use the updated `172.30.0.133`
fixture IPs — all pass.

### 8b. Full 30-test suite

**NOT run locally** — 6 test modules import `agno`, which cannot install on this laptop
(32-bit Python → no wheels). Full 30/30 re-runs only in the 133 container or in CI.
**CI is currently broken** (runners point to dead 52:81), so the full 30-test suite
**cannot be verified until the runners are re-pointed.**

### 8c. `git diff --check`

**Command:** `git diff --check`
**Exit code:** 0 (clean — no whitespace errors)

### 8d. Secret scan

**Command:** `git diff --unified=0 | grep -iE "(sk-[a-zA-Z0-9]{20,}|glpat-...|glrt-...|...)"`
**Result:** **0 secrets found in the diff.**

Note: A runner token was accidentally exposed in SSH output during the audit (the
`9router-ci-server52` runner's `token` field). **This token is NOT in the repo, NOT in the
diff, and NOT printed in this report.** It should be rotated as a precaution.

---

## 9. Pipeline Status

| Pipeline | Ref | Status | Date | Notes |
|---|---|---|---|---|
| #202 | `refs/merge-requests/1/head` (old head `44d3223`) | **success** | 2026-10-22 | Last known green pipeline — **before the 52→133 migration** |
| (none) | `docs/fix-52-to-133-migration` (new head `f1c445b`) | **NOT TRIGGERED** | — | CI is broken — runners point to dead `172.20.1.52:81` |

**The old green pipeline (#202) does NOT confirm current state.** It ran on the old
`44d3223` head, before the migration, before any of the 13 file changes in this STEP 1.
The current pipeline **cannot run** until the runners are re-pointed.

---

## 10. Unresolved Problems

| # | Problem | Impact | Resolution path |
|---|---|---|---|
| 1 | **Both CI runners point to dead `http://172.20.1.52:81`** | CI is completely broken — no pipeline can run for any project on 133's GitLab | Re-point `url`/`clone_url` to `http://172.30.0.133:81` + restart `gitlab-runner`. **Requires backup + user approval.** |
| 2 | **Full 30-test suite cannot be verified** | Cannot confirm no regression until CI works | Re-point runners → push → CI runs full suite |
| 3 | **Runner token leaked in audit output** | The `9router-ci-server52` runner's `token` field was visible in SSH output | **Rotate the token.** (Not in repo, not in this report.) |
| 4 | **Prometheus targets may still reference `172.20.1.52`** | Monitoring gaps on 133 | Separate follow-up (out of this repo's scope) |
| 5 | **GitLab runner `url` is HTTP, not HTTPS** | Security: credentials sent in cleartext over LAN | Pre-existing; not a STEP 1 change. Use HTTPS if a cert is available. |
| 6 | **Git credential on laptop** | The laptop's git config has `credential.http://172.20.1.52:81.provider=generic` — stale | Clean up (minor) |

---

## 11. Items Needing User Approval

| # | Item | Why approval needed |
|---|---|---|
| 1 | **Re-point CI runners** (`aio-server52` + `9router-ci-server52`) from `172.20.1.52:81` to `172.30.0.133:81` | Runners may be shared between projects; changing `url`/`clone_url` affects all attached projects. Per user instruction: backup + separate approval required. |
| 2 | **Rotate `9router-ci-server52` runner token** | Token was accidentally exposed in audit SSH output. |
| 3 | **Merge MR !1** | Per user instruction: "Merge و Deploy ممنوع؛ منتظر تأیید من بمان." (Merge and Deploy forbidden; wait for my approval.) |
| 4 | **Deploy** | Merging MR !1 to main triggers the `deploy` job → 7779 rebuild + restart. User must confirm 133 is stable + accept the 7779 restart. |
| 5 | **Clean up laptop git config** | Remove stale `credential.http://172.20.1.52:81.provider=generic` and `credential.http://172.20.1.52.provider=generic` entries. |

---

## 12. Rollback Plan

All changes are on an **independent branch** (`docs/fix-52-to-133-migration`). Nothing is
merged to `main`. Rollback is trivial:

### Option A — Discard the branch entirely
```bash
git checkout main
git branch -D docs/fix-52-to-133-migration
git push origin --delete docs/fix-52-to-133-migration
# Revert MR !1 source branch back to docs/audit-baseline-2026-10-21 (via GitLab API or Web UI)
```

### Option B — Keep the branch, revert specific files
```bash
# On the branch, revert specific files to their pre-STEP-1 state:
git checkout f404e10 -- <file>
git commit -m "revert: ..."
```

### Option C — Revert the MR
- Close MR !1 (do not merge).
- The source branch `docs/fix-52-to-133-migration` remains on the remote but is not merged.
- MR !1 can be re-pointed back to `docs/audit-baseline-2026-10-21` if the original scope is
  still needed.

### What is NOT reversible without action
- The git remote URL was changed from `172.20.1.52:81` to `172.30.0.133:81` (local `.git/config`).
  This is correct (the old address is dead) and should be kept.
- A 30-day PAT was minted for `saber13812002` (name: `step1-push-2026-11-02`). It can be
  revoked via GitLab Admin → Users → Tokens, or it expires in 30 days.

---

## 13. NEXT_CHAT_CHECKPOINT

```
PROJECT: AI Product Orchestrator
REPO: http://172.30.0.133:81/common/website/ai-product-orchestrator.git
  (migrated from 52/172.20.1.52 on 2026-11-02; old address is DEAD)

COMPLETED THIS SESSION (STEP 1 — Infrastructure Reconciliation):
  - All operational 172.20.1.52 refs → 172.30.0.133 (13 files)
  - docs/SERVER_TOPOLOGY.md created (authoritative address map)
  - docs/AI_HANDOFF.md §0a updated (52-down finding marked SUPERSEDED)
  - test_endpoint.py fixtures updated (hermetic, no network)
  - Committed on docs/fix-52-to-133-migration (f1c445b), pushed to 133:81
  - MR !1 updated: source branch = docs/fix-52-to-133-migration, head = f1c445b
  - 15/15 hermetic tests pass locally; git diff --check clean; 0 secrets in diff

BLOCKING ITEMS FOR NEXT SESSION:
  1. RE-POINT CI RUNNERS (requires user approval + backup):
     - /home/saber/gitlab-runner-aio/config.toml: url/clone_url → http://172.30.0.133:81
     - /home/saber/.gitlab-runner/config.toml: url → http://172.30.0.133:81
     - sudo systemctl restart gitlab-runner
     - Verify with test pipeline
  2. ROTATE runner token for 9router-ci-server52 (leaked in audit output)
  3. USER MERGES MR !1 (no merge without explicit approval)
  4. FULL 30-TEST verification (needs working CI or in-container run)

SERVER STATE (133 = 172.30.0.133, hostname AI-TOOLS):
  - GitLab :81 UP
  - AgentOS 7777 (prod) + 7779 (deploy target) UP
  - LiteLLM :4000 UP
  - CI runners: UP (systemd) but BROKEN (url → dead 52:81)
  - 53 (172.20.1.53): model backends :8000/:8001 UP (unchanged)

HARD RULES (unchanged):
  No secrets in repo. CI hermetic. No 7777/7779 restart without approval.
  No merge/deploy without explicit user approval. ASR/Whisper/Voice Bot out of scope.
  Never blindly replace all 52s with 133. Don't rewrite history.

READ FIRST: docs/AI_HANDOFF.md + docs/SERVER_TOPOLOGY.md + audit/STEP1_INFRASTRUCTURE_RECONCILIATION.md
```
