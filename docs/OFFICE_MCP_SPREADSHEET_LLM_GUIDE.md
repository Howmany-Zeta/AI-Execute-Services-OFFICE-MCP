# Office MCP Spreadsheet — LLM 调用指南

面向 Agent / LLM 的 **Spreadsheet 类**文档（**`.ods` / `.xlsx` / `.xls`**）精细化创建与编辑说明。

- **规格（What）**：[OFFICE_MCP_SPREADSHEET_UPGRADE.md](./OFFICE_MCP_SPREADSHEET_UPGRADE.md)
- **实现真源（How）**：[OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_DESIGN.md](./OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_DESIGN.md) — MCP 参数名、as-built 行为、已知 gap

> **M7 同步**：单元格定位 **`sheet_name` / `sheet_index`** + **A1** / `range`（**ADR-015**、**ADR-040**）。read 响应含 **`headers`**（**ADR-033**：首行镜像）。

---

## 1. 何时用哪个工具

| 任务 | 使用工具 | 不要用 |
|------|----------|--------|
| 读取 sheet/单元格结构（编辑前） | `office_read_spreadsheet` | `office_read_document` 的行 index |
| 从零创建工作簿 | `office_create_spreadsheet` | 裸 `office_execute_builder` |
| 改单元格/区域/插 sheet | `office_edit_spreadsheet` | `office_edit_document`（Word API） |
| 合并多个 Excel 文件 | `office_merge_spreadsheets` | `office_merge_word` |
| 按单元格模板填数 | `office_apply_template_spreadsheet` | `office_apply_template_word` |
| 快速看一眼单表 csv | `office_read_document` | 作为多 sheet 编辑依据 |
| xlsx → pdf | `office_call_api` convert | — |

---

## 2. 格式选择

| 扩展名 | 建议 |
|--------|------|
| **`.xlsx`** | 默认新建 |
| **`.ods`** | LibreOffice / 开放文档 |
| **`.xls`** | 仅 legacy 读写；**新建用 xlsx/ods** |

---

## 3. 核心概念

### 3.1 定位符

| 字段 | 说明 |
|------|------|
| **`sheet_index`** | 0-based，与最近 `office_read_spreadsheet` 一致 |
| **`sheet_name`** | 如 `"Summary"` |
| **`cell`** | A1 记法，如 `"B3"`（**推荐**） |
| **`range`** | 如 `"A1:D10"`、`"B2:B5"` |

**v1 不暴露 `row`/`col`**（**ADR-015**）：避免与 A1 记法混淆；内部 Builder 仍用 0-based `GetRangeByNumber`。

优先级：`sheet_name` / `sheet_index` 必填其一；单元格用 **`cell`** 或区域用 **`range`**。

### 3.2 读→改闭环

```
office_read_spreadsheet → office_edit_spreadsheet →（可选）再 read 验证
```

**禁止**：用 `office_read_document` 的 `elements[].index` 当行号去改 xlsx（且无 sheet 维度）。

### 3.3 粗读 vs 精读

| `read_mode` | 行为 |
|-------------|------|
| **`fine`**（默认） | Builder 读多 sheet；可编辑 |
| **`coarse`** | Conversion→csv；通常**仅单 sheet** |

### 3.4 Read 选项（**ADR-031** / **ADR-034**）

| 选项 | 说明 |
|------|------|
| `options.max_rows` | 每 sheet 最大行数（与 `range` 叠加时 **先 range 后 max_rows**） |
| `options.range` | 如 `"A1:D100"`，裁剪每 sheet 返回区域 |
| `options.include_formulas` | `true` 时 fine read 返回公式字符串（默认 `false` 为计算值） |

读响应每 sheet 含 **`headers`**（等于 `rows[0]`）与完整 **`rows`**（**ADR-033**）。

---

## 4. 工作流示例

### 4.1 创建 `.xlsx` 工作簿（两个 sheet）

```json
{
  "tool": "office_create_spreadsheet",
  "arguments": {
    "output_path": "gs://my-bucket/data/sales-q1.xlsx",
    "sheets": [
      {
        "name": "Summary",
        "header_row": true,
        "rows": [
          ["Product", "Units", "Revenue"],
          ["Widget A", 120, 2400],
          ["Widget B", 85, 1700]
        ]
      },
      {
        "name": "Log",
        "rows": [
          ["Generated", "2026-06-21"]
        ]
      }
    ]
  }
}
```

### 4.2 创建 `.ods`

```json
{
  "tool": "office_create_spreadsheet",
  "arguments": {
    "output_path": "gs://my-bucket/budget.ods",
    "sheets": [
      {
        "name": "Budget",
        "rows": [
          ["Category", "Amount"],
          ["Travel", 5000],
          ["Software", 12000]
        ]
      }
    ]
  }
}
```

### 4.3 读取后编辑

**Step 1 — Read**

```json
{
  "tool": "office_read_spreadsheet",
  "arguments": {
    "source_path": "gs://my-bucket/data/sales-q1.xlsx",
    "format": "structured",
    "options": { "read_mode": "fine" }
  }
}
```

**Step 2 — Edit**

```json
{
  "tool": "office_edit_spreadsheet",
  "arguments": {
    "source_path": "gs://my-bucket/data/sales-q1.xlsx",
    "output_path": "gs://my-bucket/data/sales-q1-v2.xlsx",
    "operations": [
      {
        "op": "set_cell",
        "sheet_name": "Summary",
        "cell": "C2",
        "value": 2600
      },
      {
        "op": "set_range",
        "sheet_name": "Summary",
        "range": "A4:C4",
        "values": [["Widget C", 40, 800]]
      },
      {
        "op": "set_formula",
        "sheet_name": "Summary",
        "cell": "C6",
        "formula": "=SUM(C2:C4)"
      }
    ]
  }
}
```

### 4.4 模板：`{{key}}` 辅助（ADR-014）

显式地址为主；模板单元格可写 `{{product_name}}`，`data` 含同名键时在 **used range** 内替换：

```json
{
  "tool": "office_apply_template_spreadsheet",
  "arguments": {
    "template_path": "gs://my-bucket/templates/quarterly.xlsx",
    "output_path": "gs://my-bucket/reports/q1-filled.xlsx",
    "data": {
      "product_name": "Widget Pro",
      "Summary!B2": 125000
    }
  }
}
```

若同时提供 `Summary!B2` 与 `product_name`，**显式地址优先**。

### 4.5 编辑 legacy `.xls` 并另存 `.xlsx`

```json
{
  "tool": "office_edit_spreadsheet",
  "arguments": {
    "source_path": "gs://my-bucket/legacy/old.xls",
    "output_path": "gs://my-bucket/legacy/old-upgraded.xlsx",
    "operations": [
      { "op": "set_cell", "sheet_index": 0, "cell": "A1", "value": "Updated title" }
    ]
  }
}
```

### 4.6 模板填充（显式地址）

```json
{
  "tool": "office_apply_template_spreadsheet",
  "arguments": {
    "template_path": "gs://my-bucket/templates/quarterly.xlsx",
    "output_path": "gs://my-bucket/reports/q1-filled.xlsx",
    "data": {
      "Summary!B2": 125000,
      "Summary!B3": 98000
    }
  }
}
```

（v1 主路径为 **`SheetName!A1` 显式地址**；`{{key}}` used range 辅助见 §4.4。）

### 4.7 合并工作簿

```json
{
  "tool": "office_merge_spreadsheets",
  "arguments": {
    "source_paths": [
      "gs://my-bucket/jan.xlsx",
      "gs://my-bucket/feb.xlsx"
    ],
    "output_path": "gs://my-bucket/jan-feb.xlsx",
    "options": { "rename_conflicts": true }
  }
}
```

---

## 5. `office_edit_spreadsheet` 操作速查

表中「sheet 定位」指 **`sheet_name`** 或 **`sheet_index`**（二选一或省略则用活动 sheet）。

| op | 必填 | 说明 |
|----|------|------|
| `set_cell` | sheet 定位, `value`, **`cell`** | 单格（A1 记法） |
| `set_range` | sheet 定位, **`values`**, **`range`** | 区域 |
| `clear_range` | sheet 定位, `range` | 清空 |
| `insert_rows` | sheet 定位, `at_row`, `count`, `values?` | 插行；可选 **`values`** 填充新行（**ADR-037**） |
| `delete_rows` | sheet 定位, `from_row`, `count` | 删行（1-based） |
| `add_sheet` | **`name`** | 新建空 sheet（**ADR-036**：无初始 `rows` → 再用 `set_range`） |
| `delete_sheet` | **`sheet_name`** 或 **`sheet_index`** | 删 sheet |
| `rename_sheet` | **`sheet_name`**, **`new_name`** | 重命名 |
| `set_formula` | sheet 定位, `cell`, `formula` | 如 `"=SUM(A1:A10)"` |
| `copy_sheet` | **`sheet_name`** 或 **`sheet_index`**, `new_name?` | 复制 sheet；可选 **`new_name`**（**ADR-035**） |

---

## 6. `office_create_spreadsheet` sheet 字段

| 字段 | 说明 |
|------|------|
| `name` | Sheet 名 |
| `rows` | 二维数组；数字/字符串/布尔 |
| `header_row` | **ADR-033**：纯语义（「首行是表头」）；不改变 Builder；read 时 **`headers` 恒为 `rows[0]`** |

---

## 7. 常见错误

| 错误 | 后果 | 正确做法 |
|------|------|----------|
| 用 read_document 编辑 xlsx | 无 sheet、行 index 不可靠 | `office_read_spreadsheet` |
| coarse read 当多 sheet 依据 | 丢 sheet | `read_mode: fine` |
| 对 docx 用 spreadsheet 工具 | 失败 | `office_*_word` |
| 超大表一次 read 全量 | 超时/体积爆 | `max_rows` 或指定 sheet |
| 复杂 pivot/图表只用 operations | 失败 | `office_execute_builder` |

---

## 8. 实现状态

| 工具 | Handler / unit | E2E |
|------|----------------|-----|
| `office_read_spreadsheet` | ✅ | ✅（ADR-021 能力 skip） |
| `office_create_spreadsheet` | ✅ | ✅（ADR-021 能力 skip） |
| `office_edit_spreadsheet` | ✅ | ✅（ADR-021 能力 skip） |
| `office_merge_spreadsheets` | ✅（`rename_conflicts` **ADR-038**） | ✅（ADR-021 能力 skip） |
| `office_apply_template_spreadsheet` | ✅（**ADR-039** dedup） | ✅（ADR-021 能力 skip） |

细节与 **ADR-031–040** 代码落地状态见 [IMPLEMENTATION_DESIGN](./OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_DESIGN.md) §14 · [TASKS ST-037–057](./OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_TASKS_BY_FILE.md) · [ADR.md](./ADR.md)。

---

## 9. 相关文档

- [OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_DESIGN.md](./OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_DESIGN.md) — **as-built 真源**
- [OFFICE_MCP_SPREADSHEET_UPGRADE.md](./OFFICE_MCP_SPREADSHEET_UPGRADE.md)
- [OFFICE_TOOL_ARCHITECTURE_REORG.md](./OFFICE_TOOL_ARCHITECTURE_REORG.md)
- [ADR.md](./ADR.md) — Spreadsheet **ADR-013–015、031–040**
- [ONLYOFFICE Spreadsheet API](https://api.onlyoffice.com/docs/office-api/usage-api/spreadsheet-api/)
