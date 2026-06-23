# Office MCP Spreadsheet Upgrade

让 LLM 对 **Spreadsheet 类**文档（重点：`.ods`、`.xlsx`、`.xls`）进行**精细化创建**与**精细化编辑**的升级设计。

> **状态**：**部分实现**（M5 架构 S0–S4 + unit ✅）；**收尾待办**（S-E2E、schema/Builder 接线、edit 规格 gap）见 [IMPLEMENTATION_DESIGN](./OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_DESIGN.md) §2.2 / [TASKS BY FILE](./OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_TASKS_BY_FILE.md) **ST-037–057**  
> **范围**：`aiecs/tools/office_tool/spreadsheet/`（新架构垂直模块）  
> **依赖**：ONLYOFFICE DocumentServer Document Builder + Conversion API；`core/` 公共层  
> **MCP 参数真源**：`spreadsheet/schemas/*` + 各 `tools/*/TOOL_DEF`（见 [IMPLEMENTATION_DESIGN §14](./OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_DESIGN.md#14-与-upgrade--llm-指南同步说明)）  
> **关联**：[OFFICE_TOOL_ARCHITECTURE_REORG.md](./OFFICE_TOOL_ARCHITECTURE_REORG.md)、[OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_DESIGN.md](./OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_DESIGN.md)（实现设计）、[OFFICE_MCP_SPREADSHEET_LLM_GUIDE.md](./OFFICE_MCP_SPREADSHEET_LLM_GUIDE.md)、[OFFICE_MCP_WORD_UPGRADE.md](./OFFICE_MCP_WORD_UPGRADE.md)（平行类别参考）

本升级是架构重组 **M5 阶段**的 spreadsheet 垂直交付，遵循 `office_{action}_{category}` 命名，`category = spreadsheet`。

---

## 1. 背景与目标

### 1.1 问题

当前 Office MCP 对 spreadsheet 的支持**最弱**，且无专用工具：

| 能力 | 现状 | 问题 |
|------|------|------|
| **读取** | `office_read_document` → Conversion → **csv** → `parse_csv_to_structure` | 仅扁平行列表；**多 sheet 丢失**；无 `A1`/列名语义 |
| **创建** | 仅 `office_execute_builder` 手写 JS | 无声明式 workbook spec |
| **编辑** | 无专用工具；`office_edit_document` 为 Word API | LLM 无法改单元格 |
| **合并 / 模板** | 无 | — |
| **读→改闭环** | **不可用** | csv `elements[].index` 是行号，与 Builder 无稳定映射 |

LLM 无法可靠完成：「改 Sheet2 的 B3」「追加一行销售数据」「从模板 xlsx 填 Q1 数字」「创建 ods 含两个 sheet」等任务。

### 1.2 目标（Must Have）

1. **精细化读取**（`office_read_spreadsheet`）：workbook → `sheets[]`，每 sheet 含 `used_range`、`headers`（**ADR-033**：首行镜像）、`rows[][]`、行列计数；定位符 **`sheet_index` / `sheet_name` + `cell`（A1）或 `range`**（**ADR-015**）。`options.include_formulas`（**ADR-031**）、`options.range`（**ADR-034**）已实现（**ST-043–044**）。
2. **精细化创建**（`office_create_spreadsheet`）：声明式 `sheets[{name, rows[][]}]` → `.xlsx` / `.ods` / `.xls`。
3. **精细化编辑**（`office_edit_spreadsheet`）：声明式 `operations[]`（`set_cell`、`set_range`、`add_sheet` 等）。
4. **格式覆盖**：至少 **`.ods`、`.xlsx`、`.xls`**；并支持 `core/categories.py` 中 `SPREADSHEET_EXTENSIONS`（含 csv/tsv 只读场景）。
5. **架构对齐**：`spreadsheet/{parser,builder,schemas,tools}/`；`core/builder_runtime.py`；`registry.py` 注册。
6. **向后兼容**：`legacy/read_document` 对 xlsx 仍走 csv 粗读。

### 1.3 非目标（Out of Scope v1）

-  pivot 表、宏/VBA、复杂条件格式全量编辑
-  公式引擎级操作（v1 可 **写入公式字符串** 如 `=SUM(A1:A10)`，不保证重算语义文档化）
-  图表系列数据精细改（v1 仅识别 chart 存在）
-  实时协同编辑
-  将 **`.xls`** 作为推荐**新建**格式（可读可写；新建推荐 `.xlsx` 或 `.ods`）

---

## 2. 在新架构中的位置

### 2.1 分层与依赖

```mermaid
flowchart TB
    subgraph MCP["MCP 层"]
        Registry[registry.py]
    end

    subgraph SheetTools["spreadsheet/tools/*"]
        ReadT[read.py]
        CreateT[create.py]
        EditT[edit.py]
        MergeT[merge.py]
        TemplateT[template.py]
    end

    subgraph SheetDomain["spreadsheet 领域层"]
        ParserCSV[parser/csv.py]
        ParserWB[parser/workbook.py]
        Builder[builder/create|edit|merge|template.py]
        Schemas[schemas/*]
    end

    subgraph Core["core/"]
        Runtime[builder_runtime.py]
        Sidecar[builder_json_sidecar.py]
        CoarseRead[coarse_read.py]
        Categories[categories.py]
    end

    Registry --> SheetTools
    SheetTools --> SheetDomain
    SheetTools --> Core
    SheetDomain --> Core
```

**依赖约束**：`spreadsheet/` 仅 import `core/`；不 import `word/` / `presentation/` / `pdf/`。

### 2.2 双轨读取策略

| 模式 | 工具 | 路径 | 用途 |
|------|------|------|------|
| **精读（structured）** | `office_read_spreadsheet` | Builder **`GetSheetsCount()` + for** 遍历 sheet + `GetUsedRange` → sidecar JSON（**ADR-013**） | 多 sheet；编辑定位 |
| **粗读（兼容）** | `office_read_document` | Conversion → csv → `parser/csv.py` | 单 sheet 快照；快速预览 |
| **粗读 fallback** | `office_read_spreadsheet` `read_mode=coarse` | 同上 csv | Builder 不可用 |

**默认**：编辑前用 **`office_read_spreadsheet`**（`read_mode=fine`）。

**Conversion csv 限制**：通常只反映**活动 sheet** 或 flatten 后单表；不可作为多 sheet 编辑依据。

### 2.3 工具矩阵

| MCP 工具名 | 代码位置 | 类型 | 说明 |
|------------|----------|------|------|
| `office_read_spreadsheet` | `spreadsheet/tools/read.py` | **新增** | 精读 workbook + 统一 schema |
| `office_create_spreadsheet` | `spreadsheet/tools/create.py` | **新增** | 声明式 `sheets[]` |
| `office_edit_spreadsheet` | `spreadsheet/tools/edit.py` | **新增** | 声明式 `operations[]` |
| `office_merge_spreadsheets` | `spreadsheet/tools/merge.py` | **新增** | 合并 workbook（追加 sheet） |
| `office_apply_template_spreadsheet` | `spreadsheet/tools/template.py` | **新增** | 按单元格占位符填充 |
| `office_read_document` | `legacy/read_document.py` | 保留 | xlsx/xls/ods → csv 粗读 |
| `office_execute_builder` | `gateway/execute_builder.py` | 保留 | 手写 Spreadsheet API |
| `office_call_api` | `gateway/call_api.py` | 保留 | convert 等 |

### 2.4 统一 read 顶层 schema

```json
{
  "category": "spreadsheet",
  "title": "Sales Q1",
  "unit_count": 2,
  "sheets": [
    {
      "sheet_index": 0,
      "name": "Summary",
      "used_range": "A1:D10",
      "row_count": 10,
      "col_count": 4,
      "headers": ["Product", "Units", "Revenue", "Region"],
      "rows": [
        ["Product", "Units", "Revenue", "Region"],
        ["Widget A", "120", "2400", "EMEA"]
      ]
    }
  ],
  "units": "<与 sheets[] 相同内容>",
  "source_path": "gs://bucket/sales.xlsx",
  "read_mode": "fine",
  "_locator_note": "Edit with office_edit_spreadsheet: sheet_name or sheet_index + cell (A1) or range.",
  "_note": "Do not use office_read_document row index for Builder edits."
}
```

> **ADR-033**：fine read **`headers = rows[0]`**（`rows` 仍含完整数据含首行）。**ADR-031 / ADR-034**：`include_formulas`、`range` 见 §4.1（**ST-043–044** ✅）。`max_rows` 已接线。

| 统一字段 | spreadsheet 映射 |
|----------|-------------------|
| `unit_count` | sheet 数量 |
| `units[]` | 与 `sheets[]` **同内容**（须 mirror，见架构 §4） |

大表策略：`options.max_rows` 已接线；`options.range`（**ADR-034**，先 range 后 max_rows，待 **ST-044**）；`format=outline` 只返回 sheet 名与 `used_range`（range 裁剪后更新 `used_range` 字符串）。

---

## 3. 支持格式

### 3.1 用户重点格式

| 扩展名 | 角色 | CreateFile / OpenFile | 说明 |
|--------|------|----------------------|------|
| **`.xlsx`** | 推荐新建 | `"xlsx"` | OOXML |
| **`.ods`** | 推荐（开放文档） | `"ods"` | ODF Spreadsheet |
| **`.xls`** | legacy 互操作 | `"xls"` | Excel 97–2003 |

### 3.2 完整 Spreadsheet 类扩展名

`core/categories.py` → `SPREADSHEET_EXTENSIONS`：

```
csv, et, ett, fods, ods, ots, sxc, tsv,
xls, xlsb, xlsm, xlsx, xlt, xltm, xltx
```

入口校验：`classify_file_ext(ext) == "spreadsheet"`（csv/tsv 只读或作为 create 输出特例）。

| 场景 | 建议 |
|------|------|
| LLM 新建 | `output_path` 以 **`.xlsx`** 或 **`.ods`** 结尾 |
| 读取 `.xls` | 支持 OpenFile `"xls"` |
| 保存格式 | 由 `output_path` 扩展名决定 |
| 粗读 | Conversion → `csv`（`llm_coarse_output_type`） |

---

## 4. 工具规格

### 4.1 `office_read_spreadsheet`

**代码**：`spreadsheet/tools/read.py` → `spreadsheet/parser/workbook.py` + `core/builder_json_sidecar.py`

#### 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `source_path` / `source_url` | string | 二选一 | 源文件 |
| `format` | enum | 否 | `structured` \| `outline` \| `text` |
| `options.read_mode` | enum | 否 | `fine`（默认）\| `coarse` |
| `options.sheet_names` | string[] | 否 | 只读指定 sheet；默认全部 |
| `options.max_rows` | int | 否 | 每 sheet 最大行数（已接线） |
| `options.include_formulas` | bool | 否 | true 时 fine read 用 `GetFormula()` 写入 `rows`（**ADR-031**；**ST-043** ✅） |
| `options.range` | string | 否 | 每 sheet 裁剪区域，如 `A1:D100`（**ADR-034**；待 **ST-044**） |

#### 精读 sidecar 脚本（示意）

Builder 无整表 ToJSON；脚本遍历 sheet 与 used range，组装 JSON 写入 sidecar：

```javascript
builder.OpenFile("{url}", "{ext}");
var out = { sheets: [] };
var count = Api.GetSheetsCount();
for (var i = 0; i < count; i++) {
  var ws = Api.GetSheet(i);
  var name = ws.GetName();
  var used = ws.GetUsedRange();
  // 迭代 used range → values[][] （GetValue / GetText）
  out.sheets.push({ sheet_index: i, name: name, rows: [...], used_range: "..." });
}
var jsonStr = JSON.stringify(out);
// write jsonStr to sidecar txt (core/builder_json_sidecar)
builder.CloseFile();
```

若 DS 无 `GetSheetsCount`：fine read E2E skip，coarse csv 仍可用（**ADR-013** / **ADR-021**）。

`spreadsheet/parser/workbook.py`：sidecar JSON → `sheets[]`；**ADR-033** 填充 `headers`（首行镜像）；内部 `parse_a1` / `parse_range`；**ADR-034** `apply_range_filter`（**ST-044** ✅）。

#### 粗读（`read_mode=coarse`）

Conversion `outputtype=csv` → `spreadsheet/parser/csv.py`（自 `html_parser.parse_csv_to_structure` 迁入），返回 `read_mode: "coarse"` 与 `_note` 警告单 sheet。

---

### 4.2 `office_create_spreadsheet`

**代码**：`spreadsheet/tools/create.py` → `spreadsheet/builder/create.py`

#### 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `sheets` | array | 是 | `spreadsheet/schemas/workbook_spec.py` |
| `output_path` | string | 是 | `.xlsx` / `.ods` / `.xls` |

> **ADR-032**：v1 **无** `default_col_width`（列宽用 `office_execute_builder` 或 v2）。

#### WorkbookSpec（v1）

```json
{
  "sheets": [
    {
      "name": "Summary",
      "rows": [
        ["Product", "Units", "Revenue"],
        ["Widget A", 120, 2400],
        ["Widget B", 85, 1700]
      ],
      "header_row": true
    },
    {
      "name": "Detail",
      "rows": [
        ["Date", "SKU", "Qty"],
        ["2026-01-01", "A-001", 10]
      ]
    }
  ]
}
```

> **`header_row`**（**ADR-033**）：纯 LLM 语义（「首行 intentional 为表头」）；**不改变** Builder；read 恒 `headers=rows[0]`，与 create 参数无关。

#### Builder 示意（参考 ONLYOFFICE samples）

```javascript
builder.CreateFile("xlsx");
var ws = Api.GetActiveSheet();
ws.SetName("Summary");
var data = [["Product","Units","Revenue"], ["Widget A", 120, 2400]];
var start = ws.GetRangeByNumber(0, 0);
var end = ws.GetRangeByNumber(data.length - 1, data[0].length - 1);
ws.GetRange(start, end).SetValue(data);
// 第二 sheet: Api.AddSheet() / GetSheet(1) ...
builder.SaveFile("xlsx", "output.xlsx");
builder.CloseFile();
```

---

### 4.3 `office_edit_spreadsheet`

**代码**：`spreadsheet/tools/edit.py` → `spreadsheet/builder/edit.py`

#### 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `source_path` / `source_url` | string | 二选一 | 源 workbook |
| `output_path` | string | 是 | 输出路径 |
| `operations` | array | 是 | `spreadsheet/schemas/edit_ops.py` |
| `options.backup` | bool | 否 | object storage 备份 |

#### Operation 类型（v1 · **ADR-040** canonical）

**Sheet 定位**（除 `add_sheet`）：**`sheet_name`** 或 **`sheet_index`**（0-based）；省略时用活动 sheet。**禁止** `sheet`、`from_sheet`。

| op | 字段 | 说明 |
|----|------|------|
| `set_cell` | sheet 定位 + **`cell`**（A1）, `value` | 单格（**ADR-015**） |
| `set_range` | sheet 定位 + **`range`**, **`values`** | 区域；**无** anchor 备选（**ADR-037**） |
| `clear_range` | sheet 定位 + `range` | 清空 |
| `insert_rows` | sheet 定位 + `at_row`（**1-based**）, `count`, `values?` | **ADR-037**：可选 `values[][]` 插行后填充 |
| `delete_rows` | sheet 定位 + `from_row`（1-based）, `count` | 删行 |
| `add_sheet` | **`name`** | **ADR-036**：v1 **无** 初始 `rows`；填数用后续 `set_range` |
| `delete_sheet` | **`sheet_name`** 或 **`sheet_index`** | 删除 sheet |
| `rename_sheet` | **`sheet_name`**, **`new_name`** | 重命名 |
| `set_formula` | sheet 定位 + `cell`, `formula` | 写公式字符串 |
| `copy_sheet` | **`sheet_name`** 或 **`sheet_index`**, `new_name?` | **ADR-035**：可选新 sheet 名 |

示例：

```json
{
  "source_path": "gs://bucket/sales.xlsx",
  "output_path": "gs://bucket/sales-updated.xlsx",
  "operations": [
    {
      "op": "set_cell",
      "sheet_name": "Summary",
      "cell": "B3",
      "value": 150
    },
    {
      "op": "set_range",
      "sheet_index": 1,
      "range": "A2:C2",
      "values": [["2026-06-21", "A-002", 25]]
    },
    {
      "op": "add_sheet",
      "name": "Notes"
    }
  ]
}
```

> 代码落地：**ST-043–050**、**ST-055–056**；字段真源 [IMPLEMENTATION_DESIGN §14](./OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_DESIGN.md#14-与-upgrade--llm-指南同步说明) · [ADR-031–040](./ADR.md)

---

### 4.4 `office_merge_spreadsheets`

**代码**：`spreadsheet/tools/merge.py` → `spreadsheet/builder/merge.py`

按顺序打开各源 workbook，将每个 sheet **追加**到目标 workbook。**ADR-038**：`rename_conflicts=true`（默认）冲突时后缀 `_2`、`_3`…；`false` 时同名 → `{isError}`（**ST-048** ✅）。

---

### 4.5 `office_apply_template_spreadsheet`

**代码**：`spreadsheet/tools/template.py` → `spreadsheet/builder/template.py`

#### 占位符（v1）

**主路径：显式单元格映射**。`data` 键为 `"SheetName!A1"` 地址，值为写入内容：

```json
{
  "data": {
    "Summary!B2": 125000,
    "Summary!B3": 98000
  }
}
```

**可选辅助**（**ADR-014** / **ADR-039**）：`{{key}}` 在 used_range 内 Search；显式地址优先；builder dedup（**ST-050** ✅）。

#### 参数

| 参数 | 类型 | 必填 |
|------|------|------|
| `template_path` / `template_url` | string | 二选一 |
| `data` | object | 是 |
| `output_path` | string | 是 |

OpenFile → 按显式地址 `SetValue`；可选在各 sheet used range 内 Search `{{key}}` → SaveFile。

---

### 4.6 与 Word/Presentation 的差异

| 维度 | Word | Spreadsheet |
|------|------|-------------|
| 精读 | `doc.ToJSON` | **无整表 ToJSON**；脚本遍历 `GetSheet` + `GetUsedRange` |
| 粗读 | HTML | **csv**（单 sheet 局限） |
| 主定位 | `block_index`, `heading_path` | **`sheet_name` / `sheet_index` + A1 / `range`** |

---

## 5. 目录与文件清单

```
aiecs/tools/office_tool/spreadsheet/
├── __init__.py
├── parser/
│   ├── csv.py                    # ← html_parser.parse_csv_* 迁入
│   └── workbook.py               # sidecar JSON → sheets[]
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

### 测试

```
tests/office_mcp/spreadsheet/
├── test_workbook_parser.py
├── test_read_spreadsheet.py
├── test_create_spreadsheet.py
├── test_edit_spreadsheet.py
├── test_merge_spreadsheets.py
├── test_apply_template_spreadsheet.py
└── test_e2e_spreadsheet_tools.py   # @pytest.mark.spreadsheet @pytest.mark.e2e
```

---

## 6. LLM 工作流

```
# 创建
office_create_spreadsheet({ sheets, output_path: ".../data.ods" })

# 编辑
office_read_spreadsheet({ source_path, format: "structured" })
office_edit_spreadsheet({ source_path, output_path, operations })

# 模板 / 合并
office_apply_template_spreadsheet({ template_path, data, output_path })
office_merge_spreadsheets({ source_paths, output_path })
```

详见 [OFFICE_MCP_SPREADSHEET_LLM_GUIDE.md](./OFFICE_MCP_SPREADSHEET_LLM_GUIDE.md)。

---

## 7. 测试策略

### 7.1 单元

- `workbook.py` / `csv.py` parser fixtures
- `edit_ops` 校验；sheet 定位；A1 解析工具（内部 `GetRangeByNumber` 仍 0-based，不暴露给 LLM）

### 7.2 E2E

> **As-built**：`tests/office_mcp/spreadsheet/test_e2e_spreadsheet_tools.py` 为 **placeholder skip**；下列用例为 **目标清单**（**ST-037–042**）。fine read 另 gated on `GetSheetsCount`（ADR-021）。

```bash
DOCUMENTSERVER_URL=... DOCUMENTSERVER_JWT_SECRET=... \
  poetry run pytest tests/office_mcp/spreadsheet/ -v -m "spreadsheet and e2e"
```

用例：

1. create xlsx 双 sheet → read fine → 断言 sheet_count（**ST-037**）
2. edit set_cell + set_range → read 验证（**ST-037**）
3. **ods 往返**：create ods → edit → save ods（**ST-038**）
4. **xls 读取**：open xls → read（fine 或 coarse）（**ST-053**）
5. merge 两个 xlsx → 断言 sheet 数（**ST-039**）
6. template：`Summary!B2` + `{{key}}`（**ST-040**）
7. legacy `office_read_document` xlsx→csv 不变（**ST-041**）

---

## 8. 实施计划（M5）

**实现细节**（文件级 API、Pydantic schema、sidecar/Builder 模板、PR 分解、测试 checklist）见 **[OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_DESIGN.md](./OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_DESIGN.md)**。

| 阶段 | 交付 | 验证 |
|------|------|------|
| **M5-S0** | `spreadsheet/` 目录 + `parser/csv.py` + `office_read_spreadsheet` coarse | unit ✅；legacy 回归 ✅ |
| **M5-S1** | fine read sidecar + `parser/workbook.py` | unit ✅；E2E 多 sheet → **ST-037** |
| **M5-S2** | `office_create_spreadsheet` | unit ✅；E2E xlsx/ods → **ST-037–038** |
| **M5-S3** | `office_edit_spreadsheet` core ops | unit ✅；E2E edit → **ST-037** |
| **M5-S4** | merge + template + registry | unit ✅；merge/template E2E → **ST-039–040**；rename → **ST-048** |

**前置依赖**：M0–M1（`core/builder_runtime`、`categories`）；可与 M4 presentation 并行。

### 8.1 实施状态（M7 · 与 DESIGN / TASKS 对齐）

| 项 | 状态 | 说明 |
|----|------|------|
| M5 S0–S4 代码 + unit | ✅ | `spreadsheet/` 五工具；**52** unit tests（`-m "not e2e"`） |
| M5 registry | ✅ | M5 **18/22**；M6 终态 **23/27** |
| **S-E2E** | ✅ | **ST-042**；E2E 用例已实现，DS 无能力时 ADR-021 skip |
| merge `rename_conflicts` | ✅ | **ADR-038** → **ST-048** |
| read `include_formulas` / `options.range` | ✅ | **ADR-031 / ADR-034** → **ST-043–044** |
| read `headers` / create `header_row` | ✅ | **ADR-033** → **ST-046** |
| `default_col_width` | ✅ 已从 schema 移除 | **ADR-032** → **ST-045** |
| `copy_sheet` + `new_name` | ✅ | **ADR-035** → **ST-049** |
| template dedup | ✅ | **ADR-039** → **ST-050** |
| `add_sheet.rows` | ✅ 已裁定不支持 | **ADR-036** → **ST-055** |
| `insert_rows.values` | ✅ | **ADR-037** → **ST-056** |
| `set_range` anchor | ✅ 已裁定不支持 | **ADR-037** §4 |
| edit TOOL_DEF 同步 | ✅ | **ADR-040** → **ST-047** |
| 空 used range 行为 | ✅ | **ST-054** |
| M6 registry **23/27** | ✅ | 回归断言 — **ST-057** |
| M7 文档 | ✅ | 本表 + [LLM 指南](./OFFICE_MCP_SPREADSHEET_LLM_GUIDE.md) + [实现设计](./OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_DESIGN.md) §13 + [TASKS](./OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_TASKS_BY_FILE.md) |

**禁止**在本表将 S-E2E 或 schema 接线标为 ✅，直至对应 ST 任务 `[x]`。

---

## 9. 向后兼容

| 项目 | 策略 |
|------|------|
| `office_read_document` + xlsx/xls/ods | 保持 csv 粗读；description 指向 `office_read_spreadsheet` |
| csv/tsv 纯文本 | 可走 read_spreadsheet coarse 或 read_document |

---

## 10. 风险与缓解

| 风险 | 缓解 |
|------|------|
| csv 粗读丢 sheet | fine read 默认；文档强调 |
| 大表 sidecar JSON 过大 | `max_rows`（已接线）；`range`（ST-044）；outline 模式 |
| xls 格式限制 | E2E；输出推荐 xlsx/ods |
| 公式 vs 值 | `include_formulas`（**ADR-031** / ST-043）；edit 用 `set_formula` |
| GetSheet 循环边界 | sidecar 用 **`GetSheetsCount()` + for**；不可用则 fine read E2E skip（**ADR-013**） |

---

## 11. 参考

- [OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_DESIGN.md](./OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_DESIGN.md) — M5 S0–S4 as-built + §14 字段真源
- [OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_TASKS_BY_FILE.md](./OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_TASKS_BY_FILE.md) — ST-001–057 按文件任务
- [ADR.md](./ADR.md) — Spreadsheet：**ADR-013–015、031–040**
- [implementation_design.md](./implementation_design.md) §7.3 — 全局 M5 任务
- [OFFICE_TOOL_ARCHITECTURE_REORG.md](./OFFICE_TOOL_ARCHITECTURE_REORG.md) §7.3
- [ONLYOFFICE Spreadsheet API](https://api.onlyoffice.com/docs/office-api/usage-api/spreadsheet-api/)
- [ApiWorksheet](https://api.onlyoffice.com/docs/office-api/usage-api/spreadsheet-api/ApiWorksheet/)
- [filling_spreadsheet sample](https://github.com/ONLYOFFICE/document-builder-samples/blob/master/python/filling_spreadsheet/main.py)
- 现有：`read_document.py`、`html_parser.parse_csv_to_structure`

---

## 附录 A：`.ods` / `.xlsx` / `.xls` 对照

| 维度 | .xlsx | .ods | .xls |
|------|-------|------|------|
| 标准 | OOXML | ODF | Excel 97–2003 |
| CreateFile | `"xlsx"` | `"ods"` | `"xls"` |
| LLM 新建推荐 | ✅ 默认 | ✅ 开放文档 | ⚠️ 仅兼容 |
| API | `Api.GetSheet` / `GetActiveSheet` | 同左 | 同左 |
| 粗读 | csv | csv | csv |

三者共用 `spreadsheet/` 模块；差异在 `file_ext` 与 SaveFile。
