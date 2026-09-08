# Scholar-kg ↔ Office MCP parse contract (ADR-048)

Office MCP implements parse. scholar-kg owns etag / `derived/` / wiki. This repo does not implement scholar-kg.

## Ingest (scholar-kg worker)

| Field | Rule |
|-------|------|
| `source_path` | Required `s3://` or `gs://`. **No `source_url`** (including presigned). |
| `output_path` | Required. L4-validated derived key only (e.g. `…/derived/{etag}/canonical.md`). Never forward raw user paths. |
| `engine` | `auto` (PDF → Document AI; Office binaries → DocumentServer) |
| `output_format` | `markdown` + `structured` |
| Poll | `office_parse_document_status` with `job_id` + `job_secret` from submit |

## Submit response

`{ success, job_id, job_secret, status: "queued" }`

## Status succeeded

`canonical_ref` + `structure_ref` + hashes. Default **no** inline markdown. Structure sidecar: `{output_path minus last ext}.structure.json`.

## Error codes

| Code | Meaning |
|------|---------|
| `office_unsupported` | Extension not in ALLOW_DAI / ALLOW_DS |
| `source_too_large` | Over `PARSE_MAX_SOURCE_BYTES` |
| `page_limit_exceeded` | PDF >500 pages without a valid `page_range` |
| `retryable` | Timeout / 5xx |
| `worker_restarted` | In-process worker died mid non-batch job |
