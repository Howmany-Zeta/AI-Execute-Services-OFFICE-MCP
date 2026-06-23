# Office MCP Spreadsheet — 按文件必选任务（S0–S4 + M5）

**用途：** 落地 [OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_DESIGN.md](./OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_DESIGN.md) 时，将 Spreadsheet 垂直模块从扁平 legacy / `html_parser` csv 路径迁移为 **`spreadsheet/{parser,builder,schemas,tools}/` + registry 注册** 的**逐文件**执行清单。

**对齐（设计真源，实现前必读）：**

| 文档 | 角色 |
|------|------|
| [OFFICE_MCP_SPREADSHEET_UPGRADE.md](./OFFICE_MCP_SPREADSHEET_UPGRADE.md) | What：工具参数、sheets/operations 语义 |
| [OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_DESIGN.md](./OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_DESIGN.md) | How（Spreadsheet）：目录树、Core 集成、Builder、Gate |
| [implementation_design.md](./implementation_design.md) | How（全局）：Core §4、Registry §5、M5 §7.3 |
| [OFFICE_TOOL_IMPLEMENTATION_TASKS_BY_FILE.md](./OFFICE_TOOL_IMPLEMENTATION_TASKS_BY_FILE.md) | 全局 OT-100–112；**本表为其 Spreadsheet 子集展开** |
| [ADR.md](./ADR.md) | ADR-002、006、013–015、021、024–025、028–029、**031–040** |
| [OFFICE_MCP_SPREADSHEET_LLM_GUIDE.md](./OFFICE_MCP_SPREADSHEET_LLM_GUIDE.md) | LLM 示例（`sheet_name` / `sheet_index` + A1） |

**Preconditions（全局 M0–M3，Spreadsheet 开工前）**

- [x] **M0**：`core/builder_runtime.py`、`core/builder_js.py`（全局 OT-013–022）
- [x] **M1**：`core/categories`、`errors`、`read_response`、`coarse_read`、`builder_json_sidecar`、`source`、`storage`（全局 OT-023–045）
- [x] **M3**：`registry.py` 骨架；Word 六工具已注册（**M5 前 canonical=8**）
- [x] `poetry run pytest tests/office_mcp/ -v -m "not e2e"` 全绿

**任务编号：** **ST-001 … ST-036**（架构交付）+ **ST-037 … ST-057**（UPGRADE 收尾）+ **ST-DOC-***。

**路径约定：** Python 相对仓库根 `aiecs/`、`tests/`；文档相对 `docs/`。

**完成定义：** **`[ ]` → `[x]`** = 本 Task 在对应 PR 中落地并满足「必须完成」列。

> **代码状态（2026-06）**
>
> | 范围 | 状态 |
> |------|------|
> | **架构 M5**（ST-001–036、ST-DOC-01–03） | ✅ 已落地：模块、registry |
> | **UPGRADE 收尾**（ST-037–057、ST-DOC-04） | ✅ 已落地：E2E、**ADR-031–040**、Builder 收尾 |
>
> 架构重组 **G3（Spreadsheet 注册）** 与 **UPGRADE §7.2 E2E** 均已满足。

**遵循的方法（Spreadsheet 子集）：**

| 方法 | 来源 | 要求 |
|------|------|------|
| `run_builder_script` | ADR-009 | create / merge |
| `run_builder_on_source` | ADR-009 | edit / template（有源） |
| `build_read_response` | ADR-028 | `office_read_spreadsheet` structured/outline |
| `err` / `ok` | ADR-006 | 全部 handler |
| Pydantic v2 | ADR-002 | `spreadsheet/schemas/*` |
| A1 / `range` | ADR-015 | **`cell` / `range`**；**非** `row` / `col` |
| Sidecar | ADR-013 | `GetSheetsCount()` + for |
| Template | ADR-014 | 显式 `Sheet!A1` + used_range `{{key}}` |
| Registry M5 | ADR-024 | 五工具 canonical；**无** spreadsheet legacy 别名 |
| `[Spreadsheet]` 前缀 | ADR-025 | 五 canonical description |
| 行为冻结 | ST-NA-01 | `office_read_document` xlsx/xls/ods **csv 粗读**不变 |

---

## 里程碑与 Gate

| 阶段 | Gate | 交付摘要 | 全局 |
|------|------|----------|------|
| **S0** | S0 | 目录 + csv 粗读；legacy xlsx csv 回归 | OT-100–101, 105(部分), 110 |
| **S1** | S1 | fine read sidecar + `parser/workbook.py` | OT-102, 108(部分), 111 |
| **S2** | S2 | create + `workbook_spec` | OT-103–104, 105(部分) |
| **S3** | S3 | edit 10 op + A1 schema | OT-103–104, 105(部分) |
| **S4** | S4 | merge + template + unit | OT-104–105, 108(部分) |
| **M5** | G3（Sheet 切片） | registry 五工具 + `[Spreadsheet]` + tests 目录 | OT-106–112 |

**Registry（Spreadsheet 相关）：** M5 时 gateway×2 + word×6 + pres×5 + sheet×5 → **`collect_office_tools()==18`**，`get_handlers()==22`（+4 legacy，无 sheet legacy）。

---

## Group A — S0：目录 + csv 粗读

**Batch `T-ST-S0` — Tasks ST-001 – ST-009** · **Gate：S0**

### [x] **Task ST-001** — `aiecs/tools/office_tool/spreadsheet/__init__.py`（OT-100）

| 字段 | 内容 |
|------|------|
| **必须完成** | 包初始化 |

### [x] **Task ST-002** — `spreadsheet/parser/__init__.py`

| 字段 | 内容 |
|------|------|
| **必须完成** | 导出 `csv`、`workbook` public API |

### [x] **Task ST-003** — `spreadsheet/parser/csv.py`（OT-101）

| 字段 | 内容 |
|------|------|
| **必须完成** | re-export `core/coarse_parsers/csv`：`parse_csv_to_structure`、`extract_outline_from_csv`、`csv_to_coarse_sheets` |
| **S0 禁止** | 改变 `office_read_document` 对 xlsx/xls/ods 的 csv 粗读行为 |

### [x] **Task ST-004** — `spreadsheet/schemas/read.py`（OT-103 · 部分）

| 字段 | 内容 |
|------|------|
| **必须完成** | `SpreadsheetReadOptions`, `SpreadsheetReadArgs` |
| **必须完成** | `source_path` XOR `source_url` |

### [x] **Task ST-005** — `spreadsheet/tools/read.py` · coarse 路径（OT-105 · 部分）

| 字段 | 内容 |
|------|------|
| **必须完成** | `read_mode=coarse` → `convert_and_fetch` → `csv_to_coarse_sheets` |
| **必须完成** | `build_read_response` + coarse `_note` |
| **ADR-028** | 不得 inline 拼顶层 read dict |

### [x] **Task ST-006** — `spreadsheet/builder/__init__.py` / `schemas/__init__.py` / `tools/__init__.py`

| 字段 | 内容 |
|------|------|
| **必须完成** | 包结构完整 |

### [x] **Task ST-007** — legacy xlsx csv 回归（OT-110）

| 字段 | 内容 |
|------|------|
| **必须完成** | `legacy/read_document.py` spreadsheet 仍走 csv |
| **验收** | 现有 `test_office_read*` 绿 |

### [x] **Task ST-008** — `tests/office_mcp/spreadsheet/test_csv_parser.py`（OT-108 · 部分）

| 字段 | 内容 |
|------|------|
| **必须完成** | 三 csv 函数 + re-export 路径 |

### [x] **Task ST-009** — Gate **S0**

| 字段 | 内容 |
|------|------|
| **必须完成** | `poetry run pytest tests/office_mcp/spreadsheet/ -v -m "not e2e"` 绿（S0 范围） |
| **禁止** | legacy csv 行为回归 |

---

## Group B — S1：fine read + sidecar

**Batch `T-ST-S1` — Tasks ST-010 – ST-016** · **Gate：S1**

### [x] **Task ST-010** — `spreadsheet/parser/workbook.py`（OT-102）

| 字段 | 内容 |
|------|------|
| **必须完成** | `WORKBOOK_SIDECAR_EXTRACT_BODY`（**ADR-013**：`GetSheetsCount()` + for） |
| **必须完成** | `parse_workbook_json`, `filter_sheet_names`, `apply_max_rows` |
| **必须完成** | `parse_a1`, `parse_range`, `sheets_to_outline`, `sheets_to_text` |

### [x] **Task ST-011** — `spreadsheet/tools/read.py` · fine 路径（OT-105 · 部分）

| 字段 | 内容 |
|------|------|
| **必须完成** | `read_sidecar_json(..., WORKBOOK_SIDECAR_EXTRACT_BODY)` |
| **必须完成** | `format`: structured / outline / text；`read_mode`: fine / coarse |
| **必须完成** | `_locator_note` 指向 `office_edit_spreadsheet` + A1 |
| **必须完成** | `sheets[]` ≡ `units[]` mirror |

### [x] **Task ST-012** — `tests/office_mcp/spreadsheet/test_workbook_parser.py`（OT-108）

| 字段 | 内容 |
|------|------|
| **必须完成** | 双 sheet fixture；filter；max_rows；outline/text |
| **必须完成** | sidecar body 含 `GetSheetsCount` |

### [x] **Task ST-013** — `tests/office_mcp/spreadsheet/test_read_spreadsheet.py`

| 字段 | 内容 |
|------|------|
| **必须完成** | mock sidecar fine read；coarse 分支；缺 source 错误 |

### [x] **Task ST-014** — `tests/office_mcp/spreadsheet/test_e2e_spreadsheet_tools.py`（OT-109）

| 字段 | 内容 |
|------|------|
| **markers** | `@pytest.mark.spreadsheet` `@pytest.mark.e2e` |
| **已交付** | 文件 + skip 占位 + GetSheetsCount probe skip（ADR-021） |
| **未完成** | 真实 create/read/edit 闭环 → **ST-037–042** |

### [x] **Task ST-015** — DS 探针 GetSheetsCount（OT-111）

| 字段 | 内容 |
|------|------|
| **必须完成** | `tests/office_mcp/probe_ds_capabilities.py` 骨架；fine E2E gated |
| **关联** | 全局 OT-045b 探针基础设施 |

### [x] **Task ST-016** — Gate **S1**

| 字段 | 内容 |
|------|------|
| **必须完成** | S1 unit 绿 |
| **部分完成** | E2E 仅占位；完整 Gate 见 **ST-042** |

---

## Group C — S2：声明式 create

**Batch `T-ST-S2` — Tasks ST-017 – ST-021** · **Gate：S2**

### [x] **Task ST-017** — `spreadsheet/schemas/workbook_spec.py`（OT-103）

| 字段 | 内容 |
|------|------|
| **必须完成** | `SheetSpec`, `SpreadsheetCreateArgs`, `SpreadsheetCreateOptions` |
| **说明** | `header_row` 纯语义（**ADR-033**）；**ADR-032** 无 `default_col_width` → **ST-045** 移除 |

### [x] **Task ST-018** — `spreadsheet/builder/create.py`（OT-104 · S2）

| 字段 | 内容 |
|------|------|
| **必须完成** | `build_create_script(sheets, output_ext, options)` |
| **必须完成** | 首 sheet `GetActiveSheet`；后续 `AddSheet`/`GetSheet`；`SetValue` 二维块 |
| **必须完成** | `SaveFile` 跟 `output_path` ext（xlsx/ods） |

### [x] **Task ST-019** — `spreadsheet/tools/create.py`（OT-105）

| 字段 | 内容 |
|------|------|
| **必须完成** | `office_create_spreadsheet` → `run_builder_script` |
| **必须完成** | `assert_category_path("spreadsheet", output_path)` |

### [x] **Task ST-020** — `tests/office_mcp/spreadsheet/test_create_spreadsheet.py`

| 字段 | 内容 |
|------|------|
| **必须完成** | mock runtime；script 含 `CreateFile`、`SetName`、`GetActiveSheet` |

### [x] **Task ST-021** — Gate **S2**

| 字段 | 内容 |
|------|------|
| **必须完成** | S2 unit 绿 |
| **未完成** | create xlsx/ods **E2E** → **ST-037–038** |

---

## Group D — S3：声明式 edit

**Batch `T-ST-S3` — Tasks ST-022 – ST-027** · **Gate：S3**

### [x] **Task ST-022** — `spreadsheet/schemas/edit_ops.py`（OT-103 · S3）

| 字段 | 内容 |
|------|------|
| **必须完成** | `EditOperation`, `SpreadsheetEditArgs`；10 种 `op` |
| **ADR-015** | `set_cell`/`set_range` 用 **`cell`/`range`**；`no_row_col` validator |
| **必须完成** | `insert_rows`/`delete_rows` 用 **1-based** `at_row`/`from_row` |
| **字段名** | `rename_sheet` → **`sheet_name` + `new_name`** |

### [x] **Task ST-023** — `spreadsheet/builder/edit.py`（OT-104 · S3）

| 字段 | 内容 |
|------|------|
| **必须完成** | `build_edit_script(operations, file_ext)` — body only |
| **必须完成** | `_emit_resolve_sheet`：`GetSheetByName` / `GetSheet(i)` / `GetActiveSheet` |
| **说明** | `copy_sheet` + `new_name`（**ST-049** ✅） |

### [x] **Task ST-024** — `spreadsheet/tools/edit.py`（OT-105）

| 字段 | 内容 |
|------|------|
| **必须完成** | `office_edit_spreadsheet` → `run_builder_on_source` |
| **必须完成** | 可选 `options.backup` |

### [x] **Task ST-025** — `tests/office_mcp/spreadsheet/test_schemas.py`

| 字段 | 内容 |
|------|------|
| **必须完成** | set_cell/range/insert_rows 校验；source 必填 |

### [x] **Task ST-026** — `tests/office_mcp/spreadsheet/test_edit_spreadsheet.py`

| 字段 | 内容 |
|------|------|
| **必须完成** | mock runtime；`set_cell` A1 在 script body |

### [x] **Task ST-027** — Gate **S3**

| 字段 | 内容 |
|------|------|
| **必须完成** | S3 unit 绿 |
| **收尾** | E2E edit 闭环 → **ST-037** ✅；`copy_sheet` → **ST-049** ✅ |

---

## Group E — S4：merge + template

**Batch `T-ST-S4` — Tasks ST-028 – ST-032** · **Gate：S4**

### [x] **Task ST-028** — `spreadsheet/builder/merge.py`（OT-104 · S4）

| 字段 | 内容 |
|------|------|
| **必须完成** | `build_merge_script`：多源 OpenFile → Copy sheets → SaveFile |
| **收尾** | `rename_conflicts` 重命名 JS → **ST-048** ✅ |

### [x] **Task ST-029** — `spreadsheet/builder/template.py`（OT-104 · ADR-014）

| 字段 | 内容 |
|------|------|
| **必须完成** | 显式 `Sheet!A1` → `SetValue` |
| **必须完成** | `{{key}}` → used_range `SearchAndReplace` |
| **收尾** | 显式 wins dedup → **ST-050** ✅ |

### [x] **Task ST-030** — `spreadsheet/tools/merge.py` / `template.py`（OT-105）

| 字段 | 内容 |
|------|------|
| **必须完成** | `office_merge_spreadsheets` → `run_builder_script` |
| **必须完成** | `office_apply_template_spreadsheet` → `run_builder_on_source` |

### [x] **Task ST-031** — `tests/office_mcp/spreadsheet/test_merge_spreadsheets.py` / `test_apply_template_spreadsheet.py`

| 字段 | 内容 |
|------|------|
| **必须完成** | merge script 含 `GetSheetsCount` |
| **必须完成** | template 显式地址 + placeholder 在 body |

### [x] **Task ST-032** — Gate **S4**

| 字段 | 内容 |
|------|------|
| **必须完成** | merge + template unit 绿 |
| **收尾** | merge rename / template dedup E2E → **ST-039、ST-040、ST-048–050** ✅ |

---

## Group F — M5：Registry + 描述 + 测试目录

**Batch `T-ST-M5` — Tasks ST-033 – ST-036** · **Gate：G3（Spreadsheet 切片）** · 全局 OT-106–112

### [x] **Task ST-033** — `registry.py` Spreadsheet 五模块（OT-106）

| 字段 | 内容 |
|------|------|
| **必须完成** | `CANONICAL_MODULES` 含 spreadsheet.tools.read/create/edit/merge/template |
| **禁止** | spreadsheet legacy 别名 |
| **验收** | M5：`len(collect_office_tools())==18`；`len(get_handlers())==22` |

### [x] **Task ST-034** — `[Spreadsheet]` description + marker（OT-107）

| 字段 | 内容 |
|------|------|
| **ADR-025** | 五 canonical `TOOL_DEF["description"]` 前缀 `[Spreadsheet]` |
| **必须完成** | **`pyproject.toml` 注册 `spreadsheet` marker**（strict-markers） |

### [x] **Task ST-035** — `tests/office_mcp/spreadsheet/` 目录（OT-108 · ADR-023）

| 字段 | 内容 |
|------|------|
| **必须完成** | spreadsheet 相关测试均在 `tests/office_mcp/spreadsheet/` |
| **必须完成** | `fixtures/workbook_sidecar.json` |

### [x] **Task ST-036** — Gate **M5 / G3 部分**（OT-112 · 部分）

| 字段 | 内容 |
|------|------|
| **必须完成** | `test_registry.py` M5 断言 **18/22** |
| **必须完成** | **OT-138 子集**：集成测试断言 **18** canonical |
| **部分完成** | OT-112 E2E 绿 → 仅占位；**M6 23/27** → **ST-057** |

---

## Group G — 文档（M5 同步）

**Batch `T-ST-DOC` — 映射全局 OT-004 / OT-008**

### [x] **Task ST-DOC-01** — `docs/OFFICE_MCP_SPREADSHEET_UPGRADE.md`

| 字段 | 内容 |
|------|------|
| **必须完成** | §4 字段名与 `edit_ops.py` 一致（`sheet_name`/`new_name`）；§2.4 / §4.1 **无** as-built 未实现的 `headers` 承诺 |
| **必须完成** | §8.1 与 DESIGN §13 / TASKS 验收闸门一致（部分实现 + ST-037+ 待办） |
| **收尾** | ST-042 / ST-DOC-04 后复核 E2E 行 ✅ |

### [x] **Task ST-DOC-02** — `docs/OFFICE_MCP_SPREADSHEET_LLM_GUIDE.md`

| 字段 | 内容 |
|------|------|
| **必须完成** | `sheet_name` / `sheet_index` + A1；链接 IMPLEMENTATION_DESIGN |
| **收尾** | 实现状态随 **ST-042** / **ST-DOC-04** 更新 |

### [x] **Task ST-DOC-03** — `docs/OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_DESIGN.md` + **本文档**

| 字段 | 内容 |
|------|------|
| **必须完成** | 设计与 tasks 互链；§13–§14 checklist 与代码一致（**ST-001–057**） |

---

## Group H — 明确禁止（ST-NA）

| ID | 禁止 | 全局 |
|----|------|------|
| **ST-NA-01** | `office_read_document` → fine read 透明转发 | OT-NA-05 |
| **ST-NA-02** | edit 使用 `row` / `col` 对外字段 | ADR-015 |
| **ST-NA-03** | M3 后在 `core/` 做 Spreadsheet feature（非 bugfix） | OT-NA-09 / ADR-029 |
| **ST-NA-04** | spreadsheet legacy MCP 别名 | ADR-024 |
| **ST-NA-05** | 用 `office_read_document` 的 `elements[].index` 编辑 xlsx | LLM 指南 §3.2 |
| **ST-NA-06** | `spreadsheet/*` import word/presentation/pdf | 架构 §7.3 |

---

## Group I — UPGRADE 收尾：E2E

**Batch `T-ST-E2E` — Tasks ST-037 – ST-042** · [OFFICE_MCP_SPREADSHEET_UPGRADE.md](./OFFICE_MCP_SPREADSHEET_UPGRADE.md) §7.2

> M5 架构（Group A–F）✅；本节为 **真实 E2E** 与 OT-112 / OT-067 诚实验收。

### [x] **Task ST-037** — `test_e2e_spreadsheet_tools.py`：create → read → edit → read（xlsx）

| 字段 | 内容 |
|------|------|
| **必须完成** | 替换 placeholder `pytest.skip`；`.env.test` + DocumentServer + MCP |
| **必须完成** | `office_create_spreadsheet` 双 sheet → `office_read_spreadsheet` fine → `office_edit_spreadsheet` → re-read |
| **验收** | `-m "spreadsheet and e2e"` 至少 1 case **PASS** |
| **关联** | OT-109、OT-112；ST-014 占位补全 |

### [x] **Task ST-038** — E2E：ods 往返

| 字段 | 内容 |
|------|------|
| **必须完成** | create ods → edit → save ods（UPGRADE §7.2 #3） |

### [x] **Task ST-053** — E2E：`.xls` 读取

| 字段 | 内容 |
|------|------|
| **必须完成** | `E2E_SOURCE_PATH` 或 fixture 为 `.xls` → `office_read_spreadsheet` fine（或 ADR-021 coarse fallback） |
| **关联** | UPGRADE §7.2 #4；DESIGN §11.3 #4 |

### [x] **Task ST-039** — E2E：`office_merge_spreadsheets`

| 字段 | 内容 |
|------|------|
| **必须完成** | 合并两 xlsx；断言 sheet 总数 |
| **依赖** | **ST-048** `rename_conflicts` 若测冲突重命名 |

### [x] **Task ST-040** — E2E：`office_apply_template_spreadsheet`

| 字段 | 内容 |
|------|------|
| **必须完成** | `Summary!B2` 显式 + `{{key}}` used_range 辅助 |

### [x] **Task ST-041** — E2E：`office_read_document` xlsx csv 粗读（ST-NA-01）

| 字段 | 内容 |
|------|------|
| **必须完成** | legacy csv 粗读不变；无透明 fine 转发 |

### [x] **Task ST-042** — Gate **S-E2E**

| 字段 | 内容 |
|------|------|
| **必须完成** | ST-037–041、**ST-053** 全部 `[x]`；本文档验收闸门 E2E 行改 `[x]` |
| **必须完成** | IMPLEMENTATION_DESIGN §2.2 S-E2E ✅ |

---

## Group J — Schema / Read 接线

**Batch `T-ST-SCHEMA` — Tasks ST-043 – ST-047**

### [x] **Task ST-043** — `options.include_formulas`（`parser/workbook.py` + `tools/read.py`）

| 字段 | 内容 |
|------|------|
| **ADR-031** | **v1 实现**：`include_formulas=true` 时 sidecar 逐格 `GetFormula()` 非空则写入 `rows`；否则 `GetValue()` |
| **必须完成** | coarse 路径忽略；单测 mock 含公式格 |
| **验收** | ST-043 `[x]` |

### [x] **Task ST-044** — `options.range` read 过滤（`tools/read.py` + `parser/workbook.py`）

| 字段 | 内容 |
|------|------|
| **ADR-034** | **v1 实现** A1 range；每 sheet 裁剪；**先 range 后 max_rows** |
| **必须完成** | `apply_range_filter`；outline 更新裁剪后 `used_range` |
| **验收** | ST-044 `[x]` |

### [x] **Task ST-045** — 移除 `default_col_width`（`schemas/workbook_spec.py` + `tools/create.py`）

| 字段 | 内容 |
|------|------|
| **ADR-032** | 从 Pydantic、`TOOL_DEF`、UPGRADE/LLM **删除** `default_col_width` / `SpreadsheetCreateOptions` |
| **必须完成** | `build_create_script` 签名去掉 `options` |
| **验收** | ST-045 `[x]` |

### [x] **Task ST-046** — read `headers`（`parser/workbook.py`）

| 字段 | 内容 |
|------|------|
| **ADR-033** | `parse_workbook_json`：`rows` 非空时 **`headers = rows[0]`**（rows 仍含首行） |
| **必须完成** | create `header_row` 保持纯语义；单测双 sheet fixture |
| **验收** | ST-046 `[x]` |

### [x] **Task ST-047** — `spreadsheet/tools/edit.py` · `TOOL_DEF` operations schema

| 字段 | 内容 |
|------|------|
| **ADR-040** | `inputSchema.operations.items` 与 `edit_ops.py` 一致（10 op、`new_name`、`insert_rows.values` 等） |
| **必须完成** | 单一来源（**ADR-002** `model_json_schema`） |
| **验收** | ST-047 `[x]` |

---

## Group K — Builder 收尾

**Batch `T-ST-BUILDER` — Tasks ST-048 – ST-050**

### [x] **Task ST-048** — `builder/merge.py` · `rename_conflicts`

| 字段 | 内容 |
|------|------|
| **ADR-038** | `true`：冲突 sheet 名 `_2`/`_3`…；`false`：Builder 失败 → `{isError}` |
| **必须完成** | unit 断言 script body |
| **关联** | **ST-039** E2E |

### [x] **Task ST-049** — `builder/edit.py` · `copy_sheet`

| 字段 | 内容 |
|------|------|
| **ADR-035** | ONLYOFFICE Copy API；可选 **`new_name`** → `SetName` |
| **必须完成** | `edit_ops.py` 增 `new_name`；unit / E2E |

### [x] **Task ST-050** — `builder/template.py` · 显式 wins dedup（ADR-014 / ADR-039）

| 字段 | 内容 |
|------|------|
| **ADR-039** | 显式地址 consumed keys 跳过 `{{key}}` Search |
| **必须完成** | `test_apply_template_spreadsheet.py` 显式优先用例 |

---

## Group L — Edit 规格 gap 与 Parser 行为

**Batch `T-ST-SPEC-GAP` — Tasks ST-054 – ST-057** · DESIGN §14.2

### [x] **Task ST-054** — 空 used range（`parser/workbook.py`）

| 字段 | 内容 |
|------|------|
| **现状** | sidecar 对无 `used` 的 sheet 输出 `{rows:[]}`，**省略** `used_range` 键 |
| **必须完成** | `test_workbook_parser.py` 空 sheet fixture；UPGRADE/DESIGN §6.2 行为说明一致 |

### [x] **Task ST-055** — `add_sheet` 初始 `rows[][]`

| 字段 | 内容 |
|------|------|
| **ADR-036** | **v1 永久不支持**；Pydantic 带 `rows` 的 `add_sheet` → validation 拒绝 |
| **必须完成** | UPGRADE/LLM 已标注；单测拒绝非法 JSON |

### [x] **Task ST-056** — `insert_rows` 插行后 `values[][]`

| 字段 | 内容 |
|------|------|
| **ADR-037** | **v1 实现** 可选 `values`；shape 与 `count` 不匹配 → `{isError}` |
| **必须完成** | `edit_ops.py` + `builder/edit.py`；单测 |

### [x] **Task ST-057** — `set_range` 规格 + M6 registry

| 字段 | 内容 |
|------|------|
| **set_range** | **ADR-037** §4：确认 as-built 仅 `range`+`values`；UPGRADE 无 anchor 备选 |
| **M6** | `test_registry.py` / 验收命令断言终态 **23/27** 含 spreadsheet×5（ST-036 仅 M5 **18/22**） |

---

## Group M — 文档与卫生

**Batch `T-ST-HYGIENE` — ST-051、ST-DOC-04**

### [x] **Task ST-051** — `test_edit_builder.py`（可选但推荐）

| 字段 | 内容 |
|------|------|
| **说明** | Word 有 `test_edit_builder.py`；Spreadsheet 可补 `build_edit_script` / `build_merge_script` 断言 |
| **必须完成** | 至少覆盖 ST-048–049 改动的 builder 行 |

### [x] **Task ST-DOC-04** — Gate / E2E / gap 文档同步

| 字段 | 内容 |
|------|------|
| **必须完成** | IMPLEMENTATION_DESIGN §2.2 / §11.3 / §13–§14；UPGRADE §8.1；LLM_GUIDE §8 |
| **必须完成** | ST-054–057 收口后更新 §14.2 表 |
| **必须完成** | 全局 OT-112 脚注：Spreadsheet DS E2E 完成（ST-042） |

---

## 新建文件总览

### `aiecs/tools/office_tool/spreadsheet/`

| 文件 | 阶段 | ST |
|------|------|-----|
| `__init__.py` | S0 | ST-001 |
| `parser/csv.py` | S0 | ST-003 |
| `parser/workbook.py` | S1 | ST-010 |
| `schemas/read.py` | S0/S1 | ST-004 |
| `schemas/workbook_spec.py` | S2 | ST-017 |
| `schemas/edit_ops.py` | S3/S4 | ST-022 |
| `builder/create.py` | S2 | ST-018 |
| `builder/edit.py` | S3 | ST-023 |
| `builder/merge.py` | S4 | ST-028 |
| `builder/template.py` | S4 | ST-029 |
| `tools/read.py` | S0/S1 | ST-005, ST-011 |
| `tools/create.py` | S2 | ST-019 |
| `tools/edit.py` | S3 | ST-024 |
| `tools/merge.py` | S4 | ST-030 |
| `tools/template.py` | S4 | ST-030 |

### `tests/office_mcp/spreadsheet/`

| 文件 | 阶段 | ST |
|------|------|-----|
| `test_csv_parser.py` | S0 | ST-008 |
| `test_workbook_parser.py` | S1 | ST-012 |
| `test_read_spreadsheet.py` | S1 | ST-013 |
| `test_create_spreadsheet.py` | S2 | ST-020 |
| `test_schemas.py` | S3 | ST-025 |
| `test_edit_spreadsheet.py` | S3 | ST-026 |
| `test_merge_spreadsheets.py` | S4 | ST-031 |
| `test_apply_template_spreadsheet.py` | S4 | ST-031 |
| `test_edit_builder.py` | M | ST-051 |
| `test_e2e_spreadsheet_tools.py` | S1+ | ST-014 |
| `fixtures/workbook_sidecar.json` | M5 | ST-035 |

---

## ST ↔ OT 对照表

| Spreadsheet Batch | ST 范围 | 全局 OT |
|-------------------|---------|---------|
| S0 | ST-001 – ST-009 | OT-100–101, 105(部分), 110 |
| S1 | ST-010 – ST-016 | OT-102, 108–109, 111 |
| S2 | ST-017 – ST-021 | OT-103–105(部分) |
| S3 | ST-022 – ST-027 | OT-103–105(部分) |
| S4 | ST-028 – ST-032 | OT-104–105(部分) |
| M5 | ST-033 – ST-036 | OT-106–112 |
| DOC | ST-DOC-* | OT-004, 008 |
| **E2E** | **ST-037 – ST-042, ST-053** | OT-109, OT-112 |
| **SCHEMA** | ST-043 – ST-047 | ADR-031–034、032、033、040 |
| **BUILDER** | ST-048 – ST-050 | ADR-038–039 |
| **SPEC-GAP** | ST-054 – ST-057 | ADR-036–037、DESIGN §14 |
| **HYGIENE** | ST-051, ST-DOC-04 | — |

---

## 验收闸门（Spreadsheet）

| 闸门 | 条件 | ST |
|------|------|-----|
| **S0** | csv 粗读 + legacy 回归 | ST-009 |
| **S1** | fine read sidecar + parser unit | ST-016 |
| **S2** | create + workbook_spec unit | ST-021 |
| **S3** | edit 10 op + schemas unit | ST-027 |
| **S4** | merge + template unit | ST-032 |
| **M5** | registry 18/22；`[Spreadsheet]`；`tests/spreadsheet/` | ST-036 |
| **S-E2E** | DS 自动化 E2E（ST-037–041、ST-053） | **ST-042** |

**命令：**

```bash
poetry run pytest tests/office_mcp/spreadsheet/ -v -m "not e2e"
DOCUMENTSERVER_URL=... DOCUMENTSERVER_JWT_SECRET=... \
  poetry run pytest tests/office_mcp/spreadsheet/ -v -m "spreadsheet and e2e"
python3 -c "
from aiecs.tools.office_tool.registry import collect_office_tools, get_handlers
s = {'office_read_spreadsheet','office_create_spreadsheet','office_edit_spreadsheet',
     'office_merge_spreadsheets','office_apply_template_spreadsheet'}
assert s <= {t['name'] for t in collect_office_tools()}
print('OK:', len(collect_office_tools()), len(get_handlers()))
"
! rg "word|presentation|pdf" aiecs/tools/office_tool/spreadsheet/ --glob "*.py" \
  | rg "^import|^from" && echo "FAIL" || echo "OK: spreadsheet isolated"
```

- [x] **S0–S4** unit 全绿（52 tests）
- [x] **S-E2E** spreadsheet（ST-037–042、**ST-053**；DS/能力探针 skip，无 test-body placeholder skip）
- [x] **M5** spreadsheet canonical ∈ `list_tools`（**18/22**）
- [x] **M6** registry 终态 **23/27** 含 sheet×5（**ST-057**）
- [x] **`office_read_document`** xlsx/xls/ods csv unit 回归（DS E2E → ST-041）
- [x] **Schema 接线**（ST-047；ST-043–046 ✅）
- [x] **Builder 收尾**（ST-048–050）
- [x] **Edit 规格 gap**（ST-054–057）
- [x] **文档 Gate 诚实**（ST-DOC-04）

---

## 维护说明

**本文档** 为 [OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_DESIGN.md](./OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_DESIGN.md) 的**按文件执行清单**；与全局 [OFFICE_TOOL_IMPLEMENTATION_TASKS_BY_FILE.md](./OFFICE_TOOL_IMPLEMENTATION_TASKS_BY_FILE.md) 冲突时，以 **ADR 已采纳项** → Spreadsheet 实现设计 → 全局 tasks 为准。

**建议 PR 顺序：** S0 → S1 → S2 → S3 → S4 → M5（已完成）→ **ST-037–042、ST-053（E2E）** → ST-043–047（schema）→ ST-048–050（builder）→ **ST-054–057（spec gap + M6）** → ST-051 / ST-DOC-04。

**UPGRADE 收尾优先级：** ST-037–042、ST-053（E2E）> ST-043–047（schema/TOOL_DEF）> ST-048–050（merge/copy/template）> **ST-054–057** > ST-DOC-04。

**AI 编程 prompt（未完成 Task）：** [AI_PROMPT_OFFICE_MCP_SPREADSHEET_IMPLEMENTATION.md](./AI_PROMPT_OFFICE_MCP_SPREADSHEET_IMPLEMENTATION.md)（ST-037–057、ST-DOC-04；一次一个 Batch）。

**单 PR 模板：** 见 Spreadsheet 实现设计 [附录 A](./OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_DESIGN.md#附录-a单-pr-回归模板spreadsheet-_touch)。
