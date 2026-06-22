# Office MCP Word — LLM 调用指南

面向 Agent / LLM 的 **Word 类**文档（**`.odt` / `.docx` / `.doc`**）精细化创建与编辑说明。  
完整设计见 [OFFICE_MCP_WORD_UPGRADE.md](./OFFICE_MCP_WORD_UPGRADE.md) · 实现细节 [OFFICE_MCP_WORD_IMPLEMENTATION_DESIGN.md](./OFFICE_MCP_WORD_IMPLEMENTATION_DESIGN.md)。

> **M7 同步**：工具名与 `registry.collect_office_tools()` 一致；`office_edit_word` 使用 **`search_string` / `replace_string`**；定位用 `block_index` / `heading_path` / `match_text`（**无** `relative_index`，ADR-011）。

---

## 1. 何时用哪个工具

| 任务 | 使用工具 | 不要用 |
|------|----------|--------|
| 读取块/标题/表格结构（编辑前） | `office_read_word` | `office_read_document` 的 index 做 edit 定位 |
| 从零写报告/公文 | `office_create_word` | 裸 `office_execute_builder`（除非复杂版式） |
| 改段落/标题/插表/替换 | `office_edit_word` | `office_edit_document` 写 JS（除非兜底） |
| 合并多个 Word 文件 | `office_merge_word` | — |
| 模板 `{{key}}` 填充 | `office_apply_template_word` | — |
| 快速预览任意 Office 类型 | `office_read_document` | 作为 edit 定位来源 |
| 手写 Search/Builder 逻辑 | `office_edit_word_script` | — |
| docx/odt → pdf | `office_call_api` convert | — |

---

## 2. 格式选择

| 扩展名 | 建议 |
|--------|------|
| **`.docx`** | 默认新建格式 |
| **`.odt`** | 开放文档、LibreOffice 互操作 |
| **`.doc`** | 仅当必须读写 legacy；**新建优先 docx/odt** |

`output_path` 扩展名决定保存格式。

---

## 3. 核心概念

### 3.1 定位符（编辑）

优先级：

1. **`block_index`** — 与最近一次 `office_read_word` 一致（0-based）
2. **`heading_path`** — 标题路径，如 `["Annual Report", "Background"]`
3. **`match_text`** — 块内唯一或短文本片段
4. **`style_name`** — 如 `"Heading 2"`（多处同样式时慎用）

**禁止**：使用 `office_read_document` 返回的 `elements[].index` 调用 Builder `GetElement(i)`。

### 3.2 读→改闭环

```
office_read_word → office_edit_word →（可选）office_read_word 验证
```

编辑前若文件可能已变，**必须重新 read**。

### 3.3 目录（TOC）

- **`office_create_word`**：`options.add_toc: true` 时，目录插入在**第一个 section 之前**（文首）；不支持文末 TOC（**ADR-012**）。
- **`office_edit_word`**：`insert_toc` op 在 operations 顺序位置插入目录（已有文档）。

---

## 4. 工作流示例

### 4.1 创建 `.docx` 报告

```json
{
  "tool": "office_create_word",
  "arguments": {
    "output_path": "gs://my-bucket/reports/annual.docx",
    "options": { "add_toc": true },
    "sections": [
      { "type": "heading1", "text": "Annual Report 2026" },
      { "type": "paragraph", "text": "This report summarizes performance." },
      {
        "type": "bullets",
        "items": ["Revenue +12%", "Margin stable", "Two new products"]
      },
      {
        "type": "table",
        "rows": [
          ["Quarter", "Revenue"],
          ["Q1", "1.2M"],
          ["Q2", "1.4M"]
        ],
        "header_row": true
      }
    ]
  }
}
```

### 4.2 创建 `.odt` 文档

```json
{
  "tool": "office_create_word",
  "arguments": {
    "output_path": "gs://my-bucket/memo.odt",
    "sections": [
      { "type": "heading1", "text": "Internal Memo" },
      { "type": "paragraph", "text": "Please review the attached policy." }
    ]
  }
}
```

### 4.3 读取后编辑

**Step 1 — Read**

```json
{
  "tool": "office_read_word",
  "arguments": {
    "source_path": "gs://my-bucket/reports/annual.docx",
    "format": "structured"
  }
}
```

**Step 2 — Edit**

```json
{
  "tool": "office_edit_word",
  "arguments": {
    "source_path": "gs://my-bucket/reports/annual.docx",
    "output_path": "gs://my-bucket/reports/annual-v2.docx",
    "operations": [
      {
        "op": "set_heading",
        "heading_path": ["Annual Report 2026"],
        "text": "Annual Report 2026 — Final"
      },
      {
        "op": "search_replace",
        "search_string": "DRAFT",
        "replace_string": "FINAL"
      },
      {
        "op": "insert_bullets",
        "items": ["Approved by board on 2026-06-21"]
      }
    ]
  }
}
```

### 4.4 用 block_index 精确改一段

```json
{
  "op": "set_block_text",
  "block_index": 4,
  "text": "Updated paragraph content."
}
```

### 4.5 编辑 legacy `.doc` 并另存为 `.docx`

```json
{
  "tool": "office_edit_word",
  "arguments": {
    "source_path": "gs://my-bucket/legacy/old.doc",
    "output_path": "gs://my-bucket/legacy/old-upgraded.docx",
    "operations": [
      { "op": "search_replace", "search_string": "2005", "replace_string": "2026" }
    ]
  }
}
```

### 4.6 模板填充

```json
{
  "tool": "office_apply_template_word",
  "arguments": {
    "template_path": "gs://my-bucket/templates/contract.docx",
    "output_path": "gs://my-bucket/contracts/acme.docx",
    "data": {
      "party_a": "ACME Corp",
      "party_b": "Client Ltd",
      "effective_date": "2026-06-21",
      "amount": "50000"
    }
  }
}
```

模板中正文中写 `{{party_a}}`、`{{amount}}` 等。

### 4.7 合并为 `.odt`

```json
{
  "tool": "office_merge_word",
  "arguments": {
    "source_paths": [
      "gs://my-bucket/part1.docx",
      "gs://my-bucket/part2.docx"
    ],
    "output_path": "gs://my-bucket/combined.odt",
    "options": {
      "add_page_break": true,
      "add_toc": false
    }
  }
}
```

---

## 5. `office_edit_word` 操作速查

字段名与 **`word/schemas/edit_ops.py`** 一致。

| op | 必填 | 说明 |
|----|------|------|
| `search_replace` | `search_string`, `replace_string` | 全文替换；可选 `scope: "subtree"` + `block_index` / `heading_path` / `match_text` 限定块内 |
| `set_block_text` | `text` + 定位 | `block_index` 或 `heading_path` / `match_text` |
| `set_heading` | `text` + 定位 | 可选 `style_name`（如 `"Heading 2"`） |
| `insert_paragraph` | `text` | 可选 `after`: `"start"` / `"end"` / 标题片段；或 `block_index` / `heading_path` / `match_text` |
| `insert_bullets` | `items[]` | 同上定位字段；省略则追加到**文档末尾** |
| `insert_table` | `rows[][]` | 同上定位字段；省略则追加到**文档末尾** |
| `delete_block` | 定位 | 不可删表格块（**ADR-010**） |
| `apply_style` | `style_name` + 定位 | 应用样式名 |
| `add_page_break` | — | 可选定位；省略则追加到**文档末尾** |
| `insert_section_break` | — | 可选定位；插入分节符（W4）；省略则追加到**文档末尾** |
| `insert_toc` | — | 文首插入目录 |

`operations` **按顺序执行**。`block_index` 与 fine read 块序对齐时走 `GetElement(block_index)`。

---

## 6. `office_create_word` section 类型

| type | 字段 |
|------|------|
| `heading1` / `heading2` / `heading3` | `text` |
| `paragraph` | `text`；可选 `bold` |
| `bullets` | `items[]`；可选 `level` |
| `table` | `rows[][]`；可选 `header_row` |
| `page_break` | — |

---

## 7. 常见错误

| 错误 | 后果 | 正确做法 |
|------|------|----------|
| 用 `read_document` 的 index 编辑 | 改错位置 | `office_read_word` + `block_index` |
| 不 re-read 就用旧 block_index | 越界/改错 | 每次 edit 前 read |
| 对 pptx 用 word 工具 | 报错 | 用 `office_*_presentation` |
| `output_path` 无扩展名 | 格式不明 | 始终 `.docx` / `.odt` / `.doc` |
| 复杂排版只用 operations | 失败 | `office_edit_word_script` 或 `office_execute_builder` |
| 使用 `search` / `replace` 字段名 | Pydantic 校验失败 | 使用 **`search_string` / `replace_string`** |
| 期望 `insert_bullets` 插入到某标题下 | 需带 `block_index` / `heading_path` / `match_text` 或 `after` 标题片段 | fine read 取 `block_index`，再 edit |

---

## 8. Legacy 工具映射

| Legacy 名 | 新名 / 行为 |
|-----------|-------------|
| `office_read_document` | 粗读；word→HTML |
| `office_edit_document` | 同 `office_edit_word_script` |
| `office_merge_documents` | 同 `office_merge_word` |
| `office_apply_template` | 同 `office_apply_template_word` |

新 Agent **优先使用** `office_*_word` 系列。

---

## 9. 实现状态

| 工具 | 文档 | 代码 |
|------|------|------|
| `office_read_word` | ✅ | ✅ |
| `office_create_word` | ✅ | ✅ |
| `office_edit_word` | ✅ | ✅ |
| `office_merge_word` | ✅ | ✅ |
| `office_apply_template_word` | ✅ | ✅ |
| `office_edit_word_script` | ✅ | ✅ |

参数名以代码为准：`search_replace` 使用 **`search_string` / `replace_string`**（非 `search` / `replace`）。详见 [OFFICE_MCP_WORD_IMPLEMENTATION_DESIGN.md](./OFFICE_MCP_WORD_IMPLEMENTATION_DESIGN.md) §14。

---

## 10. 相关文档

- [OFFICE_MCP_WORD_UPGRADE.md](./OFFICE_MCP_WORD_UPGRADE.md) — 设计与模块结构
- [OFFICE_MCP_WORD_IMPLEMENTATION_DESIGN.md](./OFFICE_MCP_WORD_IMPLEMENTATION_DESIGN.md) — 代码真源与字段名
- [OFFICE_TOOL_ARCHITECTURE_REORG.md](./OFFICE_TOOL_ARCHITECTURE_REORG.md) — 横向架构
- [ONLYOFFICE Document API](https://api.onlyoffice.com/docs/office-api/usage-api/document-api/)
