# Office MCP Spreadsheet — Implementation Design

Spreadsheet 垂直模块的**可执行实现设计**：在 [OFFICE_MCP_SPREADSHEET_UPGRADE.md](./OFFICE_MCP_SPREADSHEET_UPGRADE.md)（What/规格）与 [implementation_design.md](./implementation_design.md)（全局 How）基础上，给出 **M5 S0–S4** 的文件级任务、API 签名、Pydantic schema、sidecar/Builder 脚本模板、测试与验收标准。

> **状态**：Implementation design（待开发）  
> **读者**：Spreadsheet 模块实现工程师、Reviewers  
> **前置**：**M0**（`core/builder_runtime`）、**M1**（`core/categories`、`coarse_read`、`read_response`、`errors`）、**M3**（`registry.py`）必须合并  
> **架构约束**：[OFFICE_TOOL_ARCHITECTURE_REORG.md](./OFFICE_TOOL_ARCHITECTURE_REORG.md) §2、§7.3

---

## 1. 文档关系

| 文档 | 本设计如何使用 |
|------|----------------|
| [OFFICE_MCP_SPREADSHEET_UPGRADE.md](./OFFICE_MCP_SPREADSHEET_UPGRADE.md) | 工具参数、sheets schema、operations、LLM 工作流 — **规格源** |
| [implementation_design.md](./implementation_design.md) | Core API（§4）、registry（§5）、统一 read（§6）、M5 任务（§9） — **全局约束** |
| [OFFICE_TOOL_ARCHITECTURE_REORG.md](./OFFICE_TOOL_ARCHITECTURE_REORG.md) | 目录树、依赖方向、legacy 粗读策略 |
| [ADR.md](./ADR.md) | Spreadsheet 相关已采纳决策（见 §2） |
| [OFFICE_MCP_SPREADSHEET_LLM_GUIDE.md](./OFFICE_MCP_SPREADSHEET_LLM_GUIDE.md) | 实现完成后同步 A1/range 示例与 `_locator_note` |

**分工**：UPGRADE = 产品/LLM 规格；**本文档** = 工程师 checklist；`implementation_design.md` = 四类垂直 + core 总表。

---

## 2. 已采纳 ADR（Spreadsheet 实现必须遵守）

| ADR | 决策 | 实现落点 |
|-----|------|----------|
| **ADR-002** | MCP 参数用 Pydantic v2 | `spreadsheet/schemas/*` |
| **ADR-006** | 统一 `{isError}` / `{success}` | 全部 handler 经 `core/errors.py` |
| **ADR-013** | sidecar 用 **`GetSheetsCount()` + for**；不可用则 fine E2E skip | `parser/workbook.py` extract_body + CI 探针 |
| **ADR-014** | 模板：显式 `Sheet!A1` 优先；`{{key}}` 仅 **used_range** 内 Search | `builder/template.py` |
| **ADR-015** | schema **弃用 `row`/`col`**；对外 **`cell` / `range`（A1）** | `edit_ops.py`；builder 内部 `GetRangeByNumber` 仍 0-based |
| **ADR-021** | DS 能力探针；无 `GetSheetsCount` → fine read E2E skip | `tests/office_mcp/probe_ds_capabilities.py` |
| **ADR-024** | `list_tools` **M6 终态** 23 canonical；无 spreadsheet legacy 别名 | 五工具仅 canonical；**M5 后 registry 18/22** |
| **ADR-025** | description 前缀 `[Spreadsheet]` | 五个 canonical spreadsheet 工具 |
| **ADR-028** | `build_read_response` M1 blocking | `spreadsheet/tools/read.py` |
| **ADR-029** | M3 后 core 严格 freeze | 新需求不得改 core 行为 |

---

## 3. 交付范围与验收（S0–S4）

### 3.1 工具清单

| 工具 | 模块 | 阶段 | 验收 |
|------|------|------|------|
| `office_read_spreadsheet` | `spreadsheet/tools/read.py` | S0–S1 | coarse csv + fine multi-sheet；`sheets[]` ≡ `units[]` |
| `office_create_spreadsheet` | `spreadsheet/tools/create.py` | S2 | xlsx/ods 双 sheet 创建 + E2E read |
| `office_edit_spreadsheet` | `spreadsheet/tools/edit.py` | S3 | core ops + A1/range schema |
| `office_merge_spreadsheets` | `spreadsheet/tools/merge.py` | S4 | 追加 sheet；冲突重命名 |
| `office_apply_template_spreadsheet` | `spreadsheet/tools/template.py` | S4 | 显式地址 + `{{key}}` ADR-014 |

**无 spreadsheet legacy 别名**：`office_read_document` 保留全类别 csv 粗读；description 指向 `office_read_spreadsheet`。

### 3.2 Release Gates

| Gate | 条件 |
|------|------|
| **S0** | `spreadsheet/` 树 + `parser/csv.py` + read coarse；legacy xlsx csv 回归 |
| **S1** | fine read sidecar + `parser/workbook.py`；E2E 多 sheet xlsx（或 DS 不支持则 skip + coarse 绿） |
| **S2** | `office_create_spreadsheet` E2E xlsx + ods |
| **S3** | edit：`set_cell` / `set_range` / `add_sheet` 闭环 |
| **S4** | merge + template + registry 五工具；health 列表含 spreadsheet |

---

## 4. 目录与迁移映射

### 4.1 目标树

```
aiecs/tools/office_tool/spreadsheet/
├── __init__.py
├── parser/
│   ├── csv.py                    # ← html_parser.parse_csv_*
│   └── workbook.py               # NEW: sidecar JSON → sheets[]
├── builder/
│   ├── create.py
│   ├── edit.py
│   ├── merge.py
│   └── template.py
├── schemas/
│   ├── read.py
│   ├── workbook_spec.py
│   └── edit_ops.py
└── tools/
    ├── read.py
    ├── create.py
    ├── edit.py
    ├── merge.py
    └── template.py
```

### 4.2 自现有代码迁移（S0）

| 现路径 | 新路径 | S0 动作 |
|--------|--------|---------|
| `html_parser.parse_csv_to_structure` | `spreadsheet/parser/csv.py` | 移动函数；根/html_parser shim re-export |
| `html_parser.extract_outline_from_csv` | `spreadsheet/parser/csv.py` | 同上 |
| — | `legacy/read_document.py` | 改 import 指向 `spreadsheet/parser/csv.py`（M1 coarse_read 已封装则经 core） |

**S0 禁止**：改变 `office_read_document` 对 xlsx/xls/ods 的 csv 粗读行为。

### 4.3 依赖规则

```
spreadsheet/tools/*  →  spreadsheet/builder/*, schemas/*, parser/*, core/*
spreadsheet/builder/*  →  core/builder_js, core/builder_runtime
spreadsheet/parser/*  →  stdlib + csv；workbook.py 无 DS 调用
spreadsheet/*  ↛  word|presentation|pdf
```

---

## 5. Pydantic Schemas（ADR-002 / ADR-015）

### 5.1 `schemas/read.py`

```python
class SpreadsheetReadOptions(BaseModel):
    read_mode: Literal["fine", "coarse"] = "fine"
    sheet_names: list[str] | None = None
    max_rows: int | None = Field(default=None, ge=1)
    include_formulas: bool = False
    range: str | None = None  # 可选：限制每 sheet 返回区域，如 "A1:D100"

class SpreadsheetReadArgs(BaseModel):
    source_path: str | None = None
    source_url: str | None = None
    format: Literal["structured", "outline", "text"] = "structured"
    options: SpreadsheetReadOptions = Field(default_factory=SpreadsheetReadOptions)
```

校验：`classify_file_ext(ext) == "spreadsheet"`（csv/tsv 允许 coarse 只读）。

### 5.2 `schemas/workbook_spec.py`

```python
class SheetSpec(BaseModel):
    name: str = Field(min_length=1, max_length=31)  # Excel sheet 名长度
    rows: list[list[Any]] = Field(min_length=1)
    header_row: bool = False

class SpreadsheetCreateOptions(BaseModel):
    default_col_width: float | None = Field(default=None, gt=0)

class SpreadsheetCreateArgs(BaseModel):
    sheets: list[SheetSpec] = Field(min_length=1)
    output_path: str
    options: SpreadsheetCreateOptions = Field(default_factory=SpreadsheetCreateOptions)
```

### 5.3 `schemas/edit_ops.py`

**Sheet 定位**（各 op 共用）：

```python
class SheetLocator(BaseModel):
    sheet_index: int | None = Field(default=None, ge=0)
    sheet_name: str | None = None

    @model_validator(mode="after")
    def exactly_one(self) -> Self:
        # sheet_index XOR sheet_name（部分 op 仅 name，如 add_sheet）
        ...
```

**Op 枚举**（v1）：

```python
OpName = Literal[
    "set_cell", "set_range", "clear_range",
    "insert_rows", "delete_rows",
    "add_sheet", "delete_sheet", "rename_sheet",
    "set_formula", "copy_sheet",
]
```

**ADR-015 — 对外字段**：

| op | LLM 面向字段 | 禁止/弃用 |
|----|--------------|-----------|
| `set_cell` | `cell: str`（A1）, `value` | 无 `row`/`col` |
| `set_range` | `range: str` 或 anchor + `values[][]` | 无 `row`/`col` |
| `clear_range` | `range` | — |
| `set_formula` | `cell`, `formula` | — |
| `insert_rows` | `at_row`（**1-based Excel 行号**）, `count`, `values[][]?` | 内部转 0-based |
| `delete_rows` | `from_row`（1-based）, `count` | 内部转 0-based |

`insert_rows` / `delete_rows` 的 `at_row`/`from_row` 为 **Excel UI 1-based**；`builder/edit.py` 调用 `GetRangeByNumber(at_row - 1, ...)`。

```python
class EditOperation(BaseModel):
    op: OpName
    # sheet_index | sheet_name via SheetLocator mixin fields
    ...

class SpreadsheetEditArgs(BaseModel):
    source_path: str | None = None
    source_url: str | None = None
    output_path: str
    operations: list[EditOperation] = Field(min_length=1)
    options: SpreadsheetEditOptions = Field(default_factory=SpreadsheetEditOptions)
```

### 5.4 Merge / Template

```python
class SpreadsheetMergeOptions(BaseModel):
    rename_conflicts: bool = True  # sheet 名冲突 → suffix _2, _3

class SpreadsheetMergeArgs(BaseModel):
    source_paths: list[str] | None = None
    source_urls: list[str] | None = None
    output_path: str
    options: SpreadsheetMergeOptions = Field(default_factory=SpreadsheetMergeOptions)

class SpreadsheetTemplateArgs(BaseModel):
    template_path: str | None = None
    template_url: str | None = None
    data: dict[str, Any]  # keys: "Sheet!A1" 和/或 "{{key}}" 辅助键
    output_path: str
```

---

## 6. Parser

### 6.1 `parser/csv.py`

```python
def parse_csv_to_structure(text: str) -> dict:
    """自 html_parser 迁入；签名不变。"""

def extract_outline_from_csv(text: str) -> list[dict]:
    """首行作 outline。"""

def csv_to_coarse_sheets(text: str) -> list[dict]:
    """
    粗读：单 sheet 快照 → [{sheet_index: 0, name: "Sheet1", rows, ...}]
    附 _note：多 sheet 可能丢失
    """
```

### 6.2 `parser/workbook.py`

```python
def parse_workbook_json(raw: dict | str) -> list[dict]:
    """
    sidecar JSON { sheets: [...] } → 规范化 sheets[]。
    每项: sheet_index, name, used_range, row_count, col_count,
          headers?, rows[][], formulas? (include_formulas)
    """

def sheets_to_outline(sheets: list[dict]) -> list[dict]:
    """{sheet_index, name, used_range} only"""

def sheets_to_text(sheets: list[dict]) -> str:
    """TSV 风格拼接，sheet 间 --- name --- 分隔"""

def parse_a1(cell: str) -> tuple[int, int]:
    """A1 → (row_0based, col_0based) for builder internal use"""

def parse_range(range_str: str) -> tuple[int, int, int, int]:
    """B2:D5 → (r0, c0, r1, c1) 0-based inclusive"""
```

**规范化规则**：

1. `headers`：若 sidecar 无 headers 且 `rows` 非空，可选首行作 headers（read options 控制）。
2. `max_rows`：截断 `rows`；`extra._truncated = true`。
3. `sheet_names` filter：只保留匹配 name 的 sheet。

### 6.3 Sidecar extract_body（**ADR-013**）

置于 `spreadsheet/parser/workbook.py` 或 `spreadsheet/builder/read_sidecar.py`：

```javascript
builder.OpenFile("{url}", "{ext}");
var out = { sheets: [] };
var count = Api.GetSheetsCount();
for (var i = 0; i < count; i++) {
  var ws = Api.GetSheet(i);
  var name = ws.GetName();
  var used = ws.GetUsedRange();
  if (!used) {
    out.sheets.push({ sheet_index: i, name: name, rows: [], used_range: null });
    continue;
  }
  // 迭代 used.GetRows().length / GetCols().length
  // GetValue() 或 GetText()；include_formulas 时 GetFormula()
  var rows = [];
  // ... fill rows[][]
  out.sheets.push({
    sheet_index: i,
    name: name,
    rows: rows,
    used_range: used.GetAddress()  // 或手动拼 A1:Dn
  });
}
var jsonStr = JSON.stringify(out);
// 注入 core/builder_json_sidecar 写 txt sidecar
builder.CloseFile();
```

**DS 探针**（**ADR-021**）：session fixture 检测 `GetSheetsCount`；不可用则 `@pytest.mark.spreadsheet` fine E2E skip，coarse 仍跑。

---

## 7. Builder 脚本生成

扩展名：`builder_file_ext(output_path)` → `"xlsx"` / `"ods"` / `"xls"`。

### 7.1 `builder/create.py`

```python
def build_create_script(
    sheets: list[SheetSpec],
    *,
    output_ext: str,
    options: SpreadsheetCreateOptions,
) -> str:
    """
    1. CreateFile(output_ext)
    2. 第一 sheet: GetActiveSheet().SetName + SetValue data
    3. 后续: Api.AddSheet() / GetSheet(i) ...
    4. SaveFile(output_ext, "output.{ext}")
    """
```

**Sheet 数据写入**（参考 ONLYOFFICE filling_spreadsheet sample）：

```javascript
var data = [["Product","Units"], ["A", 120]];
var ws = Api.GetActiveSheet();
ws.SetName("Summary");
var start = ws.GetRangeByNumber(0, 0);
var end = ws.GetRangeByNumber(data.length - 1, data[0].length - 1);
ws.GetRange(start, end).SetValue(data);
```

### 7.2 `builder/edit.py`

```python
def build_edit_script(
    operations: list[EditOperation],
    *,
    file_ext: str,
) -> str:
    """edit body only；run_builder_on_source 注入 Open/Save"""
```

| op | Builder 策略 |
|----|--------------|
| `set_cell` | `_resolve_sheet(loc)` → `GetRange("B3")` 或 `GetRangeByNumber` → `SetValue` |
| `set_range` | `GetRange("A2:C2")` → `SetValue(values)` 二维 |
| `clear_range` | `GetRange(...).Clear()` |
| `insert_rows` | `InsertRows(at_row_0based, count)` + 可选 SetValue |
| `delete_rows` | `DeleteRows(from_row_0based, count)` |
| `add_sheet` | `AddSheet()` + SetName + 可选 SetValue |
| `delete_sheet` | `DeleteSheet()` / API 等价 |
| `rename_sheet` | `SetName` |
| `set_formula` | `GetRange(cell).SetFormula(formula)` |
| `copy_sheet` | `Copy` + `SetName` |

**Sheet 解析**：

```python
def _emit_resolve_sheet(loc: SheetLocator) -> str:
    # sheet_index → Api.GetSheet(i)
    # sheet_name → 循环 GetSheetsCount 匹配 GetName()，或 GetSheetByName 若 API 存在
```

### 7.3 `builder/merge.py`

```python
def build_merge_script(
    source_urls: list[str],
    source_exts: list[str],
    *,
    output_ext: str,
    rename_conflicts: bool = True,
) -> str:
    """
    1. CreateFile(output_ext) → 空目标 wb
    2. 对每个源 OpenFile → 遍历 sheets → Copy/Append 到目标
    3. sheet 名冲突：rename_conflicts → name + "_2"
    4. SaveFile(output_ext, ...)
    """
```

### 7.4 `builder/template.py`（**ADR-014**）

```python
def build_template_script(
    data: dict[str, Any],
    *,
    file_ext: str,
) -> str:
    """
    阶段 1 — 显式地址（优先）:
      解析 "Summary!B2" → GetSheet + GetRange → SetValue
    阶段 2 — {{key}} 辅助（仅未在阶段 1 消费的 key）:
      各 sheet GetUsedRange() 内 SearchAndReplace("{{key}}", value)
    显式与 {{key}} 同 key 冲突 → 显式 wins（不再 Search）
    """
```

**地址解析**：

```python
def split_sheet_ref(ref: str) -> tuple[str, str]:
    """'Summary!B2' → ('Summary', 'B2')；无 ! 则 active sheet 或报错"""
```

---

## 8. Tool Handlers

每个 `spreadsheet/tools/*.py` 导出：`TOOL_NAME`, `TOOL_DEF`, `handler`。

### 8.1 `tools/read.py` — `office_read_spreadsheet`

```python
async def office_read_spreadsheet(...) -> dict:
    # 1. SpreadsheetReadArgs validate
    # 2. resolve source；assert spreadsheet category
    # 3. read_mode=fine:
    #      read_sidecar_json(..., extract_body=WORKBOOK_SIDECAR_BODY)
    #      sheets = parse_workbook_json(raw)
    #      filter sheet_names / max_rows / range
    #      build_read_response(category="spreadsheet", units=sheets, read_mode="fine",
    #        locator_note="Edit with office_edit_spreadsheet: sheet_name or sheet_index + cell (A1) or range.")
    # 4. read_mode=coarse:
    #      convert_and_fetch(output_type=csv) → csv_to_coarse_sheets
    #      build_read_response(read_mode="coarse", _note 警告单 sheet)
    # 5. format=outline / text 分支
```

**Mirror**：`build_read_response` 须填充 `sheets[]` 与 `units[]` 相同内容（架构 §4）。

**Description**：`[Spreadsheet] ...`（**ADR-025**）。

### 8.2 `tools/create.py` — `office_create_spreadsheet`

```python
async def office_create_spreadsheet(...) -> dict:
    args = SpreadsheetCreateArgs.model_validate(...)
    script = build_create_script(args.sheets, output_ext=builder_file_ext(...), ...)
    return await run_builder_script(script, output_path=args.output_path, client=client)
```

### 8.3 `tools/edit.py` — `office_edit_spreadsheet`

```python
async def office_edit_spreadsheet(...) -> dict:
    args = SpreadsheetEditArgs.model_validate(...)
    body = build_edit_script(args.operations, file_ext=ext)
    return await run_builder_on_source(
        fetch_url, file_ext, body, args.output_path,
        backup_source_path=...,
        client=client,
    )
```

### 8.4 `tools/merge.py` / `tools/template.py`

- **merge**：resolve 多源 signed URL → `build_merge_script` → `run_builder_script`
- **template**：resolve template → `build_template_script` → `run_builder_on_source`

---

## 9. Registry（M5-S4）

在 `registry.py` 的 `OFFICE_TOOL_MODULES` 追加：

```python
"aiecs.tools.office_tool.spreadsheet.tools.read",
"aiecs.tools.office_tool.spreadsheet.tools.create",
"aiecs.tools.office_tool.spreadsheet.tools.edit",
"aiecs.tools.office_tool.spreadsheet.tools.merge",
"aiecs.tools.office_tool.spreadsheet.tools.template",
```

- `collect_office_tools()`：五工具 canonical（序号 14–18，见 implementation_design §12）；**M5 后共 18 canonical**
- `get_handlers()`：**M5 后 22**（18 canonical + 4 legacy）
- 无 spreadsheet legacy handler

---

## 10. 测试计划

### 10.1 目录

```
tests/office_mcp/spreadsheet/
├── test_csv_parser.py              # 自 flat test 迁入 csv 部分
├── test_workbook_parser.py         # sidecar JSON fixtures
├── test_a1_utils.py                # parse_a1 / parse_range
├── test_read_spreadsheet.py
├── test_create_spreadsheet.py
├── test_edit_spreadsheet.py
├── test_merge_spreadsheets.py
├── test_apply_template_spreadsheet.py
├── test_schemas.py                 # ADR-015：无 row/col on set_cell
└── test_e2e_spreadsheet_tools.py   # @pytest.mark.spreadsheet @pytest.mark.e2e
```

### 10.2 单元测试要点

| 文件 | 用例 |
|------|------|
| `test_workbook_parser.py` | 双 sheet；空 sheet；used_range 缺失；max_rows 截断 |
| `test_schemas.py` | `set_cell` 缺 `cell` 拒绝；`row`/`col` 字段不存在；`Sheet!A1` template data |
| `test_a1_utils.py` | `B3` → (2,1)；`AA10`；invalid |
| `test_apply_template_spreadsheet.py` | 显式优先于 `{{key}}`；used_range 外不替换 |

### 10.3 E2E 清单

1. **create xlsx** 双 sheet → **read fine** → `unit_count == 2`  
2. **edit**：`set_cell` B3 + `set_range` + `add_sheet` → re-read 验证  
3. **ods 往返**：create ods → edit → save ods  
4. **xls 读取**：open xls → read fine 或 coarse  
5. **merge** 两个 xlsx → sheet 总数 = 源1 + 源2（减冲突重命名）  
6. **template**：`Summary!B2` + `{{label}}` used_range 辅助  
7. **legacy**：`office_read_document` xlsx → csv `elements[]` 不变  
8. **DS 无 GetSheetsCount**：fine E2E skip；coarse 仍 pass  

```bash
DOCUMENTSERVER_URL=... DOCUMENTSERVER_JWT_SECRET=... \
  poetry run pytest tests/office_mcp/spreadsheet/ -v -m "spreadsheet and e2e"
```

---

## 11. PR 分解建议

| PR | 内容 | Verify |
|----|------|--------|
| **PR-S0** | `spreadsheet/` 树；`parser/csv.py`；read coarse；legacy import 更新 | `test_office_read*` 绿 |
| **PR-S1** | sidecar extract + `workbook.py` + read fine | unit + E2E multi-sheet |
| **PR-S2** | `workbook_spec` + `builder/create` + `office_create_spreadsheet` | E2E xlsx/ods |
| **PR-S3** | `edit_ops` + `builder/edit` + `office_edit_spreadsheet` | E2E edit 闭环 |
| **PR-S4** | merge + template + registry 注册 | merge/template E2E + `test_registry` **M5: 18/22** |

S2/S3 可合并若 review 带宽允许。

---

## 12. 实现检查清单（Copy for PR description）

### S0

- [ ] `spreadsheet/parser/csv.py` 自 `html_parser` 迁入
- [ ] `office_read_spreadsheet` coarse 路径
- [ ] `legacy/read_document` spreadsheet 仍 csv
- [ ] 根 shim / coarse_read import 更新

### S1

- [ ] sidecar JS：`GetSheetsCount()` + for（**ADR-013**）
- [ ] `parse_workbook_json` + fixtures
- [ ] `build_read_response` sheets/units mirror
- [ ] DS 探针 + fine E2E skip 逻辑

### S2

- [ ] Pydantic `workbook_spec`
- [ ] `office_create_spreadsheet` xlsx + ods E2E

### S3

- [ ] `edit_ops` A1/range only（**ADR-015**）
- [ ] `insert_rows`/`delete_rows` 1-based → 0-based 转换
- [ ] E2E set_cell / set_range / add_sheet

### S4

- [ ] `office_merge_spreadsheets` + conflict rename
- [ ] `office_apply_template_spreadsheet`（**ADR-014**）
- [ ] registry 五模块 + `[Spreadsheet]` 前缀
- [ ] `test_registry` **M5: 18/22**（非终态 23/27）

---

## 13. 风险与实现备注

| 项 | 备注 |
|----|------|
| csv 粗读丢 sheet | fine 默认；coarse `_note` 必显 |
| sidecar 超时/体积 | `max_rows`；outline；可选 `options.range` |
| 公式 vs 值 | `include_formulas`；edit 用 `set_formula` |
| xls 限制 | E2E 覆盖；新建推荐 xlsx/ods |
| GetSheetsCount 不可用 | ADR-021 skip fine；文档说明多 sheet 编辑不可用 |
| A1 与 row 混淆 | schema 无 row/col；LLM 指南仅 A1 |

---

## 14. 参考

- 规格：[OFFICE_MCP_SPREADSHEET_UPGRADE.md](./OFFICE_MCP_SPREADSHEET_UPGRADE.md)
- 全局实现：[implementation_design.md](./implementation_design.md) §4、§6、§7.3、§9 M5
- 架构：[OFFICE_TOOL_ARCHITECTURE_REORG.md](./OFFICE_TOOL_ARCHITECTURE_REORG.md) §7.3
- ADR：[ADR.md](./ADR.md) ADR-002、006、013–015、021、024–025、028–029
- 现码：`html_parser.parse_csv_to_structure`、`read_document.py`
- ONLYOFFICE：[Spreadsheet API](https://api.onlyoffice.com/docs/office-api/usage-api/spreadsheet-api/)
