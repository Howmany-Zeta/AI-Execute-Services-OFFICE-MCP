# Office MCP PDF — Implementation Design

PDF 垂直模块的**可执行实现设计**：在 [OFFICE_MCP_PDF_UPGRADE.md](./OFFICE_MCP_PDF_UPGRADE.md)（What/规格）与 [implementation_design.md](./implementation_design.md)（全局 How）基础上，给出 **M6 P0–P5** 的文件级任务、API 签名、Pydantic schema、sidecar/Builder 脚本模板、测试与验收标准。

> **状态**：Implementation design（待开发）  
> **读者**：PDF 模块实现工程师、 Reviewers  
> **前置**：**M0**（`core/builder_runtime`）、**M1**（`core/categories`、`coarse_read`、`read_response`、`errors`）、**M3**（`registry.py`）必须合并  
> **架构约束**：[OFFICE_TOOL_ARCHITECTURE_REORG.md](./OFFICE_TOOL_ARCHITECTURE_REORG.md) §2、§7.4

---

## 1. 文档关系

| 文档 | 本设计如何使用 |
|------|----------------|
| [OFFICE_MCP_PDF_UPGRADE.md](./OFFICE_MCP_PDF_UPGRADE.md) | 工具参数、pages/blocks schema、operations、能力边界 — **规格源** |
| [implementation_design.md](./implementation_design.md) | Core API（§4）、registry（§5）、统一 read（§6）、M6 任务（§9）、PDF 创建分层（§8.4） — **全局约束** |
| [OFFICE_TOOL_ARCHITECTURE_REORG.md](./OFFICE_TOOL_ARCHITECTURE_REORG.md) | 目录树、依赖方向、legacy txt 粗读、无 apply_template_pdf |
| [ADR.md](./ADR.md) | PDF 相关已采纳决策（见 §2） |
| [OFFICE_MCP_PDF_LLM_GUIDE.md](./OFFICE_MCP_PDF_LLM_GUIDE.md) | 实现完成后同步 create_mode / fill_form 示例 |

**分工**：UPGRADE = 产品/LLM 规格；**本文档** = 工程师 checklist；`implementation_design.md` = 四类垂直 + core 总表。

**与 Word 差异**：PDF **无** `office_apply_template_*`；表单填写专用 **`office_fill_pdf_form`**（**ADR-030**）。

---

## 2. 已采纳 ADR（PDF 实现必须遵守）

| ADR | 决策 | 实现落点 |
|-----|------|----------|
| **ADR-002** | MCP 参数用 Pydantic v2 | `pdf/schemas/*` |
| **ADR-006** | 统一 `{isError}` / `{success}` | 全部 handler 经 `core/errors.py` |
| **ADR-008** | edit 单脚本、无 op 级 rollback | `builder/edit.py` 一次 `run_builder_on_source` |
| **ADR-009** | create/merge → `run_builder_script`；edit/fill → `run_builder_on_source` | 各 `tools/*.py` |
| **ADR-017** | `create_mode` 默认 `native`；**不** auto fallback → via_docx | `tools/create.py` 错误文案 |
| **ADR-018** | merge 默认 Builder；`options.engine=conversion` 显式 | `builder/merge.py` + Conversion 路径 |
| **ADR-019** | fill_form **逐字段 SetValue**；不用 SetFormsData | `builder/fill_form.py` |
| **ADR-020** | coarse 分页：`\f` → `--- page N ---` → 单页 + `_note` | `parser/pages_txt.py` |
| **ADR-021** | DS 探针；PDF native < 9.3 → skip native E2E | `probe_ds_capabilities.py` |
| **ADR-024** | 五工具 canonical；无 PDF legacy 别名 | registry |
| **ADR-025** | description 前缀 `[PDF]` | 五个 canonical PDF 工具 |
| **ADR-028** | `build_read_response` M1 blocking | `pdf/tools/read.py` |
| **ADR-029** | M3 后 core 严格 freeze | 新需求不得改 core 行为 |
| **ADR-030** | **无** `fill_form_field` op；表单仅 `office_fill_pdf_form` | `schemas/edit_ops.py` |

---

## 3. 交付范围与验收（P0–P5）

### 3.1 工具清单

| 工具 | 模块 | 阶段 | 验收 |
|------|------|------|------|
| `office_read_pdf` | `pdf/tools/read.py` | P0–P1 | coarse pages_txt + fine sidecar；`pages[]` ≡ `units[]` |
| `office_merge_pdfs` | `pdf/tools/merge.py` | P2 | Builder 默认 + conversion 显式 |
| `office_create_pdf` | `pdf/tools/create.py` | P3 | native + 显式 via_docx；**无** auto fallback |
| `office_edit_pdf` | `pdf/tools/edit.py` | P3 | 页/段落/注释 ops；**无** fill_form_field |
| `office_fill_pdf_form` | `pdf/tools/fill_form.py` | P4 | 逐字段 SetValue E2E |

**无** `office_apply_template_pdf`（架构 §7.4、**ADR-030**）。

**Legacy**：`office_read_document` 保留 pdf→txt（`parse_txt_to_structure`）；**行为冻结**，与 `office_read_pdf` coarse（`pages_txt`）可不同（**ADR-020** 仅约束后者）。

### 3.2 Release Gates

| Gate | 条件 |
|------|------|
| **P0** | `pdf/` 树 + `parser/pages_txt.py` + read coarse |
| **P1** | fine read sidecar + `parser/document.py`；E2E read |
| **P2** | `office_merge_pdfs` Builder + conversion E2E |
| **P3** | create + edit E2E（native 或 via_docx 视 DS） |
| **P4** | `office_fill_pdf_form` + registry 五工具 |
| **P5** | LLM 指南、README、DS 版本说明 |

---

## 4. 目录与迁移映射

### 4.1 目标树

```
aiecs/tools/office_tool/pdf/
├── __init__.py
├── parser/
│   ├── pages_txt.py              # NEW: Conversion txt → pages[]（ADR-020）
│   └── document.py               # NEW: sidecar JSON → pages[] / blocks[]
├── builder/
│   ├── create.py                 # native + via_docx
│   ├── edit.py
│   ├── merge.py                  # builder + conversion engine
│   └── fill_form.py
├── schemas/
│   ├── read.py
│   ├── page_spec.py
│   ├── edit_ops.py
│   └── fill_form.py              # FillFormArgs（可与 edit 共享 field 校验）
└── tools/
    ├── read.py
    ├── create.py
    ├── edit.py
    ├── merge.py
    └── fill_form.py
```

### 4.2 迁移说明（P0）

| 现路径 | 新路径 | 动作 |
|--------|--------|------|
| — | `pdf/parser/pages_txt.py` | **新建**；legacy 仍用 `html_parser.parse_txt_to_structure` |
| — | `pdf/parser/document.py` | **新建**；fine read only |

**P0 禁止**：修改 `office_read_document` 对 pdf 的 txt 解析行为。

### 4.3 依赖规则

```
pdf/tools/*  →  pdf/builder/*, schemas/*, parser/*, core/*
pdf/builder/*  →  core/builder_js, core/builder_runtime
pdf/parser/*  →  stdlib + re；无 DS 调用
pdf/*  ↛  word|presentation|spreadsheet
```

复杂版式 PDF 创建：**不**在 pdf 模块 import word；LLM 用 `office_create_word` + `office_call_api` convert（UPGRADE §1.4）。

---

## 5. Pydantic Schemas（ADR-002）

### 5.1 `schemas/read.py`

```python
class PdfReadOptions(BaseModel):
    read_mode: Literal["fine", "coarse"] = "fine"
    page_range: tuple[int, int] | None = None  # inclusive page_index
    include_form_fields: bool = True
    include_annotations: bool = False

class PdfReadArgs(BaseModel):
    source_path: str | None = None
    source_url: str | None = None
    format: Literal["structured", "outline", "text"] = "structured"
    options: PdfReadOptions = Field(default_factory=PdfReadOptions)
```

校验：`classify_file_ext(ext) == "pdf"` 为主路径；`djvu`/`xps`/`oxps` 仅 coarse（若 categories 允许）。

### 5.2 `schemas/page_spec.py`

```python
BlockType = Literal["paragraph", "table"]  # v2: image

class BlockSpec(BaseModel):
    type: BlockType
    text: str | None = None
    align: Literal["left", "center", "right"] | None = None
    bold: bool = False
    rows: list[list[str]] | None = None  # table

class PageSpec(BaseModel):
    blocks: list[BlockSpec] = Field(min_length=1)

class PdfCreateOptions(BaseModel):
    page_size: Literal["A4", "Letter"] | None = None
    create_mode: Literal["native", "via_docx"] = "native"  # ADR-017

class PdfCreateArgs(BaseModel):
    pages: list[PageSpec] = Field(min_length=1)
    output_path: str
    options: PdfCreateOptions = Field(default_factory=PdfCreateOptions)
```

### 5.3 `schemas/edit_ops.py`（**ADR-030**：无 fill_form_field）

```python
OpName = Literal[
    "add_paragraph", "set_page_text", "add_page", "delete_page",
    "rotate_page", "add_annotation",
]

class EditOperation(BaseModel):
    op: OpName
    page_index: int | None = Field(default=None, ge=0)
    after_index: int | None = Field(default=None, ge=-1)
    text: str | None = None
    align: Literal["left", "center", "right"] | None = None
    blocks: list[BlockSpec] | None = None
    degrees: Literal[90, 180, 270] | None = None
    kind: Literal["freetext", "highlight"] | None = None
    rect: dict[str, float] | None = None  # x, y, width, height
    # model_validator 按 op 强制字段

class PdfEditArgs(BaseModel):
    source_path: str | None = None
    source_url: str | None = None
    output_path: str
    operations: list[EditOperation] = Field(min_length=1)
    options: PdfEditOptions = Field(default_factory=PdfEditOptions)
```

### 5.4 `schemas/fill_form.py` / merge

```python
class PdfFillFormArgs(BaseModel):
    source_path: str | None = None
    source_url: str | None = None
    data: dict[str, Any]  # FieldName → value
    output_path: str

class PdfMergeOptions(BaseModel):
    engine: Literal["builder", "conversion"] = "builder"  # ADR-018

class PdfMergeArgs(BaseModel):
    source_paths: list[str] | None = None
    source_urls: list[str] | None = None
    output_path: str
    options: PdfMergeOptions = Field(default_factory=PdfMergeOptions)
```

---

## 6. Parser

### 6.1 `parser/pages_txt.py`（**ADR-020**）

```python
def parse_txt_to_pages(text: str) -> tuple[list[dict], str | None]:
    """
    Conversion txt → pages[] for office_read_pdf coarse.
    优先级:
      1. split on \\f (form feed)
      2. lines matching --- page N ---
      3. 整份作为单页 page_index=0；返回 note 说明未检测到页界

    每页: { page_index, blocks: [{ block_index, type: "paragraph", text }] }
    """

def pages_to_outline(pages: list[dict]) -> list[dict]:
    """每页首 block 文本或启发式标题"""

def pages_to_text(pages: list[dict]) -> str:
    """\\n--- page N ---\\n 分隔（与 presentation slides_to_text 风格一致）"""
```

**与 legacy 区别**：`office_read_document` 仍调用 `html_parser.parse_txt_to_structure`（扁平 `elements[]`）；**不得**在 P0–P5 替换 legacy 行为。

### 6.2 `parser/document.py`

```python
def parse_document_json(raw: dict | str) -> list[dict]:
    """
    sidecar { pages: [...] } → 规范化 pages[]。
    每项: page_index, blocks[], form_fields?[]
    blocks: block_index, type, text
    form_fields: name, type, value
    """

def apply_page_range(pages: list[dict], page_range: tuple[int, int] | None) -> list[dict]:
    """Inclusive filter"""
```

### 6.3 Sidecar extract_body

```javascript
builder.OpenFile("{url}", "pdf");
var doc = Api.GetDocument();
var out = { pages: [] };
for (var i = 0; i < doc.GetElementsCount(); i++) {
  var page = doc.GetElement(i);
  var blocks = [];
  // 遍历 page 上 paragraph/table → blocks[]
  // 若 include_form_fields: 枚举 widget → form_fields[]
  out.pages.push({ page_index: i, blocks: blocks, form_fields: [...] });
}
var jsonStr = JSON.stringify(out);
// core/builder_json_sidecar 写 structure.txt
builder.CloseFile();
```

**DS 探针**（**ADR-021**）：session fixture 检测 PDF native API；< 9.3 → skip native create/edit fine E2E；coarse 仍可用。

---

## 7. Builder 脚本生成

输出扩展名：`builder_file_ext(output_path)` → `"pdf"`（v1 创建/编辑/合并主输出均为 pdf）。

### 7.1 `builder/create.py`（**ADR-009** + **ADR-017**）

```python
def build_create_script(
    pages: list[PageSpec],
    *,
    output_ext: str,
    options: PdfCreateOptions,
) -> str:
    """
    create_mode=native:
      CreateFile("pdf") → Api.GetDocument() → 逐页 Push blocks → SaveFile("pdf", ...)
    create_mode=via_docx:
      CreateFile("docx") → Word API 填内容 → SaveFile("pdf", ...)
    失败由 runtime 返回 {isError}；handler 附加「可尝试 create_mode=via_docx」文案，不自动重试。
    """
```

| block type | native JS 要点 |
|------------|----------------|
| `paragraph` | `Api.CreateParagraph()` → `SetJc(align)` → `AddText` → `page.Push` |
| `table` | `Api.CreateTable` → Push |

`page_size`：设置页面尺寸 API（以实现时 DS 文档为准）。

### 7.2 `builder/edit.py`（**ADR-009**：edit body；**ADR-030** 无表单 op）

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
| `add_paragraph` | `doc.GetElement(page_index)` → CreateParagraph → Push |
| `set_page_text` | 清空页内容 → 重建 blocks（慎用） |
| `add_page` | InsertPage / AddPage after_index |
| `delete_page` | RemoveElement(page_index) |
| `rotate_page` | page Rotate(degrees) 若 API 存在 |
| `add_annotation` | AddAnnotation(kind, text, rect) v1 子集 |

定位：`page_index` + `block_index`（fine read 对齐）；`set_page_text` 替换整页。

### 7.3 `builder/merge.py`（**ADR-018**）

```python
def build_merge_script_builder(
    source_urls: list[str],
    *,
    output_ext: str,
) -> str:
    """
    默认 engine:
      OpenFile 第一个 → 依次 OpenFile 后续 → 复制/插入页 → SaveFile
    """

async def merge_pdfs_conversion(
    source_urls: list[str],
    output_path: str,
    client: DocumentServerClient,
) -> dict:
    """
    options.engine=conversion 显式路径:
      Conversion API 链式合并（实现以 DS 文档为准）
      可能丢表单/注释；返回 _note 或 tool description 说明
    """
```

Handler 逻辑：

```python
if args.options.engine == "conversion":
    return await merge_pdfs_conversion(...)
script = build_merge_script_builder(...)
return await run_builder_script(script, output_path=...)
```

**禁止** silent 从 builder 失败切 conversion。

### 7.4 `builder/fill_form.py`（**ADR-019** + **ADR-009**）

```python
def build_fill_form_script(
    data: dict[str, Any],
    *,
    file_ext: str,
) -> str:
    """
    OpenFile 后（body only）:
      for (name, value) in data:
        widget = doc.GetFormFieldByName(name) 或等价 API
        widget.SetValue(str(value))
    不用 SetFormsData 批量接口
    """
```

执行：`run_builder_on_source(template_pdf_url, "pdf", body, output_path)`。

---

## 8. Tool Handlers

每个 `pdf/tools/*.py` 导出：`TOOL_NAME`, `TOOL_DEF`, `handler`。

### 8.1 `tools/read.py` — `office_read_pdf`

```python
async def office_read_pdf(...) -> dict:
    # 1. PdfReadArgs validate
    # 2. resolve source；assert pdf category（或 djvu coarse only）
    # 3. read_mode=fine:
    #      read_sidecar_json(..., extract_body=PDF_PAGE_EXTRACT_BODY)
    #      pages = parse_document_json(raw)
    #      apply page_range / include_form_fields / include_annotations
    #      build_read_response(
    #        category="pdf", units=pages, read_mode="fine",
    #        extra={"page_count": len(pages)},
    #        locator_note="Use page_index and block_index with office_edit_pdf.",
    #      )
    # 4. read_mode=coarse:
    #      convert_and_fetch(txt) → parse_txt_to_pages
    #      build_read_response(read_mode="coarse", ...)
    # 5. structured 响应 mirror pages[] / units[]
    # 6. _note: rich reports → office_create_word + convert
```

**Description**：`[PDF] ...`（**ADR-025**）。

### 8.2 `tools/create.py` — `office_create_pdf`

```python
async def office_create_pdf(...) -> dict:
    args = PdfCreateArgs.model_validate(...)
    script = build_create_script(args.pages, output_ext="pdf", options=args.options)
    result = await run_builder_script(script, output_path=args.output_path, client=client)
    if result.get("isError") and args.options.create_mode == "native":
        # 追加 ADR-017 提示，不自动 via_docx 重试
        result["text"] += " Try create_mode=via_docx explicitly."
    return result
```

成功响应可选 `_note` 指向 word→convert 路径（复杂版式）。

### 8.3 `tools/edit.py` — `office_edit_pdf`

```python
async def office_edit_pdf(...) -> dict:
    args = PdfEditArgs.model_validate(...)
    body = build_edit_script(args.operations, file_ext="pdf")
    return await run_builder_on_source(
        fetch_url, "pdf", body, args.output_path,
        backup_source_path=...,
        client=client,
    )
```

### 8.4 `tools/merge.py` / `tools/fill_form.py`

- **merge**：见 §7.3 双 engine
- **fill_form**：`build_fill_form_script` → `run_builder_on_source`

---

## 9. Registry（P4）

在 `registry.py` 的 `OFFICE_TOOL_MODULES` 追加：

```python
"aiecs.tools.office_tool.pdf.tools.read",
"aiecs.tools.office_tool.pdf.tools.create",
"aiecs.tools.office_tool.pdf.tools.edit",
"aiecs.tools.office_tool.pdf.tools.merge",
"aiecs.tools.office_tool.pdf.tools.fill_form",
```

- `collect_office_tools()`：五工具 canonical（序号 19–23）；**M6 后共 23 canonical**（**ADR-024** 终态）
- `get_handlers()`：**M6 后 27**（23 canonical + 4 legacy）
- 无 PDF legacy handler；**无** apply_template 条目

---

## 10. 测试计划

### 10.1 目录

```
tests/office_mcp/pdf/
├── test_pages_txt_parser.py        # ADR-020: \\f, --- page N ---, 单页
├── test_document_parser.py         # sidecar JSON fixtures
├── test_read_pdf.py
├── test_create_pdf.py
├── test_edit_pdf.py
├── test_merge_pdfs.py
├── test_fill_pdf_form.py
├── test_schemas.py                 # 无 fill_form_field op
├── fixtures/
│   ├── acroform_template.pdf       # fill_form E2E
│   └── two_page_sample.pdf
└── test_e2e_pdf_tools.py           # @pytest.mark.pdf @pytest.mark.e2e
```

### 10.2 单元测试要点

| 文件 | 用例 |
|------|------|
| `test_pages_txt_parser.py` | `\f` 分页；`--- page 2 ---`；无页界 → 单页 + note |
| `test_schemas.py` | `fill_form_field` 不在 edit_ops；create_mode 枚举 |
| `test_create_pdf.py` | native 失败 mock → 无第二次 via_docx 调用 |
| `test_merge_pdfs.py` | 默认 builder script；`engine=conversion` 走 conversion 函数 |
| `test_fill_pdf_form.py` | mock SetValue 循环；字段名与 read form_fields 一致 |

### 10.3 E2E 清单

1. **create_pdf** 2 页 → **read_pdf** → `page_count == 2`  
2. **edit_pdf** `add_paragraph` → re-read 验证  
3. **merge_pdfs** 两个 1-page pdf → 2 pages（builder 默认）  
4. **merge_pdfs** `options.engine=conversion` 显式路径  
5. **fill_pdf_form** AcroForm fixture  
6. **create_mode=native** 与显式 **via_docx** 各测（**不**测 auto fallback；DS < 9.3 skip native）  
7. **legacy**：`office_read_document` pdf→txt 不变  

```bash
DOCUMENTSERVER_URL=... DOCUMENTSERVER_JWT_SECRET=... \
  poetry run pytest tests/office_mcp/pdf/ -v -m "pdf and e2e"
```

---

## 11. PR 分解建议

| PR | 内容 | Verify |
|----|------|--------|
| **PR-P0** | `pdf/` 树 + `pages_txt.py` + read coarse | unit pages_txt |
| **PR-P1** | sidecar + `document.py` + read fine | E2E read |
| **PR-P2** | `builder/merge.py` + merge tool（双 engine） | E2E merge |
| **PR-P3a** | `page_spec` + create（native/via_docx） | E2E create |
| **PR-P3b** | `edit_ops` + edit（无 fill_form_field） | E2E edit |
| **PR-P4** | fill_form + registry | E2E form + `test_registry` **M6: 23/27** |
| **PR-P5** | LLM 指南 + README | 文档 |

P3a/P3b 可合并。

---

## 12. 实现检查清单（Copy for PR description）

### P0

- [ ] `pdf/parser/pages_txt.py`（**ADR-020**）
- [ ] `office_read_pdf` coarse
- [ ] legacy pdf txt **未改**

### P1

- [ ] sidecar extract + `parse_document_json`
- [ ] `build_read_response` pages/units mirror + `page_count`
- [ ] E2E read fine

### P2

- [ ] merge Builder 默认（**ADR-018**）
- [ ] `options.engine=conversion` 显式路径 + 限制说明
- [ ] E2E merge

### P3

- [ ] `office_create_pdf` native + via_docx；**无** auto fallback（**ADR-017**）
- [ ] `office_edit_pdf`；**无** `fill_form_field`（**ADR-030**）
- [ ] E2E create + edit

### P4

- [ ] `office_fill_pdf_form` 逐字段 SetValue（**ADR-019**）
- [ ] registry 五模块 + `[PDF]` 前缀
- [ ] `test_registry` **M6 终态** canonical **23** / handlers **27**

### P5

- [ ] `OFFICE_MCP_PDF_LLM_GUIDE.md` 同步
- [ ] DS 版本 / 探针文档

---

## 13. 能力边界速查（实现时勿扩 scope）

| 用户意图 | 正确工具 |
|----------|----------|
| 填 AcroForm（任意字段数） | `office_fill_pdf_form` |
| 合并多个 PDF | `office_merge_pdfs` |
| 页内加段落 / 注释 | `office_edit_pdf` |
| 简单多页 PDF | `office_create_pdf` |
| 长报告 / 复杂排版 | `office_create_word` → `office_call_api` convert |
| 演示稿 PDF | `office_create_presentation` → convert |
| 全文 `{{key}}` 模板 | **不支持**（用 fill_form 字段名或 word template） |

---

## 14. 风险与实现备注

| 项 | 备注 |
|----|------|
| DS PDF API 版本 | **ADR-021** 探针；native E2E skip |
| 扫描 PDF 无文本 | fine read 空 blocks + `_note` OCR 非范围 |
| merge Builder 不稳定 | conversion 显式备选；不 silent 切换 |
| create 空 PDF | `{isError}`；提示 via_docx（**ADR-017**） |
| coarse 页界不准 | `_note`；edit 必须 fine read |
| edit 与 fill 混淆 | schema + LLM 指南强调 **ADR-030** |

---

## 15. 参考

- 规格：[OFFICE_MCP_PDF_UPGRADE.md](./OFFICE_MCP_PDF_UPGRADE.md)
- 全局实现：[implementation_design.md](./implementation_design.md) §4、§6、§7.4、§8.4、§9 M6
- 架构：[OFFICE_TOOL_ARCHITECTURE_REORG.md](./OFFICE_TOOL_ARCHITECTURE_REORG.md) §7.4
- ADR：[ADR.md](./ADR.md) ADR-002、006、008–009、017–021、024–025、028–030
- 现码：`read_document.py`、`html_parser.parse_txt_to_structure`
- ONLYOFFICE：[PDF API](https://api.onlyoffice.com/docs/office-api/usage-api/pdf-api/)
