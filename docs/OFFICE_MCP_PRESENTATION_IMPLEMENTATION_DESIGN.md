# Office MCP Presentation — Implementation Design

Presentation 垂直模块的**可执行实现设计**：在 [OFFICE_MCP_PRESENTATION_UPGRADE.md](./OFFICE_MCP_PRESENTATION_UPGRADE.md)（What/规格）与 [implementation_design.md](./implementation_design.md)（全局 How）基础上，给出 **M4 P0–P4** 的文件级任务、API 签名、Pydantic schema、sidecar/Builder 脚本模板、测试与验收标准。

> **状态**：As-built 设计（M4 架构 ✅；**ADR-041～047** 已裁定；E2E / 代码 gap 见 tasks **PT-037+**）  
> **读者**：Presentation 模块实现工程师、Reviewers  
> **前置**：**M0**（`core/builder_runtime`）、**M1**（`core/categories`、`coarse_read`、`read_response`、`errors`）、**M3**（`registry.py`）必须合并  
> **架构约束**：[OFFICE_TOOL_ARCHITECTURE_REORG.md](./OFFICE_TOOL_ARCHITECTURE_REORG.md) §2、§7.2

---

## 1. 文档关系

| 文档 | 本设计如何使用 |
|------|----------------|
| [OFFICE_MCP_PRESENTATION_UPGRADE.md](./OFFICE_MCP_PRESENTATION_UPGRADE.md) | 工具参数、slides schema、operations、LLM 工作流 — **规格源** |
| [implementation_design.md](./implementation_design.md) | Core API（§4）、registry（§5）、统一 read（§6）、M4 任务（§9） — **全局约束** |
| [OFFICE_TOOL_ARCHITECTURE_REORG.md](./OFFICE_TOOL_ARCHITECTURE_REORG.md) | 目录树、依赖方向、legacy txt 粗读 |
| [ADR.md](./ADR.md) | Presentation 相关已采纳决策（见 §2） |
| [OFFICE_MCP_PRESENTATION_LLM_GUIDE.md](./OFFICE_MCP_PRESENTATION_LLM_GUIDE.md) | 实现完成后同步 layout / slide_index 示例 |
| [OFFICE_MCP_PRESENTATION_IMPLEMENTATION_TASKS_BY_FILE.md](./OFFICE_MCP_PRESENTATION_IMPLEMENTATION_TASKS_BY_FILE.md) | **按文件执行清单**（PT-001–052、PT-DOC-*） |
| [AI_PROMPT_OFFICE_MCP_PRESENTATION_IMPLEMENTATION.md](./AI_PROMPT_OFFICE_MCP_PRESENTATION_IMPLEMENTATION.md) | **Agent 执行序**（PT-037–053 收尾 Batch prompt） |

**分工**：UPGRADE = 产品/LLM 规格；**本文档** = 工程师 checklist；**tasks 文档** = 逐文件 `[ ]`/`[x]`；`implementation_design.md` = 四类垂直 + core 总表。

---

## 2. 已采纳 ADR（Presentation 实现必须遵守）

| ADR | 决策 | 实现落点 |
|-----|------|----------|
| **ADR-002** | MCP 参数用 Pydantic v2 | `presentation/schemas/*` |
| **ADR-006** | 统一 `{isError}` / `{success}` | 全部 handler 经 `core/errors.py` |
| **ADR-009** | create/merge/template → `run_builder_script`；edit → `run_builder_on_source` | 各 `tools/*.py` |
| **ADR-016** | layout **仅枚举**；read 返回 `layouts[]`；create/`add_slide` 精确匹配 | `parser/slides.py` + `slide_spec.py` + `edit_ops.py` |
| **ADR-024** | `list_tools` **M6 终态** 23 canonical；无 presentation legacy 别名 | 五工具仅 canonical；**M4 后 registry 13/17** |
| **ADR-025** | description 前缀 `[Presentation]` | 五个 canonical presentation 工具 |
| **ADR-028** | `build_read_response` M1 blocking | `presentation/tools/read.py`；`layouts[]` 经 `extra=` |
| **ADR-029** | M3 后 core 严格 freeze | 新需求不得改 core 行为 |
| **ADR-041** | `add_slide` 可选 `title` / `subtitle` / `items` | `edit_ops.py` + `builder/edit.py`（**PT-046**） |
| **ADR-042** | merge 分隔页 `separator_layout` + caller `allowed_layouts` | `edit_ops` MergeOptions + `tools/merge.py`（**PT-049**） |
| **ADR-043** | edit `TOOL_DEF` ← `model_json_schema()` | `tools/edit.py`（**PT-045**） |
| **ADR-044** | fine 失败 → coarse fallback + `_note` | `tools/read.py` + `schemas/read.py`（**PT-047**） |
| **ADR-045** | sidecar `slide_range` → extract start/end | `parser/slides.py` + `tools/read.py`（**PT-048**） |
| **ADR-046** | v1 **无** create `template_path` | 文档；LLM read→create / apply_template |
| **ADR-047** | `layouts[]` = SlidesToJSON 去重 + 不完整 `_note` | `parser/slides.py` + `tools/read.py` |

**ADR-008**（edit 单脚本、无 op 级 rollback）：`builder/edit.py` 编译全部 operations 为一段 JS，一次 `run_builder_on_source`。

---

## 3. 交付范围与验收（P0–P4）

### 3.1 工具清单

| 工具 | 模块 | 阶段 | 验收 |
|------|------|------|------|
| `office_read_presentation` | `presentation/tools/read.py` | P0 | fine SlidesToJSON + coarse txt；`slides[]` ≡ `units[]`；`layouts[]` |
| `office_create_presentation` | `presentation/tools/create.py` | P1 | pptx/odp 创建；layout Pydantic 校验 |
| `office_edit_presentation` | `presentation/tools/edit.py` | P1 | core ops；`run_builder_on_source` |
| `office_merge_presentations` | `presentation/tools/merge.py` | P2 | 按 slide 合并 |
| `office_apply_template_presentation` | `presentation/tools/template.py` | P2 | `{{key}}` + `slide_{N}_` 前缀 |

**无 presentation legacy 别名**：`office_read_document` 保留 txt 粗读；**勿**用 `office_edit_document` 编辑 pptx。

### 3.2 Release Gates

| Gate | 条件 |
|------|------|
| **P0** | `presentation/` 树 + `parser/slides.py` + read fine/coarse；legacy pptx txt 回归 |
| **P1** | create + edit E2E（3 页 pptx deck）；create→read→edit→read |
| **P2** | merge + template E2E |
| **P3** | registry 五工具 + `[Presentation]` 前缀 + LLM 指南同步 |
| **P4** | odp layout 枚举 E2E 表（**ADR-016**）；与 pptx 分表 |

---

## 4. 目录与迁移映射

### 4.1 目标树

```
aiecs/tools/office_tool/presentation/
├── __init__.py
├── parser/
│   ├── slides.py                 # SlidesToJSON → slides[] / layouts[]
│   └── txt.py                    # ← html_parser.parse_txt_*（coarse）
├── builder/
│   ├── create.py
│   ├── edit.py
│   ├── merge.py
│   └── template.py
├── schemas/
│   ├── read.py
│   ├── slide_spec.py
│   └── edit_ops.py
└── tools/
    ├── read.py
    ├── create.py
    ├── edit.py
    ├── merge.py
    └── template.py
```

### 4.2 自现有代码迁移（P0）

| 现路径 | 新路径 | P0 动作 |
|--------|--------|---------|
| `html_parser.parse_txt_to_structure` | `presentation/parser/txt.py` | 移动；根 shim re-export |
| `html_parser.extract_outline_from_txt` | `presentation/parser/txt.py` | 同上 |
| — | `legacy/read_document.py` | presentation 分支 import `presentation/parser/txt.py`（或经 `core/coarse_read`） |

**P0 禁止**：改变 `office_read_document` 对 pptx/ppt/odp 的 txt 粗读行为。

### 4.3 依赖规则

```
presentation/tools/*  →  presentation/builder/*, schemas/*, parser/*, core/*
presentation/builder/*  →  core/builder_js, core/builder_runtime（禁止 Api.GetDocument Word API）
presentation/parser/*  →  stdlib + re；slides.py 无 DS 调用
presentation/*  ↛  word|spreadsheet|pdf
```

---

## 5. Pydantic Schemas（ADR-002 / ADR-016）

### 5.1 `schemas/read.py`

```python
class PresentationReadOptions(BaseModel):
    read_mode: Literal["fine", "coarse"] = "fine"
    slide_range: tuple[int, int] | None = None  # inclusive slide_index 起止
    include_notes: bool = False
    include_layout_meta: bool = False
    allow_coarse_fallback: bool = True  # ADR-044

class PresentationReadArgs(BaseModel):
    source_path: str | None = None
    source_url: str | None = None
    format: Literal["structured", "outline", "text"] = "structured"
    options: PresentationReadOptions = Field(default_factory=PresentationReadOptions)
```

校验：`classify_file_ext(ext) == "presentation"`。

### 5.2 `schemas/slide_spec.py`

```python
class ShapePosition(BaseModel):
    x: int  # EMU
    y: int

class ShapeSize(BaseModel):
    width: int
    height: int

class ShapeSpec(BaseModel):
    type: Literal["textbox", "image", "title", "body"]
    text: str | None = None
    url: str | None = None  # image
    position: ShapePosition | None = None
    size: ShapeSize | None = None

class SlideSpec(BaseModel):
    layout: str = Field(min_length=1)  # 运行时须 ∈ allowed_layouts（ADR-016）
    title: str | None = None
    subtitle: str | None = None
    bullets: list[str] | None = None
    shapes: list[ShapeSpec] | None = None
    notes: str | None = None

class PresentationCreateOptions(BaseModel):
    size: dict[str, int] | None = None  # {width, height} EMU；默认 16:9
    allowed_layouts: list[str] = Field(min_length=1)  # ADR-016；prior read layouts[]

class PresentationCreateArgs(BaseModel):
    slides: list[SlideSpec] = Field(min_length=1)
    output_path: str
    options: PresentationCreateOptions
```

**Layout 校验（ADR-016 / ADR-046）**：

```python
def validate_slides_layouts(
    slides: list[SlideSpec],
    allowed_layouts: list[str],
) -> str | None:
    """Reject layouts not in allowed_layouts. No fuzzy; no default fallback."""
```

**v1**：caller **必须**传 `options.allowed_layouts`（prior fine read 或 E2E fixture）。**不**实现 `options.template_path`（**ADR-046**）；有模板 deck 时用 `office_apply_template_presentation` 或 read→create。

### 5.3 `schemas/edit_ops.py`

```python
OpName = Literal[
    "set_text", "set_title", "set_bullets",
    "add_slide", "delete_slide", "duplicate_slide", "move_slide",
    "set_notes", "replace_image", "remove_shape",
]

class EditOperation(BaseModel):
    op: OpName
    slide_index: int | None = Field(default=None, ge=0)
    shape_index: int | None = Field(default=None, ge=0)
    match_text: str | None = None
    role: Literal["title", "body", "subtitle"] | None = None
    text: str | None = None
    items: list[str] | None = None  # set_bullets; add_slide 初始 bullets（ADR-041）
    title: str | None = None       # add_slide only（ADR-041）
    subtitle: str | None = None    # add_slide only（ADR-041）
    after_index: int | None = Field(default=None, ge=-1)
    from_index: int | None = None
    to_index: int | None = None
    layout: str | None = None  # add_slide：须 ∈ layouts[]
    url: str | None = None     # replace_image
    # model_validator 按 op 强制字段

class PresentationEditOptions(BaseModel):
    backup: bool = False
    allowed_layouts: list[str] | None = None  # required when add_slide（ADR-016）

class PresentationEditArgs(BaseModel):
    source_path: str | None = None
    source_url: str | None = None
    output_path: str
    operations: list[EditOperation] = Field(min_length=1)
    options: PresentationEditOptions = Field(default_factory=PresentationEditOptions)
```

**定位优先级**（builder 实现）：`shape_index` > `match_text` > `role`。

### 5.4 Merge / Template

```python
class PresentationMergeOptions(BaseModel):
    separator_slide: bool = False
    separator_layout: str | None = None   # required if separator_slide（ADR-042）
    allowed_layouts: list[str] | None = None  # required if separator_slide；separator_layout ∈ 此列表

class PresentationMergeArgs(BaseModel):
    source_paths: list[str] | None = None
    source_urls: list[str] | None = None
    output_path: str
    options: PresentationMergeOptions = Field(default_factory=PresentationMergeOptions)

class PresentationTemplateArgs(BaseModel):
    template_path: str | None = None
    template_url: str | None = None
    data: dict[str, Any]  # {{company_name}} 或 slide_1_title 等
    output_path: str
```

---

## 6. Parser

### 6.1 `parser/slides.py`

```python
def parse_slides_json(raw: dict | str) -> tuple[list[dict], list[str]]:
    """
    SlidesToJSON 解析 → (slides[], layouts[])。
    slides[] 每项: slide_index, title, layout, shapes[], notes?
    shapes[]: shape_index, type, role?, text, placeholder_type?
    layouts[]: 去重 master layout 名称列表（ADR-016 枚举源）
    """

def slides_to_outline(slides: list[dict]) -> list[dict]:
    """{slide_index, title} only"""

def slides_to_text(slides: list[dict]) -> str:
    """\\n--- slide N ---\\n 分隔"""

def apply_slide_range(slides: list[dict], slide_range: tuple[int, int] | None) -> list[dict]:
    """Inclusive filter by slide_index"""
```

**Shape `role` 启发式**（v1）：

- `placeholder_type == "title"` 或 layout 首 placeholder → `role: "title"`
- body placeholder / bullet 容器 → `role: "body"`
- 其余 → `type: "shape"`，无 role

### 6.2 `parser/txt.py`

```python
def parse_txt_to_structure(text: str) -> dict:
    """自 html_parser 迁入；legacy coarse read。"""

def extract_outline_from_txt(text: str) -> list[dict]:
    """Heuristic slide titles from txt conversion。"""
```

### 6.3 Sidecar extract_body

置于 `presentation/parser/slides.py` 或 `presentation/builder/read_sidecar.py`：

```javascript
builder.OpenFile("{url}", "{ext}");
var pres = Api.GetPresentation();
var last = pres.GetSlidesCount() - 1;
var start = {start_slide};  // 来自 options.slide_range 或 0
var end = {end_slide};      // 或 last
var jsonStr = JSON.stringify(pres.SlidesToJSON(start, end, false, false, false, false));
// core/builder_json_sidecar 写 structure.txt
builder.CloseFile();
```

**layouts 提取（ADR-047）**：

- **v1**：`parse_slides_json` — JSON 顶层 `layouts` / `layoutNames`（若有）+ 各 slide `layout` **去重**；**不**调用 `GetAllLayouts()`。
- fine read：若 `len(layouts) <= 1` 且 `slide_count > 0`，`extra._note` 警告列表可能不完整。
- **v2 候选**：`options.include_all_layouts` + GetAllLayouts（**ADR-047R**）。

---

## 7. Builder 脚本生成

扩展名：`builder_file_ext(output_path)` → `"pptx"` / `"odp"` / `"ppt"`。

**禁止**：`Api.GetDocument()`、`CreateFile("docx")`（Word merge/template 路径）。

### 7.1 `builder/create.py`（**ADR-009**：`run_builder_script`）

```python
def build_create_script(
    slides: list[SlideSpec],
    *,
    output_ext: str,
    options: PresentationCreateOptions,
) -> str:
    """
    1. CreateFile(output_ext)
    2. pres = Api.GetPresentation(); SetSizes(...)
    3. 每 SlideSpec: AddSlide(layout) → 填 title/subtitle/bullets/shapes
    4. SaveFile(output_ext, "output.{ext}")
    """
```

**SlideSpec → JS 要点**：

| 字段 | ONLYOFFICE 思路 |
|------|-----------------|
| `layout` | `pres.AddSlide(layoutName)` 或等价 API |
| `title` / `subtitle` | 占位符 `GetPlaceholder("title")` → `SetText` |
| `bullets` | body placeholder → `AddText` / numbering |
| `shapes[]` image | `CreateImage(url)` + position/size |
| `notes` | `slide.GetNotesPage()` → SetText |

### 7.2 `builder/edit.py`（**ADR-009**：edit body only）

```python
def build_edit_script(
    operations: list[EditOperation],
    *,
    file_ext: str,
) -> str:
    """OpenFile 由 run_builder_on_source 注入"""
```

| op | Builder 策略 |
|----|--------------|
| `set_text` | `GetSlide(i).GetAllShapes()[j]` 或 Search shape text → SetText |
| `set_title` | title placeholder on slide |
| `set_bullets` | body placeholder → clear + add bullets |
| `add_slide` | `AddSlide(layout)` after_index |
| `delete_slide` | `RemoveSlide(index)` |
| `duplicate_slide` | `DuplicateSlide` / copy API |
| `move_slide` | reorder API |
| `set_notes` | notes page SetText |
| `replace_image` | shape SetImage / ReplaceImage(url) |
| `remove_shape` | Remove shape |

**Shape 定位**：

```python
def _emit_resolve_shape(slide_var: str, op: EditOperation) -> str:
    # shape_index → GetAllShapes()[shape_index]
    # match_text → loop shapes Search text
    # role → GetPlaceholder("title"|"body")
```

### 7.3 `builder/merge.py`（**ADR-009**：`run_builder_script`）

```python
def build_merge_script(
    source_urls: list[str],
    source_exts: list[str],
    *,
    output_ext: str,
    separator_slide: bool = False,
) -> str:
    """
    1. CreateFile(output_ext) → target pres
    2. 每源 OpenFile → SlidesToJSON / FromJSON 或逐 slide Copy
    3. 可选 separator_slide: 插入空白分隔页
    4. SaveFile
    """
```

### 7.4 `builder/template.py`（**ADR-009**：`run_builder_on_source`）

```python
def build_template_script(
    data: dict[str, Any],
    *,
    file_ext: str,
) -> str:
    """
    遍历所有 slide 所有 shape 文本：
    - 全局 {{company_name}} → SearchAndReplace 或逐 shape Replace
    - 按页 {{slide_1_title}}：1-based 页码前缀 slide_{N}_
    v1 不支持 {{slide:2:title}} 语法
    """
```

**勿**复用 `word/builder/template.py`（Document SearchAndReplace）。

---

## 8. Tool Handlers

每个 `presentation/tools/*.py` 导出：`TOOL_NAME`, `TOOL_DEF`, `handler`。

### 8.1 `tools/read.py` — `office_read_presentation`

```python
async def office_read_presentation(...) -> dict:
    # 1. PresentationReadArgs validate
    # 2. resolve source；assert presentation category
    # 3. read_mode=fine:
    #      read_sidecar_json(..., extract_body=SLIDES_TOJSON_BODY)
    #      slides, layouts = parse_slides_json(raw)
    #      apply slide_range / include_notes / include_layout_meta
    #      build_read_response(
    #        category="presentation", units=slides, read_mode="fine",
    #        extra={"layouts": layouts, "slide_count": len(slides)},
    #        locator_note="Use slide_index and shape_index with office_edit_presentation. layout values for create/add_slide must match layouts[] exactly (ADR-016).",
    #      )
    # 4. read_mode=coarse:
    #      convert_and_fetch(txt) → parse_txt_to_structure
    #      build_read_response(read_mode="coarse", _note 警告不可用于 edit 定位)
    # 5. fine 失败：allow_coarse_fallback（ADR-044）→ coarse + _note；否则 err
    # 6. ADR-047：len(layouts)<=1 且 slide_count>0 → extra._note 不完整警告
    # 7. format=outline / text
```

**Mirror**：`slides[]` 与 `units[]` 相同；`slide_count == unit_count`（**ADR-028** `extra`）。

**Description**：`[Presentation] ...`（**ADR-025**）。

### 8.2 `tools/create.py` — `office_create_presentation`

```python
async def office_create_presentation(...) -> dict:
    args = PresentationCreateArgs.model_validate(...)
    validate_slides_layouts(args.slides, args.options.allowed_layouts)  # ADR-016
    script = build_create_script(...)
    return await run_builder_script(script, output_path=args.output_path, client=client)
```

### 8.3 `tools/edit.py` — `office_edit_presentation`

```python
async def office_edit_presentation(...) -> dict:
    args = PresentationEditArgs.model_validate(...)
    validate_add_slide_layouts(args.operations, args.options.allowed_layouts)  # ADR-016
    body = build_edit_script(args.operations, file_ext=ext)
    return await run_builder_on_source(
        fetch_url, file_ext, body, args.output_path,
        backup_source_path=...,
        client=client,
    )
```

### 8.4 `tools/merge.py` / `tools/template.py`

- **merge**：`validate_merge_separator_layout`（**ADR-042**）→ `build_merge_script` → `run_builder_script`（**ADR-009**）
- **template**：`build_template_script` → `run_builder_on_source`

---

## 9. Registry（P3）

在 `registry.py` 的 `OFFICE_TOOL_MODULES` 追加：

```python
"aiecs.tools.office_tool.presentation.tools.read",
"aiecs.tools.office_tool.presentation.tools.create",
"aiecs.tools.office_tool.presentation.tools.edit",
"aiecs.tools.office_tool.presentation.tools.merge",
"aiecs.tools.office_tool.presentation.tools.template",
```

- `collect_office_tools()`：五工具 canonical（序号 9–13，见 implementation_design §12）；**M4 后共 13 canonical**
- `get_handlers()`：**M4 后 17**（13 canonical + 4 legacy）
- 无 presentation legacy handler

---

## 10. 测试计划

### 10.1 目录

```
tests/office_mcp/presentation/
├── test_slides_parser.py
├── test_txt_parser.py
├── test_read_presentation.py
├── test_create_presentation.py
├── test_edit_presentation.py
├── test_merge_presentations.py
├── test_apply_template_presentation.py
├── test_presentation_builder.py   # build_edit_script 断言（PT-050）
├── test_schemas.py                 # layout 枚举；非法 slide_index
├── fixtures/
│   ├── slides_tojson_pptx.json
│   ├── layouts_pptx.json           # ADR-016 pptx 枚举表
│   └── layouts_odp.json            # ADR-016 odp 枚举表（P4）
└── test_e2e_presentation_tools.py  # @pytest.mark.presentation @pytest.mark.e2e
```

### 10.2 单元测试要点

| 文件 | 用例 |
|------|------|
| `test_slides_parser.py` | 多 slide；shapes role；layouts 去重；slide_range |
| `test_schemas.py` | layout 不在 allowed → reject；add_slide 缺 layout |
| `test_edit_presentation.py` | mock `run_builder_on_source`；断言 `Api.GetPresentation` |
| `test_apply_template_presentation.py` | `{{company_name}}`；`slide_1_title` |

### 10.3 E2E 清单

1. **create pptx** 3 slides → **read fine** → `slide_count` / `layouts[]`  
2. **edit**：`set_title` + `set_bullets` + `add_slide`（layout ∈ layouts）→ re-read  
3. **merge** 两个 pptx → slide 数增加  
4. **template**：`{{company_name}}` 替换  
5. **odp 往返**：create odp → edit → save odp（**P4** layout 用 `layouts_odp.json`）  
6. **legacy**：`office_read_document` pptx → txt `elements[]` 不变  
7. **禁止路径**：不对 pptx 调用 `office_edit_document`（文档/集成测试说明）

```bash
DOCUMENTSERVER_URL=... DOCUMENTSERVER_JWT_SECRET=... \
  poetry run pytest tests/office_mcp/presentation/ -v -m "presentation and e2e"
```

---

## 11. PR 分解建议

| PR | 内容 | Verify |
|----|------|--------|
| **PR-P0** | `presentation/` 树；`parser/txt.py` + `parser/slides.py`；read coarse + fine sidecar | unit + legacy txt 绿 |
| **PR-P1a** | `slide_spec` + `builder/create` + `office_create_presentation` | E2E create pptx |
| **PR-P1b** | `edit_ops` + `builder/edit` + `office_edit_presentation` | E2E edit 闭环 |
| **PR-P2** | merge + template | E2E merge + template |
| **PR-P3** | registry 五模块 + `[Presentation]` + LLM 指南 | `test_registry` **M4: 13/17** |
| **PR-P4** | odp layout fixture + odp E2E | ADR-016 odp 表 |

P1a/P1b 可合并；P3 可与 P2 同 PR。

---

## 12. 实现检查清单（Copy for PR description）

### P0

- [x] `presentation/parser/txt.py` 自 `html_parser` 迁入
- [x] sidecar SlidesToJSON extract + `parse_slides_json`
- [x] `office_read_presentation` fine/coarse/outline/text
- [x] `build_read_response` slides/units mirror + `layouts[]` extra
- [x] legacy pptx txt 行为不变

### P1

- [x] Pydantic slide_spec + edit_ops（`allowed_layouts` on create/edit）
- [x] `office_create_presentation` + `office_edit_presentation`
- [x] **ADR-009**：create→`run_builder_script`；edit→`run_builder_on_source`
- [ ] E2E create → read → edit → read（pptx）（**PT-037–038**）

### P2

- [x] `office_merge_presentations`
- [x] `office_apply_template_presentation`（Presentation API，非 Word）
- [ ] E2E merge + template（**PT-039–040**）

### P3

- [x] registry 五模块
- [ ] `test_registry` **M4: 13/17**（**PT-052** 可选）
- [x] description `[Presentation]` 前缀
- [x] `OFFICE_MCP_PRESENTATION_LLM_GUIDE.md` 同步 layout 规则（**PT-DOC-04**）

### P4

- [x] `fixtures/layouts_odp.json`（fixture）
- [ ] odp E2E（**PT-041**、**PT-051**）
- [ ] create/add_slide layout 精确匹配 E2E

### UPGRADE 收尾（ADR-041～045 代码）

- [ ] **PT-045** ADR-043 edit TOOL_DEF
- [ ] **PT-046** ADR-041 add_slide fields
- [ ] **PT-047** ADR-044 coarse fallback
- [ ] **PT-048** ADR-045 sidecar slide_range
- [ ] **PT-049** ADR-042 merge separator_layout
- [ ] **PT-053** ADR-047 layouts 不完整 `_note`

---

## 13. 风险与实现备注

| 项 | 备注 |
|----|------|
| SlidesToJSON 体积 | `slide_range`；outline；parser 字段裁剪 |
| shape_index 不稳定 | edit 前 fine read；`match_text` / `role` fallback |
| ppt vs pptx | OpenFile 用真实 ext；输出推荐 pptx/odp |
| odp layout 名 | **ADR-016** read 返回 `layouts[]`；E2E 分表 |
| M0 未就绪 | 强制 M0→M1→M3 后再 M4 |
| Word API 误用 | edit/merge/template 代码 review 禁止 `GetDocument` |

---

## 14. 与 UPGRADE / LLM 指南同步说明

维护时以 **`presentation/schemas/*` + `tools/*/TOOL_DEF` + builder 行为** 为真源；**ADR-041～047** 已裁定 v1 目标规格与 as-built 差异的收口方向。

### 14.1 目标规格（ADR-041～047）与代码状态

| 项 | ADR | 目标 | 代码（as-built） |
|----|-----|------|------------------|
| `add_slide` title/subtitle/items | **041** | schema + builder | ⏳ **PT-046** |
| merge separator_layout | **042** | + `allowed_layouts` caller 校验 | ⏳ **PT-049**（现硬编码 `"Blank"`） |
| edit TOOL_DEF | **043** | `model_json_schema()` | ⏳ **PT-045** |
| fine→coarse fallback | **044** | `allow_coarse_fallback` 默认 true | ⏳ **PT-047** |
| sidecar slide_range | **045** | extract 参数化 start/end | ⏳ **PT-048** |
| create template_path | **046** | **v1 不实现** | ✅ 文档已同步 |
| layouts[] 去重 + `_note` | **047** | parse 去重；不完整 warning | ✅ parse；⏳ `_note` **PT-053** |

### 14.2 其它 as-built 索引

| 项 | 说明 |
|----|------|
| create `allowed_layouts` | **required**（**ADR-016**） |
| edit `add_slide` | 须 `options.allowed_layouts` |
| merge 分隔页 | 须 `separator_layout` + `allowed_layouts`（**ADR-042**） |
| M6 registry | presentation×5 ∈ **23/27** |
| E2E | **PT-037–044** 待替换 placeholder |
| ADR-047 `_note` | **PT-053** 待 read handler 实现 |

**LLM 指南** §2.4–§3.5 与 §14.1 一致；UPGRADE §4 / §8.1 已按 ADR 回写。

---

## 15. 参考

- 规格：[OFFICE_MCP_PRESENTATION_UPGRADE.md](./OFFICE_MCP_PRESENTATION_UPGRADE.md)
- 全局实现：[implementation_design.md](./implementation_design.md) §4、§6、§7.2、§9 M4
- 架构：[OFFICE_TOOL_ARCHITECTURE_REORG.md](./OFFICE_TOOL_ARCHITECTURE_REORG.md) §7.2
- ADR：[ADR.md](./ADR.md) ADR-002、006、008、009、016、024–025、028–029、**041–047**
- 任务：[OFFICE_MCP_PRESENTATION_IMPLEMENTATION_TASKS_BY_FILE.md](./OFFICE_MCP_PRESENTATION_IMPLEMENTATION_TASKS_BY_FILE.md)
- 现码：`html_parser.parse_txt_to_structure`、`read_document.py`
- ONLYOFFICE：[Presentation API](https://api.onlyoffice.com/docs/office-api/usage-api/presentation-api/)、[SlidesToJSON](https://api.onlyoffice.com/docs/office-api/usage-api/presentation-api/ApiPresentation/Methods/SlidesToJSON/)
