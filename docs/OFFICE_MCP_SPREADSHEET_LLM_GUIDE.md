# Office MCP Spreadsheet — LLM 调用指南

面向 Agent / LLM 的 **Spreadsheet 类**文档（**`.ods` / `.xlsx` / `.xls`**）精细化创建与编辑说明。  
完整设计见 [OFFICE_MCP_SPREADSHEET_UPGRADE.md](./OFFICE_MCP_SPREADSHEET_UPGRADE.md)。

> **M7 同步**：单元格定位用 `sheet` + **A1** / `range`（ADR-015）；不以 row/col 为主推参数。

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

| op | 必填 | 说明 |
|----|------|------|
| `set_cell` | `sheet`, `value`, **`cell`** | 单格（A1 记法） |
| `set_range` | `sheet`, `values` 或 `values[][]`, **`range`** | 区域 |
| `clear_range` | `sheet`, `range` | 清空 |
| `insert_rows` | `sheet`, `at_row`, `count` | 插行 |
| `delete_rows` | `sheet`, `from_row`, `count` | 删行 |
| `add_sheet` | `name` | 可选 `rows[][]` |
| `delete_sheet` | `sheet` | 删 sheet |
| `rename_sheet` | `sheet`, `name` | 重命名 |
| `set_formula` | `sheet`, `cell`, `formula` | 如 `"=SUM(A1:A10)"` |
| `copy_sheet` | `from_sheet`, `name` | 复制 sheet |

---

## 6. `office_create_spreadsheet` sheet 字段

| 字段 | 说明 |
|------|------|
| `name` | Sheet 名 |
| `rows` | 二维数组；数字/字符串/布尔 |
| `header_row` | true 时首行作表头（read 时映射 `headers`） |

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

| 工具 | 文档 | 代码 |
|------|------|------|
| `office_read_spreadsheet` | ✅ | ⏳ 待实现 |
| `office_create_spreadsheet` | ✅ | ⏳ 待实现 |
| `office_edit_spreadsheet` | ✅ | ⏳ 待实现 |
| `office_merge_spreadsheets` | ✅ | ⏳ 待实现 |
| `office_apply_template_spreadsheet` | ✅ | ⏳ 待实现 |

---

## 9. 相关文档

- [OFFICE_MCP_SPREADSHEET_UPGRADE.md](./OFFICE_MCP_SPREADSHEET_UPGRADE.md)
- [OFFICE_TOOL_ARCHITECTURE_REORG.md](./OFFICE_TOOL_ARCHITECTURE_REORG.md)
- [ONLYOFFICE Spreadsheet API](https://api.onlyoffice.com/docs/office-api/usage-api/spreadsheet-api/)
