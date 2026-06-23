# Office MCP Spreadsheet — UPGRADE 收尾 — AI Prompt Sequence

将下方 prompt **按顺序**复制到 AI 会话（Cursor Agent 等）。**一次只跑一个 Batch**；本文件 **仅覆盖未完成 Task**（ST-037–ST-057、ST-DOC-04）。ST-001–036 架构交付已完成，**勿重复实现**。

**按文件任务（未完成）：** [`OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_TASKS_BY_FILE.md`](./OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_TASKS_BY_FILE.md) — Group I–M  
**Spreadsheet 实现设计：** [`OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_DESIGN.md`](./OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_DESIGN.md)  
**规格 / E2E 清单：** [`OFFICE_MCP_SPREADSHEET_UPGRADE.md`](./OFFICE_MCP_SPREADSHEET_UPGRADE.md) §4.3、§7.2  
**LLM 字段名：** [`OFFICE_MCP_SPREADSHEET_LLM_GUIDE.md`](./OFFICE_MCP_SPREADSHEET_LLM_GUIDE.md)（`sheet_name` / `sheet_index` + A1）  
**E2E 参考：** [`tests/office_mcp/test_e2e_office_tools.py`](../tests/office_mcp/test_e2e_office_tools.py)、[`tests/env_test.py`](../tests/env_test.py)

**范围（必做）：**

| Batch | Tasks | 内容 |
|-------|-------|------|
| **I — E2E** | ST-037 – ST-042、**ST-053** | 替换 `test_e2e_spreadsheet_tools.py` placeholder；Gate **S-E2E** |
| **J — Schema** | ST-043 – ST-046 | ADR-031–034、032、033：formulas/range/headers、移除 default_col_width |
| **J′ — TOOL_DEF** | **ST-047**（与 **ST-056** 同批） | ADR-040：`TOOL_DEF` ↔ `edit_ops.py`（含 `insert_rows.values`） |
| **K — Builder** | ST-048 – ST-050 | ADR-038 merge rename、ADR-035 copy_sheet、ADR-039 template dedup |
| **L — Spec gap** | ST-054 – ST-057、**ST-047** | 空 used range、ADR-036/037、M6 `test_registry.py` |
| **M — 卫生** | ST-051、ST-DOC-04 | `test_edit_builder.py`、文档 Gate 同步 |

**前置（已满足，仅核对）：**

- `spreadsheet/` 五 canonical 工具已在 `registry.py`（M5 **18/22**；M6 终态 **23/27**）
- `poetry run pytest tests/office_mcp/spreadsheet/ -v -m "not e2e"` 全绿（35 tests）
- **无** spreadsheet legacy MCP 别名
- `tests/office_mcp/spreadsheet/test_e2e_spreadsheet_tools.py` 仍为 **placeholder skip**

**真源优先级：** ADR（已采纳，含 **ADR-031–040** Spreadsheet 收尾）→ Spreadsheet IMPLEMENTATION_DESIGN §14 → **本 tasks 文档** → UPGRADE

---

## 0. Session Bootstrap Prompt（仅首次）

```
You are completing Office MCP Spreadsheet UPGRADE follow-up — tasks ST-037 through ST-057 and ST-DOC-04 ONLY.

DO NOT re-implement ST-001–036 (spreadsheet/ tree, registry, unit tests already done).

Required reading:
- docs/OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_TASKS_BY_FILE.md (Group I–M ONLY)
- docs/OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_DESIGN.md (§5 schemas, §7 builder, §11 tests, §14 gap index)
- docs/OFFICE_MCP_SPREADSHEET_UPGRADE.md (§4.3 edit ops, §7.2 E2E list, §8.1 status)
- docs/OFFICE_MCP_SPREADSHEET_LLM_GUIDE.md
- docs/ADR.md — ADR-013–015, 021, 031–040 (Spreadsheet follow-up)
- tests/office_mcp/test_e2e_office_tools.py (_call_tool_via_mcp pattern)
- tests/env_test.py (E2EConfig, .env.test)

Global constraints:
1. One prompt = one batch per docs/AI_PROMPT_OFFICE_MCP_SPREADSHEET_IMPLEMENTATION.md Appendix A.
2. Do NOT git commit unless I explicitly ask.
3. Surgical changes — touch spreadsheet/, tests/office_mcp/spreadsheet/, and docs listed in ST-DOC-04 only.
4. Do NOT modify core/ except ADR-029 bugfix (prefer zero core changes).
5. spreadsheet/* MUST NOT import word|presentation|pdf.
6. office_read_document: xlsx/xls/ods csv coarse behavior FROZEN (ST-NA-01 / OT-NA-05) — no transparent fine forwarding.
7. Edit ops use sheet_name / sheet_index + cell / range (A1, ADR-015) — NOT row/col.
8. No spreadsheet legacy MCP aliases (ADR-024).
9. E2E: MCP HTTP tools/call via test_e2e_office_tools.py pattern; config from .env.test.
10. Fine read E2E gated on GetSheetsCount probe (ADR-021) — coarse E2E may still run.
11. Do NOT leave unconditional pytest.skip("placeholder") in E2E test bodies after ST-037+.
12. After each batch, mark completed ST-* as [x] in OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_TASKS_BY_FILE.md.

Precondition check:
- poetry run pytest tests/office_mcp/spreadsheet/ -v -m "not e2e"  # must pass
- test -f aiecs/tools/office_tool/spreadsheet/tools/read.py
- test -f tests/office_mcp/spreadsheet/test_e2e_spreadsheet_tools.py
- rg "pytest.skip.*placeholder" tests/office_mcp/spreadsheet/test_e2e_spreadsheet_tools.py && echo "OK: placeholder still present (to replace)"

Reply "Ready for ST-prep" — do not write code yet.
```

---

## 1. Task ST-prep — 基线 + E2E 环境

```
[TASK ST-prep] Baseline; confirm .env.test; inventory open tasks

1. poetry run pytest tests/office_mcp/spreadsheet/ -v -m "not e2e"  # must pass

2. Read tests/env_test.py E2EConfig — document which vars are set:
   E2E_SOURCE_PATH / E2E_SOURCE_PATHS / E2E_TEMPLATE_PATH / E2E_MCP_URL / DOCUMENTSERVER_URL / JWT

3. Confirm test_e2e_office_tools.py has _call_tool_via_mcp — reuse for spreadsheet E2E.

4. List open tasks ST-037–057 from docs/OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_TASKS_BY_FILE.md Group I–M.

5. Read ADR-031–040 summaries in docs/ADR.md for upcoming schema/builder batches.

Do NOT implement E2E yet.
```

**Verification commands**
```bash
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
poetry run pytest tests/office_mcp/spreadsheet/ -v -m "not e2e"
test -f .env.test && echo "OK: .env.test exists" || echo "WARN: no .env.test — E2E needs local config"
rg "placeholder" tests/office_mcp/spreadsheet/test_e2e_spreadsheet_tools.py
rg "_call_tool_via_mcp" tests/office_mcp/test_e2e_office_tools.py | head -2
```

---

## 2. Batch T-ST-E2E-A — Tasks ST-037 – ST-038（xlsx + ods）

```
[TASK ST-037–038] Implement real Spreadsheet E2E: xlsx create/read/edit + ods round-trip

Implement ST-037 and ST-038 from docs/OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_TASKS_BY_FILE.md Group I.

File: tests/office_mcp/spreadsheet/test_e2e_spreadsheet_tools.py

ST-037 — xlsx:
1. Remove unconditional pytest.skip("placeholder") from implemented tests.
2. test_e2e_create_read_edit_spreadsheet_xlsx:
   - office_create_spreadsheet (2 sheets) → unique gs:// output_path .xlsx
   - office_read_spreadsheet fine structured → assert unit_count == 2
   - office_edit_spreadsheet: set_cell + set_range (sheet_name + A1)
   - office_read_spreadsheet again → assert change visible

ST-038 — ods:
3. test_e2e_ods_create_edit_roundtrip_spreadsheet:
   - output_path ends with .ods
   - create → edit → output still .ods

Use _call_tool_via_mcp from test_e2e_office_tools.py.
Use unique output paths (uuid) under E2E bucket prefix.
Keep @pytest.mark.spreadsheet @pytest.mark.e2e and documentserver_reachable skipif.
Fine read tests: skip if GetSheetsCount unavailable (probe pattern already in file).

Mark ST-037, ST-038 [x] when done.
Do NOT git commit unless I ask.
```

**Verification commands**
```bash
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
poetry run pytest tests/office_mcp/spreadsheet/test_e2e_spreadsheet_tools.py -v -m "spreadsheet and e2e" -k "xlsx or ods" 2>&1 | tail -30
poetry run pytest tests/office_mcp/spreadsheet/ -v -m "not e2e"
```

---

## 3. Batch T-ST-E2E-B — Tasks ST-039 – ST-041（merge / template / read_document）

```
[TASK ST-039–041] Spreadsheet E2E: merge, template, read_document coarse

Implement ST-039, ST-040, ST-041 from tasks doc Group I.

In tests/office_mcp/spreadsheet/test_e2e_spreadsheet_tools.py:

ST-039 — test_e2e_merge_spreadsheets:
- Two source xlsx (E2E_SOURCE_PATHS or create two workbooks first); record each source unit_count via office_read_spreadsheet fine
- office_merge_spreadsheets → output_path *.xlsx
- **必须**：office_read_spreadsheet fine on merged output → assert unit_count == sum(source unit_counts) when sheet names do not collide
  (若源 sheet 同名，先记录预期 behavior；rename_conflicts 断言留到 ST-048 后补测)
- Assert merge handler success — success alone is NOT sufficient for ST-039 [x]

ST-040 — test_e2e_apply_template_spreadsheet:
- E2E_TEMPLATE_PATH xlsx + data with Summary!B2 and {{key}}
- Assert success

ST-041 — test_e2e_read_document_xlsx_coarse:
- office_read_document on xlsx source
- Assert csv/elements coarse path — NOT fine sheets[] from read_spreadsheet
- Must NOT regress to transparent fine forwarding

Reference UPGRADE §7.2 #5–7.

Mark ST-039–041 [x] when done.
```

**Verification commands**
```bash
poetry run pytest tests/office_mcp/spreadsheet/test_e2e_spreadsheet_tools.py -v -m "spreadsheet and e2e" -k "merge or template or read_document" 2>&1 | tail -40
# ST-039: merge test must call read_spreadsheet and assert unit_count (grep test body)
rg "unit_count" tests/office_mcp/spreadsheet/test_e2e_spreadsheet_tools.py
poetry run pytest tests/office_mcp/spreadsheet/ -v -m "not e2e"
```

---

## 4. Task ST-053 — E2E `.xls` 读取

```
[TASK ST-053] E2E: read legacy .xls (fine or coarse fallback)

Implement ST-053 from tasks doc Group I.

test_e2e_read_spreadsheet_xls:
- Source: E2E_SOURCE_PATH ending in .xls OR skip if no .xls fixture configured
- office_read_spreadsheet fine when GetSheetsCount available
- Else read_mode=coarse per ADR-021
- Assert success response (structured or coarse _note)

UPGRADE §7.2 #4; DESIGN §11.3 #4.

Mark ST-053 [x] when done.
```

**Verification commands**
```bash
poetry run pytest tests/office_mcp/spreadsheet/test_e2e_spreadsheet_tools.py -v -m "spreadsheet and e2e" -k "xls" 2>&1 | tail -20
```

---

## 5. Task ST-042 — Gate S-E2E

```
[TASK ST-042] Close Gate S-E2E

1. ST-037–041 and ST-053 all [x] in OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_TASKS_BY_FILE.md
2. Update tasks doc bottom checklist: S-E2E line → [x]
3. Update IMPLEMENTATION_DESIGN §2.2 S-E2E row → ✅
4. Module docstring: required .env.test vars

Verification: full spreadsheet e2e suite without placeholder skip in test bodies (module may skip if DS down — OK per ADR-021).
```

**Verification commands**
```bash
poetry run pytest tests/office_mcp/spreadsheet/ -v -m "spreadsheet and e2e"
grep "S-E2E" docs/OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_TASKS_BY_FILE.md | head -5
```

---

## 6. Batch T-ST-SCHEMA — Tasks ST-043 – ST-046

```
[TASK ST-043–046] Schema / Read — ADR-031–034, 032, 033

Implement ST-043 through ST-046 from tasks doc Group J. Read ADR-031–034, 032, 033 in docs/ADR.md.

**Do NOT mark ST-047 [x] in this batch** — ST-047 (TOOL_DEF / ADR-040) completes with ST-056 in §8.

ST-043 (ADR-031) include_formulas:
- Files: spreadsheet/parser/workbook.py (sidecar GetFormula), spreadsheet/tools/read.py
- sidecar: GetFormula() when include_formulas=true else GetValue()
- Unit test: tests/office_mcp/spreadsheet/test_read_spreadsheet.py (mock sidecar with formula cell)

ST-044 (ADR-034) options.range:
- Files: spreadsheet/parser/workbook.py (apply_range_filter), spreadsheet/tools/read.py
- **range before max_rows**; outline updates clipped used_range
- Unit test: test_workbook_parser.py and/or test_read_spreadsheet.py

ST-045 (ADR-032) remove default_col_width:
- Files: spreadsheet/schemas/workbook_spec.py, spreadsheet/tools/create.py (TOOL_DEF),
  spreadsheet/builder/create.py (drop options from build_create_script if empty)
- Delete from UPGRADE/LLM if still present

ST-046 (ADR-033) read headers:
- File: spreadsheet/parser/workbook.py — parse_workbook_json: headers = rows[0] when rows non-empty
- Unit test: tests/office_mcp/spreadsheet/test_workbook_parser.py using fixtures/workbook_sidecar.json (双 sheet fixture)

Run: poetry run pytest tests/office_mcp/spreadsheet/ -v -m "not e2e"

Sync UPGRADE §2.4 / §4.1 / §8.1 rows for ST-043–046 when done.

Mark ST-043–046 [x] only (NOT ST-047).
```

**Verification commands**
```bash
poetry run pytest tests/office_mcp/spreadsheet/ -v -m "not e2e"
poetry run pytest tests/office_mcp/spreadsheet/test_read_spreadsheet.py tests/office_mcp/spreadsheet/test_workbook_parser.py -v
! rg "default_col_width" aiecs/tools/office_tool/spreadsheet/ && echo "FAIL: default_col_width remains" || echo "OK"
```

---

## 7. Batch T-ST-BUILDER — Tasks ST-048 – ST-050

```
[TASK ST-048–050] Builder: merge rename, copy_sheet, template dedup

Implement ST-048, ST-049, ST-050 from tasks doc Group K.

ST-048 (ADR-038) builder/merge.py rename_conflicts:
- true: suffix _2/_3 on sheet name collision
- false: let Builder fail → handler {isError}
- test_merge_spreadsheets.py asserts script body

ST-049 (ADR-035) builder/edit.py copy_sheet:
- Correct ONLYOFFICE Copy API
- Optional new_name in edit_ops.py → SetName on copy
- Unit test script body

ST-050 (ADR-039) builder/template.py:
- Explicit Sheet!A1 keys consumed → skip {{key}} SearchAndReplace for those keys
- test_apply_template_spreadsheet.py explicit-wins case

Mark ST-048–050 [x].
Re-run ST-039 E2E if merge rename now testable.
```

**Verification commands**
```bash
poetry run pytest tests/office_mcp/spreadsheet/test_merge_spreadsheets.py tests/office_mcp/spreadsheet/test_apply_template_spreadsheet.py tests/office_mcp/spreadsheet/test_edit_spreadsheet.py -v
poetry run pytest tests/office_mcp/spreadsheet/ -v -m "not e2e"
```

---

## 8. Batch T-ST-SPEC-GAP — Tasks ST-054 – ST-057 + ST-047

```
[TASK ST-054–057, ST-047] Parser / edit spec / TOOL_DEF / M6 registry

Implement ST-054 through ST-057 AND ST-047 from tasks doc Group L (+ ST-047 from Group J).

ST-054 — empty used range:
- File: spreadsheet/parser/workbook.py
- tests/office_mcp/spreadsheet/test_workbook_parser.py: fixture sheet with no used range (rows:[], used_range key omitted)
- Align DESIGN §6.2 / UPGRADE if needed

ST-055 (ADR-036) add_sheet rows permanently unsupported:
- File: spreadsheet/schemas/edit_ops.py — validator rejects add_sheet with extra rows field
- tests/office_mcp/spreadsheet/test_schemas.py: illegal JSON rejected
- UPGRADE/LLM already say unsupported

ST-056 (ADR-037) insert_rows optional values:
- Files: spreadsheet/schemas/edit_ops.py, spreadsheet/builder/edit.py
- After InsertRows, SetValue when values provided; shape mismatch → validation or {isError}
- tests/office_mcp/spreadsheet/test_schemas.py + test_edit_spreadsheet.py or test_edit_builder.py

ST-047 (ADR-040) edit TOOL_DEF — **same batch as ST-056**:
- File: spreadsheet/tools/edit.py
- Regenerate inputSchema.operations.items from edit_ops.py via model_json_schema (ADR-002)
- **Must include insert_rows.values** after ST-056 lands — mark ST-047 [x] only together with ST-056

ST-057 — set_range spec + M6 registry:
- Confirm as-built only range+values (no anchor); update DESIGN §14.2 row if needed
- **必须**：tests/office_mcp/test_registry.py asserts M6终态 len(collect_office_tools())==23 and len(get_handlers())==27 (spreadsheet×5 included)
- Also run one-liner below as smoke check

Mark ST-054–057 and ST-047 [x] together when all pass.
```

**Verification commands**
```bash
poetry run pytest tests/office_mcp/spreadsheet/test_workbook_parser.py tests/office_mcp/spreadsheet/test_schemas.py -v
python3 -c "
from aiecs.tools.office_tool.spreadsheet.tools.edit import TOOL_DEF
props = TOOL_DEF['inputSchema']['properties']['operations']['items']['properties']
assert 'cell' in props and 'new_name' in props, list(props.keys())
print('OK: TOOL_DEF base fields')
"
poetry run pytest tests/office_mcp/test_registry.py -v -k "M6"
python3 -c "
from aiecs.tools.office_tool.registry import collect_office_tools, get_handlers
c,h=len(collect_office_tools()),len(get_handlers())
assert (c,h)==(23,27), (c,h)
print('OK: M6 registry 23/27')
"
```

---

## 9. Batch T-ST-HYGIENE — Tasks ST-051、ST-DOC-04

```
[TASK ST-051–DOC-04] test_edit_builder + documentation Gate sync

ST-051 (recommended):
- Add tests/office_mcp/spreadsheet/test_edit_builder.py
- Assert build_edit_script / build_merge_script for ST-048–049 changes

ST-DOC-04 (run **after** ST-054–057 [x]):
- OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_DESIGN.md §2.2 / §11.3 / §13 all ✅ for completed work
- OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_DESIGN.md **§14.2 UPGRADE 规格级 API 与收尾 Task 表** — every row ✅ or N/A
- OFFICE_MCP_SPREADSHEET_UPGRADE.md §8.1 honest status (no premature ✅ on E2E/schema rows)
- OFFICE_MCP_SPREADSHEET_LLM_GUIDE.md §8
- OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_TASKS_BY_FILE.md: Group I–M all [x]; bottom checklist all [x]
- OFFICE_TOOL_IMPLEMENTATION_TASKS_BY_FILE.md **OT-112** footnote: Spreadsheet DS E2E complete (ST-042)

Do NOT mark ST-DOC-04 [x] until ST-054–057 and §14.2 table are synced.

Mark ST-051, ST-DOC-04 [x].
```

**Verification commands**
```bash
poetry run pytest tests/office_mcp/spreadsheet/ -v -m "not e2e"
rg "ST-0(3[7-9]|[4-9][0-9]|5[0-7])" docs/OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_TASKS_BY_FILE.md | rg "\[ \]" || echo "OK: no open ST-037+ tasks"
```

---

## 10. Task ST-T — Definition of Done

```
[TASK ST-T] Spreadsheet UPGRADE wrap-up

Verify docs/OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_TASKS_BY_FILE.md Group I–M all [x].

1. Unit: poetry run pytest tests/office_mcp/spreadsheet/ -v -m "not e2e"
2. E2E: poetry run pytest tests/office_mcp/spreadsheet/ -v -m "spreadsheet and e2e" (PASS or ADR-021 skip — no placeholder)
3. Schema: include_formulas, range, headers per ADR-031/034/033; default_col_width removed (ADR-032)
4. Builder: merge rename (ADR-038), copy_sheet (ADR-035), template dedup (ADR-039)
5. Spec gap: add_sheet.rows rejected (ADR-036), insert_rows.values + ST-047 TOOL_DEF (ADR-037/040), M6 test_registry (ST-057)
6. Docs synced (ST-DOC-04 incl. DESIGN §14.2)
7. spreadsheet isolated: ! rg "word|presentation|pdf" imports in spreadsheet/

Output report:
- Tasks ST-037–057 status
- E2E env requirements (.env.test keys)
- ADR-031–040 behavior summary for LLM callers
- Files touched

Do NOT git commit unless I explicitly ask.
```

**Verification commands**
```bash
cd "$(git rev-parse --show-toplevel 2>/dev/null || pwd)"
poetry run pytest tests/office_mcp/spreadsheet/ -v -m "not e2e"
poetry run pytest tests/office_mcp/spreadsheet/ -v -m "spreadsheet and e2e"
! rg "from aiecs.tools.office_tool.(word|presentation|pdf)" aiecs/tools/office_tool/spreadsheet/
poetry run pytest tests/office_mcp/test_registry.py -v -k "M6"
python3 -c "
from aiecs.tools.office_tool.registry import collect_office_tools, get_handlers
assert len(collect_office_tools())==23 and len(get_handlers())==27
print('OK: registry终态')
"
```

---

## Appendix A — Recommended execution order

| Step | Prompt | Tasks | Gate |
|------|--------|-------|------|
| 0 | Bootstrap | — | — |
| 1 | §1 ST-prep | env + baseline | — |
| 2 | §2 | **ST-037–038** | E2E xlsx/ods |
| 3 | §3 | **ST-039–041** | E2E merge/template/coarse |
| 4 | §4 | **ST-053** | E2E xls read |
| 5 | §5 | **ST-042** | **S-E2E** |
| 6 | §6 | **ST-043–046** | Schema read (not ST-047) |
| 7 | §7 | **ST-048–050** | Builder |
| 8 | §8 | **ST-054–057 + ST-047** | Spec gap + TOOL_DEF + M6 registry |
| 9 | §9 | **ST-051, ST-DOC-04** | Docs（ST-DOC-04 在 §14.2 同步后） |
| 10 | §10 ST-T | DoD | 终验收 |

**顺序约束：** E2E（I + ST-053）→ Schema **ST-043–046** → Builder（K）→ **ST-054–057 + ST-047**（L；ST-047 与 ST-056 同批完成）→ 卫生（M）。**禁止**在 ST-056 之前单独将 ST-047 标 `[x]`。

---

## Appendix B — Fix prompt template

```
Spreadsheet task ST-{XXX} verification failed.

Failed command output:
<paste output>

Fix ONLY within ST-{XXX} / batch scope per docs/OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_TASKS_BY_FILE.md Group I–M.
Do NOT re-do ST-001–036.
Do NOT change office_read_document csv coarse behavior (ST-NA-01).
Do NOT modify core/ unless ADR-029 bugfix.
Use sheet_name / sheet_index + cell / range (A1, ADR-015).
Re-run this step's verification commands only.
Mark [x] in tasks doc when fixed.
Do NOT git commit unless I explicitly ask.
```

---

## Appendix C — Single-session continuous prompt（高级）

```
Follow docs/AI_PROMPT_OFFICE_MCP_SPREADSHEET_IMPLEMENTATION.md Appendix A (steps 0–10) for ST-037–057 ONLY.
Skip ST-001–036 entirely.
After each batch: run verification, mark [x] in OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_TASKS_BY_FILE.md, continue.
Finish with ST-T report.
Do NOT git commit unless I explicitly ask.
```

---

## Appendix D — `.env.test` 参考（E2E）

| 变量 | 用途 |
|------|------|
| `DOCUMENTSERVER_URL` | DS healthcheck |
| `DOCUMENTSERVER_JWT_SECRET` | Builder/Conversion |
| `E2E_MCP_URL` | MCP `tools/call` HTTP |
| `E2E_MCP_PUBLIC_URL` | DS 拉 script 可达地址 |
| `E2E_SOURCE_PATH` | 单 xlsx/xls 源 |
| `E2E_SOURCE_PATHS` | merge 多源（逗号或 JSON） |
| `E2E_TEMPLATE_PATH` | apply_template xlsx |

**维护：** 随 [`OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_TASKS_BY_FILE.md`](./OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_TASKS_BY_FILE.md) Group I–M 更新。

---

## Appendix E — Task ID 覆盖矩阵（未完成部分）

| Task | TASKS Group | AI_PROMPT | 备注 |
|------|-------------|-----------|------|
| ST-037–038 | I | §2 | xlsx + ods 测试名 `test_e2e_ods_*` |
| ST-039–041 | I | §3 | ST-039 **必须** re-read 断言 `unit_count` |
| ST-053 | I | §4 | xls read |
| ST-042 | I | §5 | S-E2E Gate |
| ST-043–046 | J | §6 | 不含 ST-047 |
| ST-047 | J | §8（与 ST-056） | ADR-040 TOOL_DEF |
| ST-048–050 | K | §7 | Builder |
| ST-054–057 | L | §8 | 含 ST-047、`test_registry.py` |
| ST-051 | M | §9 | 可选但推荐 |
| ST-DOC-04 | M | §9 | §14.2 表 + OT-112 |
| ST-NA-01–06 | H | §0 Bootstrap | 约束级 |
| ST-001–036 | A–F | — | ⛔ 已完成 |
| ST-DOC-01–03 | G | — | ⛔ 已完成 |
