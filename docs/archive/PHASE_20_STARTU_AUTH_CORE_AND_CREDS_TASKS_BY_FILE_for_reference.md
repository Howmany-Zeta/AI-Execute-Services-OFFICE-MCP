# Phase 20 — 平行 `startuAuth` / `startuCredsService`（`startu-auth-core-and-creds`）— 按文件必选任务

**用途：** 落地 **`0035-startu-auth-core-and-creds.patch`** 时，完成 **Layer A L1 服务层**：Workbench **`startuAuth` + `startuCreds` + DI + Secret 契约 + 命令**，**不含** 登录 Webview / entitlement 大改 / chatbot。

**对齐：** [**`PHASE_20_STARTU_AUTH_CORE_AND_CREDS_DESIGN.md`](./PHASE_20_STARTU_AUTH_CORE_AND_CREDS_DESIGN.md)** · [**`PATCH_DEVELOPMENT_PLAN.md`](./PATCH_DEVELOPMENT_PLAN.md)** 表 **#20**（依赖 **#19 / `0033` 验收通过**）。

**只读参考：** **`packages/auth-chatbot-shared/`** · **`docen/overlays/product.json`**（URL 占位 · **#19**）· **`extensions/startu-auth-core/`**（薄壳 · **#19**）。

**Preconditions**

- **`0033` + `0034` + overlays** 已 materialize；**`ci-verify-docen.sh`** 绿。
- **`extensions/copilot/`** 不存在；**`startu-auth-core`** 已枚举。
- **`@startu/auth-chatbot-shared`** 在 **`vscode-main/package.json`** 可解析。

**任务编号：** **20-001 … 20-028**（服务 + 接线 + 扩展委托 + 测试 + 元任务）。

**路径约定：** TS 相对 **`vscode-main/`**；pipeline / overlay 相对 **父仓库**。

**完成定义：** **`[ ]`** → **`[x]`** = 本 Task 在 **`0035`**、pipeline PR 或脚注 **N/A(20)**（并写明归属 **#20a+**）。

---

## 里程碑定位（Phase 20 在 Layer A 中的位置）

| 阶段 | 计划 # / 补丁 | 性质 |
|------|----------------|------|
| **#19 / `0033`** | L0 封禁 + product 占位 + 薄扩展 | **前置闸门** |
| **#20 / `0035`** | **L1 登录 · 服务** | **`startuAuth` + `startuCreds` + Secret + 命令** |
| **#20a** | L1 登录 · UI | Webview + gateway **`/auth/*`** |
| **#21** | deeplink | token → **`setSession`** |
| **#22** | L2 entitlement | **`chatEntitlementService`** 改线 |

**约定：** **`0035` 验收通过** 后，**#20a** 默认在 **无 `contrib/chatbot`**、**未改 chatSetup** 的树上叠加。

---

## 当前树核对摘要（`0033`+`0034` 后 → #20 前）

| 查证项 | 结论 |
|--------|------|
| **`services/startuAuth/`** | **不存在** |
| **`IStartuAuthService` / `IStartuCredsService`** | **不存在** |
| **`startu.auth.openLogin` 命令** | product 已声明；**Workbench 未注册** |
| **`startu.gatewayUrl` 配置** | product **`providerUriSetting`** 已写；**configuration 未注册** |
| **`startu-auth-core` provider** | **stub**（`getSessions` → `[]`，`createSession` reject） |
| **`chatEntitlementService.ts`** | **上游 Copilot 路径** → **#22** |
| **`packages/auth-chatbot-shared`** | 父仓库 **已有**；workbench **可 import**（#19 接线） |

---

## Group A — 接口与类型（common）

**Batch `T-20-IFACE` — Tasks 20-001 – 20-003**

### [ ] **Task 20-001** — `src/vs/workbench/services/startuAuth/common/startuAuth.ts`

| 字段 | 内容 |
|------|------|
| **必须完成** | 定义 **`IStartuAuthService`**（`_serviceBrand`）、**`IStartuAuthSession`**、**`createDecorator('startuAuthService')`**。 |
| **必须完成** | 方法：**`waitForAuthReady`**、**`isAuthenticated`**、**`getAccessToken`**、**`refreshAuthentication`**、**`getSession`**、**`setSession`**、**`clearSession`**、**`onDidChangeSession`**（见设计 §3.1）。 |
| **必须完成** | **`SubscriptionInfo`** 从 **`@startu/auth-chatbot-shared`** type-only import（或本地 mirror 类型，tasks 锁定一种）。 |
| **禁止** | 实现类、**`registerSingleton`**（→ **20-005**）。 |

### [ ] **Task 20-002** — `src/vs/workbench/services/startuAuth/common/startuCreds.ts`

| 字段 | 内容 |
|------|------|
| **必须完成** | **`IStartuCredsService`** + **`createDecorator('startuCredsService')`**。 |
| **必须完成** | **`getPricingUrl`**、**`getWebsiteUrl`**、**`getGatewayUrl`**、**`storeMembershipType`**、**`getMembershipType`**、**`onDidChangeMembershipType`**。 |
| **禁止** | 打开 **`SubscribePage`** / 内嵌购订 Webview。 |

### [ ] **Task 20-003** — `src/vs/workbench/services/startuAuth/common/startuConfiguration.ts`

| 字段 | 内容 |
|------|------|
| **必须完成** | 常量 **`STARTU_GATEWAY_URL_SETTING = 'startu.gatewayUrl'`**；**`registerConfiguration`** 块（string，描述 gateway 基址）。 |
| **默认** | 空字符串 → 运行时 fallback **`getGatewayUrl()`** 链（设计 §3.2）。 |

---

## Group B — Browser 实现

**Batch `T-20-IMPL` — Tasks 20-004 – 20-007**

### [ ] **Task 20-004** — `src/vs/workbench/services/startuAuth/browser/startuCredsService.ts`

| 字段 | 内容 |
|------|------|
| **必须完成** | 实现 **`IStartuCredsService`**；注入 **`IProductService`**、**`IConfigurationService`**、**`ISecretStorageService`**。 |
| **必须完成** | **`getPricingUrl()`**：`pricingUrl` → `startuUpgradeUrl` → `` `${websiteUrl}/pricing` ``。 |
| **必须完成** | **`getGatewayUrl()`**：配置 **`startu.gatewayUrl`** → **`getGatewayUrl()` from shared**（传入 override）。 |
| **必须完成** | **`storeMembershipType` / `getMembershipType`**：Secret 键 **`startuAuth.membershipType`**。 |
| **必须完成** | **`registerSingleton(IStartuCredsService, StartuCredsService, InstantiationType.Delayed)`**。 |

### [ ] **Task 20-005** — `src/vs/workbench/services/startuAuth/browser/startuAuthService.ts`

| 字段 | 内容 |
|------|------|
| **必须完成** | 实现 **`IStartuAuthService`**；注入 **`ISecretStorageService`**、**`ILogService`**、**`IStartuCredsService`**（gateway URL）。 |
| **必须完成** | 启动时读 **`startuAuth.session`** → hydrate → **`Barrier` / Promise** 供 **`waitForAuthReady`**。 |
| **必须完成** | **`setSession` / `clearSession`**：读写 Secret + **`clearServiceTokenCache()`**（shared）+ fire **`onDidChangeSession`**。 |
| **必须完成** | **`getAccessToken`**：过期检查（若 **`expiresAt`** 存在）；过期可尝试 **`refreshAuthentication`** 或返回 `undefined`（策略在实现注释锁定）。 |
| **必须完成** | **`refreshAuthentication`**：调用 gateway refresh 端点 **或** 仅清会话并返回 `false`（若 gateway 契约未定，**最小实现** 为「无 refresh token 则 false」+ 文档脚注 **#20a 补全**）。 |
| **必须完成** | **`registerSingleton(IStartuAuthService, StartuAuthService, InstantiationType.Eager)`**（或 Delayed，与 creds 一致 — **二选一锁定**）。 |
| **禁止** | 内嵌 fetch 登录表单、OAuth redirect。 |

### [ ] **Task 20-006** — Secret 键常量

| 字段 | 内容 |
|------|------|
| **必须完成** | 在 **`startuAuth.ts`** 或 **`startuAuthSessionStorage.ts`** 导出：**`STARTU_AUTH_SESSION_KEY = 'startuAuth.session'`**、**`STARTU_AUTH_MEMBERSHIP_KEY = 'startuAuth.membershipType'`**。 |
| **验收** | **#20a** 设计 §3.3 与此 **完全一致**。 |

### [ ] **Task 20-007** — `refreshAuthentication` 与 gateway（可选最小）

| 字段 | 内容 |
|------|------|
| **必须完成** | 若实现 refresh HTTP：仅用 **`@startu/auth-chatbot-shared`** 的 **`apiRequest`** / **`fetchServiceToken`** 模式；endpoint 与 **[`STARTU_GATEWAY_REFERENCE.md`](./STARTU_GATEWAY_REFERENCE.md)** 对齐。 |
| **允许 N/A** | gateway **`/auth/refresh`** 未定时：**stub 返回 false** + 设计文档脚注；**#20a** 登录后写长寿命 token。 |

---

## Group C — 命令与 contribution

**Batch `T-20-CMD` — Tasks 20-008 – 20-011**

### [ ] **Task 20-008** — `src/vs/workbench/services/startuAuth/browser/startuAuth.contribution.ts`

| 字段 | 内容 |
|------|------|
| **必须完成** | 注册命令：**`startu.auth.openLogin`**、**`startu.auth.refreshToken`**、**`startu.auth.signOut`**、**`startu.auth.setSession`**（后者可 **internal** / **`when: false`** 菜单）。 |
| **`openLogin` #20** | **不** 打开 Webview；**notification**「Login UI ships in Phase 20a」**或** 静默 noop — **实现前在 PR 描述锁定**。 |
| **`refreshToken`** | 调用 **`IStartuAuthService.refreshAuthentication()`**。 |
| **`setSession`** | 解析参数 → **`setSession()`**（供 **#20a** extension 调用）。 |

### [ ] **Task 20-009** — `workbench.common.main.ts`

| 字段 | 内容 |
|------|------|
| **必须完成** | import **`./services/startuAuth/browser/startuAuthService.js`** |
| **必须完成** | import **`./services/startuAuth/browser/startuCredsService.js`** |
| **必须完成** | import **`./services/startuAuth/browser/startuAuth.contribution.js`** |
| **必须完成** | import **`./services/startuAuth/common/startuConfiguration.js`**（若 configuration 在独立文件注册） |
| **禁止** | 在 **`workbench.desktop.main.ts`** 重复 import（除非 Electron-only 服务 — **#20 不需要**）。 |

### [ ] **Task 20-010** — #22 挂钩点（事件 only）

| 字段 | 内容 |
|------|------|
| **必须完成** | **`onDidChangeSession`** 在 **`setSession` / `clearSession`** 后 **必 fire**。 |
| **禁止** | 在 #20 调用 **`chatEntitlementService.refresh*`** 或改 **`chatEntitlementService.ts`**。 |
| **说明** | **#22** 新增 listener 文件或 contribution。 |

### [ ] **Task 20-011** — product 命令对齐审计

| 字段 | 内容 |
|------|------|
| **必须完成** | materialized **`product.json`** 中 **`walkthroughCommand`** / **`chatRefreshTokenCommand`** 与注册命令 ID **一致**。 |
| **归属** | overlay **#19 已写**；#20 **仅验证**，除非发现 typo。 |

---

## Group D — 内置扩展委托（最小）

**Batch `T-20-EXT` — Tasks 20-012 – 20-014**

### [ ] **Task 20-012** — `extensions/startu-auth-core/src/authProvider.ts`

| 字段 | 内容 |
|------|------|
| **必须完成** | **`createSession`**：`vscode.commands.executeCommand('startu.auth.openLogin')` 后 **仍 reject 或 pend** 直至 #20a 写 session（**不** 在 #20 实现完整 OAuth）。 |
| **可选** | **`getSessions`**：若 Secret 对扩展不可见，保持 **`[]`** 直至 #20a 双写 **`AuthenticationSession`**。 |
| **禁止** | 新增 Webview、**`auth-login-webview.ts`**。 |

### [ ] **Task 20-013** — `extensions/startu-auth-core/README.md`

| 字段 | 内容 |
|------|------|
| **必须完成** | 声明：**会话真源 = Workbench `IStartuAuthService`（#20）**；UI = **#20a**；Secret 键 = 设计 §3.3。 |

### [ ] **Task 20-014** — `extensions/startu-auth-core/package.json`

| 字段 | 内容 |
|------|------|
| **默认 N/A(20)** | **不** 新增 **`contributes.commands`**，除非 #20a 需要扩展侧命令。 |
| **若改** | 仅 **`activationEvents`** 文档化 **`onCommand:startu.auth.openLogin`** — **可选**。 |

---

## Group E — 测试

**Batch `T-20-TEST` — Tasks 20-015 – 20-017**

### [ ] **Task 20-015** — `src/vs/workbench/services/startuAuth/test/browser/startuAuthService.test.ts`

| 字段 | 内容 |
|------|------|
| **必须完成** | mock **`ISecretStorageService`**：**setSession → getAccessToken → isAuthenticated true → clearSession → false**。 |
| **必须完成** | **`waitForAuthReady`** resolves（空 Secret 与有 Secret 各一例）。 |

### [ ] **Task 20-016** — `startuCredsService` 单元测试

| 字段 | 内容 |
|------|------|
| **必须完成** | mock **`IProductService`**：**`getPricingUrl()`** 返回 overlay 期望 URL。 |

### [ ] **Task 20-017** — 编译 / CI

| 字段 | 内容 |
|------|------|
| **必须完成** | **`npm run compile`** 含新测试文件（或 **`test/browser`** 被现有 test 任务拾取）。 |
| **说明** | 若 upstream test  harness 排除 workbench services，**最低** compile + **手动 dev 脚本** 脚注。 |

---

## Group F — Pipeline 与补丁元数据

**Batch `T-20-PIPE` — Tasks 20-018 – 20-022**

### [ ] **Task 20-018** — `patches/0035-startu-auth-core-and-creds.patch`

| 字段 | 内容 |
|------|------|
| **必须完成** | **`./scripts/create-patch.sh`** 自 **#19 materialized 树** 导出；**单一意图**。 |
| **禁止** | 混入 **#20a** Webview、**#22** entitlement diff。 |

### [ ] **Task 20-019** — `patches/series.post-transform`

| 字段 | 内容 |
|------|------|
| **必须完成** | 在 **`0034`** 后追加 **`0035-startu-auth-core-and-creds.patch`**。 |

### [ ] **Task 20-020** — `transforms/pipeline.json`

| 字段 | 内容 |
|------|------|
| **必须完成** | production pipeline **apply 0035**（扩展 **`post-copilot` 段** 或新 step **`post-auth-services`** — **id 在 PR 锁定**）。 |
| **验收** | **`apply-pipeline.py`** 全量 materialize 含 **0035**。 |

### [ ] **Task 20-021** — `scripts/ci-verify-docen.sh`

| 字段 | 内容 |
|------|------|
| **默认 N/A(20)** | 若 pipeline 已含 0035，**无需** 改 ci-verify。 |
| **若改** | 仅当新增 **marker / 契约断言**（例如 **`rg IStartuAuthService`**）— **可选**。 |

### [ ] **Task 20-022** — `docs/PATCH_DEVELOPMENT_PLAN.md` 链接

| 字段 | 内容 |
|------|------|
| **必须完成** | 表 **#20** 行增加本设计 + tasks 链接（与 **#19** 格式一致）。 |

---

## Group G — 明确禁止 / 归属脚注（N/A）

**Batch `T-20-NA` — Tasks 20-023 – 20-028**

| Task | 路径 / 能力 | 归属 |
|------|-------------|------|
| **20-023** | **`auth-login-webview.ts`** / **`webview-out/*`** | **#20a** |
| **20-024** | **`packages/auth-ui-shared`** 打包进扩展 | **#20a** |
| **20-025** | **`extensions/startu-deeplink`** | **#21** |
| **20-026** | **`chatEntitlementService.ts` 大改** | **#22** |
| **20-027** | **`contrib/chatbot/**`** | **#24～#26** |
| **20-028** | **`chatSetup*` / `welcomeOnboarding` 改线** | **#27** |

---

## 任务批次总览

| 批次 | Tasks | 阻塞 compile | 阻塞 #20a |
|------|-------|--------------|-----------|
| A 接口 | 20-001 – 20-003 | 是 | — |
| B 实现 | 20-004 – 20-007 | 是 | — |
| C 命令/接线 | 20-008 – 20-011 | 是 | 部分（**openLogin** 壳） |
| D 扩展 | 20-012 – 20-014 | 是 | 是（Secret 双写 **#20a**） |
| E 测试 | 20-015 – 20-017 | 是 | — |
| F pipeline | 20-018 – 20-022 | 是 | — |
| G N/A | 20-023 – 20-028 | — | — |

---

## 补丁与验收

| 项 | 内容 |
|----|------|
| **补丁** | **`0035-startu-auth-core-and-creds.patch`** |
| **`series.post-transform`** | **`0034`** 之后 |
| **前置** | **`0033` 验收通过** |

**闸门：**

- [ ] **`ci-verify-docen.sh`**（pipeline 含 **0035**）
- [ ] **`npm run compile`**
- [ ] **`IStartuAuthService` / `IStartuCredsService`** 已 **`registerSingleton`**
- [ ] Secret roundtrip 测试（**20-015**）
- [ ] **`getPricingUrl()`** 与 overlay 一致（**20-016**）
- [ ] **`startu.auth.openLogin`** / **`startu.auth.refreshToken`** 已注册（**20-008**）
- [ ] **`0035` diff** 范围锁（**20-023～028** 无违规路径）

**非闸门（#20 中间态）：** 无登录 Webview、Setup 仍 Copilot 风、Chat 不可用 — **#20a/#27 前预期**。

- [ ] **里程碑**：**#20a** 仅在 **本 Phase 验收通过后** 开栈

---

## #27b 审阅脚注

**Phase 27b audit (2026-05-31):** 通过 — **GAP-27b-20a-001** 已修复（`startu.creds.getWebsiteUrl` / `getSignupUrl`）。

**维护：** 本节为 **Phase 20 按文件真源**；[`PHASE_20_STARTU_AUTH_CORE_AND_CREDS_DESIGN.md`](./PHASE_20_STARTU_AUTH_CORE_AND_CREDS_DESIGN.md) 为设计真源。Agent 逐步实现：**[`AI_PROMPT_PHASE_20.md`](./AI_PROMPT_PHASE_20.md)**。
