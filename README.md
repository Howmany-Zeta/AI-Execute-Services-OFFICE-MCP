# MCP Server - Office Document Tools

[![Python Version](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

A standalone MCP (Model Context Protocol) server that exposes **23 canonical office document tools** via JSON-RPC 2.0 over HTTP. Built with [FastMCP](https://github.com/jlowin/fastmcp) and integrated with [ONLYOFFICE DocumentServer](https://github.com/ONLYOFFICE/DocumentServer).

## Features

- **23 canonical tools** across gateway, Word, presentation, spreadsheet, and PDF categories
- **4 legacy aliases** still callable via `call_tool` but hidden from `list_tools` (migration period)
- **DocumentServer integration**: Builder API, Conversion API, and Command API
- **OpenAI function calling**: optional `/openai/v1/tools` endpoint
- **Hybrid storage**: `source_path` (gs:// / s3://) or `source_url` (HTTP/HTTPS)
- **Health monitoring**: `/health` with tool counts and DocumentServer reachability
- **Docker support**: optimized image, port 5040

## Canonical Tools (23)

| Category | Tool | Purpose |
|----------|------|---------|
| **Gateway** | `office_execute_builder` | Run raw Document Builder JavaScript |
| | `office_call_api` | Conversion / Command API (convert, forcesave, info) |
| **Word** | `office_read_word` | Fine/coarse read (docx, odt, doc) |
| | `office_create_word` | Declarative create from sections |
| | `office_edit_word` | Declarative edit operations |
| | `office_merge_word` | Merge multiple Word files |
| | `office_apply_template_word` | Template fill with `{{key}}` |
| | `office_edit_word_script` | Raw Builder edit script on Word source |
| **Presentation** | `office_read_presentation` | Fine/coarse read (pptx, ppt, odp) |
| | `office_create_presentation` | Declarative slide deck create |
| | `office_edit_presentation` | Declarative slide/shape edits |
| | `office_merge_presentations` | Merge presentations |
| | `office_apply_template_presentation` | Template fill for slides |
| **Spreadsheet** | `office_read_spreadsheet` | Fine/coarse read (xlsx, ods, xls) |
| | `office_create_spreadsheet` | Declarative workbook create |
| | `office_edit_spreadsheet` | Declarative cell/range edits |
| | `office_merge_spreadsheets` | Merge workbooks |
| | `office_apply_template_spreadsheet` | Template fill with `Sheet!A1` + `{{key}}` |
| **PDF** | `office_read_pdf` | Fine/coarse read (pdf) |
| | `office_create_pdf` | Native or via_docx create |
| | `office_edit_pdf` | Declarative page/block edits |
| | `office_merge_pdfs` | Merge PDF files |
| | `office_fill_pdf_form` | AcroForm field fill |

**Legacy (call_tool only, not in list_tools):** `office_read_document`, `office_edit_document`, `office_merge_documents`, `office_apply_template`. See [docs/LEGACY_TOOL_MIGRATION.md](docs/LEGACY_TOOL_MIGRATION.md).

**LLM guides:** [Word](docs/OFFICE_MCP_WORD_LLM_GUIDE.md) · [Presentation](docs/OFFICE_MCP_PRESENTATION_LLM_GUIDE.md) · [Spreadsheet](docs/OFFICE_MCP_SPREADSHEET_LLM_GUIDE.md) · [PDF](docs/OFFICE_MCP_PDF_LLM_GUIDE.md)

## Architecture

```
aiecs/tools/office_tool/
├── core/              # builder_runtime, categories, storage, read_response (frozen post-M3)
├── gateway/           # execute_builder, call_api
├── word/              # parser, builder, schemas, tools (6)
├── presentation/      # parser, builder, schemas, tools (5)
├── spreadsheet/       # parser, builder, schemas, tools (5)
├── pdf/               # parser, builder, schemas, tools (5)
├── legacy/            # read/edit/merge/template aliases (4 handlers)
├── registry.py        # collect_office_tools (23) + get_handlers (27)
└── *.py               # import shims (ADR-022; retained)
```

Registry is the single source of truth for `list_tools` and handler routing. The MCP adapter delegates to `registry.collect_office_tools()` and `registry.get_handlers()`.

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
MCP_HOST=0.0.0.0
MCP_PORT=5040
MCP_ENABLE_OPENAI_FORMAT=true

DOCUMENTSERVER_URL=http://localhost:8000
DOCUMENTSERVER_JWT_SECRET=your_secret
DOCUMENTSERVER_JWT_IN_BODY=true

# Builder script hosting (one of):
MCP_PUBLIC_URL=http://host:5040
# DOCBUILDER_SCRIPT_STORAGE_PATH=gs://bucket/temp/docbuilder
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

docker-compose -f docker-compose.mcp.yml up -d
```

## Endpoints

- `POST /mcp/v1` — JSON-RPC for `tools/list`, `tools/call`
- `GET /openai/v1/tools` — OpenAI function format (when `MCP_ENABLE_OPENAI_FORMAT=true`)
- `GET /health` — readiness probe with tool counts and `documentserver_reachable`

## Health Check

```bash
curl http://localhost:5040/health
```

Response (M6/M7 final registry):

```json
{
  "status": "healthy",
  "version": "1.0.0",
  "server_type": "office_mcp",
  "tool_count": 23,
  "canonical_count": 23,
  "registered_handler_count": 27,
  "documentserver_reachable": true
}
```

`tool_count` and `canonical_count` are both **23** (canonical tools in `list_tools`). `registered_handler_count` is **27** (23 canonical + 4 legacy aliases).

## Development & Testing

### Unit tests (no DocumentServer required)

```bash
poetry run pytest tests/office_mcp/ -v -m "not e2e and not integration"
```

### E2E tests (DocumentServer required)

Set `DOCUMENTSERVER_URL` and JWT (see `.env.test`). When DocumentServer is unreachable, **all** `@pytest.mark.e2e` tests are skipped (ADR-021); unit tests must still pass.

```bash
# All E2E
DOCUMENTSERVER_URL=http://your-ds:80 DOCUMENTSERVER_JWT_SECRET=<secret> \
  poetry run pytest tests/office_mcp/ -v -m e2e

# By category marker (pyproject.toml — strict-markers)
poetry run pytest tests/office_mcp/word/ -v -m "word and e2e"
poetry run pytest tests/office_mcp/presentation/ -v -m "presentation and e2e"
poetry run pytest tests/office_mcp/spreadsheet/ -v -m "spreadsheet and e2e"
poetry run pytest tests/office_mcp/pdf/ -v -m "pdf and e2e"
```

### pytest markers

| Marker | Scope |
|--------|--------|
| `e2e` | Requires live DocumentServer |
| `word` | Word category tools |
| `presentation` | Presentation category tools |
| `spreadsheet` | Spreadsheet category tools |
| `pdf` | PDF category tools |

Combine markers, e.g. `-m "word and e2e"`.

### DocumentServer capability probe (ADR-021)

`tests/office_mcp/probe_ds_capabilities.py` caches session-level DS capabilities for E2E skip decisions:

| Capability | Effect when unavailable |
|------------|------------------------|
| `get_sheets_count` | Spreadsheet **fine read** E2E skipped; coarse csv still runs |
| `pdf_native_create` | PDF **native create** E2E skipped; via_docx/coarse still available |

Override for CI or local debugging:

```bash
OFFICE_DS_GET_SHEETS_COUNT=0   # force skip fine spreadsheet E2E
OFFICE_DS_PDF_NATIVE=1         # force enable native PDF E2E
```

**Recommended DocumentServer:** 9.3+ for PDF native API; spreadsheet fine read requires `GetSheetsCount()` support. Probe runs Builder smoke scripts when `MCP_PUBLIC_URL` or `DOCBUILDER_SCRIPT_STORAGE_PATH` is configured.

Use the `ds_capabilities` session fixture from `tests/office_mcp/conftest.py` in E2E tests.

**Full test matrix** (unit vs live DS vs Phase 2 scope): [docs/OFFICE_MCP_TEST_AND_CAPABILITY_MATRIX.md](docs/OFFICE_MCP_TEST_AND_CAPABILITY_MATRIX.md).  
**Live DS known issues** (fileUrl, Builder probes, fix checklist): [docs/OFFICE_MCP_LIVE_DS_ISSUES.md](docs/OFFICE_MCP_LIVE_DS_ISSUES.md).

### Per-PR regression checklist (implementation_design §10.4)

Every PR that touches office tools should run:

```bash
# Required — no DocumentServer needed
poetry run pytest tests/office_mcp/ -v -m "not e2e and not integration"

# Registry final state
python3 -c "
from aiecs.tools.office_tool.registry import collect_office_tools, get_handlers
assert len(collect_office_tools()) == 23 and len(get_handlers()) == 27
"

# Core must not import vertical/legacy (ADR-029)
! rg "office_tool\.(word|presentation|spreadsheet|pdf|legacy)" aiecs/tools/office_tool/core/ --glob "*.py" | rg -v test && echo "OK: core clean"
```

Optional when DocumentServer is available (or CI `workflow_dispatch` with secrets):

```bash
DOCUMENTSERVER_URL=... DOCUMENTSERVER_JWT_SECRET=... \
  poetry run pytest tests/office_mcp/ -v -m e2e
```

Category-scoped E2E: `-m "word and e2e"`, `-m "presentation and e2e"`, etc.

CI: [`.github/workflows/ci-office-mcp.yml`](.github/workflows/ci-office-mcp.yml) runs unit tests on every push/PR; E2E is manual dispatch with `DOCUMENTSERVER_URL` / `DOCUMENTSERVER_JWT_SECRET` secrets.

## Security & deployment constraints

- **Error sanitization**: `OfficeToolAdapter.call_tool` redacts paths and secrets from unhandled exceptions via `sanitize_error_message` before returning to MCP clients.
- **Gateway SSRF surface**: `office_execute_builder` (arbitrary script URL) and `office_call_api` convert (user-supplied `url` forwarded to DocumentServer) intentionally accept HTTP(S) targets per gateway design. There is **no URL allowlist** or internal-network block in this repo. Deployments that expose MCP publicly should restrict network egress, authenticate callers, and/or disable gateway tools for untrusted agents.
- **Object storage**: Category tools accept `gs://` and `s3://` paths resolved to presigned URLs; scope credentials and bucket policies accordingly.

## Configuration Reference

| Variable | Description | Default |
|----------|-------------|---------|
| `MCP_PORT` | Server port | `5040` |
| `MCP_ENABLE_OPENAI_FORMAT` | Enable `/openai/v1/tools` | `false` |
| `MCP_PUBLIC_URL` | Public URL for Builder script hosting | — |
| `DOCUMENTSERVER_URL` | DocumentServer base URL | `http://localhost:8000` |
| `DOCUMENTSERVER_JWT_SECRET` | JWT secret for API auth | — |
| `DOCUMENTSERVER_JWT_IN_BODY` | Put JWT in body for Conversion/Command | `true` |
| `DOCBUILDER_SCRIPT_STORAGE_PATH` | gs:// or s3:// path for .docbuilder uploads | — |

## Documentation

- [Plan.md](Plan.md) — milestone roadmap M0–M7
- [docs/implementation_design.md](docs/implementation_design.md) — global implementation design
- [docs/OFFICE_TOOL_ARCHITECTURE_REORG.md](docs/OFFICE_TOOL_ARCHITECTURE_REORG.md) — architecture rationale
- [docs/ADR.md](docs/ADR.md) — architecture decision records

## License

MIT License — see [LICENSE](LICENSE).
