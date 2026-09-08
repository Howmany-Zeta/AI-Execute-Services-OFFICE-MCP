"""Document AI Layout Parser client (ADR-048).

Online process and batch submit/poll are split so tools/call never waits on LRO.
google-cloud-documentai is imported lazily so unit tests can mock this module.
"""

from __future__ import annotations

import logging
from functools import lru_cache
from typing import Any, Optional

logger = logging.getLogger(__name__)

ONLINE_MAX_BYTES = 20 * 1024 * 1024
ONLINE_MAX_PAGES = 15
BATCH_MAX_PAGES = 500


class DocumentAIOnlineLimitError(Exception):
    """Online process rejected the PDF for page or file-size limits."""


class DocumentAIError(Exception):
    """Non-limit Document AI failure."""


def _processor_name(cfg) -> str:
    base = f"projects/{cfg.project}/locations/{cfg.location}/processors/{cfg.processor_id}"
    if cfg.processor_version.strip():
        return f"{base}/processorVersions/{cfg.processor_version.strip()}"
    return base


def _is_online_limit_error(exc: BaseException) -> bool:
    text = str(exc).lower()
    needles = ("page", "15", "20", "size", "limit", "too large", "exceed")
    return any(n in text for n in needles)


class DocumentAIClient:
    def __init__(self, cfg=None):
        from aiecs.config import get_documentai_config

        self.cfg = cfg or get_documentai_config()

    def _api_client(self):
        from google.cloud import documentai_v1 as documentai

        return documentai.DocumentProcessorServiceClient(
            client_options={"api_endpoint": f"{self.cfg.location}-documentai.googleapis.com"}
        )

    def _document_to_dict(self, document) -> dict[str, Any]:
        if hasattr(document, "_pb"):
            from google.protobuf.json_format import MessageToDict

            return MessageToDict(document._pb, preserving_proto_field_name=True)
        if isinstance(document, dict):
            return document
        return {"text": getattr(document, "text", "")}

    async def process_pdf_online(
        self,
        *,
        raw_bytes: bytes | None = None,
        gcs_uri: str | None = None,
        page_indexes: list[int] | None = None,
    ) -> dict[str, Any]:
        if not self.cfg.is_configured():
            raise DocumentAIError("DOCUMENT_AI_PROJECT and DOCUMENT_AI_PROCESSOR_ID are required")
        from google.cloud import documentai_v1 as documentai
        from google.api_core import exceptions as gexc

        request: dict[str, Any] = {"name": _processor_name(self.cfg)}
        if raw_bytes is not None:
            request["raw_document"] = documentai.RawDocument(content=raw_bytes, mime_type="application/pdf")
        elif gcs_uri:
            request["gcs_document"] = documentai.GcsDocument(gcs_uri=gcs_uri, mime_type="application/pdf")
        else:
            raise DocumentAIError("raw_bytes or gcs_uri is required")
        if page_indexes:
            request["process_options"] = documentai.ProcessOptions(
                individual_page_selector=documentai.ProcessOptions.IndividualPageSelector(
                    pages=[i + 1 for i in page_indexes]
                )
            )

        def _do():
            return self._api_client().process_document(request=request)

        try:
            import asyncio

            result = await asyncio.to_thread(_do)
        except Exception as e:
            if isinstance(e, gexc.InvalidArgument) or _is_online_limit_error(e):
                raise DocumentAIOnlineLimitError(str(e)) from e
            raise DocumentAIError(str(e)) from e
        return self._document_to_dict(result.document)

    async def submit_pdf_batch(self, gcs_uri: str, output_prefix: str) -> str:
        if not self.cfg.is_configured():
            raise DocumentAIError("DOCUMENT_AI_PROJECT and DOCUMENT_AI_PROCESSOR_ID are required")
        if not output_prefix.startswith("gs://"):
            raise DocumentAIError("batch output prefix must be gs://")
        from google.cloud import documentai_v1 as documentai

        request = documentai.BatchProcessRequest(
            name=_processor_name(self.cfg),
            input_documents=documentai.BatchDocumentsInputConfig(
                gcs_documents=documentai.GcsDocuments(
                    documents=[documentai.GcsDocument(gcs_uri=gcs_uri, mime_type="application/pdf")]
                )
            ),
            document_output_config=documentai.DocumentOutputConfig(
                gcs_output_config=documentai.DocumentOutputConfig.GcsOutputConfig(gcs_uri=output_prefix)
            ),
        )

        def _do():
            return self._api_client().batch_process_documents(request=request)

        import asyncio

        op = await asyncio.to_thread(_do)
        name = getattr(op, "operation", None)
        op_name = getattr(name, "name", None) or getattr(op, "name", None)
        if not op_name:
            raise DocumentAIError("batch_process_documents did not return an operation name")
        return str(op_name)

    async def poll_batch_operation(self, operation_name: str) -> Optional[dict[str, Any]]:
        """Return document dict when done, None if still running."""
        def _do():
            client = self._api_client()
            op = client.transport.operations_client.get_operation(name=operation_name)
            return op

        import asyncio

        op = await asyncio.to_thread(_do)
        done = bool(getattr(op, "done", False))
        if not done:
            return None
        if getattr(op, "error", None) and getattr(op.error, "code", 0):
            raise DocumentAIError(f"batch operation failed: {op.error}")
        return {"operation": operation_name, "done": True}

    async def load_batch_output_document(self, output_prefix: str) -> dict[str, Any]:
        """Load DocumentLayout JSON shards written under the batch GCS prefix."""
        import json

        from aiecs.tools.office_tool.core.storage import download_object_bytes, list_objects_under_prefix

        uris = [u for u in await list_objects_under_prefix(output_prefix) if u.lower().endswith(".json")]
        if not uris:
            return {"documentLayout": {"blocks": []}}
        merged_blocks: list[Any] = []
        text_parts: list[str] = []
        last: dict[str, Any] = {}
        for uri in uris:
            raw = await download_object_bytes(uri, 80 * 1024 * 1024)
            doc = json.loads(raw.decode("utf-8"))
            if not isinstance(doc, dict):
                continue
            last = doc
            layout = doc.get("documentLayout") or doc.get("document_layout") or {}
            merged_blocks.extend(layout.get("blocks") or [])
            if doc.get("text"):
                text_parts.append(str(doc["text"]))
        if merged_blocks:
            return {"documentLayout": {"blocks": merged_blocks}}
        if text_parts:
            return {"text": "\n".join(text_parts)}
        return last


@lru_cache()
def get_documentai_client() -> DocumentAIClient:
    return DocumentAIClient()
