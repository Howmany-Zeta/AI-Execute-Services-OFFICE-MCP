# Office MCP Spreadsheet Upgrade

让 LLM 对 **Spreadsheet 类**文档（重点：`.ods`、`.xlsx`、`.xls`）进行**精细化创建**与**精细化编辑**的升级设计。

> **状态**：**已实现**（M5）；M7 文档同步  
> **范围**：`aiecs/tools/office_tool/spreadsheet/`（新架构垂直模块）  
> **依赖**：ONLYOFFICE DocumentServer Document Builder + Conversion API；`core/` 公共层  
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

1. **精细化读取**（`office_read_spreadsheet`）：workbook → sheets[]，每 sheet 含 `used_range`、表头、行/单元格值；定位符 **`sheet_index` / `sheet_name` + `cell`（A1）或 `range`**（**ADR-015**：schema 弃用 `row`/`col`）。
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

| 统一字段 | spreadsheet 映射 |
|----------|-------------------|
| `unit_count` | sheet 数量 |
| `units[]` | 与 `sheets[]` **同内容**（须 mirror，见架构 §4） |

大表策略：`options.max_rows` / `options.range` 限制返回体积；`format=outline` 只返回 sheet 名与 `used_range`。

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
| `options.max_rows` | int | 否 | 每 sheet 最大行数 |
| `options.include_formulas` | bool | 否 | true 返回公式字符串；false 返回值 |

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

`spreadsheet/parser/workbook.py`：规范化 `headers`（首行可选）、`A1` 地址辅助。

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
| `options.default_col_width` | number | 否 | 默认列宽 |

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

#### Operation 类型（v1）

| op | 字段 | 说明 |
|----|------|------|
| `set_cell` | `sheet` + `cell`（A1）, `value` | 单格赋值（**ADR-015**：v1 schema 不暴露 `row`/`col`） |
| `set_range` | `sheet`, `range`（如 `B2:D5`）或 anchor + `values[][]`, `values` | 区域赋值 |
| `clear_range` | `sheet`, `range` | 清空 |
| `insert_rows` | `sheet`, `at_row`, `count`, `values[][]?` | 插入行 |
| `delete_rows` | `sheet`, `from_row`, `count` | 删行 |
| `add_sheet` | `name`, `rows[][]?` | 新建 sheet |
| `delete_sheet` | `sheet` | 删除 sheet |
| `rename_sheet` | `sheet`, `name` | 重命名 |
| `set_formula` | `sheet`, `cell`, `formula` | 写公式字符串 |
| `copy_sheet` | `from_sheet`, `name` | 复制 sheet |

**`sheet` 定位**：`sheet_index`（int）或 `sheet_name`（string）。

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
      "name": "Notes",
      "rows": [["Note"], ["Updated by MCP"]]
    }
  ]
}
```

---

### 4.4 `office_merge_spreadsheets`

**代码**：`spreadsheet/tools/merge.py` → `spreadsheet/builder/merge.py`

按顺序打开各源 workbook，将每个 sheet **追加**到目标 workbook（sheet 名冲突时后缀 `_2`）。

参数：`source_paths` / `source_urls`、`output_path`、`options.rename_conflicts`（默认 true）。

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

**可选辅助**（**ADR-014**）：模板单元格内写 `{{product_name}}`，若 `data` 含同名键且**未**提供 `Summary!A1` 形式地址，则在各 sheet **`GetUsedRange()`** 内 Search 替换 `{{key}}` → 值。同 key 多格全部替换。二者同时存在时，**显式地址优先**。

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
| 主定位 | `block_index`, `heading_path` | **`sheet` + `A1` / range** |

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

```bash
DOCUMENTSERVER_URL=... DOCUMENTSERVER_JWT_SECRET=... \
  poetry run pytest tests/office_mcp/spreadsheet/ -v -m "spreadsheet and e2e"
```

用例：

1. create xlsx 双 sheet → read fine → 断言 sheet_count
2. edit set_cell + set_range → read 验证
3. **ods 往返**：create ods → edit → save ods
4. **xls 读取**：open xls → read（fine 或 coarse）
5. merge 两个 xlsx → 断言 sheet 数
6. legacy `office_read_document` xlsx→csv 不变

---

## 8. 实施计划（M5）

**实现细节**（文件级 API、Pydantic schema、sidecar/Builder 模板、PR 分解、测试 checklist）见 **[OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_DESIGN.md](./OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_DESIGN.md)**。

| 阶段 | 交付 | 验证 |
|------|------|------|
| **M5-S0** | `spreadsheet/` 目录 + `parser/csv.py` + `office_read_spreadsheet` coarse | 单元；legacy 回归 |
| **M5-S1** | fine read sidecar + `parser/workbook.py` | E2E 多 sheet xlsx |
| **M5-S2** | `office_create_spreadsheet` | E2E xlsx/ods |
| **M5-S3** | `office_edit_spreadsheet` core ops | E2E set_cell/range/add_sheet |
| **M5-S4** | merge + template + registry | E2E；health 工具列表 |

**前置依赖**：M0–M1（`core/builder_runtime`、`categories`）；可与 M4 presentation 并行。

### 8.1 实施状态（M7 · Gate G5）

| 阶段 | 状态 | 代码位置 |
|------|------|----------|
| M5 S0–S4 | ✅ | `spreadsheet/` 五工具 |
| M5 registry | ✅ | `registry.py` +18 canonical |
| M7 文档 | ✅ | 本表 + [LLM 指南](./OFFICE_MCP_SPREADSHEET_LLM_GUIDE.md) |

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
| 大表 sidecar JSON 过大 | `max_rows`；`range`；outline 模式 |
| xls 格式限制 | E2E；输出推荐 xlsx/ods |
| 公式 vs 值 | `include_formulas` 选项 |
| GetSheet 循环边界 | sidecar 用 **`GetSheetsCount()` + for**；不可用则 fine read E2E skip（**ADR-013**） |

---

## 11. 参考

- [OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_DESIGN.md](./OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_DESIGN.md) — M5 S0–S4 可执行实现设计
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
