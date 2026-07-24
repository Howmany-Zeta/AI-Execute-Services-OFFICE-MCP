# aiecs-office-mcp — Artifact Registry 发布规范

## 镜像仓库

| 项 | 值 |
|---|---|
| Registry | `us-central1-docker.pkg.dev/ca-biz-kjmsdw-y59m/aiecs-mcp-servers` |
| 镜像名 | `aiecs-office-mcp` |
| 完整路径 | `us-central1-docker.pkg.dev/ca-biz-kjmsdw-y59m/aiecs-mcp-servers/aiecs-office-mcp` |

## 镜像内容原则

**包含（应用运行时）：**

- Python 3.11 运行时与 `pyproject.toml` 中 `--only=main` 依赖
- Office MCP 服务代码（`aiecs/mcp`、`office_tool`、DocumentServer client、tool executor 等）
- Redis **客户端**库（连接外部 Redis，非 Redis 服务本身）

**不包含（外部基础设施，由 Compose / 云环境提供）：**

- DocumentServer / OnlyOffice
- Redis / Postgres / RabbitMQ / MinIO 等服务进程
- GCS 凭证文件（通过 volume + `GOOGLE_APPLICATION_CREDENTIALS` 注入）
- `.env` / `.env.prod`（运行时 `env_file` 注入）

## Tag 规范

| Tag | 示例 | 用途 | 可变性 |
|-----|------|------|--------|
| `<semver>` | `1.9.3` | 版本发布 | 同一 semver 仅对应一次正式发布 |
| `<semver>-<git-sha>` | `1.9.3-7d54c53` | **生产推荐 pin** | 不可变 |
| `<git-sha>` | `7d54c53` | CI / 调试追溯 | 不可变 |
| `latest` | `latest` | 滚动最新稳定版 | 可变 |

版本号来源：`pyproject.toml` → `[project].version`。

## 发布流程

### 前置条件

1. 代码已在目标 commit（`git status` 干净或确认接受 dirty tree 警告）
2. 已安装 Docker、`gcloud`，且对 Artifact Registry 有 push 权限
3. 一次性配置 Docker 凭据：

```bash
gcloud auth configure-docker us-central1-docker.pkg.dev
```

### 1. 生产检查（本地）

```bash
cd startu-tool-mcp/AI-Execute-Services-OFFICE-MCP
./scripts/validate_production_image.sh
```

检查项：multi-stage 构建、非 root 运行、依赖 import、MCP 端点、无 gcc 工具链。

### 2. 构建并推送

```bash
./scripts/publish_artifact_registry.sh
```

可选参数：

- `--dry-run` — 仅打印将推送的 tag
- `--no-latest` — 不更新 `:latest`
- `--push-only` — 跳过 build，推送本地已有 tag

### 3. 在 startu 部署仓使用

`docker-compose.yml` 中改为拉取远程镜像（示例）：

```yaml
aiecs-office-mcp:
  image: us-central1-docker.pkg.dev/ca-biz-kjmsdw-y59m/aiecs-mcp-servers/aiecs-office-mcp:1.9.3-7d54c53
  env_file:
    - ./config/mcp/aiecs-office-mcp.env.prod   # 或保留现有 .env.prod 路径
```

生产环境请 **pin 到 `<semver>-<git-sha>`**，避免 `latest` 漂移。

### 4. 发布后验证

```bash
docker compose pull aiecs-office-mcp
docker compose up -d aiecs-office-mcp
curl -s http://localhost:5040/health | jq .
# documentserver_reachable 应为 true（需 DocumentServer 已启动）
```

## 回滚

```bash
# 切换到上一已知 good tag
docker compose stop aiecs-office-mcp
# 修改 compose 中 image tag 为旧版本
docker compose pull aiecs-office-mcp
docker compose up -d aiecs-office-mcp
```

## 与 DocumentServer 镜像对齐

DocumentServer 已使用同一 registry 前缀：

`us-central1-docker.pkg.dev/ca-biz-kjmsdw-y59m/aiecs-mcp-servers/aiecs-documentserver:latest`

Office MCP 与其共用 `gcloud auth configure-docker us-central1-docker.pkg.dev` 认证。
