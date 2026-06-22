# Office Tool 架构重组 — 按文件必选任务（M0–M7）

**用途：** 落地 [implementation_design.md](./implementation_design.md) 时，将 Office MCP 从扁平 **6 工具 / 14 文件** 迁移为 **core + 4 vertical + legacy/gateway + registry（23 canonical / 27 handlers）** 的**逐文件**执行清单。

**对齐（设计真源，实现前必读）：**

| 文档 | 角色 |
|------|------|
| [implementation_design.md](./implementation_design.md) | 全局 How、Release Gate、工具表 §12 |
| [OFFICE_TOOL_ARCHITECTURE_REORG.md](./OFFICE_TOOL_ARCHITECTURE_REORG.md) | Why/What、目录树、依赖约束 |
| [ADR.md](./ADR.md) | 已采纳决策 ADR-001～030 |
| [OFFICE_MCP_WORD_IMPLEMENTATION_DESIGN.md](./OFFICE_MCP_WORD_IMPLEMENTATION_DESIGN.md) | M2 W0–W3 细节 |
| [OFFICE_MCP_PRESENTATION_IMPLEMENTATION_DESIGN.md](./OFFICE_MCP_PRESENTATION_IMPLEMENTATION_DESIGN.md) | M4 P0–P4 细节 |
| [OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_DESIGN.md](./OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_DESIGN.md) | M5 S0–S4 细节 |
| [OFFICE_MCP_PDF_IMPLEMENTATION_DESIGN.md](./OFFICE_MCP_PDF_IMPLEMENTATION_DESIGN.md) | M6 P0–P5 细节 |
| [AI_PROMPT_OFFICE_TOOL_IMPLEMENTATION.md](./AI_PROMPT_OFFICE_TOOL_IMPLEMENTATION.md) | Agent Batch 执行序 |
| 各类 [OFFICE_MCP_*_UPGRADE.md](./OFFICE_MCP_WORD_UPGRADE.md) / [OFFICE_MCP_*_LLM_GUIDE.md](./OFFICE_MCP_WORD_LLM_GUIDE.md) | 工具参数与 LLM 示例 |

> **勿**以 [`docs/archive/`](./archive/README.md) 为实施真源。

**Preconditions**

- 现有 `poetry run pytest tests/office_mcp/ -v -m "not e2e"` 全绿。
- `DOCUMENTSERVER_URL` / JWT / storage 配置与现 E2E 一致（E2E 见 **ADR-021**）。
- **M3 合并前**不得并行改 `core/` 与 vertical 大 PR（**ADR-029** freeze 自 M3 起）。

**任务编号：** **OT-001 … OT-141**（按里程碑分组；同文件多 Task 表示分步验收）。

**路径约定：** Python 相对仓库根 `aiecs/`、`tests/`；文档相对 `docs/`。

**完成定义：** **`[ ]` → `[x]`** = 本 Task 在对应里程碑 PR 中落地并满足「必须完成」列。

**遵循的方法（全局）：**

| 方法 | 来源 | 要求 |
|------|------|------|
| `run_builder_script` | ADR-009 | create / merge / template（无源） |
| `run_builder_on_source` | ADR-009 | edit / fill_form / edit_script |
| `build_read_response` | ADR-028 | 全部 `office_read_*` fine/coarse |
| `core/errors.err` / `ok` | ADR-006 | 全部 handler 返回 |
| Pydantic v2 `model_validate` | ADR-002 | 全部 `*/schemas/*` + tools 入口 |
| Registry **递增** | ADR-024 / §5.2 | **勿在 M3 断言 23/27**；见下表 |
| Description `[Category]` | ADR-025 | M3 起已注册 canonical；legacy **无** `[Legacy]` |
| `office_read_document` 行为冻结 | implementation_design §11.2 | 不得透明改 fine read |
| pytest `--strict-markers` | pyproject.toml | category marker **须先于** `@pytest.mark.*` 注册（OT-045c/092/107/123） |

**Registry 递增注册（真源：[implementation_design.md §5.2](./implementation_design.md)）**：

| 里程碑 | `collect_office_tools()` | `get_handlers()` |
|--------|--------------------------|------------------|
| **M3** | **8** | **12** |
| M4 | 13 | 17 |
| M5 | 18 | 22 |
| **M6** | **23** | **27** |

---

## 里程碑定位

| 阶段 | Gate | 交付摘要 |
|------|------|----------|
| **M0** | G0（部分） | `core/builder_runtime` + `builder_js`；根文件改调 runtime |
| **M1** | **G0** | core 迁移、shim、errors、read_response、coarse_read |
| **M2** | G1（部分） | `word/` W0–W3 |
| **M3** | **G1** | `registry.py`、adapter 瘦身、word tests 搬迁 |
| **M4** | **G2** | `presentation/` 五工具 |
| **M5** | **G3** | `spreadsheet/` 五工具 |
| **M6** | **G4** | `pdf/` 五工具（无 apply_template） |
| **M7** | **G5** | ✅ README / Plan / LLM 指南 / health 一致 |

> **代码状态（2026-06）**：M0–M7 已落地；OT-013–OT-133 与 OT-135–OT-141 已勾选完成。OT-134（`tests/office_mcp/gateway/` 子目录）仍为可选 `[ ]`。

**并行：** M4 / M5 / M6 可在 **M3 完成后**并行；均依赖 M0–M1。

---

## 当前树核对摘要（M7 后 · 2026-06）

| 查证项 | 结论 |
|--------|------|
| `aiecs/tools/office_tool/` | `core/`、`gateway/`、`word/`、`presentation/`、`spreadsheet/`、`pdf/`、`legacy/`、`registry.py`；**根 shim 已删除**（ADR-022） |
| MCP 工具 | **23 canonical** / **27 handlers**（registry） |
| `office_tool_adapter.py` | 委托 `registry`；异常经 `sanitize_error_message` |
| `main_mcp.py` health | `tool_count` / `canonical_count` == 23；`registered_handler_count` == 27 |
| `tests/office_mcp/` | `core/`、`word/`、`presentation/`、`spreadsheet/`、`pdf/` 子目录；gateway/legacy 测试仍为扁平（OT-134 可选） |
| `pyproject.toml` markers | `word` / `presentation` / `spreadsheet` / `pdf` 已注册 |

---

## Group A — 设计文档（只读真源 + M7 同步）

**Batch `T-OT-DOC` — Tasks OT-001 – OT-012**

### [x] **Task OT-001** — `docs/implementation_design.md`

| 字段 | 内容 |
|------|------|
| **角色** | 全局实现设计真源 |
| **M7 必须完成** | §2.2 Gate 全部 `[x]`；§9 M0–M7 checklist 与代码一致 |
| **必须完成** | 链到本文档（tasks by file） |

### [x] **Task OT-002** — `docs/OFFICE_TOOL_ARCHITECTURE_REORG.md`

| 字段 | 内容 |
|------|------|
| **角色** | 架构 Why/What |
| **M7 必须完成** | §7.1–7.4 实现状态表；工具矩阵与 §12 一致 |

### [x] **Task OT-003** — `docs/ADR.md`

| 字段 | 内容 |
|------|------|
| **角色** | ADR-001～030 |
| **实现约束** | 代码须与「已采纳」决策一致；冲突时 **先改 ADR 再改代码** |

### [x] **Task OT-004** — `docs/OFFICE_MCP_WORD_UPGRADE.md` + `OFFICE_MCP_WORD_IMPLEMENTATION_DESIGN.md`

| 字段 | 内容 |
|------|------|
| **M2 遵循** | W0–W3、block schema、edit ops、ADR-010/011/012 |
| **M7 必须完成** | UPGRADE §8 实施状态；LLM 指南链接有效 |

### [x] **Task OT-005** — `docs/OFFICE_MCP_PRESENTATION_UPGRADE.md` + `OFFICE_MCP_PRESENTATION_IMPLEMENTATION_DESIGN.md`

| 字段 | 内容 |
|------|------|
| **M4 遵循** | SlidesToJSON、layouts[]、ADR-016 |
| **M7** | 实施状态表 |

### [x] **Task OT-006** — `docs/OFFICE_MCP_SPREADSHEET_UPGRADE.md` + `OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_DESIGN.md`

| 字段 | 内容 |
|------|------|
| **M5 遵循** | GetSheetsCount sidecar、A1/range、ADR-013/014/015 |
| **M7** | 实施状态表 |

### [x] **Task OT-007** — `docs/OFFICE_MCP_PDF_UPGRADE.md` + `OFFICE_MCP_PDF_IMPLEMENTATION_DESIGN.md`

| 字段 | 内容 |
|------|------|
| **M6 遵循** | pages_txt、create_mode、merge engine、fill_form、ADR-017～020/030 |
| **M7** | 实施状态表 |

### [x] **Task OT-008** — `docs/OFFICE_MCP_WORD_LLM_GUIDE.md`

| 字段 | 内容 |
|------|------|
| **M7 必须完成** | 工具名、`block_index`/`heading_path`；**无** `relative_index`（ADR-011） |

### [x] **Task OT-009** — `docs/OFFICE_MCP_PRESENTATION_LLM_GUIDE.md`

| 字段 | 内容 |
|------|------|
| **M7 必须完成** | `slide_index`/`shape_index`；layout 精确枚举（ADR-016） |

### [x] **Task OT-010** — `docs/OFFICE_MCP_SPREADSHEET_LLM_GUIDE.md`

| 字段 | 内容 |
|------|------|
| **M7 必须完成** | `sheet` + A1/`range`；**无** row/col 主推（ADR-015） |

### [x] **Task OT-011** — `docs/OFFICE_MCP_PDF_LLM_GUIDE.md`

| 字段 | 内容 |
|------|------|
| **M7 必须完成** | create_mode 显式切换；表单仅 `office_fill_pdf_form`（ADR-030） |

### [x] **Task OT-012** — `docs/LEGACY_TOOL_MIGRATION.md`

| 字段 | 内容 |
|------|------|
| **M3 必须完成** | 发布；legacy 四工具 → canonical 对照（ADR-024） |
| **M7** | 与 registry §12 一致 |

---

## Group B — M0：Core Builder Runtime

**Batch `T-OT-M0` — Tasks OT-013 – OT-022** · **Gate：G0 部分**

### [x] **Task OT-013** — `aiecs/tools/office_tool/core/__init__.py`（新建）

| 字段 | 内容 |
|------|------|
| **必须完成** | 包初始化；导出 `builder_runtime`、`builder_js` public API |

### [x] **Task OT-014** — `aiecs/tools/office_tool/core/builder_js.py`（新建）

| 字段 | 内容 |
|------|------|
| **必须完成** | `escape_js`, `open_file`, `save_file`, `close_file`, `wrap_script`（implementation_design §4.2） |
| **设计** | 自 `edit_document._escape_js` 等迁入 |

### [x] **Task OT-015** — `aiecs/tools/office_tool/core/builder_runtime.py`（新建）

| 字段 | 内容 |
|------|------|
| **必须完成** | `run_builder_script`, `run_builder_on_source`（§4.3） |
| **必须完成** | 成功 `{success, output_path?}` / 失败 `{isError, text}`（ADR-006） |
| **依赖** | `docbuilder_script.script_to_url`, `storage.upload_to_storage`, DS client |

### [x] **Task OT-016** — `aiecs/tools/office_tool/edit_document.py`（改）

| 字段 | 内容 |
|------|------|
| **必须完成** | 改为调用 `run_builder_on_source`；**行为等价** |
| **禁止** | 改 MCP schema / 工具名 |

### [x] **Task OT-017** — `aiecs/tools/office_tool/merge_document.py`（改）

| 字段 | 内容 |
|------|------|
| **必须完成** | 脚本生成保留；执行改 `run_builder_script` |

### [x] **Task OT-018** — `aiecs/tools/office_tool/apply_template.py`（改）

| 字段 | 内容 |
|------|------|
| **必须完成** | 执行改 `run_builder_script` |

### [x] **Task OT-019** — `aiecs/tools/office_tool/execute_builder.py`（改）

| 字段 | 内容 |
|------|------|
| **必须完成** | 执行改 `run_builder_script` |

### [x] **Task OT-020** — `tests/office_mcp/core/test_builder_runtime.py`（新建）

| 字段 | 内容 |
|------|------|
| **必须完成** | mock DS + storage；`run_builder_script` / `run_builder_on_source`  happy path + error |
| **验收** | `pytest tests/office_mcp/core/ -v` |

### [x] **Task OT-021** — 回归：`tests/office_mcp/test_office_*.py`

| 字段 | 内容 |
|------|------|
| **必须完成** | M0 PR：`pytest tests/office_mcp/ -m "not e2e"` 全绿 |
| **禁止** | 行为回归（edit/merge/template/execute_builder） |

### [x] **Task OT-022** — `aiecs/tools/office_tool/read_document.py` / `call_api.py`

| 字段 | 内容 |
|------|------|
| **M0** | **不改**（M1 再迁） |
| **验收** | M0 仍 pass |

---

## Group C — M1：Core 迁移 + Shims + Read 基础设施

**Batch `T-OT-M1` — Tasks OT-023 – OT-045c** · **Gate：G0 完整**

### [x] **Task OT-023** — `aiecs/tools/office_tool/core/categories.py`（新建）

| 字段 | 内容 |
|------|------|
| **必须完成** | 自 `conversion_output.py` 迁入并扩展（§4.1）：`classify_file_ext`, `llm_coarse_output_type`, `builder_file_ext`, `assert_category_path` |
| **ADR** | 四类 `*_EXTENSIONS` frozenset |

### [x] **Task OT-024** — `aiecs/tools/office_tool/conversion_output.py`（改 shim）

| 字段 | 内容 |
|------|------|
| **必须完成** | re-export `core.categories`；`# deprecated: use core.categories` |
| **ADR-022** | M7 **不删** shim |

### [x] **Task OT-025** — `aiecs/tools/office_tool/core/errors.py`（新建）

| 字段 | 内容 |
|------|------|
| **必须完成** | `err(text)`, `ok(**kwargs)`（ADR-006） |

### [x] **Task OT-026** — `aiecs/tools/office_tool/core/read_response.py`（新建）

| 字段 | 内容 |
|------|------|
| **必须完成** | `build_read_response(...)`（§6.1, ADR-028） |
| **必须完成** | mirror：`blocks`/`slides`/`sheets`/`pages` + `slide_count`/`page_count` |

### [x] **Task OT-027** — `aiecs/tools/office_tool/core/builder_json_sidecar.py`（新建）

| 字段 | 内容 |
|------|------|
| **必须完成** | `SIDECAR_FILENAME`, `build_sidecar_extract_script`, `read_sidecar_json`（§4.4） |

### [x] **Task OT-028** — `aiecs/tools/office_tool/core/coarse_read.py`（新建）

| 字段 | 内容 |
|------|------|
| **必须完成** | `convert_and_fetch`, `coarse_read_legacy`（§4.5） |
| **必须完成** | 从 `read_document.py` 抽 Conversion 逻辑 |

### [x] **Task OT-029** — `aiecs/tools/office_tool/core/source.py`（新建）

| 字段 | 内容 |
|------|------|
| **必须完成** | 自 `source_resolver.py` 移动；保留 `resolve_document_source` |

### [x] **Task OT-030** — `aiecs/tools/office_tool/source_resolver.py`（改 shim）

| 字段 | 内容 |
|------|------|
| **必须完成** | `from core.source import *` |

### [x] **Task OT-031** — `aiecs/tools/office_tool/core/storage/paths.py`（新建）

| 字段 | 内容 |
|------|------|
| **必须完成** | 自 `storage_paths.py` 移动 |

### [x] **Task OT-032** — `aiecs/tools/office_tool/core/storage/backend.py`（新建）

| 字段 | 内容 |
|------|------|
| **必须完成** | 自 `storage.py` 移动：`upload_to_storage`, `copy_storage_file`, `get_file_ext`, 等 |

### [x] **Task OT-033** — `aiecs/tools/office_tool/core/storage/object_fetch.py`（新建）

| 字段 | 内容 |
|------|------|
| **必须完成** | 自 `object_fetch.py` 移动 |

### [x] **Task OT-034** — `aiecs/tools/office_tool/core/storage/__init__.py`（新建）

| 字段 | 内容 |
|------|------|
| **必须完成** | 聚合 storage public API |

### [x] **Task OT-035** — `aiecs/tools/office_tool/storage.py` / `storage_paths.py` / `object_fetch.py`（改 shim）

| 字段 | 内容 |
|------|------|
| **必须完成** | re-export `core.storage.*` |

### [x] **Task OT-036** — `aiecs/tools/office_tool/core/docbuilder_script.py`（新建）

| 字段 | 内容 |
|------|------|
| **必须完成** | 自 `docbuilder_script.py` 移动：`script_to_url`, `get_script` |

### [x] **Task OT-037** — `aiecs/tools/office_tool/docbuilder_script.py`（改 shim）

| 字段 | 内容 |
|------|------|
| **必须完成** | re-export |

### [x] **Task OT-038** — `aiecs/tools/office_tool/legacy/read_document.py`（新建）

| 字段 | 内容 |
|------|------|
| **必须完成** | 自 `read_document.py` 迁入；调用 `coarse_read_legacy` |
| **必须完成** | **行为冻结**（§11.2）：html/txt/csv 粗读不变 |

### [x] **Task OT-039** — `aiecs/tools/office_tool/read_document.py`（改 shim）

| 字段 | 内容 |
|------|------|
| **必须完成** | re-export `legacy.read_document` 或 thin forward |

### [x] **Task OT-040** — `tests/office_mcp/core/test_categories.py`（新建）

| 字段 | 内容 |
|------|------|
| **必须完成** | docx/pptx/xlsx/pdf/unknown 分类 |

### [x] **Task OT-041** — `tests/office_mcp/core/test_read_response.py`（新建）

| 字段 | 内容 |
|------|------|
| **必须完成** | 四类 category alias mirror |

### [x] **Task OT-042** — `tests/office_mcp/core/test_storage.py`（新建）

| 字段 | 内容 |
|------|------|
| **必须完成** | 自 `test_office_storage*.py` 迁路径或 re-import smoke |

### [x] **Task OT-043** — `tests/office_mcp/test_office_read_document*.py`（改）

| 字段 | 内容 |
|------|------|
| **必须完成** | import 路径更新；**断言不变** |

### [x] **Task OT-044** — `aiecs/main_mcp.py`（M1 可选）

| 字段 | 内容 |
|------|------|
| **允许 N/A(M1)** | docbuilder/object_fetch import 可仍走 shim |
| **M3 必须完成** | health 见 OT-078 |

### [x] **Task OT-045** — M1 验收

| 字段 | 内容 |
|------|------|
| **必须完成** | `pytest tests/office_mcp/ -m "not e2e"` 全绿 |
| **Gate** | **G0** |

### [x] **Task OT-045b** — `tests/office_mcp/conftest.py` + `probe_ds_capabilities.py` 骨架（M1/M3）

| 字段 | 内容 |
|------|------|
| **必须完成** | 无 `DOCUMENTSERVER_URL` 时 `-m e2e` **skip**（不 fail，**ADR-021**） |
| **必须完成** | `probe_ds_capabilities.py` **占位**（session 缓存结构；M5/M6 前补 GetSheetsCount / PDF native） |
| **说明** | 完整探针逻辑可在 M7（OT-133）补文档；M5 OT-111 / M6 依赖此骨架 |

### [x] **Task OT-045c** — `pyproject.toml`（M1 · `word` marker）

| 字段 | 内容 |
|------|------|
| **必须完成** | 在 `pyproject.toml` `[tool.pytest.ini_options] markers` 追加 **`word: word category tools`** |
| **原因** | 仓库 **`--strict-markers`**；M2 E2E（OT-064/067）使用 `@pytest.mark.word`，**须 M1 注册** |
| **禁止** | M7 才一次性注册全部 category markers（presentation/spreadsheet/pdf 随 M4/M5/M6 追加，见 OT-092/107/123） |

---

## Group D — M2：Word 垂直（W0–W3）

**Batch `T-OT-M2` — Tasks OT-046 – OT-067** · **Gate：G1 部分** · 细节见 [OFFICE_MCP_WORD_IMPLEMENTATION_DESIGN.md](./OFFICE_MCP_WORD_IMPLEMENTATION_DESIGN.md)

### [x] **Task OT-046** — `aiecs/tools/office_tool/word/__init__.py`（新建）

### [x] **Task OT-047** — `word/parser/html.py`（新建，W0）

| 字段 | 内容 |
|------|------|
| **必须完成** | 自 `html_parser.py` 迁入 `parse_html_to_structure` 等 |
| **shim** | `html_parser.py` re-export |

### [x] **Task OT-048** — `word/parser/document.py`（新建，W1）

| 字段 | 内容 |
|------|------|
| **必须完成** | `parse_document_json`, `blocks_to_outline`, `blocks_to_text` |
| **sidecar** | ToJSON extract_body 片段 |

### [x] **Task OT-049** — `word/schemas/read.py` / `section_spec.py` / `edit_ops.py`（新建，W2）

| 字段 | 内容 |
|------|------|
| **必须完成** | Pydantic v2（ADR-002） |
| **ADR** | 010 delete_block；011 无 relative_index；012 add_toc 文首 |

### [x] **Task OT-050** — `word/builder/create.py` / `edit.py` / `merge.py` / `template.py`（新建）

| 字段 | 内容 |
|------|------|
| **W0** | merge/template 自根文件迁入脚本生成 |
| **W2/W3** | create/edit 完整 |
| **W3** | merge `SaveFile` 跟 `output_path` ext |

### [x] **Task OT-051** — `word/tools/read.py`（新建，W1）

| 字段 | 内容 |
|------|------|
| **必须完成** | `office_read_word`；fine/coarse；`build_read_response` |
| **导出** | `TOOL_NAME`, `TOOL_DEF`, `handler` |

### [x] **Task OT-052** — `word/tools/create.py`（新建，W2）

| 字段 | 内容 |
|------|------|
| **必须完成** | `office_create_word` → `run_builder_script` |

### [x] **Task OT-053** — `word/tools/edit.py`（新建，W2）

| 字段 | 内容 |
|------|------|
| **必须完成** | `office_edit_word` → `run_builder_on_source` |

### [x] **Task OT-054** — `word/tools/merge.py`（新建，W3）

| 字段 | 内容 |
|------|------|
| **必须完成** | `office_merge_word` |

### [x] **Task OT-055** — `word/tools/template.py`（新建，W3）

| 字段 | 内容 |
|------|------|
| **必须完成** | `office_apply_template_word` |

### [x] **Task OT-056** — `word/tools/edit_script.py`（新建，W3）

| 字段 | 内容 |
|------|------|
| **必须完成** | 自 `edit_document.py` 迁入；`office_edit_word_script` |

### [x] **Task OT-057** — `legacy/edit_document.py` / `merge_documents.py` / `apply_template.py`（新建，W3）

| 字段 | 内容 |
|------|------|
| **必须完成** | `LEGACY_ALIASES` → word handlers |
| **shim** | 根 `edit_document.py` 等 re-export |

### [x] **Task OT-058** — 根 `merge_document.py` / `apply_template.py` / `edit_document.py`（W3 shim）

| 字段 | 内容 |
|------|------|
| **必须完成** | re-export 或删逻辑留 shim（ADR-022：M7 保留） |

### [x] **Task OT-059** — `tests/office_mcp/word/test_document_parser.py`（新建，W1）

### [x] **Task OT-060** — `tests/office_mcp/word/test_read_word.py`（新建，W1）

### [x] **Task OT-061** — `tests/office_mcp/word/test_create_word.py` / `test_edit_word.py`（新建，W2）

### [x] **Task OT-062** — `tests/office_mcp/word/test_merge_word.py` / `test_apply_template_word.py` / `test_edit_word_script.py`（新建，W3）

### [x] **Task OT-063** — `tests/office_mcp/word/test_legacy_compat.py`（新建，W3）

### [x] **Task OT-064** — `tests/office_mcp/word/test_e2e_word_tools.py`（新建，W2+）

| 字段 | 内容 |
|------|------|
| **markers** | `@pytest.mark.word` `@pytest.mark.e2e` |

### [x] **Task OT-065** — `tests/office_mcp/test_office_edit_document.py` 等（改，W3）

| 字段 | 内容 |
|------|------|
| **必须完成** | import 更新；legacy 行为等价 |

### [x] **Task OT-066** — W0 验收

| 字段 | 内容 |
|------|------|
| **必须完成** | 目录迁移；**无行为变更**；全量 unit 绿 |

### [x] **Task OT-067** — W1–W3 E2E 验收

| 字段 | 内容 |
|------|------|
| **必须完成** | create→read→edit→read（docx/odt）；merge odt 输出 |

---

## Group E — M3：Registry + Adapter + Platform

**Batch `T-OT-M3` — Tasks OT-068 – OT-082** · **Gate：G1 完整**

### [x] **Task OT-068** — `aiecs/tools/office_tool/registry.py`（新建）

| 字段 | 内容 |
|------|------|
| **必须完成** | `OFFICE_TOOL_MODULES`, `collect_office_tools`, `get_handlers`, `tool_count`, `canonical_count`（§5.2） |
| **ADR-024** | M3：**8/12**；M6 终态 **23/27** |
| **M3 注册** | gateway×2 + word×6 canonical；legacy×4 仅 handlers |

### [x] **Task OT-069** — `aiecs/mcp/office_tool_adapter.py`（改）

| 字段 | 内容 |
|------|------|
| **必须完成** | `from registry import collect_office_tools, get_handlers` |
| **禁止** | 硬编码 `OFFICE_TOOLS` / `_TOOL_HANDLERS` |
| **ADR-025** | 依赖 registry 侧 description 前缀 |

### [x] **Task OT-070** — `aiecs/tools/office_tool/gateway/execute_builder.py`（新建）

| 字段 | 内容 |
|------|------|
| **必须完成** | 自根 `execute_builder.py` 迁入 |
| **时机** | **M3** registry PR（**M0** 可选提前迁目录 + shim，见 implementation_design §7.5） |

### [x] **Task OT-071** — `aiecs/tools/office_tool/gateway/call_api.py`（新建）

| 字段 | 内容 |
|------|------|
| **必须完成** | 自根 `call_api.py` 迁入 |
| **时机** | 同 OT-070 |

### [x] **Task OT-072** — 根 `execute_builder.py` / `call_api.py`（改 shim）

### [x] **Task OT-073** — `aiecs/tools/office_tool/__init__.py`（改）

| 字段 | 内容 |
|------|------|
| **必须完成** | 导出策略：保留 legacy 六工具 re-export 或文档化 deprecated |

### [x] **Task OT-074** — `tests/office_mcp/test_registry.py`（新建）

| 字段 | 内容 |
|------|------|
| **必须完成** | **按里程碑断言**（见文首 Registry 表）：M3 **8/12**；M4 13/17；M5 18/22；M6 **23/27** |
| **禁止** | M3 PR 写死 `== 23` / `== 27` |

### [x] **Task OT-075** — `tests/office_mcp/test_office_tool_adapter.py`（改）

| 字段 | 内容 |
|------|------|
| **必须完成** | list_tools 不含 legacy 名 |
| **必须完成** | **OT-138 子集**：工具数量与当前 milestone registry 一致（**M3=8**） |

### [x] **Task OT-076** — `tests/office_mcp/test_integration.py`（改）

| 字段 | 内容 |
|------|------|
| **必须完成** | tool 列表断言更新 |
| **必须完成** | **OT-138 子集**：与 registry canonical 计数一致（**M3=8**） |

### [x] **Task OT-077** — `tests/office_mcp/test_office_*.py` → `tests/office_mcp/word/`（搬迁，ADR-023）

| 字段 | 内容 |
|------|------|
| **必须完成** | word 相关 flat 测试迁入 `word/` 或标记 deprecated path |

### [x] **Task OT-078** — `aiecs/main_mcp.py`（改）

| 字段 | 内容 |
|------|------|
| **必须完成** | health 增加 `canonical_count`（**ADR-026**）；`tool_count` = 当前 `len(list_tools())`（**M3=8**，M6=23） |
| **必须完成** | 可选 `registered_handler_count`（**M3=12**，M6=27） |

### [x] **Task OT-079** — `docs/LEGACY_TOOL_MIGRATION.md`（完成 OT-012）

### [x] **Task OT-080** — CHANGELOG（新建或更新）

| 字段 | 内容 |
|------|------|
| **必须完成** | ADR-024 list_tools 变更条目 |

### [x] **Task OT-081** — Word 工具 `[Word]` description（ADR-025）

| 字段 | 内容 |
|------|------|
| **必须完成** | 6 个 word canonical `TOOL_DEF["description"]` 前缀 |

### [x] **Task OT-082** — M3 验收 · **Gate G1**

| 字段 | 内容 |
|------|------|
| **必须完成** | registry + adapter + word E2E 绿 |
| **必须完成** | **OT-138 子集**（OT-075/076）：集成测试断言 **8** canonical |
| **ADR-029** | 自本 PR 合并起 **core/ freeze** |

---

## Group F — M4：Presentation 垂直

**Batch `T-OT-M4` — Tasks OT-083 – OT-099** · **Gate：G2** · [OFFICE_MCP_PRESENTATION_IMPLEMENTATION_DESIGN.md](./OFFICE_MCP_PRESENTATION_IMPLEMENTATION_DESIGN.md)

### [x] **Task OT-083** — `presentation/__init__.py` + 目录树（P0）

### [x] **Task OT-084** — `presentation/parser/txt.py`（P0）

| 字段 | 内容 |
|------|------|
| **必须完成** | 自 `html_parser.parse_txt_*` 迁入（coarse） |

### [x] **Task OT-085** — `presentation/parser/slides.py`（P0–P1）

| 字段 | 内容 |
|------|------|
| **必须完成** | `parse_slides_json` → slides[] + layouts[]（ADR-016） |
| **sidecar** | SlidesToJSON extract_body |

### [x] **Task OT-086** — `presentation/schemas/read.py` / `slide_spec.py` / `edit_ops.py`（P1）

### [x] **Task OT-087** — `presentation/builder/create.py` / `edit.py` / `merge.py` / `template.py`（P1–P2）

| 字段 | 内容 |
|------|------|
| **ADR-009** | create/merge/template → `run_builder_script`；edit → `run_builder_on_source` |
| **禁止** | `Api.GetDocument()` Word API |

### [x] **Task OT-088** — `presentation/tools/read.py`（P0）

| 字段 | 内容 |
|------|------|
| **必须完成** | `office_read_presentation`；`extra={"layouts": ...}` |

### [x] **Task OT-089** — `presentation/tools/create.py` / `edit.py`（P1）

### [x] **Task OT-090** — `presentation/tools/merge.py` / `template.py`（P2）

| 字段 | 内容 |
|------|------|
| **工具名** | `office_merge_presentations`, `office_apply_template_presentation` |

### [x] **Task OT-091** — `registry.py`（改）

| 字段 | 内容 |
|------|------|
| **必须完成** | 追加 presentation 五模块；**M4 后 canonical=13** |

### [x] **Task OT-092** — `[Presentation]` description 前缀（5 工具）

| 字段 | 内容 |
|------|------|
| **必须完成** | 5 个 presentation canonical `TOOL_DEF["description"]` 前缀 |
| **必须完成** | **`pyproject.toml` 注册 `presentation` marker**（**strict-markers**；M4 E2E 前置） |

### [x] **Task OT-093** — `tests/office_mcp/presentation/test_slides_parser.py` 等（全套，§10.1）

### [x] **Task OT-094** — `tests/office_mcp/presentation/fixtures/layouts_pptx.json` / `layouts_odp.json`（P4，ADR-016）

### [x] **Task OT-095** — `tests/office_mcp/presentation/test_e2e_presentation_tools.py`

### [x] **Task OT-096** — legacy pptx txt 回归

| 字段 | 内容 |
|------|------|
| **必须完成** | `office_read_document` pptx 行为不变 |

### [x] **Task OT-097** — `tests/office_mcp/presentation/test_schemas.py`（P1）

| 字段 | 内容 |
|------|------|
| **必须完成** | layout 枚举校验；非法 slide_index（ADR-016） |

### [x] **Task OT-098** — `[Presentation]` description 与 registry **M4=13/17** 复核

| 字段 | 内容 |
|------|------|
| **必须完成** | OT-091/092 与 `test_registry` 一致 |
| **必须完成** | **OT-138 子集**：`test_openai_format` / `test_fastmcp_integration` 断言 **13** canonical |

### [x] **Task OT-099** — M4 E2E 验收 · **Gate G2**

---

## Group G — M5：Spreadsheet 垂直

**Batch `T-OT-M5` — Tasks OT-100 – OT-112** · **Gate：G3** · [OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_DESIGN.md](./OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_DESIGN.md)

### [x] **Task OT-100** — `spreadsheet/__init__.py` + 目录树（S0）

### [x] **Task OT-101** — `spreadsheet/parser/csv.py`（S0）

| 字段 | 内容 |
|------|------|
| **必须完成** | 自 `html_parser.parse_csv_*` 迁入 |

### [x] **Task OT-102** — `spreadsheet/parser/workbook.py`（S1）

| 字段 | 内容 |
|------|------|
| **必须完成** | sidecar GetSheetsCount + for（ADR-013）；`parse_workbook_json` |

### [x] **Task OT-103** — `spreadsheet/schemas/read.py` / `workbook_spec.py` / `edit_ops.py`（S2–S3）

| 字段 | 内容 |
|------|------|
| **ADR-015** | A1/range；无 row/col 对外 |

### [x] **Task OT-104** — `spreadsheet/builder/create.py` / `edit.py` / `merge.py` / `template.py`（S2–S4）

| 字段 | 内容 |
|------|------|
| **ADR-014** | template 显式 `Sheet!A1` + used_range `{{key}}` |

### [x] **Task OT-105** — `spreadsheet/tools/read.py` / `create.py` / `edit.py` / `merge.py` / `template.py`（S0–S4）

### [x] **Task OT-106** — `registry.py`（改）：spreadsheet 五模块；**M5 后 canonical=18**（23 在 M6）

### [x] **Task OT-107** — `[Spreadsheet]` description 前缀（5 工具）

| 字段 | 内容 |
|------|------|
| **必须完成** | 5 个 spreadsheet canonical `TOOL_DEF["description"]` 前缀 |
| **必须完成** | **`pyproject.toml` 注册 `spreadsheet` marker**（**strict-markers**；M5 E2E 前置） |

### [x] **Task OT-108** — `tests/office_mcp/spreadsheet/test_workbook_parser.py` 等（全套）

### [x] **Task OT-109** — `tests/office_mcp/spreadsheet/test_e2e_spreadsheet_tools.py`

### [x] **Task OT-110** — legacy xlsx csv 回归

### [x] **Task OT-111** — DS 探针：GetSheetsCount skip（ADR-021，依赖 OT-045b 骨架）

### [x] **Task OT-112** — M5 E2E 验收 · **Gate G3**

| 字段 | 内容 |
|------|------|
| **必须完成** | spreadsheet E2E 绿（或 ADR-021 skip） |
| **必须完成** | **OT-138 子集**：集成测试断言 **18** canonical |

---

## Group H — M6：PDF 垂直

**Batch `T-OT-M6` — Tasks OT-113 – OT-126** · **Gate：G4** · [OFFICE_MCP_PDF_IMPLEMENTATION_DESIGN.md](./OFFICE_MCP_PDF_IMPLEMENTATION_DESIGN.md)

### [x] **Task OT-113** — `pdf/__init__.py` + 目录树（P0）

### [x] **Task OT-114** — `pdf/parser/pages_txt.py`（P0）

| 字段 | 内容 |
|------|------|
| **必须完成** | ADR-020：`\f` → `--- page N ---` → 单页 + `_note` |

### [x] **Task OT-115** — `pdf/parser/document.py`（P1）

| 字段 | 内容 |
|------|------|
| **必须完成** | fine read sidecar → pages[] / blocks[] / form_fields[] |

### [x] **Task OT-116** — `pdf/schemas/read.py` / `page_spec.py` / `edit_ops.py` / `fill_form.py`（P3–P4）

| 字段 | 内容 |
|------|------|
| **ADR-030** | edit_ops **无** `fill_form_field` |

### [x] **Task OT-117** — `pdf/builder/create.py`（P3）

| 字段 | 内容 |
|------|------|
| **ADR-017** | native / via_docx；**不** auto fallback |

### [x] **Task OT-118** — `pdf/builder/edit.py`（P3）

### [x] **Task OT-119** — `pdf/builder/merge.py`（P2）

| 字段 | 内容 |
|------|------|
| **ADR-018** | builder 默认 + `options.engine=conversion` 显式 |

### [x] **Task OT-120** — `pdf/builder/fill_form.py`（P4）

| 字段 | 内容 |
|------|------|
| **ADR-019** | 逐字段 SetValue |

### [x] **Task OT-121** — `pdf/tools/read.py` / `create.py` / `edit.py` / `merge.py` / `fill_form.py`（P0–P4）

| 字段 | 内容 |
|------|------|
| **禁止** | `office_apply_template_pdf` |

### [x] **Task OT-122** — `registry.py`（改）：pdf 五模块；**M6 后 canonical=23**（handlers=27）；确认列表完整

### [x] **Task OT-123** — `[PDF]` description 前缀（5 工具）

| 字段 | 内容 |
|------|------|
| **必须完成** | 5 个 pdf canonical `TOOL_DEF["description"]` 前缀 |
| **必须完成** | **`pyproject.toml` 注册 `pdf` marker**（**strict-markers**；M6 E2E 前置） |

### [x] **Task OT-124** — `tests/office_mcp/pdf/test_pages_txt_parser.py` 等 + `fixtures/acroform_template.pdf`

### [x] **Task OT-125** — `tests/office_mcp/pdf/test_e2e_pdf_tools.py`

### [x] **Task OT-126** — M6 E2E 验收 · **Gate G4**

| 字段 | 内容 |
|------|------|
| **必须完成** | merge builder + conversion 显式；fill_form；create native/via_docx **无** auto fallback |
| **必须完成** | **OT-138 子集**：集成测试断言 **23** canonical（终态） |

---

## Group I — M7：文档、配置、收尾

**Batch `T-OT-M7` — Tasks OT-127 – OT-136** · **Gate：G5**

### [x] **Task OT-127** — `README.md`（改）

| 字段 | 内容 |
|------|------|
| **必须完成** | 23 工具列表；架构目录；E2E 命令 |

### [x] **Task OT-128** — `Plan.md` 或项目路线图（改）

| 字段 | 内容 |
|------|------|
| **必须完成** | M0–M7 状态 |

### [x] **Task OT-129** — OT-008 – OT-011 LLM 指南同步

### [x] **Task OT-130** — OT-004 – OT-007 UPGRADE 实施状态表

### [x] **Task OT-131** — Legacy 工具 description（adapter/registry）

| 字段 | 内容 |
|------|------|
| **说明** | legacy **不在 list_tools**；**无** `[Legacy]` description 前缀（**ADR-025**，与 implementation_design M7 一致） |

### [x] **Task OT-132** — `pyproject.toml` markers 终态复核（M7）

| 字段 | 内容 |
|------|------|
| **必须完成** | 复核 `word` / `presentation` / `spreadsheet` / `pdf` 四类 marker **均已注册**（M1 OT-045c、M4 OT-092、M5 OT-107、M6 OT-123 已逐 milestone 追加） |
| **必须完成** | README 文档化 category marker 与 E2E 命令（§10.2） |
| **说明** | **非** M7 才首次追加 markers（避免 M2–M6 触发 strict-markers 失败） |

### [x] **Task OT-133** — `tests/office_mcp/probe_ds_capabilities.py`（补全 + 文档）

| 字段 | 内容 |
|------|------|
| **必须完成** | 在 OT-045b 骨架上补全 GetSheetsCount / PDF native 等（**ADR-021**） |
| **必须完成** | conftest 与 M5/M6 E2E skip 策略文档化 |
| **说明** | 依赖 OT-045b（M1/M3 已建 skip 骨架） |

### [ ] **Task OT-134** — `tests/office_mcp/gateway/` / `legacy/` 测试子目录（**可选 · 未做**）

| 字段 | 内容 |
|------|------|
| **允许** | 自 flat 测试逐步迁入；gateway 测试仍为 `tests/office_mcp/test_office_execute_builder.py` 等 |

### [x] **Task OT-135** — Shim 删除（**ADR-022 breaking PR · 已完成**）

| 字段 | 内容 |
|------|------|
| **ADR-022** | 根 shim 已删除；见 CHANGELOG「ADR-022 breaking」 |

### [x] **Task OT-136** — M7 验收 · **Gate G5**

| 字段 | 内容 |
|------|------|
| **必须完成** | health `tool_count`+`canonical_count`==23；文档与 registry 一致 |

---

## Group J — 测试与 CI 横切

**Batch `T-OT-TEST` — Tasks OT-137 – OT-141**

### [x] **Task OT-137** — `tests/office_mcp/test_e2e_office_tools.py`

| 字段 | 内容 |
|------|------|
| **M4–M6** | 逐步拆到 `test_e2e_*_{category}_tools.py` 或保留 smoke |
| **ADR-021** | 无 DS 时 `-m e2e` skip |

### [x] **Task OT-138** — `tests/office_mcp/test_openai_format.py` / `test_fastmcp_integration.py`（改）

| 字段 | 内容 |
|------|------|
| **M3** | 断言 **8** canonical；`list_tools` 无 legacy |
| **M4** | 断言 **13** |
| **M5** | 断言 **18** |
| **M6 终态** | 断言 **23** |
| **说明** | **各 milestone PR 须更新**（非仅 M7）；与 OT-075/076/098/112 联动 |

### [x] **Task OT-139** — CI 工作流（若存在 `.github/workflows/*`）

| 字段 | 内容 |
|------|------|
| **必须完成** | unit 必跑；e2e 可选 DS secrets |

### [x] **Task OT-140** — 每 PR 回归命令（§10.4）

```bash
poetry run pytest tests/office_mcp/ -v -m "not e2e"
DOCUMENTSERVER_URL=... DOCUMENTSERVER_JWT_SECRET=... \
  poetry run pytest tests/office_mcp/ -v -m e2e
```

### [x] **Task OT-141** — `aiecs/clients/documentserver_client.py`

| 字段 | 内容 |
|------|------|
| **禁止** | M0–M7 改 API 面（§2.3）；仅 bugfix |

---

## Group K — 明确禁止 / 归属脚注（N/A）

**Batch `T-OT-NA`**

| Task | 路径 / 能力 | 归属 / 说明 |
|------|-------------|-------------|
| **OT-NA-01** | `office_apply_template_pdf` | **不存在**；用 `office_fill_pdf_form`（ADR-030） |
| **OT-NA-02** | `edit_pdf.fill_form_field` | **删除**（ADR-030） |
| **OT-NA-03** | PDF create auto via_docx fallback | **禁止**（ADR-017） |
| **OT-NA-04** | merge silent conversion fallback | **禁止**（ADR-018） |
| **OT-NA-05** | `office_read_document` → fine read 透明转发 | **禁止**（§11.2） |
| **OT-NA-06** | Word `relative_index` | **禁止**（ADR-011） |
| **OT-NA-07** | Spreadsheet schema `row`/`col` 主推 | **禁止**（ADR-015） |
| **OT-NA-08** | Presentation layout fuzzy match | **禁止**（ADR-016） |
| **OT-NA-09** | `core/` 在 M3 后 feature 增强 | **须单独 PR**（ADR-029） |
| **OT-NA-10** | OCR / PDF 签名 / 加密 | **Out of scope**（§2.3） |
| **OT-NA-11** | M7 删除 conversion_output 等 shim | **ADR-022** breaking PR |
| **OT-NA-12** | 从 `list_tools` 移除 legacy | **ADR-024**；breaking PR |
| **OT-NA-13** | `core/protocols.py` TypedDict | **v1 不建**（ADR-027） |

---

## 新建文件总览（按目录）

### `aiecs/tools/office_tool/core/`

| 文件 | 里程碑 |
|------|--------|
| `__init__.py` | M0 |
| `builder_js.py` | M0 |
| `builder_runtime.py` | M0 |
| `categories.py` | M1 |
| `errors.py` | M1 |
| `read_response.py` | M1 |
| `builder_json_sidecar.py` | M1 |
| `coarse_read.py` | M1 |
| `source.py` | M1 |
| `docbuilder_script.py` | M1 |
| `storage/__init__.py`, `paths.py`, `backend.py`, `object_fetch.py` | M1 |

### `aiecs/tools/office_tool/gateway/`

| 文件 | 里程碑 |
|------|--------|
| `execute_builder.py`, `call_api.py` | M3 |

### `aiecs/tools/office_tool/legacy/`

| 文件 | 里程碑 |
|------|--------|
| `read_document.py` | M1 |
| `edit_document.py`, `merge_documents.py`, `apply_template.py` | M2-W3 |

### `aiecs/tools/office_tool/word/`（见 OT-046–056）

`parser/html.py`, `parser/document.py`, `schemas/*`, `builder/*`, `tools/*` — **M2**

### `aiecs/tools/office_tool/presentation/` — **M4**

### `aiecs/tools/office_tool/spreadsheet/` — **M5**

### `aiecs/tools/office_tool/pdf/` — **M6**

| 文件 | 里程碑 |
|------|--------|
| `parser/pages_txt.py`, `parser/document.py` | M6-P0/P1 |
| `schemas/*`, `builder/*`, `tools/*` | M6-P2–P4 |

### `aiecs/tools/office_tool/registry.py` — **M3**（M4–M6 增量注册）

---

## 修改/Shim 现有根文件总览

| 文件 | M0 | M1 | M2 | M3 | 动作 |
|------|----|----|----|----|------|
| `edit_document.py` | 改 runtime | shim | W3→legacy | shim | 最终 re-export |
| `merge_document.py` | 改 runtime | — | 迁 word | shim | |
| `apply_template.py` | 改 runtime | — | 迁 word | shim | |
| `execute_builder.py` | 改 runtime | — | — | 迁 gateway | shim |
| `call_api.py` | — | — | — | 迁 gateway | shim |
| `read_document.py` | — | 迁 legacy | shim | shim | |
| `html_parser.py` | — | — | 迁 word | shim | |
| `conversion_output.py` | — | shim | shim | shim | ADR-022 保留 |
| `source_resolver.py` | — | shim | shim | shim | |
| `storage.py` / `storage_paths.py` / `object_fetch.py` | — | shim | shim | shim | |
| `docbuilder_script.py` | — | shim | shim | shim | |
| `__init__.py` | — | — | 改 export | 改 export | |

---

## 任务批次总览

| 批次 | Tasks | 里程碑 | 阻塞 Gate |
|------|-------|--------|-----------|
| A 设计文档 | OT-001 – OT-012 | 全程 / M7 同步 | G5 |
| B M0 runtime | OT-013 – OT-022 | M0 | G0 部分 |
| C M1 core | OT-023 – OT-045c | M1 | **G0** |
| D M2 word | OT-046 – OT-067 | M2 | G1 部分 |
| E M3 registry | OT-068 – OT-082 | M3 | **G1** |
| F M4 presentation | OT-083 – OT-099 | M4 | **G2** |
| G M5 spreadsheet | OT-100 – OT-112 | M5 | **G3** |
| H M6 pdf | OT-113 – OT-126 | M6 | **G4** |
| I M7 docs | OT-127 – OT-136 | M7 | **G5** |
| J 测试横切 | OT-137 – OT-141 | M1–M7 | 全程 |
| K N/A | OT-NA-* | — | — |

---

## 验收闸门（总表）

| 闸门 | 条件 | 关联 Tasks |
|------|------|------------|
| **G0** | M0+M1；flat unit 全绿 | OT-013–045c |
| **G1** | Word + registry **M3=8/12**；legacy call_tool | OT-046–082 |
| **G2** | Presentation 五工具 E2E | OT-083–099 |
| **G3** | Spreadsheet 五工具 E2E | OT-100–112 |
| **G4** | PDF 五工具 E2E；无 apply_template | OT-113–126 |
| **G5** | README/health/docs 一致（**M6 终态 23/27**） | OT-127–136 |

**命令（按里程碑调整期望）：**

- [ ] `poetry run pytest tests/office_mcp/ -v -m "not e2e"`
- [ ] `DOCUMENTSERVER_URL=... poetry run pytest tests/office_mcp/ -v -m e2e`（或整包 skip，ADR-021）
- [ ] **M3**：`len(collect_office_tools()) == 8`；`len(get_handlers()) == 12`
- [ ] **M6 终态**：`len(collect_office_tools()) == 23`；`len(get_handlers()) == 27`
- [ ] **M6 终态**：health `tool_count` == `canonical_count` == 23
- [ ] `core/` 未 import vertical（grep 审计）
- [ ] vertical 互不 import（grep 审计）
- [ ] `office_read_document` pdf/pptx/xlsx/docx 回归快照通过

---

## 维护说明

**本文档** 为 [implementation_design.md](./implementation_design.md) 的**按文件执行真源**；与四份 `OFFICE_MCP_*_IMPLEMENTATION_DESIGN.md` 冲突时，以 **ADR.md 已采纳项** 为准。

**Agent / 开发者逐步实现建议顺序：** M0 → M1 → M2 → M3 →（M4 ∥ M5 ∥ M6）→ M7。  
**Agent 会话：** 见 [AI_PROMPT_OFFICE_TOOL_IMPLEMENTATION.md](./AI_PROMPT_OFFICE_TOOL_IMPLEMENTATION.md)。

**单 PR 模板：** 见 implementation_design §16 附录 A。
