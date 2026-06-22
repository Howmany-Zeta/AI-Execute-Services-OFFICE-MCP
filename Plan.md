# office-Tool

MCP Server，包装 DocumentServer（OnlyOffice），供 LLM 实现文档创建、编辑、转换等操作。

## 状态

**v2 已实现（M0–M7 完成）**：**23** 个 canonical MCP 工具 + **4** 个 legacy 别名（`call_tool` only）。  
架构：`core/` + `gateway/` + 四类 vertical + `registry.py`。详见 [docs/OFFICE_TOOL_ARCHITECTURE_REORG.md](./docs/OFFICE_TOOL_ARCHITECTURE_REORG.md)。

| 里程碑 | Gate | 状态 | 交付摘要 |
|--------|------|------|----------|
| **M0** | G0（部分） | ✅ | `core/builder_runtime` + `builder_js` |
| **M1** | **G0** | ✅ | core 迁移、shim、errors、read_response、coarse_read |
| **M2** | G1（部分） | ✅ | `word/` W0–W3（6 工具） |
| **M3** | **G1** | ✅ | `registry.py`、adapter 瘦身、word tests 搬迁 |
| **M4** | **G2** | ✅ | `presentation/` 五工具 |
| **M5** | **G3** | ✅ | `spreadsheet/` 五工具 |
| **M6** | **G4** | ✅ | `pdf/` 五工具（无 apply_template_pdf） |
| **M7** | **G5** | ✅ | README / Plan / LLM 指南 / health / registry 一致 |

**Registry 终态：** `collect_office_tools()` = **23**；`get_handlers()` = **27**。

## 当前 Tool（v2 canonical · 23）

### Gateway（2）

| Tool | 描述 |
|------|------|
| `office_execute_builder` | Builder JS 脚本 POST `/docbuilder` |
| `office_call_api` | Conversion / Command API |

### Word（6）

| Tool | 描述 |
|------|------|
| `office_read_word` | 精读/粗读 Word（docx/odt/doc） |
| `office_create_word` | 声明式创建 |
| `office_edit_word` | 声明式编辑 |
| `office_merge_word` | 合并 Word |
| `office_apply_template_word` | 模板 `{{key}}` |
| `office_edit_word_script` | 裸 Builder 编辑脚本 |

### Presentation（5）

| Tool | 描述 |
|------|------|
| `office_read_presentation` | 精读/粗读 pptx/ppt/odp |
| `office_create_presentation` | 声明式创建 |
| `office_edit_presentation` | 声明式编辑 |
| `office_merge_presentations` | 合并演示稿 |
| `office_apply_template_presentation` | 模板填充 |

### Spreadsheet（5）

| Tool | 描述 |
|------|------|
| `office_read_spreadsheet` | 精读/粗读 xlsx/ods/xls |
| `office_create_spreadsheet` | 声明式创建 |
| `office_edit_spreadsheet` | 声明式编辑 |
| `office_merge_spreadsheets` | 合并工作簿 |
| `office_apply_template_spreadsheet` | 模板 `Sheet!A1` + `{{key}}` |

### PDF（5）

| Tool | 描述 |
|------|------|
| `office_read_pdf` | 精读/粗读 pdf |
| `office_create_pdf` | native / via_docx 创建 |
| `office_edit_pdf` | 声明式编辑 |
| `office_merge_pdfs` | 合并 PDF |
| `office_fill_pdf_form` | AcroForm 填写 |

### Legacy（call_tool only · 4）

| Tool | 映射 |
|------|------|
| `office_read_document` | coarse read（行为冻结） |
| `office_edit_document` | → `office_edit_word_script` |
| `office_merge_documents` | → `office_merge_word` |
| `office_apply_template` | → `office_apply_template_word` |

## 技术要点

- **Builder**：POST `/docbuilder`，async: false
- **JWT**：Builder header；Conversion/Command 当 `JWT_IN_BODY=true` 时 body token
- **output_path**：Builder 返回临时 URL → 下载 → 上传存储（gs:// / s3://）
- **超时**：Builder **600s**、Conversion 300s、Command 10s
- **读定位**：用各类 `office_read_{category}` fine read；legacy `office_read_document` index 不可用于 Builder `GetElement(i)`

## 环境变量

```
DOCUMENTSERVER_URL=http://documentserver:80
DOCUMENTSERVER_JWT_SECRET=${JWT_SECRET}
MCP_PORT=5040
MCP_PUBLIC_URL=http://host:5040
```

## 文档

- [README.md](./README.md) — 快速开始、E2E、health
- [docs/OFFICE_MCP_*_LLM_GUIDE.md](./docs/OFFICE_MCP_WORD_LLM_GUIDE.md) — LLM 调用指南
- [docs/LEGACY_TOOL_MIGRATION.md](./docs/LEGACY_TOOL_MIGRATION.md) — legacy 迁移
