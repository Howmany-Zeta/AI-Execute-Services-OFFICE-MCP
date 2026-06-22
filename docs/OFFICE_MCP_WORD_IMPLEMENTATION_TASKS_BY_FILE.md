# Office MCP Word — 按文件必选任务（W0–W3 + M3）

**用途：** 落地 [OFFICE_MCP_WORD_IMPLEMENTATION_DESIGN.md](./OFFICE_MCP_WORD_IMPLEMENTATION_DESIGN.md) 时，将 Word 垂直模块从扁平 legacy 文件迁移为 **`word/{parser,builder,schemas,tools}/` + legacy 别名 + registry 注册** 的**逐文件**执行清单。

**对齐（设计真源，实现前必读）：**

| 文档 | 角色 |
|------|------|
| [OFFICE_MCP_WORD_UPGRADE.md](./OFFICE_MCP_WORD_UPGRADE.md) | What：工具参数、block/operations 语义 |
| [OFFICE_MCP_WORD_IMPLEMENTATION_DESIGN.md](./OFFICE_MCP_WORD_IMPLEMENTATION_DESIGN.md) | How（Word）：目录树、Core 集成、Builder、Gate |
| [implementation_design.md](./implementation_design.md) | How（全局）：Core §4、Registry §5、M2 §7.1 |
| [OFFICE_TOOL_IMPLEMENTATION_TASKS_BY_FILE.md](./OFFICE_TOOL_IMPLEMENTATION_TASKS_BY_FILE.md) | 全局 OT-046–082；**本表为其 Word 子集展开** |
| [ADR.md](./ADR.md) | ADR-002、006、010–012、023–025、028、029 |
| [OFFICE_MCP_WORD_LLM_GUIDE.md](./OFFICE_MCP_WORD_LLM_GUIDE.md) | LLM 示例（`search_string` / `replace_string`） |

**Preconditions（全局 M0–M1，Word 开工前）**

- [x] **M0**：`core/builder_runtime.py`、`core/builder_js.py`；根 builder 工具改调 runtime（全局 OT-013–022）
- [x] **M1**：`core/categories`、`errors`、`read_response`、`coarse_read`、`builder_json_sidecar`、`source`、`storage`（全局 OT-023–045）
- [x] **M1**：`pyproject.toml` 注册 **`word`** marker（全局 OT-045c；`--strict-markers`）
- [x] `poetry run pytest tests/office_mcp/ -v -m "not e2e"` 全绿

**任务编号：** **WT-001 … WT-036**（架构交付）+ **WT-037 … WT-049**（UPGRADE 收尾）+ **WT-DOC-***。

**路径约定：** Python 相对仓库根 `aiecs/`、`tests/`；文档相对 `docs/`。

**完成定义：** **`[ ]` → `[x]`** = 本 Task 在对应 PR 中落地并满足「必须完成」列。

> **代码状态（2026-06）**
>
> | 范围 | 状态 |
> |------|------|
> | **架构 M2–M3**（WT-001–036、WT-DOC-01–03） | ✅ 已落地：模块、registry、unit 测试 |
> | **UPGRADE 收尾**（WT-037–049、WT-DOC-04） | ✅ 已完成 |
>
> 架构重组 **G1（Word 注册）** 已满足；**UPGRADE §1.2 Must Have** 的自动化 E2E 与部分 schema 字段仍见 **Group H**。

**遵循的方法（Word 子集）：**

| 方法 | 来源 | 要求 |
|------|------|------|
| `run_builder_script` | ADR-009 | create / merge / template |
| `run_builder_on_source` | ADR-009 | edit / edit_script / template（有源） |
| `build_read_response` | ADR-028 | `office_read_word` structured/outline |
| `err` / `ok` | ADR-006 | 全部 handler |
| Pydantic v2 | ADR-002 | `word/schemas/*` |
| `search_string` / `replace_string` | edit_ops.py | **非** `search` / `replace` |
| Registry M3 | ADR-024 | Word 六工具 canonical；legacy 三别名 handlers only |
| `[Word]` 前缀 | ADR-025 | 六 canonical description |
| 行为冻结 | OT-NA-05 | `office_read_document` 不得透明 fine 转发 |

---

## 里程碑与 Gate

| 阶段 | Gate | 交付摘要 | 全局 |
|------|------|----------|------|
| **W0** | W0 | 目录迁移；merge/template/edit_script；**无行为变更** | OT-046–047, 050(部分), 056–058, 066 |
| **W1** | W1 | `office_read_word` + `parser/document.py` | OT-048, 051, 059–060 |
| **W2** | W2 | create/edit + schemas + E2E 闭环 | OT-049, 050(部分), 052–053, 061, 064 |
| **W3** | W3 | merge ext、template、legacy 别名 | OT-054–057, 062–065 |
| **M3** | G1（Word 部分） | registry 六工具 + `[Word]` + tests 目录 | OT-068, 077, 081–082 |

**Registry（Word 相关）：** M3 时 gateway×2 + word×6 → **`collect_office_tools()==8`**，`get_handlers()==12`（含 legacy×4）。

---

## Group A — W0：目录迁移（无新 MCP 暴露）

**Batch `T-WT-W0` — Tasks WT-001 – WT-012** · **Gate：W0**

### [x] **Task WT-001** — `aiecs/tools/office_tool/word/__init__.py`（OT-046）

| 字段 | 内容 |
|------|------|
| **必须完成** | 包初始化 |

### [x] **Task WT-002** — `word/parser/__init__.py`

| 字段 | 内容 |
|------|------|
| **必须完成** | 导出 `html`、`document` public API（可选空包） |

### [x] **Task WT-003** — `word/parser/html.py`（OT-047）

| 字段 | 内容 |
|------|------|
| **必须完成** | 自原 `html_parser.py` 迁入 `parse_html_to_structure`、`extract_plain_text` |
| **必须完成** | 供 coarse read + legacy 粗读复用 |
| **历史** | M7 前根 `html_parser.py` shim；**ADR-022 后 shim 已删** |

### [x] **Task WT-004** — `word/builder/merge.py`（OT-050 · W0）

| 字段 | 内容 |
|------|------|
| **必须完成** | 自原 `merge_document.py` 迁入 `build_merge_script` |
| **W3 增强** | `builder_file_ext(output_path)`，非写死 `docx` |

### [x] **Task WT-005** — `word/builder/template.py`（OT-050 · W0）

| 字段 | 内容 |
|------|------|
| **必须完成** | 自原 `apply_template.py` 迁入 `build_apply_template_script` |
| **必须完成** | `{{key}}` → `SearchAndReplace` |

### [x] **Task WT-006** — `word/tools/merge.py`（OT-054 · W0 可仅 handler 壳）

| 字段 | 内容 |
|------|------|
| **必须完成** | `office_merge_word` handler；`TOOL_NAME`, `TOOL_DEF`, `handler` |
| **必须完成** | 调用 `build_merge_script` + `run_builder_script` |

### [x] **Task WT-007** — `word/tools/template.py`（OT-055 · W0 可仅 handler 壳）

| 字段 | 内容 |
|------|------|
| **必须完成** | `office_apply_template_word` |

### [x] **Task WT-008** — `word/tools/edit_script.py`（OT-056）

| 字段 | 内容 |
|------|------|
| **必须完成** | 自原 `edit_document.py` 迁入；`office_edit_word_script` |
| **必须完成** | `run_builder_on_source`；用户脚本 **不含** Open/Save |

### [x] **Task WT-009** — `word/builder/__init__.py` / `word/schemas/__init__.py` / `word/tools/__init__.py`

| 字段 | 内容 |
|------|------|
| **必须完成** | 包结构完整 |

### [x] **Task WT-010** — Gate **W0** 回归（OT-066）

| 字段 | 内容 |
|------|------|
| **必须完成** | `poetry run pytest tests/office_mcp/ -v -m "not e2e"` 全绿 |
| **禁止** | merge/template/edit_script **行为回归** |

---

## Group B — W1：精读 read

**Batch `T-WT-W1` — Tasks WT-011 – WT-018** · **Gate：W1**

### [x] **Task WT-011** — `word/parser/document.py`（OT-048）

| 字段 | 内容 |
|------|------|
| **必须完成** | `WORD_TOJSON_EXTRACT_BODY` |
| **必须完成** | `parse_document_json`, `blocks_to_outline`, `blocks_to_text`, `word_count_from_blocks` |
| **必须完成** | `block_index`, `heading_path`, `type`, table `rows[][]` |

### [x] **Task WT-012** — `word/schemas/read.py`（OT-049 · 部分）

| 字段 | 内容 |
|------|------|
| **必须完成** | `WordReadOptions`, `WordReadArgs` |
| **必须完成** | `source_path` XOR `source_url` |

### [x] **Task WT-013** — `word/tools/read.py`（OT-051）

| 字段 | 内容 |
|------|------|
| **必须完成** | `office_read_word` |
| **必须完成** | fine：`read_sidecar_json` + `parse_document_json` + `build_read_response` |
| **必须完成** | coarse：`convert_and_fetch` + `parser/html` |
| **必须完成** | `format`: structured / outline / text；`read_mode`: fine / coarse |
| **必须完成** | `_locator_note` 固定文案（指向 `office_edit_word`） |
| **ADR-028** | 不得 inline 拼顶层 read dict |

### [x] **Task WT-014** — `tests/office_mcp/word/test_document_parser.py`（OT-059）

| 字段 | 内容 |
|------|------|
| **必须完成** | ToJSON fixture → blocks / heading_path / table |

### [x] **Task WT-015** — `tests/office_mcp/word/test_read_word.py`（OT-060）

| 字段 | 内容 |
|------|------|
| **必须完成** | mock sidecar / coarse；outline / text 分支 |

### [x] **Task WT-016** — Gate **W1**（OT-060 + E2E read）

| 字段 | 内容 |
|------|------|
| **必须完成** | unit 绿；有 DS 时 docx fine read E2E |

---

## Group C — W2：声明式 create / edit

**Batch `T-WT-W2` — Tasks WT-017 – WT-027** · **Gate：W2**

### [x] **Task WT-017** — `word/schemas/section_spec.py`（OT-049 · 部分）

| 字段 | 内容 |
|------|------|
| **必须完成** | `SectionSpec`, `WordCreateArgs`, `WordCreateOptions` |
| **必须完成** | `WordMergeArgs`, `WordTemplateArgs`, `WordEditScriptArgs` |
| **ADR-012** | `add_toc` bool；create 脚本文首 TOC |

### [x] **Task WT-018** — `word/schemas/edit_ops.py`（OT-049 · 部分）

| 字段 | 内容 |
|------|------|
| **必须完成** | `EditOperation`, `WordEditArgs`；10 种 `op` |
| **ADR-010** | `delete_block` + `block_type==table` → ValidationError |
| **ADR-011** | 拒绝 `relative_index` |
| **字段名** | `search_string`, `replace_string` |

### [x] **Task WT-019** — `word/builder/create.py`（OT-050 · W2）

| 字段 | 内容 |
|------|------|
| **必须完成** | `build_create_script(sections, output_ext, options)` |
| **必须完成** | section 类型：heading1–3, paragraph, bullets, table, page_break |

### [x] **Task WT-020** — `word/builder/edit.py`（OT-050 · W2）

| 字段 | 内容 |
|------|------|
| **必须完成** | `build_edit_script(operations, file_ext)` — body only |
| **必须完成** | `block_index` → `GetElement`；否则 `Search` |
| **说明** | `insert_bullets` / `insert_table` v1 追加文档末尾 |

### [x] **Task WT-021** — `word/tools/create.py`（OT-052）

| 字段 | 内容 |
|------|------|
| **必须完成** | `office_create_word` → `run_builder_script` |
| **必须完成** | `assert_category_path("word", output_path)` |

### [x] **Task WT-022** — `word/tools/edit.py`（OT-053）

| 字段 | 内容 |
|------|------|
| **必须完成** | `office_edit_word` → `run_builder_on_source` |
| **必须完成** | 可选 `options.backup` |

### [x] **Task WT-023** — `tests/office_mcp/word/test_schemas.py`

| 字段 | 内容 |
|------|------|
| **必须完成** | ADR-010/011/012；非法 op；`search_string` 必填 |

### [x] **Task WT-024** — `tests/office_mcp/word/test_create_word.py` / `test_edit_word.py`（OT-061）

| 字段 | 内容 |
|------|------|
| **必须完成** | mock runtime；schema 校验 |

### [x] **Task WT-025** — `tests/office_mcp/word/test_edit_builder.py`

| 字段 | 内容 |
|------|------|
| **必须完成** | `build_edit_script` 含 `GetElement` / `SearchAndReplace` |

### [x] **Task WT-026** — `tests/office_mcp/word/test_e2e_word_tools.py`（OT-064 · W2 起）

| 字段 | 内容 |
|------|------|
| **markers** | `@pytest.mark.word` `@pytest.mark.e2e` |
| **已交付** | 文件 + skip 占位（ADR-021 无 DS 时 skip） |
| **未完成** | 真实 create/read/edit 闭环 → **WT-037–042** |

### [x] **Task WT-027** — Gate **W2**（OT-061 + OT-064）

| 字段 | 内容 |
|------|------|
| **必须完成** | W2 unit 绿（mock runtime） |
| **部分完成** | E2E 仅占位；完整 Gate 见 **WT-042** |

---

## Group D — W3：merge 修复 + legacy

**Batch `T-WT-W3` — Tasks WT-028 – WT-034** · **Gate：W3**

### [x] **Task WT-028** — `word/builder/merge.py` · SaveFile ext（OT-050 · W3）

| 字段 | 内容 |
|------|------|
| **必须完成** | `SaveFile("{output_ext}", ...)` 跟 `output_path`（含 `.odt`） |
| **验收** | `test_merge_word.py` 断言 odt |

### [x] **Task WT-029** — `legacy/edit_document.py` / `merge_documents.py` / `apply_template.py`（OT-057）

| 字段 | 内容 |
|------|------|
| **必须完成** | `LEGACY_ALIASES` → 对应 word handler |
| **ADR-024** | legacy **不在** `collect_office_tools()` |

### [x] **Task WT-030** — 根 shim（OT-058 · 历史）

| 字段 | 内容 |
|------|------|
| **W3** | 根 `merge_document.py` 等 re-export |
| **M7** | **ADR-022**：根 shim **已删除**（当前树无根 merge/edit 文件） |

### [x] **Task WT-031** — `tests/office_mcp/word/test_merge_word.py`（OT-062）

| 字段 | 内容 |
|------|------|
| **必须完成** | merge 脚本 ext；mock signed URLs |

### [x] **Task WT-032** — `tests/office_mcp/word/test_legacy_compat.py`（OT-063）

| 字段 | 内容 |
|------|------|
| **必须完成** | legacy 名调用与 canonical 等价 |

### [x] **Task WT-033** — `tests/office_mcp/word/test_office_edit_document.py` / `test_office_merge_document.py` / `test_office_apply_template.py`（OT-065）

| 字段 | 内容 |
|------|------|
| **必须完成** | legacy 路径回归；import 指向 `word/` / `legacy/` |

### [x] **Task WT-034** — Gate **W3**（OT-067）

| 字段 | 内容 |
|------|------|
| **必须完成** | merge odt **unit**（`test_merge_word`）；legacy 别名 unit |
| **必须完成** | `office_read_document` docx 粗读 unit 回归 |
| **未完成** | ~~DS E2E~~ → **WT-039–041** ✅（`test_e2e_word_tools.py`） |

---

## Group E — M3：Registry + 描述 + 测试目录

**Batch `T-WT-M3` — Tasks WT-035 – WT-036** · **Gate：G1（Word 切片）** · 全局 OT-068–082

### [x] **Task WT-035** — `registry.py` Word 六模块（OT-068 · 部分）

| 字段 | 内容 |
|------|------|
| **必须完成** | `CANONICAL_MODULES` 含 word.tools.read/create/edit/merge/template/edit_script |
| **必须完成** | `LEGACY_MODULES` 含 legacy 三别名 + read_document |
| **验收** | M3：`len(collect_office_tools())==8`；`len(get_handlers())==12` |

### [x] **Task WT-036** — `[Word]` description + tests 目录（OT-081, OT-077, ADR-023）

| 字段 | 内容 |
|------|------|
| **ADR-025** | 六 canonical `TOOL_DEF["description"]` 前缀 `[Word]` |
| **ADR-023** | word 相关测试在 `tests/office_mcp/word/` |
| **必须完成** | `test_registry.py` M3 断言 **8/12**（非 23/27） |

---

## Group F — 文档（M7 同步）

**Batch `T-WT-DOC` — 映射全局 OT-004 / OT-008**

### [x] **Task WT-DOC-01** — `docs/OFFICE_MCP_WORD_UPGRADE.md`

| 字段 | 内容 |
|------|------|
| **必须完成** | §4.3 字段名与 schema 一致；§8 实施状态 |

### [x] **Task WT-DOC-02** — `docs/OFFICE_MCP_WORD_LLM_GUIDE.md`

| 字段 | 内容 |
|------|------|
| **必须完成** | `search_string` / `replace_string`；实现状态 ✅ |

### [x] **Task WT-DOC-03** — `docs/OFFICE_MCP_WORD_IMPLEMENTATION_DESIGN.md` + **本文档**

| 字段 | 内容 |
|------|------|
| **必须完成** | 设计与 tasks 互链；Gate checklist 与代码一致 |

---

## Group G — 明确禁止（WT-NA）

| ID | 禁止 | 全局 |
|----|------|------|
| **WT-NA-01** | `office_read_document` → fine read 透明转发 | OT-NA-05 |
| **WT-NA-02** | `relative_index` 字段 | OT-NA-06 / ADR-011 |
| **WT-NA-03** | `delete_block` 删表格块 | ADR-010 |
| **WT-NA-04** | M3 后在 `core/` 做 Word feature（非 bugfix） | OT-NA-09 / ADR-029 |
| **WT-NA-05** | merge 写死 `SaveFile("docx", ...)` | UPGRADE §4.4 |
| **WT-NA-06** | `search` / `replace` 作为 edit op 字段名 | 用 `search_string` / `replace_string` |

---

## Group H — UPGRADE 收尾（待完成）

**Batch `T-WT-FOLLOWUP` — Tasks WT-037 – WT-042** · [OFFICE_MCP_WORD_UPGRADE.md](./OFFICE_MCP_WORD_UPGRADE.md) §7.2

> M2–M3 架构（Group A–E）✅；本节为 **真实 E2E** 与 OT-067 诚实验收。

### [x] **Task WT-037** — `test_e2e_word_tools.py`：create → read → edit → read（docx）

| 字段 | 内容 |
|------|------|
| **必须完成** | 替换 placeholder `pytest.skip`；`.env.test` + DocumentServer |
| **必须完成** | `office_create_word` → `office_read_word` fine → `office_edit_word` → re-read |
| **验收** | `-m "word and e2e"` 至少 1 case **PASS** |
| **关联** | OT-064、OT-067；WT-026 占位补全 |

### [x] **Task WT-038** — E2E：odt 往返

| 字段 | 内容 |
|------|------|
| **必须完成** | create odt → edit → save odt（UPGRADE §7.2 用例 3） |

### [x] **Task WT-039** — E2E：`office_merge_word` → `.odt`

| 字段 | 内容 |
|------|------|
| **必须完成** | 合并两源；`output_path=*.odt`（UPGRADE §7.2 用例 5） |

### [x] **Task WT-040** — E2E：legacy 三别名 smoke

| 字段 | 内容 |
|------|------|
| **必须完成** | `office_merge_documents` / `office_apply_template` / `office_edit_document` |

### [x] **Task WT-041** — E2E：`office_read_document` docx 粗读（OT-NA-05）

| 字段 | 内容 |
|------|------|
| **必须完成** | legacy 粗读不变；无透明 fine 转发 |

### [x] **Task WT-042** — Gate **W-E2E**

| 字段 | 内容 |
|------|------|
| **必须完成** | WT-037–041 全部 `[x]`；本文档验收闸门 E2E 行改 `[x]` |

---

## Group I — Schema / Builder 对齐（待完成）

**Batch `T-WT-SCHEMA` — Tasks WT-043 – WT-045**

### [x] **Task WT-043** — `options.page_size`（`builder/create.py`）

| 字段 | 内容 |
|------|------|
| **现状** | schema + `TOOL_DEF` 有 `A4`/`Letter`；Builder **未实现** |
| **择一** | 实现页面尺寸 JS；或从 schema/`TOOL_DEF` **移除**并改 UPGRADE |

### [x] **Task WT-044** — `options.title`（`builder/create.py`）

| 字段 | 内容 |
|------|------|
| **现状** | `WordCreateOptions.title` 未写入 Builder |
| **择一** | 实现文档标题属性；或从 schema **移除** |

### [x] **Task WT-045** — `word/tools/edit.py` · `TOOL_DEF` operations schema

| 字段 | 内容 |
|------|------|
| **必须完成** | `inputSchema` 与 `edit_ops.py` 一致（`search_string`/`replace_string`、`after` 等） |

---

## Group J — v1.1 能力增强（**必做**）

**Batch `T-WT-V11` — Tasks WT-046 – WT-048** · UPGRADE §8 **W4** · **本收尾阶段必做，非 optional**

### [x] **Task WT-046** — `insert_bullets` / `insert_table` 定位

| 字段 | 内容 |
|------|------|
| **现状** | v1 仅 Push 文档末尾 |
| **目标** | `after` / `block_index` / `heading_path` 插入 |

### [x] **Task WT-047** — `search_replace` scope / 子树

| 字段 | 内容 |
|------|------|
| **现状** | 仅全文替换 |
| **目标** | 可选 `heading_path` 或 `scope` 限定范围 |

### [x] **Task WT-048** — UPGRADE **W4**（footnote / 图片 / 分节）

| 字段 | 内容 |
|------|------|
| **说明** | v1.1 必做项；按需拆 PR，但 WT-046–048 须全部完成 |

---

## Group K — 文档与命名卫生（已完成）

**Batch `T-WT-HYGIENE` — WT-049、WT-DOC-04**

### [x] **Task WT-049** — 测试文件名 vs 全局 OT-062

| 字段 | 内容 |
|------|------|
| **决策** | 更新全局 OT-062 / OT-065 描述以匹配 as-built 文件名（最小 churn） |
| **真源** | `test_merge_word.py`（OT-062）；`test_legacy_compat.py` + `test_office_*`（template/edit_script/legacy） |

### [x] **Task WT-DOC-04** — Gate / E2E 文档同步

| 字段 | 内容 |
|------|------|
| **必须完成** | IMPLEMENTATION_DESIGN §2.2 / §11.3 E2E ✅；v1.1 ✅ |
| **必须完成** | UPGRADE §8.1 E2E + v1.1 状态；全局 OT-067 脚注 |

---

## 新建文件总览

### `aiecs/tools/office_tool/word/`

| 文件 | 阶段 | WT |
|------|------|-----|
| `__init__.py` | W0 | WT-001 |
| `parser/html.py` | W0 | WT-003 |
| `parser/document.py` | W1 | WT-011 |
| `schemas/read.py` | W1 | WT-012 |
| `schemas/section_spec.py` | W2 | WT-017 |
| `schemas/edit_ops.py` | W2 | WT-018 |
| `builder/create.py` | W2 | WT-019 |
| `builder/edit.py` | W2 | WT-020 |
| `builder/merge.py` | W0/W3 | WT-004, WT-028 |
| `builder/template.py` | W0 | WT-005 |
| `tools/read.py` | W1 | WT-013 |
| `tools/create.py` | W2 | WT-021 |
| `tools/edit.py` | W2 | WT-022 |
| `tools/merge.py` | W0/W3 | WT-006 |
| `tools/template.py` | W0 | WT-007 |
| `tools/edit_script.py` | W0 | WT-008 |

### `aiecs/tools/office_tool/legacy/`（Word 相关）

| 文件 | 阶段 | WT |
|------|------|-----|
| `edit_document.py` | W3 | WT-029 |
| `merge_documents.py` | W3 | WT-029 |
| `apply_template.py` | W3 | WT-029 |

### `tests/office_mcp/word/`

| 文件 | 阶段 | WT |
|------|------|-----|
| `test_document_parser.py` | W1 | WT-014 |
| `test_read_word.py` | W1 | WT-015 |
| `test_schemas.py` | W2 | WT-023 |
| `test_create_word.py` | W2 | WT-024 |
| `test_edit_word.py` | W2 | WT-024 |
| `test_edit_builder.py` | W2 | WT-025 |
| `test_e2e_word_tools.py` | W2+ | WT-026 |
| `test_merge_word.py` | W3 | WT-031 |
| `test_legacy_compat.py` | W3 | WT-032 |
| `test_office_edit_document.py` 等 | W3 | WT-033 |

---

## WT ↔ OT 对照表

| Word Batch | WT 范围 | 全局 OT |
|------------|---------|---------|
| W0 | WT-001 – WT-010 | OT-046–047, 050(部分), 054–056, 066 |
| W1 | WT-011 – WT-016 | OT-048–051, 059–060 |
| W2 | WT-017 – WT-027 | OT-049–053, 061, 064 |
| W3 | WT-028 – WT-034 | OT-054–057, 062–065, 067 |
| M3 | WT-035 – WT-036 | OT-068, 077, 081–082 |
| DOC | WT-DOC-* | OT-004, 008 |
| **FOLLOWUP** | **WT-037 – WT-042** | OT-064, OT-067（E2E） |
| **SCHEMA** | WT-043 – WT-045 | — |
| **V11** | WT-046 – WT-048（**必做**） | UPGRADE W4 |
| **HYGIENE** | WT-049, WT-DOC-04 | OT-062 |

---

## 验收闸门（Word）

| 闸门 | 条件 | WT |
|------|------|-----|
| **W0** | 迁移无行为变更；unit 全绿 | WT-010 |
| **W1** | read fine/coarse + parser 单测 | WT-016 |
| **W2** | create/edit + schemas + unit | WT-027 |
| **W3** | merge odt unit + legacy unit | WT-034 |
| **M3** | registry 8/12；`[Word]`；`tests/word/` | WT-036 |
| **W-E2E** | DS 自动化 E2E（WT-037–041） | **WT-042** |

**命令：**

```bash
poetry run pytest tests/office_mcp/word/ -v -m "not e2e"
DOCUMENTSERVER_URL=... DOCUMENTSERVER_JWT_SECRET=... \
  poetry run pytest tests/office_mcp/word/ -v -m "word and e2e"
python3 -c "
from aiecs.tools.office_tool.registry import collect_office_tools, get_handlers
w = {'office_read_word','office_create_word','office_edit_word',
     'office_merge_word','office_apply_template_word','office_edit_word_script'}
assert w <= {t['name'] for t in collect_office_tools()}
print('OK:', len(collect_office_tools()), len(get_handlers()))
"
! rg "presentation|spreadsheet|pdf" aiecs/tools/office_tool/word/ --glob "*.py" \
  | rg "^import|^from" && echo "FAIL" || echo "OK: word isolated"
```

- [x] **W0–W3** unit 全绿
- [x] **W-E2E** word（WT-037–042；`test_e2e_word_tools.py` 真实 E2E，无 placeholder skip）
- [x] **M3** word canonical ∈ `list_tools`；legacy 名 ∉ `list_tools`
- [x] **`office_read_document`** 粗读 unit 回归（DS E2E → WT-041）
- [x] **Schema 对齐**（WT-043–045）
- [x] **v1.1**（WT-046–048；insert 定位、search_replace scope、W4 op）
- [x] **文档 Gate 诚实**（WT-DOC-04）

---

## 维护说明

**本文档** 为 [OFFICE_MCP_WORD_IMPLEMENTATION_DESIGN.md](./OFFICE_MCP_WORD_IMPLEMENTATION_DESIGN.md) 的**按文件执行清单**；与全局 [OFFICE_TOOL_IMPLEMENTATION_TASKS_BY_FILE.md](./OFFICE_TOOL_IMPLEMENTATION_TASKS_BY_FILE.md) 冲突时，以 **ADR 已采纳项** → Word 实现设计 → 全局 tasks 为准。

**建议 PR 顺序：** W0 → W1 → W2 → W3 → M3（已完成）→ **WT-037–042（E2E）** → WT-043–045（schema）→ **WT-046–048（v1.1 必做）** → WT-049 / WT-DOC-04。

**UPGRADE 收尾优先级：** WT-037–042（E2E）> WT-043–045（schema/TOOL_DEF）> **WT-046–048（v1.1 必做）** > WT-049 / WT-DOC-04。

**AI 编程 prompt（未完成 Task）：** [AI_PROMPT_OFFICE_MCP_WORD_IMPLEMENTATION.md](./AI_PROMPT_OFFICE_MCP_WORD_IMPLEMENTATION.md)（WT-037–049、WT-DOC-04；一次一个 Batch）。

**单 PR 模板：** 见 Word 实现设计 [附录 A](./OFFICE_MCP_WORD_IMPLEMENTATION_DESIGN.md#附录-a单-pr-回归模板word-_touch)。
