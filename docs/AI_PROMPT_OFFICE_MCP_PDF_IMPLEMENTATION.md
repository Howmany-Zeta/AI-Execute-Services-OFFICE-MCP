# Office MCP PDF — UPGRADE 收尾 — AI Prompt Sequence

将下方 prompt **按顺序**复制到 AI 会话（Cursor Agent 等）。**一次只跑一个 Batch**；本文件 **仅覆盖未完成 Task**（PDF-037–PDF-046）。PDF-001–036 架构交付与 **PDF-DOC-04** 文档 as-built 已完成，**勿重复实现**。

**按文件任务（未完成）：** [`OFFICE_MCP_PDF_IMPLEMENTATION_TASKS_BY_FILE.md`](./OFFICE_MCP_PDF_IMPLEMENTATION_TASKS_BY_FILE.md) — Group G–H  
**PDF 实现设计：** [`OFFICE_MCP_PDF_IMPLEMENTATION_DESIGN.md`](./OFFICE_MCP_PDF_IMPLEMENTATION_DESIGN.md)  
**规格 / E2E 清单：** [`OFFICE_MCP_PDF_UPGRADE.md`](./OFFICE_MCP_PDF_UPGRADE.md) §6、§7.1  
**LLM 字段名：** [`OFFICE_MCP_PDF_LLM_GUIDE.md`](./OFFICE_MCP_PDF_LLM_GUIDE.md)（`page_index` / `block_index` + `create_mode` / `office_fill_pdf_form`）  
**E2E 参考：** [`tests/office_mcp/test_e2e_office_tools.py`](../tests/office_mcp/test_e2e_office_tools.py)、[`tests/env_test.py`](../tests/env_test.py)

**范围（必做）：**

| Batch | Tasks | 内容 |
|-------|-------|------|
| **G — E2E** | PDF-037 – PDF-044 | 替换 `test_e2e_pdf_tools.py` placeholder；Gate **P-E2E** |
| **H — GAP** | PDF-045 – PDF-046 | `page_size` builder emit；edit `TOOL_DEF` schema（可选 hygiene） |

**前置（已满足，仅核对）：**

- `pdf/` 五 canonical 工具已在 `registry.py`（M6 **23/27** 含 pdf×5）
- `poetry run pytest tests/office_mcp/pdf/ -v -m "not e2e"` 全绿（29 tests）
- **无** PDF legacy MCP 别名；**无** `office_apply_template_pdf`（PDF-NA-04）
- `tests/office_mcp/pdf/test_e2e_pdf_tools.py` 仍为 **placeholder skip**
- **PDF-DOC-04** ✅（DESIGN §14 / UPGRADE §7.1 / LLM §8 as-built 已同步）

**真源优先级：** ADR（已采纳 **ADR-017–021、030**）→ PDF IMPLEMENTATION_DESIGN §14 → **本 tasks 文档** → UPGRADE

---

## 0. Session Bootstrap Prompt（仅首次）

```
You are completing Office MCP PDF UPGRADE follow-up — tasks PDF-037 through PDF-046 ONLY.

DO NOT re-implement PDF-001–036 (pdf/ tree, registry, unit tests already done).
DO NOT re-do PDF-DOC-04 (DESIGN / UPGRADE / LLM §8 docs already synced).

Required reading:
- docs/OFFICE_MCP_PDF_IMPLEMENTATION_TASKS_BY_FILE.md (Group G–H ONLY)
- docs/OFFICE_MCP_PDF_IMPLEMENTATION_DESIGN.md (§5 schemas, §7 builder, §10 tests, §14 gap index)
- docs/OFFICE_MCP_PDF_UPGRADE.md (§6 E2E list, §7.1 status)
- docs/OFFICE_MCP_PDF_LLM_GUIDE.md
- docs/ADR.md — ADR-002, 006, 008, 009, 017–021, 024–025, 028–030
- tests/office_mcp/test_e2e_office_tools.py (_call_tool_via_mcp pattern)
- tests/office_mcp/pdf/fixtures/acroform_template.pdf (fill_form E2E)
- tests/office_mcp/pdf/fixtures/two_page_sample.pdf (optional merge source)
- tests/env_test.py (E2EConfig, .env.test)
- tests/office_mcp/probe_ds_capabilities.py (pdf_native_create, ADR-021)

Global constraints:
1. One prompt = one batch per docs/AI_PROMPT_OFFICE_MCP_PDF_IMPLEMENTATION.md Appendix A.
2. Do NOT git commit unless I explicitly ask.
3. Surgical changes — touch pdf/, tests/office_mcp/pdf/, and post-E2E doc lines in tasks/global OT only.
4. Do NOT modify core/ except ADR-029 bugfix (prefer zero core changes).
5. pdf/* MUST NOT import word|presentation|spreadsheet.
6. office_read_document: pdf→txt coarse behavior FROZEN (PDF-NA-01 / OT-NA-05) — no transparent fine forwarding.
7. Edit uses page_index / block_index from office_read_pdf fine — NOT office_read_document index.
8. Form filling: office_fill_pdf_form ONLY — NO fill_form_field in office_edit_pdf (ADR-030 / PDF-NA-02).
9. create_mode: default native; native failure → {isError} + hint via_docx — NO auto retry (ADR-017 / PDF-NA-03).
10. merge: builder default; options.engine=conversion explicit only — NO silent fallback (ADR-018 / PDF-NA-05).
11. No PDF legacy MCP aliases (ADR-024); NO office_apply_template_pdf (PDF-NA-04).
12. E2E: MCP HTTP tools/call via test_e2e_office_tools.py _call_tool_via_mcp; config from .env.test (E2E_SOURCE_PATH gs:// or s3:// prefix for outputs).
13. Native create E2E: skip when probe_ds_capabilities().pdf_native_create is false (ADR-021) — use pytest.skip with reason, NOT placeholder skip.
14. Do NOT leave unconditional pytest.skip("placeholder") or pytest.skip("run manually") in E2E test bodies after PDF-037+.
15. After each batch, mark completed PDF-* as [x] in OFFICE_MCP_PDF_IMPLEMENTATION_TASKS_BY_FILE.md.

Precondition check:
- poetry run pytest tests/office_mcp/pdf/ -v -m "not e2e"  # must pass
- test -f aiecs/tools/office_tool/pdf/tools/read.py
- test -f tests/office_mcp/pdf/test_e2e_pdf_tools.py
- rg "pytest.skip.*placeholder|run manually" tests/office_mcp/pdf/test_e2e_pdf_tools.py && echo "OK: placeholder still present (to replace)"

Reply "Ready for PDF-prep" — do not write code yet.
```

---

## 1. Task PDF-prep — 基线 + E2E 环境

```
[TASK PDF-prep] Baseline; confirm .env.test; inventory open tasks

1. poetry run pytest tests/office_mcp/pdf/ -v -m "not e2e"  # must pass (29 tests)

2. Read tests/env_test.py E2EConfig — document which vars are set:
   E2E_SOURCE_PATH / E2E_SOURCE_PATHS / E2E_MCP_URL / E2E_MCP_PUBLIC_URL /
   DOCUMENTSERVER_URL / DOCUMENTSERVER_JWT_SECRET
   Note: PDF E2E typically create *.pdf under E2E_SOURCE_PATH prefix (uuid paths).

3. Confirm test_e2e_office_tools.py has _call_tool_via_mcp — reuse for PDF E2E.

4. Read tests/office_mcp/pdf/fixtures/document_sidecar.json — form field name company_name for fill_form mock alignment.

5. List open tasks PDF-037–046 from docs/OFFICE_MCP_PDF_IMPLEMENTATION_TASKS_BY_FILE.md Group G–H.

6. Read existing test_e2e_pdf_tools.py _pdf_native_available() — reuse ADR-021 probe pattern.

Do NOT implement E2E yet.
```

**Verification commands**
```bash
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
poetry run pytest tests/office_mcp/pdf/ -v -m "not e2e"
test -f .env.test && echo "OK: .env.test exists" || echo "WARN: no .env.test — E2E needs local config"
rg "placeholder|run manually" tests/office_mcp/pdf/test_e2e_pdf_tools.py
rg "_call_tool_via_mcp" tests/office_mcp/test_e2e_office_tools.py | head -2
python3 -c "
from aiecs.tools.office_tool.registry import collect_office_tools
p={'office_read_pdf','office_create_pdf','office_edit_pdf','office_merge_pdfs','office_fill_pdf_form'}
assert p <= {t['name'] for t in collect_office_tools()}
print('OK: pdf×5 registered')
"
```

---

## 2. Batch T-PDF-E2E-A — Tasks PDF-037 – PDF-038（create/read + edit）

```
[TASK PDF-037–038] Implement real PDF E2E: create 2 pages → read fine + edit add_paragraph re-read

Implement PDF-037 and PDF-038 from docs/OFFICE_MCP_PDF_IMPLEMENTATION_TASKS_BY_FILE.md Group G.

File: tests/office_mcp/pdf/test_e2e_pdf_tools.py

Replace placeholder skip with real tests. Module docstring: required .env.test vars (E2E_SOURCE_PATH, E2E_MCP_URL, JWT, etc.).

PDF-037 — test_e2e_create_read_pdf_two_pages:
1. Remove unconditional pytest.skip("placeholder") / "run manually" from implemented tests.
2. office_create_pdf — 2 pages, each PageSpec with at least one paragraph block
   - output_path: unique under E2E_SOURCE_PATH prefix, ends with .pdf
   - options.create_mode: prefer via_docx if native probe false; else default native OK
3. office_read_pdf fine structured → assert page_count == 2 (or unit_count == 2)
4. assert pages[] / units[] mirror with page_index 0 and 1

PDF-038 — test_e2e_edit_pdf_add_paragraph:
5. office_edit_pdf on PDF from PDF-037 (or shared helper):
   - op: add_paragraph with page_index from prior read + text
6. office_read_pdf fine again → assert new paragraph text visible on target page
7. success alone NOT sufficient for PDF-038 [x]

Use _call_tool_via_mcp from test_e2e_office_tools.py.
Use unique output paths (uuid) under E2E bucket prefix.
Keep @pytest.mark.pdf @pytest.mark.e2e and documentserver_reachable skipif.

Mark PDF-037, PDF-038 [x] when done.
Do NOT git commit unless I ask.
```

**Verification commands**
```bash
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
poetry run pytest tests/office_mcp/pdf/test_e2e_pdf_tools.py -v -m "pdf and e2e" -k "create or edit" 2>&1 | tail -30
poetry run pytest tests/office_mcp/pdf/ -v -m "not e2e"
! rg "pytest.skip.*placeholder|run manually" tests/office_mcp/pdf/test_e2e_pdf_tools.py && echo "OK: no placeholder skip" || echo "FAIL"
```

---

## 3. Batch T-PDF-E2E-B — Tasks PDF-039 – PDF-041（merge + fill_form）

```
[TASK PDF-039–041] PDF E2E: merge builder, conversion explicit, fill_pdf_form

Implement PDF-039, PDF-040, PDF-041 from tasks doc Group G.

In tests/office_mcp/pdf/test_e2e_pdf_tools.py:

PDF-039 — test_e2e_merge_pdfs_builder:
- Two 1-page pdf sources (create two small pdfs in-test OR upload two_page_sample split / two creates)
- office_merge_pdfs with default engine (builder)
- **必须**：office_read_pdf fine on merged output → assert page_count == 2
- Assert merge handler success — success alone NOT sufficient for PDF-039 [x]

PDF-040 — test_e2e_merge_pdfs_conversion:
- Same or similar two sources
- office_merge_pdfs with options.engine=conversion
- Assert success OR documented {isError} with ADR-018 limitation note in test docstring
- Do NOT silently fall back from builder failure

PDF-041 — test_e2e_fill_pdf_form_acroform:
- Source: acroform_template.pdf uploaded to E2E storage OR preconfigured E2E path
  (field name company_name per fixtures/document_sidecar.json)
- office_fill_pdf_form data={"company_name": "Acme E2E PDF"}
- Assert handler success; **推荐** re-read fine include_form_fields and assert value

Reference UPGRADE §6 #3–5; DESIGN §10.3 #3–5.

Mark PDF-039–041 [x] when done.
```

**Verification commands**
```bash
poetry run pytest tests/office_mcp/pdf/test_e2e_pdf_tools.py -v -m "pdf and e2e" -k "merge or fill" 2>&1 | tail -40
rg "page_count|unit_count" tests/office_mcp/pdf/test_e2e_pdf_tools.py
poetry run pytest tests/office_mcp/pdf/ -v -m "not e2e"
```

---

## 4. Batch T-PDF-E2E-C — Tasks PDF-042 – PDF-043（create_mode native / via_docx）

```
[TASK PDF-042–043] PDF E2E: create_mode=native (probe-gated) + explicit via_docx

PDF-042 — test_e2e_create_pdf_native (ADR-021):
- Reuse _pdf_native_available() from module
- If not pdf_native_create: pytest.skip("PDF native API not available (ADR-021)") — OK
- If available: office_create_pdf 1 page, options.create_mode=native → read fine assert page_count >= 1
- Must NOT use placeholder skip when native IS available

PDF-043 — test_e2e_create_pdf_via_docx:
- office_create_pdf with options.create_mode=via_docx explicitly (1–2 pages)
- office_read_pdf fine → assert page_count matches
- **禁止**：测 native 失败后自动 via_docx（PDF-NA-03 / ADR-017）
- May run on any DS with JWT regardless of native probe

Reference DESIGN §10.3 #6; UPGRADE §6 #6.

Mark PDF-042, PDF-043 [x] when done.
```

**Verification commands**
```bash
poetry run pytest tests/office_mcp/pdf/test_e2e_pdf_tools.py -v -m "pdf and e2e" -k "native or via_docx" 2>&1 | tail -30
poetry run pytest tests/office_mcp/pdf/ -v -m "not e2e"
```

---

## 5. Task PDF-044 — Gate P-E2E + legacy read

```
[TASK PDF-044] Close Gate P-E2E + legacy office_read_document pdf coarse

1. PDF-037–043 all [x] in OFFICE_MCP_PDF_IMPLEMENTATION_TASKS_BY_FILE.md

2. Add test_e2e_read_document_pdf_coarse (UPGRADE §6 #7 / DESIGN §10.3 #7):
   - Use a pdf source (from prior create or E2E path)
   - office_read_document on pdf → assert txt/coarse elements path (legacy html_parser behavior)
   - Must NOT transparently return office_read_pdf fine pages[] structure
   - PDF-NA-01 frozen behavior

3. Update tasks doc bottom checklist: P-E2E line → [x]

4. Update IMPLEMENTATION_DESIGN §3.2 / §12 E2E rows → ✅

5. Update IMPLEMENTATION_DESIGN §14.2 **DS E2E 全清单** row → ✅（移除 placeholder skip 表述；仍 ⏳ 的行仅 **PDF-045** / **PDF-046**）

6. Update OFFICE_MCP_PDF_UPGRADE.md §7.1 **P-E2E** row → ✅

7. Update OFFICE_MCP_PDF_LLM_GUIDE.md §8（E2E 收口，**PDF-DOC-04 之后、PDF-044 必做**）:
   - 底部 **E2E（DS）** 行：⏳ → ✅ **PDF-037–044**（7 cases；无 placeholder skip）
   - 各工具 **收尾** 列：E2E 相关 ⏳ → ✅（read **PDF-037–038**；create **PDF-037、042–043**；edit **PDF-038**；merge **PDF-039–040**；fill **PDF-041**）
   - **仍 open 的 gap** 保留在收尾列：**PDF-045** `page_size`、**PDF-046** TOOL_DEF（直至 Group H 完成）

8. Update OFFICE_TOOL_IMPLEMENTATION_TASKS_BY_FILE.md OT-126 footnote: PDF DS E2E complete (PDF-044)

9. Module docstring in test_e2e_pdf_tools.py: required .env.test vars; no placeholder skip in test bodies

Verification: full pdf e2e suite without placeholder/manual skip in test bodies (module may skip if DS down or ADR-021 — OK).

Mark PDF-044 [x].
```

**Verification commands**
```bash
poetry run pytest tests/office_mcp/pdf/ -v -m "pdf and e2e"
grep "P-E2E" docs/OFFICE_MCP_PDF_IMPLEMENTATION_TASKS_BY_FILE.md | head -5
! rg "pytest.skip.*placeholder|run manually" tests/office_mcp/pdf/test_e2e_pdf_tools.py && echo "OK"
rg "PDF-037–044" docs/OFFICE_MCP_PDF_LLM_GUIDE.md docs/OFFICE_MCP_PDF_IMPLEMENTATION_DESIGN.md | head -6
```

---

## 6. Batch T-PDF-GAP — Task PDF-045（page_size）

```
[TASK PDF-045] Wire page_size A4/Letter into build_create_script

Implement PDF-045 from tasks doc Group H.

Files:
- aiecs/tools/office_tool/pdf/builder/create.py
- tests/office_mcp/pdf/test_create_pdf.py

Requirements:
- When options.page_size is "A4" or "Letter", emitted JS sets page dimensions per DS PDF/Word API
- Apply to both create_mode=native and create_mode=via_docx paths where applicable
- Unit test: mock run_builder_script; assert script body contains page size API for A4 and/or Letter

Do NOT change schema (already has page_size in page_spec.py and TOOL_DEF).

Mark PDF-045 [x].
```

**Verification commands**
```bash
poetry run pytest tests/office_mcp/pdf/test_create_pdf.py -v
rg "page_size" aiecs/tools/office_tool/pdf/builder/create.py
poetry run pytest tests/office_mcp/pdf/ -v -m "not e2e"
```

---

## 7. Batch T-PDF-GAP-B — Task PDF-046（edit TOOL_DEF，可选）

```
[TASK PDF-046] edit TOOL_DEF operations schema from edit_ops.py (optional hygiene)

Implement PDF-046 from tasks doc Group H.

File: aiecs/tools/office_tool/pdf/tools/edit.py

- Regenerate inputSchema.operations.items from EditOperation.model_json_schema() (ADR-002)
- op enum must list all 6 OpName values from schemas/edit_ops.py
- Must NOT include fill_form_field (ADR-030)

Tests: tests/office_mcp/pdf/test_schemas.py — verify op enum still rejects fill_form_field

Mark PDF-046 [x] when done (skip only if user explicitly defers optional task).
```

**Verification commands**
```bash
poetry run pytest tests/office_mcp/pdf/test_schemas.py tests/office_mcp/pdf/test_edit_pdf.py -v
python3 -c "
from aiecs.tools.office_tool.pdf.tools.edit import TOOL_DEF
from aiecs.tools.office_tool.pdf.schemas.edit_ops import OpName
props = TOOL_DEF['inputSchema']['properties']['operations']['items']['properties']
assert 'op' in props, list(props.keys())
enum = props['op'].get('enum') or props['op'].get('anyOf', [{}])[0].get('enum', [])
assert set(enum) == set(OpName.__args__), (enum, OpName.__args__)
print('OK: TOOL_DEF op enum')
"
```

---

## 8. Task PDF-T — Definition of Done

```
[TASK PDF-T] PDF UPGRADE wrap-up

Verify docs/OFFICE_MCP_PDF_IMPLEMENTATION_TASKS_BY_FILE.md Group G–H all [x] (PDF-046 optional: document if deferred).

1. Unit: poetry run pytest tests/office_mcp/pdf/ -v -m "not e2e"
2. E2E: poetry run pytest tests/office_mcp/pdf/ -v -m "pdf and e2e" (PASS or ADR-021/DS skip — no placeholder)
3. page_size in create builder (PDF-045)
4. edit TOOL_DEF hygiene (PDF-046) if implemented
5. **文档 as-built 复核**（若 PDF-044 已做但 GAP 刚完成，补全下列项）:
   - OFFICE_MCP_PDF_UPGRADE.md §7.1：P-E2E ✅；**PDF-045–046** 行随 gap 关闭 → ✅
   - OFFICE_MCP_PDF_IMPLEMENTATION_DESIGN.md §14.2：`page_size` / edit TOOL_DEF 行 → ✅（当 PDF-045/046 完成）
   - OFFICE_MCP_PDF_LLM_GUIDE.md §8：收尾列移除已完成的 **PDF-045** / **PDF-046** ⏳；五工具 E2E ✅（PDF-044 后）
   - OFFICE_TOOL_IMPLEMENTATION_TASKS_BY_FILE.md OT-126 / G4 footnote：PDF DS E2E complete (PDF-044)
6. pdf isolated: ! rg "word|presentation|spreadsheet" imports in pdf/

Output report:
- Tasks PDF-037–046 status
- E2E env requirements (.env.test keys)
- ADR-017–021 / 030 behavior summary for LLM callers
- Doc sync status (UPGRADE §7.1 / DESIGN §14 / LLM §8)
- Files touched

Do NOT git commit unless I explicitly ask.
```

**Verification commands**
```bash
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
poetry run pytest tests/office_mcp/pdf/ -v -m "not e2e"
poetry run pytest tests/office_mcp/pdf/ -v -m "pdf and e2e"
! rg "from aiecs.tools.office_tool.(word|presentation|spreadsheet)" aiecs/tools/office_tool/pdf/
python3 -c "
from aiecs.tools.office_tool.registry import collect_office_tools
p={'office_read_pdf','office_create_pdf','office_edit_pdf','office_merge_pdfs','office_fill_pdf_form'}
assert p <= {t['name'] for t in collect_office_tools()}
print('OK: pdf×5 in registry')
"
rg "PDF-0(3[7-9]|[4][0-6])" docs/OFFICE_MCP_PDF_IMPLEMENTATION_TASKS_BY_FILE.md | rg "\[ \]" || echo "OK: no open PDF-037+ tasks"
rg "⏳.*PDF-037–044|placeholder skip" docs/OFFICE_MCP_PDF_LLM_GUIDE.md docs/OFFICE_MCP_PDF_IMPLEMENTATION_DESIGN.md && echo "WARN: E2E doc rows still stale (expected until PDF-044)" || echo "OK: E2E doc sync"
```

---

## Appendix A — Recommended execution order

| Step | Prompt | Tasks | Gate |
|------|--------|-------|------|
| 0 | Bootstrap | — | — |
| 1 | §1 PDF-prep | env + baseline | — |
| 2 | §2 | **PDF-037–038** | E2E create/read + edit |
| 3 | §3 | **PDF-039–041** | E2E merge + fill_form |
| 4 | §4 | **PDF-042–043** | create_mode native / via_docx |
| 5 | §5 | **PDF-044** | **P-E2E** + legacy read_document + LLM §8 / DESIGN §14 E2E 收口 |
| 6 | §6 | **PDF-045** | page_size builder |
| 7 | §7 | **PDF-046** | edit TOOL_DEF（可选） |
| 8 | §8 PDF-T | DoD | 终验收 |

**顺序约束：** E2E（G）→ **PDF-044 Gate** → GAP（H：PDF-045 优先于 PDF-046）。E2E 中 merge **必须** re-read 断言 `page_count`（PDF-039）。

---

## Appendix B — Fix prompt template

```
PDF task PDF-{XXX} verification failed.

Failed command output:
<paste output>

Fix ONLY within PDF-{XXX} / batch scope per docs/OFFICE_MCP_PDF_IMPLEMENTATION_TASKS_BY_FILE.md Group G–H.
Do NOT re-do PDF-001–036 or PDF-DOC-04.
Do NOT change office_read_document pdf txt coarse behavior (PDF-NA-01).
Do NOT add fill_form_field to edit_pdf (PDF-NA-02 / ADR-030).
Do NOT auto via_docx on native create failure (PDF-NA-03 / ADR-017).
Do NOT silent merge builder→conversion fallback (PDF-NA-05 / ADR-018).
Do NOT modify core/ unless ADR-029 bugfix.
Use page_index / block_index from office_read_pdf fine.
Re-run this step's verification commands only.
Mark [x] in tasks doc when fixed.
Do NOT git commit unless I explicitly ask.
```

---

## Appendix C — Single-session continuous prompt（高级）

```
Follow docs/AI_PROMPT_OFFICE_MCP_PDF_IMPLEMENTATION.md Appendix A (steps 0–8) for PDF-037–046 ONLY.
Skip PDF-001–036 and PDF-DOC-04 entirely.
After each batch: run verification, mark [x] in OFFICE_MCP_PDF_IMPLEMENTATION_TASKS_BY_FILE.md, continue.
Finish with PDF-T report.
Do NOT git commit unless I explicitly ask.
```

---

## Appendix D — `.env.test` 参考（E2E）

| 变量 | 用途 |
|------|------|
| `DOCUMENTSERVER_URL` | DS healthcheck |
| `DOCUMENTSERVER_JWT_SECRET` | Builder/Conversion |
| `E2E_MCP_URL` | MCP `tools/call` HTTP |
| `E2E_MCP_PUBLIC_URL` | DS 拉 docbuilder script 可达地址 |
| `E2E_SOURCE_PATH` | 输出 pdf 前缀（`gs://` 或 `s3://`） |
| `E2E_SOURCE_PATHS` | merge 多源（可选；测试常 in-test create） |

**Fixtures（单测 / E2E 参考）：**

- AcroForm：`tests/office_mcp/pdf/fixtures/acroform_template.pdf`（字段 `company_name`）
- Sidecar 样例：`tests/office_mcp/pdf/fixtures/document_sidecar.json`
- 双页样例：`tests/office_mcp/pdf/fixtures/two_page_sample.pdf`

**ADR-021：** native create E2E 需 `probe_ds_capabilities().pdf_native_create`；否则 `pytest.skip` 带明确 reason。

**维护：** 随 [`OFFICE_MCP_PDF_IMPLEMENTATION_TASKS_BY_FILE.md`](./OFFICE_MCP_PDF_IMPLEMENTATION_TASKS_BY_FILE.md) Group G–H 更新。

---

## Appendix E — Task ID 覆盖矩阵（未完成部分）

| Task | TASKS Group | AI_PROMPT | 备注 |
|------|-------------|-----------|------|
| PDF-037–038 | G | §2 | create 2p → read fine + edit re-read |
| PDF-039–041 | G | §3 | merge **必须** re-read 断言 page_count；fill_form |
| PDF-042–043 | G | §4 | native probe skip；via_docx 显式 |
| PDF-044 | G | §5 | P-E2E Gate + legacy read_document + **LLM §8 / DESIGN §14 E2E 收口** |
| PDF-045 | H | §6 | page_size builder |
| PDF-046 | H | §7 | edit TOOL_DEF（可选） |
| PDF-NA-01–07 | F | §0 Bootstrap | 约束级覆盖 |
| PDF-001–036 | A–E | — | ⛔ 已完成 |
| PDF-DOC-04 | I | — | ⛔ 已完成 |

**未完成 PDF 共 10 项**（PDF-037–046）：prompt 均有对应 batch，无遗漏 Task ID。
