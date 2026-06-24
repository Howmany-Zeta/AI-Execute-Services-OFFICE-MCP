# Office MCP PDF — LLM 调用指南

面向 Agent / LLM 的 **PDF**（**`.pdf`**）精细化创建、修改与合并说明。  
完整设计见 [OFFICE_MCP_PDF_UPGRADE.md](./OFFICE_MCP_PDF_UPGRADE.md)。

> **M7 同步**：`office_create_pdf` 须显式 `create_mode`（native / via_docx，**ADR-017**）；表单填写仅 `office_fill_pdf_form`（**ADR-030**）；M6 五工具 **unit ✅**；DS E2E ✅ **PDF-037–044**；gap ✅ **PDF-045–046**。

---

## 1. 何时用哪个工具

| 任务 | 使用工具 | 不要用 |
|------|----------|--------|
| 读取 PDF 页/块/表单域 | `office_read_pdf` | `office_read_document` 当页界结构 |
| 简单多页 PDF（文字/小表） | `office_create_pdf` | 长报告用 word→pdf |
| 改页、加段、注释 | `office_edit_pdf` | `office_edit_word` |
| 任意 AcroForm 填写（单/多字段） | `office_fill_pdf_form` | `edit_pdf`（v1 无 fill op，**ADR-030**） |
| 合并多个 PDF | `office_merge_pdfs` | — |
| **复杂版式** PDF 报告 | `office_create_word` → `office_call_api` convert | `office_create_pdf` |
| 演示稿 PDF | `office_create_presentation` → convert | — |
| 手写 PDF API | `office_execute_builder` | — |

---

## 2. 能力边界（必读）

PDF **不是** Word 的等价物：

- **适合** `office_create_pdf`：少量页面、居中标题、简单段落/表格、后续 `fill_form`
- **不适合** `office_create_pdf`：长文报告、多级标题排版、复杂样式 → 用 **`office_create_word` + convert**

---

## 3. 定位符

| 字段 | 说明 |
|------|------|
| **`page_index`** | 0-based，与最近 `office_read_pdf` 一致 |
| **`block_index`** | 页内块顺序（paragraph 等） |
| **表单域 `name`** | AcroForm 字段名（read 返回 `form_fields[].name`） |

编辑前：**`office_read_pdf`** → 再 **`office_edit_pdf`** / **`office_fill_pdf_form`**。

### 3.1 `create_mode`（ADR-017）

| 值 | 行为 |
|----|------|
| **`native`**（默认） | Docs 9.3+ PDF Builder API |
| **`via_docx`** | `CreateFile("docx")` → 填内容 → `SaveFile("pdf")` |

**不自动 fallback**：`native` 失败 → `{isError, text}`，含「可尝试 `create_mode=via_docx`」；须 **显式** 改 mode 后重试。

### 3.2 Coarse read 分页（ADR-020）

`read_mode=coarse` 时页界：`\f` → 行 `--- page N ---` → 否则单页 + `_note`（勿用于 edit 定位）。

---

## 4. 工作流示例

### 4.1 创建简单 2 页 PDF

```json
{
  "tool": "office_create_pdf",
  "arguments": {
    "output_path": "gs://my-bucket/notice.pdf",
    "options": { "create_mode": "native" },
    "pages": [
      {
        "blocks": [
          {
            "type": "paragraph",
            "text": "Internal Notice",
            "align": "center",
            "bold": true
          },
          {
            "type": "paragraph",
            "text": "Please review the updated policy by Friday."
          }
        ]
      },
      {
        "blocks": [
          { "type": "paragraph", "text": "Contact: hr@example.com" }
        ]
      }
    ]
  }
}
```

### 4.2 读取后追加一段

```json
{
  "tool": "office_read_pdf",
  "arguments": {
    "source_path": "gs://my-bucket/contract.pdf",
    "format": "structured"
  }
}
```

```json
{
  "tool": "office_edit_pdf",
  "arguments": {
    "source_path": "gs://my-bucket/contract.pdf",
    "output_path": "gs://my-bucket/contract-v2.pdf",
    "operations": [
      {
        "op": "add_paragraph",
        "page_index": 4,
        "text": "Appendix: Terms updated 2026-06-21."
      }
    ]
  }
}
```

### 4.3 填写 PDF 表单

```json
{
  "tool": "office_fill_pdf_form",
  "arguments": {
    "source_path": "gs://my-bucket/forms/application.pdf",
    "output_path": "gs://my-bucket/forms/application-filled.pdf",
    "data": {
      "ApplicantName": "Jane Doe",
      "SignDate": "2026-06-21",
      "AgreeTerms": true
    }
  }
}
```

（字段名须与 PDF 内 AcroForm 名一致；可先 `read_pdf` 查看 `form_fields`。实现为 **逐字段 SetValue**，**ADR-019**。）

### 4.4 合并 PDF

默认 **Builder** 引擎：

```json
{
  "tool": "office_merge_pdfs",
  "arguments": {
    "source_paths": [
      "gs://my-bucket/cover.pdf",
      "gs://my-bucket/body.pdf",
      "gs://my-bucket/appendix.pdf"
    ],
    "output_path": "gs://my-bucket/full-pack.pdf"
  }
}
```

Builder 失败时可 **显式** 指定 Conversion 引擎（可能丢表单/注释，**ADR-018**）：

```json
{
  "tool": "office_merge_pdfs",
  "arguments": {
    "source_paths": ["gs://my-bucket/a.pdf", "gs://my-bucket/b.pdf"],
    "output_path": "gs://my-bucket/merged.pdf",
    "options": { "engine": "conversion" }
  }
}
```

### 4.5 native 失败 → 显式 via_docx

```json
{
  "tool": "office_create_pdf",
  "arguments": {
    "output_path": "gs://my-bucket/notice.pdf",
    "options": { "create_mode": "via_docx" },
    "pages": [
      {
        "blocks": [
          { "type": "paragraph", "text": "Fallback path", "align": "center" }
        ]
      }
    ]
  }
}
```

### 4.6 从 Word 生成「精细版式」PDF（推荐路径）

```json
{
  "tool": "office_create_word",
  "arguments": {
    "output_path": "gs://my-bucket/report.docx",
    "sections": [
      { "type": "heading1", "text": "Annual Report" },
      { "type": "paragraph", "text": "..." }
    ]
  }
}
```

```json
{
  "tool": "office_call_api",
  "arguments": {
    "action": "convert",
    "params": {
      "url": "<fetchable docx url>",
      "filetype": "docx",
      "outputtype": "pdf",
      "key": "<uuid>"
    }
  }
}
```

---

## 5. `office_edit_pdf` 操作速查

| op | 说明 |
|----|------|
| `add_paragraph` | 指定页追加段落 |
| `set_page_text` | 替换整页内容（慎用） |
| `add_page` | 插入页 |
| `delete_page` | 删除页 |
| `rotate_page` | 旋转页 |
| `add_annotation` | 注释（freetext/highlight 等子集） |

AcroForm 填写（含单字段）请用 **`office_fill_pdf_form`**（**ADR-030**）；`edit_pdf` 不提供 `fill_form_field`。

合并多个 PDF 请用 **`office_merge_pdfs`**（v1 不提供 `append_pdf_pages` op）。

---

## 6. `office_create_pdf` block 类型（v1）

| type | 字段 |
|------|------|
| `paragraph` | `text`；可选 `align`、`bold` |
| `table` | `rows[][]` |

---

## 7. 常见错误

| 错误 | 正确做法 |
|------|----------|
| 用 read_document 的 index 编辑 PDF | `office_read_pdf` + `page_index` |
| 用 create_pdf 写 20 页报告 | `create_word` + convert |
| native 失败时期望自动 via_docx | 读 `{isError}`，显式 `create_mode=via_docx` 重试（**ADR-017**） |
| Builder merge 失败 | 显式 `options.engine=conversion`（**ADR-018**） |
| 用 template_word 填 PDF 表单 | **`office_fill_pdf_form`**（勿用 `edit_pdf`） |
| 期望 OCR 扫描件 | 本 MCP 不提供 OCR |

---

## 8. 实现状态

| 工具 | 文档 | 代码（M6 架构） | 收尾 |
|------|------|-----------------|------|
| `office_read_pdf` | ✅ | ✅ unit | E2E ✅ **PDF-037–038** |
| `office_create_pdf` | ✅ | ✅ unit | ✅ **PDF-037、042–043** E2E；**PDF-045** `page_size` |
| `office_edit_pdf` | ✅ | ✅ unit | ✅ **PDF-038** E2E；**PDF-046** `TOOL_DEF` schema |
| `office_merge_pdfs` | ✅ | ✅ unit | E2E ✅ **PDF-039–040** |
| `office_fill_pdf_form` | ✅ | ✅ unit | E2E ✅ **PDF-041** |

**E2E（DS）**：✅ **PDF-037–044**（8 cases；无 placeholder skip；ADR-021 capability skip 允许）。详见 [OFFICE_MCP_PDF_UPGRADE.md](./OFFICE_MCP_PDF_UPGRADE.md) §7.1。

---

## 9. 相关文档

- [OFFICE_MCP_PDF_UPGRADE.md](./OFFICE_MCP_PDF_UPGRADE.md)
- [OFFICE_MCP_WORD_UPGRADE.md](./OFFICE_MCP_WORD_UPGRADE.md)（复杂 PDF 源）
- [OFFICE_TOOL_ARCHITECTURE_REORG.md](./OFFICE_TOOL_ARCHITECTURE_REORG.md)
