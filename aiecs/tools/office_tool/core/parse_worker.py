"""In-process parse worker (ADR-048)."""

from __future__ import annotations

import asyncio
import hashlib
import json
import logging
from typing import Any

from aiecs.config import get_documentai_config, get_parse_job_config
from aiecs.clients.documentai_client import (
    BATCH_MAX_PAGES,
    ONLINE_MAX_BYTES,
    ONLINE_MAX_PAGES,
    DocumentAIOnlineLimitError,
    get_documentai_client,
)
from aiecs.tools.office_tool.core.coarse_read import convert_and_fetch
from aiecs.tools.office_tool.core.parse_job import (
    claim_next_job_id,
    load_job,
    recover_stale_running,
    update_job,
)
from aiecs.tools.office_tool.core.parse_routing import parse_file_ext, route_parse_engine
from aiecs.tools.office_tool.core.parse_security import (
    output_path_allowed,
    post_webhook,
    structure_sidecar_path,
)
from aiecs.tools.office_tool.core.pdf_pages import estimate_pdf_pages
from aiecs.tools.office_tool.core.projectors import structure_to_markdown, structure_to_text
from aiecs.tools.office_tool.core.storage import (
    SourceTooLargeError,
    delete_object,
    delete_prefix,
    download_object_bytes,
    stat_object_size,
    upload_to_storage,
)
from aiecs.tools.office_tool.core.source import resolve_document_source

logger = logging.getLogger(__name__)

_worker_task: asyncio.Task | None = None
_stop = asyncio.Event()


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def _page_range_span(page_range: list[int] | None) -> int | None:
    if not page_range or len(page_range) != 2:
        return None
    start, end = int(page_range[0]), int(page_range[1])
    return abs(end - start) + 1


async def _load_source_bytes(source_path: str, source_url: str, max_bytes: int) -> tuple[bytes, str]:
    if source_path:
        data = await download_object_bytes(source_path, max_bytes)
        return data, parse_file_ext(source_path)
    import httpx

    async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
        head = await client.head(source_url)
        cl = head.headers.get("Content-Length")
        if cl and int(cl) > max_bytes:
            raise SourceTooLargeError(f"source_too_large: {cl} > {max_bytes}")
        resp = await client.get(source_url)
        resp.raise_for_status()
        data = resp.content
    if len(data) > max_bytes:
        raise SourceTooLargeError(f"source_too_large: {len(data)} > {max_bytes}")
    return data, parse_file_ext(source_url)


def _ds_structure(ext: str, content: str, output_type: str) -> list[dict[str, Any]]:
    if output_type == "html":
        from aiecs.tools.office_tool.word.parser.html import parse_html_to_structure

        parsed = parse_html_to_structure(content)
        blocks = []
        for el in parsed.get("elements") or []:
            blocks.append({
                "block_index": len(blocks),
                "type": el.get("type", "paragraph"),
                "text": el.get("text", ""),
            })
        return [{"kind": "section", "blocks": blocks}]
    if ext in {"ppt", "pptx", "pptm", "odp", "otp", "pps", "ppsx"}:
        from aiecs.tools.office_tool.presentation.parser.txt import parse_txt_to_structure

        parsed = parse_txt_to_structure(content)
        units = []
        for el in parsed.get("elements") or []:
            units.append({
                "kind": "slide",
                "slide_index": el.get("index", len(units)),
                "blocks": [{"block_index": 0, "type": "paragraph", "text": el.get("text", "")}],
            })
        return units or [{"kind": "slide", "slide_index": 0, "blocks": [{"block_index": 0, "type": "paragraph", "text": content[:5000]}]}]
    return [{"kind": "section", "blocks": [{"block_index": 0, "type": "paragraph", "text": content}]}]


async def _write_outputs(output_path: str, formats: list[str], structure: list[dict], markdown: str, text: str, source_path: str | None = None) -> tuple[dict, dict]:
    deny = output_path_allowed(output_path, source_path)
    if deny:
        raise PermissionError(deny)
    body = markdown
    if "text" in formats and "markdown" not in formats:
        body = text
    raw = body.encode("utf-8")
    await upload_to_storage(raw, output_path)
    struct_bytes = json.dumps(structure, ensure_ascii=False).encode("utf-8")
    sidecar = structure_sidecar_path(output_path)
    side_deny = output_path_allowed(sidecar, source_path)
    if side_deny:
        raise PermissionError(side_deny)
    await upload_to_storage(struct_bytes, sidecar)
    canonical_ref = {
        "storage": "object",
        "output_path": output_path,
        "sha256": _sha256(raw),
        "bytes": len(raw),
    }
    structure_ref = {
        "storage": "object",
        "output_path": sidecar,
        "sha256": _sha256(struct_bytes),
        "bytes": len(struct_bytes),
    }
    return canonical_ref, structure_ref


async def _run_documentserver(fetch_url: str, ext: str) -> list[dict[str, Any]]:
    from aiecs.tools.office_tool.core.categories import llm_coarse_output_type

    output_type = llm_coarse_output_type(ext)
    content, error = await convert_and_fetch(fetch_url, ext, output_type)
    if error:
        raise RuntimeError(error)
    return _ds_structure(ext, content or "", output_type)


def _batch_out_prefix(job_id: str) -> str:
    dai_cfg = get_documentai_config()
    return dai_cfg.batch_output_prefix.rstrip("/") + f"/out/{job_id}/"


def _batch_staging_uri(job_id: str) -> str:
    dai_cfg = get_documentai_config()
    return dai_cfg.batch_output_prefix.rstrip("/") + f"/staging/{job_id}.pdf"


async def _cleanup_dai_io(job_id: str, staging: str | None = None) -> None:
    dai_cfg = get_documentai_config()
    if not dai_cfg.batch_output_prefix:
        return
    try:
        if staging:
            await delete_object(staging)
        else:
            await delete_object(_batch_staging_uri(job_id))
        await delete_prefix(_batch_out_prefix(job_id))
    except Exception:
        logger.warning("DAI staging cleanup failed for %s", job_id, exc_info=True)


async def _document_from_batch_result(client, done: dict[str, Any], job_id: str) -> dict[str, Any]:
    if done.get("documentLayout") or done.get("document_layout") or done.get("text"):
        return done
    return await client.load_batch_output_document(_batch_out_prefix(job_id))


async def _poll_batch_until_done(client, job_id: str, operation: str) -> dict[str, Any]:
    while True:
        done = await client.poll_batch_operation(operation)
        if done:
            document = await _document_from_batch_result(client, done, job_id)
            await _cleanup_dai_io(job_id)
            return document
        await asyncio.sleep(2.0)


async def _resume_document_ai(job_id: str, operation: str) -> list[dict[str, Any]]:
    from aiecs.tools.office_tool.pdf.parser.document_ai import layout_to_pages, pages_to_structure

    client = get_documentai_client()
    document = await _poll_batch_until_done(client, job_id, operation)
    return pages_to_structure(layout_to_pages(document))


async def _run_document_ai(job_id: str, source_path: str, data: bytes | None, page_range: list[int] | None) -> list[dict[str, Any]]:
    cfg = get_parse_job_config()
    dai_cfg = get_documentai_config()
    if not dai_cfg.is_configured():
        raise RuntimeError("document_ai_not_configured")
    client = get_documentai_client()
    size = len(data) if data is not None else (await stat_object_size(source_path) if source_path.startswith("gs://") or source_path.startswith("s3://") else 0)
    pages = estimate_pdf_pages(data) if data else None
    span = _page_range_span(page_range)
    if pages is not None and pages > BATCH_MAX_PAGES and (span is None or span > BATCH_MAX_PAGES):
        raise RuntimeError("page_limit_exceeded")
    if size > cfg.max_source_bytes:
        raise SourceTooLargeError(f"source_too_large: {size} > {cfg.max_source_bytes}")

    use_online = size <= ONLINE_MAX_BYTES and (pages is None or pages <= ONLINE_MAX_PAGES) and (span is None or span <= ONLINE_MAX_PAGES)
    page_indexes = None
    if page_range and len(page_range) == 2:
        page_indexes = list(range(int(page_range[0]), int(page_range[1]) + 1))

    if use_online:
        try:
            gcs_uri = source_path if source_path.startswith("gs://") else None
            raw = None if gcs_uri else data
            from aiecs.tools.office_tool.pdf.parser.document_ai import layout_to_pages, pages_to_structure

            document = await client.process_pdf_online(raw_bytes=raw, gcs_uri=gcs_uri, page_indexes=page_indexes)
            return pages_to_structure(layout_to_pages(document))
        except DocumentAIOnlineLimitError:
            if size > cfg.max_source_bytes:
                raise
            if pages is not None and pages > BATCH_MAX_PAGES:
                raise RuntimeError("page_limit_exceeded")
            # one batch fallback only

    if not dai_cfg.batch_output_prefix:
        raise RuntimeError("DOCUMENT_AI_BATCH_OUTPUT_PREFIX is required for batch")
    gcs_uri = source_path if source_path.startswith("gs://") else None
    staging = None
    if not gcs_uri:
        if data is None:
            data = await download_object_bytes(source_path, cfg.max_source_bytes)
        staging = _batch_staging_uri(job_id)
        if not staging.startswith(dai_cfg.batch_output_prefix.rstrip("/")):
            raise RuntimeError("staging path must stay under DOCUMENT_AI_BATCH_OUTPUT_PREFIX")
        await upload_to_storage(data, staging)
        gcs_uri = staging
    out_prefix = _batch_out_prefix(job_id)
    op = await client.submit_pdf_batch(gcs_uri, out_prefix)
    await update_job(job_id, operation=op)
    from aiecs.tools.office_tool.pdf.parser.document_ai import layout_to_pages, pages_to_structure

    document = await _poll_batch_until_done(client, job_id, op)
    return pages_to_structure(layout_to_pages(document))


async def run_parse_job(job_id: str) -> None:
    job = await load_job(job_id)
    if not job:
        return
    if job.get("status") in {"succeeded", "failed"}:
        return
    existing_op = (job.get("operation") or "").strip()
    if not existing_op:
        await update_job(job_id, status="running")
    payload = json.loads(job.get("payload") or "{}")
    try:
        source_path = (payload.get("source_path") or "").strip()
        source_url = (payload.get("source_url") or "").strip()
        ext = parse_file_ext(source_path or source_url)
        engine, route_err = route_parse_engine(ext, payload.get("engine") or "auto")
        if route_err:
            await update_job(job_id, status="failed", error_code=route_err, error=route_err)
            return
        cfg = get_parse_job_config()
        data = None
        fetch_url = ""
        if engine == "documentserver":
            resolved = await resolve_document_source(source_path, source_url)
            if isinstance(resolved, dict):
                await update_job(job_id, status="failed", error_code="resolve_failed", error=resolved.get("text", "resolve failed"))
                return
            fetch_url, ext, _, _ = resolved
            structure = await _run_documentserver(fetch_url, ext)
            parser = {"name": "documentserver", "version": "conversion"}
        elif existing_op:
            structure = await _resume_document_ai(job_id, existing_op)
            parser = {"name": "document_ai", "version": get_documentai_config().processor_version or "default"}
        else:
            if source_path.startswith("s3://") or (source_path.startswith("gs://") is False and source_url):
                data, _ = await _load_source_bytes(source_path, source_url, cfg.max_source_bytes)
            elif source_path.startswith("gs://"):
                size = await stat_object_size(source_path)
                if size > cfg.max_source_bytes:
                    raise SourceTooLargeError(f"source_too_large: {size} > {cfg.max_source_bytes}")
                if size <= ONLINE_MAX_BYTES:
                    data = await download_object_bytes(source_path, cfg.max_source_bytes)
            structure = await _run_document_ai(job_id, source_path, data, payload.get("page_range"))
            parser = {"name": "document_ai", "version": get_documentai_config().processor_version or "default"}

        markdown = structure_to_markdown(structure)
        text = structure_to_text(structure)
        formats = payload.get("output_format") or ["markdown", "structured"]
        if isinstance(formats, str):
            formats = [formats]
        canonical_ref, structure_ref = await _write_outputs(
            payload["output_path"], formats, structure, markdown, text, source_path or None
        )
        await update_job(
            job_id,
            status="succeeded",
            parser_json=json.dumps(parser),
            canonical_ref_json=json.dumps(canonical_ref),
            structure_ref_json=json.dumps(structure_ref),
        )
        callback = (payload.get("callback_url") or "").strip()
        if callback:
            await post_webhook(callback, {
                "job_id": job_id,
                "status": "succeeded",
                "canonical_ref": canonical_ref,
                "sha256": canonical_ref.get("sha256"),
            })
    except SourceTooLargeError as e:
        await update_job(job_id, status="failed", error_code="source_too_large", error=str(e))
    except Exception as e:
        code = "page_limit_exceeded" if "page_limit_exceeded" in str(e) else "retryable" if "timeout" in str(e).lower() else "failed"
        logger.exception("parse job failed")
        await update_job(job_id, status="failed", error_code=code, error=str(e)[:500])


async def worker_loop() -> None:
    await recover_stale_running()
    while not _stop.is_set():
        job_id = await claim_next_job_id()
        if not job_id:
            try:
                await asyncio.wait_for(_stop.wait(), timeout=0.5)
            except asyncio.TimeoutError:
                pass
            continue
        try:
            await run_parse_job(job_id)
        except Exception:
            logger.exception("worker crashed on job")


def start_parse_worker() -> None:
    global _worker_task
    _stop.clear()
    _worker_task = asyncio.create_task(worker_loop(), name="office-parse-worker")


async def stop_parse_worker() -> None:
    global _worker_task
    _stop.set()
    if _worker_task:
        _worker_task.cancel()
        try:
            await _worker_task
        except (asyncio.CancelledError, Exception):
            pass
        _worker_task = None
