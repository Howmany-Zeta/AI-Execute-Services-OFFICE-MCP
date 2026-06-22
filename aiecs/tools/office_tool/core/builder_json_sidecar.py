"""
Builder JSON sidecar extraction for fine read (word/presentation/spreadsheet/pdf).
"""

import json
import logging
from typing import Optional, Tuple

import httpx

from aiecs.clients.documentserver_client import (
    DocumentServerClient,
    BUILDER_TIMEOUT,
    get_documentserver_client,
)
from aiecs.tools.office_tool.core.builder_js import close_file, open_file, save_file
from aiecs.tools.office_tool.core.builder_runtime import run_builder_script
from aiecs.tools.office_tool.core.source import resolve_document_source

logger = logging.getLogger(__name__)

SIDECAR_FILENAME = "structure.txt"


def build_sidecar_extract_script(
    open_url: str,
    file_ext: str,
    extract_body: str,
) -> str:
    """
    OpenFile → extract_body (must assign JSON to jsonStr)
    → CreateFile txt → AddText(jsonStr) → SaveFile → CloseFile
    """
    lines = [
        open_file(open_url, file_ext),
        extract_body.strip(),
        'builder.CreateFile("txt");',
        "var sidecarDoc = Api.GetDocument();",
        "var sidecarPara = sidecarDoc.GetElement(0);",
        "sidecarPara.AddText(jsonStr);",
        save_file("txt", SIDECAR_FILENAME),
        close_file(),
    ]
    return "\n".join(lines)


async def read_sidecar_json(
    source_path: str | None,
    source_url: str | None,
    file_ext: str,
    extract_body: str,
    client: DocumentServerClient | None = None,
) -> tuple[dict | None, str | None]:
    """
    Resolve source, run sidecar Builder script, download and parse JSON.

    Returns:
        (parsed_dict, None) on success
        (None, error_text) on failure
    """
    path_val = (source_path or "").strip()
    url_val = (source_url or "").strip()

    resolved = await resolve_document_source(path_val, url_val)
    if isinstance(resolved, dict):
        return None, resolved.get("text", "Failed to resolve document source")

    fetch_url, resolved_ext, _, _ = resolved
    ext = file_ext or resolved_ext
    script = build_sidecar_extract_script(fetch_url, ext, extract_body)

    result = await run_builder_script(script, client=client)
    if result.get("isError"):
        return None, result.get("text", "Builder sidecar failed")

    file_url = result.get("file_url")
    if not file_url:
        return None, "DocumentServer did not return sidecar fileUrl"

    try:
        async with httpx.AsyncClient(timeout=BUILDER_TIMEOUT) as http_client:
            response = await http_client.get(file_url)
            response.raise_for_status()
            text = response.text
        return json.loads(text), None
    except json.JSONDecodeError as e:
        logger.exception("Sidecar JSON parse failed")
        return None, f"Invalid sidecar JSON: {e}"
    except Exception as e:
        logger.exception("Failed to download sidecar")
        return None, str(e)
