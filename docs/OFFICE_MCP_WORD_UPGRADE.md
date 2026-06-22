# Office MCP Word Upgrade

让 LLM 对 **Word 类**文档（重点：`.odt`、`.docx`、`.doc`）进行**精细化创建**与**精细化编辑**的升级设计。

> **状态**：**已实现**（M2–M3）；M7 文档同步  
> **范围**：`aiecs/tools/office_tool/word/`（新架构垂直模块）  
> **依赖**：ONLYOFFICE DocumentServer Document Builder + Conversion API；`core/` 公共层  
> **关联**：[OFFICE_TOOL_ARCHITECTURE_REORG.md](./OFFICE_TOOL_ARCHITECTURE_REORG.md)、[OFFICE_MCP_WORD_IMPLEMENTATION_DESIGN.md](./OFFICE_MCP_WORD_IMPLEMENTATION_DESIGN.md)（实现设计）、[OFFICE_MCP_WORD_LLM_GUIDE.md](./OFFICE_MCP_WORD_LLM_GUIDE.md)、[OFFICE_MCP_PRESENTATION_UPGRADE.md](./OFFICE_MCP_PRESENTATION_UPGRADE.md)（平行类别参考）

本升级是架构重组 **M2–M3（word 迁移）+ W1–W2（精读/声明式读写）** 的交付物，遵循 `office_{action}_{category}` 命名，`category = word`。

---

## 1. 背景与目标

### 1.1 问题

当前 Word 类能力**强于 presentation，但未达到「精细化」**：

| 能力 | 现状 | 问题 |
|------|------|------|
| **读取** | `office_read_document` → Conversion → HTML → `html_parser` | 有 heading/paragraph/table；`elements[].index` **不可**用于 Builder `GetElement(i)` |
| **创建** | 仅 `office_execute_builder` 手写 JS | 无声明式 spec；无 E2E 之外的 LLM 指引 |
| **编辑** | `office_edit_document` + 裸 `edit_script` | LLM 需写 JS；仅文档提示 `Search()` / `GetStyleName()` |
| **合并** | `office_merge_documents` | 已实现，但硬编码 `CreateFile("docx")`、输出格式未跟 `output_path` |
| **模板** | `office_apply_template` | 已实现，`{{key}}` 全局替换 |
| **读→改闭环** | 部分可用 | HTML index 与 Builder 不对齐；无 `block_index` / `heading_path` 级 operations |

LLM 难以可靠完成：「在二级标题 *Background* 下插入一段」「把第三段改为 bullet 列表」「创建 odt 报告含目录与表格」等任务。

### 1.2 目标（Must Have）

1. **精细化读取**（`office_read_word`）：块级结构 + **可编辑定位符**（`block_index`、`heading_path`、`style_name`、文本片段）。
2. **精细化创建**（`office_create_word`）：声明式 `sections[]` → Builder 脚本 → `.docx` / `.odt` / `.doc`（由 `output_path` 决定）。
3. **精细化编辑**（`office_edit_word`）：声明式 `operations[]`，无需 LLM 写 JavaScript。
4. **格式覆盖**：至少 **`.odt`、`.docx`、`.doc`**；并支持 `core/categories.py` 中全部 `WORD_EXTENSIONS`。
5. **架构对齐**：代码在 `word/{parser,builder,schemas,tools}/`；管线用 `core/builder_runtime.py`；`registry.py` 注册。
6. **向后兼容**：`legacy/read_document`、`legacy/edit_document`、`legacy/merge_documents`、`legacy/apply_template` 保留旧名与行为。

### 1.3 非目标（Out of Scope v1）

- 修订模式、批注、脚注/endnote 完整 CRUD（v1 可只读存在性）
- 复杂样式/theme 全量编辑（v1 支持 named style 引用与基础 bold/italic）
- 邮件合并域（MERGEFIELD）——可用 template + `office_apply_template_word` 替代
- 在线 DocumentEditor 嵌入 URL
- 将 `.doc` 作为**推荐输出**格式（可读可写；新建推荐 `.docx` 或 `.odt`）

---

## 2. 在新架构中的位置

### 2.1 分层与依赖

```mermaid
flowchart TB
    subgraph MCP["MCP 层"]
        Adapter[office_tool_adapter.py]
        Registry[registry.py]
    end

    subgraph WordTools["word/tools/*"]
        ReadT[read.py]
        CreateT[create.py]
        EditT[edit.py]
        MergeT[merge.py]
        TemplateT[template.py]
        EditScriptT[edit_script.py]
    end

    subgraph WordDomain["word 领域层"]
        ParserHTML[parser/html.py]
        ParserDoc[parser/document.py]
        Builder[builder/create|edit|merge|template.py]
        Schemas[schemas/*]
    end

    subgraph Core["core/"]
        Runtime[builder_runtime.py]
        Sidecar[builder_json_sidecar.py]
        Categories[categories.py]
        CoarseRead[coarse_read.py]
    end

    Adapter --> Registry
    Registry --> WordTools
    WordTools --> WordDomain
    WordTools --> Core
    WordDomain --> Core
```

**与 presentation 平行**：`word/` 不 import `presentation/`；共用 `core/`。

### 2.2 双轨读取策略

| 模式 | 工具 | 路径 | 用途 |
|------|------|------|------|
| **精读（structured）** | `office_read_word` | Builder `doc.ToJSON(...)` → sidecar → `parser/document.py` | 编辑前定位；读→改闭环 |
| **粗读（兼容）** | `office_read_document` | Conversion → HTML → `parser/html.py` | 跨类别 legacy；快速预览 |
| **粗读 fallback** | `office_read_word` `format=text` | Conversion HTML → 纯文本 | DocumentServer 不可 Builder 时降级 |

**默认**：LLM 编辑 Word 类文件前调用 **`office_read_word`**，不用 `office_read_document` 的 `elements[].index`。

### 2.3 工具矩阵

| MCP 工具名 | 代码位置 | 类型 | 说明 |
|------------|----------|------|------|
| `office_read_word` | `word/tools/read.py` | **新增** | 精读 + 统一 schema |
| `office_create_word` | `word/tools/create.py` | **新增** | 声明式 `sections[]` |
| `office_edit_word` | `word/tools/edit.py` | **新增** | 声明式 `operations[]` |
| `office_merge_word` | `word/tools/merge.py` | **迁移** | 自 `merge_document.py`；支持 output ext |
| `office_apply_template_word` | `word/tools/template.py` | **迁移** | 自 `apply_template.py` |
| `office_edit_word_script` | `word/tools/edit_script.py` | **迁移** | 原 `edit_document`（裸 JS） |
| `office_read_document` | `legacy/read_document.py` | 保留 | 全类别粗读 |
| `office_edit_document` | `legacy/edit_document.py` | 保留 | → `edit_word_script` 别名 |
| `office_merge_documents` | `legacy/merge_documents.py` | 保留 | → `merge_word` 别名 |
| `office_apply_template` | `legacy/apply_template.py` | 保留 | → `apply_template_word` 别名 |
| `office_execute_builder` | `gateway/execute_builder.py` | 保留 | 高级 JS |
| `office_call_api` | `gateway/call_api.py` | 保留 | convert 等 |

注册经 `registry.py`；legacy 名可指向同一 handler（避免双份逻辑）。

### 2.4 统一 read 顶层 schema

```json
{
  "category": "word",
  "title": "Project Proposal",
  "unit_count": 24,
  "units": "<与 blocks[] 相同内容>",
  "blocks": [],
  "word_count": 1840,
  "page_count": 6,
  "source_path": "gs://bucket/proposal.docx",
  "source_path_format": "gs://bucket/path/to/file.ext",
  "read_mode": "fine",
  "_locator_note": "Use block_index, heading_path, or match_text with office_edit_word.",
  "_note": "Do not use office_read_document elements[].index with GetElement(i)."
}
```

| 统一字段 | word 映射 |
|----------|-----------|
| `units[]` | 与 `blocks[]` **同内容**（须 mirror，见架构 §4） |
| `unit_count` | `len(blocks)` |

---

## 3. 支持格式

### 3.1 用户重点格式

| 扩展名 | 角色 | OpenFile / CreateFile | 说明 |
|--------|------|---------------------|------|
| **`.docx`** | 推荐新建/交换 | `"docx"` | Office Open XML；merge 历史默认 |
| **`.odt`** | 推荐（开放文档） | `"odt"` | OpenDocument Text；与 docx 共用 Document API |
| **`.doc`** | legacy 互操作 | `"doc"` | 二进制 Word；可读可写；输出优先 docx/odt |

### 3.2 完整 Word 类扩展名

`core/categories.py` → `WORD_EXTENSIONS`（节选）：

```
doc, docm, docx, dot, dotm, dotx, fodt, hwp, hwpx, odt, ott,
rtf, txt, wps, xml, ...
```

入口校验：`classify_file_ext(ext) == "word"`。

| 场景 | 建议 |
|------|------|
| LLM 新建 | `output_path` 以 **`.docx`** 或 **`.odt`** 结尾 |
| 读取 legacy `.doc` | 支持；OpenFile 用 `"doc"` |
| 保存格式 | 由 `output_path` 扩展名 → `builder.SaveFile(ext, ...)` |
| merge 输出 | **修复**：`SaveFile` 使用 `output_path` 扩展名，不再写死 docx |

---

## 4. 工具规格

### 4.1 `office_read_word`

**代码**：`word/tools/read.py` → `word/parser/document.py` + `core/builder_json_sidecar.py`  
**降级**：`core/coarse_read.py`（Conversion HTML，复用 `parser/html.py`）

#### 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `source_path` / `source_url` | string | 二选一 | 源文件 |
| `format` | enum | 否 | `structured`（默认）\| `outline` \| `text` |
| `options.read_mode` | enum | 否 | `fine`（默认）\| `coarse`（仅 Conversion HTML） |
| `options.include_tables` | bool | 否 | structured 是否展开表格单元格，默认 true |
| `options.max_blocks` | int | 否 | 截断块数（大文档） |

#### 精读实现（`read_mode=fine`）

Sidecar 脚本（示意）：

```javascript
builder.OpenFile("{url}", "{ext}");
var doc = Api.GetDocument();
var jsonStr = JSON.stringify(doc.ToJSON(true, true, true, true, true, true));
builder.CreateFile("txt");
var tmp = Api.GetDocument();
tmp.GetElement(0).AddText(jsonStr);
builder.SaveFile("txt", "structure.txt");
builder.CloseFile();
```

`word/parser/document.py`：`parse_document_json(raw) -> blocks[]`

#### Block schema（`format=structured`）

```json
{
  "category": "word",
  "title": "Project Proposal",
  "unit_count": 5,
  "blocks": [
    {
      "block_index": 0,
      "type": "heading1",
      "text": "Project Proposal",
      "style_name": "Heading 1",
      "heading_path": ["Project Proposal"]
    },
    {
      "block_index": 1,
      "type": "heading2",
      "text": "Background",
      "style_name": "Heading 2",
      "heading_path": ["Project Proposal", "Background"]
    },
    {
      "block_index": 2,
      "type": "paragraph",
      "text": "This project aims to ...",
      "style_name": "Normal"
    },
    {
      "block_index": 3,
      "type": "table",
      "rows": [["Item", "Cost"], ["A", "100"]],
      "row_count": 2,
      "col_count": 2
    }
  ],
  "units": "<与 blocks[] 相同内容>",
  "word_count": 42,
  "page_count": 1,
  "read_mode": "fine",
  "_locator_note": "Edit with office_edit_word using block_index, heading_path, or match_text."
}
```

`format=outline`：`[{block_index, type, text, heading_path}]`（仅 heading*）。  
`format=text`：纯文本（fine 模式由 blocks 拼接；coarse 由 HTML 提取）。

**定位符优先级（供 edit）**：`block_index` > `heading_path` > `match_text` > `style_name`（同页多处时慎用）。v1 **不实现** `relative_index`（**ADR-011**）。

---

### 4.2 `office_create_word`

**代码**：`word/tools/create.py` → `word/builder/create.py`

#### 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `sections` | array | 是 | `word/schemas/section_spec.py` |
| `output_path` | string | 是 | `.docx` / `.odt` / `.doc` |
| `options.title` | string | 否 | 文档标题属性 |
| `options.page_size` | string | 否 | `A4` \| `Letter`（v1 枚举） |
| `options.add_toc` | bool | 否 | 在**第一个 section 之前**插入目录（**ADR-012**：v1 仅文首；不支持文末） |

#### SectionSpec（v1）

```json
{
  "type": "heading1",
  "text": "Annual Report"
}
```

```json
{
  "type": "paragraph",
  "text": "Summary paragraph.",
  "bold": false
}
```

```json
{
  "type": "bullets",
  "items": ["Point A", "Point B"],
  "level": 1
}
```

```json
{
  "type": "table",
  "rows": [
    ["Header A", "Header B"],
    ["Cell 1", "Cell 2"]
  ],
  "header_row": true
}
```

```json
{
  "type": "page_break"
}
```

**v1 `type` 枚举**：`heading1`–`heading3`、`paragraph`、`bullets`、`table`、`page_break`。

#### Builder 示意

```javascript
builder.CreateFile("docx");  // or odt per output_path
var doc = Api.GetDocument();
// 若 options.add_toc: 在 Push 任何 section 之前插入 TOC
var para = Api.CreateParagraph();
para.AddText("Annual Report");
para.SetStyle("Heading 1");
doc.Push(para);
// ... sections → Push / CreateTable ...
builder.SaveFile("docx", "output.docx");
builder.CloseFile();
```

执行：`run_builder_script(script, output_path=...)`

---

### 4.3 `office_edit_word`

**代码**：`word/tools/edit.py` → `word/builder/edit.py`

#### 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `source_path` / `source_url` | string | 二选一 | 源文件 |
| `output_path` | string | 是 | 输出路径 |
| `operations` | array | 是 | `word/schemas/edit_ops.py` |
| `options.backup` | bool | 否 | object storage 备份 |

#### Operation 类型（v1）

| op | 主要字段 | 说明 |
|----|----------|------|
| `search_replace` | `search`, `replace`, `scope?` | 全文或限定 `heading_path` 子树 |
| `set_block_text` | `block_index` 或 `heading_path`+`match_text`, `text` | 替换块文本 |
| `set_heading` | `heading_path` 或 `block_index`, `text`, `level?` | 改标题 |
| `insert_paragraph` | `after`（block_index / heading_path / `"start"`/`"end"`), `text` | 插入段 |
| `insert_bullets` | `after`, `items[]` | 插入列表 |
| `insert_table` | `after`, `rows[][]` | 插入表格 |
| `delete_block` | `block_index` 或 `match_text` | 删除块 |
| `apply_style` | `block_index`, `style_name` | 应用段落样式 |
| `add_page_break` | `after` | 分页 |
| `insert_toc` | `{}` | 插入目录（文档级） |

**定位**：与 read 返回的 `block_index` / `heading_path` 对齐；编辑前应用 **`office_read_word`**。

示例：

```json
{
  "source_path": "gs://bucket/report.odt",
  "output_path": "gs://bucket/report-v2.odt",
  "operations": [
    {
      "op": "set_heading",
      "heading_path": ["Annual Report", "Background"],
      "text": "Background & Context"
    },
    {
      "op": "insert_bullets",
      "after": {"heading_path": ["Annual Report", "Background & Context"]},
      "items": ["Market shift in Q1", "Regulatory update"]
    },
    {
      "op": "search_replace",
      "search": "DRAFT",
      "replace": "FINAL",
      "scope": "document"
    }
  ]
}
```

#### 实现映射（Builder）

| op | ONLYOFFICE 思路 |
|----|-----------------|
| `search_replace` | `doc.SearchAndReplace({searchString, replaceString})` |
| `set_block_text` | `Search(unique_snippet)` → 父 paragraph `SetText` / Replace |
| `insert_paragraph` | `Api.CreateParagraph()` + `doc.Push` / `InsertContent` |
| `insert_table` | `Api.CreateTable(cols, rows)` + Push |
| `delete_block` | Search 定位 → Remove 元素（或 ToJSON 重建——v2） |

#### `block_index` 语义与 Builder 映射

`block_index` 是 **`word/parser/document.py` 解析 `ToJSON` 后的逻辑序号**（0-based），**不是** Conversion HTML 的 `elements[].index`，也**不保证**等于 `Api.GetDocument().GetElement(i)` 的 `i`。

| 定位方式 | Builder 实现（v1） |
|----------|-------------------|
| `block_index` | 从 read 结果取该块的 `text` 首句/唯一片段 → `doc.Search(...)` → 父 paragraph `SetText` / Replace |
| `heading_path` | 拼接路径末级标题文本 → `Search`；或在 `heading_path` 子树内 `SearchAndReplace` |
| `match_text` | 直接 `Search(match_text)` |
| `style_name` | `GetAllParagraphs()` / 样式过滤（多处同样式时慎用） |

**稳定性**：`block_index` 仅在与最近一次 **`office_read_word`（`read_mode=fine`）** 对应的文件版本上有效；任何 edit 后若继续用 index，**须 re-read**。复杂块（嵌套表格、文本框）v1 优先 `heading_path` + `match_text`，或 fallback `office_edit_word_script`。

复杂 op（跨节排版）v1 可 fallback 提示使用 `office_edit_word_script`。

---

### 4.4 `office_merge_word`

**代码**：`word/tools/merge.py` → `word/builder/merge.py`（自 `merge_document.py` 迁入）

#### 变更（相对 legacy）

1. **`SaveFile` 扩展名**跟随 `output_path`（支持合并为 `.odt`）。
2. 工具名 **`office_merge_word`**；legacy `office_merge_documents` 别名。
3. 脚本生成用 `core/builder_js`；执行用 `core/builder_runtime`。

#### 参数

同 legacy：`source_paths` / `source_urls`、`output_path`、`options.add_page_break`、`options.add_toc`。

---

### 4.5 `office_apply_template_word`

**代码**：`word/tools/template.py` → `word/builder/template.py`

占位符：`{{key}}`；`data` 值 `str()` 后 `SearchAndReplace`。

Legacy 名：`office_apply_template`。

---

### 4.6 `office_edit_word_script`

**代码**：`word/tools/edit_script.py`（原 `edit_document.py`）

裸 `edit_script`；OpenFile/SaveFile 由 `run_builder_on_source` 注入。

Legacy 名：`office_edit_document`。

**与 `office_edit_word` 分工**：默认 declarative edit；仅当 operations 无法表达时用 script。

---

## 5. 目录与文件清单

### 5.1 word 垂直模块

```
aiecs/tools/office_tool/word/
├── __init__.py
├── parser/
│   ├── html.py                   # ← html_parser.py（Conversion HTML）
│   └── document.py               # NEW: ToJSON → blocks[]
├── builder/
│   ├── create.py
│   ├── edit.py
│   ├── merge.py                  # ← merge_document 脚本生成
│   └── template.py               # ← apply_template 脚本生成
├── schemas/
│   ├── read.py
│   ├── section_spec.py
│   └── edit_ops.py
└── tools/
    ├── read.py                   # office_read_word
    ├── create.py                 # office_create_word
    ├── edit.py                   # office_edit_word
    ├── merge.py                  # office_merge_word
    ├── template.py               # office_apply_template_word
    └── edit_script.py            # office_edit_word_script
```

### 5.2 core 补充

```
core/coarse_read.py               # Conversion 粗读（legacy + read_word fallback）
```

其余 `builder_runtime`、`builder_json_sidecar`、`categories` 与 presentation 共用。

### 5.3 legacy

```
legacy/read_document.py           # 全类别；word 走 HTML
legacy/edit_document.py           # → edit_word_script
legacy/merge_documents.py         # → merge_word
legacy/apply_template.py          # → apply_template_word
```

### 5.4 测试

```
tests/office_mcp/word/
├── test_document_parser.py
├── test_read_word.py
├── test_create_word.py
├── test_edit_word.py
├── test_merge_word.py
├── test_apply_template_word.py
├── test_edit_word_script.py
├── test_legacy_compat.py
└── test_e2e_word_tools.py        # @pytest.mark.word @pytest.mark.e2e
```

---

## 6. LLM 工作流

### 6.1 创建 `.odt` / `.docx` 报告

```
office_create_word({
  sections: [...],
  output_path: "gs://bucket/report.odt"
})
```

### 6.2 编辑已有文档

```
1. office_read_word({ source_path, format: "structured" })
2. 根据 block_index / heading_path 构造 operations
3. office_edit_word({ source_path, output_path, operations })
```

### 6.3 模板

```
office_apply_template_word({ template_path, data, output_path })
```

### 6.4 合并

```
office_merge_word({ source_paths, output_path: ".../combined.odt", options: {...} })
```

### 6.5 高级

```
office_edit_word_script({ edit_script: "oDoc.Search(...)...", ... })
office_execute_builder({ script: "builder.CreateFile('odt'); ..." })
```

详见 [OFFICE_MCP_WORD_LLM_GUIDE.md](./OFFICE_MCP_WORD_LLM_GUIDE.md)。

---

## 7. 测试策略

### 7.1 单元

- `parser/document.py`：fixture ToJSON → blocks / heading_path
- `parser/html.py`：ONLYOFFICE HTML fixture（回归现有测试）
- operations schema 校验；`.doc` / `.odt` / `.docx` ext 校验

### 7.2 E2E

```bash
DOCUMENTSERVER_URL=... DOCUMENTSERVER_JWT_SECRET=... \
  poetry run pytest tests/office_mcp/word/ -v -m "word and e2e"
```

用例：

1. `create_word` docx → `read_word` → 断言 blocks
2. `edit_word` search_replace + insert_bullets → read 验证
3. **odt 往返**：create odt → edit → save odt
4. **doc 读取**：open doc → read_word fine or coarse
5. `merge_word` → output `.odt`（非写死 docx）
6. legacy `office_read_document` / `office_merge_documents` 行为不变

---

## 8. 实施计划

**实现细节**（文件级 API、Pydantic schema、Builder 模板、PR 分解、测试 checklist）见 **[OFFICE_MCP_WORD_IMPLEMENTATION_DESIGN.md](./OFFICE_MCP_WORD_IMPLEMENTATION_DESIGN.md)**。

| 阶段 | 架构 | Word 交付 | 验证 |
|------|------|-----------|------|
| **M0** | `core/builder_runtime`, `builder_js` | — | pytest 全绿 |
| **M1** | `core/categories`, storage 迁入 | — | import 更新 |
| **M2-W0** | 建 `word/` 树 | 迁入 html/merge/template/edit_script | 无行为变更 |
| **M2-W1** | | `office_read_word`（fine + coarse） | 单元 + E2E |
| **M2-W2** | | `office_create_word` + `office_edit_word` | E2E docx/odt |
| **M2-W3** | | `office_merge_word` + `office_apply_template_word` + legacy 别名 | merge odt 输出 |
| **M3** | `registry.py` | 注册全部 word 工具 | health 工具列表 |
| **W4** | | 扩展 op：footnote、图片、分节 | 按需 |

Word 迁移 **M2** 可与 presentation **M4** 并行，均依赖 **M0–M1**。

### 8.1 实施状态（M7 · Gate G5）

| 阶段 | 状态 | 代码位置 |
|------|------|----------|
| M0–M1 core | ✅ | `aiecs/tools/office_tool/core/` |
| M2 W0–W3 | ✅ | `word/` 六工具 |
| M3 registry | ✅ | `registry.py` 注册 word×6 |
| M7 文档 | ✅ | 本表 + [LLM 指南](./OFFICE_MCP_WORD_LLM_GUIDE.md) |

---

## 9. 向后兼容

| 项目 | 策略 |
|------|------|
| `office_read_document` | 保留；word 仍 Conversion→HTML；description 指向 `office_read_word` |
| `office_edit_document` | legacy 别名 → `edit_word_script` |
| `office_merge_documents` | legacy 别名 → `merge_word`；修复 output ext |
| `office_apply_template` | legacy 别名 → `apply_template_word` |
| `elements[].index` | 继续在 coarse read 返回；`_note` 禁止用于 GetElement |

---

## 10. 风险与缓解

| 风险 | 缓解 |
|------|------|
| ToJSON 过大 | `max_blocks`；outline 模式 |
| ToJSON 解析复杂 | v1 只暴露 blocks 子集；复杂版式走 script |
| `.doc` 二进制兼容性 | E2E 覆盖；输出推荐 docx/odt |
| HTML index 误导 LLM | `office_read_word` 默认 fine；明确 `_locator_note` |
| merge 写死 docx | W3 必改 SaveFile ext |
| heading_path 重名 | 路径数组 + 最近 read 的 block_index |

---

## 11. 参考

- [OFFICE_MCP_WORD_IMPLEMENTATION_DESIGN.md](./OFFICE_MCP_WORD_IMPLEMENTATION_DESIGN.md) — W0–W3 可执行实现设计
- [implementation_design.md](./implementation_design.md) §7.1 — 全局 M2 任务
- [OFFICE_TOOL_ARCHITECTURE_REORG.md](./OFFICE_TOOL_ARCHITECTURE_REORG.md) §7.1
- [ONLYOFFICE Document API](https://api.onlyoffice.com/docs/office-api/usage-api/document-api/)
- [ApiDocument ToJSON / FromJSON](https://api.onlyoffice.com/docs/office-api/usage-api/document-api/ApiDocument/Methods/ToJSON/)
- [CreateFile](https://api.onlyoffice.com/docs/document-builder/builder-framework/CDocBuilder/CreateFile/)
- 现有实现：`read_document.py`、`edit_document.py`、`merge_document.py`、`apply_template.py`、`html_parser.py`

---

## 附录 A：`.odt` / `.docx` / `.doc` 对照

| 维度 | .docx | .odt | .doc |
|------|-------|------|------|
| 标准 | OOXML | ODF | Microsoft 97–2003 |
| Builder CreateFile | `"docx"` | `"odt"` | `"doc"` |
| LLM 新建推荐 | ✅ 默认 | ✅ 开放文档场景 | ⚠️ 仅兼容需求 |
| 精读 API | `Api.GetDocument()` | 同左 | 同左 |
| Conversion 粗读 | → html | → html | → html |

三者在本升级中**共用** `word/` 模块与同一套 tools；差异仅在 `file_ext` 与 SaveFile 格式。
