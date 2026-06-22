# Office MCP Presentation Upgrade

让 LLM 对 `.odp` / `.pptx` / `.ppt` 等 presentation 文件进行**精细化创建**与**精细化编辑**的升级设计。

> **状态**：**已实现**（M4）；M7 文档同步  
> **范围**：`aiecs/tools/office_tool/presentation/`（新架构垂直模块）  
> **依赖**：ONLYOFFICE DocumentServer Document Builder + Conversion API；`core/` 公共层  
> **关联**：[OFFICE_TOOL_ARCHITECTURE_REORG.md](./OFFICE_TOOL_ARCHITECTURE_REORG.md)（横向架构）、[OFFICE_MCP_PRESENTATION_IMPLEMENTATION_DESIGN.md](./OFFICE_MCP_PRESENTATION_IMPLEMENTATION_DESIGN.md)（实现设计）、[OFFICE_MCP_PRESENTATION_LLM_GUIDE.md](./OFFICE_MCP_PRESENTATION_LLM_GUIDE.md)（LLM 调用指南）

本升级是架构重组中 **M4 阶段**的 presentation 垂直交付，遵循 `office_{action}_{category}` 命名，代码落在 `presentation/{parser,builder,schemas,tools}/`，公共逻辑复用 `core/`。

---

## 1. 背景与目标

### 1.1 问题

当前 Office MCP 对 presentation 的支持停留在「粗粒度」：

| 能力 | Word (docx) | Presentation (ppt/pptx/odp) |
|------|-------------|-------------------------------|
| 结构化读取 | Conversion → HTML → DOM 解析 | Conversion → **txt** → 段落块 |
| 创建 | 有 E2E 示例与文档 | 无示例；需 LLM 裸写 Presentation API |
| 编辑 | `Search()` / `GetStyleName()` 有明确指引 | 工具描述面向 Word；无 slide/shape 定位 |
| 合并 / 模板 | `office_merge_documents` / `office_apply_template` | 硬编码 Word API，不可用 |
| 读→改闭环 | 可用（有 caveats） | **不可用**（index 语义不一致） |

LLM 无法可靠回答诸如「改第 3 页标题」「在第 2 页插入 bullet 列表」「复制母版布局新建一页」等需求。

### 1.2 目标（Must Have）

1. **精细化读取**：返回 slide 级结构（页码、标题、形状、文本、类型、可选位置）。
2. **精细化创建**：LLM 用声明式 JSON 描述 slides，MCP 生成 Builder 脚本并输出 pptx/odp。
3. **精细化编辑**：LLM 用声明式 **operations** 数组（按 slide_index / shape_index / text 定位）修改已有文件。
4. **格式覆盖**：输入/输出支持 `.ppt`、`.pptx`、`.odp`（及 `core/categories.py` 中 `PRESENTATION_EXTENSIONS`）；**推荐** LLM 输出 `.pptx` 或 `.odp`。
5. **架构对齐**：实现于 `presentation/` 子树；Builder 管线走 `core/builder_runtime.py`；工具经 `registry.py` 注册。
6. **向后兼容**：`legacy/read_document.py` 对 presentation 继续 txt 粗读；gateway 工具不变。

### 1.3 非目标（Out of Scope v1）

- 动画、切换效果、演讲者备注的完整 CRUD（v1 可只读 notes 文本）
- 在线协作编辑 URL（DocumentEditor 嵌入）
- 复杂图表数据系列编辑（v1 仅识别 chart 存在与标题）
- 与 PPT-Tool（Banana Slides / AI 生图 PPT）合并——二者定位不同，Office MCP 走 DocumentServer 原生编辑

---

## 2. 在新架构中的位置

### 2.1 分层与依赖

```mermaid
flowchart TB
    subgraph MCP["MCP 层"]
        Adapter[office_tool_adapter.py]
        Registry[registry.py]
    end

    subgraph PresTools["presentation/tools/*"]
        ReadT[read.py]
        CreateT[create.py]
        EditT[edit.py]
        MergeT[merge.py]
        TemplateT[template.py]
    end

    subgraph PresDomain["presentation 领域层"]
        Parser[parser/slides.py]
        Builder[builder/create|edit|merge|template.py]
        Schemas[schemas/*]
    end

    subgraph Core["core/"]
        Runtime[builder_runtime.py]
        Sidecar[builder_json_sidecar.py]
        Categories[categories.py]
        Source[source.py]
        BuilderJS[builder_js.py]
        Storage[storage/*]
    end

    Adapter --> Registry
    Registry --> PresTools
    PresTools --> PresDomain
    PresTools --> Core
    PresDomain --> Core
```

**依赖约束**（与 [OFFICE_TOOL_ARCHITECTURE_REORG.md §10](./OFFICE_TOOL_ARCHITECTURE_REORG.md) 一致）：

- `presentation/` **可** import `core/`；**不可** import `word/` / `spreadsheet/` / `pdf/`。
- `core/` **不可** import `presentation/`。
- 类别内职责：`tools/` 薄封装 MCP schema；`builder/` 生成 JS；`parser/` 解析 sidecar JSON；`schemas/` 校验 spec/operations。

### 2.2 设计原则

- **LLM 不写 Builder JS**（默认路径）：`presentation/builder/*` 根据 schemas 生成脚本，经 `core/builder_runtime.run_builder_script()` 执行。
- **高级路径**：`gateway/execute_builder.py`（`office_execute_builder`）；勿用 `legacy/edit_document` 编辑 pptx（Word API）。
- **精读走 Builder JSON**：`SlidesToJSON` + `core/builder_json_sidecar.py`；不用 Conversion txt 做 structured read。
- **稳定定位符**：`slide_index`（0-based）+ `shape_index`（页内 0-based）+ 可选 `match_text` / `role` 回退。
- **跨类别 read 顶层字段**：与架构统一（§2.4）。

### 2.3 工具矩阵（presentation 垂直 + 兼容层）

命名规范：`office_{action}_{category}`，`category = presentation`。

| MCP 工具名 | 代码位置 | 类型 | 说明 |
|------------|----------|------|------|
| `office_read_presentation` | `presentation/tools/read.py` | **新增** | 结构化读取 |
| `office_create_presentation` | `presentation/tools/create.py` | **新增** | 声明式创建 |
| `office_edit_presentation` | `presentation/tools/edit.py` | **新增** | 声明式 operations 编辑 |
| `office_merge_presentations` | `presentation/tools/merge.py` | **新增** | 按 slide 合并 |
| `office_apply_template_presentation` | `presentation/tools/template.py` | **新增** | 模板占位符填充 |
| `office_read_document` | `legacy/read_document.py` | 保留 | presentation 仍 Conversion→txt |
| `office_execute_builder` | `gateway/execute_builder.py` | 保留 | 手写 Presentation API |
| `office_call_api` | `gateway/call_api.py` | 保留 | convert / forcesave / info |

注册：五个新工具在各自 `tools/*.py` 导出 `TOOL_DEF` + handler，由 `registry.py` 汇总；**不再**在 `office_tool_adapter.py` 手工逐个 import。

对外 MCP 工具数：六 → **十一**（+5 presentation；health / OpenAI tools 来自 registry）。

### 2.4 统一 read 顶层 schema（跨类别）

`office_read_presentation` 在 presentation 专有字段之外，包含架构统一的顶层键：

```json
{
  "category": "presentation",
  "title": "Quarterly Review",
  "unit_count": 12,
  "units": [],
  "word_count": 420,
  "source_path": "gs://bucket/deck.pptx",
  "source_path_format": "gs://bucket/path/to/file.ext",
  "_locator_note": "Use slide_index and shape_index with office_edit_presentation. layout values for create/add_slide must match layouts[] exactly (ADR-016).",
  "_note": "Do not use office_read_document elements[].index for editing."
}
```

| 统一字段 | presentation 映射 |
|----------|---------------------|
| `unit_count` | slide 总数（同 `slide_count`，两者并存，`slide_count` 为便捷别名） |
| `units[]` | 与 `slides[]` **同内容**（须 mirror，见架构 §4） |

实现：**`slides[]` 与 `units[]` 均填充相同 slide 对象**；跨类别 Agent 可读 `units`，人类可读 `slides`。

### 2.5 数据流

```mermaid
flowchart TB
    LLM[LLM Agent]
    Tool[presentation/tools/*]
    Runtime[core/builder_runtime]
    Sidecar[core/builder_json_sidecar]
    Parser[presentation/parser/slides.py]
    DS[DocumentServer Builder]
    Store[(gs:// / s3://)]

    LLM -->|office_read_presentation| Tool
    Tool --> Sidecar
    Sidecar --> Runtime
    Runtime --> DS
    DS -->|sidecar txt| Runtime
    Runtime --> Parser
    Parser -->|slides[]| LLM

    LLM -->|office_create_presentation| Tool
    Tool -->|builder/create.py| Runtime
    Runtime --> DS
    Runtime --> Store

    LLM -->|office_edit_presentation| Tool
    Tool -->|builder/edit.py| Runtime
    Runtime --> DS
    Runtime --> Store
```

---

## 3. 支持格式

复用 `core/categories.py`（自 `conversion_output.py` 迁入）中的 `PRESENTATION_EXTENSIONS`：

```
dps, dpt, fodp, key, odg, odp, otp, pot, potm, potx,
pps, ppsm, ppsx, ppt, pptm, pptx, sxi
```

入口校验：`classify_file_ext(ext) == "presentation"`，否则返回 `{isError, text}`。

| 场景 | 建议 |
|------|------|
| LLM 新建文件 | `output_path` 以 `.pptx` 或 `.odp` 结尾 |
| 读取已有文件 | 任意 presentation 扩展名 |
| 保存格式 | `core/categories.builder_create_type(output_ext)` → `SaveFile` |
| 读取实现 | `core/builder_js.open_file(url, ext)` + sidecar 脚本 |

**odp**：Builder 支持 `CreateFile("odp")` / `OpenFile(..., "odp")`；与 pptx 共用 `Api.GetPresentation()`。

**legacy 粗读**：`legacy/read_document.py` 仍用 `llm_coarse_output_type(ext)` → presentation 为 `txt`（`core/categories.py`）。

---

## 4. 工具规格

### 4.1 `office_read_presentation`

**代码**：`presentation/tools/read.py` → `presentation/parser/slides.py` + `core/builder_json_sidecar.py`

**用途**：编辑前读取 slide/shape 结构。`office_read_document` 对 presentation 仅 txt 粗读，**不可**用于 edit 定位（见架构 §5.2）。

#### 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `source_path` | string | 二选一 | `gs://` / `s3://` |
| `source_url` | string | 二选一 | HTTP(S) 可抓取 URL |
| `format` | enum | 否 | `structured`（默认）\| `outline` \| `text` |
| `options.read_mode` | enum | 否 | `fine`（默认，Builder SlidesToJSON）\| `coarse`（Conversion txt；**不可**用于 edit 定位） |
| `options.slide_range` | [int, int] | 否 | Inclusive 起止 slide_index；默认全部 |
| `options.include_notes` | bool | 否 | 演讲者备注，默认 false |
| `options.include_layout_meta` | bool | 否 | layout/master 名称，默认 false |

**降级**：`read_mode=fine` 且 Builder 失败时，可 fallback 到 `coarse` 并在 `_note` 中警告「须 re-read fine 后再 edit」。

#### 实现要点

1. `core/source.resolve_document_source()` 解析 URL 与扩展名。
2. `core/builder_json_sidecar.read_sidecar_json()` 执行 extract 脚本（见 §4.6）。
3. Extract 脚本内使用 `pres.SlidesToJSON(start, end, false, false, false, false)`。
4. `presentation/parser/slides.py`：`parse_slides_json(raw) -> slides[]`。
5. Schema 校验：`presentation/schemas/read.py`。

#### 返回 schema（`format=structured`）

```json
{
  "category": "presentation",
  "title": "Quarterly Review",
  "unit_count": 12,
  "slide_count": 12,
  "layouts": [
    "Title Slide",
    "Title and Content",
    "Section Header",
    "Two Content"
  ],
  "slides": [
    {
      "slide_index": 0,
      "title": "Quarterly Review",
      "layout": "Title Slide",
      "shapes": [
        {
          "shape_index": 0,
          "type": "shape",
          "role": "title",
          "text": "Quarterly Review",
          "placeholder_type": "title"
        },
        {
          "shape_index": 1,
          "type": "shape",
          "role": "subtitle",
          "text": "Q1 2026"
        }
      ],
      "notes": ""
    }
  ],
  "units": "<与 slides[] 相同内容>",
  "read_mode": "fine",
  "word_count": 420,
  "source_path": "gs://bucket/deck.pptx",
  "source_path_format": "gs://bucket/path/to/file.ext",
  "_locator_note": "Use slide_index and shape_index with office_edit_presentation. layout values for create/add_slide must match layouts[] exactly (ADR-016).",
  "_note": "Do not use office_read_document index."
}
```

`format=outline`：`units` 仅 `{slide_index, title}`。  
`format=text`：按页拼接，分隔符 `\n--- slide N ---\n`（优于 legacy Conversion txt）。

**Layout 枚举（ADR-016）**：fine read 响应顶层 **`layouts[]`** 列出当前 deck 可用 layout 名称（来自 master）。`office_create_presentation` 与 `add_slide` 的 `layout` 字段须 **精确抄录**（大小写敏感）；Pydantic 校验拒绝非枚举值。无 fuzzy、无 `default_layout` fallback。新建空白 deck 前可先 read 模板 deck 获取 `layouts[]`；**odp E2E 须维护 layout 枚举 fixture 表**（与 pptx 分表）。

---

### 4.2 `office_create_presentation`

**代码**：`presentation/tools/create.py` → `presentation/builder/create.py` → `core/builder_runtime.py`

#### 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `slides` | array | 是 | `presentation/schemas/slide_spec.py`；每页 `layout` 须为 read 返回的 `layouts[]` 成员 |
| `output_path` | string | 是 | 扩展名决定输出格式 |
| `options.size` | object | 否 | `{width, height}` EMU；默认 16:9 |

#### SlideSpec

定义于 `presentation/schemas/slide_spec.py`：

```json
{
  "layout": "Title and Content",
  "title": "Slide title",
  "subtitle": "Optional",
  "bullets": ["Point A", "Point B"],
  "shapes": [
    {
      "type": "textbox",
      "text": "Free text",
      "position": {"x": 608400, "y": 1267200},
      "size": {"width": 7772400, "height": 1380000}
    },
    {
      "type": "image",
      "url": "https://example.com/logo.png",
      "position": {"x": 0, "y": 0},
      "size": {"width": 914400, "height": 914400}
    }
  ],
  "notes": "Speaker notes"
}
```

**v1 shape types**：`title`、`body` / `bullets`、`textbox`、`image`（URL）。

#### Builder 生成

`presentation/builder/create.py`：

```python
def build_create_script(slides: list, out_ext: str, options: dict) -> str:
    """Uses core/builder_js for CreateFile, SaveFile, escape_js."""
```

示意 JS：

```javascript
builder.CreateFile("pptx");
var pres = Api.GetPresentation();
pres.SetSizes(9144000, 6858000);
// ... SlideSpec → shapes ...
builder.SaveFile("pptx", "output.pptx");
builder.CloseFile();
```

执行：

```python
script = build_create_script(...)
await run_builder_script(script, output_path=output_path)
```

---

### 4.3 `office_edit_presentation`

**代码**：`presentation/tools/edit.py` → `presentation/builder/edit.py`

#### 参数

| 参数 | 类型 | 必填 | 说明 |
|------|------|------|------|
| `source_path` / `source_url` | string | 二选一 | 源文件 |
| `output_path` | string | 是 | 输出路径 |
| `operations` | array | 是 | `presentation/schemas/edit_ops.py` |
| `options.backup` | bool | 否 | `core/storage` 备份（object storage） |

#### Operation 类型（v1）

| op | 字段 | 说明 |
|----|------|------|
| `set_text` | `slide_index`, `shape_index` 或 `match_text`, `text` | 替换形状内文本 |
| `set_title` | `slide_index`, `text` | 标题占位符 |
| `set_bullets` | `slide_index`, `items[]` | 正文 bullet |
| `add_slide` | `after_index`, `layout`（须 ∈ `layouts[]`）, `title`, ... | 插入页 |
| `delete_slide` | `slide_index` | 删除页 |
| `duplicate_slide` | `slide_index`, `after_index` | 复制页 |
| `move_slide` | `from_index`, `to_index` | 调整顺序 |
| `set_notes` | `slide_index`, `text` | 演讲者备注 |
| `replace_image` | `slide_index`, `shape_index`, `url` | 替换图片 |
| `remove_shape` | `slide_index`, `shape_index` | 删除形状 |

**定位优先级**：`shape_index` > `match_text` > `role`（`title` / `body`）。

#### 实现

1. 校验 `operations`（`presentation/schemas/edit_ops.py`）。
2. `presentation/builder/edit.py`：`build_edit_script(source_url, file_ext, operations, out_ext)`。
3. `run_builder_on_source(...)` 或 `run_builder_script(...)`（`core/builder_runtime.py`）。

**勿**复用 `word/tools/edit_script.py`（`Api.GetDocument()`）。

---

### 4.4 `office_merge_presentations`

**代码**：`presentation/tools/merge.py` → `presentation/builder/merge.py`

#### 参数

| 参数 | 类型 | 必填 |
|------|------|------|
| `source_paths` / `source_urls` | array | 二选一 |
| `output_path` | string | 是 |
| `options.separator_slide` | bool | 否，默认 false |

#### 实现

```javascript
builder.CreateFile("pptx");
var target = Api.GetPresentation();
// OpenFile → SlidesToJSON → FromJSON → AddSlide per source
builder.SaveFile("pptx", "output.pptx");
builder.CloseFile();
```

**勿**调用 `word/builder/merge.py`（`CreateFile("docx")`）。

---

### 4.5 `office_apply_template_presentation`

**代码**：`presentation/tools/template.py` → `presentation/builder/template.py`

#### 占位符（v1）

- **全局**：模板文本框写 `{{company_name}}`，`data.company_name` 全文替换。
- **按页**：模板写 `{{slide_1_title}}`，`data.slide_1_title` 替换（1-based 页码前缀 `slide_{N}_`）。

不支持 `{{slide:2:title}}` 语法（v1）。

#### 参数

| 参数 | 类型 | 必填 |
|------|------|------|
| `template_path` / `template_url` | string | 二选一 |
| `data` | object | 是 |
| `output_path` | string | 是 |

**勿**复用 `word/builder/template.py`（`Api.GetDocument().SearchAndReplace`）。

---

### 4.6 JSON 回传（sidecar）

**代码**：`core/builder_json_sidecar.py`（presentation / spreadsheet 共用模式）

`office_read_presentation` 通过 sidecar 取 Builder JSON，**推荐 v1 方案**：

```javascript
builder.OpenFile(url, ext);
var pres = Api.GetPresentation();
var last = pres.GetSlidesCount() - 1;
var jsonStr = JSON.stringify(pres.SlidesToJSON(0, last, false, false, false, false));
builder.CreateFile("txt");
var doc = Api.GetDocument();
doc.GetElement(0).AddText(jsonStr);
builder.SaveFile("txt", "structure.txt");
builder.CloseFile();
```

Python 流程：

```
read_builder_sidecar_text(source, ext, extract_script)
  → download structure.txt
  → presentation/parser/slides.parse_slides_json(text)
```

---

## 5. 目录与文件清单

### 5.1 presentation 垂直模块（本升级新建）

```
aiecs/tools/office_tool/presentation/
├── __init__.py
├── parser/
│   └── slides.py                 # SlidesToJSON → slides[] / units[]
├── builder/
│   ├── create.py                 # SlideSpec → JS
│   ├── edit.py                   # operations → JS
│   ├── merge.py
│   └── template.py
├── schemas/
│   ├── read.py                   # structured 返回类型
│   ├── slide_spec.py
│   └── edit_ops.py
└── tools/
    ├── read.py                   # OFFICE_READ_PRESENTATION_TOOL
    ├── create.py
    ├── edit.py
    ├── merge.py
    └── template.py
```

### 5.2 core 依赖（架构 M0–M1，presentation 实现前需就绪）

```
aiecs/tools/office_tool/core/
├── categories.py                 # PRESENTATION_EXTENSIONS, classify_file_ext
├── builder_runtime.py            # run_builder_script, run_builder_on_source
├── builder_js.py                 # escape_js, open_file, save_file, close_file
├── builder_json_sidecar.py       # read_builder_sidecar_text
├── coarse_read.py                # Conversion 粗读 fallback
├── source.py                     # resolve_document_source
└── storage/                      # upload, backup, signed URL
```

### 5.3 注册与 MCP 层

```
aiecs/tools/office_tool/registry.py     # 注册 presentation/tools/* 五工具
aiecs/mcp/office_tool_adapter.py        # 仅调用 registry（瘦适配）
```

### 5.4 测试（镜像 presentation/）

```
tests/office_mcp/presentation/
├── test_slides_parser.py
├── test_read_presentation.py
├── test_create_presentation.py
├── test_edit_presentation.py
├── test_merge_presentations.py
├── test_apply_template_presentation.py
└── test_e2e_presentation_tools.py      # @pytest.mark.presentation @pytest.mark.e2e
```

### 5.5 文档

| 文件 | 角色 |
|------|------|
| [OFFICE_MCP_PRESENTATION_UPGRADE.md](./OFFICE_MCP_PRESENTATION_UPGRADE.md) | 本文档 |
| [OFFICE_MCP_PRESENTATION_LLM_GUIDE.md](./OFFICE_MCP_PRESENTATION_LLM_GUIDE.md) | LLM 调用（需同步工具名） |
| [OFFICE_TOOL_ARCHITECTURE_REORG.md](./OFFICE_TOOL_ARCHITECTURE_REORG.md) | 横向架构与 M0–M6 迁移 |

---

## 6. LLM 推荐工作流

### 6.1 创建新 deck

```
office_create_presentation({ slides: [...], output_path: "gs://.../deck.pptx" })
```

### 6.2 编辑已有 deck

```
1. office_read_presentation({ source_path, format: "structured" })
2. 根据 slide_index / shape_index 构造 operations
3. office_edit_presentation({ source_path, output_path, operations })
```

**禁止**：用 `office_read_document` 的 `elements[].index` 编辑 presentation。

### 6.3 模板批量生成

```
office_apply_template_presentation({ template_path, data, output_path })
```

### 6.4 合并

```
office_merge_presentations({ source_paths: [a, b], output_path })
```

### 6.5 高级 / 兜底

```
office_execute_builder({ script: "... Api.GetPresentation() ..." })
```

勿对 pptx 使用 `office_edit_document`（Word `oDoc` API）。

---

## 7. 测试策略

### 7.1 单元测试

- `presentation/parser/slides.py`：fixture JSON → `slides[]` / `unit_count`
- 各 `presentation/tools/*`：mock `core/builder_runtime`、`resolve_document_source`
- `presentation/schemas/edit_ops.py`：越界 slide_index、缺字段

### 7.2 E2E

```bash
DOCUMENTSERVER_URL=... DOCUMENTSERVER_JWT_SECRET=... \
  poetry run pytest tests/office_mcp/presentation/ -v -m "presentation and e2e"
```

用例：create → read → edit → merge；odp 往返。

### 7.3 回归

- `legacy/read_document`：pptx→txt 不变
- `word/` 与 gateway E2E 全绿
- `registry` 工具列表含 5 个 presentation 工具

---

## 8. 实施计划（与架构迁移对齐）

**实现细节**（文件级 API、Pydantic schema、sidecar/Builder 模板、PR 分解、测试 checklist）见 **[OFFICE_MCP_PRESENTATION_IMPLEMENTATION_DESIGN.md](./OFFICE_MCP_PRESENTATION_IMPLEMENTATION_DESIGN.md)**。

| 阶段 | 架构 | Presentation 交付 | 验证 |
|------|------|-------------------|------|
| **M0** | `core/builder_runtime` + `builder_js` | — | 现有 pytest 全绿 |
| **M1** | `core/categories` + `storage` 迁入 | — | import 路径更新 |
| **M2–M3** | `word/` 迁移 + `registry.py` | — | adapter 瘦身 |
| **M4-P0** | presentation/ 目录 | `parser` + `office_read_presentation` + sidecar | 单元 + E2E read |
| **M4-P1** | | `create` + `edit`（core ops） | E2E 3 页 deck |
| **M4-P2** | | `merge` + `apply_template_presentation` | E2E merge + 模板 |
| **M4-P3** | | registry 注册 + LLM 指南 + README | 11 tools in health |
| **M4-P4** | | odp layout 枚举 E2E 表；chart/table op 按需 | E2E odp layout |

Presentation 工作 **依赖 M0–M1**（至少 `builder_runtime`、`categories`、`source`、`storage`）；可与 M2–M3 并行，但不应在 flat 旧结构上直接加文件。

### 8.1 实施状态（M7 · Gate G5）

| 阶段 | 状态 | 代码位置 |
|------|------|----------|
| M4 P0–P2 | ✅ | `presentation/` 五工具 |
| M4 P3 registry | ✅ | `registry.py` +13 canonical |
| M7 文档 | ✅ | 本表 + [LLM 指南](./OFFICE_MCP_PRESENTATION_LLM_GUIDE.md) |

---

## 9. 向后兼容

| 项目 | 策略 |
|------|------|
| `office_read_document` + pptx | legacy 保持 txt；description 指向 `office_read_presentation` |
| `office_merge_documents` | 仍仅 Word；presentation 用 `office_merge_presentations` |
| `office_apply_template` | 仍仅 Word；presentation 用 `office_apply_template_presentation` |
| 工具注册 | `registry.py`；health `tool_count` 随 registry 自动更新 |
| 旧 import 路径 | M1/M2 期间 `office_tool/conversion_output` 等可 re-export shim |

---

## 10. 风险与缓解

| 风险 | 缓解 |
|------|------|
| ONLYOFFICE JSON 体积大 | `slide_range`；outline；parser 裁剪字段 |
| shape_index 不稳定 | edit 前 read；`match_text` / `role` |
| ppt vs pptx | OpenFile 用真实 ext；输出推荐 pptx |
| odp layout 名差异 | fine read 返回 `layouts[]`；LLM 精确抄录；E2E 维护 odp 枚举表（**ADR-016**） |
| Builder 超时 | 大 deck 分批 read；`BUILDER_TIMEOUT` 已 600s |
| M0 未就绪就写 presentation | 实施顺序强制 M0→M1→M4 |

---

## 11. 参考

- [OFFICE_MCP_PRESENTATION_IMPLEMENTATION_DESIGN.md](./OFFICE_MCP_PRESENTATION_IMPLEMENTATION_DESIGN.md) — M4 P0–P4 可执行实现设计
- [implementation_design.md](./implementation_design.md) §7.2 — 全局 M4 任务
- [OFFICE_TOOL_ARCHITECTURE_REORG.md](./OFFICE_TOOL_ARCHITECTURE_REORG.md)
- [ONLYOFFICE Presentation API](https://api.onlyoffice.com/docs/office-api/usage-api/presentation-api/)
- [ApiPresentation.SlidesToJSON](https://api.onlyoffice.com/docs/office-api/usage-api/presentation-api/ApiPresentation/Methods/SlidesToJSON/)
- [CreateFile](https://api.onlyoffice.com/docs/document-builder/builder-framework/CDocBuilder/CreateFile/)
- 现有 Word 参考实现（迁移后路径）：`word/builder/merge.py`、`word/tools/edit_script.py`、`legacy/read_document.py`

---

## 附录 A：与 PPT-Tool 的边界

| | Office MCP（本升级） | PPT-Tool |
|--|---------------------|----------|
| 引擎 | ONLYOFFICE DocumentServer | python-pptx + AI 生图 |
| 场景 | 精确改字、企业模板、odp/pptx 互操作 | AI 视觉化 slide 生成 |
| 代码位置 | `office_tool/presentation/` | 独立仓库 |
| LLM 用法 | `office_*_presentation` 声明式工具 | project / content / export |

两者可并存：PPT-Tool 出初稿 → 上传 gs:// → `office_edit_presentation` 精修。

---

## 附录 B：工具名变更对照

| 旧草案名（若有） | 新架构规范名 |
|------------------|--------------|
| `office_apply_presentation_template` | **`office_apply_template_presentation`** |
| 根目录 `presentation_parser.py` | **`presentation/parser/slides.py`** |
| 根目录 `presentation_builder.py` | **`presentation/builder/*.py`** |
| 手工 adapter 注册 | **`registry.py` 自动汇总** |
