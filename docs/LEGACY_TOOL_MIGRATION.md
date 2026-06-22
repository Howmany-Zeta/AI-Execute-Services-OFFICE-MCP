# Legacy MCP 工具迁移指南

> **ADR-024**：自 **M3 registry** 起，`list_tools` **不再暴露** legacy 四工具（OpenAI 与非 OpenAI 客户端一致）。  
> **`call_tool` 仍支持** legacy 名称，供存量集成过渡；请尽快迁移至 canonical 工具。

---

## 1. 变更摘要（Changelog）

| 版本 / 里程碑 | 变更 |
|---------------|------|
| **M3** | `list_tools` **不再暴露** legacy 四工具；**已注册 canonical 数为 8**（gateway×2 + word×6），非终态 23 |
| **M3** | 已暴露工具的 `description` 增加 `[Word]` / `[Gateway]` 等类别前缀（ADR-025）；legacy **无** `[Legacy]` 前缀 |
| **M3** | health 返回 `tool_count` + `canonical_count`（**当前值，M3=8**）；可选 `registered_handler_count`（M3=12） |
| **M6** | canonical 注册满额 **23**；`registered_handler_count` **27** |
| **M7（ADR-022 breaking）** | 根 import shim **已删除**；`office_tool/` 根目录仅保留 `__init__.py` 与 `registry.py` |
| **后续 breaking PR** | 计划移除 legacy `call_tool` 注册（日期待定） |

---

## 2. 工具名对照表

| Legacy（不再出现在 `list_tools`） | 迁移至（canonical） | 说明 |
|-----------------------------------|---------------------|------|
| `office_read_document` | 见 §3 按扩展名分流 | 粗读/预览；**编辑前**须用 `office_read_{category}` fine read |
| `office_edit_document` | `office_edit_word_script` 或 `office_edit_word` | 原 Builder JS 编辑 → `edit_word_script`；声明式 → `edit_word` |
| `office_merge_documents` | `office_merge_word` | **仅 Word**；PPT → `office_merge_presentations`；Sheet → `office_merge_spreadsheets`；PDF → `office_merge_pdfs` |
| `office_apply_template` | `office_apply_template_word` | **仅 Word**；其他类别见对应 `office_apply_template_{category}` |

---

## 3. `office_read_document` → 按文件类型

| 扩展名 | 新工具 | 备注 |
|--------|--------|------|
| `.docx` / `.odt` / `.doc` | `office_read_word` | `read_mode=fine` 供 edit；coarse 仅预览 |
| `.pptx` / `.ppt` / `.odp` | `office_read_presentation` | legacy txt 粗读**不可**用于 edit 定位 |
| `.xlsx` / `.xls` / `.ods` | `office_read_spreadsheet` | legacy csv 通常单 sheet |
| `.pdf` | `office_read_pdf` | legacy txt 无可靠页界 |

**参数变化**：

- 新 read 工具统一：`source_path` / `source_url`、`format`（`structured` \| `outline` \| `text`）、`options.read_mode`（`fine` \| `coarse`）。
- legacy `format=text|html|...` 映射见各类 UPGRADE；**勿**将 legacy 返回的 `elements[].index` 用于 edit。

---

## 4. `office_edit_document` → Word 编辑

### 4.1 仍写 Builder JS（等价迁移）

```json
{
  "tool": "office_edit_word_script",
  "arguments": {
    "source_path": "gs://bucket/doc.docx",
    "output_path": "gs://bucket/doc-out.docx",
    "script": "builder.OpenFile(...); ... builder.CloseFile();"
  }
}
```

### 4.2 声明式 operations（推荐）

```json
{
  "tool": "office_edit_word",
  "arguments": {
    "source_path": "gs://bucket/doc.docx",
    "output_path": "gs://bucket/doc-out.docx",
    "operations": [
      { "op": "search_replace", "search_string": "OLD", "replace_string": "NEW" }
    ]
  }
}
```

**勿**对 pptx/xlsx/pdf 继续调用 `office_edit_document`（Word API）。

---

## 5. `office_merge_documents` → 按类别

| 源文件类型 | 新工具 |
|------------|--------|
| Word | `office_merge_word` |
| Presentation | `office_merge_presentations` |
| Spreadsheet | `office_merge_spreadsheets` |
| PDF | `office_merge_pdfs` |

参数：`source_paths` / `source_urls`、`output_path`；Word 可选 `options.add_page_break`、`options.add_toc`。

---

## 6. `office_apply_template` → 按类别

| 模板类型 | 新工具 |
|----------|--------|
| Word（`{{key}}`） | `office_apply_template_word` |
| Presentation | `office_apply_template_presentation` |
| Spreadsheet（`Sheet!A1` / `{{key}}`） | `office_apply_template_spreadsheet` |
| PDF 表单 | **`office_fill_pdf_form`**（无 apply_template_pdf） |

---

## 7. 集成检查清单

- [ ] 不再依赖 `list_tools` 中出现 legacy 四名称
- [ ] Agent prompt / 工具路由表已更新为 canonical 23 名
- [ ] 若仍 `call_tool` legacy 名：计划在下个发布周期改为 canonical
- [ ] Read → Edit 闭环改用 `office_read_{category}` + `office_edit_{category}`
- [ ] health 监控改用 `canonical_count`（**M6 终态 23**；M3 里程碑为 **8**）

---

## 8. Python import 路径迁移（ADR-022 · post-M7 breaking）

若代码仍 `from aiecs.tools.office_tool.edit_document import ...` 等根路径，须改为 canonical 模块。MCP **`call_tool` 工具名**（如 `office_edit_document`）未变；变的是 **Python import**。

| 旧 import 模块（已删除） | 新 import 模块 | 说明 |
|--------------------------|----------------|------|
| `aiecs.tools.office_tool.execute_builder` | `aiecs.tools.office_tool.gateway.execute_builder` | Gateway |
| `aiecs.tools.office_tool.call_api` | `aiecs.tools.office_tool.gateway.call_api` | Gateway |
| `aiecs.tools.office_tool.read_document` | `aiecs.tools.office_tool.legacy.read_document` | Legacy MCP handler |
| `aiecs.tools.office_tool.edit_document` | `aiecs.tools.office_tool.legacy.edit_document` 或 `word.tools.edit_script` | Legacy 名 vs Builder JS |
| `aiecs.tools.office_tool.merge_document` | `aiecs.tools.office_tool.legacy.merge_documents` 或 `word.tools.merge` | 单数旧模块 → legacy 复数 |
| `aiecs.tools.office_tool.apply_template` | `aiecs.tools.office_tool.legacy.apply_template` 或 `word.tools.template` | Word 模板 |
| `aiecs.tools.office_tool.conversion_output` | `aiecs.tools.office_tool.core.categories` | 分类 / 扩展名 |
| `aiecs.tools.office_tool.html_parser` | `aiecs.tools.office_tool.word.parser.html` | Word HTML；粗读见 `core.coarse_parsers.html` |
| `aiecs.tools.office_tool.storage` | `aiecs.tools.office_tool.core.storage` | GCS/S3 上传 |
| `aiecs.tools.office_tool.storage_paths` | `aiecs.tools.office_tool.core.storage.paths` | 路径校验 |
| `aiecs.tools.office_tool.object_fetch` | `aiecs.tools.office_tool.core.storage.object_fetch` | 对象下载 |
| `aiecs.tools.office_tool.docbuilder_script` | `aiecs.tools.office_tool.core.docbuilder_script` | Builder 脚本托管 |
| `aiecs.tools.office_tool.source_resolver` | `aiecs.tools.office_tool.core.source` | source_path/url 解析 |

**包根 `aiecs.tools.office_tool`**：仍可从 `__init__.py` 导入 legacy 四工具与 gateway 两工具 handler；新代码应直接 import 目标模块。

详见 CHANGELOG「ADR-022 breaking — Remove root import shims」。

---

## 9. 相关文档

- [ADR.md](./ADR.md) — ADR-022、024、025、026
- [implementation_design.md](./implementation_design.md) — §5 Registry、§7.5 Gateway SSRF、§11 兼容
- 各类 [OFFICE_MCP_*_LLM_GUIDE.md](./OFFICE_MCP_WORD_LLM_GUIDE.md)
