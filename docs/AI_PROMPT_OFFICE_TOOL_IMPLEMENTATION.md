# Office Tool 架构重组（M0–M7）— AI Prompt Sequence

将下方 prompt **按顺序**复制到 AI 会话（Cursor Agent 等）。**一次只跑一个 Task 或一个 Batch**；执行该步 **Verification** 通过后再进入下一步。

**设计真源：** [`implementation_design.md`](./implementation_design.md)（全局 How、Release Gate §2.2、Registry §5.2、工具表 §12）  
**按文件任务：** [`OFFICE_TOOL_IMPLEMENTATION_TASKS_BY_FILE.md`](./OFFICE_TOOL_IMPLEMENTATION_TASKS_BY_FILE.md)（**OT-001 … OT-141**）  
**架构 Why/What：** [`OFFICE_TOOL_ARCHITECTURE_REORG.md`](./OFFICE_TOOL_ARCHITECTURE_REORG.md)（概念层；API 细节以 implementation_design §4 为准）  
**已采纳决策：** [`ADR.md`](./ADR.md)（ADR-001～030）  
**Legacy 迁移：** [`LEGACY_TOOL_MIGRATION.md`](./LEGACY_TOOL_MIGRATION.md)  
**Agent 执行序：** [`AI_PROMPT_OFFICE_TOOL_IMPLEMENTATION.md`](./AI_PROMPT_OFFICE_TOOL_IMPLEMENTATION.md)

> **勿**以 [`docs/archive/`](./archive/README.md) 为 Office Tool 实施真源（仅历史/格式参考）。

**垂直实现设计（按里程碑打开）：**

| 里程碑 | 文档 |
|--------|------|
| M2 Word W0–W3 | [`OFFICE_MCP_WORD_IMPLEMENTATION_DESIGN.md`](./OFFICE_MCP_WORD_IMPLEMENTATION_DESIGN.md) |
| M4 Presentation | [`OFFICE_MCP_PRESENTATION_IMPLEMENTATION_DESIGN.md`](./OFFICE_MCP_PRESENTATION_IMPLEMENTATION_DESIGN.md) |
| M5 Spreadsheet | [`OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_DESIGN.md`](./OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_DESIGN.md) |
| M6 PDF | [`OFFICE_MCP_PDF_IMPLEMENTATION_DESIGN.md`](./OFFICE_MCP_PDF_IMPLEMENTATION_DESIGN.md) |

**当前代码基线（M0 前）：**

- `aiecs/tools/office_tool/`：**14 个扁平 `.py`**，无 `core/`、`word/`、`registry.py`
- MCP：**6 工具**，`office_tool_adapter.py` 硬编码
- `tests/office_mcp/`：**扁平** `test_office_*.py`

**Registry 递增（勿在 M3 断言 23/27）：**

| 里程碑 | `collect_office_tools()` | `get_handlers()` |
|--------|--------------------------|------------------|
| **M3** | **8** | **12** |
| M4 | 13 | 17 |
| M5 | 18 | 22 |
| **M6** | **23** | **27** |

**真源优先级：** ADR（已采纳）→ implementation_design → tasks by file → ARCHITECTURE_REORG

---

## 0. Session Bootstrap Prompt（仅首次）

```
You are implementing Office Tool architecture reorg — milestones M0 through M7 (OT-001–OT-141).

Required reading (Office-Tool repo):
- docs/implementation_design.md (§2 Release Gates, §4 Core API, §5 Registry, §6 Read, §9 M0–M7 checklist)
- docs/OFFICE_TOOL_IMPLEMENTATION_TASKS_BY_FILE.md (full task list + OT-NA bans)
- docs/ADR.md — Accepted ADRs only (especially ADR-006, 009, 021–030)
- docs/LEGACY_TOOL_MIGRATION.md
- docs/OFFICE_TOOL_ARCHITECTURE_REORG.md (directory tree + dependency rules)
- Vertical design doc for current milestone (Word / Presentation / Spreadsheet / PDF)

Global constraints:
1. One prompt = one task OR one batch as defined in docs/AI_PROMPT_OFFICE_TOOL_IMPLEMENTATION.md.
2. Do NOT git commit unless I explicitly ask.
3. Surgical changes only — match existing style; no speculative refactors.
4. core/ MUST NOT import word|presentation|spreadsheet|pdf|legacy (grep audit each gate).
5. Vertical modules MUST NOT cross-import each other.
6. ADR-029: After M3 merges, core/ is FROZEN (bugfix-only PRs).
7. ADR-024: list_tools = canonical only; legacy names call_tool only (27 handlers at M6).
8. ADR-025: [Word]/[Presentation]/[Spreadsheet]/[PDF]/[Gateway] prefixes on exposed tools; NO [Legacy] prefix.
9. test_registry.py: assert INCREMENTAL counts per milestone (M3=8/12, NOT 23/27).
10. office_read_document behavior FROZEN (§11.2 / OT-NA-05) — no transparent fine-read forwarding.
11. Shim files (ADR-022): keep root re-exports through M7; do NOT delete shims in M7.
12. Do NOT modify aiecs/clients/documentserver_client.py API surface (OT-141).
13. Do NOT implement OT-NA-* items (see tasks doc Group K).
14. pyproject.toml uses --strict-markers: register category markers BEFORE use (word=M1 OT-045c; presentation=M4; spreadsheet=M5; pdf=M6).
15. Do NOT use docs/archive/ as implementation source (format reference only).

Precondition check before coding:
- poetry run pytest tests/office_mcp/ -v -m "not e2e" — must pass on current tree
- test -d aiecs/tools/office_tool && ls aiecs/tools/office_tool/*.py | wc -l
- ! test -f aiecs/tools/office_tool/registry.py && echo "OK: no registry yet"
- Read tasks doc "当前树核对摘要" and confirm alignment

After confirming you read the design docs, reply "Ready for OT-prep" — do not write code yet.
```

---

## 1. Task OT-prep — Baseline inventory + scope lock

```
[TASK OT-prep] Baseline inventory; confirm pre-M0 tree; lock scope

Prerequisite: flat office_tool unit tests green.

From repo root:
1. Run baseline unit tests (no e2e):
   poetry run pytest tests/office_mcp/ -v -m "not e2e"

2. Inventory current office_tool (document only):
   - List all .py under aiecs/tools/office_tool/
   - Confirm adapter hardcodes 6 tools in aiecs/mcp/office_tool_adapter.py
   - Confirm no core/, word/, registry.py

3. Lock scope for M0:
   - ONLY core/builder_js.py + core/builder_runtime.py + root file rewires (OT-013–022)
   - Do NOT start M1 core migration yet
   - Do NOT create registry.py yet

4. Mark in your notes which OT tasks are already [x] in tasks doc (if any).

Do NOT edit production code in this step except documenting baseline.
```

**Verification commands**
```bash
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
poetry run pytest tests/office_mcp/ -v -m "not e2e"
test -d aiecs/tools/office_tool
! test -f aiecs/tools/office_tool/registry.py && echo "OK: pre-M3 tree"
rg "OFFICE_TOOLS|_TOOL_HANDLERS" aiecs/mcp/office_tool_adapter.py | head -5
ls aiecs/tools/office_tool/*.py | wc -l
```

---

## 2. Group A — OT-001 – OT-012（设计文档 · 只读）

```
[TASK OT-001–012] Read design docs; do NOT implement code in this step

Tasks OT-001 through OT-012 from docs/OFFICE_TOOL_IMPLEMENTATION_TASKS_BY_FILE.md Group A.

Action:
- Read implementation_design, ARCHITECTURE_REORG, ADR, four UPGRADE + IMPLEMENTATION_DESIGN docs, LLM guides, LEGACY_TOOL_MIGRATION
- These are authoritative during M0–M6; code changes reference them, do not rewrite them unless I ask
- OT-001–012 checkbox [x] for docs happens at M7 (OT-127–130) when code matches design

Output: 5-bullet summary of Registry rules (ADR-024/026), core freeze (ADR-029), and current milestone you will implement next.

Do NOT write Python in this step.
```

**Verification commands**
```bash
test -f docs/implementation_design.md && test -f docs/OFFICE_TOOL_IMPLEMENTATION_TASKS_BY_FILE.md
test -f docs/OFFICE_MCP_WORD_IMPLEMENTATION_DESIGN.md
grep -q "M3.*8.*12" docs/OFFICE_TOOL_IMPLEMENTATION_TASKS_BY_FILE.md && echo "OK: incremental registry table"
```

---

## 3. Batch T-OT-M0 — Tasks OT-013 – OT-022（Core Builder Runtime · Gate G0 部分）

```
[TASK OT-013–022] M0 — core/builder_runtime + builder_js; root files call runtime

Implement Tasks OT-013 through OT-022 from docs/OFFICE_TOOL_IMPLEMENTATION_TASKS_BY_FILE.md Group B.

1) aiecs/tools/office_tool/core/__init__.py (NEW)
2) core/builder_js.py (NEW): escape_js, open_file, save_file, close_file, wrap_script (implementation_design §4.2)
3) core/builder_runtime.py (NEW): run_builder_script, run_builder_on_source (§4.3, ADR-006 err/ok shape)
4) Rewire WITHOUT schema/name changes:
   - edit_document.py → run_builder_on_source
   - merge_document.py, apply_template.py, execute_builder.py → run_builder_script
5) tests/office_mcp/core/test_builder_runtime.py (NEW): mock DS + storage
6) OT-021 regression: all flat unit tests still green
7) OT-022: read_document.py / call_api.py UNCHANGED in M0

BAN:
- Do NOT create categories.py, errors.py, registry.py
- Do NOT change MCP tool schemas or handler signatures visible to clients

After implementation, mark OT-013–022 [x] in tasks doc when I ask to commit.
```

**Verification commands**
```bash
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
test -f aiecs/tools/office_tool/core/builder_runtime.py
test -f aiecs/tools/office_tool/core/builder_js.py
poetry run pytest tests/office_mcp/core/ -v
poetry run pytest tests/office_mcp/ -v -m "not e2e"
rg "run_builder_script|run_builder_on_source" aiecs/tools/office_tool/edit_document.py aiecs/tools/office_tool/merge_document.py
! test -f aiecs/tools/office_tool/registry.py && echo "OK: no registry in M0"
```

---

## 4. Batch T-OT-M1 — Tasks OT-023 – OT-045c（Core 迁移 · Gate G0 完整）

```
[TASK OT-023–045c] M1 — core migration, shims, errors, read_response, coarse_read, legacy read, word marker

Implement Tasks OT-023 through OT-045, OT-045b, and OT-045c from docs/OFFICE_TOOL_IMPLEMENTATION_TASKS_BY_FILE.md Group C.

Follow implementation_design §4 and §9 M1 checklist:

Core NEW:
- categories.py (from conversion_output; §4.1)
- errors.py (err/ok, ADR-006)
- read_response.py (build_read_response, ADR-028) — BLOCKING same PR as errors
- builder_json_sidecar.py, coarse_read.py, source.py, docbuilder_script.py
- core/storage/{paths,backend,object_fetch,__init__}.py

Shims (ADR-022 keep through M7):
- conversion_output.py, source_resolver.py, storage*.py, docbuilder_script.py, read_document.py

Legacy:
- legacy/read_document.py — behavior FROZEN (§11.2); coarse_read_legacy only

Tests NEW:
- tests/office_mcp/core/test_categories.py, test_read_response.py, test_storage.py
- Update test_office_read_document*.py imports

OT-045b skeleton (ADR-021):
- tests/office_mcp/conftest.py — e2e skip when no DOCUMENTSERVER_URL
- tests/office_mcp/probe_ds_capabilities.py — stub/skeleton (full logic M7 OT-133)

OT-045c (strict-markers — REQUIRED before M2 E2E):
- pyproject.toml: add marker `word: word category tools` under [tool.pytest.ini_options] markers

BAN:
- Do NOT create word/ vertical yet
- Do NOT create registry.py
- Do NOT transparently forward office_read_document to fine read (OT-NA-05)

Gate G0: poetry run pytest tests/office_mcp/ -v -m "not e2e" all green.
```

**Verification commands**
```bash
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
test -f aiecs/tools/office_tool/core/errors.py
test -f aiecs/tools/office_tool/core/read_response.py
test -f aiecs/tools/office_tool/legacy/read_document.py
poetry run pytest tests/office_mcp/core/ -v
poetry run pytest tests/office_mcp/ -v -m "not e2e"
! rg "from aiecs.tools.office_tool.word|presentation|spreadsheet|pdf" aiecs/tools/office_tool/core/ && echo "OK: core no vertical imports"
test -f tests/office_mcp/conftest.py && echo "OK: conftest skeleton"
rg "word: word category tools" pyproject.toml && echo "OK: word marker registered (OT-045c)"
```

---

## 5. Batch T-OT-M2 — Tasks OT-046 – OT-067（Word W0–W3 · Gate G1 部分）

```
[TASK OT-046–067] M2 — Word vertical W0–W3

Implement Tasks OT-046 through OT-067 from docs/OFFICE_TOOL_IMPLEMENTATION_TASKS_BY_FILE.md Group D.

Authoritative detail: docs/OFFICE_MCP_WORD_IMPLEMENTATION_DESIGN.md (W0–W3, PR-M0..M3 word scope).

W0: word/ tree; html_parser → word/parser/html.py + shim
W1: parser/document.py, office_read_word, tests word/read
W2: schemas, create/edit tools + E2E
W3: merge/template/edit_script, legacy/edit_document|merge_documents|apply_template aliases, root shims

Each tool module exports: TOOL_NAME, TOOL_DEF, handler
All handlers use core/errors err/ok; read uses build_read_response

BAN (Word):
- No relative_index (OT-NA-06 / ADR-011)
- Do NOT register tools in registry yet (M3)
- Do NOT move tests to tests/office_mcp/word/ yet (M3 ADR-023) — optional early move only if tasks say so

Sub-gates:
- OT-066 W0: directory only, no behavior change
- OT-067: word E2E with @pytest.mark.word @pytest.mark.e2e (requires OT-045c word marker from M1)

Verify: unit green; word E2E if DS available.
```

**Verification commands**
```bash
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
test -f aiecs/tools/office_tool/word/tools/read.py
test -f aiecs/tools/office_tool/word/tools/create.py
test -f aiecs/tools/office_tool/legacy/edit_document.py
poetry run pytest tests/office_mcp/ -v -m "not e2e"
poetry run pytest tests/office_mcp/ -v -m "word and e2e" 2>/dev/null || echo "SKIP: no DS for e2e"
! test -f aiecs/tools/office_tool/registry.py && echo "OK: registry still M3"
```

---

## 6. Batch T-OT-M3 — Tasks OT-068 – OT-082（Registry · Gate G1 完整）

```
[TASK OT-068–082] M3 — registry.py, adapter slim, gateway/, test move, health incremental

Implement Tasks OT-068 through OT-082 from docs/OFFICE_TOOL_IMPLEMENTATION_TASKS_BY_FILE.md Group E.

1) registry.py (NEW):
   - collect_office_tools() — gateway×2 + word×6 = 8 canonical
   - get_handlers() — 8 + legacy×4 = 12
   - Legacy NOT in collect_office_tools (ADR-024)

2) office_tool_adapter.py — import from registry; NO hardcoded OFFICE_TOOLS

3) gateway/execute_builder.py, gateway/call_api.py — move from root + shims (OT-070–072)

4) [Word] + [Gateway] description prefixes (ADR-025)

5) tests/office_mcp/test_registry.py — assert M3: len(collect)==8, len(handlers)==12
   FORBIDDEN: assert == 23 or == 27 in M3 PR

6) Move word tests → tests/office_mcp/word/ (ADR-023)

7) main_mcp.py health: tool_count + canonical_count (M3=8); optional registered_handler_count=12 (ADR-026)

8) LEGACY_TOOL_MIGRATION.md + CHANGELOG entries (legacy hidden from list_tools)

9) ADR-029: core/ freeze begins after this PR merges

10) OT-138 subset (THIS milestone): update test_office_tool_adapter, test_integration,
    test_openai_format, test_fastmcp_integration — assert 8 canonical tools, no legacy in list_tools

Gate G1 complete.
```

**Verification commands**
```bash
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
test -f aiecs/tools/office_tool/registry.py
poetry run pytest tests/office_mcp/test_registry.py -v
poetry run pytest tests/office_mcp/ -v -m "not e2e"
python3 -c "
from aiecs.tools.office_tool.registry import collect_office_tools, get_handlers
assert len(collect_office_tools()) == 8, len(collect_office_tools())
assert len(get_handlers()) == 12, len(get_handlers())
print('OK: M3 registry 8/12')
"
! rg "OFFICE_TOOLS\s*=" aiecs/mcp/office_tool_adapter.py && echo "OK: adapter not hardcoded"
rg "canonical_count|tool_count" aiecs/main_mcp.py | head -3
poetry run pytest tests/office_mcp/test_office_tool_adapter.py tests/office_mcp/test_integration.py -v -m "not e2e" 2>/dev/null || true
```

---

## 7. Batch T-OT-M4 — Tasks OT-083 – OT-099（Presentation · Gate G2）

```
[TASK OT-083–099] M4 — presentation/ five tools + registry increment

Prerequisite: M3 merged (Gate G1 passed).

Implement Tasks OT-083 through OT-099 from docs/OFFICE_TOOL_IMPLEMENTATION_TASKS_BY_FILE.md Group F.

Authoritative: docs/OFFICE_MCP_PRESENTATION_IMPLEMENTATION_DESIGN.md (P0–P4).

Deliver:
- presentation/ full tree (parser, schemas, builder, tools)
- Five tools: read, create, edit, merge, template
- registry += 5 modules → canonical 13, handlers 17
- [Presentation] description prefixes
- pyproject.toml: register `presentation` marker (OT-092; strict-markers before M4 E2E)
- tests/office_mcp/presentation/* + E2E
- test_registry asserts M4: 13/17
- OT-138 subset: integration/openai tests assert 13 canonical

BAN:
- No presentation legacy aliases
- No layout fuzzy match (OT-NA-08 / ADR-016)
- Do NOT touch core/ except bugfix (ADR-029)

Gate G2: presentation E2E green (or skipped per ADR-021).
```

**Verification commands**
```bash
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
test -d aiecs/tools/office_tool/presentation/tools
poetry run pytest tests/office_mcp/presentation/ -v -m "not e2e"
python3 -c "
from aiecs.tools.office_tool.registry import collect_office_tools, get_handlers
assert len(collect_office_tools()) == 13
assert len(get_handlers()) == 17
print('OK: M4 registry 13/17')
"
poetry run pytest tests/office_mcp/ -v -m "presentation and e2e" 2>/dev/null || echo "SKIP: no DS"
rg "presentation: presentation category tools" pyproject.toml && echo "OK: presentation marker"
```

---

## 8. Batch T-OT-M5 — Tasks OT-100 – OT-112（Spreadsheet · Gate G3）

```
[TASK OT-100–112] M5 — spreadsheet/ five tools + registry increment

Prerequisite: M3 merged. (May run after M4 in parallel branch — one batch per session.)

Implement Tasks OT-100 through OT-112 from docs/OFFICE_TOOL_IMPLEMENTATION_TASKS_BY_FILE.md Group G.

Authoritative: docs/OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_DESIGN.md (S0–S4).

Deliver:
- spreadsheet/ full tree
- Five tools: read, create, edit, merge, template
- registry → canonical 18, handlers 22
- [Spreadsheet] prefixes
- pyproject.toml: register `spreadsheet` marker (OT-107)
- test_registry M5: 18/22
- OT-138 subset: integration/openai tests assert 18 canonical
- OT-111: GetSheetsCount skip via probe_ds_capabilities skeleton (OT-045b)

BAN:
- No row/col as primary schema (OT-NA-07 / ADR-015)
- Do NOT assert registry 23/27 yet

Gate G3.
```

**Verification commands**
```bash
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
test -d aiecs/tools/office_tool/spreadsheet/tools
poetry run pytest tests/office_mcp/spreadsheet/ -v -m "not e2e"
python3 -c "
from aiecs.tools.office_tool.registry import collect_office_tools, get_handlers
assert len(collect_office_tools()) == 18
assert len(get_handlers()) == 22
print('OK: M5 registry 18/22')
"
rg "spreadsheet: spreadsheet category tools" pyproject.toml && echo "OK: spreadsheet marker"
```

---

## 9. Batch T-OT-M6 — Tasks OT-113 – OT-126（PDF · Gate G4）

```
[TASK OT-113–126] M6 — pdf/ five tools; registry终态 23/27

Prerequisite: M3 merged.

Implement Tasks OT-113 through OT-126 from docs/OFFICE_TOOL_IMPLEMENTATION_TASKS_BY_FILE.md Group H.

Authoritative: docs/OFFICE_MCP_PDF_IMPLEMENTATION_DESIGN.md (P0–P5).

Deliver:
- pdf/ tree including tools/create.py, fill_form.py — NO office_apply_template_pdf (OT-NA-01)
- Five tools: read, create, edit, merge, fill_form
- registry → canonical 23, handlers 27 (FINAL)
- [PDF] prefixes
- pyproject.toml: register `pdf` marker (OT-123)
- test_registry M6: 23/27
- OT-138 subset: integration/openai tests assert 23 canonical (FINAL)
- ADR-017: no auto via_docx fallback on native create failure
- ADR-018: merge builder default; conversion engine explicit only
- ADR-019: fill_form SetValue only; no fill_form_field in edit (OT-NA-02)

Gate G4.
```

**Verification commands**
```bash
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
test -f aiecs/tools/office_tool/pdf/tools/fill_form.py
! test -f aiecs/tools/office_tool/pdf/tools/apply_template.py 2>/dev/null; true
poetry run pytest tests/office_mcp/pdf/ -v -m "not e2e"
python3 -c "
from aiecs.tools.office_tool.registry import collect_office_tools, get_handlers
assert len(collect_office_tools()) == 23
assert len(get_handlers()) == 27
print('OK: M6 registry 23/27')
"
poetry run pytest tests/office_mcp/ -v -m "pdf and e2e" 2>/dev/null || echo "SKIP: no DS"
rg "pdf: pdf category tools" pyproject.toml && echo "OK: pdf marker"
poetry run pytest tests/office_mcp/test_office_tool_adapter.py tests/office_mcp/test_openai_format.py -v -m "not e2e" 2>/dev/null || true
```

---

## 10. Batch T-OT-M7 — Tasks OT-127 – OT-136（文档收尾 · Gate G5）

```
[TASK OT-127–136] M7 — README, Plan, LLM guides, markers, probe, Gate G5

Implement Tasks OT-127 through OT-136 from docs/OFFICE_TOOL_IMPLEMENTATION_TASKS_BY_FILE.md Group I.

Deliver:
- README.md: 23 canonical tools; architecture tree; E2E commands
- Plan.md roadmap M0–M7 status
- Sync UPGRADE §8 + LLM guides (OT-129, OT-130)
- OT-131: legacy handlers call_tool only; NO [Legacy] description prefix
- OT-132: verify all four category markers in pyproject.toml (registered M1/M4/M5/M6); README E2E docs
- probe_ds_capabilities.py full implementation + docs (OT-133)
- OT-135: do NOT delete shims (ADR-022)
- health tool_count == canonical_count == 23; registered_handler_count == 27
- Mark OT-001–012 doc tasks [x] where design matches code

Gate G5: docs + health + registry终态一致.
```

**Verification commands**
```bash
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
rg "word:|presentation:|spreadsheet:|pdf:" pyproject.toml
test -f tests/office_mcp/probe_ds_capabilities.py
poetry run pytest tests/office_mcp/ -v -m "not e2e"
grep -q "23" README.md && echo "OK: README mentions 23 tools"
python3 -c "
from aiecs.tools.office_tool.registry import collect_office_tools, get_handlers
assert len(collect_office_tools()) == 23 and len(get_handlers()) == 27
"
```

---

## 11. Batch T-OT-TEST — Tasks OT-137 – OT-141（测试横切）

> **OT-138**：各 milestone PR（M3–M6）已执行子集；本 Batch 做 **终态复核** 与 CI/文档收尾。

```
[TASK OT-137–141] Cross-cutting tests + CI (finalize at M7; OT-138 ongoing since M3)

Implement Tasks OT-137 through OT-141 from docs/OFFICE_TOOL_IMPLEMENTATION_TASKS_BY_FILE.md Group J.

- OT-137: test_e2e_office_tools.py — smoke or split by category
- OT-138: FINAL verify test_openai_format.py / test_fastmcp_integration.py — 23 canonical (if not done at M6)
- OT-139: CI workflow markers if .github/workflows exist
- OT-140: document per-PR regression commands (implementation_design §10.4)
- OT-141: documentserver_client.py — NO API changes unless bugfix

Run full suite:
  poetry run pytest tests/office_mcp/ -v -m "not e2e"
  DOCUMENTSERVER_URL=... poetry run pytest tests/office_mcp/ -v -m e2e  # if DS available
```

**Verification commands**
```bash
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
poetry run pytest tests/office_mcp/ -v -m "not e2e"
# Dependency audit (G5 checklist):
! rg "office_tool\.(word|presentation|spreadsheet|pdf|legacy)" aiecs/tools/office_tool/core/ --glob "*.py" | rg -v "test" && echo "OK: core clean"
```

---

## 12. Task OT-T — Definition of Done（M0–M7 完成）

```
[TASK OT-T] Office Tool reorg wrap-up; M0–M7 complete

Cross-check docs/OFFICE_TOOL_IMPLEMENTATION_TASKS_BY_FILE.md (OT-001–OT-141) and implementation_design §2.2 Release Gates:

1. All gates:
   - G0: M0+M1 unit green
   - G1: M3 registry 8/12; word E2E; legacy call_tool works
   - G2–G4: presentation / spreadsheet / pdf E2E (or ADR-021 skip documented)
   - G5: health 23/23; docs aligned

2. Registry终态:
   len(collect_office_tools()) == 23
   len(get_handlers()) == 27
   list_tools has NO legacy names

3. Bans respected (Group K OT-NA-*)

4. office_read_document regression: pdf/pptx/xlsx/docx coarse behavior unchanged

5. Mark all completed tasks [x] in OFFICE_TOOL_IMPLEMENTATION_TASKS_BY_FILE.md when I ask to commit

Output completion report:
- Milestones merged (M0–M7)
- Registry counts per gate
- Test command results (unit + e2e status)
- Known skips (DS version, ADR-021)
- Files created (core/, word/, presentation/, spreadsheet/, pdf/, registry.py)

Do NOT delete shims unless I explicitly request a separate ADR-022 breaking PR.
```

**Verification commands**
```bash
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
poetry run pytest tests/office_mcp/ -v -m "not e2e"
python3 -c "
from aiecs.tools.office_tool.registry import collect_office_tools, get_handlers
c,h=len(collect_office_tools()),len(get_handlers())
assert (c,h)==(23,27), (c,h)
print('OK:终态 23/27')
"
test -f aiecs/tools/office_tool/core/builder_runtime.py
test -f aiecs/tools/office_tool/registry.py
test -d aiecs/tools/office_tool/word
test -d aiecs/tools/office_tool/presentation
test -d aiecs/tools/office_tool/spreadsheet
test -d aiecs/tools/office_tool/pdf
```

---

## Appendix A — Recommended execution order

| Step | Prompt | Tasks | Gate |
|------|--------|-------|------|
| 0 | Session bootstrap | — | — |
| 1 | §1 OT-prep | baseline | — |
| 2 | §2 | OT-001–012 | 只读 |
| 3 | §3 | OT-013–022 | G0 部分 |
| 4 | §4 | OT-023–045c | **G0** |
| 5 | §5 | OT-046–067 | G1 部分 |
| 6 | §6 | OT-068–082 + **OT-138@M3** | **G1** |
| 7 | §7 | OT-083–099 + **OT-138@M4** | **G2** |
| 8 | §8 | OT-100–112 + **OT-138@M5** | **G3** |
| 9 | §9 | OT-113–126 + **OT-138@M6** | **G4** |
| 10 | §10 | OT-127–136 | **G5** |
| 11 | §11 | OT-137–141 | 横切终复核 |
| 12 | §12 OT-T | DoD | 终验收 |

**顺序约束：** M0 → M1 → M2 → M3 **必须严格串行**。M4 / M5 / M6 可在 M3 后**分 PR 并行**，但 **一次会话只做一个 Batch**。

**单 PR 粒度：** 见 implementation_design §16 附录 A；Word 可 W0/W1/W2/W3 拆分；垂直模块可 P0/P1/… 拆分，但 **registry 计数与 OT-138 集成测试须在对应 milestone PR 同步更新**。

---

## Appendix B — Fix prompt template

```
Office Tool task OT-{XXX} verification failed.

Failed command output:
<paste output>

Fix ONLY within OT-{XXX} / batch T-OT-M{N} scope per docs/OFFICE_TOOL_IMPLEMENTATION_TASKS_BY_FILE.md.
Respect OT-NA bans (Group K).
Do NOT assert registry 23/27 before M6.
Do NOT modify core/ for feature work after M3 (ADR-029) — bugfix only.
Do NOT change office_read_document coarse behavior (OT-NA-05).
Re-run this step's verification commands only.
Do NOT git commit unless I explicitly ask.
```

---

## Appendix C — Single-session continuous prompt（高级）

```
Follow docs/AI_PROMPT_OFFICE_TOOL_IMPLEMENTATION.md Appendix A order (steps 0–12).
After each step:
1. Run that step's verification commands
2. List changed files under aiecs/tools/office_tool/ and tests/office_mcp/
3. Update task checkboxes [x] in OFFICE_TOOL_IMPLEMENTATION_TASKS_BY_FILE.md for completed OT IDs
4. Continue to the next step automatically ONLY if verification passed

Global constraints match Session Bootstrap (§0).
Stop before M4 if M3 gate fails (registry must be 8/12).
Finish with Task OT-T completion report.
Do NOT git commit unless I explicitly ask.
```

---

## Appendix D — OT-NA 速查（禁止项 · 勿粘贴进 Agent 除非踩雷）

| ID | 禁止 |
|----|------|
| OT-NA-01 | `office_apply_template_pdf` |
| OT-NA-02 | `edit_pdf.fill_form_field` |
| OT-NA-03 | PDF create auto via_docx fallback |
| OT-NA-04 | merge silent conversion fallback |
| OT-NA-05 | `office_read_document` → fine read 转发 |
| OT-NA-06 | Word `relative_index` |
| OT-NA-07 | Spreadsheet row/col 主推 |
| OT-NA-08 | Presentation layout fuzzy match |
| OT-NA-09 | M3 后 core/ feature PR |
| OT-NA-10 | OCR / PDF 签名 / 加密 |
| OT-NA-11 | M7 删 shim |
| OT-NA-12 | 从 list_tools 移除 legacy（breaking PR） |
| OT-NA-13 | `core/protocols.py` v1 |

**维护：** 本节随 `OFFICE_TOOL_IMPLEMENTATION_TASKS_BY_FILE.md` 更新；prompt 编排格式参考 [`archive/AI_PROMPT_PHASE_28_for_reference.md`](./archive/AI_PROMPT_PHASE_28_for_reference.md)（**非** Office Tool 范围真源）。
