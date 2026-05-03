# MCP Server - Office Document Tools

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A standalone MCP (Model Context Protocol) server that exposes office document tools as MCP tools via JSON-RPC 2.0 over HTTP. Built with [FastMCP](https://github.com/jlowin/fastmcp) and integrated with [ONLYOFFICE DocumentServer](https://github.com/ONLYOFFICE/DocumentServer).

## Features

- **Six Office Tools**: Create, edit, read, merge, template-fill, and convert documents
- **DocumentServer Integration**: Uses ONLYOFFICE Builder API, Conversion API, and Command API
- **OpenAI Function Calling**: Optional `/openai/v1/tools` endpoint for OpenAI Chat Completions
- **Hybrid storage**: `source_path` (gs://) for optional GCS; `source_url` (HTTP/HTTPS) for caller-provided URLs
- **Health Monitoring**: `/health` with `documentserver_reachable` status
- **Docker Support**: Optimized image, port 5040

## Tools Overview

| Tool | Purpose |
|------|---------|
| `office_execute_builder` | Execute Builder JS script to create documents from scratch |
| `office_edit_document` | Edit existing document at GCS path with Builder script |
| `office_read_document` | Read document structure/content via Conversion API → HTML |
| `office_merge_documents` | Merge multiple documents with optional page breaks and TOC |
| `office_apply_template` | Fill template with `{{key}}` placeholders from data dict |
| `office_call_api` | Call Conversion or Command API directly (convert, forcesave, info) |

## Quick Start

### Installation

```bash
git clone https://github.com/your-org/aiecs-office-mcp.git
cd aiecs-office-mcp
poetry install
```

### Configuration

Copy `.env.example` to `.env`:

```bash
# MCP Server
MCP_HOST=0.0.0.0
MCP_PORT=5040
MCP_ENABLE_OPENAI_FORMAT=true

# DocumentServer (ONLYOFFICE) - required
DOCUMENTSERVER_URL=http://localhost:8000
DOCUMENTSERVER_JWT_SECRET=your_secret
DOCUMENTSERVER_JWT_IN_BODY=true

# GCS for office tools (gs:// paths)
# GOOGLE_APPLICATION_CREDENTIALS=/path/to/service-account.json
```

### Running

```bash
python -m aiecs.main_mcp
# Server listens on http://0.0.0.0:5040
```

### Docker

```bash
docker build -f Dockerfile.mcp -t aiecs-office-mcp:latest .
docker run -p 5040:5040 aiecs-office-mcp:latest

# Or with docker-compose
docker-compose -f docker-compose.mcp.yml up -d
```

## Endpoints

- `POST /mcp/v1` - JSON-RPC for `tools/list`, `tools/call`
- `GET /openai/v1/tools` - OpenAI function format (when `MCP_ENABLE_OPENAI_FORMAT=true`)
- `GET /health` - Health check with `server_type: office_mcp`, `tools`, `documentserver_reachable`

## Tool Details

### office_execute_builder

Execute a Document Builder JavaScript script. Script runs on DocumentServer.

- **script** (required): Builder JS (e.g. `builder.CreateFile('docx'); var oDoc = Api.GetDocument(); ...`)
- **output_path** (optional): If set, download result and upload to this path (local or `gs://`)

**output_path handling**: DocumentServer returns a temporary `fileUrl`. When `output_path` is set, the tool downloads the file and uploads to the specified storage (GCS or local).

### office_edit_document

Edit an existing document. Opens file via Builder `OpenFile`, runs your edit script, saves.

- **source_path** or **source_url** (one required): `source_path` = GCS `gs://bucket/path/file.docx`; `source_url` = HTTP/HTTPS URL (caller provides fetchable URL)
- **edit_script** (required): Builder JS edit logic only—**do NOT** include `builder.OpenFile`, `builder.SaveFile`, or `builder.CloseFile` (injected automatically)
- **output_path** (required): Output path (can equal source_path to overwrite)
- **options.backup** (optional): If true, backup source before overwrite

**edit_script convention**: Use `Search(text)` or `GetStyleName()` for positioning. **Do NOT use `GetElement(index)`**—the index from `office_read_document` does not correspond to Builder's `GetElement(i)` (headers, footers, tables cause misalignment). Recommended: call `office_read_document` first, then use `Search()` or `GetStyleName()` in `edit_script`.

### office_read_document

Read document structure/content. Uses Conversion API to HTML, then parses.

- **source_path** or **source_url** (one required): `source_path` = GCS `gs://`; `source_url` = HTTP/HTTPS URL
- **format** (optional): `structured` (default) | `text` | `outline`

**index semantics**: The `index` in returned elements is for logical order only. **Do NOT use it with Builder `GetElement(index)`**—the index sources differ. Use `Search(text)` or `GetStyleName()` for positioning in `office_edit_document`.

### office_merge_documents

Merge multiple documents in order.

- **source_paths** or **source_urls** (one required): GCS paths or HTTP/HTTPS URLs
- **output_path** (required): Output path
- **options.add_page_break** (optional): Insert page break between each document
- **options.add_toc** (optional): Add table of contents at beginning

### office_apply_template

Fill template with data. Placeholders use `{{key}}` format.

- **template_path** or **template_url** (one required): GCS path or HTTP/HTTPS URL to template
- **data** (required): Dict mapping keys to values (values converted to string)
- **output_path** (required): Output path

Example: `{"name": "Alice", "amount": 5000}` replaces `{{name}}` and `{{amount}}` in template.

### office_call_api

Call DocumentServer Conversion or Command API directly.

- **action**: `convert` | `forcesave` | `info`
- **params**:
  - **convert**: `url`, `filetype`, `outputtype`, `key` (all required)
  - **forcesave** / **info**: `key` (required)

Example convert: `{"action": "convert", "params": {"url": "https://signed/file.docx", "filetype": "docx", "outputtype": "pdf", "key": "unique-key"}}`

## JWT Signing

DocumentServer requires JWT for API calls. The payload is signed with `DOCUMENTSERVER_JWT_SECRET`:

- **Builder API**: JWT in `Authorization: Bearer <token>` header
- **Conversion/Command API**: JWT in request body as `token` when `DOCUMENTSERVER_JWT_IN_BODY=true`

Signing adds `iat` to the payload; the original payload is not modified.

## Builder Script Examples

```javascript
// Create new doc
builder.CreateFile("docx");
var oDoc = Api.GetDocument();
oDoc.GetElement(0).SetText("Hello");
builder.SaveFile("docx", "out.docx");
builder.CloseFile();

// Edit (OpenFile/SaveFile/CloseFile injected by office_edit_document)
oDoc.Search("old text").Replace("new text");
```

## Health Check

```bash
curl http://localhost:5040/health
```

Response:
```json
{
  "status": "healthy",
  "version": "1.0.0",
  "server_type": "office_mcp",
  "tools": ["office_execute_builder", "office_edit_document", "office_read_document", "office_merge_documents", "office_apply_template", "office_call_api"],
  "tool_count": 6,
  "documentserver_reachable": true
}
```

## Configuration

| Variable | Description | Default |
|----------|--------------|---------|
| `MCP_PORT` | Server port | `5040` |
| `MCP_ENABLE_OPENAI_FORMAT` | Enable `/openai/v1/tools` | `false` |
| `DOCUMENTSERVER_URL` | DocumentServer base URL | `http://localhost:8000` |
| `DOCUMENTSERVER_JWT_SECRET` | JWT secret for API auth | — |
| `DOCUMENTSERVER_JWT_IN_BODY` | Put JWT in body for Conversion/Command | `true` |
| `GOOGLE_APPLICATION_CREDENTIALS` | Path to GCS service account JSON | — |

## Code Structure

```
aiecs/
├── mcp/
│   ├── office_tool_adapter.py   # Six tools → MCP
│   ├── fastmcp_integration.py
│   └── ...
├── tools/
│   └── office_tool/             # Office tools
│       ├── execute_builder.py
│       ├── edit_document.py
│       ├── read_document.py
│       ├── merge_document.py
│       ├── apply_template.py
│       ├── call_api.py
│       ├── storage.py
│       └── html_parser.py
├── clients/
│   └── documentserver_client.py
└── main_mcp.py
```

## Development

```bash
# Unit tests (mocked DocumentServer)
poetry run pytest tests/office_mcp/test_office_*.py -v

# E2E tests (real DocumentServer at 100.70.32.65:8081)
# Requires DOCUMENTSERVER_JWT_SECRET. GCS tools need E2E_GCS_* env vars.
DOCUMENTSERVER_URL=http://100.70.32.65:8081 DOCUMENTSERVER_JWT_SECRET=<your-secret> \
  poetry run pytest tests/office_mcp/test_e2e_office_tools.py -v -m e2e
```

## License

MIT License - see [LICENSE](LICENSE) file for details.
