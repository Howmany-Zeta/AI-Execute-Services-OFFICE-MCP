# Office MCP Live DocumentServer — 官方回应

| 字段 | 内容 |
|------|------|
| **文档编号** | DS-RESP-2026-06-24-001 |
| **状态** | 已发布（Pending remediation） |
| **发布日期** | 2026-06-24 |
| **回应对象** | [Office MCP — Live DocumentServer 已知问题](./OFFICE_MCP_LIVE_DS_ISSUES.md) |
| **环境** | `.env.test` · `DOCUMENTSERVER_URL=http://100.70.32.65:9000` |
| **发布方** | AI Execute Services — DocumentServer / Platform |

---

## 1. 执行摘要

针对 [OFFICE_MCP_LIVE_DS_ISSUES.md](./OFFICE_MCP_LIVE_DS_ISSUES.md) 中记录的 **DS-001～DS-006**，平台组于 **2026-06-24** 完成独立核查，结论如下：

1. **问题性质确认**：所列问题均属于 **live DocumentServer 部署与网络可达性** 范畴，**不属于** Office MCP 应用代码缺陷，**不属于** Phase 2 规格未实现。
2. **根因判定**：**DS-001**（Builder smoke 失败、`error: -4`、无 `fileUrl`）为 **阻塞性根因**；DS-002、DS-003、DS-006 为其直接或衍生表现；DS-004、DS-005 在 Builder 链路修复前无法完成有效验收。
3. **版本核查**：live DS 当前运行 **ONLYOFFICE Docs 9.3.1 (build:10)**，**已满足** PDF native API 所需的 **≥ 9.3** 版本门槛；**DS-005 当前失败不能归因于版本不足**。
4. **MCP 侧行为**：单元测试 **437 passed**（`-m "not e2e"`）；E2E lazy skip（ADR-021）与探针门控行为 **符合设计**，无需 MCP 代码变更。
5. **Remediation 责任**：修复工作归属 **DS/运维侧**；MCP 侧维持现有探针与 skip 逻辑，待环境就绪后按 issue 文档 §5 复验。

**官方立场**：在 DS-001 未关闭前，本环境 **不具备** Builder 相关 E2E 验收条件；Conversion 与 Word docx 主路径可继续使用，但不得将 Builder 失败解读为 MCP 功能缺失。

---

## 2. 核查方法与证据

### 2.1 核查范围

| 项 | 方法 | 时间 |
|----|------|------|
| DocumentServer 存活 | `GET /healthcheck` | 2026-06-24 |
| DocumentServer 版本 | `GET /web-apps/apps/api/documents/api.js` 解析 `Version:` 行 | 2026-06-24 |
| 官方最新版本 | GitHub Release `ONLYOFFICE/DocumentServer`、Docker Hub `onlyoffice/documentserver` | 2026-06-24 |
| E2E / 探针结果 | 引用 issue 文档 2026-06-24 全量跑数 | 2026-06-24 |
| MCP 单元测试 | 引用 issue 文档 §3 | 2026-06-24 |

### 2.2 关键证据

**Healthcheck**

```text
GET http://100.70.32.65:9000/healthcheck
→ true
```

**Live 版本（2026-06-24 实测）**

```text
GET http://100.70.32.65:9000/web-apps/apps/api/documents/api.js
→ Version: 9.3.1 (build:10)
```

**官方最新稳定版（2026-06-24 查询）**

| 来源 | 版本 | 发布日期 |
|------|------|----------|
| GitHub Release | v9.4.0 | 2026-05-19 |
| Docker Hub `latest` / `9.4.0.1` | 9.4.0.1 | 2026-05-19 |

live 环境较官方最新 **落后一个 minor 版本**（9.3.1 vs 9.4.0.1），但 **不低于 9.3**，不影响 PDF native API 的版本前置条件判定。

---

## 3. 分项官方回应

### DS-001 — Builder smoke 失败（`error: -4`，无 `fileUrl`）

| 项 | 官方结论 |
|----|----------|
| **严重性** | 高 — **P0 阻塞项** |
| **责任归属** | DS / 运维 |
| **是否 MCP 缺陷** | **否** |
| **根因（官方判定）** | DocumentServer **无法从 MCP 可达地址下载 Builder 脚本或回写结果**；`-4` 在 ONLYOFFICE 语义下通常对应 **下载 / 回调 URL 失败**，与 Conversion 可用、Builder 不可用现象一致 |
| **Remediation** | 见 §4.1 |
| **关闭条件** | `probe_ds_capabilities.py` → `builder_available: true` |

---

### DS-002 — 全部 E2E 能力探针为 False

| 项 | 官方结论 |
|----|----------|
| **严重性** | 高 |
| **责任归属** | DS / 运维（依赖 DS-001） |
| **是否 MCP 缺陷** | **否** — 13 项 `e2e_support` 探针均依赖 Builder 前置条件 |
| **官方判定** | **DS-001 的级联结果**；非 MCP 未实现 |
| **Remediation** | 先关闭 DS-001，再全量复跑 `e2e_support` 探针 |
| **关闭条件** | 目标 vertical 对应探针为 `True` |

---

### DS-003 — legacy `merge_documents` E2E 失败

| 项 | 官方结论 |
|----|----------|
| **严重性** | 中 |
| **责任归属** | DS / 运维 |
| **是否 MCP 缺陷** | **否** |
| **官方判定** | 与 DS-001 **同类** — merge 路径需稳定 `fileUrl` 与多步 `OpenFile`，对 script hosting / 超时 / 存储要求更高 |
| **Remediation** | 同 DS-001；额外确认 Builder 超时与结果上传 |
| **关闭条件** | `test_e2e_legacy_office_merge_documents_produces_merged_file` **pass** |

---

### DS-004 — `GetSheetsCount` / Spreadsheet fine read 不可用

| 项 | 官方结论 |
|----|----------|
| **严重性** | 中 |
| **责任归属** | DS / 运维 |
| **是否 MCP 缺陷** | **否** |
| **版本因素** | live DS **9.3.1** 理论上支持 spreadsheet Builder API；当前 `get_sheets_count=false` **更可能由 DS-001 导致探针无法完成**，而非版本不支持 |
| **Remediation** | DS-001 关闭后复跑 `_GET_SHEETS_COUNT_PROBE_SCRIPT`；勿在生产使用 `OFFICE_DS_GET_SHEETS_COUNT=1` 绕过 |
| **关闭条件** | `get_sheets_count: true` + spreadsheet fine read E2E 可跑 |

---

### DS-005 — PDF native API 不可用

| 项 | 官方结论 |
|----|----------|
| **严重性** | 中 |
| **责任归属** | DS / 运维 |
| **是否 MCP 缺陷** | **否** |
| **版本因素（重要更正）** | issue 文档建议「升级到 ≥ 9.3」；**官方核查确认 live 已为 9.3.1**，版本门槛 **已满足**。`pdf_native_create=false` **不能** 解释为版本不足 |
| **官方判定** | 当前失败 **首要归因 DS-001**（Builder 不可用）；native PDF 探针需 `run_builder_script` 成功 |
| **Remediation** | 优先修复 DS-001；可选规划升级至 **9.4.0.1**（功能增强，**非** DS-005 关闭的必要条件） |
| **关闭条件** | `pdf_native_create: true` + PDF fine/edit/fill E2E 可跑 |

---

### DS-006 — Builder 能力不一致

| 项 | 官方结论 |
|----|----------|
| **严重性** | 低 |
| **责任归属** | DS / 运维 |
| **是否 MCP 缺陷** | **否** |
| **官方判定** | 简单 `CreateFile` 与 merge / sidecar / 全量探针对 **网络与 script 投递** 要求不同；**不得以单个 docx create 通过作为 Builder 就绪依据** |
| **Remediation** | 以 **全量 `e2e_support` 探针 + legacy merge** 作为 Builder 就绪门槛 |
| **关闭条件** | 探针与 merge 结果一致为 pass / true |

---

## 4. 官方 Remediation 计划

### 4.1 P0 — 关闭 DS-001（阻塞项）

运维侧 **必须** 完成以下配置与验证：

1. **设置 MCP 对 DS 可达的公网/内网地址**

   在 `.env.test` 配置 **`E2E_MCP_PUBLIC_URL`**（或 `MCP_PUBLIC_URL`），确保该 URL 从 **DocumentServer 容器/主机网络** 可 HTTP GET（不得使用仅 MCP 本机可见的 `127.0.0.1` 或 Docker 内部 service name）。

2. **或配置 Builder 脚本外部托管**

   设置 **`DOCBUILDER_SCRIPT_GCS_PATH`** / MinIO 公共 URL，使 DS 可直接下载 docbuilder 脚本。

3. **网络连通性自测**

   ```bash
   # 在 DS 容器或与其同网段的主机上执行
   curl -sf "$E2E_MCP_PUBLIC_URL/health"
   curl -sfI "<Builder script URL>"
   ```

4. **JWT 一致性**

   确认 `DOCUMENTSERVER_JWT_SECRET` 与 DS 侧配置一致（Conversion 已通，Builder 仍须单独验证）。

5. **日志排查**

   查看 DS 日志中 Builder 请求与 `error: -4` 详情。

### 4.2 P1 — DS-001 关闭后复验

按 [issue 文档 §5](./OFFICE_MCP_LIVE_DS_ISSUES.md#5-ds-修复后验收) 顺序执行：

```bash
python3 tests/office_mcp/probe_ds_capabilities.py
# 期望：builder_available: true

python3 -c "
from tests.office_mcp.e2e_support import pdf_fine_read_supported, spreadsheet_fine_read_supported, presentation_pptx_create_supported, word_merge_builder_supported
print('pdf_fine_read', pdf_fine_read_supported())
print('spreadsheet_fine_read', spreadsheet_fine_read_supported())
print('presentation_pptx_create', presentation_pptx_create_supported())
print('word_merge_builder', word_merge_builder_supported())
"

python3 -m pytest tests/office_mcp/ -m e2e -q
# 期望：0 failed
```

### 4.3 P2 — 可选版本升级

| 当前 | 官方最新 | 建议 |
|------|----------|------|
| 9.3.1 (build:10) | 9.4.0.1 | **非阻塞**；可在 DS-001 关闭后纳入常规划升级窗口 |

升级 **不能替代** P0 网络/URL 修复；9.4 主要包含 license、表格 Dark Document、幻灯片主题等增强，**不保证** 单独解决 Builder `-4` 问题。

---

## 5. 责任矩阵

| 问题 ID | MCP 团队 | DS / 运维 | 说明 |
|---------|----------|-----------|------|
| DS-001 | 无代码变更 | **负责修复** | P0 |
| DS-002 | 维持 skip 门控 | **负责修复** | 依赖 DS-001 |
| DS-003 | 无代码变更 | **负责修复** | 依赖 DS-001 |
| DS-004 | 无代码变更 | **负责复验** | DS-001 后判定 |
| DS-005 | 无代码变更 | **负责复验** | 版本已满足；依赖 DS-001 |
| DS-006 | 无代码变更 | **负责复验** | 以全量探针为准 |

**MCP 团队承诺**：环境就绪后配合复跑 E2E；若 DS-001 关闭后仍有单项探针失败，按 vertical 单独开 issue 跟踪（区分 DS 与 MCP）。

---

## 6. 当前环境能力声明（官方）

在 **DS-001 未关闭** 前，官方认定 live DS 能力边界如下：

| 能力 | 状态 |
|------|------|
| Conversion coarse read | ✅ 可用 |
| `office_call_api` | ✅ 可用 |
| Word docx create / read / edit 主路径 | ✅ 可用 |
| PDF conversion merge | ✅ 可用 |
| Legacy read / edit / template（除 merge） | ✅ 可用 |
| Builder 依赖路径（merge、fine read、sidecar、PDF native 等） | ❌ **不可用** — 待 DS-001 关闭 |
| 全量 E2E Builder 验收 | ❌ **不具备条件** |

---

## 7. 对 issue 文档的勘误

| 位置 | 原表述 | 官方更正（2026-06-24） |
|------|--------|------------------------|
| DS-005 建议处理 §1 | 「升级到 ONLYOFFICE Docs **≥ 9.3**」 | live 已运行 **9.3.1**；**无需为 DS-005 单独升级版本**。应先关闭 DS-001 |
| DS-004 / DS-005 表头「DS/运维侧」 | 「DS 版本或 Builder」「需 Docs ≥ 9.3 + Builder」 | 版本条件 **已满足**；当前 blocker 为 **Builder 链路（DS-001）** |

以上勘误 **不改变** issue 文档中现象描述与验收命令的有效性。

---

## 8. 验收与关闭标准

| 里程碑 | 标准 | 负责人 |
|--------|------|--------|
| M1 — DS-001 关闭 | `builder_available: true` | DS / 运维 |
| M2 — 能力探针恢复 | 目标 vertical 对应 `e2e_support` 为 `True` | DS / 运维 + MCP 复验 |
| M3 — E2E 清零失败 | `pytest -m e2e` → **0 failed**（skip 仅限 xls fixture 等非 DS 项） | MCP 复验 |
| M4 — 文档同步 | 更新 [issue 文档](./OFFICE_MCP_LIVE_DS_ISSUES.md) 各 ID 状态与 §6 变更记录 | 平台组 |

**整体关闭条件**：M1～M4 全部完成。

---

## 9. 变更记录

| 日期 | 版本 | 变更 |
|------|------|------|
| 2026-06-24 | 1.0 | 初版：回应 OFFICE_MCP_LIVE_DS_ISSUES.md；纳入 live DS 9.3.1 版本核查与 DS-005 勘误 |

---

## 10. 引用

- [Office MCP — Live DocumentServer 已知问题](./OFFICE_MCP_LIVE_DS_ISSUES.md)
- [ONLYOFFICE DocumentServer Releases](https://github.com/ONLYOFFICE/DocumentServer/releases)
- [onlyoffice/documentserver Docker Hub](https://hub.docker.com/r/onlyoffice/documentserver/tags)
- ONLYOFFICE Builder `error: -4` — 下载 / 回调 URL 失败（常见运维类错误）
