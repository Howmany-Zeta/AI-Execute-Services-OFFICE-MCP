# Office MCP Word — Implementation Design

Word 垂直模块的**可执行实现设计**：在 [OFFICE_MCP_WORD_UPGRADE.md](./OFFICE_MCP_WORD_UPGRADE.md)（What/规格）与 [implementation_design.md](./implementation_design.md)（全局 How）基础上，给出 **M2 W0–W3 + M3 注册** 的文件级任务、API 签名、Pydantic schema、Builder 脚本模板、测试与验收标准。

> **状态**：Implementation design（待开发）  
> **读者**：Word 模块实现工程师、Reviewers  
> **前置**：**M0**（`core/builder_runtime`）、**M1**（`core/categories`、`coarse_read`、`read_response`、`errors`）必须合并  
> **架构约束**：[OFFICE_TOOL_ARCHITECTURE_REORG.md](./OFFICE_TOOL_ARCHITECTURE_REORG.md) §2、§7.1

---

## 1. 文档关系

| 文档 | 本设计如何使用 |
|------|----------------|
| [OFFICE_MCP_WORD_UPGRADE.md](./OFFICE_MCP_WORD_UPGRADE.md) | 工具参数、block schema、operations 语义、LLM 工作流 — **规格源** |
| [implementation_design.md](./implementation_design.md) | Core API（§4）、registry（§5）、统一 read（§6）、M2 任务清单（§9） — **全局约束** |
| [OFFICE_TOOL_ARCHITECTURE_REORG.md](./OFFICE_TOOL_ARCHITECTURE_REORG.md) | 目录树、依赖方向、legacy 策略 |
| [ADR.md](./ADR.md) | Word 相关已采纳决策（见 §2） |
| [OFFICE_MCP_WORD_LLM_GUIDE.md](./OFFICE_MCP_WORD_LLM_GUIDE.md) | 实现完成后同步示例与 `_locator_note` 文案 |

**分工**：UPGRADE = 产品/LLM 规格；**本文档** = 工程师 checklist；`implementation_design.md` = 四类垂直 + core 总表。

---

## 2. 已采纳 ADR（Word 实现必须遵守）

| ADR | 决策 | 实现落点 |
|-----|------|----------|
| **ADR-002** | MCP 参数用 Pydantic v2 | `word/schemas/*`；`tools/*` 入口 `model_validate` |
| **ADR-006** | 统一 `{isError}` / `{success}` | 全部 handler 经 `core/errors.py` |
| **ADR-010** | `delete_block` v1 仅 Search→Remove；表格块拒绝 | `edit_ops.py` validator + `builder/edit.py` |
| **ADR-011** | v1 **无** `relative_index` | schema 与 LLM 指南不得出现该字段 |
| **ADR-012** | `options.add_toc` / `insert_toc` **仅文首** | `builder/create.py`、`builder/edit.py` |
| **ADR-023** | M3 **强制**搬迁 word tests | `tests/office_mcp/word/` |
| **ADR-024** | `list_tools` 终态 23；legacy 仅 `call_tool` | `registry.py` + `legacy/*`；**M3=8/12 递增** |
| **ADR-025** | description 前缀 `[Word]` | 六个 canonical word 工具 |
| **ADR-028** | `build_read_response` M1 blocking | `word/tools/read.py` 不得 inline 拼顶层 dict |

---

## 3. 交付范围与验收（W0–W3）

### 3.1 工具清单

| 工具 | 模块 | 阶段 | 验收 |
|------|------|------|------|
| `office_read_word` | `word/tools/read.py` | W1 | fine/coarse/outline/text；`blocks[]` ≡ `units[]` |
| `office_create_word` | `word/tools/create.py` | W2 | docx/odt 创建 + E2E read 验证 |
| `office_edit_word` | `word/tools/edit.py` | W2 | 10 种 op + schema 拒绝非法 op |
| `office_merge_word` | `word/tools/merge.py` | W3 | `SaveFile` 跟 `output_path` ext（含 `.odt`） |
| `office_apply_template_word` | `word/tools/template.py` | W3 | `{{key}}` 替换行为与 legacy 等价 |
| `office_edit_word_script` | `word/tools/edit_script.py` | W3 | `run_builder_on_source`；与 legacy 等价 |

**Legacy 别名**（`get_handlers` only，**ADR-024**）：

| Legacy | 转发 |
|--------|------|
| `office_edit_document` | `office_edit_word_script` |
| `office_merge_documents` | `office_merge_word` |
| `office_apply_template` | `office_apply_template_word` |

`office_read_document` 保留在 `legacy/read_document.py`（全类别粗读）；description 指向 `office_read_word`。

### 3.2 Release Gates（Word 子集）

| Gate | 条件 |
|------|------|
| **W0** | 目录迁移完成；`pytest tests/office_mcp/test_office_*.py` 全绿；**无行为变更** |
| **W1** | `parser/document.py` 单元测试 + `office_read_word` E2E（docx fine read） |
| **W2** | create → read → edit → read 闭环（docx + odt） |
| **W3** | merge odt 输出 + legacy 三别名 E2E + template |
| **M3** | 六工具进 registry；word tests 迁至 `tests/office_mcp/word/`（**ADR-023**）；**registry 计数 M3=8/12** |

---

## 4. 目录与迁移映射

### 4.1 目标树

```
aiecs/tools/office_tool/word/
├── __init__.py
├── parser/
│   ├── html.py              # ← html_parser.py
│   └── document.py          # NEW: ToJSON → blocks[]
├── builder/
│   ├── create.py
│   ├── edit.py
│   ├── merge.py             # ← merge_document._build_merge_script
│   └── template.py          # ← apply_template 脚本生成
├── schemas/
│   ├── read.py
│   ├── section_spec.py
│   └── edit_ops.py
└── tools/
    ├── read.py
    ├── create.py
    ├── edit.py
    ├── merge.py
    ├── template.py
    └── edit_script.py       # ← edit_document.py
```

### 4.2 自现有文件迁移（W0）

| 现路径 | 新路径 | W0 动作 |
|--------|--------|---------|
| `html_parser.py` | `word/parser/html.py` | 移动；根 shim re-export |
| `merge_document.py` | `word/tools/merge.py` + `word/builder/merge.py` | 拆：handler vs `_build_merge_script` |
| `apply_template.py` | `word/tools/template.py` + `word/builder/template.py` | 同上 |
| `edit_document.py` | `word/tools/edit_script.py` | 改用 `run_builder_on_source`（M0 已做） |
| — | `legacy/merge_documents.py` | 薄包装：`office_merge_documents` → `office_merge_word` |
| — | `legacy/apply_template.py` | → `office_apply_template_word` |
| — | `legacy/edit_document.py` | → `office_edit_word_script` |

**W0 禁止**：改 merge/template/edit_script **对外行为**（除 M0 已统一的 runtime 错误格式）。

### 4.3 依赖规则

```
word/tools/*  →  word/builder/*, word/schemas/*, word/parser/*, core/*
word/builder/*  →  core/builder_js, core/builder_runtime（不 import tools）
word/parser/*  →  仅 stdlib + bs4（html）；document.py 无 DS 调用
word/*  ↛  presentation|spreadsheet|pdf
```

---

## 5. Pydantic Schemas（ADR-002）

文件：`word/schemas/`。所有 `tools/*.py` 在 handler 入口：

```python
args = WordCreateArgs.model_validate(raw_arguments)
```

### 5.1 `schemas/read.py`

```python
class WordReadOptions(BaseModel):
    read_mode: Literal["fine", "coarse"] = "fine"
    include_tables: bool = True
    max_blocks: int | None = Field(default=None, ge=1)

class WordReadArgs(BaseModel):
    source_path: str | None = None
    source_url: str | None = None
    format: Literal["structured", "outline", "text"] = "structured"
    options: WordReadOptions = Field(default_factory=WordReadOptions)

    @model_validator(mode="after")
    def exactly_one_source(self) -> Self: ...
```

校验：`classify_file_ext(ext) == "word"`（经 `core/categories.assert_category_path`）。

### 5.2 `schemas/section_spec.py`

```python
SectionType = Literal[
    "heading1", "heading2", "heading3",
    "paragraph", "bullets", "table", "page_break",
]

class SectionSpec(BaseModel):
    type: SectionType
    text: str | None = None
    bold: bool = False
    items: list[str] | None = None
    level: int = Field(default=1, ge=1, le=9)
    rows: list[list[str]] | None = None
    header_row: bool = False

    @model_validator(mode="after")
    def type_fields(self) -> Self:
        # heading*/paragraph 需 text；bullets 需 items；table 需 rows；page_break 无额外字段
        ...

class WordCreateOptions(BaseModel):
    title: str | None = None
    page_size: Literal["A4", "Letter"] | None = None
    add_toc: bool = False  # ADR-012: 仅文首

class WordCreateArgs(BaseModel):
    sections: list[SectionSpec] = Field(min_length=1)
    output_path: str
    options: WordCreateOptions = Field(default_factory=WordCreateOptions)
```

### 5.3 `schemas/edit_ops.py`

```python
class LocatorBlockIndex(BaseModel):
    block_index: int = Field(ge=0)

class LocatorHeadingPath(BaseModel):
    heading_path: list[str] = Field(min_length=1)

class LocatorMatchText(BaseModel):
    match_text: str = Field(min_length=1)

class AfterLocator(BaseModel):
    """after: block_index | heading_path | 'start' | 'end'"""
    block_index: int | None = None
    heading_path: list[str] | None = None
    start: bool = False
    end: bool = False
    # 互斥校验

OpName = Literal[
    "search_replace", "set_block_text", "set_heading",
    "insert_paragraph", "insert_bullets", "insert_table",
    "delete_block", "apply_style", "add_page_break", "insert_toc",
]

class EditOperation(BaseModel):
    op: OpName
    # 各 op 字段 optional；model_validator 按 op 强制必填

class WordEditArgs(BaseModel):
    source_path: str | None = None
    source_url: str | None = None
    output_path: str
    operations: list[EditOperation] = Field(min_length=1)
    options: WordEditOptions = Field(default_factory=WordEditOptions)
```

**ADR-010 — `delete_block`**：

```python
@model_validator(mode="after")
def delete_block_rules(self) -> Self:
    if self.op != "delete_block":
        return self
    # 若 read 侧 type==table 且用 block_index → ValidationError
    # v1 schema 层：delete_block 不得与 type=table 的 block_index 同 op（文档说明；runtime 二次检查）
    ...
```

**ADR-011**：schema 与 `model_json_schema()` 导出均**不得**含 `relative_index`。

### 5.4 Merge / Template / EditScript

- `WordMergeArgs`：同 legacy `office_merge_documents` 字段；Pydantic 校验 source_paths XOR source_urls。
- `WordTemplateArgs`：同 legacy `office_apply_template`。
- `WordEditScriptArgs`：同 legacy `office_edit_document`（`edit_script`, `output_path`, backup）。

---

## 6. Parser：`word/parser/document.py`

### 6.1 公共 API

```python
def parse_document_json(raw: dict | str) -> list[dict]:
    """
    ONLYOFFICE doc.ToJSON(...) 解析为 blocks[]。
    返回每项含: block_index, type, text, style_name?, heading_path?, rows?, row_count?, col_count?
    """

def blocks_to_outline(blocks: list[dict]) -> list[dict]:
    """仅 heading* → {block_index, type, text, heading_path}"""

def blocks_to_text(blocks: list[dict]) -> str:
    """段落/标题文本拼接，表格用 tab 分隔"""

def word_count_from_blocks(blocks: list[dict]) -> int:
    """累加 paragraph/heading 词数；表格单元格计入"""
```

### 6.2 解析算法（v1）

1. 若 `raw` 为 `str`：`json.loads`。
2. 自 ToJSON 根取 **document body 元素列表**（ONLYOFFICE 结构以 fixture 为准；实现时锁定一版 DS 样本 JSON）。
3. 顺序遍历元素，`block_index` 从 0 递增：
   - **段落/标题**：由 `style` / `outlineLvl` / 文本模式映射 `type` → `heading1`–`heading3` 或 `paragraph`；维护 `heading_path` 栈。
   - **表格**：`type=table`；`rows[][]` 来自 cell 文本；`row_count` / `col_count`。
   - **分页符**：可选 `type=page_break`（若 ToJSON 可识别）。
4. 应用 `max_blocks`：截断并可在 read 响应加 `_truncated: true`（extra 字段）。

### 6.3 Sidecar extract_body（Word 专用）

置于 `word/parser/document.py` 或 `word/builder/read_sidecar.py`：

```javascript
// extract_body 片段（注入 build_sidecar_extract_script）
var doc = Api.GetDocument();
var jsonStr = JSON.stringify(doc.ToJSON(true, true, true, true, true, true));
```

### 6.4 `word/parser/html.py`

自 `html_parser.py` 迁入，**不改** `parse_html_to_structure` 签名；供 `read_mode=coarse` 与 `legacy/read_document` 复用。

---

## 7. Builder 脚本生成

共用 `core/builder_js.escape_js`、`open_file`、`save_file`、`close_file`；输出扩展名用 `core/categories.builder_file_ext(output_path)`。

### 7.1 `builder/create.py`

```python
def build_create_script(
    sections: list[SectionSpec],
    *,
    output_ext: str,
    options: WordCreateOptions,
) -> str:
    """
    1. builder.CreateFile(output_ext)
    2. 若 options.add_toc: doc.AddTableOfContents({})  # ADR-012 文首，在任何 Push 之前
    3. 遍历 sections → _emit_section(spec)
    4. SaveFile(output_ext, "output.{ext}")
    5. CloseFile
    """
```

**Section → JS 映射**：

| type | JS 要点 |
|------|---------|
| `heading1`–`3` | `Api.CreateParagraph()` → `AddText` → `SetStyle("Heading N")` → `doc.Push` |
| `paragraph` | Push；可选 `SetBold` |
| `bullets` | `CreateNumbering` / `SetNumbering` 或 `AddText` + bullet char（与 DS 样本对齐） |
| `table` | `Api.CreateTable(cols, rows)` → 填 cell → Push |
| `page_break` | `Api.CreateParagraph()` → `AddPageBreak()` → Push |

### 7.2 `builder/edit.py`

```python
def build_edit_script(
    operations: list[EditOperation],
    *,
    file_ext: str,
) -> str:
    """
    仅 edit body（不含 Open/Save）；供 run_builder_on_source 注入。
    按 operations 顺序生成 JS；单 op 失败时整脚本失败（DS 层）。
    """
```

| op | v1 JS 策略 |
|----|------------|
| `search_replace` | `doc.SearchAndReplace({searchString, replaceString})`；`scope=heading_path` 时先 Search 限定范围（v1 可 document 级） |
| `set_block_text` | `_locate_paragraph(locator)` → `SetText` / Replace |
| `set_heading` | Search 标题 → `SetText` + `SetStyle("Heading N")` |
| `insert_paragraph` | `CreateParagraph` + `AddText` → `_insert_after(after)` |
| `insert_bullets` | 同 create bullets |
| `insert_table` | `CreateTable` + Push after |
| `delete_block` | **ADR-010**：`Search(unique_snippet)` → `Remove()`；无唯一匹配 → 脚本内抛错或前置 Python 校验 |
| `apply_style` | Search block text → `SetStyle(style_name)` |
| `add_page_break` | `AddPageBreak` after locator |
| `insert_toc` | `doc.AddTableOfContents({})` at **文首**（ADR-012） |

**`_locate_paragraph`（v1）**：

```python
def _search_snippet_from_locator(op, blocks_cache: dict | None) -> str:
    """
    block_index → 从最近一次 read 缓存的 text 首 80 字符（工具层不传 cache 时用 match_text/heading_path）
    heading_path → path[-1]
    match_text → 原样
    """
```

实现说明：`office_edit_word` **不**保证 `GetElement(block_index)`；与 UPGRADE §4.3 一致，用 Search。

### 7.3 `builder/merge.py`

自 `merge_document._build_merge_script` 迁入；**W3 修复**：

```python
output_ext = builder_file_ext(output_path)  # 非写死 "docx"
# ...
lines.append(f'builder.SaveFile("{output_ext}", "output.{output_ext}");')
```

`options.add_toc`：与 create 相同，**文首**插入（merge 脚本末尾、Save 前若需要则按 legacy 行为：在 merge 循环后 `AddTableOfContents`）。

### 7.4 `builder/template.py`

自 `apply_template.py` 迁入：`SearchAndReplace("{{key}}", value)` 循环；`str()` 转换 data 值。

---

## 8. Tool Handlers

每个 `word/tools/*.py` 导出：`TOOL_NAME`, `TOOL_DEF`, `handler`（见 implementation_design §5.1）。

### 8.1 `tools/read.py` — `office_read_word`

```python
async def office_read_word(...) -> dict:
    # 1. WordReadArgs validate
    # 2. resolve_document_source → ext；assert word category
    # 3. branch:
    #    read_mode=fine + format in structured|outline|text:
    #      read_sidecar_json(..., extract_body=WORD_TOJSON_BODY)
    #      blocks = parse_document_json(raw)
    #      apply max_blocks / include_tables
    #      units = blocks; build_read_response(category="word", units=..., read_mode="fine", ...)
    #    read_mode=coarse OR format=text fallback:
    #      convert_and_fetch → parser/html → coarse units
    #      build_read_response(read_mode="coarse", ...)
    # 4. format=outline → 替换 units 为 blocks_to_outline(blocks)
    # 5. format=text → 返回 {text: ...} 或 read_response + text field
```

**`_locator_note`**（固定文案，与 UPGRADE 一致）：

> Edit with office_edit_word using block_index, heading_path, or match_text. Do not use office_read_document elements[].index.

**Description 前缀**：`[Word] ...`（**ADR-025**）。

### 8.2 `tools/create.py` — `office_create_word`

```python
async def office_create_word(...) -> dict:
    args = WordCreateArgs.model_validate(...)
    err = assert_category_path("word", args.output_path)
    if err: return err(...)
    script = build_create_script(args.sections, output_ext=builder_file_ext(...), options=args.options)
    return await run_builder_script(script, output_path=args.output_path, client=client)
```

### 8.3 `tools/edit.py` — `office_edit_word`

```python
async def office_edit_word(...) -> dict:
    args = WordEditArgs.model_validate(...)
    # delete_block + table: schema/runtime 拒绝 ADR-010
    body = build_edit_script(args.operations, file_ext=ext)
    backup = args.options.backup and source_path
    return await run_builder_on_source(
        fetch_url, file_ext, body, args.output_path,
        backup_source_path=source_path if backup else None,
        client=client,
    )
```

### 8.4 `tools/merge.py` / `template.py` / `edit_script.py`

- **merge**：逻辑同现 `office_merge_documents`；调用 `build_merge_script` + `run_builder_script`。
- **template**：同现 `office_apply_template`。
- **edit_script**：同现 `office_edit_document`；legacy 名注册 alias。

---

## 9. Registry（M3）

在 `registry.py` 的 `OFFICE_TOOL_MODULES` 追加：

```python
"aiecs.tools.office_tool.word.tools.read",
"aiecs.tools.office_tool.word.tools.create",
"aiecs.tools.office_tool.word.tools.edit",
"aiecs.tools.office_tool.word.tools.merge",
"aiecs.tools.office_tool.word.tools.template",
"aiecs.tools.office_tool.word.tools.edit_script",
"aiecs.tools.office_tool.legacy.merge_documents",
"aiecs.tools.office_tool.legacy.apply_template",
"aiecs.tools.office_tool.legacy.edit_document",
```

- `collect_office_tools()`：六 word canonical + gateway（**M3 时共 8**；presentation 等随 M4+ 递增，**M6 终态 23**）
- `get_handlers()`：**M3 时 12**（8 canonical + 4 legacy）；**M6 终态 27**

---

## 10. 测试计划

### 10.1 目录（M3 强制，ADR-023）

```
tests/office_mcp/word/
├── test_document_parser.py      # fixture ToJSON → blocks, heading_path
├── test_html_parser.py            # 自 test_office_read 迁入 html 部分
├── test_read_word.py
├── test_create_word.py
├── test_edit_word.py
├── test_merge_word.py
├── test_apply_template_word.py
├── test_edit_word_script.py
├── test_legacy_compat.py
├── test_schemas.py                # Pydantic 非法 op / ADR-010/011/012
└── test_e2e_word_tools.py         # @pytest.mark.word @pytest.mark.e2e
```

### 10.2 单元测试要点

| 文件 | 用例 |
|------|------|
| `test_document_parser.py` | 多级 heading_path；表格 rows；空文档；malformed JSON |
| `test_schemas.py` | `delete_block` on table；无 `relative_index`；`add_toc` bool；sections 缺字段 |
| `test_edit_word.py` | mock `run_builder_on_source`；断言 `build_edit_script` 含 Search |
| `test_merge_word.py` | `output_path=*.odt` → script 含 `SaveFile("odt", ...)` |

### 10.3 E2E 清单

1. **create docx** → **read_word structured** → `block_index` 连续、`heading_path` 正确  
2. **edit_word**：`set_heading` + `insert_bullets` + `search_replace` → re-read 验证  
3. **odt 往返**：create odt → edit → save odt  
4. **read legacy .doc**（fine 或 coarse）  
5. **merge_word** → `output_path` 以 `.odt` 结尾，下载 ext 正确  
6. **legacy**：`office_merge_documents` / `office_apply_template` / `office_edit_document` 与 W0 行为一致  
7. **delete_block**：段落成功；表格 block **拒绝**（schema 或 `{isError}`）

```bash
DOCUMENTSERVER_URL=... DOCUMENTSERVER_JWT_SECRET=... \
  poetry run pytest tests/office_mcp/word/ -v -m "word and e2e"
```

---

## 11. PR 分解建议

| PR | 内容 | Verify |
|----|------|--------|
| **PR-W0** | 建 `word/` 树；迁入 html/merge/template/edit_script；legacy 薄包装；shim | 全量 `test_office_*` 绿 |
| **PR-W1** | `parser/document.py` + `office_read_word` + sidecar | unit + E2E read |
| **PR-W2a** | `schemas/section_spec` + `builder/create` + `office_create_word` | E2E create docx/odt |
| **PR-W2b** | `schemas/edit_ops` + `builder/edit` + `office_edit_word` | E2E edit 闭环 |
| **PR-W3** | merge ext 修复 + template + edit_script + legacy 别名 | merge odt + legacy |
| **PR-M3** | registry + adapter 瘦身 + test 搬迁 + `[Word]` 前缀 | `test_registry` **M3: 8/12**（非 23/27） |

W2a/W2b 可合并为单 PR，若 review 带宽允许。

---

## 12. 实现检查清单（Copy for PR description）

### W0

- [ ] `word/parser/html.py` 自 `html_parser.py` 迁入，根 shim 保留
- [ ] `word/builder/merge.py` + `word/tools/merge.py` 拆分
- [ ] `word/builder/template.py` + `word/tools/template.py` 拆分
- [ ] `word/tools/edit_script.py` 自 `edit_document.py` 迁入
- [ ] `legacy/*` 三个别名模块
- [ ] 无新 MCP 工具暴露（仅搬迁）

### W1

- [ ] `parse_document_json` + fixtures
- [ ] `office_read_word` fine/coarse/outline/text
- [ ] `build_read_response` 填充 `blocks`/`units` mirror
- [ ] E2E：`read_word` docx fine

### W2

- [ ] Pydantic section_spec + edit_ops（ADR-002/010/011/012）
- [ ] `office_create_word` + `office_edit_word`
- [ ] E2E：create → read → edit → read（docx + odt）

### W3

- [ ] merge `SaveFile` 跟 output ext
- [ ] `office_apply_template_word` + `office_edit_word_script`
- [ ] Legacy 别名 E2E
- [ ] `delete_block` ADR-010 行为

### M3

- [ ] registry 注册 6 word canonical + 4 legacy handlers（**M3 总计 8/12**）
- [ ] `test_registry` 断言 **8** / **12**（见 implementation_design §5.2 表）

---

## 13. 风险与实现备注

| 项 | 备注 |
|----|------|
| ToJSON 结构版本差异 | 锁定 DS 版本 + fixture；parser 单测防回归 |
| `block_index` vs `GetElement(i)` | 一律 Search；read 响应 `_locator_note` 必显 |
| edit 后复用旧 index | LLM 指南要求 re-read；可选返回 `_note` |
| merge `add_toc` 位置 | 与 ADR-012 一致：文首语义；与 legacy 对齐测试 |
| 大文档 | `max_blocks` + outline 模式 |

---

## 14. 参考

- 规格：[OFFICE_MCP_WORD_UPGRADE.md](./OFFICE_MCP_WORD_UPGRADE.md)
- 全局实现：[implementation_design.md](./implementation_design.md) §4、§6、§7.1、§9 M2
- 架构：[OFFICE_TOOL_ARCHITECTURE_REORG.md](./OFFICE_TOOL_ARCHITECTURE_REORG.md)
- ADR：[ADR.md](./ADR.md) ADR-002、006、010–012、023–025、028
- 现码：`html_parser.py`、`merge_document.py`、`apply_template.py`、`edit_document.py`
