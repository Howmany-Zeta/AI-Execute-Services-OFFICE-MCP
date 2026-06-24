# Office MCP PDF — 按文件必选任务（P0–P4 + M6）

**用途：** 落地 [OFFICE_MCP_PDF_IMPLEMENTATION_DESIGN.md](./OFFICE_MCP_PDF_IMPLEMENTATION_DESIGN.md) 时，将 PDF 垂直模块从 legacy txt 粗读迁移为 **`pdf/{parser,builder,schemas,tools}/` + registry 注册** 的**逐文件**执行清单。

**对齐（设计真源，实现前必读）：**

| 文档 | 角色 |
|------|------|
| [OFFICE_MCP_PDF_UPGRADE.md](./OFFICE_MCP_PDF_UPGRADE.md) | What：工具参数、pages/blocks schema、operations、能力边界 |
| [OFFICE_MCP_PDF_IMPLEMENTATION_DESIGN.md](./OFFICE_MCP_PDF_IMPLEMENTATION_DESIGN.md) | How（PDF）：目录树、Core 集成、Builder、Gate |
| [implementation_design.md](./implementation_design.md) | How（全局）：Core §4、Registry §5、M6 §7.4 |
| [OFFICE_TOOL_IMPLEMENTATION_TASKS_BY_FILE.md](./OFFICE_TOOL_IMPLEMENTATION_TASKS_BY_FILE.md) | 全局 OT-113–126；**本表为其 PDF 子集展开** |
| [ADR.md](./ADR.md) | ADR-002、006、008–009、017–021、024–025、028–030 |
| [OFFICE_MCP_PDF_LLM_GUIDE.md](./OFFICE_MCP_PDF_LLM_GUIDE.md) | LLM 示例（`page_index` / `block_index` + `create_mode`） |

**Preconditions（全局 M0–M3，PDF 开工前）**

- [x] **M0**：`core/builder_runtime.py`、`core/builder_js.py`（全局 OT-013–022）
- [x] **M1**：`core/categories`、`errors`、`read_response`、`coarse_read`、`builder_json_sidecar`、`source`、`storage`（全局 OT-023–045）
- [x] **M3**：`registry.py` 骨架；Word + Presentation + Spreadsheet 已注册（**M6 前 canonical=18**）
- [x] `poetry run pytest tests/office_mcp/ -v -m "not e2e"` 全绿

**任务编号：** **PDF-001 … PDF-036**（架构交付）+ **PDF-037 … PDF-046**（UPGRADE 收尾）+ **PDF-DOC-***。

**路径约定：** Python 相对仓库根 `aiecs/`、`tests/`；文档相对 `docs/`。

**完成定义：** **`[ ]` → `[x]`** = 本 Task 在对应 PR 中落地并满足「必须完成」列。

> **代码状态（2026-06）**
>
> | 范围 | 状态 |
> |------|------|
> | **架构 M6**（PDF-001–036、PDF-DOC-01–03） | ✅ 已落地：模块、registry、69 unit 测试 |
> | **UPGRADE 收尾**（PDF-037–046） | ✅ **PDF-037–046** 全部完成 |
> | **文档 as-built** | ✅ **PDF-DOC-04**（UPGRADE §7.1 / DESIGN §14 / LLM §8） |
>
> 架构重组 **G4（PDF 注册）** 已满足；**UPGRADE §6 E2E** 与 as-built gap 见 **Group G–I**。

**遵循的方法（PDF 子集）：**

| 方法 | 来源 | 要求 |
|------|------|------|
| `run_builder_script` | ADR-009 | create / merge（builder engine） |
| `run_builder_on_source` | ADR-009 | edit / fill_form（有源） |
| `build_read_response` | ADR-028 | `office_read_pdf` structured/outline；`pages[]` ≡ `units[]` |
| `err` / `ok` | ADR-006 | 全部 handler |
| Pydantic v2 | ADR-002 | `pdf/schemas/*` |
| coarse 分页 | ADR-020 | `\f` → `--- page N ---` → 单页 + `_note` |
| create_mode | ADR-017 | 默认 `native`；**不** auto via_docx |
| merge engine | ADR-018 | 默认 builder；`conversion` 显式 |
| fill_form | ADR-019、030 | 逐字段 SetValue；**无** `fill_form_field` edit op |
| Registry M6 | ADR-024 | 五工具 canonical；**无** PDF legacy 别名 |
| `[PDF]` 前缀 | ADR-025 | 五 canonical description |
| 行为冻结 | PDF-NA-01 | `office_read_document` pdf→txt **不变** |

---

## 里程碑与 Gate

| 阶段 | Gate | 交付摘要 | 全局 |
|------|------|----------|------|
| **P0** | P0 | 目录 + pages_txt 粗读；legacy pdf txt 回归 | OT-113–114, 121(部分), 124 |
| **P1** | P1 | fine read sidecar + `parser/document.py` | OT-115, 121(部分), 124 |
| **P2** | P2 | merge builder + conversion 显式 | OT-119, 121(部分) |
| **P3** | P3 | create + edit（native/via_docx；无 fill_form_field） | OT-116–118, 121(部分) |
| **P4** | P4 | fill_form + registry 五工具 | OT-120–123 |
| **M6** | **G4** | registry **23/27**；`[PDF]`；fixtures | OT-122–126 |
| **P5** | P5 | LLM 指南、README、DS 探针 | OT-127、OT-011 |

**Registry（PDF 相关）：** M6 时 gateway×2 + word×6 + pres×5 + sheet×5 + pdf×5 → **`collect_office_tools()==23`**，`get_handlers()==27`（+4 legacy，无 PDF legacy）。

---

## Group A — P0：目录 + pages_txt 粗读

**Batch `T-PDF-P0` — Tasks PDF-001 – PDF-009** · **Gate：P0**

### [x] **Task PDF-001** — `aiecs/tools/office_tool/pdf/__init__.py`（OT-113）

| 字段 | 内容 |
|------|------|
| **必须完成** | 包初始化 |

### [x] **Task PDF-002** — `pdf/parser/__init__.py`

| 字段 | 内容 |
|------|------|
| **必须完成** | 导出 `pages_txt`、`document` public API |

### [x] **Task PDF-003** — `pdf/parser/pages_txt.py`（OT-114）

| 字段 | 内容 |
|------|------|
| **必须完成** | `parse_txt_to_pages`：`\f` → `--- page N ---` → 单页 + `_note` |
| **必须完成** | `pages_to_outline`、`pages_to_text` |
| **ADR-020** | coarse 专用；legacy 仍用 `html_parser.parse_txt_to_structure` |
| **P0 禁止** | 改变 `office_read_document` 对 pdf 的 txt 粗读行为 |

### [x] **Task PDF-004** — `pdf/schemas/read.py`（OT-116 · 部分）

| 字段 | 内容 |
|------|------|
| **必须完成** | `PdfReadOptions`, `PdfReadArgs` |
| **必须完成** | `source_path` XOR `source_url`；`classify_file_ext == pdf` |

### [x] **Task PDF-005** — `pdf/tools/read.py` · coarse 路径（OT-121 · 部分）

| 字段 | 内容 |
|------|------|
| **必须完成** | `read_mode=coarse` → `convert_and_fetch` → `parse_txt_to_pages` |
| **必须完成** | `build_read_response` + coarse `_note`（不可用于 edit 定位） |
| **ADR-028** | 不得 inline 拼顶层 read dict |
| **ADR-025** | description 前缀 `[PDF]` |

### [x] **Task PDF-006** — `pdf/builder/__init__.py` / `schemas/__init__.py` / `tools/__init__.py`

| 字段 | 内容 |
|------|------|
| **必须完成** | 包结构完整 |

### [x] **Task PDF-007** — legacy pdf txt 回归

| 字段 | 内容 |
|------|------|
| **必须完成** | `legacy/read_document.py` pdf 仍走 `html_parser.parse_txt_to_structure` |
| **验收** | 现有 unit 绿；DS E2E → **PDF-044** |

### [x] **Task PDF-008** — `tests/office_mcp/pdf/test_pages_txt_parser.py`（OT-124 · 部分）

| 字段 | 内容 |
|------|------|
| **必须完成** | `\f` 分页；`--- page N ---`；无页界 → 单页 + note |

### [x] **Task PDF-009** — Gate **P0**

| 字段 | 内容 |
|------|------|
| **必须完成** | `poetry run pytest tests/office_mcp/pdf/ -v -m "not e2e"` 绿（P0 范围） |
| **禁止** | legacy pdf txt 行为回归 |

---

## Group B — P1：fine read + document parser

**Batch `T-PDF-P1` — Tasks PDF-010 – PDF-016** · **Gate：P1**

### [x] **Task PDF-010** — `pdf/parser/document.py`（OT-115）

| 字段 | 内容 |
|------|------|
| **必须完成** | `parse_document_json`：sidecar `{ pages: [...] }` → 规范化 pages[] |
| **必须完成** | `apply_page_range`；blocks / form_fields 结构 |
| **说明** | extract body 常量与 `core/builder_json_sidecar` 集成 |

### [x] **Task PDF-011** — `pdf/tools/read.py` · fine 路径（OT-121 · 部分）

| 字段 | 内容 |
|------|------|
| **必须完成** | `read_sidecar_json(..., PDF extract body)` |
| **必须完成** | `format`: structured / outline / text；`pages[]` ≡ `units[]` mirror |
| **必须完成** | `extra={"page_count"}`；`_locator_note` 指向 `office_edit_pdf` |
| **必须完成** | `include_form_fields` / `include_annotations` 选项 |

### [x] **Task PDF-012** — `tests/office_mcp/pdf/test_document_parser.py`（OT-124）

| 字段 | 内容 |
|------|------|
| **必须完成** | sidecar JSON fixtures；page_range；form_fields |

### [x] **Task PDF-013** — `tests/office_mcp/pdf/test_read_pdf.py`

| 字段 | 内容 |
|------|------|
| **必须完成** | mock sidecar fine read；coarse 分支；缺 source 错误 |

### [x] **Task PDF-014** — `tests/office_mcp/pdf/test_e2e_pdf_tools.py`（OT-125）

| 字段 | 内容 |
|------|------|
| **markers** | `@pytest.mark.pdf` `@pytest.mark.e2e` |
| **已交付** | 文件 + skip 占位 + `documentserver_reachable` skipif + ADR-021 native probe |
| **未完成** | 真实 create/read/edit/merge/fill 闭环 → **PDF-037–044** |

### [x] **Task PDF-015** — `tests/office_mcp/pdf/fixtures/`（OT-124）

| 字段 | 内容 |
|------|------|
| **必须完成** | `acroform_template.pdf`、`two_page_sample.pdf`、`document_sidecar.json` |

### [x] **Task PDF-016** — Gate **P1**

| 字段 | 内容 |
|------|------|
| **必须完成** | P1 unit 绿 |
| **部分完成** | E2E 仅占位；完整 Gate 见 **PDF-044** |

---

## Group C — P2：merge（builder + conversion）

**Batch `T-PDF-P2` — Tasks PDF-017 – PDF-022** · **Gate：P2**

### [x] **Task PDF-017** — `pdf/builder/merge.py`（OT-119）

| 字段 | 内容 |
|------|------|
| **必须完成** | `build_merge_script_builder`：多源 OpenFile → 合并页 → SaveFile |
| **必须完成** | `merge_pdfs_conversion` 显式路径 |
| **ADR-018** | **禁止** builder 失败 silent 切 conversion |
| **ADR-009** | builder 路径 → `run_builder_script` |

### [x] **Task PDF-018** — `pdf/tools/merge.py`（OT-121 · 部分）

| 字段 | 内容 |
|------|------|
| **必须完成** | `office_merge_pdfs`：`engine=conversion` → `merge_pdfs_conversion`；否则 builder script |
| **ADR-025** | `[PDF]` description；conversion 限制 `_note` |

### [x] **Task PDF-019** — `tests/office_mcp/pdf/test_merge_pdfs.py`

| 字段 | 内容 |
|------|------|
| **必须完成** | mock runtime；默认 builder script |
| **必须完成** | `engine=conversion` 走 conversion 函数 |

### [x] **Task PDF-020** — `tests/office_mcp/pdf/test_merge_builder.py`

| 字段 | 内容 |
|------|------|
| **必须完成** | `build_merge_script_builder` JS 结构断言 |

### [x] **Task PDF-021** — merge handler 双源校验

| 字段 | 内容 |
|------|------|
| **必须完成** | `source_paths` / `source_urls` 至少其一；pdf category 校验 |

### [x] **Task PDF-022** — Gate **P2**

| 字段 | 内容 |
|------|------|
| **必须完成** | P2 unit 绿 |
| **未完成** | merge **E2E** → **PDF-039–040** |

---

## Group D — P3：create + edit

**Batch `T-PDF-P3` — Tasks PDF-023 – PDF-030** · **Gate：P3**

### [x] **Task PDF-023** — `pdf/schemas/page_spec.py` / `edit_ops.py`（OT-116）

| 字段 | 内容 |
|------|------|
| **必须完成** | `PageSpec`, `BlockSpec`, `PdfCreateArgs`, `PdfCreateOptions` |
| **必须完成** | `EditOperation`, `PdfEditArgs`；6 种 `op` |
| **ADR-017** | `create_mode`: native / via_docx |
| **ADR-030** | edit_ops **无** `fill_form_field` |
| **已完成** | `page_size` schema + builder emit（**PDF-045**） |

### [x] **Task PDF-024** — `pdf/builder/create.py`（OT-117）

| 字段 | 内容 |
|------|------|
| **必须完成** | `build_create_script`：native `CreateFile("pdf")`；via_docx `CreateFile("docx")` → SaveFile pdf |
| **ADR-017** | native 失败 handler 追加 via_docx 提示；**不**自动重试 |
| **已完成** | `page_size` A4/Letter JS（**PDF-045**） |

### [x] **Task PDF-025** — `pdf/builder/edit.py`（OT-118）

| 字段 | 内容 |
|------|------|
| **必须完成** | `build_edit_script`：add_paragraph, set_page_text, add_page, delete_page, rotate_page, add_annotation |
| **ADR-008** | 单脚本一次 `run_builder_on_source` |
| **ADR-030** | **无** fill_form op |

### [x] **Task PDF-026** — `pdf/tools/create.py` / `edit.py`（OT-121 · 部分）

| 字段 | 内容 |
|------|------|
| **必须完成** | `office_create_pdf` → `run_builder_script` |
| **必须完成** | `office_edit_pdf` → `run_builder_on_source`；可选 `options.backup` |
| **已完成** | edit `TOOL_DEF.operations.items` ← `EditOperation.model_json_schema()`（**PDF-046**） |

### [x] **Task PDF-027** — `tests/office_mcp/pdf/test_create_pdf.py`

| 字段 | 内容 |
|------|------|
| **必须完成** | mock runtime；native / via_docx script 分支 |
| **必须完成** | native 失败 mock → **无**第二次 via_docx 调用 |

### [x] **Task PDF-028** — `tests/office_mcp/pdf/test_edit_pdf.py`

| 字段 | 内容 |
|------|------|
| **必须完成** | mock runtime；script 含 PDF document API |

### [x] **Task PDF-029** — `tests/office_mcp/pdf/test_schemas.py`

| 字段 | 内容 |
|------|------|
| **必须完成** | `fill_form_field` 不在 edit_ops；create_mode 枚举 |
| **必须完成** | merge engine 默认 builder |

### [x] **Task PDF-030** — Gate **P3**

| 字段 | 内容 |
|------|------|
| **必须完成** | P3 unit 绿 |
| **未完成** | create/edit **E2E** → **PDF-037–038、042–043** |

---

## Group E — P4 / M6：fill_form + registry

**Batch `T-PDF-P4` — Tasks PDF-031 – PDF-036** · **Gate：G4（PDF 切片）** · 全局 OT-120–126

### [x] **Task PDF-031** — `pdf/schemas/fill_form.py` / `builder/fill_form.py`（OT-120）

| 字段 | 内容 |
|------|------|
| **必须完成** | `PdfFillFormArgs`；`build_fill_form_script` 逐字段 SetValue |
| **ADR-019** | **不用** SetFormsData 批量接口 |
| **ADR-009** | `run_builder_on_source` |

### [x] **Task PDF-032** — `pdf/tools/fill_form.py`（OT-121 · 部分）

| 字段 | 内容 |
|------|------|
| **必须完成** | `office_fill_pdf_form` handler |
| **禁止** | `office_apply_template_pdf` |
| **ADR-025** | `[PDF]` description |

### [x] **Task PDF-033** — `tests/office_mcp/pdf/test_fill_pdf_form.py`（OT-124）

| 字段 | 内容 |
|------|------|
| **必须完成** | mock SetValue 循环；字段名与 read form_fields 一致 |

### [x] **Task PDF-034** — `registry.py` PDF 五模块（OT-122）

| 字段 | 内容 |
|------|------|
| **必须完成** | `CANONICAL_MODULES` 含 pdf.tools.read/create/edit/merge/fill_form |
| **禁止** | PDF legacy 别名；**无** apply_template 条目 |
| **验收** | M6：`len(collect_office_tools())==23`；`len(get_handlers())==27` |

### [x] **Task PDF-035** — `[PDF]` description + marker（OT-123）

| 字段 | 内容 |
|------|------|
| **ADR-025** | 五 canonical `TOOL_DEF["description"]` 前缀 `[PDF]` |
| **必须完成** | **`pyproject.toml` 注册 `pdf` marker**（strict-markers） |

### [x] **Task PDF-036** — Gate **M6 / G4 部分**（OT-126 · 部分）

| 字段 | 内容 |
|------|------|
| **必须完成** | `tests/office_mcp/test_registry.py` M6 **23/27**；pdf×5 ∈ canonical |
| **必须完成** | `poetry run pytest tests/office_mcp/pdf/ -v -m "not e2e"` **69 passed** |
| **未完成** | DS E2E 全清单 → **PDF-044**；OT-126 / G4 完整验收 |

---

## Group F — 明确禁止（PDF-NA）

| ID | 禁止 | 全局 |
|----|------|------|
| **PDF-NA-01** | `office_read_document` pdf→txt 行为变更 | OT-NA-05 / ADR-020 |
| **PDF-NA-02** | edit 中 `fill_form_field` op | **ADR-030** / OT-NA |
| **PDF-NA-03** | create native 失败 auto via_docx | **ADR-017** / OT-NA-03 |
| **PDF-NA-04** | `office_apply_template_pdf` | 架构 §7.4 |
| **PDF-NA-05** | merge builder 失败 silent 切 conversion | **ADR-018** |
| **PDF-NA-06** | `pdf/*` import word/presentation/spreadsheet | 架构 §7.4 |
| **PDF-NA-07** | OCR / 签名 / 加密 | Out of scope |

---

## Group G — UPGRADE 收尾：E2E（待完成）

**Batch `T-PDF-E2E` — Tasks PDF-037 – PDF-044** · [OFFICE_MCP_PDF_UPGRADE.md](./OFFICE_MCP_PDF_UPGRADE.md) §6 · DESIGN §10.3

> M6 架构（Group A–E）✅；本节为 **真实 E2E** 与 OT-126 / Gate G4 诚实验收。

### [x] **Task PDF-037** — E2E：`office_create_pdf` 2 页 → `office_read_pdf` fine

| 字段 | 内容 |
|------|------|
| **必须完成** | 替换 placeholder `pytest.skip`；`.env.test` + DocumentServer + storage paths |
| **必须完成** | create 2 页（paragraph blocks）→ read fine → assert `page_count == 2` |
| **验收** | `-m "pdf and e2e"` 至少 1 case **PASS** |
| **关联** | DESIGN §10.3 #1；OT-125、OT-126 |

### [x] **Task PDF-038** — E2E：`office_edit_pdf` `add_paragraph` → re-read

| 字段 | 内容 |
|------|------|
| **必须完成** | 基于 PDF-037 输出或 fixture；`page_index` + fine read 对齐 |
| **必须完成** | re-read fine → 新段落可见 |
| **关联** | DESIGN §10.3 #2 |

### [x] **Task PDF-039** — E2E：`office_merge_pdfs` builder 默认

| 字段 | 内容 |
|------|------|
| **必须完成** | 合并两个 1-page pdf（fixture 或先 create） |
| **必须完成** | re-read merged → assert `page_count == 2` |
| **关联** | DESIGN §10.3 #3 |

### [x] **Task PDF-040** — E2E：`office_merge_pdfs` `options.engine=conversion`

| 字段 | 内容 |
|------|------|
| **必须完成** | 显式 conversion 路径；断言 success 或 documented limitation |
| **关联** | DESIGN §10.3 #4；**ADR-018** |

### [x] **Task PDF-041** — E2E：`office_fill_pdf_form` + `acroform_template.pdf`

| 字段 | 内容 |
|------|------|
| **必须完成** | `data` 字段名与模板 form field 一致 |
| **必须完成** | 输出 pdf success；可选 re-read `form_fields` 值 |
| **关联** | DESIGN §10.3 #5；**ADR-019** |

### [x] **Task PDF-042** — E2E：`create_mode=native`（ADR-021 skip）

| 字段 | 内容 |
|------|------|
| **必须完成** | DS ≥ 9.3 + `probe_ds_capabilities().pdf_native_create` → native create PASS |
| **必须完成** | DS 不支持 → `pytest.skip`（非 placeholder skip） |
| **关联** | DESIGN §10.3 #6 native 分支 |

### [x] **Task PDF-043** — E2E：`create_mode=via_docx` 显式

| 字段 | 内容 |
|------|------|
| **必须完成** | 显式 `via_docx` create → read fine |
| **禁止** | 测 auto fallback（**PDF-NA-03**） |
| **关联** | DESIGN §10.3 #6 via_docx 分支；**ADR-017** |

### [x] **Task PDF-044** — Gate **P-E2E**

| 字段 | 内容 |
|------|------|
| **必须完成** | PDF-037–043 全部 `[x]`；本文档验收闸门 E2E 行改 `[x]` |
| **必须完成** | IMPLEMENTATION_DESIGN §3.2 / §12 E2E ✅；**UPGRADE §7.1** P-E2E 行 ✅ |
| **必须完成** | 无 unconditional `pytest.skip("placeholder")` / `"run manually"` 于 E2E test body |
| **关联** | OT-126；Gate **G4** |

---

## Group H — 代码 gap（待完成）

**Batch `T-PDF-GAP` — Tasks PDF-045 – PDF-046**

### [x] **Task PDF-045** — `builder/create.py` · `page_size` A4/Letter

| 字段 | 内容 |
|------|------|
| **必须完成** | `options.page_size` 写入 native / via_docx JS（以 DS PDF/Word API 为准） |
| **必须完成** | `test_create_pdf.py` 断言 script 含 page size 设置 |
| **现状** | schema + TOOL_DEF 已有；`build_create_script` 忽略 |
| **关联** | DESIGN §5.2、§7.1 |

### [x] **Task PDF-046** — `pdf/tools/edit.py` · `TOOL_DEF` operations schema（可选 hygiene）

| 字段 | 内容 |
|------|------|
| **建议** | `inputSchema.operations.items` ← `EditOperation.model_json_schema()` |
| **必须完成** | 6 op 枚举 + 各 op 字段单一来源 |
| **现状** | TOOL_DEF 仅 `"items": {"type": "object"}` |
| **说明** | 对标 Presentation **PT-045**（PDF 无 ADR-043 编号，但 MCP 发现性一致） |

---

## Group I — 文档收口（PDF-DOC-04 ✅）

**Batch `T-PDF-HYGIENE` — PDF-DOC-04**（架构文档已同步；E2E 后更新 OT-126）

### [x] **Task PDF-DOC-04** — Gate / E2E / gap 文档同步

| 字段 | 内容 |
|------|------|
| **必须完成** | IMPLEMENTATION_DESIGN §3.2 / §10 / §12 / **§14** as-built 与代码一致 |
| **必须完成** | UPGRADE §7.1 诚实状态（架构 ✅；**PDF-037–046** ✅） |
| **必须完成** | LLM_GUIDE §8 工具实现状态（unit ✅；E2E/gap ✅） |
| **已完成** | §1.2/§1.4 与 **ADR-030** 对齐；§6 E2E 清单与 DESIGN §10.3 对齐 |
| **待 E2E 后** | ~~全局 OT-126 / G4 脚注：PDF DS E2E 完成（**PDF-044**）~~ ✅ |

---

## 新建文件总览

### `aiecs/tools/office_tool/pdf/`

| 文件 | 阶段 | PDF |
|------|------|-----|
| `__init__.py` | P0 | PDF-001 |
| `parser/pages_txt.py` | P0 | PDF-003 |
| `parser/document.py` | P1 | PDF-010 |
| `schemas/read.py` | P0/P1 | PDF-004 |
| `schemas/page_spec.py` | P3 | PDF-023 |
| `schemas/edit_ops.py` | P3 | PDF-023 |
| `schemas/fill_form.py` | P4 | PDF-031 |
| `builder/create.py` | P3 | PDF-024 |
| `builder/edit.py` | P3 | PDF-025 |
| `builder/merge.py` | P2 | PDF-017 |
| `builder/fill_form.py` | P4 | PDF-031 |
| `tools/read.py` | P0/P1 | PDF-005, PDF-011 |
| `tools/create.py` | P3 | PDF-026 |
| `tools/edit.py` | P3 | PDF-026 |
| `tools/merge.py` | P2 | PDF-018 |
| `tools/fill_form.py` | P4 | PDF-032 |

### `tests/office_mcp/pdf/`

| 文件 | 阶段 | PDF |
|------|------|-----|
| `test_pages_txt_parser.py` | P0 | PDF-008 |
| `test_document_parser.py` | P1 | PDF-012 |
| `test_read_pdf.py` | P1 | PDF-013 |
| `test_merge_pdfs.py` | P2 | PDF-019 |
| `test_merge_builder.py` | P2 | PDF-020 |
| `test_create_pdf.py` | P3 | PDF-027 |
| `test_edit_pdf.py` | P3 | PDF-028 |
| `test_schemas.py` | P3 | PDF-029 |
| `test_fill_pdf_form.py` | P4 | PDF-033 |
| `test_e2e_pdf_tools.py` | P1+ | PDF-014 |
| `fixtures/acroform_template.pdf` | P4 | PDF-015 |
| `fixtures/two_page_sample.pdf` | P1 | PDF-015 |
| `fixtures/document_sidecar.json` | P1 | PDF-015 |

---

## PDF ↔ OT 对照表

| PDF Batch | PDF 范围 | 全局 OT |
|-----------|----------|---------|
| P0 | PDF-001 – PDF-009 | OT-113–114, 121(部分), 124 |
| P1 | PDF-010 – PDF-016 | OT-115, 121(部分), 125 |
| P2 | PDF-017 – PDF-022 | OT-119, 121(部分) |
| P3 | PDF-023 – PDF-030 | OT-116–118, 121(部分) |
| P4/M6 | PDF-031 – PDF-036 | OT-120–126 |
| **E2E** | **PDF-037 – PDF-044** | OT-125–126（G4） |
| **GAP** | **PDF-045 – PDF-046** | DESIGN §7.1 / §5.2 |
| **DOC** | PDF-DOC-04 ✅ | OT-007, OT-011, OT-126 |

---

## 验收闸门（PDF）

| 闸门 | 条件 | PDF |
|------|------|-----|
| **P0** | pages_txt 粗读 + legacy 回归 | PDF-009 |
| **P1** | fine read sidecar + parser unit | PDF-016 |
| **P2** | merge builder + conversion unit | PDF-022 |
| **P3** | create + edit unit；无 fill_form_field | PDF-030 |
| **M6 / G4** | registry **23/27**；`[PDF]`；69 unit tests | PDF-036 |
| **P-E2E** | DS 自动化 E2E（PDF-037–043） | **PDF-044** |
| **P5** | LLM 指南 §8 + README | **PDF-DOC-04** ✅ |

**命令：**

```bash
poetry run pytest tests/office_mcp/pdf/ -v -m "not e2e"
DOCUMENTSERVER_URL=... DOCUMENTSERVER_JWT_SECRET=... \
  poetry run pytest tests/office_mcp/pdf/ -v -m "pdf and e2e"
python3 -c "
from aiecs.tools.office_tool.registry import collect_office_tools, get_handlers
p = {'office_read_pdf','office_create_pdf','office_edit_pdf',
     'office_merge_pdfs','office_fill_pdf_form'}
assert p <= {t['name'] for t in collect_office_tools()}
c,h=len(collect_office_tools()),len(get_handlers())
assert (c,h)==(23,27), (c,h)
print('OK:', c, h)
"
! rg "word|presentation|spreadsheet" aiecs/tools/office_tool/pdf/ --glob "*.py" \
  | rg "^import|^from" && echo "FAIL" || echo "OK: pdf isolated"
```

- [x] **P0–P4** unit 全绿（29 tests）
- [x] **文档 as-built**（**PDF-DOC-04** ✅）
- [x] **P-E2E** pdf（PDF-037–044；`test_e2e_pdf_tools.py` 8 cases；无 placeholder skip）
- [x] **M6** pdf canonical ∈ `list_tools`（**23/27**）
- [x] **`page_size`** builder emit（**PDF-045**）
- [x] **edit TOOL_DEF** schema hygiene（**PDF-046** 可选）
- [x] **LLM_GUIDE §8** 实现状态（**PDF-DOC-04** ✅）

---

## 维护说明

**本文档** 为 [OFFICE_MCP_PDF_IMPLEMENTATION_DESIGN.md](./OFFICE_MCP_PDF_IMPLEMENTATION_DESIGN.md) 的**按文件执行清单**；与全局 [OFFICE_TOOL_IMPLEMENTATION_TASKS_BY_FILE.md](./OFFICE_TOOL_IMPLEMENTATION_TASKS_BY_FILE.md) 冲突时，以 **ADR 已采纳项** → PDF 实现设计 → 全局 tasks 为准。

**建议 PR 顺序：** P0 → P1 → P2 → P3 → P4 → M6（已完成）→ ~~PDF-DOC-04~~ ✅ → **PDF-037–044（E2E）** → **PDF-045–046**。

**UPGRADE 收尾优先级：** PDF-037–044（E2E）> PDF-045（page_size）> PDF-046（TOOL_DEF 可选）> ~~PDF-DOC-04~~ ✅。

**AI 编程 prompt（未完成 Task）：** [AI_PROMPT_OFFICE_MCP_PDF_IMPLEMENTATION.md](./AI_PROMPT_OFFICE_MCP_PDF_IMPLEMENTATION.md)（PDF-037–046；一次一个 Batch）。

**单 PR 模板：** 见 PDF 实现设计 §11 PR 分解。
