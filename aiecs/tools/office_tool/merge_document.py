"""
office_merge_documents: Merge multiple documents via DocumentServer Builder.

Python generates Builder script: OpenFile each source, ToJSON content, then CreateFile
and merge via ReplaceDocumentContent + Push. Supports add_page_break and add_toc.
"""

import logging
from typing import Any, Dict, List, Optional

import httpx

from aiecs.clients.documentserver_client import (
    DocumentServerClient,
    get_documentserver_client,
    BUILDER_TIMEOUT,
)
from aiecs.tools.office_tool.docbuilder_script import script_to_url
from aiecs.tools.office_tool.storage import (
    get_signed_url,
    upload_to_storage,
    get_file_ext,
    SIGNED_URL_EXPIRY_SECONDS,
)

logger = logging.getLogger(__name__)


def _escape_js(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r")


def _build_merge_script(
    signed_urls: List[str],
    file_exts: List[str],
    add_page_break: bool,
    add_toc: bool,
) -> str:
    """
    Generate Builder script to merge documents.

    Flow: Open each source, store doc.ToJSON in GlobalVariable, then CreateFile,
    ReplaceDocumentContent(first), Push each subsequent doc's elements with optional page break.
    If add_toc, add table of contents at start after all content.
    """
    lines: List[str] = []

    # Phase 1: collect each document's content as JSON
    for i, (url, ext) in enumerate(zip(signed_urls, file_exts)):
        lines.append(f'builder.OpenFile("{_escape_js(url)}", "{ext}");')
        lines.append("var doc = Api.GetDocument();")
        lines.append('GlobalVariable["merge_' + str(i) + '"] = doc.ToJSON(true, true, true, true, true, true);')
        lines.append("builder.CloseFile();")
        lines.append("")

    # Phase 2: create merged document
    lines.append('builder.CreateFile("docx");')
    lines.append("var doc = Api.GetDocument();")
    lines.append('var content0 = Api.FromJSON(GlobalVariable["merge_0"]);')
    lines.append("Api.ReplaceDocumentContent(content0);")
    lines.append("")

    for i in range(1, len(signed_urls)):
        if add_page_break:
            lines.append("var pageBreakPara = Api.CreateParagraph();")
            lines.append("var pageBreakRun = Api.CreateRun();")
            lines.append("pageBreakRun.AddPageBreak();")
            lines.append("pageBreakPara.AddElement(pageBreakRun);")
            lines.append("doc.Push(pageBreakPara);")
            lines.append("")
        lines.append('var content = Api.FromJSON(GlobalVariable["merge_' + str(i) + '"]);')
        lines.append("var elements = content.GetContent(false);")
        lines.append("for (var j = 0; j < elements.length; j++) { doc.Push(elements[j]); }")
        lines.append("")

    if add_toc:
        lines.append("doc.MoveCursorToStart();")
        lines.append("doc.AddTableOfContents({});")
        lines.append("")

    lines.append('builder.SaveFile("docx", "output.docx");')
    lines.append("builder.CloseFile();")

    return "\n".join(lines)


def _is_http_url(s: str) -> bool:
    s = (s or "").strip()
    return s.startswith("http://") or s.startswith("https://")


OFFICE_MERGE_DOCUMENTS_TOOL = {
    "name": "office_merge_documents",
    "description": (
        "Merge multiple documents into one output file. Provide source_paths (GCS gs://) OR source_urls (HTTP/HTTPS). "
        "Documents are merged in order. Options: add_page_break, add_toc."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "source_paths": {
                "type": "array",
                "items": {"type": "string"},
                "description": "GCS paths (gs://bucket/path/file.docx). Optional if source_urls provided.",
            },
            "source_urls": {
                "type": "array",
                "items": {"type": "string"},
                "description": "HTTP/HTTPS URLs to documents. Optional if source_paths provided.",
            },
            "output_path": {
                "type": "string",
                "description": "Output path (gs:// or local)",
            },
            "options": {
                "type": "object",
                "properties": {
                    "add_page_break": {"type": "boolean"},
                    "add_toc": {"type": "boolean"},
                },
                "description": "Optional. add_page_break, add_toc",
            },
        },
        "required": ["output_path"],
    },
}


async def office_merge_documents(
    output_path: str,
    source_paths: Optional[List[str]] = None,
    source_urls: Optional[List[str]] = None,
    options: Optional[Dict[str, Any]] = None,
    client: Optional[DocumentServerClient] = None,
) -> Dict[str, Any]:
    """
    Merge multiple documents into one output file.

    Args:
        source_paths: GCS paths (gs://bucket/path). Optional if source_urls provided.
        source_urls: HTTP/HTTPS URLs to documents. Optional if source_paths provided.
        output_path: Output path (gs:// or local)
        options: Optional {"add_page_break": True, "add_toc": True}
        client: Optional DocumentServerClient

    Returns:
        {"success": True, "output_path"} or {"isError": True, "text": str}
    """
    paths = source_paths or []
    urls = source_urls or []
    if not isinstance(paths, list):
        paths = []
    if not isinstance(urls, list):
        urls = []

    if paths and urls:
        return {"isError": True, "text": "Provide source_paths OR source_urls, not both"}
    if not paths and not urls:
        return {"isError": True, "text": "Provide source_paths (gs://) or source_urls (HTTP/HTTPS)"}
    if not output_path or not output_path.strip():
        return {"isError": True, "text": "output_path is required"}

    sources = paths if paths else urls
    use_gcs = bool(paths)

    for p in sources:
        if not p or not str(p).strip():
            return {"isError": True, "text": "Each source must be non-empty"}
        if use_gcs and not str(p).startswith("gs://"):
            return {"isError": True, "text": f"source_paths must be GCS paths (gs://): {p}"}
        if not use_gcs and not _is_http_url(str(p)):
            return {"isError": True, "text": f"source_urls must be HTTP/HTTPS URLs: {p}"}

    opts = options or {}
    add_page_break = bool(opts.get("add_page_break"))
    add_toc = bool(opts.get("add_toc"))

    ds_client = client or get_documentserver_client()

    try:
        fetch_urls: List[str] = []
        file_exts: List[str] = []
        for item in sources:
            if use_gcs:
                url = await get_signed_url(item, expiry_seconds=SIGNED_URL_EXPIRY_SECONDS)
                fetch_urls.append(url)
                file_exts.append(get_file_ext(item))
            else:
                fetch_urls.append(item)
                file_exts.append(get_file_ext(item))
    except Exception as e:
        return {"isError": True, "text": f"Failed to resolve sources: {e}"}

    signed_urls = fetch_urls

    script = _build_merge_script(signed_urls, file_exts, add_page_break, add_toc)

    try:
        script_url = await script_to_url(script)
        result = await ds_client.execute_builder(url=script_url)
    except httpx.HTTPStatusError as e:
        logger.error(f"DocumentServer Builder error: {e}")
        return {"isError": True, "text": f"DocumentServer error: {e.response.status_code} {e.response.text[:500]}"}
    except httpx.TimeoutException:
        return {"isError": True, "text": f"DocumentServer timeout (>{BUILDER_TIMEOUT}s)"}
    except Exception as e:
        logger.exception("office_merge_documents Builder failed")
        return {"isError": True, "text": str(e)}

    file_url = result.get("fileUrl")
    if not file_url:
        return {"isError": True, "text": "DocumentServer did not return fileUrl"}

    try:
        async with httpx.AsyncClient(timeout=BUILDER_TIMEOUT) as http_client:
            response = await http_client.get(file_url)
            response.raise_for_status()
            content = response.content

        await upload_to_storage(content, output_path)
        return {"success": True, "output_path": output_path}
    except Exception as e:
        logger.exception(f"Failed to download/upload to {output_path}")
        return {"isError": True, "text": str(e)}
