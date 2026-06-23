# Office MCP Presentation — 按文件必选任务（P0–P4 + M4）

**用途：** 落地 [OFFICE_MCP_PRESENTATION_IMPLEMENTATION_DESIGN.md](./OFFICE_MCP_PRESENTATION_IMPLEMENTATION_DESIGN.md) 时，将 Presentation 垂直模块从扁平 legacy / `html_parser` txt 路径迁移为 **`presentation/{parser,builder,schemas,tools}/` + registry 注册** 的**逐文件**执行清单。

**对齐（设计真源，实现前必读）：**

| 文档 | 角色 |
|------|------|
| [OFFICE_MCP_PRESENTATION_UPGRADE.md](./OFFICE_MCP_PRESENTATION_UPGRADE.md) | What：工具参数、slides/operations 语义 |
| [OFFICE_MCP_PRESENTATION_IMPLEMENTATION_DESIGN.md](./OFFICE_MCP_PRESENTATION_IMPLEMENTATION_DESIGN.md) | How（Presentation）：目录树、Core 集成、Builder、Gate |
| [implementation_design.md](./implementation_design.md) | How（全局）：Core §4、Registry §5、M4 §7.2 |
| [OFFICE_TOOL_IMPLEMENTATION_TASKS_BY_FILE.md](./OFFICE_TOOL_IMPLEMENTATION_TASKS_BY_FILE.md) | 全局 OT-083–099；**本表为其 Presentation 子集展开** |
| [ADR.md](./ADR.md) | ADR-002、006、008、009、016、024–025、028–029、**041–047** |
| [OFFICE_MCP_PRESENTATION_LLM_GUIDE.md](./OFFICE_MCP_PRESENTATION_LLM_GUIDE.md) | LLM 示例（`slide_index` / `shape_index` + `layouts[]`） |

**Preconditions（全局 M0–M3，Presentation 开工前）**

- [x] **M0**：`core/builder_runtime.py`、`core/builder_js.py`（全局 OT-013–022）
- [x] **M1**：`core/categories`、`errors`、`read_response`、`coarse_read`、`builder_json_sidecar`、`source`、`storage`（全局 OT-023–045）
- [x] **M3**：`registry.py` 骨架；Word 六工具已注册（**M4 前 canonical=8**）
- [x] `poetry run pytest tests/office_mcp/ -v -m "not e2e"` 全绿

**任务编号：** **PT-001 … PT-036**（架构交付）+ **PT-037 … PT-053**（UPGRADE 收尾）+ **PT-DOC-***。

**路径约定：** Python 相对仓库根 `aiecs/`、`tests/`；文档相对 `docs/`。

**完成定义：** **`[ ]` → `[x]`** = 本 Task 在对应 PR 中落地并满足「必须完成」列。

> **代码状态（2026-06）**
>
> | 范围 | 状态 |
> |------|------|
> | **架构 M4**（PT-001–036、PT-DOC-01–03） | ✅ 已落地：模块、registry、31 unit 测试 |
> | **UPGRADE 收尾**（PT-037–053） | ⏳ 待完成：E2E、**PT-045–049**、**PT-053** 代码 gap |
> | **文档 ADR-041～047** | ✅ **PT-DOC-04** 已同步 UPGRADE / DESIGN / LLM 指南 |
>
> 架构重组 **G2（Presentation 注册）** 已满足；**UPGRADE §7.2 E2E** 与部分 as-built gap 见 **Group I–L**。

**遵循的方法（Presentation 子集）：**

| 方法 | 来源 | 要求 |
|------|------|------|
| `run_builder_script` | ADR-009 | create / merge |
| `run_builder_on_source` | ADR-009 | edit / template（有源） |
| `build_read_response` | ADR-028 | `office_read_presentation` structured/outline；`layouts[]` 经 `extra=` |
| `err` / `ok` | ADR-006 | 全部 handler |
| Pydantic v2 | ADR-002 | `presentation/schemas/*` |
| `layouts[]` 精确匹配 | ADR-016 | create / `add_slide` 的 `layout`；**odp 与 pptx 分表** |
| Registry M4 | ADR-024 | 五工具 canonical；**无** presentation legacy 别名 |
| `[Presentation]` 前缀 | ADR-025 | 五 canonical description |
| 行为冻结 | PT-NA-01 | `office_read_document` pptx/ppt/odp **txt 粗读**不变 |

---

## 里程碑与 Gate

| 阶段 | Gate | 交付摘要 | 全局 |
|------|------|----------|------|
| **P0** | P0 | 目录 + txt 粗读；legacy pptx txt 回归 | OT-083–084, 088(部分), 096 |
| **P1-read** | P1（部分） | fine read sidecar + `parser/slides.py` | OT-085, 088, 093 |
| **P1a** | P1a | create + `slide_spec` | OT-086–087, 089(部分) |
| **P1b** | P1b | edit 10 op + `edit_ops` | OT-086–087, 089 |
| **P2** | P2 | merge + template + unit | OT-087, 090 |
| **M4** | **G2** | registry 五工具 + `[Presentation]` + fixtures | OT-091–098 |
| **P4** | P4 | `layouts_odp.json` + odp layout 校验 | OT-094(部分) |

**Registry（Presentation 相关）：** M4 时 gateway×2 + word×6 + pres×5 → **`collect_office_tools()==13`**，`get_handlers()==17`（+4 legacy，无 presentation legacy）。

---

## Group A — P0：目录 + txt 粗读

**Batch `T-PT-P0` — Tasks PT-001 – PT-009** · **Gate：P0**

### [x] **Task PT-001** — `aiecs/tools/office_tool/presentation/__init__.py`（OT-083）

| 字段 | 内容 |
|------|------|
| **必须完成** | 包初始化 |

### [x] **Task PT-002** — `presentation/parser/__init__.py`

| 字段 | 内容 |
|------|------|
| **必须完成** | 导出 `txt`、`slides` public API |

### [x] **Task PT-003** — `presentation/parser/txt.py`（OT-084）

| 字段 | 内容 |
|------|------|
| **必须完成** | 自 `html_parser.parse_txt_*` 迁入：`parse_txt_to_structure`、`extract_outline_from_txt` |
| **P0 禁止** | 改变 `office_read_document` 对 pptx/ppt/odp 的 txt 粗读行为 |

### [x] **Task PT-004** — `presentation/schemas/read.py`（OT-086 · 部分）

| 字段 | 内容 |
|------|------|
| **必须完成** | `PresentationReadOptions`, `PresentationReadArgs` |
| **必须完成** | `source_path` XOR `source_url`；`classify_file_ext == presentation` |

### [x] **Task PT-005** — `presentation/tools/read.py` · coarse 路径（OT-088 · 部分）

| 字段 | 内容 |
|------|------|
| **必须完成** | `read_mode=coarse` → `convert_and_fetch` → `parse_txt_to_structure` |
| **必须完成** | `build_read_response` + coarse `_note`（不可用于 edit 定位） |
| **ADR-028** | 不得 inline 拼顶层 read dict |
| **未完成** | fine 失败 → coarse fallback + `_note` → **PT-047**（**ADR-044**） |

### [x] **Task PT-006** — `presentation/builder/__init__.py` / `schemas/__init__.py` / `tools/__init__.py`

| 字段 | 内容 |
|------|------|
| **必须完成** | 包结构完整 |

### [x] **Task PT-007** — legacy pptx txt 回归（OT-096）

| 字段 | 内容 |
|------|------|
| **必须完成** | `legacy/read_document.py` presentation 仍走 txt |
| **验收** | 现有 `test_office_read*` unit 绿；DS E2E → **PT-042** |

### [x] **Task PT-008** — `tests/office_mcp/presentation/test_txt_parser.py`（OT-093 · 部分）

| 字段 | 内容 |
|------|------|
| **必须完成** | txt 解析 + canonical import 路径（ADR-022） |

### [x] **Task PT-009** — Gate **P0**

| 字段 | 内容 |
|------|------|
| **必须完成** | `poetry run pytest tests/office_mcp/presentation/ -v -m "not e2e"` 绿（P0 范围） |
| **禁止** | legacy txt 行为回归 |

---

## Group B — P1-read：fine read + slides parser

**Batch `T-PT-P1-READ` — Tasks PT-010 – PT-016** · **Gate：P1-read**

### [x] **Task PT-010** — `presentation/parser/slides.py`（OT-085）

| 字段 | 内容 |
|------|------|
| **必须完成** | `SLIDES_TOJSON_EXTRACT_BODY` sidecar extract |
| **必须完成** | `parse_slides_json`, `apply_slide_range`, `slides_to_outline`, `slides_to_text`, `word_count_from_slides` |
| **必须完成** | `layouts[]` 去重（**ADR-016**） |
| **未完成** | sidecar 按 `options.slide_range` 传 start/end → **PT-048**（**ADR-045**） |
| **ADR-047** | `layouts[]` 不完整 `_note` → **PT-053**（非 PT-011） |

### [x] **Task PT-011** — `presentation/tools/read.py` · fine 路径（OT-088）

| 字段 | 内容 |
|------|------|
| **必须完成** | `read_sidecar_json(..., SLIDES_TOJSON_EXTRACT_BODY)` |
| **必须完成** | `format`: structured / outline / text；`slides[]` ≡ `units[]` mirror |
| **必须完成** | `extra={"layouts", "slide_count"}`；`_locator_note` 指向 `office_edit_presentation` |
| **ADR-025** | description 前缀 `[Presentation]` |

### [x] **Task PT-012** — `tests/office_mcp/presentation/test_slides_parser.py`（OT-093）

| 字段 | 内容 |
|------|------|
| **必须完成** | 多 slide fixture；layouts 去重；slide_range；outline/text |

### [x] **Task PT-013** — `tests/office_mcp/presentation/test_read_presentation.py`

| 字段 | 内容 |
|------|------|
| **必须完成** | mock sidecar fine read；coarse 分支；缺 source 错误 |

### [x] **Task PT-014** — `tests/office_mcp/presentation/test_e2e_presentation_tools.py`（OT-095）

| 字段 | 内容 |
|------|------|
| **markers** | `@pytest.mark.presentation` `@pytest.mark.e2e` |
| **已交付** | 文件 + skip 占位 + `documentserver_reachable` skipif |
| **未完成** | 真实 create/read/edit 闭环 → **PT-037–044** |

### [x] **Task PT-015** — `tests/office_mcp/presentation/fixtures/slides_tojson_pptx.json`（OT-093）

| 字段 | 内容 |
|------|------|
| **必须完成** | SlidesToJSON 样例供 parser 单测 |

### [x] **Task PT-016** — Gate **P1-read**

| 字段 | 内容 |
|------|------|
| **必须完成** | P1-read unit 绿 |
| **部分完成** | E2E 仅占位；完整 Gate 见 **PT-044** |

---

## Group C — P1a：声明式 create

**Batch `T-PT-P1A` — Tasks PT-017 – PT-021** · **Gate：P1a**

### [x] **Task PT-017** — `presentation/schemas/slide_spec.py`（OT-086）

| 字段 | 内容 |
|------|------|
| **必须完成** | `SlideSpec`, `ShapeSpec`, `PresentationCreateArgs`, `PresentationCreateOptions` |
| **ADR-016** | `validate_slides_layouts`；`options.allowed_layouts` required（**ADR-046** 无 template_path） |
| **必须完成** | `layout` 字段 min_length=1 |

### [x] **Task PT-018** — `presentation/builder/create.py`（OT-087 · P1a）

| 字段 | 内容 |
|------|------|
| **必须完成** | `build_create_script(slides, output_ext, options)` |
| **必须完成** | `CreateFile` → `Api.GetPresentation()` → `AddSlide(layout)` → title/subtitle/bullets/shapes/notes |
| **必须完成** | `SaveFile` 跟 `output_path` ext（pptx/odp） |
| **禁止** | `Api.GetDocument()` Word API |
| **说明** | `ShapeSpec.position` 未写入 JS（as-built 默认位置） |

### [x] **Task PT-019** — `presentation/tools/create.py`（OT-089 · 部分）

| 字段 | 内容 |
|------|------|
| **必须完成** | `office_create_presentation` → `run_builder_script` |
| **必须完成** | `assert_category_path("presentation", output_path)` |
| **ADR-025** | `[Presentation]` description |

### [x] **Task PT-020** — `tests/office_mcp/presentation/test_create_presentation.py`

| 字段 | 内容 |
|------|------|
| **必须完成** | mock runtime；script 含 `CreateFile`、`GetPresentation`、`AddSlide` |

### [x] **Task PT-021** — Gate **P1a**

| 字段 | 内容 |
|------|------|
| **必须完成** | P1a unit 绿 |
| **未完成** | create pptx **E2E** → **PT-037** |

---

## Group D — P1b：声明式 edit

**Batch `T-PT-P1B` — Tasks PT-022 – PT-027** · **Gate：P1b**

### [x] **Task PT-022** — `presentation/schemas/edit_ops.py`（OT-086 · P1b）

| 字段 | 内容 |
|------|------|
| **必须完成** | `EditOperation`, `PresentationEditArgs`；10 种 `op` |
| **ADR-016** | `add_slide` 须 `layout`；`validate_add_slide_layouts` + `options.allowed_layouts` |
| **定位** | `shape_index` / `match_text` / `role` 校验 |
| **未完成** | `add_slide` 的 `title`/`subtitle`/`items` → **PT-046**（**ADR-041**） |

### [x] **Task PT-023** — `presentation/builder/edit.py` + `builder/notes.py`（OT-087 · P1b）

| 字段 | 内容 |
|------|------|
| **必须完成** | `build_edit_script(operations, file_ext)` — body only |
| **必须完成** | 10 op 均有 `_emit_operation` 分支 |
| **必须完成** | shape 解析：`shape_index` > `match_text` > `role` |
| **ADR-008** | 单脚本一次 `run_builder_on_source` |
| **说明** | `test_presentation_builder.py` 仅覆盖部分 op → **PT-050** |

### [x] **Task PT-024** — `presentation/tools/edit.py`（OT-089）

| 字段 | 内容 |
|------|------|
| **必须完成** | `office_edit_presentation` → `run_builder_on_source` |
| **必须完成** | 可选 `options.backup`；`allowed_layouts` 校验 `add_slide` |
| **未完成** | `TOOL_DEF.operations.items` 与 `edit_ops.py` 一致 → **PT-045**（**ADR-043**） |

### [x] **Task PT-025** — `tests/office_mcp/presentation/test_schemas.py`（OT-097）

| 字段 | 内容 |
|------|------|
| **必须完成** | layout 枚举 reject/accept（`layouts_pptx.json`） |
| **必须完成** | 非法 slide_index、缺字段 |
| **未完成** | `layouts_odp.json` 用例；duplicate/move/set_notes → **PT-051** |

### [x] **Task PT-026** — `tests/office_mcp/presentation/test_edit_presentation.py`

| 字段 | 内容 |
|------|------|
| **必须完成** | mock runtime；script 含 `Api.GetPresentation` |

### [x] **Task PT-027** — Gate **P1b / P1**

| 字段 | 内容 |
|------|------|
| **必须完成** | P1 unit 绿 |
| **未完成** | E2E create→read→edit→read → **PT-037–038** |

---

## Group E — P2：merge + template

**Batch `T-PT-P2` — Tasks PT-028 – PT-032** · **Gate：P2**

### [x] **Task PT-028** — `presentation/builder/merge.py`（OT-087 · P2）

| 字段 | 内容 |
|------|------|
| **必须完成** | `build_merge_script`：多源 OpenFile → 合并 slides → SaveFile |
| **ADR-009** | `run_builder_script` |
| **未完成** | `separator_slide` 硬编码 `"Blank"` → **PT-049**（**ADR-042**：`separator_layout` + `allowed_layouts`） |

### [x] **Task PT-029** — `presentation/builder/template.py`（OT-087 · P2）

| 字段 | 内容 |
|------|------|
| **必须完成** | `{{key}}` 全局替换 + `slide_{N}_` 前缀键 |
| **禁止** | 复用 `word/builder/template.py`（Document API） |
| **ADR-009** | edit body → `run_builder_on_source` |

### [x] **Task PT-030** — `presentation/tools/merge.py` / `template.py`（OT-090）

| 字段 | 内容 |
|------|------|
| **必须完成** | `office_merge_presentations` → `run_builder_script` |
| **必须完成** | `office_apply_template_presentation` → `run_builder_on_source` |
| **工具名** | 与 UPGRADE §4 一致 |

### [x] **Task PT-031** — `tests/office_mcp/presentation/test_merge_presentations.py` / `test_apply_template_presentation.py`

| 字段 | 内容 |
|------|------|
| **必须完成** | merge script 含 Presentation API |
| **必须完成** | template `{{company_name}}` / `slide_1_*` mock 断言 |

### [x] **Task PT-032** — Gate **P2**

| 字段 | 内容 |
|------|------|
| **必须完成** | merge + template unit 绿 |
| **未完成** | merge/template **E2E** → **PT-039–040** |

---

## Group F — M4：Registry + 描述 + fixtures

**Batch `T-PT-M4` — Tasks PT-033 – PT-036** · **Gate：G2（Presentation 切片）** · 全局 OT-091–098

### [x] **Task PT-033** — `registry.py` Presentation 五模块（OT-091）

| 字段 | 内容 |
|------|------|
| **必须完成** | `CANONICAL_MODULES` 含 presentation.tools.read/create/edit/merge/template |
| **禁止** | presentation legacy 别名 |
| **验收** | M4：`len(collect_office_tools())==13`；`len(get_handlers())==17` |

### [x] **Task PT-034** — `[Presentation]` description + marker（OT-092）

| 字段 | 内容 |
|------|------|
| **ADR-025** | 五 canonical `TOOL_DEF["description"]` 前缀 `[Presentation]` |
| **必须完成** | **`pyproject.toml` 注册 `presentation` marker**（strict-markers） |

### [x] **Task PT-035** — `tests/office_mcp/presentation/` 目录 + fixtures（OT-093–094）

| 字段 | 内容 |
|------|------|
| **必须完成** | presentation 相关测试均在 `tests/office_mcp/presentation/` |
| **必须完成** | `fixtures/layouts_pptx.json`、`fixtures/layouts_odp.json`（**ADR-016**） |
| **未完成** | odp fixture 无单测/E2E 引用 → **PT-041、PT-051** |

### [x] **Task PT-036** — Gate **M4 / G2 部分**（OT-098–099 · 部分）

| 字段 | 内容 |
|------|------|
| **必须完成** | 五工具 ∈ `collect_office_tools()`；`test_registry` 前缀断言（M6 23/27 含 pres×5） |
| **部分完成** | **无** dedicated M4 **13/17** 单测（`test_registry` 仅 M6）→ **PT-052** |
| **部分完成** | OT-099 / G2 E2E 绿 → 仅占位；**P-E2E** → **PT-044** |

---

## Group G — 文档（M4 同步）

**Batch `T-PT-DOC` — 映射全局 OT-004 / OT-008**

### [x] **Task PT-DOC-01** — `docs/OFFICE_MCP_PRESENTATION_UPGRADE.md`

| 字段 | 内容 |
|------|------|
| **必须完成** | §4 字段名与 schema 一致；§8 实施计划 |
| **收尾** | PT-044 后复核 E2E 行 ✅；**ADR-041～047** 已同步（**PT-DOC-04** ✅） |

### [x] **Task PT-DOC-02** — `docs/OFFICE_MCP_PRESENTATION_LLM_GUIDE.md`

| 字段 | 内容 |
|------|------|
| **必须完成** | `slide_index` / `layouts[]` / `allowed_layouts`；**ADR-041～047** 示例 |
| **已完成** | **PT-DOC-04**：§2.4、§3、§7 与 ADR 同步 |

### [x] **Task PT-DOC-03** — `docs/OFFICE_MCP_PRESENTATION_IMPLEMENTATION_DESIGN.md` + **本文档**

| 字段 | 内容 |
|------|------|
| **必须完成** | 设计与 tasks 互链；§12 / **§14** gap 表与 ADR-041～047（**PT-001–053**） |

---

## Group H — 明确禁止（PT-NA）

| ID | 禁止 | 全局 |
|----|------|------|
| **PT-NA-01** | `office_read_document` → fine read 透明转发 | OT-NA-05 |
| **PT-NA-02** | 对 pptx 使用 `office_edit_document`（Word `oDoc` API） | UPGRADE §6 |
| **PT-NA-03** | M3 后在 `core/` 做 Presentation feature（非 bugfix） | OT-NA-09 / ADR-029 |
| **PT-NA-04** | presentation legacy MCP 别名 | ADR-024 |
| **PT-NA-05** | 用 `office_read_document` 的 `elements[].index` 编辑 pptx | LLM 指南 §5 |
| **PT-NA-06** | `presentation/*` import word/spreadsheet/pdf | 架构 §7.2 |

---

## Group I — UPGRADE 收尾：E2E（待完成）

**Batch `T-PT-E2E` — Tasks PT-037 – PT-044** · [OFFICE_MCP_PRESENTATION_UPGRADE.md](./OFFICE_MCP_PRESENTATION_UPGRADE.md) §7.2 · DESIGN §10.3

> M4 架构（Group A–F）✅；本节为 **真实 E2E** 与 OT-099 / Gate G2 诚实验收。

### [ ] **Task PT-037** — `test_e2e_presentation_tools.py`：create pptx → read fine（3 slides）

| 字段 | 内容 |
|------|------|
| **必须完成** | 替换 placeholder `pytest.skip`；`.env.test` + DocumentServer + MCP |
| **必须完成** | `office_create_presentation` 3 slides（layout ∈ `layouts_pptx.json` 或先 read 模板 deck） |
| **必须完成** | `office_read_presentation` fine → assert `slide_count` / `unit_count` == 3；`layouts[]` 非空 |
| **验收** | `-m "presentation and e2e"` 至少 1 case **PASS** |
| **关联** | OT-095、OT-099；PT-014 占位补全 |

### [ ] **Task PT-038** — E2E：edit `set_title` + `set_bullets` + `add_slide` → re-read

| 字段 | 内容 |
|------|------|
| **必须完成** | `office_edit_presentation` 三 op；`add_slide.layout` ∈ prior read `layouts[]` |
| **必须完成** | re-read fine → 变更可见 |
| **关联** | DESIGN §10.3 #2；UPGRADE §7.2 |

### [ ] **Task PT-039** — E2E：`office_merge_presentations`

| 字段 | 内容 |
|------|------|
| **必须完成** | 合并两 pptx（`E2E_SOURCE_PATHS` 或先 create 两 deck） |
| **必须完成** | re-read merged → assert `slide_count` == sum(sources)（无 slide 冲突时） |
| **关联** | DESIGN §10.3 #3 |

### [ ] **Task PT-040** — E2E：`office_apply_template_presentation`

| 字段 | 内容 |
|------|------|
| **必须完成** | `E2E_TEMPLATE_PATH` pptx + `data` 含 `{{company_name}}` 或 `slide_1_title` |
| **必须完成** | 断言 handler success |
| **推荐** | re-read fine 断言 `{{company_name}}` 或 `slide_1_*` 替换可见 |
| **关联** | DESIGN §10.3 #4 |

### [ ] **Task PT-041** — E2E：odp 往返（**P4** / ADR-016）

| 字段 | 内容 |
|------|------|
| **必须完成** | create odp → edit → save odp；layout 来自 `fixtures/layouts_odp.json` |
| **关联** | DESIGN §10.3 #5、§12 P4 |

### [ ] **Task PT-042** — E2E：`office_read_document` pptx txt 粗读（PT-NA-01）

| 字段 | 内容 |
|------|------|
| **必须完成** | legacy txt 粗读不变；无透明 fine 转发 |
| **关联** | DESIGN §10.3 #6 |

### [ ] **Task PT-043** — E2E / 集成：禁止对 pptx 调用 `office_edit_document`

| 字段 | 内容 |
|------|------|
| **必须完成** | `tests/office_mcp/presentation/test_e2e_presentation_tools.py` **或** `tests/office_mcp/test_integration.py`：对 pptx 源调用 `office_edit_document` → 断言 `{isError}` 或非成功编辑（Word API 不适用） |
| **禁止** | 仅 module docstring 替代本 Task 的自动化断言 |
| **关联** | DESIGN §10.3 #7；PT-NA-02 |

### [ ] **Task PT-044** — Gate **P-E2E**

| 字段 | 内容 |
|------|------|
| **必须完成** | PT-037–043 全部 `[x]`；本文档验收闸门 E2E 行改 `[x]` |
| **必须完成** | IMPLEMENTATION_DESIGN §3.2 P1/P2/P4 E2E ✅；**UPGRADE §8.1** P-E2E 行 ✅ |
| **必须完成** | 无 unconditional `pytest.skip("placeholder")` 于 E2E test body |

---

## Group J — Schema / Read 对齐（待完成）

**Batch `T-PT-SCHEMA` — Tasks PT-045 – PT-049、PT-053** · ADR-041～045、047

### [ ] **Task PT-045** — `presentation/tools/edit.py` · `TOOL_DEF` operations schema

| 字段 | 内容 |
|------|------|
| **ADR-043** | `inputSchema.operations.items` ← `EditOperation.model_json_schema()` |
| **ADR-002** | 10 op 枚举 + 各 op 字段（含 **ADR-041** add_slide 字段） |
| **必须完成** | 单一来源；禁止手写 JSON Schema 双份维护 |
| **现状** | TOOL_DEF 仅 `"items": {"type": "object"}` |

### [ ] **Task PT-046** — `add_slide` schema ↔ builder 对齐

| 字段 | 内容 |
|------|------|
| **ADR-041** | `edit_ops.py` 增加可选 **`title`**, **`subtitle`**, **`items`** |
| **必须完成** | `builder/edit.py` 填 subtitle/items；UPGRADE/LLM 用 `items` 非 `bullets` |
| **必须完成** | PT-046 完成后 **重跑 PT-038** E2E（或补 `add_slide` + `items` 单测/E2E 断言） |
| **现状** | builder 引用 `op.title`；schema 无字段 |

### [ ] **Task PT-047** — fine read 失败 → coarse fallback + `_note`

| 字段 | 内容 |
|------|------|
| **ADR-044** | `options.allow_coarse_fallback` 默认 true；false → `err` |
| **文件** | `presentation/tools/read.py`, `schemas/read.py` |
| **现状** | sidecar 失败直接 `err` |

### [ ] **Task PT-048** — sidecar `slide_range` 传入 extract body

| 字段 | 内容 |
|------|------|
| **ADR-045** | `build_slides_extract_body(start, end)`；`SlidesToJSON(start,end,...)` |
| **文件** | `presentation/parser/slides.py`, `presentation/tools/read.py` |
| **现状** | 固定 `0..last`；range 仅 Python 后过滤 |

### [ ] **Task PT-049** — `builder/merge.py` · `separator_slide` layout

| 字段 | 内容 |
|------|------|
| **ADR-042** | `separator_layout` + **`options.allowed_layouts`**（handler 校验，与 edit 同模式） |
| **必须完成** | 删除 `AddSlide("Blank")`；`validate_merge_separator_layout` |
| **文件** | `edit_ops` MergeOptions, `slide_spec.py`, `tools/merge.py`, `builder/merge.py` |

### [ ] **Task PT-053** — read `layouts[]` 不完整 `_note`（**ADR-047**）

| 字段 | 内容 |
|------|------|
| **ADR-047** | fine structured：当 `len(layouts) <= 1` 且 `slide_count > 0` 时，`build_read_response` **`extra` append `_note`**（与 `_locator_note` / ADR-044 coarse `_note` 并存） |
| **文案** | *"layouts[] may be incomplete if deck uses few layouts; read a multi-layout template master for full enum (ADR-047)."* |
| **文件** | `presentation/tools/read.py` |
| **必须完成** | `tests/office_mcp/presentation/test_read_presentation.py` mock 断言 `_note` 条件 |
| **关联** | PT-010 parse 去重 ✅；**非** PT-011（架构 read 路径已交付） |

---

## Group K — Builder / 单测收尾（待完成）

**Batch `T-PT-BUILDER` — Tasks PT-050 – PT-052**

### [ ] **Task PT-050** — `test_presentation_builder.py` 覆盖剩余 edit op

| 字段 | 内容 |
|------|------|
| **必须完成** | 至少断言 script body：`set_bullets`, `duplicate_slide`, `move_slide`, `set_notes`, `replace_image`, `remove_shape`, `match_text`/`role` |
| **说明** | 对标 Word `test_edit_builder.py` |

### [ ] **Task PT-051** — `test_schemas.py` · odp + 剩余 op 校验

| 字段 | 内容 |
|------|------|
| **必须完成** | `layouts_odp.json` layout 枚举用例 |
| **必须完成** | `duplicate_slide` / `move_slide` / `set_notes` 必填字段 reject |

### [ ] **Task PT-052** — `test_registry.py` · M4 **13/17** 里程碑（可选但推荐）

| 字段 | 内容 |
|------|------|
| **说明** | 当前仅 M6 23/27；可增 `TestRegistryM4` 或 slice 断言 modules[8:13] 为 presentation |
| **关联** | OT-098；DESIGN §9 |

---

## Group L — 文档收口（PT-DOC-04 ✅）

**Batch `T-PT-HYGIENE` — PT-DOC-04**（架构文档已同步；E2E 后更新 OT-099）

### [x] **Task PT-DOC-04** — Gate / E2E / gap 文档同步

| 字段 | 内容 |
|------|------|
| **必须完成** | IMPLEMENTATION_DESIGN §3.2 / §10 / §12 / **§14** 与 ADR-041～047 一致 |
| **必须完成** | UPGRADE §4 / §8.1 诚实状态（架构 ✅；E2E / PT-045–049、**PT-053** ⏳） |
| **必须完成** | LLM_GUIDE §2.4–§3.5 / §7 与 ADR 同步 |
| **待 E2E 后** | 全局 OT-099 / G2 脚注：Presentation DS E2E 完成（**PT-044**） |

---

## 新建文件总览

### `aiecs/tools/office_tool/presentation/`

| 文件 | 阶段 | PT |
|------|------|-----|
| `__init__.py` | P0 | PT-001 |
| `parser/txt.py` | P0 | PT-003 |
| `parser/slides.py` | P1-read | PT-010 |
| `schemas/read.py` | P0/P1-read | PT-004 |
| `schemas/slide_spec.py` | P1a | PT-017 |
| `schemas/edit_ops.py` | P1b | PT-022 |
| `builder/create.py` | P1a | PT-018 |
| `builder/edit.py` | P1b | PT-023 |
| `builder/notes.py` | P1b | PT-023 |
| `builder/merge.py` | P2 | PT-028 |
| `builder/template.py` | P2 | PT-029 |
| `tools/read.py` | P0/P1-read | PT-005, PT-011 |
| `tools/create.py` | P1a | PT-019 |
| `tools/edit.py` | P1b | PT-024 |
| `tools/merge.py` | P2 | PT-030 |
| `tools/template.py` | P2 | PT-030 |

### `tests/office_mcp/presentation/`

| 文件 | 阶段 | PT |
|------|------|-----|
| `test_txt_parser.py` | P0 | PT-008 |
| `test_slides_parser.py` | P1-read | PT-012 |
| `test_read_presentation.py` | P1-read | PT-013 |
| `test_create_presentation.py` | P1a | PT-020 |
| `test_schemas.py` | P1b | PT-025 |
| `test_edit_presentation.py` | P1b | PT-026 |
| `test_merge_presentations.py` | P2 | PT-031 |
| `test_apply_template_presentation.py` | P2 | PT-031 |
| `test_presentation_builder.py` | P1b | PT-023 |
| `test_e2e_presentation_tools.py` | P1-read+ | PT-014 |
| `fixtures/slides_tojson_pptx.json` | P1-read | PT-015 |
| `fixtures/layouts_pptx.json` | M4 | PT-035 |
| `fixtures/layouts_odp.json` | M4/P4 | PT-035 |

---

## PT ↔ OT 对照表

| Presentation Batch | PT 范围 | 全局 OT |
|--------------------|---------|---------|
| P0 | PT-001 – PT-009 | OT-083–084, 088(部分), 096 |
| P1-read | PT-010 – PT-016 | OT-085, 088, 093, 095 |
| P1a | PT-017 – PT-021 | OT-086–087, 089(部分) |
| P1b | PT-022 – PT-027 | OT-086–087, 089, 097 |
| P2 | PT-028 – PT-032 | OT-087, 090 |
| M4 | PT-033 – PT-036 | OT-091–099 |
| DOC | PT-DOC-* | OT-004, 008 |
| **E2E** | **PT-037 – PT-044** | OT-095, OT-099（G2） |
| **SCHEMA** | PT-045 – PT-049、**PT-053** | **ADR-041～045、047** |
| **BUILDER** | PT-050 – PT-052 | DESIGN §10.2 |
| **HYGIENE** | PT-DOC-04 | OT-099 |

---

## 验收闸门（Presentation）

| 闸门 | 条件 | PT |
|------|------|-----|
| **P0** | txt 粗读 + legacy 回归 | PT-009 |
| **P1-read** | fine read sidecar + parser unit | PT-016 |
| **P1a** | create + slide_spec unit | PT-021 |
| **P1b** | edit 10 op + schemas unit | PT-027 |
| **P2** | merge + template unit | PT-032 |
| **M4 / G2** | registry 13/17；`[Presentation]`；`tests/presentation/` | PT-036 |
| **P-E2E** | DS 自动化 E2E（PT-037–043） | **PT-044** |
| **P4** | odp layout E2E + enum 单测 | **PT-041**, **PT-051** |

**命令：**

```bash
poetry run pytest tests/office_mcp/presentation/ -v -m "not e2e"
DOCUMENTSERVER_URL=... DOCUMENTSERVER_JWT_SECRET=... \
  poetry run pytest tests/office_mcp/presentation/ -v -m "presentation and e2e"
python3 -c "
from aiecs.tools.office_tool.registry import collect_office_tools, get_handlers
p = {'office_read_presentation','office_create_presentation','office_edit_presentation',
     'office_merge_presentations','office_apply_template_presentation'}
assert p <= {t['name'] for t in collect_office_tools()}
c,h=len(collect_office_tools()),len(get_handlers())
assert (c,h)==(13,17) or (c,h)==(23,27), (c,h)
print('OK:', c, h)
"
! rg "word|spreadsheet|pdf" aiecs/tools/office_tool/presentation/ --glob "*.py" \
  | rg "^import|^from" && echo "FAIL" || echo "OK: presentation isolated"
```

- [x] **P0–P2** unit 全绿（31 tests）
- [ ] **P-E2E** presentation（PT-037–044；placeholder skip）
- [x] **M4** presentation canonical ∈ `list_tools`（**13/17** at M4 slice；当前 repo **23/27** M6）
- [ ] **`office_read_document`** pptx txt DS E2E（PT-042）
- [ ] **Schema / Read 对齐**（PT-045–049、**PT-053**；**ADR-041～045、047** 代码）
- [ ] **Builder / 单测收尾**（PT-050–052）
- [ ] **P4 odp** layout E2E（PT-041、PT-051）
- [x] **文档 ADR-041～047**（**PT-DOC-04**）

---

## 维护说明

**本文档** 为 [OFFICE_MCP_PRESENTATION_IMPLEMENTATION_DESIGN.md](./OFFICE_MCP_PRESENTATION_IMPLEMENTATION_DESIGN.md) 的**按文件执行清单**；与全局 [OFFICE_TOOL_IMPLEMENTATION_TASKS_BY_FILE.md](./OFFICE_TOOL_IMPLEMENTATION_TASKS_BY_FILE.md) 冲突时，以 **ADR 已采纳项** → Presentation 实现设计 → 全局 tasks 为准。

**建议 PR 顺序：** P0 → P1-read → P1a → P1b → P2 → M4（已完成）→ **PT-037–044（E2E）** → PT-045–049、**PT-053**（**ADR-041～045、047** 代码）→ PT-050–052 → ~~PT-DOC-04~~ ✅。

**UPGRADE 收尾优先级：** PT-037–044（E2E）> PT-045–049、**PT-053**（TOOL_DEF / read / merge layout）> PT-050–052 > ~~PT-DOC-04~~ ✅。

**AI 编程 prompt（未完成 Task）：** [AI_PROMPT_OFFICE_MCP_PRESENTATION_IMPLEMENTATION.md](./AI_PROMPT_OFFICE_MCP_PRESENTATION_IMPLEMENTATION.md)（PT-037–053；一次一个 Batch）。

**单 PR 模板：** 见 Presentation 实现设计 §11 PR 分解。
