# Office MCP — Live DocumentServer 已知问题

> **环境**：`.env.test` · `DOCUMENTSERVER_URL=http://100.70.32.65:9000` · 探针/全量 E2E 日期 **2026-06-24**  
> **关联**：[测试矩阵](./OFFICE_MCP_TEST_AND_CAPABILITY_MATRIX.md) · [ADR-021](./ADR.md) · `tests/office_mcp/probe_ds_capabilities.py`

本文档记录 **live DS 安装/网络** 导致的问题（非 Office MCP 代码缺陷、非 Phase 2 规格缺口）。升级 DS 或修正部署后，请更新状态并复跑 §5 验收命令。

---

## 1. 问题总览

| ID | 严重性 | 摘要 | MCP 侧状态 | DS/运维侧 |
|----|--------|------|------------|-----------|
| [DS-001](#ds-001-builder-smoke-失败-fileurl-error--4) | **高** | Builder 探针 smoke 失败（`error: -4`，无 `fileUrl`） | 探针 `builder_available=false` | 待修复 |
| [DS-002](#ds-002-全部-e2e-能力探针为-false) | **高** | 13 个 `e2e_support` 能力探针均为 `False` | E2E lazy skip（ADR-021） | 依赖 DS-001 |
| [DS-003](#ds-003-legacy-merge_documents-e2e-失败) | **中** | `office_merge_documents` E2E 无 `fileUrl` | 1 个 E2E **fail** | 同 DS-001 类 |
| [DS-004](#ds-004-getsheetscount--spreadsheet-fine-read-不可用) | **中** | `get_sheets_count=false` | Spreadsheet fine/edit/merge E2E skip | DS 版本或 Builder |
| [DS-005](#ds-005-pdf-native-api-不可用) | **中** | `pdf_native_create=false` | PDF fine/edit/fill/create E2E skip | 需 Docs **≥ 9.3** + Builder |
| [DS-006](#ds-006-builder-能力不一致) | **低** | 部分 Builder E2E 通过、探针/merge 失败 | 结果不稳定 | 脚本 hosting / 超时 |

**当前可用（本 DS）**：Conversion coarse read、`office_call_api`、Word **docx** create/read/edit 主路径、PDF **conversion** merge、legacy read/edit/template（除 merge）。

---

## 2. 问题详情

### DS-001: Builder smoke 失败 (`fileUrl`, error -4)

**现象**

```
DocumentServer did not return fileUrl. Raw response: {'error': -4}
probe_ds_capabilities → builder_available: false
```

**影响**

- `tests/office_mcp/probe_ds_capabilities.py` 会话探针标记 Builder 不可用。
- 依赖 `run_builder_script` 且需稳定 `fileUrl` 的路径（sidecar、多步 merge、部分 smoke）不可靠。

**可能原因**

1. DocumentServer **无法回拉 Builder 脚本或结果 URL**（`MCP_PUBLIC_URL` / `DOCBUILDER_SCRIPT_*` 对 DS 不可达）。
2. DS 与 MCP 不在同一可达网络（Docker 服务名、`127.0.0.1` 仅本机可见）。
3. JWT / Builder 端点配置不完整（与 Conversion 可用但 Builder 失败一致）。

**建议处理**

1. 在 `.env.test` 设置 **`E2E_MCP_PUBLIC_URL`**（或 `MCP_PUBLIC_URL`）为 **DocumentServer 能 HTTP GET 的地址**（非容器内部 hostname）。
2. 或配置 **`DOCBUILDER_SCRIPT_GCS_PATH`** / MinIO 公共 URL，使 DS 能下载 docbuilder 脚本。
3. 从 DS 容器内手动 `curl` MCP 的 script URL 与 healthcheck。
4. 查看 DS 日志中 Builder 请求与 `-4` 详情（ONLYOFFICE 常见为下载/回调失败）。

**验证**

```bash
python3 tests/office_mcp/probe_ds_capabilities.py
# 期望：builder_available: true
```

---

### DS-002: 全部 E2E 能力探针为 False

**现象**（2026-06-24，`e2e_support.py` 全量探针，~11 min）

```
word_odt_create: False
word_merge_builder: False
spreadsheet_fine_read: False
spreadsheet_ods_create: False
spreadsheet_merge: False
spreadsheet_edit: False
presentation_pptx_create: False
presentation_merge: False
presentation_odp_create: False
presentation_edit: False
pdf_fine_read: False
pdf_edit: False
pdf_fill_form: False
```

**影响**

- 各 vertical `@pytest.mark.skipif` 门控的 E2E **全部 skip**（见 [测试矩阵 §2.4](./OFFICE_MCP_TEST_AND_CAPABILITY_MATRIX.md#24-e2e-跳过29)）。
- **不是** MCP 未实现；是 live DS 不满足 Builder 能力前置条件。

**建议处理**

- 先解决 [DS-001](#ds-001-builder-smoke-失败-fileurl-error--4)。
- 再逐项复跑探针；Spreadsheet/PDF 另需 [DS-004](#ds-004-getsheetscount--spreadsheet-fine-read-不可用)、[DS-005](#ds-005-pdf-native-api-不可用)。

---

### DS-003: legacy `merge_documents` E2E 失败

**现象**

```
FAILED test_e2e_legacy_office_merge_documents_produces_merged_file
→ DocumentServer did not return fileUrl
```

**影响**

- Legacy `office_merge_documents` 多文档 Builder merge 路径在本环境不可用。
- Word canonical `office_merge_word` 相关 E2E 亦因 `word_merge_builder_supported=false` 被 skip。

**建议处理**

- 与 DS-001 相同：Builder 回调与 `fileUrl` 链路。
- merge 脚本较长、多次 `OpenFile`；确认 DS Builder 超时与存储上传均正常。

**验证**

```bash
python3 -m pytest tests/office_mcp/test_e2e_office_tools.py::test_e2e_legacy_office_merge_documents_produces_merged_file -v
python3 -m pytest tests/office_mcp/word/test_e2e_word_tools.py -m e2e -k merge -v
```

---

### DS-004: `GetSheetsCount` / Spreadsheet fine read 不可用

**现象**

- `probe_ds_capabilities → get_sheets_count: false`
- Spreadsheet fine read sidecar E2E skip。

**影响**

- `office_read_spreadsheet` **fine**、`office_edit_spreadsheet`、`office_merge_spreadsheets`（Builder）、ods create 等 E2E 无法在本 DS 验收。
- **Coarse**（Conversion csv + legacy `read_document`）仍可用。

**建议处理**

1. 确认 ONLYOFFICE 版本支持 spreadsheet Builder API `Api.GetSheetsCount()`。
2. 在 DS-001 修复后复跑 `_GET_SHEETS_COUNT_PROBE_SCRIPT`（见 `probe_ds_capabilities.py`）。
3. 临时调试可设 `OFFICE_DS_GET_SHEETS_COUNT=1`（**仅本地**，不表示生产可用）。

---

### DS-005: PDF native API 不可用

**现象**

- `probe_ds_capabilities → pdf_native_create: false`
- PDF fine read / edit / fill / native create E2E skip。

**影响**

- `office_read_pdf` fine sidecar、`office_edit_pdf`、`office_fill_pdf_form`、`office_create_pdf`（native）无法 E2E 验收。
- **仍可用**：`office_read_pdf` coarse、`office_merge_pdfs` **conversion** engine、legacy pdf→txt。

**建议处理**

1. 升级到 ONLYOFFICE Docs **9.3+**（PDF native API，见 [PDF UPGRADE](./OFFICE_MCP_PDF_UPGRADE.md)）。
2. DS-001 修复后复跑 `_PDF_NATIVE_PROBE_SCRIPT`。
3. 生产可显式 `create_mode=via_docx`（不依赖 native API）；fine read 仍要 Builder OpenFile + sidecar。

---

### DS-006: Builder 能力不一致

**现象**

- 同一 DS 上 **部分** Builder E2E 通过（如 `office_execute_builder` docx、`office_create_read_edit_word_docx`）。
- 同时探针 `builder_available=false`，merge / 全量 `e2e_support` 探针失败。

**可能原因**

- 简单 `CreateFile` 与多步 `OpenFile`/sidecar/merge 对 **script hosting、超时、存储** 要求不同。
- 探针与 E2E 使用不同 script 投递路径或竞态。

**建议处理**

- 以 **全量 `e2e_support` 探针 + legacy merge** 为「Builder 就绪」门槛，不单以单个 docx create 为准。
- 增加 Builder 超时/重试仅在确认 DS 网络稳定后考虑（MCP 默认不自动重试）。

---

## 3. 非 DS 问题（勿记入本表）

| 项 | 说明 |
|----|------|
| Phase 2 规格 | OCR、PDF image block、脚注 CRUD 等 → [测试矩阵 §4](./OFFICE_MCP_TEST_AND_CAPABILITY_MATRIX.md#4-phase-2--后续版本实现非当前-ds-问题) |
| 测试环境 | `test_e2e_read_spreadsheet_xls` skip（缺 `.xls` fixture） |
| 产品外 | `/providers` 端点、OpenAI format 未启用 → 测试 skip，非 DS |
| MCP 代码 | 单元测试 **437 passed**（`-m "not e2e"`）— 逻辑在 mock 下已验收 |

---

## 4. 环境检查清单

在报告新 Issue 前确认：

- [ ] `curl $DOCUMENTSERVER_URL/healthcheck` → `true`
- [ ] `curl $E2E_MCP_URL/health` → 200
- [ ] `DOCUMENTSERVER_JWT_SECRET` 与 DS 一致
- [ ] `E2E_SOURCE_PATH` 为 DS 可 fetch 的 signed URL（s3/gs）
- [ ] **`E2E_MCP_PUBLIC_URL`** 从 DS 网络可访问（Builder script 回调）
- [ ] `python3 tests/office_mcp/probe_ds_capabilities.py` 输出已保存

---

## 5. DS 修复后验收

```bash
# 探针
python3 tests/office_mcp/probe_ds_capabilities.py

# 能力探针（较慢，~10+ min）
python3 -c "
from tests.office_mcp.e2e_support import pdf_fine_read_supported, spreadsheet_fine_read_supported, presentation_pptx_create_supported, word_merge_builder_supported
print('pdf_fine_read', pdf_fine_read_supported())
print('spreadsheet_fine_read', spreadsheet_fine_read_supported())
print('presentation_pptx_create', presentation_pptx_create_supported())
print('word_merge_builder', word_merge_builder_supported())
"

# 全量 E2E
python3 -m pytest tests/office_mcp/ -m e2e -q
```

**期望**：`builder_available=true`；能力探针至少与本 DS 目标 vertical 一致为 `True`；全量 E2E **0 failed**（skip 仅保留 xls fixture 等非 DS 项）。

---

## 6. 变更记录

| 日期 | 变更 |
|------|------|
| 2026-06-24 | 初版：基于全量 E2E（450/29/1）与 13 项能力探针建档 |
