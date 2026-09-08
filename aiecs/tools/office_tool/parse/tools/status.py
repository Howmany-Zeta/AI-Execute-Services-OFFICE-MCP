"""office_parse_document_status — poll job (ADR-048)."""

from __future__ import annotations

import json
import logging
from typing import Any

from pydantic import ValidationError

from aiecs.tools.office_tool.core.errors import err, ok
from aiecs.tools.office_tool.core.parse_job import authenticate_job
from aiecs.tools.office_tool.core.storage import download_object_bytes
from aiecs.tools.office_tool.parse.schemas import ParseStatusArgs

logger = logging.getLogger(__name__)

TOOL_NAME = "office_parse_document_status"

TOOL_DEF = {
    "name": TOOL_NAME,
    "description": (
        "[Parse] Poll office_parse_document. Requires job_id and job_secret from submit. "
        "Default response is refs only; set include_inline to read objects under inline_max_bytes."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "job_id": {"type": "string"},
            "job_secret": {"type": "string"},
            "include_inline": {"type": "boolean"},
            "inline_max_bytes": {"type": "integer", "minimum": 1},
        },
        "required": ["job_id", "job_secret"],
    },
}


def _parse_json(raw: str) -> dict:
    if not raw:
        return {}
    try:
        return json.loads(raw)
    except json.JSONDecodeError:
        return {}


async def office_parse_document_status(
    job_id: str | None = None,
    job_secret: str | None = None,
    include_inline: bool = False,
    inline_max_bytes: int = 1_048_576,
    **kwargs: Any,
) -> dict[str, Any]:
    try:
        args = ParseStatusArgs.model_validate({
            "job_id": job_id,
            "job_secret": job_secret,
            "include_inline": include_inline,
            "inline_max_bytes": inline_max_bytes,
            **kwargs,
        })
    except ValidationError:
        return err("Job not found")

    job = await authenticate_job(args.job_id, args.job_secret)
    if not job:
        return err("Job not found")

    status = job.get("status") or "queued"
    result: dict[str, Any] = {"status": status}
    if status == "failed":
        result["error"] = job.get("error") or "failed"
        result["error_code"] = job.get("error_code") or "failed"
        return ok(**result)

    if status != "succeeded":
        return ok(**result)

    parser = _parse_json(job.get("parser_json") or "")
    canonical_ref = _parse_json(job.get("canonical_ref_json") or "")
    structure_ref = _parse_json(job.get("structure_ref_json") or "")
    result.update({"parser": parser, "canonical_ref": canonical_ref, "structure_ref": structure_ref})

    if args.include_inline:
        max_b = args.inline_max_bytes
        try:
            cpath = canonical_ref.get("output_path")
            if cpath and int(canonical_ref.get("bytes") or 0) <= max_b:
                data = await download_object_bytes(cpath, max_b)
                text = data.decode("utf-8")
                if cpath.endswith(".txt"):
                    result["text"] = text
                else:
                    result["markdown"] = text
            spath = structure_ref.get("output_path")
            if spath and int(structure_ref.get("bytes") or 0) <= max_b:
                sdata = await download_object_bytes(spath, max_b)
                result["structure"] = json.loads(sdata.decode("utf-8"))
        except Exception:
            logger.warning("include_inline read failed", exc_info=True)

    return ok(**result)


handler = office_parse_document_status
