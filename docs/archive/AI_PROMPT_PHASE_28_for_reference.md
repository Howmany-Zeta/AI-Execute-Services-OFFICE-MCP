# Phase 28 — Patch `0046` (`startu-chatbot-gating-tests`) — AI Prompt Sequence

将下方 prompt **按顺序** 复制到 AI 会话（Cursor Agent 等）。**一次只跑一个 Task**；执行该步 **Verification** 通过后再进入下一步。

**设计真源：** [`PHASE_28_STARTU_CHATBOT_GATING_TESTS_DESIGN.md`](./PHASE_28_STARTU_CHATBOT_GATING_TESTS_DESIGN.md)（含 **§2 SC-META-001～004**、**§4 CI 脚本**、**§5 手测 J1～J9**）  
**按文件任务：** [`PHASE_28_STARTU_CHATBOT_GATING_TESTS_TASKS_BY_FILE.md`](./PHASE_28_STARTU_CHATBOT_GATING_TESTS_TASKS_BY_FILE.md)  
**手测清单：** [`reference/LAYER_A_SC_META_CHECKLIST.md`](./reference/LAYER_A_SC_META_CHECKLIST.md)  
**计划表：** [`PATCH_DEVELOPMENT_PLAN.md`](./PATCH_DEVELOPMENT_PLAN.md) 表 **#28**  
**前置 Phase：** [`AI_PROMPT_PHASE_27B.md`](./AI_PROMPT_PHASE_27B.md)（**#27b / `0045`** 须已验收）

**前置：** **`0045`** 已 materialize；Layer A **#19～#27a** parity 闭环；**`ci-verify`** 至 **0045** 绿。

**#28 后中间态（必读）：** 设计 **[§1](PHASE_28_STARTU_CHATBOT_GATING_TESTS_DESIGN.md#1-与-27b--layer-b-的分水岭)** — Layer A **验收完成** 后 **Playwright 全量 E2E**、**Layer B Agent/MCP** 仍 **不在 #28** — **#29+** 开栈。

**Patch 编号：** 默认 **`0046-startu-chatbot-gating-tests.patch`**（紧接 **`0045`**）。**父仓库同 PR（不进 patch）：** **`scripts/verify-startu-layer-a-gating.sh`** · **`scripts/ci-verify-docen.sh`** 挂钩 · **`docs/reference/LAYER_A_SC_META_CHECKLIST.md`**。

**文件头（#28 新增 TS）：** 使用 **IRETBL GROUP 专有头**（**`README.md`**「许可与文件头政策」），**禁止** `Licensed under the MIT License` 第二行。

---

## 0. Session Bootstrap Prompt（仅首次）

```
You are implementing Docen Phase 28 — patch 0046-startu-chatbot-gating-tests + parent-repo CI gating scripts (Layer A Tests / SC-META acceptance ONLY).

Required reading (parent repo startu-docen):
- docs/PHASE_28_STARTU_CHATBOT_GATING_TESTS_DESIGN.md (especially §2 SC-META, §4 verify-startu-layer-a-gating.sh, §5 manual J1–J9, §7 DoD)
- docs/PHASE_28_STARTU_CHATBOT_GATING_TESTS_TASKS_BY_FILE.md (28-001–048)
- docs/reference/LAYER_A_SC_META_CHECKLIST.md
- docs/PHASE_27B_STARTU_LAYER_A_CURSOR_PARITY_AUDIT_DESIGN.md (Layer A scope — do NOT re-audit/fix product code here)
- docs/PATCH_DEVELOPMENT_PLAN.md — 用户使用效果对标评估 table
- scripts/ci-verify-docen.sh (current assert_production_contract hook point)
- README.md — 「许可与文件头政策」
- .cursor/rules/docen-orchestration.mdc
- .cursor/rules/docen-patches.mdc
- .cursor/rules/docen-vscode-main-compile.mdc

Global constraints:
1. Authoritative deliverables:
   - patches/0046-startu-chatbot-gating-tests.patch (vscode-main test/** ONLY + minimal export if needed)
   - scripts/verify-startu-layer-a-gating.sh + ci-verify-docen.sh hook (parent repo — NOT in 0046 patch)
   - docs/reference/LAYER_A_SC_META_CHECKLIST.md (already exists — extend if needed)
   - transforms/pipeline.json + patches/series.post-transform
2. Single patch intent = Layer A GATING / TESTS ONLY:
   - SC-META-001: no copilot tree, cannotImportExtensions
   - SC-META-002: startuAuth present; BAN auth-chatbot-chat LM / SubscribePage paths
   - SC-META-003: contrib/chatbot materialized; openChat → openChatbot; scholar-only HTTP constants
   - SC-META-004: Chat settings → startuSettings; pricing external via getPricingUrl/openPricing
3. BAN list (MANDATORY):
   - Modify production browser/*.ts (chatbotAgent, gatewayClient, startuSettings webview host, chatSetupController, etc.) — ONLY test/** unless compile requires trivial export
   - Layer B features (#29+): startuAgent, workspace index, scholar graph, full MCP UX
   - Playwright / new E2E framework in #28
   - general/multi-task HTTP routes
   - registerLanguageModelChatProvider / auth-chatbot-chat main path
   - SubscribePage / auth-subscribe-webview
   - Parity re-audit / GAP fixes — send back to #27b / 0045 hotfix
4. Two-repo deliverable split:
   - Parent repo: verify-startu-layer-a-gating.sh, ci-verify hook, checklist, 0046 patch file, series, pipeline, docs links
   - vscode-main (0046): new tests under contrib/chatbot/test, contrib/chat/test, services/startuAi/test
5. vscode-main must be its own git repo; never git clean -fdx inside vscode-main.
6. npm run compile in vscode-main MUST use Node 22.x PATH (docen-vscode-main-compile.mdc).
7. One prompt = one task group unless this doc explicitly merges them.
8. Do NOT git commit unless I explicitly ask.
9. vscode-main Git contract: after ci-verify through 0045, run git -C vscode-main add -A ONCE to freeze index. All #28 test edits stay UNSTAGED until export. create-patch.sh = git diff (working − index).
10. Patch files MUST use LF line endings (CRLF breaks git apply on Windows).
11. HARD BAN (docen-patches.mdc): Do NOT run ci-verify-docen.sh on dirty vscode-main before create-patch.sh export. Pre-export gate = npm run compile + run new unit tests; full ci-verify AFTER §6 export (includes new gating script).
12. #29 Layer B MUST NOT start until 28-T accepted (SC-META manual sign-off).

Precondition check before coding:
- patches/series.post-transform lists through 0045-startu-layer-a-cursor-parity-audit.patch
- 0046 is NOT yet in series (next slot)
- test -d vscode-main/src/vs/workbench/contrib/chatbot/browser
- test -d vscode-main/src/vs/workbench/contrib/startuSettings
- test -f vscode-main/src/vs/workbench/services/startuAi/common/startuScholarSummarizer.ts
- test -f docs/reference/LAYER_A_SC_META_CHECKLIST.md
- ! rg "SubscribePage|auth-subscribe-webview" vscode-main/ --glob "*.ts"

After confirming you read the design docs, reply "Ready for 28-prep" — do not write code yet.
```

---

## 1. Task 28-prep — Materialize through `0045` + freeze index

```
[TASK 28-prep] Materialize through 0045; freeze vscode-main index; baseline test inventory

Prerequisite: Phase #27b (#27b-T) accepted (0045 shipped; Layer A parity complete).

From parent repo root:
  unset UPSTREAM_WORKTREE
  DOCEN_SKIP_SUBMODULE_INIT=1 DOCEN_FORCE_SUBMODULE_HTTPS=1 ./scripts/ci-verify-docen.sh

Freeze index ONCE before any #28 vscode-main test edit:
  git -C vscode-main add -A

Baseline inventory (Tasks 28-004 — document only):
- List existing Layer A unit tests (design §6): chatbotService, chatbotAgent, chatbotChatService, startuAuth, startuCreds, startuChatPlatformGate, startuSettings, startuQuotaMapper, startuEntitlementMapper
- Confirm STARTU_SCHOLAR_SUMMARIZER_PATH / STARTU_FORBIDDEN_AI_PATHS in startuScholarSummarizer.ts

Lock scope (Task 28-001):
- Tests/gating ONLY; SC-META-001–004; NO product features
- 0046 = vscode-main test/** only
- Parent scripts NOT in 0046 patch

Do NOT edit files in this step except documenting baseline. Do NOT git add again until §6 export. Replay in english
```

**Verification commands**
```bash
cd "$(git rev-parse --show-toplevel)"
DOCEN_SKIP_SUBMODULE_INIT=1 DOCEN_FORCE_SUBMODULE_HTTPS=1 ./scripts/ci-verify-docen.sh
grep 0045 patches/series.post-transform
test -d vscode-main/src/vs/workbench/contrib/chatbot/browser && echo "OK: chatbot"
test -d vscode-main/src/vs/workbench/contrib/startuSettings && echo "OK: startuSettings"
test -f vscode-main/src/vs/workbench/services/startuAi/common/startuScholarSummarizer.ts && echo "OK: scholar paths"
! grep -q "^0046-" patches/series.post-transform && echo "OK: 0046 slot free"
git -C vscode-main diff --cached --stat | head -5
```

---

## 2. Tasks 28-006 – 28-012 — Parent CI: `verify-startu-layer-a-gating.sh`

```
[TASK 28-006–012] Create scripts/verify-startu-layer-a-gating.sh + hook ci-verify-docen.sh

Implement Tasks 28-006 through 28-012 from docs/PHASE_28_STARTU_CHATBOT_GATING_TESTS_TASKS_BY_FILE.md Group B.

1) scripts/verify-startu-layer-a-gating.sh (NEW — parent repo)
   - set -euo pipefail; ROOT from script location
   - TARGET=vscode-main
   - Implement design §4.1 SC-META-001 (no extensions/copilot, product cannotImportExtensions, build lists)
   - Implement §4.2 SC-META-002 (BAN auth-chatbot-chat/LM provider/SubscribePage; startuAuth files exist)
   - Implement §4.3 SC-META-003 (chatbot tree, workbench.common.main import, openChatbot routing, isDefault flags, scholar path, no general/multi-task in src)
   - Implement §4.4 SC-META-004 (startuSettings, chatActions settings reroute, openPricing/getPricingUrl)
   - On failure: echo "SC-META-NNN: ..." to stderr; exit 1
   - bash -n must pass

2) scripts/ci-verify-docen.sh
   - After assert_production_contract, before series coverage check:
     echo "ci-verify-docen: verify-startu-layer-a-gating.sh ..."
     ./scripts/verify-startu-layer-a-gating.sh

3) Run on clean 0045 tree (0046 tests not required yet for shell asserts — should mostly pass post-27b)

Do NOT modify vscode-main production files. Do NOT add 0046 to series yet.
```

**Verification commands**
```bash
cd "$(git rev-parse --show-toplevel)"
bash -n scripts/verify-startu-layer-a-gating.sh && echo "OK: bash -n"
./scripts/verify-startu-layer-a-gating.sh && echo "OK: SC-META shell on 0045 tree"
rg "verify-startu-layer-a-gating" scripts/ci-verify-docen.sh
```

---

## 3. Tasks 28-013 – 28-016 — Core unit tests (`0046` prep)

```
[TASK 28-013–016] Add Layer A contract unit tests in vscode-main (UNSTAGED)

Implement Tasks 28-013 through 28-016 from docs/PHASE_28_* Group C.

1) contrib/chatbot/test/browser/startuLayerAContract.test.ts (NEW)
   - Import STARTU_AI_MODE, STARTU_SCHOLAR_SUMMARIZER_PATH, STARTU_FORBIDDEN_AI_PATHS from startuScholarSummarizer / startuAiConfiguration
   - assert SCHOLAR_ONLY mode
   - assert summarizer path contains /ai/scholar/summarizer
   - assert forbidden paths include /ai/general/ and /ai/multi-task/
   - ensureNoDisposablesAreLeakedInTestSuite

2) services/startuAi/test/common/startuScholarPaths.test.ts (NEW)
   - Same constants — focused path contract tests

3) contrib/chatbot/test/browser/chatbotOpenChatRouting.test.ts (NEW)
   - Mock IChatbotService — verify OpenChatGlobalAction path (no mode) calls openChatbot
   - Reference chatActions.ts pattern from #25 (#41 patch)
   - SC-META-003

4) contrib/chat/test/browser/startuSettingsRouting.test.ts (NEW)
   - Mock IStartuSettingsService / ICommandService
   - Verify Chat "Open Settings" action uses startuSettings.open — NOT preferencesService.openSettings({ query: '@feature:chat' })
   - SC-META-004

All new .ts: IRETBL GROUP header.

Keep UNSTAGED. Do NOT modify browser/*.ts production files.
```

**Verification commands**
```bash
cd "$(git rev-parse --show-toplevel)/vscode-main"
test -f src/vs/workbench/contrib/chatbot/test/browser/startuLayerAContract.test.ts
test -f src/vs/workbench/services/startuAi/test/common/startuScholarPaths.test.ts
test -f src/vs/workbench/contrib/chatbot/test/browser/chatbotOpenChatRouting.test.ts
test -f src/vs/workbench/contrib/chat/test/browser/startuSettingsRouting.test.ts
! git diff --name-only | rg "^src/vs/workbench/contrib/chatbot/browser/[^/]+\.ts$" | rg -v test && echo "OK: no chatbot prod edits" || echo "WARN: prod files touched"
! git diff --name-only | rg "SubscribePage|auth-chatbot-chat" && echo "FAIL" || echo "OK"
```

---

## 4. Tasks 28-017 – 28-022 — Optional test extensions + compile gate

```
[TASK 28-017–022] Optional test extensions; compile; regression; scope lock

Implement Tasks 28-017 through 28-022 from docs/PHASE_28_* Group C.

Optional (if quick win):
- Extend chatbotChatService.test.ts — gate prevents gateway when not authenticated
- Extend startuChatPlatformGate.test.ts — waitForAuthReady + isAuthenticated cases

Run existing Layer A unit tests — all must pass (design §6 list).

From vscode-main:
  PATH="${NVM_NODE22:-$HOME/.nvm/versions/node/v22.22.1/bin}:$PATH" npm run compile

HARD BAN: Do NOT run full ci-verify-docen.sh on dirty tree yet.

Scope lock (28-022):
  git diff --name-only should be ONLY **/test/** paths (and maybe common export — footnote in PR if any)

Do NOT export 0046 yet.
```

**Verification commands**
```bash
cd "$(git rev-parse --show-toplevel)/vscode-main"
PATH="${NVM_NODE22:-$HOME/.nvm/versions/node/v22.22.1/bin}:$PATH" npm run compile 2>&1 | tail -25
git diff --name-only | head -20
git diff --name-only | rg "test/" && echo "OK: test-only diff expected"
```

---

## 5. Tasks 28-023 – 28-028 — Export `0046` + pipeline + docs links

```
[TASK 28-023–028] Export 0046 patch, series, pipeline, update plan links

Implement Tasks 28-023 through 28-028 from docs/PHASE_28_* Group D.

Before export: ensure patch hunks use LF (not CRLF).

From parent repo — create-patch.sh test paths only:
  git -C vscode-main diff --name-only
  ./scripts/create-patch.sh $(git -C vscode-main diff --name-only | tr '\n' ' ')

  mv patches/<generated>.patch patches/0046-startu-chatbot-gating-tests.patch
  Append after 0045 in patches/series.post-transform
  Update transforms/pipeline.json for 0046
  Update docs/PATCH_DEVELOPMENT_PLAN.md #28 row with AI_PROMPT_PHASE_28.md link
  Update docs/PATCH_DEVELOPMENT_PLAN_TASKS.md #28 row

git apply --check against tree through 0045:
  git -C vscode-main checkout -f "$(grep -v '^\s*#' config/UPSTREAM_BASELINE | head -1 | tr -d '[:space:]')"
  git -C vscode-main clean -fd
  python3 scripts/apply-pipeline.py --until-patch-before 0046-startu-chatbot-gating-tests.patch
  git -C vscode-main apply --check ../patches/0046-startu-chatbot-gating-tests.patch

Re-run full ci-verify (now includes verify-startu-layer-a-gating.sh on 0046 tree):
  DOCEN_SKIP_SUBMODULE_INIT=1 DOCEN_FORCE_SUBMODULE_HTTPS=1 ./scripts/ci-verify-docen.sh
```

**Verification commands**
```bash
cd "$(git rev-parse --show-toplevel)"
test -f patches/0046-startu-chatbot-gating-tests.patch && echo "OK: patch"
grep 0046 patches/series.post-transform
python3 -m json.tool transforms/pipeline.json >/dev/null
DOCEN_SKIP_SUBMODULE_INIT=1 DOCEN_FORCE_SUBMODULE_HTTPS=1 ./scripts/ci-verify-docen.sh
! rg "SubscribePage|auth-chatbot-chat|/ai/general/" patches/0046*.patch && echo "OK: 0046 scope"
rg "startuLayerAContract|chatbotOpenChatRouting|startuSettingsRouting|startuScholarPaths" patches/0046*.patch | head -8
```

---

## 6. Tasks 28-029 – 28-038 — Manual SC-META + user journey J1–J9

```
[TASK 28-029–038] Manual hand-test SC-META + J1–J9; sign checklist

Prerequisite: §5 ci-verify green on 0046 tree; npm run compile passed.

Use docs/reference/LAYER_A_SC_META_CHECKLIST.md — fill Pass/Fail for each item.

Execute design §5 / checklist:
- J1/J2 (002): login Webview + session persist after restart
- J3 (002/003): unsigned — chatbot/inline/setup blocked or CTA (record 硬阻断 vs 软 CTA)
- J4 (003): Open Chat → Startu Chat view
- J5 (003): Network POST …/ai/scholar/summarizer only; no general/multi-task
- J6 (004): Upgrade → external browser pricing (NOT Subscribe Webview)
- J7 (004): Startu Settings Activity Bar; Chat Open Settings → Startu Settings; Ctrl+, → Preferences
- J8 (003): chat.triggerSetup → Startu login (no Copilot install wizard)
- J9 (001): cannot install GitHub Copilot extension

Optional (28-038): after local compile, bundle spot-check design §4.5 on workbench.desktop.main.js

Document results in PR description + checklist sign-off lines.

Do NOT start Phase #29 unless all SC-META pass or N/A footnoted.
```

**Verification commands**
```bash
cd "$(git rev-parse --show-toplevel)"
# Human — verify checklist file has Pass marks for SC-META-001–004 and J1–J9
grep -c "\[x\]" docs/reference/LAYER_A_SC_META_CHECKLIST.md || grep "Pass" docs/reference/LAYER_A_SC_META_CHECKLIST.md
```

---

## 7. Task 28-T — Definition of Done + #29 开栈

```
[TASK 28-T] Phase 28 wrap-up; Layer A complete; #29 may start

Cross-check docs/PHASE_28_STARTU_CHATBOT_GATING_TESTS_TASKS_BY_FILE.md (28-001–048) and design §7:

1. Full pipeline:
   DOCEN_SKIP_SUBMODULE_INIT=1 DOCEN_FORCE_SUBMODULE_HTTPS=1 ./scripts/ci-verify-docen.sh
   (includes verify-startu-layer-a-gating.sh)

2. Compile:
   cd vscode-main && PATH="$NODE22/bin:$PATH" npm run compile

3. SC-META:
   ./scripts/verify-startu-layer-a-gating.sh — all sections pass
   Unit tests 28-013–016 (and optional 17–18) pass

4. Manual:
   LAYER_A_SC_META_CHECKLIST.md signed (J1–J9 + SC-META-001–004)

5. Scope audit (28-043):
   0046 patch contains ONLY test/** (+ minimal export if any)
   ! rg "SubscribePage|auth-chatbot-chat|gatewayClient.ts|chatbotAgent.ts" patches/0046*.patch

6. Docs (when I ask to commit):
   - Mark PHASE_28 tasks [x]
   - Footnote #19–#27a task docs: "#28 SC-META passed"
   - PATCH_DEVELOPMENT_PLAN user journey "手测写清" → 已验收

Output completion report:
- SC-META-001–004 pass summary
- Files in 0046 + parent scripts
- ci-verify + compile status
- Manual test notes (especially J3 mode, J5 network URL)
- Explicit: Layer A COMPLETE — #29 Layer B MAY start after maintainer sign-off (28-046)

Do NOT start Phase #29 unless I explicitly ask.
```

**Verification commands**
```bash
cd "$(git rev-parse --show-toplevel)"
DOCEN_SKIP_SUBMODULE_INIT=1 DOCEN_FORCE_SUBMODULE_HTTPS=1 ./scripts/ci-verify-docen.sh
./scripts/verify-startu-layer-a-gating.sh
cd vscode-main && PATH="${NVM_NODE22:-$HOME/.nvm/versions/node/v22.22.1/bin}:$PATH" npm run compile 2>&1 | tail -3
! rg "SubscribePage|auth-chatbot-chat" patches/0046*.patch -i
test -f scripts/verify-startu-layer-a-gating.sh && echo "OK: gating script shipped"
```

---

## Appendix A — Recommended execution order

| Step | Prompt | Tasks | Notes |
|------|--------|-------|-------|
| 0 | Session bootstrap | — | Once |
| 1 | §1 | 28-prep | **ci-verify through 0045 → `git add -A` freeze** |
| 2 | §2 | 28-006–012 | **Parent `verify-startu-layer-a-gating.sh` + ci-verify hook** |
| 3 | §3 | 28-013–016 | **Core unit tests (UNSTAGED)** |
| 4 | §4 | 28-017–022 | **Optional extensions + compile** |
| 5 | §5 | 28-023–028 | Export **0046** + pipeline → **full ci-verify** |
| 6 | §6 | 28-029–038 | **Manual SC-META + J1–J9 checklist** |
| 7 | §7 | 28-T | DoD + **#29 开栈批准** |

**双仓库交付：** §2 改 **父仓库 `scripts/`**；§3–§5 改 **`vscode-main` test/** → **`0046` patch**；同 PR 一起 review。

**Node PATH (Windows NVM example):** `PATH="/d/Program Files/nvm/v22.22.1/bin:$PATH"`

---

## Appendix B — Fix prompt template

```
Phase 28 task 28-{XX} verification failed.

Failed command output:
<paste output>

Fix ONLY within 28-{XX} scope per docs/PHASE_28_STARTU_CHATBOT_GATING_TESTS_TASKS_BY_FILE.md.
Do NOT modify production browser/*.ts — send product bugs to #27b/0045.
Do NOT start Phase #29. Do NOT add Layer B or Playwright E2E.
Do NOT add general/multi-task HTTP or auth-chatbot-chat LM path.
Re-run this step's verification commands only.
```

---

## Appendix C — Single-session continuous prompt（高级）

```
Follow docs/AI_PROMPT_PHASE_28.md Appendix A order (steps 0–7).
After each step:
1. Run that step's verification commands
2. Briefly list changed files (parent vs vscode-main)
3. Continue to the next step automatically

Global constraints match Session Bootstrap (Phase 28).
Finish with Task 28-T including SC-META manual checklist sign-off notes.
Do NOT start Phase #29.
```

---

## Appendix D — 与相邻 Phase 对照（勿粘贴进 Agent）

| 能力 | Phase 27b | Phase 28 | Phase 29+ |
|------|-----------|----------|-----------|
| 修产品代码 / parity | **#27b `0045`** | **禁止** | Layer B 新功能 |
| Cursor 金标 §0 回补 | **#27b** | — | — |
| CI shell SC-META grep | — | **#28** | — |
| Workbench 契约单测 | 零散已有 | **`0046` 新增** | — |
| 手测 J1–J9 | 部分在 27b | **#28 签字** | — |
| Playwright E2E | **禁止** | **N/A(28)** | 可后续 Phase |
| Layer B Agent/MCP | **禁止** | **禁止** | **#29+** |

| SC-META | 验证层 |
|---------|--------|
| **001** L0 copilot ban | `verify-startu-layer-a-gating.sh` + J9 手测 |
| **002** Auth 平行栈 | shell + 单测 + J1–J3 |
| **003** Chatbot + scholar HTTP | shell + 单测 + J4–J5–J8 手测 |
| **004** Settings + pricing | shell + 单测 + J6–J7 手测 |

**维护：** 本节随 **`PHASE_28_*`** 更新；Phase 27b 入口 **[`AI_PROMPT_PHASE_27B.md`](./AI_PROMPT_PHASE_27B.md)** · Layer B 待 **`AI_PROMPT_PHASE_29.md`**（未建）。
