"""
format=structured dispatch for office_read_document.

Word / presentation: Document Builder sidecar.
PDF: Document AI online, then batch, then PDF_PAGE_EXTRACT_BODY, then isError.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Optional

import httpx

from aiecs.clients.documentai_client import (
    BATCH_MAX_PAGES,
    DocumentAIError,
    DocumentAIOnlineLimitError,
    get_documentai_client,
    online_max_bytes,
)
from aiecs.clients.documentserver_client import DocumentServerClient
from aiecs.tools.office_tool.core.builder_json_sidecar import read_sidecar_json
from aiecs.tools.office_tool.core.categories import (
    STRUCTURED_BUILDER_PRESENTATION_EXTS,
    STRUCTURED_BUILDER_WORD_EXTS,
    STRUCTURED_DOCUMENT_AI_EXTS,
)
from aiecs.tools.office_tool.core.dai_batch import document_has_structure, process_pdf_batch
from aiecs.tools.office_tool.core.errors import err
from aiecs.tools.office_tool.core.pdf_pages import estimate_pdf_pages
from aiecs.tools.office_tool.core.storage import (
    ACCEPTED_SOURCE_PATH_FORMATS,
    SourceTooLargeError,
    download_object_bytes,
    stat_object_size,
)
from aiecs.tools.office_tool.pdf.parser.document import PDF_PAGE_EXTRACT_BODY, parse_document_json
from aiecs.tools.office_tool.pdf.parser.structured import (
    builder_pages_to_elements,
    layout_to_elements,
    pdf_page_count,
    pdf_title_from_elements,
    word_count_from_pdf_elements,
)
from aiecs.tools.office_tool.presentation.parser.structured import (
    STRUCTURED_PRESENTATION_EXTRACT_BODY,
    PresentationStructuredError,
    normalize_presentation_structured,
    presentation_title_from_elements,
    word_count_from_presentation,
)
from aiecs.tools.office_tool.word.parser.structured import (
    STRUCTURED_WORD_EXTRACT_BODY,
    normalize_word_structured,
    word_count_from_elements,
    word_page_count,
    word_title_from_elements,
)

logger = logging.getLogger(__name__)

# tools/call budget for Document AI batch LRO (parse jobs may poll longer).
_READ_BATCH_TIMEOUT_SEC = 600.0

INDEX_NOTE = (
    "index is logical order only, NOT for Builder GetElement(i). "
    "Use Search(text) or GetStyleName() for positioning in office_edit_document."
)


def uses_structured_builder(file_ext: str) -> bool:
    ext = (file_ext or "").lower().lstrip(".")
    return ext in STRUCTURED_BUILDER_WORD_EXTS or ext in STRUCTURED_BUILDER_PRESENTATION_EXTS


def uses_structured_document_ai(file_ext: str) -> bool:
    return (file_ext or "").lower().lstrip(".") in STRUCTURED_DOCUMENT_AI_EXTS


def _meta(
    *,
    source_path_format: str,
    storage_path: str,
    conversion_output_type: str,
) -> dict[str, Any]:
    meta = {
        "source_path_format": source_path_format,
        "accepted_source_path_formats": ACCEPTED_SOURCE_PATH_FORMATS,
        "conversion_output_type": conversion_output_type,
        "_note": INDEX_NOTE,
    }
    if storage_path:
        meta["source_path"] = storage_path
    return meta


async def read_word_structured(
    *,
    source_path: str | None,
    source_url: str | None,
    file_ext: str,
    storage_path: str,
    source_path_format: str,
    client: DocumentServerClient | None = None,
    fetch_url: str | None = None,
) -> dict[str, Any]:
    parsed, sidecar_err = await read_sidecar_json(
        source_path,
        source_url,
        file_ext,
        STRUCTURED_WORD_EXTRACT_BODY,
        client=client,
        fetch_url=fetch_url,
    )
    if sidecar_err:
        return err(sidecar_err)
    normalized = normalize_word_structured(parsed or {})
    elements = normalized["elements"]
    return {
        "title": word_title_from_elements(elements),
        "elements": elements,
        "word_count": word_count_from_elements(elements),
        "page_count": word_page_count(elements),
        **_meta(
            source_path_format=source_path_format,
            storage_path=storage_path,
            conversion_output_type="builder_json",
        ),
    }


async def read_presentation_structured(
    *,
    source_path: str | None,
    source_url: str | None,
    file_ext: str,
    storage_path: str,
    source_path_format: str,
    client: DocumentServerClient | None = None,
    fetch_url: str | None = None,
) -> dict[str, Any]:
    parsed, sidecar_err = await read_sidecar_json(
        source_path,
        source_url,
        file_ext,
        STRUCTURED_PRESENTATION_EXTRACT_BODY,
        client=client,
        fetch_url=fetch_url,
    )
    if sidecar_err:
        return err(sidecar_err)
    try:
        normalized = normalize_presentation_structured(parsed or {})
    except PresentationStructuredError as exc:
        return err(str(exc))
    elements = normalized["elements"]
    slides = normalized["slides"]
    return {
        "title": presentation_title_from_elements(elements),
        "elements": elements,
        "slides": slides,
        "word_count": word_count_from_presentation(elements),
        "page_count": len(slides),
        **_meta(
            source_path_format=source_path_format,
            storage_path=storage_path,
            conversion_output_type="builder_json",
        ),
    }


async def _load_pdf_bytes(path_val: str, fetch_url: str) -> tuple[bytes | None, int | None, str | None]:
    """Return (data, size, oversize_reason). oversize_reason set when over PARSE_MAX_SOURCE_BYTES."""
    max_bytes = online_max_bytes()
    try:
        if path_val.startswith("gs://") or path_val.startswith("s3://"):
            size = await stat_object_size(path_val)
            if size > max_bytes:
                return None, size, "oversize"
            data = await download_object_bytes(path_val, max_bytes)
            return data, size, None
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as http_client:
            response = await http_client.get(fetch_url)
            response.raise_for_status()
            data = response.content
        if len(data) > max_bytes:
            return None, len(data), "oversize"
        return data, len(data), None
    except SourceTooLargeError:
        return None, None, "oversize"
    except Exception as exc:
        return None, None, str(exc)


async def _pdf_builder_fallback(
    *,
    source_path: str | None,
    source_url: str | None,
    file_ext: str,
    storage_path: str,
    source_path_format: str,
    client: DocumentServerClient | None,
    fetch_url: str | None = None,
) -> dict[str, Any]:
    parsed, sidecar_err = await read_sidecar_json(
        source_path,
        source_url,
        file_ext,
        PDF_PAGE_EXTRACT_BODY,
        client=client,
        fetch_url=fetch_url,
    )
    if sidecar_err:
        return err(sidecar_err)
    pages = parse_document_json(parsed or {})
    elements = builder_pages_to_elements(pages)
    return {
        "title": pdf_title_from_elements(elements),
        "elements": elements,
        "word_count": word_count_from_pdf_elements(elements),
        "page_count": pdf_page_count(elements),
        **_meta(
            source_path_format=source_path_format,
            storage_path=storage_path,
            conversion_output_type="builder_json",
        ),
    }


def _pdf_layout_result(
    document: dict[str, Any],
    *,
    storage_path: str,
    source_path_format: str,
    document_ai_mode: str,
) -> dict[str, Any] | None:
    if not document_has_structure(document):
        return None
    elements = layout_to_elements(document)
    if not elements:
        return None
    return {
        "title": pdf_title_from_elements(elements),
        "elements": elements,
        "word_count": word_count_from_pdf_elements(elements),
        "page_count": pdf_page_count(elements),
        "document_ai_mode": document_ai_mode,
        **_meta(
            source_path_format=source_path_format,
            storage_path=storage_path,
            conversion_output_type="document_layout",
        ),
    }


async def _pdf_batch_document(path_val: str, data: bytes | None) -> dict[str, Any]:
    return await process_pdf_batch(
        source_path=path_val,
        data=data,
        work_id=f"read-{uuid.uuid4().hex}",
        timeout_sec=_READ_BATCH_TIMEOUT_SEC,
    )


async def read_pdf_structured(
    *,
    source_path: str | None,
    source_url: str | None,
    file_ext: str,
    fetch_url: str,
    storage_path: str,
    source_path_format: str,
    client: DocumentServerClient | None = None,
) -> dict[str, Any]:
    path_val = (source_path or "").strip()
    builder_kw = dict(
        source_path=source_path,
        source_url=source_url,
        file_ext=file_ext,
        storage_path=storage_path,
        source_path_format=source_path_format,
        client=client,
        fetch_url=fetch_url,
    )

    async def _builder() -> dict[str, Any]:
        return await _pdf_builder_fallback(**builder_kw)

    data, _size, load_err = await _load_pdf_bytes(path_val, fetch_url)
    if load_err == "oversize":
        return await _builder()
    if load_err:
        return err(load_err)
    if data is None:
        return err("Failed to load PDF bytes")

    pages_est = estimate_pdf_pages(data)
    if pages_est is not None and pages_est > BATCH_MAX_PAGES:
        return await _builder()

    try:
        from aiecs.config import get_documentai_config

        if not get_documentai_config().is_configured():
            return err("DOCUMENT_AI_PROJECT and DOCUMENT_AI_PROCESSOR_ID are required")
        document = await get_documentai_client().process_pdf_online(raw_bytes=data)
    except DocumentAIOnlineLimitError:
        try:
            document = await _pdf_batch_document(path_val, data)
        except Exception:
            logger.exception("PDF structured Document AI batch fallback failed")
            return await _builder()
        batched = _pdf_layout_result(
            document,
            storage_path=storage_path,
            source_path_format=source_path_format,
            document_ai_mode="batch",
        )
        return batched if batched is not None else await _builder()
    except DocumentAIError as exc:
        return err(str(exc))
    except Exception as exc:
        logger.exception("PDF structured Document AI failed")
        return err(str(exc))

    online = _pdf_layout_result(
        document,
        storage_path=storage_path,
        source_path_format=source_path_format,
        document_ai_mode="online",
    )
    if online is not None:
        return online
    try:
        document = await _pdf_batch_document(path_val, data)
    except Exception:
        logger.exception("PDF structured Document AI batch fallback failed")
        return await _builder()
    batched = _pdf_layout_result(
        document,
        storage_path=storage_path,
        source_path_format=source_path_format,
        document_ai_mode="batch",
    )
    return batched if batched is not None else await _builder()


async def structured_read_legacy(
    *,
    file_ext: str,
    fetch_url: str,
    storage_path: str,
    source_path_format: str,
    source_path: str | None,
    source_url: str | None,
    client: Optional[DocumentServerClient] = None,
) -> dict[str, Any] | None:
    """
    Return structured payload for covered extensions, else None (caller uses Conversion).
    """
    ext = (file_ext or "").lower().lstrip(".")
    if ext in STRUCTURED_BUILDER_WORD_EXTS:
        return await read_word_structured(
            source_path=source_path,
            source_url=source_url,
            file_ext=ext,
            storage_path=storage_path,
            source_path_format=source_path_format,
            client=client,
            fetch_url=fetch_url,
        )
    if ext in STRUCTURED_BUILDER_PRESENTATION_EXTS:
        return await read_presentation_structured(
            source_path=source_path,
            source_url=source_url,
            file_ext=ext,
            storage_path=storage_path,
            source_path_format=source_path_format,
            client=client,
            fetch_url=fetch_url,
        )
    if ext in STRUCTURED_DOCUMENT_AI_EXTS:
        return await read_pdf_structured(
            source_path=source_path,
            source_url=source_url,
            file_ext=ext,
            fetch_url=fetch_url,
            storage_path=storage_path,
            source_path_format=source_path_format,
            client=client,
        )
    return None
