# office-Tool

MCP Server，包装 DocumentServer（OnlyOffice），供 LLM 实现文档创建、编辑、转换等操作。

## 设计方式

采用**六工具**设计：office_execute_builder（从零创建）、office_edit_document（精确编辑）、office_read_document（读取结构）、office_merge_documents（合并文档）、office_apply_template（模板填充）、office_call_api（转换/指令）。Builder 脚本透传给 DocumentServer 执行，不引入本地 JS 运行时。

## 状态

**待开发**。设计见 [AIECS-MCP-DEPLOYMENT-DESIGN.md](../docs/AIECS-MCP-DEPLOYMENT-DESIGN.md) 第 4 节，详细变更见 `openspec/changes/convert-to-office-tool/`。

## 核心 Tool

| Tool | 描述 |
|------|------|
| `office_execute_builder` | 将 JS 脚本 POST 到 DocumentServer `/docbuilder` 执行，用于从零创建文档 |
| `office_edit_document` | 精确编辑 GCS 已有文档，Python 注入 OpenFile/SaveFile，LLM 只写编辑逻辑 |
| `office_read_document` | 读取文档结构和内容（Conversion API 转 HTML + Python 解析 DOM），供编辑前了解文档 |
| `office_merge_documents` | 合并多个文档为一个，支持 add_page_break、add_toc |
| `office_apply_template` | 模板 + 数据生成文档，占位符 `{{key}}` |
| `office_call_api` | 调用 Conversion API、Command API，action: convert / forcesave / info |

## 技术要点

- **Builder**：脚本直接透传，在 DocumentServer 的 Node.js 环境中原生执行；POST /docbuilder，async: false
- **JWT**：build_jwt 不修改原 payload；Builder 用 header；Conversion/Command 当 JWT_IN_BODY=true 时 token 在 body
- **output_path**：Builder 返回临时 URL，若指定 output_path 则下载后上传到存储（如 GCS）
- **office_edit_document**：打开已有 GCS 文件，注入 OpenFile/SaveFile；精确定位用 Search() 或 GetStyleName()，不用 GetElement(index)；options.backup 可先备份
- **office_read_document**：无 Builder 脚本；Conversion API 转 HTML，Python 解析 DOM；index 仅逻辑顺序，不可用于 GetElement(i)；ONLYOFFICE HTML 非标准语义
- **office_merge_documents**：LLM 不写脚本，Python 根据参数自动生成 Builder 脚本；options: add_page_break、add_toc
- **office_apply_template**：LLM 不写脚本，Python 根据 data 自动生成查找替换脚本；模板 `{{key}}` 占位符；data value 需 str() 转换
- **office_call_api params**：convert 需 url/filetype/outputtype/key；forcesave/info 需 key；需在 tool 定义中明确化
- **异步**：httpx.AsyncClient，避免阻塞事件循环
- **超时**：Builder 120s、Conversion 60s、Command 10s
- **健康检查**：DocumentServer `/healthcheck` 返回 `"true"` 字符串

## 技术栈

- Python 3.11+
- aiecs MCP 框架（与 API-Tool/Stats-Tool 一致）
- DocumentServer REST API（Document Builder、Conversion、Command）
- httpx、PyJWT、HTML 解析（如 BeautifulSoup）、GCS 客户端（无本地 JS 运行时）

## 环境变量

```
DOCUMENTSERVER_URL=http://documentserver:80
DOCUMENTSERVER_JWT_SECRET=${JWT_SECRET}
MCP_PORT=5040
```
