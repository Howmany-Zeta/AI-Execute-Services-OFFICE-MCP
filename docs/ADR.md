# Office Tool — Architecture Decision Records（ADR）

汇总 Office MCP 重组与四类 vertical upgrade 中的**未决项**，每项给出**唯一建议决策**供批准。批准后应回写 [implementation_design.md](./implementation_design.md) 与各 UPGRADE 文档。

> **文档状态**：**ADR-001～047 均已采纳**  
> **关联**：[OFFICE_TOOL_ARCHITECTURE_REORG.md](./OFFICE_TOOL_ARCHITECTURE_REORG.md)、[implementation_design.md](./implementation_design.md)、[OFFICE_MCP_SPREADSHEET_UPGRADE.md](./OFFICE_MCP_SPREADSHEET_UPGRADE.md)、[OFFICE_MCP_PRESENTATION_UPGRADE.md](./OFFICE_MCP_PRESENTATION_UPGRADE.md)

**批准方式**：汇总表 `[x] 已批准`；Spreadsheet **ADR-031～040** + Presentation **ADR-041～047** 均已回写对应 UPGRADE / DESIGN / LLM 指南 / tasks（Presentation **PT-DOC-04** ✅）。

---

## ADR-001：`run_builder_script` / `run_builder_on_source` 返回契约

**状态**：**已采纳**（Accepted）

**背景**：M0 重构依赖统一 runtime；现有 6 工具返回字段不完全一致（`file_url` vs `output_path`）。`execute_builder` 无 `output_path` 时返回 `file_url`，有则返回 `output_path`；`edit`/`merge`/`template` 始终返回 `output_path`。Sidecar 流程需下载 DS 临时 URL 但不向 MCP 暴露。

**决策**：

| 结果 | 返回 dict | 条件 |
|------|-----------|------|
| 成功 + 已上传 | `{"success": True, "output_path": "<path>"}` | 调用时提供了 `output_path` 且 upload 成功 |
| 成功 + 仅 DS URL | `{"success": True, "file_url": "<url>"}` | **未**提供 `output_path`（如 `office_execute_builder`、sidecar 流程） |
| 失败 | `{"isError": True, "text": "<message>"}` | 任意步骤失败；**禁止** `{success: False}` 或 success 与 isError 并存 |

`run_builder_on_source` **始终**要求 `output_path`，故成功路径**仅** `{success, output_path}`。

Sidecar（`read_sidecar_json`）在 `run_builder_script(..., output_path=None)` 成功后读 `file_url` 下载文本，**不向 MCP 客户端**暴露 sidecar URL。

**影响**：`tests/office_mcp/core/test_builder_runtime.py` 按上表断言；各 tool 不再自行拼返回 dict。

---

## ADR-002：Schema / operations 校验技术栈

**状态**：**已采纳（修订）** — 统一 **Pydantic v2**（非原 TypedDict 方案）

**背景**：四类 `edit_ops`、`slide_spec`、`workbook_spec`、`page_spec` 及 read 响应类型均需校验；MCP `TOOL_DEF["inputSchema"]` 须与运行时校验一致，否则 LLM 合法 JSON 仍可能在 Python 层被拒。项目 `pyproject.toml` 已依赖 `pydantic>=2.11`；若 v1 用手写 validate，M2–M6 后迁移 pydantic 将触及全部 `schemas/*` 与 `TOOL_DEF`，返工成本高。

**决策**：

1. **全部** vertical `schemas/*.py` 使用 **Pydantic v2 `BaseModel`**（operations 用 `discriminated union` / `Literal` op 字段）。
2. 每个 tool 模块从对应 Model **`model_json_schema()`** 生成 MCP `inputSchema`（或共享 `build_tool_def(model)` helper），**禁止**手写 JSON Schema 与 Model 双份维护。
3. Tool handler 入口：`Model.model_validate(arguments)`；失败 → `err(...)` 格式化 `ValidationError`。
4. Read 响应：`build_read_response()` 接受 `list[BaseModel]` 或 dict，内部 `model_dump()`；类别 alias（`blocks`/`slides`/…）由 read helper 填充。
5. **M2 起**第一个 word schema 即按此实现；不回退 TypedDict。

**影响**：新增 `core/schema_tools.py`（可选）封装 `model_json_schema` → OpenAI/MCP schema；测试用 `Model.model_validate` fixture。

---

## ADR-003：Registry 注册机制

**状态**：**已采纳**（Accepted）

**背景**：架构曾写「自动发现 vs 显式列表」；漏注册会导致 health 与 E2E  silently 少工具。

**决策**：**仅显式列表** `registry.OFFICE_TOOL_MODULES`；**禁止** pkgutil 扫描。新增工具 = 新模块 + 列表**一行** + `test_registry.py` 断言名称集合。

**影响**：与 [implementation_design.md §5.2](./implementation_design.md) 一致。

---

## ADR-004：Gateway 工具 registry 模块路径

**状态**：**已采纳**（Accepted）

**背景**：implementation_design 示例出现 `gateway.tools_execute_builder` 与 `gateway/execute_builder.py` 不一致。

**决策**：Gateway **不**建 `tools/` 子包；模块路径固定为：

- `aiecs.tools.office_tool.gateway.execute_builder`
- `aiecs.tools.office_tool.gateway.call_api`

各文件导出 `TOOL_DEF` / `TOOL_NAME` / `handler`（与 vertical 相同约定）。

---

## ADR-005：Sidecar 读取 API 命名

**状态**：**已采纳**（Accepted）

**背景**：架构 `read_builder_sidecar_text`、implementation_design `read_sidecar_json`、UPGRADE 混用。

**决策**：

- `core/builder_json_sidecar.read_sidecar_json(...)` → `tuple[dict | None, str | None]`
- `build_sidecar_extract_script(...)` 保持不变
- 废弃名 `read_builder_sidecar_text` / `read_sidecar_text` **不实现**；文档统一改为 `read_sidecar_json`。

---

## ADR-006：`core/errors.py` 是否 M1 必做

**状态**：**已采纳**（Accepted）

**背景**：文档写「可选」与「建议」并存；adapter 与 6 工具错误格式已统一为 `{isError, text}` 但无单一出口。

**决策**：**M1 必做**。导出 `err(text: str) -> dict`、`ok(**kwargs) -> dict`；M0 之后新增/重构的 core 与 tool **必须**使用；旧 6 工具 M2 迁移时逐步替换，**M3 前**全部统一。

---

## ADR-007：`builder_file_ext` 与 OpenFile/SaveFile 扩展名

**状态**：**已采纳**（Accepted）

**背景**：`builder_create_type` vs `builder_file_ext`；docm/xlsm 等与 ONLYOFFICE 字符串是否二次映射未定义。

**决策**：

1. Canonical 函数名：`builder_file_ext(path_or_ext: str) -> str`（小写、无点）。
2. **OpenFile / CreateFile / SaveFile** 均使用该 ext（与 ONLYOFFICE 一致）。
3. `assert_category_path(category, path)` 失败返回错误，**不**自动改扩展名。
4. **不实现** `supports_fine_grained()`；fine/coarse 由 `read_mode` 表达。

---

## ADR-008：Edit `operations[]` 执行语义（原子性）

**状态**：**已采纳**（Accepted）

**背景**：多 op 中途失败时，输出文件与 storage 状态未定义；LLM 可能假设 op 3 失败则 op 1–2 未生效。

**决策**：**单脚本、单次 Builder 执行 = 一次事务**。

- 所有 operations 编译为**一段** JS，一次 `run_builder_on_source` / `run_builder_script`。
- Builder 失败 → `{isError, text}`，**不** upload `output_path`。
- **不**做 op 级 rollback；**不**支持「部分 op 成功」的 MCP 响应。
- Pydantic 校验失败 → Python 层拒绝，**不**调用 DS。

---

## ADR-009：Create / Merge 用 `run_builder_script`；Edit 用 `run_builder_on_source`

**状态**：**已采纳**（Accepted）

**背景**：Presentation upgrade 写 edit 可用两种 runtime；merge 已是完整自包含脚本。

**决策**：

| 场景 | Runtime |
|------|---------|
| 无源文件 create | `run_builder_script` |
| 有源文件 edit | `run_builder_on_source` |
| merge / template | `run_builder_script` |

---

## ADR-010：Word `delete_block` v1 实现

**状态**：**已采纳**（Accepted）

**背景**：Search+Remove vs ToJSON 重建；表格/嵌套块删除风险高。

**决策**：v1 **仅** **Search(块内唯一文本片段) → Remove**。无唯一匹配 → `{isError, text: "delete_block: ambiguous or not found"}`。表格块 v1 **不支持** `delete_block`（Pydantic 校验拒绝）。

---

## ADR-011：Word `relative_index`

**状态**：**已采纳**（Accepted）

**背景**：read 文档曾提 `heading_path + relative_index`，edit schema 未定义，LLM 无法使用。

**决策**：**v1 不实现 `relative_index`**。从 Word UPGRADE / LLM 指南 **删除**该定位方式；edit 仅 `block_index`、`heading_path`、`match_text`、`style_name`。

---

## ADR-012：Word `options.add_toc` 位置

**状态**：**已采纳**（Accepted）

**背景（供决策）**：

- **产品场景**：`office_create_word` 的 `options.add_toc` 用于长报告；`office_edit_word` 的 `insert_toc` op 用于已有文档插入目录。Word 中目录位置影响排版（封面后 vs 摘要前）。
- **ONLYOFFICE 行为**：`ApiDocument` 插入 TOC 通常在当前光标/文档结构位置；Builder 脚本需明确「在第一个 section 前」或「在最后一个 paragraph 后 Push」。
- **文首方案**：符合多数企业报告（封面 → TOC → 正文）；实现简单（Create 后第一个 Push 前插入）。
- **文末方案**：适合「附录在前 TOC 在后」少数场景；需额外 `after: "end"` 语义，与 `insert_toc` op 重叠。
- **风险**：若 create 带 `add_toc=true` 且 sections 首项为 `heading1`，TOC 与首个标题相对顺序需在 E2E 固定；否则 LLM 困惑。
- **与 ADR-008 关系**：`add_toc` 与 `insert_toc` 在同一 edit 脚本内按 operations 顺序执行，不单独事务。

**决策**：v1 **仅固定文首**（第一个 block 之前插入 TOC）。不支持「文末 TOC」；不实现 `options.add_toc: "start" | "end"`。

**影响**：E2E 固定 `add_toc=true` 时 TOC 与首个 section 的相对顺序；LLM 指南说明 create 目录恒在文首。

---

## ADR-013：Spreadsheet 精读 sidecar — GetSheet 循环

**状态**：**已采纳**（Accepted）

**背景（供决策）**：

- **API 差异**：ONLYOFFICE Spreadsheet Builder 常见两种遍历：`GetSheetsCount()` + 索引；或 `GetSheet(i)` 直到 `null`（upgrade 原示例 `while(true)`）。不同 DS 版本文档 emphasis 不同。
- **风险**：`while` + null 在 JS 中空 sheet 或隐藏 sheet 上可能死循环或漏 sheet；`GetSheetsCount` 若不存在则脚本整体失败。
- **read 体积**：fine read 遍历全部 sheet × used range；大表 sidecar JSON 可能超时（600s Builder 上限）。
- **与 ADR-021 关系**：若选定 `GetSheetsCount` 且 E2E 证明不可用，需 CI skip fine read，coarse csv 仍可用但**不可编辑多 sheet**。
- **现有代码**：无 spreadsheet 实现；决策只影响 sidecar 模板字符串。

**决策**：sidecar JS 使用 **`GetSheetsCount()` + for 循环**；不可用时 fine read E2E skip，coarse 保留。不采用 null-break 循环。

---

## ADR-014：Spreadsheet 模板 `{{key}}` 扫描范围

**状态**：**已采纳**（Accepted）

**背景（供决策）**：

- **两路径**：显式 `"Summary!B2": 1200` 精确但 LLM 需知坐标；`{{product_name}}` 在模板格内对业务用户友好，但扫描成本与歧义更高。
- **used_range 边界**：只扫 used range 可限制 Builder 时间；若占位符在 used range 外（预留给人工填的空白格）会漏填。
- **全文 Search**：与 Word `SearchAndReplace` 类似，可能误改非模板 sheet 或公式字符串中的 `{{`。
- **冲突**：同一 key 多格、显式地址与占位符并存——需 deterministic 规则以免两次写入不同值。
- **UPGRADE 已定方向**：显式地址为主、``{{key}}`` 为辅；本 ADR 定扫描范围。

**决策**：

1. 主路径：`data["Sheet!A1"]` 显式地址。
2. 辅助 `{{key}}`：**保留**，仅 **各 sheet `GetUsedRange()`** 内 Search 替换。
3. 同 key 多格全部替换；显式地址与 `{{key}}` 冲突时 **显式优先**。

---

## ADR-015：Spreadsheet `row`/`col` 索引

**状态**：**已采纳**（Accepted）

**背景（供决策）**：

- **LLM 习惯**：用户说「第 3 行 B 列」常理解为 **1-based**（Excel UI）；ONLYOFFICE `GetRangeByNumber(row, col)` 为 **0-based**。
- **A1 记法**：`cell: "B3"` 无歧义（Excel 惯例 1-based 显示）；若同时暴露 `row`/`col`，LLM 易与 A1 混淆。
- **read 返回**：fine read 若返回 `rows[][]` 数组，edit 用 row/col 时是否要与 read 行号对齐需在 LLM 指南写清。
- **Spreadsheet LLM 指南** 仍写「若 0-based 与 Builder 一致」——说明文档层尚未拍板。

**决策**：

1. **0-based** 与 `GetRangeByNumber` 一致（若内部仍引用）。
2. 对外主推 **`cell: "B3"`** 与 **`range`**；Pydantic schema **弃用 `row`/`col`**（`deprecated` 或 v1 不暴露），减少 LLM 误用。
3. LLM 指南删除模糊表述，统一推荐 A1 记法。

---

## ADR-016：Presentation layout 名称匹配

**状态**：**已采纳**（Accepted）

**背景（供决策）**：

- **跨格式**：pptx 与 odp 的 layout 名称集不同（「Title Slide」vs 本地化名称）；SlideSpec 用英文字符串，OpenFile odp 时可能无精确匹配。
- **LLM 输出**：常近似拼写（「Title and content」vs 「Title and Content」）；严格匹配会导致 Create 失败或落默认空白 layout。
- **fuzzy 风险**：子串匹配可能命中错误 layout（「Content」匹配多个）；Levenshtein 提高准确率但实现与测试成本高。
- **create vs add_slide**：`office_create_presentation` 与 `add_slide` op 均依赖 layout 名；规则需一致。
- **风险表** 已写 fuzzy + default，未写算法。

**决策**：**仅允许枚举**——`office_read_presentation` fine read 返回当前 deck 的 **layout 名称列表**；create / `add_slide` 的 `layout` 字段须 **精确抄录** 该列表中的值（大小写敏感、无 fuzzy、无 default fallback）。

**影响**：Pydantic 校验拒绝非枚举 layout；**odp E2E 须建立 layout 枚举表**（与 pptx 分表维护）；LLM 指南要求先 read 再 create/edit。

---

## ADR-017：PDF `create_mode` native 失败 → via_docx 触发条件

**状态**：**已采纳**（Accepted）

**背景（供决策）**：

- **DS 分裂**：PDF native API（Docs 9.3+）与 `CreateFile("docx")` + `SaveFile("pdf")` 在官方文档并存；现场 DS 可能仅支持其一。
- **成本**：自动 fallback = **两次** Builder 调用（延迟、JWT、超时风险）；LLM 无感知但 MCP 延迟翻倍。
- **512 bytes 阈值**：识别「成功但空 PDF」；阈值过小误判、过大漏判。
- **显式 `create_mode`**：LLM 可 force `via_docx` 跳 native；默认 auto-fallback 对 LLM 最省心。
- **与 ADR-021**：CI 可 skip native 断言，但运行时 fallback 仍影响生产延迟。

**决策**：

1. 默认 `create_mode: "native"`；
2. **不自动 fallback**——native 失败（DS error、超时、空输出等）→ 立即 `{isError, text}`，含失败原因与「可尝试 `create_mode=via_docx`」提示；
3. LLM / 调用方须 **显式** 改 `create_mode=via_docx` 后重试。

**影响**：单次 Builder 调用、延迟可预测；LLM 指南说明 native 不可用时的显式切换流程。

---

## ADR-018：PDF `office_merge_pdfs` 实现

**状态**：**已采纳**（Accepted）

**背景（供决策）**：

- **Builder 路径**：OpenFile 多 PDF、复制页——DS 样本少，社区反馈 merge API 不稳定。
- **Conversion 链**：多次 convert + 拼接，依赖 Conversion 而非 Builder；可能丢表单/注释，但「扫描件合并」场景有时仅需页图像。
- **用户场景**：合同包合并（ADR 定位为 `office_merge_pdfs`）；失败时 silent fallback 掩盖 DS 能力缺口。
- **与 edit 边界**：已删除 `append_pdf_pages`；merge 是唯一多 PDF 入口。
- **运维**：若仅 Builder 且失败，需在文档与 `{isError}` 中明确 DS 版本要求。

**决策**：

1. v1 **默认 Builder** 路径；E2E 失败 → 明确 `{isError}`。
2. v1 **同时实现 Conversion fallback**（仅 `office_merge_pdfs`）：隐藏开关 `options.engine=conversion`；**不** silent 自动切换，须显式指定。
3. Conversion 路径可能丢表单/注释；`{isError}` / tool description 须说明限制。

**影响**：M6 实现双 engine；E2E 覆盖 builder 默认路径 + conversion 显式路径。

---

## ADR-019：PDF `office_fill_pdf_form` API

**状态**：**已采纳**（Accepted）

**背景（供决策）**：

- **表单类型**：AcroForm 文本域、checkbox、radio；`SetFormsData` 批量接口是否覆盖全部字段类型因 DS 版本而异。
- **逐字段**：兼容性好但脚本长、慢；字段名必须与 PDF 内部名一致（`read_pdf` `form_fields` 可辅助）。
- **双路径运行时切换**：增加测试矩阵；ADR 倾向 M6 探测后 **只保留一种**。
- **与 `office_edit_pdf`**：`fill_form_field` op 重复；批量仍应用 `fill_pdf_form`。
- **探测顺序**：M6 第一个 E2E 应用典型 AcroForm fixture 测 SetFormsData。

**决策**：**直接选定逐字段 SetValue**——放弃 SetFormsData 探测与实现；v1 仅逐字段路径，兼容优先。字段名须与 `read_pdf` 返回的 `form_fields` 一致。

**影响**：M6 不跑 SetFormsData 探测 E2E；Builder 脚本按字段循环 SetValue。

---

## ADR-020：PDF coarse read 分页（`pages_txt.py`）

**状态**：**已采纳**（Accepted）

**背景（供决策）**：

- **Conversion 输出**：ONLYOFFICE txt 可能含 `\f`、无分页符的长文本、或自定义分隔（取决于源 PDF 生成器）。
- **fine vs coarse**：编辑必须 fine read；coarse 用于预览与 legacy 等价。coarse 页界错仅影响 outline，不影响 edit 若 LLM 遵守 `_note`。
- **启发式单页**：整份 txt 作为 `page_index=0` 安全但丢失页界；对多页合同 preview 体验差。
- **与 legacy**：`office_read_document` pdf→txt 行为冻结；`pages_txt` 规则变更仅影响 `office_read_pdf` coarse。

**决策**（优先级）：`\f` 分页 → 行匹配 `--- page N ---` → 否则整份作为单页并在响应中加 `_note` 说明未检测到页界。

---

## ADR-021：DocumentServer 最低版本与 CI 探针

**状态**：**已采纳**（Accepted）

**背景（供决策）**：

- **环境分裂**：开发者本地 DS、CI E2E、客户现场版本可能不同；无探针则 PDF/Sheet E2E 红绿与能力无关。
- **skip vs fail**：skip 掩盖回归；fail 阻塞 PR 但版本不可控时团队无法合并。
- **PDF 9.3+**：native PDF 能力；低于此仍可用 word→convert 与 coarse read。
- **GetSheetsCount**：非所有 DS 构建相同；需一次 session 级探测缓存。
- **探针位置**：`tests/office_mcp/probe_ds_capabilities.py` vs pytest fixture `session` scope。
- **生产 MCP**：探针仅测试用；runtime **不**因版本自动降级（ADR-017 已取消 PDF create 自动 fallback）。

**决策**：

1. **CI 无 DS**（`DOCUMENTSERVER_URL` 未设或 session 探针不可达）→ **整包 `@pytest.mark.e2e` skip**（不 fail、不跑零测试红）；unit tests（`-m "not e2e"`）仍须绿。
2. **CI 有 DS**：session 级探针写 pytest cache；按能力 skip 子集：

| 能力 | CI（有 DS 时） |
|------|----------------|
| Word/Presentation fine read | 不 skip |
| Sheet fine read | 无 `GetSheetsCount` → skip fine E2E |
| PDF native create | < 9.3 → skip native E2E；保留 via_docx/coarse |

3. **README**：写**推荐**最低 DS 版本与能力说明（非 CI gate）。

**影响**：`conftest.py` session fixture 检测 DS；`pytest -m e2e` 在无 DS 环境输出 skip 摘要而非 error。

---

## ADR-022：Import shim 移除时机

**状态**：**已采纳**（Accepted）

**背景（供决策）**：

- **Shim 对象**：`conversion_output.py`、`source_resolver.py`、`html_parser.py` 等根目录 re-export；供仓库外或未更新 import 的调用方。
- **本仓库**：M1 后应改 import 至 `core.*` / `word.parser.*`；shim 主要为 **外部兼容**。
- **保留成本**：双路径 import、grep 时重复命中、新人困惑「哪个 canonical」。
- **删除风险**：未发现的 downstream（其他 repo、notebook、部署脚本）`ImportError`。
- **M7 默认保留**：implementation_design 已写；删除需 major/breaking PR。

**决策**：M1–M7 **保留 shim** + `# deprecated: use …` 注释；删除仅 **单独 breaking PR**（M7 **不**删除 shim）。

**影响**：M7 文档标注 canonical import；shim 文件顶部 deprecation 指向新路径。

---

## ADR-023：测试目录迁移时机

**状态**：**已采纳**（Accepted）

**背景（供决策）**：

- **现状**：`tests/office_mcp/test_office_*.py` 扁平六工具测试；目标态为 `tests/office_mcp/{core,word,presentation,...}/`（implementation_design §10.1）。
- **迁移成本**：搬文件 + 改 import path + CI 脚本/文档引用；与 M2–M6 功能 PR 争抢 review 带宽。
- **不迁移风险**：新 vertical 测试与旧 flat 并存，目录语义混乱；新人不知往哪加 test。
- **部分迁移**：M3 后仅 `core/`、`word/` 先搬，presentation 仍放 flat——短期更乱。
- **与 Gate 关系**：G0–G4 只要求 pytest 绿，**未**要求目录形态；M7 文档收尾是自然窗口。

**决策**：

1. M0–M2 **不搬** flat tests。
2. **M3 registry 完成时强制**将 word 相关测试迁至 `tests/office_mcp/word/`，与 `aiecs/tools/office_tool/word/` 目录对齐。
3. presentation / spreadsheet / pdf 测试随各自 M4–M6 milestone 迁入对应子目录；M7 收尾剩余 flat 项。

**影响**：M3 PR 含 `test_office_*.py` → `tests/office_mcp/word/*` 搬迁 + CI 路径更新。

---

## ADR-024：MCP `list_tools` 与 Legacy 暴露

**状态**：**已采纳**（Accepted）

**背景（供决策）**：

- **工具数量**：目标态 **27** handler = **23 canonical**（含 gateway×2）+ **4 legacy**；gateway 已计入 23 canonical，**非**「23 + 2 gateway + 4 legacy」。`list_tools` 全暴露 legacy 则 LLM 上下文与选择成本上升。
- **Legacy 四工具**：`office_read_document`、`office_edit_document`、`office_merge_documents`、`office_apply_template`——行为保留但 description 应指向新工具。
- **OpenAI 适配**：`office_tool_adapter` 可能对 OpenAI 客户端过滤/改写 tool 列表；隐藏 legacy 可减少误选，但**已有集成**若硬编码 legacy 名则不受影响（`call_tool` 仍须注册 handler）。
- **Health**：`tool_count` 是否与 `list_tools` 长度一致（含 legacy）影响监控语义。
- **Breaking**：M7 从 list 移除 legacy 名 = breaking；仅改 description = 非 breaking。

**决策**：

1. **`list_tools`（所有 MCP 客户端，含 OpenAI）仅暴露 canonical**（**M6 终态 23 个，含 gateway×2**）；**不**列出 legacy 四工具。
2. **`call_tool` 仍注册 legacy handler**（27 名可调用），直至单独 breaking PR 移除——供存量集成过渡。
3. **M3 起**发布完整 **Legacy 迁移 changelog**（见 [LEGACY_TOOL_MIGRATION.md](./LEGACY_TOOL_MIGRATION.md)）：旧工具名 → 新工具名、参数对照、示例。

**影响**：`collect_office_tools()` 与 `get_handlers()` 分离；`test_registry.py` **按里程碑递增断言**（M3: 8/12 → M6: 23/27），终态分别暴露 23 / 注册 27。

---

## ADR-025：OpenAI description 类别前缀 `[Word]`

**状态**：**已采纳**（Accepted）

**背景（供决策）**：

- **问题**：27 工具中 `office_read_*` / `office_create_*` 等同前缀多，LLM 在 `list_tools` 扫 description 时易混 category。
- **前缀方案**：`[Word] Read structured document…`、`[Legacy] Merge documents…`——人类可读，略增 token。
- **替代**：仅靠 `inputSchema` / tool name 后缀区分；对弱模型不够。
- **时机**：M3 registry 稳定后加前缀最安全；过早改 description 影响现有 E2E snapshot（若有）。
- **Gateway**：`[Gateway]` 或无前缀（仅 2 个）。

**决策**：**M3 registry 合并时**即按 Category 为 **暴露的** canonical 工具 description 加前缀：`[Word]`、`[Presentation]`、`[Spreadsheet]`、`[PDF]`、`[Gateway]`。（legacy 已从 `list_tools` 隐藏，**无** `[Legacy]` 前缀。）

**影响**：M3 PR 更新全部 `TOOL_DEF["description"]`；新增 vertical 工具同 PR 带前缀。

---

## ADR-026：Health `tool_count` 来源

**状态**：**已采纳**（Accepted）

**背景（供决策）**：

- **现状**：health 可能手工写死工具数；registry 落地后易漂移。
- **计数口径 A**：`len(collect_office_tools())` = **`list_tools` 条目数**（含 legacy 别名，通常 27）。
- **计数口径 B**：仅 canonical 新工具（23），legacy 不计——health 与 `list_tools` 不一致，易误导。
- **Dedupe**：若 registry 同一 handler 多名称，`tool_count` 是否按 **唯一 handler** 还是 **唯一 tool name**。
- **运维**：部署探活期望「工具数 ≥ N」告警；变更需随 PR 更新断言。

**决策**（与 **ADR-024** 对齐）：

- **`tool_count`**：`len(list_tools())` = **当前 milestone 暴露的 canonical 数**（M3 起 **8**，M6 起稳定 **23**）。
- **`canonical_count`**：与 `tool_count` **同值**（显式字段，供监控语义稳定）。
- **`registered_handler_count`**（可选同响应）：`len(get_handlers())`（M3 起 **12**，M6 起 **27**；含 legacy，仅 `call_tool` 可用）。

**影响**：`main_mcp.py` health 返回三字段或至少 `tool_count` + `canonical_count`；集成测试 **随 PR 更新期望**，勿在 M3 硬编码 23。

---

## ADR-027：`core/protocols.py`（FineRead 等）

**状态**：**已采纳**（Accepted）

**背景（供决策）**：

- **动机**：四类 read 工具共享「sidecar → parser → build_read_response」；Protocol 可统一类型与 mock 点。
- **成本**：`Protocol` + 每类 `FineRead` 实现增加 indirection；v1 仅 4 个 read，YAGNI 压力。
- **替代**：文档约定 + 各 `*/tools/read.py` 复制相同步骤（已够用）；测试 mock `read_sidecar_json` 即可。
- **未来**：若加 `office_read_*` 变体或统一 read 中间层，Protocol 价值上升。
- **与 ADR-028**：`read_response.py` helper 已足够共享逻辑，Protocol 非必需。

**决策**：**v1 不创建** `core/protocols.py`；**不**建 TypedDict 响应形状；read 路径靠 `read_sidecar_json` + `build_read_response` 约定。**v2 再评估**。

---

## ADR-028：`core/read_response.py`

**状态**：**已采纳**（Accepted）

**背景（供决策）**：

- **重复风险**：四类 read 各自拼 `category`、`units[]`、`blocks`/`slides`/`sheets`/`pages` alias、`_locator_note`——漏字段则 LLM 指南与 E2E 不一致。
- **helper 职责**：`build_read_response(...)` 统一填充（implementation_design §6.1）；与 **ADR-002** Pydantic read schema 可组合（内部 `model_dump`）。
- **M1 时机**：与 `errors.py`（ADR-006）同 PR 可减少后续 read 工具返工；推迟则 M2 word read 可能先写 inline dict。
- **Legacy**：`office_read_document` **不**经此 helper（行为冻结，ADR-011/架构 §5.2）。
- **extra 字段**：类别特有键（如 presentation `layouts[]`）经 `extra=` 注入。

**决策**：**M1 必做（blocking）**——创建 `core/read_response.py`；自 **M2 起**所有新 `office_read_{category}` fine/coarse 响应**必须**经 `build_read_response()`。

---

## ADR-029：并行开发（M4/M5/M6）与 core 冲突

**状态**：**已采纳**（Accepted）

**背景（供决策）**：

- **并行窗口**：M3 registry 完成后，presentation / spreadsheet / pdf 可由不同开发者并行（implementation_design §15）。
- **冲突点**：三类均依赖 `core/builder_runtime`、`read_sidecar_json`、`coarse_read`；同时改同一文件 → merge conflict 与 subtle 回归。
- **策略 A**：M3 后 **core 仅 bugfix**，新能力放 vertical；core 增强排队单线程 owner。
- **策略 B**：允许 core 增强但 **RFC/锁文件**——协调成本高。
- **vertical 互斥**：已禁止 vertical 互 import；core 是唯一共享写热点。
- **Release**：并行 PR 可独立过 unit test，但 E2E 共享 DS 环境可能 flaky。

**决策**：**维持严格 freeze**——M3 合并 registry 后，`core/` **仅 bugfix**；vertical 并行 **不得**改 `core/`；新 core 需求须 **先**单独 small core PR，再开 vertical PR。不设 liaison 例外通道。

---

## ADR-030：PDF `office_edit_pdf` 与 `office_fill_pdf_form` 边界

**状态**：**已采纳**（Accepted）

**背景（供决策）**：

- **重叠**：`office_edit_pdf` 含 `fill_form_field` op；`office_fill_pdf_form` 接受 `data` 批量填表——同一 AcroForm 两种入口。
- **LLM 体验**：多字段时 `fill_pdf_form` 更短；单字段微调用 `edit_pdf` 与 read→edit 闭环一致。
- **实现**：ADR-019 已定 `fill_pdf_form` 逐字段 SetValue；`edit_pdf` 的 `fill_form_field` 可复用同一 builder 片段。
- **合并 PDF**：已从 edit 删除 `append_pdf_pages`；边界清晰（**ADR-018** merge 工具）。
- **风险**：两工具表单语义不一致（checkbox/boolean）或字段名大小写——须共享 schema 校验。

**决策**：

1. **多 PDF 合并** → 仅 `office_merge_pdfs`；
2. **所有 AcroForm 填写**（单字段或多字段）→ **仅** `office_fill_pdf_form`；
3. **v1 删除** `office_edit_pdf` 的 **`fill_form_field` op**；edit 仅保留页/段落/注释类 operations。

**影响**：`pdf/schemas/edit_ops.py` 不含 `fill_form_field`；LLM 指南与 UPGRADE 同步；单字段亦用 `fill_pdf_form`。

---

## ADR-031：Spreadsheet fine read — `options.include_formulas`

**状态**：**已采纳**（Accepted）

**背景（供决策）**：

- **UPGRADE §4.1** 承诺 `include_formulas: true` 时返回公式字符串；as-built sidecar 仅 `GetValue()`，schema/`TOOL_DEF` 已暴露但 handler 未接线（ST-043）。
- **实现路径**：sidecar 逐格分支——有公式则 `GetFormula()`，否则 `GetValue()`；或始终 `GetFormula()` 再 fallback。
- **移除路径**：从 Pydantic / `TOOL_DEF` 删除该字段，LLM 仅见计算结果；与「改公式前需 read 公式」工作流冲突。
- **DS 风险**：部分单元格 `GetFormula()` 空串 vs 非公式；与 **ADR-013** sidecar 体积/超时同约束。
- **默认**：`false` 保持现状；仅财务/模板场景需 true。

**决策**：

1. **v1 实现** `options.include_formulas`（默认 `false`）。
2. fine read sidecar：当 `include_formulas=true` 时，逐格先 `GetFormula()`；非空则写入 `rows`/`cells` 为公式字符串（保留 leading `=`）；否则 `GetValue()`。
3. coarse csv 路径**忽略**该选项（csv 无可靠公式语义）；响应 `extra` 可加 `_note`。
4. **不**在 v1 单独返回平行 `formulas[][]` 结构——仍用 `rows` 承载，与 UPGRADE 示例一致。

**影响**：`parser/workbook.py` sidecar 模板 + `parse_workbook_json`；`tools/read.py` 传参；ST-043 按「实现」关闭；单测 mock sidecar 含公式格。

---

## ADR-032：Spreadsheet create — `options.default_col_width`

**状态**：**已采纳**（Accepted）

**背景（供决策）**：

- UPGRADE §4.2 列 `default_col_width`；as-built `SpreadsheetCreateOptions` 有字段，`build_create_script` **未**生成 `SetColumnWidth` JS（ST-045）。
- ONLYOFFICE 列宽 API 为 per-column 或 default；全表统一宽度对 LLM 创建场景价值有限。
- **ADR-002** 要求 schema 与 `TOOL_DEF` 一致；悬空字段导致 LLM 传参无效。

**决策**：

1. **v1 从 schema、`TOOL_DEF`、UPGRADE 参数表移除** `default_col_width`。
2. 列宽调整 v1 用 `office_execute_builder` 或 v2 专用 op/`options`。
3. **不**保留 deprecated  silent ignore——避免 LLM 误以为已生效。

**影响**：删除 `SpreadsheetCreateOptions.default_col_width`；ST-045 按「移除」关闭；LLM 指南删该字段。

---

## ADR-033：Spreadsheet read `headers` 与 create `header_row`

**状态**：**已采纳**（Accepted）

**背景（供决策）**：

- UPGRADE §2.4 read 示例含 `"headers": [...]`；as-built fine read 仅 `rows[][]`，无 `headers`（ST-046）。
- create `SheetSpec.header_row: true` 已入 schema，Builder **不**改变行为；LLM 指南写「不映射 read headers」造成四文档分裂。
- **方案 A**：read 始终把 `rows[0]` 复制为 `headers`（简单，可能与数据行混淆）。
- **方案 B**：仅当 create 时 `header_row=true` 才在 read 侧标记——read 无法知历史 create 参数，不可行。
- **方案 C**：read 启发式——首行全为 string/scalar 且列数与第二行一致时设 `headers`，否则 `headers=[]` 或省略。

**决策**：

1. **v1 fine read 必须产出 `headers`**：对每个 sheet，若 `rows` 非空，**`headers = rows[0]`**（与 UPGRADE 示例对齐）；`rows` 仍保留完整数据（含首行）。
2. **`header_row`（create）保留为纯 LLM 语义字段**（默认 `false`）：表示「我 intentionally 把首行当表头」；**不改变** Builder `SetValue` 或 read 规则。
3. LLM 指南说明：read 的 `headers` 恒为 first row 镜像；编辑表头用 `set_range` 改首行。

**影响**：`parse_workbook_json` 填充 `headers`；UPGRADE/DESIGN §14 与 LLM §6 同步；ST-046 按「实现 read headers」关闭。

---

## ADR-034：Spreadsheet read — `options.range` 区域过滤

**状态**：**已采纳**（Accepted）

**背景（供决策）**：

- UPGRADE §2.4 大表策略：`options.max_rows` **与** `options.range` 限制体积；schema/`TOOL_DEF` 有 `range`，handler 未过滤（ST-044）。
- 与 `max_rows` 关系：range 先裁剪 spatial，max_rows 再截断 row 数。
- 格式：A1 或 `A1:D100`；是否 per-sheet 同名 range vs 全局——LLM 多 sheet 场景需简单规则。

**决策**：

1. **v1 实现** `options.range`（可选，A1 记法，如 `"A1:D100"`）。
2. 作用于 **每个被返回的 sheet**：解析 range 为 0-based 边界，**裁剪** sidecar/parser 后的 `rows`（及对应 `headers` 若首行在 range 外则按裁剪后首行重算 **ADR-033** 规则）。
3. 与 `max_rows` 叠加顺序：**先 range 后 max_rows**。
4. `format=outline` 时 range **仍**影响 `used_range` 报告（报告裁剪后实际范围或原 used_range——**报告裁剪后行列数**，`used_range` 字段改为裁剪范围字符串）。

**影响**：`parser/workbook.py` 增 `apply_range_filter`；`tools/read.py` 接线；ST-044 关闭。

---

## ADR-035：Spreadsheet edit — `copy_sheet` 语义

**状态**：**已采纳**（Accepted）

**背景（供决策）**：

- UPGRADE §4.3 表写 `from_sheet` + `name`；as-built 用 **`sheet_name` / `sheet_index`**（**ADR-015** 一致），`ws.Copy(ws)` 未验证（ST-049）。
- ONLYOFFICE Copy 通常生成带默认后缀的新 sheet；业务常需指定名。
- **移除 op** vs **修实现**：10 op 矩阵已发布，移除 breaking。

**决策**：

1. **v1 保留 `copy_sheet` op**；源 sheet 定位仅用 **`sheet_name` 或 `sheet_index`**（**禁止** `from_sheet` 字段名）。
2. **新增可选 `new_name`**（string）：提供则复制后 `SetName(new_name)`；省略则使用 DS 默认复制名。
3. Builder 使用 ONLYOFFICE 文档化 Copy API（`GetSheet(i).Copy(...)` 或等价）；E2E/unit 断言新 sheet 存在且名称符合预期。
4. UPGRADE §4.3 表与示例 **回写**为本决策字段名。

**影响**：`edit_ops.py` 增 `new_name: str | None`；`builder/edit.py` 重写 emit；ST-049 关闭。

---

## ADR-036：Spreadsheet edit — `add_sheet` 初始 `rows`

**状态**：**已采纳**（Accepted）

**背景（供决策）**：

- UPGRADE §4.3 写 `add_sheet` 可选 `rows[][]?`；as-built 仅 `Api.AddSheet(name)`，无初始数据。
- **实现**：AddSheet 后 `SetValue` 与 create 类似，增加 builder 复杂度。
- **替代工作流**：`add_sheet` + `set_range` 两步，**ADR-008** 单脚本内可合并为两次 op，LLM 成本略增。

**决策**：

1. **v1 不实现** `add_sheet` 的初始 `rows` 字段。
2. Pydantic **`add_sheet` 仅 `name` 必填**；若 JSON 带 `rows` → validation **拒绝**（非 silent ignore）。
3. LLM 工作流：`add_sheet` 后立即 `set_range` / `set_cell` 填表。
4. UPGRADE §4.3 删除 `rows[][]?` 列。

**影响**：ST 增明确「不支持」验收；UPGRADE/DESIGN §14/LLM §5 同步。

---

## ADR-037：Spreadsheet edit — `insert_rows` 可选 `values`

**状态**：**已采纳**（Accepted）

**背景（供决策）**：

- UPGRADE §4.3 `insert_rows` 含 `values[][]?`；as-built 仅 `InsertRows`，未 SetValue。
- 场景：「在第 5 行插入一行销售数据」单 op 完成 vs `insert_rows` + `set_range` 两 op。
- 与 **ADR-008** 一致：同一 edit 脚本内先 Insert 再 SetValue。

**决策**：

1. **v1 实现** 可选 `values: list[list[Any]] | None` on `insert_rows`。
2. 当 `values` 提供且 shape 与 `count`×列宽一致时，`InsertRows(at_row-1, count)` 后对新区间 `SetValue(values)`；未提供则仅插入空行。
3. shape 不匹配 → Pydantic 或 builder 前校验 → `{isError}`。
4. **不**实现 UPGRADE 所述 `set_range` 的「anchor + values」替代语法——v1 仅 **`range` + `values`**（**ADR-015**）。

**影响**：`edit_ops.py` + `builder/edit.py`；UPGRADE 保留 `values[][]?`；补单测。

---

## ADR-038：Spreadsheet merge — `rename_conflicts` 重命名

**状态**：**已采纳**（Accepted）

**背景（供决策）**：

- UPGRADE §4.4：sheet 名冲突时后缀 `_2`、`_3`…；as-built 接受 `rename_conflicts=true` 但 **无** 重命名 JS（ST-048）。
- `rename_conflicts=false`：冲突时 Builder 失败 vs 覆盖——需 deterministic 行为。

**决策**：

1. **`rename_conflicts=true`（默认）**：合并时若目标 workbook 已有同名 sheet，新 sheet 依次尝试 `name`、`name_2`、`name_3`… 直至唯一，再 `Copy`/`SetName`。
2. **`rename_conflicts=false`**：同名冲突 → Builder 脚本失败 → `{isError, text}` 含冲突 sheet 名；**不** silent 覆盖。
3. 逻辑在 **`builder/merge.py` JS 生成**中实现（非 Python 后处理）。

**影响**：ST-048、ST-039 E2E merge 用例；UPGRADE 与 as-built 对齐。

---

## ADR-039：Spreadsheet template — 显式地址与 `{{key}}` builder dedup

**状态**：**已采纳**（Accepted）

**背景（供决策）**：

- **ADR-014** 已裁定「显式 `Sheet!A1` 优先于 `{{key}}`」；as-built `build_template_script` 可能先 SetValue 再 SearchAndReplace，同格 **双重写入**（ST-050）。
- 显式键 `"Summary!B2"` 与 `data["product_name"]` 且模板 B2 为 `{{product_name}}` 时，应以显式值为准且 **不再** Search 该 key。

**决策**：

1. **v1 builder 必须实现 dedup**（落实 ADR-014 第 3 点）：
   - 阶段 1：处理所有显式 `Sheet!A1` / bare `A1` 键，记录 consumed logical keys（bare cell 无 sheet 时不消费 placeholder key）。
   - 阶段 2：对其余 `data` 键做 `{{key}}` SearchAndReplace；**跳过**已被显式地址消费的 key。
2. 同 key 多格 `{{key}}` 仍全部替换（ADR-014 不变）。
3. 单测：`Summary!B2` 与 `product_name` 并存时 script 或 mock 断言仅显式路径生效。

**影响**：`builder/template.py`；ST-050 关闭；与 ADR-014 文档交叉引用。

---

## ADR-040：Spreadsheet edit op — 对外字段名 canonical

**状态**：**已采纳**（Accepted）

**背景（供决策）**：

- UPGRADE §4.3 操作表混用 shorthand `sheet`、`rename_sheet` 的 `name`、`copy_sheet` 的 `from_sheet`；示例 JSON 已用 `sheet_name`；DESIGN §14 / LLM 指南以 as-built 为准。
- **ADR-015** 定 A1，未统一 sheet 定位字段名与 rename/copy 参数名。
- LLM 读 UPGRADE 表 vs 读 MCP `inputSchema` 可能传错字段。

**决策**（建议）——**v1 唯一对外形状**（Pydantic + `TOOL_DEF` + 三份 Spreadsheet 文档一致）：

| op / 场景 | 字段 |
|-----------|------|
| Sheet 定位（除 `add_sheet`） | **`sheet_name`** 或 **`sheet_index`**（0-based）；**禁止** 对外 `sheet`、`from_sheet` |
| `rename_sheet` | **`sheet_name`** + **`new_name`**（**禁止** `name` 作新名） |
| `copy_sheet` | **`sheet_name` 或 `sheet_index`** + 可选 **`new_name`**（**ADR-035**） |
| `add_sheet` | 仅 **`name`** |
| 单元格/区域 | **`cell`** / **`range`**（**ADR-015**） |

1. UPGRADE §4.3 表、示例、LLM 指南 §5 **全部回写**为上表。
2. **ST-047**：`office_edit_spreadsheet` 的 `inputSchema.operations.items` 与 `edit_ops.py` discriminated union **单一来源**（**ADR-002**）。

**影响**：文档一致性修复；无新 op；ST-047 验收标准明确。

---

## ADR-041：Presentation edit — `add_slide` 可选 `title` / `subtitle` / `items`

**状态**：**已采纳**（Accepted）

**背景（供决策）**：

- UPGRADE §4.3、`OFFICE_MCP_PRESENTATION_LLM_GUIDE.md` §3.2 示例在 `add_slide` 上传 `title`、`bullets`；as-built `EditOperation` **无** `title` 字段，`builder/edit.py` 却引用 `op.title`（**PT-046**）。
- Pydantic 默认丢弃未知字段 → LLM 按文档传 `title` 时 **静默无效**。
- **择一**：A) schema 增加字段并保留 builder；B) 删 builder 死代码，要求 `add_slide` 后单独 `set_title` / `set_bullets`。

**决策**：

1. **v1 在 `edit_ops.py` 增加**（仅 `add_slide` 使用）：可选 **`title`**、**`subtitle`**、**`items`**（bullet 列表，与 `set_bullets` 同形）。
2. `builder/edit.py`：`items` → body placeholder 填 bullet；与现有 `op.title` 分支对齐并补 `subtitle`（subtitle placeholder `SetText`）。
3. UPGRADE §4.3 表、LLM 指南 §3.2、DESIGN §5.3 **回写**为 canonical 字段名 **`items`**（**禁止** 在 op 上再引入 `bullets` 别名，与 **ADR-002** 单一 schema 一致）。
4. **不**要求 `add_slide` 必填 title — **`layout` 仍为唯一必填**（**ADR-016**）；`options.allowed_layouts` 校验规则不变（**PT-024**）。

**影响**：`schemas/edit_ops.py`、`builder/edit.py`；**PT-046**；E2E **PT-038** 依赖本 ADR；**ADR-043** TOOL_DEF 须含新字段。

---

## ADR-042：Presentation merge — `separator_slide` 的 layout

**状态**：**已采纳**（Accepted）

**背景（供决策）**：

- `options.separator_slide=true` 时 as-built `builder/merge.py` 硬编码 `pres.AddSlide("Blank")`（**PT-049**）。
- **ADR-016** 要求 layout 名精确枚举；`"Blank"` 在多数 master 中不存在 → merge 可能 Builder 失败。
- **择一**：A) 新增 `options.separator_layout` + caller `allowed_layouts`；B) v1 仅 `separator_slide=false`；C) merge 前 handler 自动 fine read 源 deck 推断 layout。

**决策**：

1. **`PresentationMergeOptions` 增加**：
   - `separator_layout: str | None = None`
   - `allowed_layouts: list[str] | None = None`（与 edit/create 同名字段、同语义）
2. **校验（handler 层，与 edit 相同模式 — 不在 merge 内隐式 read）**：
   - 当 `separator_slide=false`（默认）：不校验 layout 字段。
   - 当 `separator_slide=true`：
     - **`separator_layout` 必填**（Pydantic `model_validator`）。
     - **`options.allowed_layouts` 必填**（`min_length=1`）；缺则 `err` 文案与 edit `add_slide` 一致：*"copy layouts[] from office_read_presentation fine read (ADR-016)"*。
     - **`separator_layout` 须 ∈ `allowed_layouts`**（精确匹配、大小写敏感）；否则 `err`。
   - 实现 helper：`validate_merge_separator_layout(options) -> str | None`（可置于 `slide_spec.py` 与 `validate_add_slide_layouts` 并列）。
3. **`build_merge_script`**：传入 `separator_layout` 字符串；`pres.AddSlide("{separator_layout}")`；**删除**硬编码 `"Blank"`。
4. **`tools/merge.py` TOOL_DEF**：`options` 暴露 `separator_slide`、`separator_layout`、`allowed_layouts`；`model_json_schema()` 或手写与 **ADR-002** 一致。
5. **LLM 工作流**：启用分隔页时 — Step 1 `office_read_presentation` 任选一源 deck（或模板）→ 抄录 `layouts[]` 至 `options.allowed_layouts` → 选一成员作 `separator_layout` → merge。**禁止** handler 内自动 read（避免隐式 DS 调用、与 **ADR-029** core freeze 一致）。

**影响**：`schemas/edit_ops.py`（MergeOptions + validator）、`slide_spec.py`（helper）、`builder/merge.py`、`tools/merge.py`；**PT-049**；UPGRADE §4.4、LLM 指南 §3.5。

---

## ADR-043：Presentation edit — `TOOL_DEF.operations` 与 `edit_ops.py` 单一来源

**状态**：**已采纳**（Accepted）

**背景（供决策）**：

- as-built `office_edit_presentation` 的 `inputSchema.operations.items` 为泛型 `{"type": "object"}`（**PT-045**）；Spreadsheet 已由 **ADR-040** + **ADR-002** 收口。
- MCP 客户端与 LLM 无法从 schema 获知 10 种 op 及各 op 必填字段。

**决策**：

1. **`office_edit_presentation` 的 `operations.items`** 由 `EditOperation` **`model_json_schema()`** 生成（**ADR-002**）；`op` 字段为 `enum` 10 值。
2. Pydantic `model_validator` 与 MCP schema **单一真源**；禁止手写 JSON Schema 双份维护。
3. 字段名须含 **ADR-041** 的 `add_slide` **`title` / `subtitle` / `items`**。
4. 验收：`python3 -c` 或单测断言 `TOOL_DEF` 中 `op` enum 与 `edit_ops.OpName` 一致（对标 Spreadsheet ST-047）。

**影响**：`presentation/tools/edit.py`；**PT-045**；与 Spreadsheet **ST-047 / ADR-040** 同模式。

---

## ADR-044：Presentation fine read 失败 → coarse fallback

**状态**：**已采纳**（Accepted）

**背景（供决策）**：

- UPGRADE §4.1、DESIGN §8.1 写：`read_mode=fine` 且 Builder/sidecar 失败时可 fallback coarse 并在 `_note` 警告「须 re-read fine 后再 edit」。
- as-built `presentation/tools/read.py` 在 `sidecar_err` 时直接 **`err(...)`**（**PT-047**）。
- **风险**：fallback 掩盖 DS 配置问题；但只读预览场景可提升可用性。

**决策**：

1. **v1 实现** optional fallback：fine sidecar 失败且 `options.allow_coarse_fallback !== false`（默认 **`true`**）时，走现有 `convert_and_fetch` coarse 分支（复用 `_coarse_elements_to_slides`）。
2. 响应 **`read_mode=coarse`** + **`extra._note`** = `COARSE_NOTE`（与现 coarse 路径相同：*"Coarse txt read is for preview only — re-read with read_mode=fine before edit."*）。
3. **不**将 coarse 结果标注为 fine；**不**填充可用于 edit 定位的 `shape_index`（**PT-NA-05** 不变）。
4. `options.allow_coarse_fallback: bool = True` 加入 `PresentationReadOptions` 与 TOOL_DEF；显式 `false` 时保持现行为 **`err(sidecar_err)`**。
5. 单测：`read_sidecar_json` mock 返回 error + fallback 成功 / fallback 禁用两条路径。

**影响**：`presentation/tools/read.py`、`schemas/read.py`；**PT-047**；UPGRADE §4.1 降级段落与 DESIGN §8.1 对齐。

---

## ADR-045：Presentation sidecar — `options.slide_range` 传入 extract

**状态**：**已采纳**（Accepted）

**背景（供决策）**：

- DESIGN §6.3：`SLIDES_TOJSON_EXTRACT_BODY` 的 `start`/`end` 应来自 `options.slide_range`。
- as-built sidecar 固定 `SlidesToJSON(0, last)`；`apply_slide_range` 仅 **Python 后过滤**（**PT-048**）。
- 大 deck 全量 JSON 体积与 Builder 超时风险（UPGRADE §10 风险表）。

**决策**：

1. **v1 实现**：handler 在调用 `read_sidecar_json` 前计算 `start_slide` / `end_slide`（inclusive 0-based；缺省 `0` 与 `last = GetSlidesCount()-1`）。
2. `SLIDES_TOJSON_EXTRACT_BODY` 改为 **format 模板**（如 `build_slides_extract_body(start, end)`），sidecar 内 `SlidesToJSON(start, end, false, false, false, false)`。
3. **`layouts[]`**：仍从返回 JSON 全量解析后去重（**ADR-047**）；不因 range 裁剪而缩小 layout 枚举 — layout 列表表示 deck master，非当前 slice。
4. Python `apply_slide_range` **保留**作二次裁剪（防御 off-by-one / sidecar 与 parser 不一致）。
5. `format=outline` / `text` 同样 respect range。

**影响**：`presentation/parser/slides.py`、`presentation/tools/read.py`；**PT-048**；**ADR-029** 禁止改 `core/builder_json_sidecar` 行为 — 仅换 presentation extract body 字符串。

---

## ADR-046：Presentation create — `options.template_path`（layout 来源）

**状态**：**已采纳**（Accepted）

**背景**：

- DESIGN §5.2 曾写 create handler 内 optional `options.template_path`（**v2**）；v1 文档要求 LLM **先 read** 模板 deck 取 `layouts[]`。
- UPGRADE §4.2 **未**列 `template_path`；as-built **`office_create_presentation`** 已强制 `options.allowed_layouts`（来自 prior read 或 fixture），**无** template 字段。
- LLM 典型路径：read 空白 master → create；或 read 企业模板 → create 同 master 布局。

### 选项对比（裁定依据）

| 选项 | 描述 | 优点 | 缺点 |
|------|------|------|------|
| **A — v1 不实现**（**已采纳**） | 仅 `allowed_layouts` + `slides[]`；layout 由 caller 先 read | 与 **ADR-016** 一致；无隐式 DS 读；schema 最小 | LLM 多一步 read；单页 deck **layouts[] 可能不完整**（由 **ADR-047** `_note` 缓解） |
| **B — create 内嵌 template_path** | handler OpenFile 模板 → 读 layouts 或 Copy master | 一步调用 | 与 **`office_apply_template_presentation`** 重叠；**ADR-029** 复杂度 |
| **C — 文档化组合工具流**（**已采纳**，与 A 并用） | read→create 或 apply_template | 零代码；职责清晰 | 依赖 LLM 多步 workflow |
| **D — v2 template_path 只读 layout** | 隐式 fine read 填充 `allowed_layouts` | 缓解 layout 不全 | 与 **ADR-042** caller `allowed_layouts` 模式不一致 — **v1 否决** |

### 决策

1. **v1 不实现** `options.template_path` / `template_url` on create（**选项 A + C**）。
2. v1 layout 来源：**caller 传入 `options.allowed_layouts`**（prior fine read 的 `layouts[]`，或 E2E **`layouts_pptx.json` / `layouts_odp.json`**）。
3. DESIGN §5.2：删除 handler 内 `template_path` v2 占位，改为 **「v2 候选 ADR-046R；v1 不做」**。
4. LLM 指南：**禁止** 猜测 layout；有企业模板时用 **`office_apply_template_presentation`** 或 **read → create**；无模板时 read **多 layout master** 或使用 fixture 表。
5. 空白 deck layout 不全 **不** 用 template_path 补丁 — 见 **ADR-047**。

**影响**：文档回写（**PT-DOC-04**）；无 v1 代码 schema 变更。

---

## ADR-047：Presentation read — `layouts[]` 提取策略

**状态**：**已采纳**（Accepted）

**背景**：

- **ADR-016** 要求 create / `add_slide` /（**ADR-042**）`separator_layout` 精确匹配 layout 名；**真源**是 fine read 的 `layouts[]`。
- as-built `parse_slides_json`：JSON 顶层 `layouts` / `layoutNames`（若有）→ 各 slide `layout` **去重追加**。
- 缺口：deck 仅使用 1 种 layout 时，`layouts[]` **不含** master 上未使用的 layout 名。

### 选项对比（裁定依据）

| 选项 | 描述 | 裁定 |
|------|------|------|
| **A — 维持 as-built** | meta + slide layout 去重；不调 GetAllLayouts | **v1 采纳** |
| **B — GetAllLayouts()** | sidecar 追加 API | **v1 否决**（待 v2 ADR-047R + fixture） |
| **C — 不完整 `_note`** | `len(layouts)<=1` 且 `slide_count>0` 时警告 | **v1 采纳**（叠加 A） |
| **D — v2 `include_all_layouts`** | 可选开关 + 探针 | **v2 候选** |

### 决策

1. **v1 维持** `parse_slides_json` 现逻辑（**选项 A**）；sidecar **不**调用 `GetAllLayouts()`。
2. **v1 叠加选项 C**：fine read structured 响应中，当 `len(layouts) <= 1` 且 `slide_count > 0` 时，`build_read_response` 的 **`extra` 增加或 append `_note`**：
   - *"layouts[] may be incomplete if deck uses few layouts; read a multi-layout template master for full enum (ADR-047)."*
   - 与现有 `_locator_note` / coarse `_note` **并存**（不覆盖 **ADR-044** coarse 文案）。
3. **v2** 再开 **ADR-047R** 评估 `options.include_all_layouts` + **ADR-021** 能力探针 + `GetAllLayouts_*` fixture。
4. **PT-041** odp E2E：`allowed_layouts` 仍以 **`fixtures/layouts_odp.json`** 为真源，**不**单独依赖 read 完整性。

**影响**：`presentation/tools/read.py`（`_note` 逻辑）；`parser/slides.py` 文档化（**PT-010** 验收说明）；DESIGN §6.3 / §14 gap 表；LLM 指南 §2.4；单测 `test_read_presentation.py` 断言 `_note` 条件。

---

## 批准汇总表

| ID | 标题 | 决策摘要 | 状态 |
|----|------|----------|------|
| ADR-001 | Runtime 返回契约 | output_path / file_url / isError 三分 | **[x] 已采纳** |
| ADR-002 | Schema 校验 | **Pydantic v2 + model_json_schema → inputSchema** | **[x] 已采纳（修订）** |
| ADR-003 | Registry | 显式 OFFICE_TOOL_MODULES | **[x] 已采纳** |
| ADR-004 | Gateway 路径 | gateway.execute_builder / call_api | **[x] 已采纳** |
| ADR-005 | Sidecar 命名 | read_sidecar_json | **[x] 已采纳** |
| ADR-006 | errors.py | M1 必做 | **[x] 已采纳** |
| ADR-007 | 文件扩展名 | builder_file_ext | **[x] 已采纳** |
| ADR-008 | Edit 原子性 | 单脚本单次 DS | **[x] 已采纳** |
| ADR-009 | Runtime 选用 | edit→on_source；create/merge/template→script | **[x] 已采纳** |
| ADR-010 | Word delete_block | Search+Remove | **[x] 已采纳** |
| ADR-011 | relative_index | v1 不实现 | **[x] 已采纳** |
| ADR-012 | Word TOC | **仅固定文首** | **[x] 已采纳** |
| ADR-013 | Sheet GetSheet | **GetSheetsCount + for** | **[x] 已采纳** |
| ADR-014 | Sheet 模板 {{key}} | used_range 辅助 + 显式优先 | **[x] 已采纳** |
| ADR-015 | row/col | schema 弃用 row/col，主推 cell/range | **[x] 已采纳** |
| ADR-016 | PPT layout | **仅枚举**（read 返回列表；odp E2E 枚举表） | **[x] 已采纳** |
| ADR-017 | PDF create 回退 | **不自动 fallback**，显式 via_docx | **[x] 已采纳** |
| ADR-018 | PDF merge | Builder 默认 + conversion 隐藏开关 | **[x] 已采纳** |
| ADR-019 | PDF fill_form | **逐字段 SetValue** | **[x] 已采纳** |
| ADR-020 | PDF coarse 分页 | \\f → 标记行 → 单页 + _note | **[x] 已采纳** |
| ADR-021 | DS 版本 / CI | 无 DS 整包 e2e skip；有 DS session 探针 | **[x] 已采纳** |
| ADR-022 | Shim 移除 | M1–M7 保留；单独 breaking PR 删除 | **[x] 已采纳** |
| ADR-023 | 测试目录迁移 | **M3 强制搬 word tests** | **[x] 已采纳** |
| ADR-024 | Legacy MCP 暴露 | **list_tools 不暴露 legacy**；迁移 changelog | **[x] 已采纳** |
| ADR-025 | Description 前缀 | **M3 即加** [Category] | **[x] 已采纳** |
| ADR-026 | health tool_count | **递增**；M6 起稳定 23 + canonical_count | **[x] 已采纳** |
| ADR-027 | protocols.py | v1 不建，v2 再评估 | **[x] 已采纳** |
| ADR-028 | read_response.py | **M1 blocking** | **[x] 已采纳** |
| ADR-029 | 并行 core | **严格 freeze** | **[x] 已采纳** |
| ADR-030 | PDF edit/fill 边界 | **删除 fill_form_field** | **[x] 已采纳** |
| ADR-031 | Sheet include_formulas | **v1 实现** sidecar GetFormula 分支 | **[x] 已采纳** |
| ADR-032 | Sheet default_col_width | **v1 从 schema/TOOL_DEF 移除** | **[x] 已采纳** |
| ADR-033 | Sheet headers / header_row | read **headers=rows[0]**；create header_row 纯语义 | **[x] 已采纳** |
| ADR-034 | Sheet read range | **v1 实现** options.range 裁剪 | **[x] 已采纳** |
| ADR-035 | Sheet copy_sheet | 保留 op + **new_name**；禁止 from_sheet | **[x] 已采纳** |
| ADR-036 | Sheet add_sheet rows | **v1 不支持** 初始 rows | **[x] 已采纳** |
| ADR-037 | Sheet insert_rows values | **v1 实现** 可选 values[][] | **[x] 已采纳** |
| ADR-038 | Sheet merge rename | **必须实现** _2/_3 后缀；false→isError | **[x] 已采纳** |
| ADR-039 | Sheet template dedup | builder **落实 ADR-014** 显式优先 | **[x] 已采纳** |
| ADR-040 | Sheet edit 字段名 | sheet_name/index、new_name canonical | **[x] 已采纳** |
| ADR-041 | PPT add_slide 字段 | **title/subtitle/items** 入 schema | **[x] 已采纳** |
| ADR-042 | PPT merge 分隔页 layout | **separator_layout** + **allowed_layouts** caller 校验 | **[x] 已采纳** |
| ADR-043 | PPT edit TOOL_DEF | **model_json_schema** 单一来源 | **[x] 已采纳** |
| ADR-044 | PPT fine→coarse fallback | **v1 实现** + `_note`；`allow_coarse_fallback` 默认 true | **[x] 已采纳** |
| ADR-045 | PPT sidecar slide_range | extract **参数化** start/end | **[x] 已采纳** |
| ADR-046 | PPT create template_path | **v1 不实现**（A+C）；apply_template / read→create | **[x] 已采纳** |
| ADR-047 | PPT layouts[] 来源 | **parse 去重** + 不完整 **`_note`**；GetAllLayouts → v2 | **[x] 已采纳** |

---

## 已采纳项 — 文档与代码跟进

1. 更新 [implementation_design.md](./implementation_design.md)：**§4.3 返回契约**、**§5 schema 改为 Pydantic v2**、sidecar 命名、errors M1 必做。
2. 按 **ADR-011** 删除 Word UPGRADE / LLM 指南中的 `relative_index`。
3. 架构 / UPGRADE 中 sidecar 统一为 **`read_sidecar_json`**。
4. M0 blocking：**ADR-001、006、009**；M1 blocking：**ADR-006、028**（errors + read_response）；M2 blocking：**ADR-002**

## ADR-012～020 已采纳 — 文档与代码跟进

**文档**（已回写 `implementation_design.md` 与各 UPGRADE / LLM 指南）：

1. **ADR-012**：Word UPGRADE / LLM 指南 — `add_toc` 仅文首；E2E 固定 TOC 与首 section 顺序。
2. **ADR-013**：Spreadsheet sidecar 模板改为 `GetSheetsCount()` + for；与 ADR-021 探针联动 skip fine read。
3. **ADR-014**：Spreadsheet UPGRADE — 保留 `{{key}}` used_range 辅助路径。
4. **ADR-015**：Spreadsheet schema 弃用 `row`/`col`；LLM 指南统一 A1 `cell` / `range`。
5. **ADR-016**：Presentation read 返回 `layouts[]`；create/add_slide 精确枚举；**odp E2E layout 枚举表**。
6. **ADR-017**：PDF create 移除 auto fallback；错误 text 提示显式 `create_mode=via_docx`。
7. **ADR-018**：`office_merge_pdfs` 双 engine（默认 builder，`options.engine=conversion` 显式）。
8. **ADR-019**：`office_fill_pdf_form` 仅逐字段 SetValue（不探测 SetFormsData）。
9. **ADR-020**：`pages_txt.py` 按 `\f` → `--- page N ---` → 单页 + `_note` 实现。

**代码**（待 M2–M6 实现时落地）。

## ADR-021～022 已采纳 — 文档与代码跟进

**文档**（已回写 `implementation_design.md` §10.2、§11.1、§13）：

1. **ADR-021**：`conftest.py` session 检测 DS；无 DS → 整包 `@pytest.mark.e2e` skip；有 DS → `probe_ds_capabilities` + 能力子集 skip；README 写推荐最低版本。
2. **ADR-022**：M1–M7 保留 shim + deprecation；M7 **不**删 shim；删除仅单独 breaking PR。

**代码**（待 M1 / 测试基础设施 PR 落地）。

## ADR-023～030 已采纳 — 文档与代码跟进

**文档**（已回写 `implementation_design.md`、`LEGACY_TOOL_MIGRATION.md`、PDF UPGRADE/LLM 指南）：

1. **ADR-023**：M3 强制 `tests/office_mcp/word/` 搬迁。
2. **ADR-024**：`list_tools` 仅 23；`call_tool` 仍 27；迁移 changelog。
3. **ADR-025**：M3 全部暴露工具 description 加 `[Category]` 前缀。
4. **ADR-026**：health 返回 `tool_count` + `canonical_count`（**随 milestone 递增，M6 起 23**）。
5. **ADR-027**：v1 无 `protocols.py`。
6. **ADR-028**：M1 blocking `read_response.py`。
7. **ADR-029**：M3 后 core 严格 freeze。
8. **ADR-030**：删除 `edit_pdf.fill_form_field`。

**代码**（待 M1–M7 落地）。

## ADR-031～040 已采纳 — Spreadsheet 收尾（ST-043–057）

**背景**：M5 Spreadsheet 架构已落地；[OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_DESIGN.md](./OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_DESIGN.md) §14 与 [OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_TASKS_BY_FILE.md](./OFFICE_MCP_SPREADSHEET_IMPLEMENTATION_TASKS_BY_FILE.md) Group J–L 原「择一」项已由本节 ADR 裁定。

**文档**（已回写）：

| ADR | 回写目标 |
|-----|----------|
| **ADR-031** | UPGRADE §4.1；DESIGN §6.2/§14；ST-043 → 实现 |
| **ADR-032** | 删 UPGRADE/DESIGN/LLM 中 `default_col_width`；ST-045 → 移除 |
| **ADR-033** | UPGRADE §2.4 headers；LLM §6；ST-046 → read headers |
| **ADR-034** | UPGRADE §2.4 range；ST-044 → 实现 |
| **ADR-035** | UPGRADE §4.3 copy_sheet；edit_ops；ST-049 |
| **ADR-036** | UPGRADE §4.3 删 add_sheet.rows；LLM §5；ST-055 → 永久不支持 |
| **ADR-037** | UPGRADE §4.3 insert_rows.values；builder/edit；ST-056 → 实现 |
| **ADR-038** | UPGRADE §4.4 merge；ST-048 |
| **ADR-039** | 落实 ADR-014 builder；ST-050 |
| **ADR-040** | UPGRADE §4.3 字段表统一；ST-047 TOOL_DEF |

**代码**（待 ST-043–057 按 ADR 落地；**ADR-029** 禁止为 Spreadsheet 改 `core/` 行为）。

**任务映射**：

| ST | ADR |
|----|-----|
| ST-043 | ADR-031 |
| ST-044 | ADR-034 |
| ST-045 | ADR-032 |
| ST-046 | ADR-033 |
| ST-047 | ADR-040 |
| ST-048 | ADR-038 |
| ST-049 | ADR-035 |
| ST-050 | ADR-039 |
| ST-055 | ADR-036 |
| ST-056 | ADR-037 |
| ST-057（set_range 部分） | ADR-037 §4（仅 range+values；无 anchor） |

## ADR-041～047 已采纳 — Presentation 收尾（PT-045–049 + 文档）

**背景**：M4 Presentation 架构已落地（PT-001–036）；Group J「择一」与 layout 来源项已由 **ADR-041～047** 全部裁定（对标 Spreadsheet **ADR-031～040**）。

**文档回写**（**PT-DOC-04** ✅）：

| ADR | 回写目标 |
|-----|----------|
| **ADR-041** | UPGRADE §4.3；LLM 指南 §3.2（`items`）；DESIGN §5.3；**PT-046** |
| **ADR-042** | UPGRADE §4.4；LLM 指南 §3.5；**PT-049** |
| **ADR-043** | DESIGN §8.3；**PT-045** |
| **ADR-044** | UPGRADE §4.1；DESIGN §8.1；**PT-047** |
| **ADR-045** | DESIGN §6.3；**PT-048** |
| **ADR-046** | DESIGN §5.2；UPGRADE §4.2；LLM §3.1 | ✅ **PT-DOC-04** |
| **ADR-047** | DESIGN §6.3 / §14；LLM §2.4 | ✅ **PT-DOC-04**；⏳ `_note` **PT-011** |

**代码**（待 PT-045–049 及 ADR-047 `_note` 落地；**ADR-029** 禁止为 Presentation 改 `core/`）。

**任务映射**：

| PT | ADR |
|----|-----|
| PT-045 | ADR-043 |
| PT-046 | ADR-041 |
| PT-047 | ADR-044 |
| PT-048 | ADR-045 |
| PT-049 | ADR-042 |
| PT-010 / PT-011（`_note`） | ADR-047 |
| PT-DOC-04 | ADR-046、047 文档同步 |

**非 ADR 项（测试卫生）**：**PT-052**（M4 13/17 单测，可选）；**PT-050 / PT-051**（builder/schema 单测扩充）。

**v2 候选（未采纳）**：**ADR-046R**（create `template_path`）；**ADR-047R**（`include_all_layouts` + GetAllLayouts）。
