"""Document AI batch submit/poll shared by parse jobs and read fallback."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from aiecs.clients.documentai_client import DocumentAIError, get_documentai_client
from aiecs.config import get_documentai_config, get_parse_job_config
from aiecs.tools.office_tool.core.storage import (
    download_object_bytes,
    delete_object,
    delete_prefix,
    upload_to_storage,
)

logger = logging.getLogger(__name__)

OnOperation = Callable[[str], Awaitable[None]]


def document_has_structure(document: dict[str, Any] | None) -> bool:
    if not isinstance(document, dict) or not document:
        return False
    layout = document.get("documentLayout") or document.get("document_layout") or {}
    if isinstance(layout, dict) and layout.get("blocks"):
        return True
    if str(document.get("text") or "").strip():
        return True
    pages = document.get("pages")
    return isinstance(pages, list) and bool(pages)


def batch_out_prefix(work_id: str) -> str:
    return get_documentai_config().batch_output_prefix.rstrip("/") + f"/out/{work_id}/"


def batch_staging_uri(work_id: str) -> str:
    return get_documentai_config().batch_output_prefix.rstrip("/") + f"/staging/{work_id}.pdf"


async def cleanup_dai_io(work_id: str, staging: str | None = None) -> None:
    dai_cfg = get_documentai_config()
    if not dai_cfg.batch_output_prefix:
        return
    try:
        if staging:
            await delete_object(staging)
        else:
            await delete_object(batch_staging_uri(work_id))
        await delete_prefix(batch_out_prefix(work_id))
    except Exception:
        logger.warning("DAI staging cleanup failed for %s", work_id, exc_info=True)


async def poll_batch_until_done(
    client,
    work_id: str,
    operation: str,
    *,
    timeout_sec: float | None = None,
) -> dict[str, Any]:
    elapsed = 0.0
    while True:
        done = await client.poll_batch_operation(operation)
        if done:
            document = done
            if not (
                done.get("documentLayout") or done.get("document_layout") or done.get("text")
            ):
                document = await client.load_batch_output_document(batch_out_prefix(work_id))
            await cleanup_dai_io(work_id)
            return document
        if timeout_sec is not None and elapsed >= timeout_sec:
            raise DocumentAIError(f"Document AI batch timed out after {timeout_sec}s")
        await asyncio.sleep(2.0)
        elapsed += 2.0


async def process_pdf_batch(
    *,
    source_path: str,
    data: bytes | None,
    work_id: str,
    client=None,
    on_operation: OnOperation | None = None,
    timeout_sec: float | None = None,
) -> dict[str, Any]:
    """Submit batch_process_documents and poll until a document dict is ready."""
    dai_cfg = get_documentai_config()
    if not dai_cfg.batch_output_prefix:
        raise RuntimeError("DOCUMENT_AI_BATCH_OUTPUT_PREFIX is required for batch")
    cfg = get_parse_job_config()
    client = client or get_documentai_client()
    gcs_uri = source_path if source_path.startswith("gs://") else None
    staging = None
    if not gcs_uri:
        if data is None:
            data = await download_object_bytes(source_path, cfg.max_source_bytes)
        staging = batch_staging_uri(work_id)
        if not staging.startswith(dai_cfg.batch_output_prefix.rstrip("/")):
            raise RuntimeError("staging path must stay under DOCUMENT_AI_BATCH_OUTPUT_PREFIX")
        await upload_to_storage(data, staging)
        gcs_uri = staging
    op = await client.submit_pdf_batch(gcs_uri, batch_out_prefix(work_id))
    if on_operation:
        await on_operation(op)
    return await poll_batch_until_done(client, work_id, op, timeout_sec=timeout_sec)
