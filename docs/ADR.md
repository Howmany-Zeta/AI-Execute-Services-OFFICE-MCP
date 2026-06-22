# Office Tool — Architecture Decision Records（ADR）

汇总 Office MCP 重组与四类 vertical upgrade 中的**未决项**，每项给出**唯一建议决策**供批准。批准后应回写 [implementation_design.md](./implementation_design.md) 与各 UPGRADE 文档。

> **文档状态**：**ADR-001～030 均已采纳**  
> **关联**：[OFFICE_TOOL_ARCHITECTURE_REORG.md](./OFFICE_TOOL_ARCHITECTURE_REORG.md)、[implementation_design.md](./implementation_design.md)

**批准方式**：汇总表 `[x] 已批准`；全部 ADR 已裁定，待 M1–M7 代码落地。

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
