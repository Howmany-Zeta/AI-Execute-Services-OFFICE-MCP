"""office_parse_document — enqueue async parse job (ADR-048)."""

from __future__ import annotations

import logging
from typing import Any, Optional

from pydantic import ValidationError

from aiecs.config import get_parse_job_config
from aiecs.tools.office_tool.core.errors import err, ok
from aiecs.tools.office_tool.core.parse_job import create_queued_job, job_store_ready
from aiecs.tools.office_tool.core.parse_routing import parse_file_ext, route_parse_engine
from aiecs.tools.office_tool.core.parse_security import output_path_allowed, webhook_url_allowed
from aiecs.tools.office_tool.parse.schemas import ParseDocumentArgs

logger = logging.getLogger(__name__)

TOOL_NAME = "office_parse_document"

TOOL_DEF = {
    "name": TOOL_NAME,
    "description": (
        "[Parse] Async parse of PDF (Document AI) or Office binaries (DocumentServer). "
        "Always returns job_id + job_secret. output_path is required (allowlisted gs:// or s3://). "
        "Poll with office_parse_document_status. Do not use for csv/xlsx/txt/md. ADR-048."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "source_path": {"type": "string"},
            "source_url": {"type": "string"},
            "engine": {"type": "string", "enum": ["auto", "document_ai", "documentserver"], "default": "auto"},
            "output_format": {
                "oneOf": [
                    {"type": "string", "enum": ["markdown", "text", "structured"]},
                    {"type": "array", "items": {"type": "string", "enum": ["markdown", "text", "structured"]}},
                ]
            },
            "output_path": {"type": "string"},
            "callback_url": {"type": "string"},
            "options": {
                "type": "object",
                "properties": {
                    "page_range": {"type": "array", "items": {"type": "integer"}, "minItems": 2, "maxItems": 2},
                    "inline_max_bytes": {"type": "integer", "minimum": 1},
                    "include_inline": {"type": "boolean"},
                },
            },
        },
        "required": ["output_path"],
    },
}


async def office_parse_document(
    source_path: Optional[str] = None,
    source_url: Optional[str] = None,
    engine: str = "auto",
    output_format: Any = None,
    output_path: Optional[str] = None,
    callback_url: Optional[str] = None,
    options: Optional[dict] = None,
    **kwargs: Any,
) -> dict[str, Any]:
    raw = {
        "source_path": source_path,
        "source_url": source_url,
        "engine": engine,
        "output_format": output_format or ["markdown", "structured"],
        "output_path": output_path,
        "callback_url": callback_url,
        "options": options or {},
        **kwargs,
    }
    try:
        args = ParseDocumentArgs.model_validate(raw)
    except ValidationError as e:
        return err(str(e.errors()[0]["msg"]) if e.errors() else str(e))

    cfg = get_parse_job_config()
    path_val = (args.source_path or "").strip()
    url_val = (args.source_url or "").strip()
    if cfg.require_object_source and url_val:
        return err("source_url is not allowed for this caller; use s3:// or gs:// source_path")

    ext = parse_file_ext(path_val or url_val)
    _engine, route_err = route_parse_engine(ext, args.engine)
    if route_err == "office_unsupported":
        return err("office_unsupported")
    if route_err == "invalid_engine":
        return err("engine document_ai is only valid for .pdf")

    path_err = output_path_allowed(args.output_path, path_val or None)
    if path_err:
        return err(path_err)

    if not job_store_ready():
        try:
            from aiecs.infrastructure.persistence import get_redis_client

            await get_redis_client()
        except Exception as e:
            return err(f"Parse job store unavailable: {e}")

    cb = (args.callback_url or "").strip()
    if cb:
        deny = webhook_url_allowed(cb, resolve_dns=False)
        if deny:
            return err(deny)

    try:
        job_id, job_secret = await create_queued_job({
            "source_path": path_val,
            "source_url": url_val,
            "engine": args.engine,
            "output_format": args.output_format if isinstance(args.output_format, list) else [args.output_format],
            "output_path": args.output_path.strip(),
            "callback_url": cb or None,
            "page_range": list(args.options.page_range) if args.options.page_range else None,
            "inline_max_bytes": args.options.inline_max_bytes,
            "include_inline": args.options.include_inline,
        })
    except Exception as e:
        logger.exception("create parse job failed")
        return err(f"Parse job store unavailable: {e}")

    return ok(job_id=job_id, job_secret=job_secret, status="queued")


handler = office_parse_document
