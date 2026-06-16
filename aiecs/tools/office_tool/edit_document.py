"""
office_edit_document: Edit existing document via DocumentServer Builder.

Opens source file from GCS (signed URL), injects OpenFile/SaveFile/CloseFile around
edit_script, executes Builder, uploads result to output_path.
"""

import logging
from typing import Any, Dict, Optional

import httpx

from aiecs.clients.documentserver_client import (
    DocumentServerClient,
    get_documentserver_client,
    BUILDER_TIMEOUT,
)
from aiecs.tools.office_tool.docbuilder_script import script_to_url
from aiecs.tools.office_tool.source_resolver import resolve_document_source
from aiecs.tools.office_tool.storage import (
    upload_to_storage,
    copy_storage_file,
    get_file_ext,
    SIGNED_URL_EXPIRY_SECONDS,
)
from aiecs.tools.office_tool.storage_paths import ACCEPTED_SOURCE_PATH_FORMATS, is_object_storage_path

logger = logging.getLogger(__name__)


def _escape_js(s: str) -> str:
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r")


OFFICE_EDIT_DOCUMENT_TOOL = {
    "name": "office_edit_document",
    "description": (
        f"Edit an existing document. Provide source_path ({ACCEPTED_SOURCE_PATH_FORMATS}) "
        "OR source_url (HTTP/HTTPS). "
        "Opens the file via Builder OpenFile, executes the edit_script (edit logic only - do NOT include "
        "builder.OpenFile/SaveFile/CloseFile), saves to output_path. "
        "IMPORTANT: Use Search(text) or GetStyleName() for positioning - do NOT use GetElement(index). "
        "Recommended: call office_read_document first, then use Search() or GetStyleName() for targeting."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "source_path": {
                "type": "string",
                "description": f"Object storage path ({ACCEPTED_SOURCE_PATH_FORMATS}). Optional if source_url provided.",
            },
            "source_url": {
                "type": "string",
                "description": "HTTP/HTTPS URL to document. Optional if source_path provided.",
            },
            "edit_script": {
                "type": "string",
                "description": "Builder JS edit logic. Use oDoc.Search('text') or GetStyleName() for positioning.",
            },
            "output_path": {
                "type": "string",
                "description": "Output path (gs://, s3://, or local). Can equal source_path to overwrite.",
            },
            "options": {
                "type": "object",
                "properties": {
                    "backup": {
                        "type": "boolean",
                        "description": "If true, copy source to source_path.backup before editing (object storage only)",
                    },
                },
                "description": "Optional. backup: true to backup before overwrite (requires source_path).",
            },
        },
        "required": ["edit_script", "output_path"],
    },
}


async def office_edit_document(
    edit_script: str,
    output_path: str,
    source_path: Optional[str] = None,
    source_url: Optional[str] = None,
    options: Optional[Dict[str, Any]] = None,
    client: Optional[DocumentServerClient] = None,
) -> Dict[str, Any]:
    """
    Edit existing document: OpenFile, run edit_script, SaveFile, upload to output_path.

    Args:
        source_path: GCS path (gs://bucket/path). Optional if source_url provided.
        source_url: HTTP/HTTPS URL to document. Optional if source_path provided.
        edit_script: Builder JS (no OpenFile/SaveFile - injected automatically)
        output_path: Output path (gs:// or local)
        options: Optional {"backup": True} (GCS only)
        client: Optional DocumentServerClient

    Returns:
        {"success": True, "output_path"} or {"isError": True, "text": str}
    """
    path_val = (source_path or "").strip()
    url_val = (source_url or "").strip()

    if not edit_script or not edit_script.strip():
        return {"isError": True, "text": "edit_script is required"}
    if not output_path or not output_path.strip():
        return {"isError": True, "text": "output_path is required"}

    ds_client = client or get_documentserver_client()

    if path_val and options and options.get("backup"):
        if not is_object_storage_path(path_val):
            return {"isError": True, "text": "options.backup requires source_path (gs:// or s3://)"}
        try:
            await copy_storage_file(path_val, path_val + ".backup")
        except Exception as e:
            logger.exception("Backup failed")
            return {"isError": True, "text": f"Backup failed: {e}"}

    resolved = await resolve_document_source(path_val, url_val, expiry_seconds=SIGNED_URL_EXPIRY_SECONDS)
    if isinstance(resolved, dict):
        return resolved

    fetch_url, file_ext, _, _ = resolved
    out_ext = get_file_ext(output_path)
    out_filename = f"output.{out_ext}"

    # Inject OpenFile, SaveFile, CloseFile around edit_script
    full_script = f'''builder.OpenFile("{_escape_js(fetch_url)}", "{file_ext}");
{edit_script}
builder.SaveFile("{out_ext}", "{out_filename}");
builder.CloseFile();'''

    try:
        script_url = await script_to_url(full_script)
        result = await ds_client.execute_builder(url=script_url)
    except httpx.HTTPStatusError as e:
        logger.error(f"DocumentServer Builder error: {e}")
        return {"isError": True, "text": f"DocumentServer error: {e.response.status_code} {e.response.text[:500]}"}
    except httpx.TimeoutException:
        return {"isError": True, "text": f"DocumentServer timeout (>{BUILDER_TIMEOUT}s)"}
    except Exception as e:
        logger.exception("office_edit_document Builder failed")
        return {"isError": True, "text": str(e)}

    file_url = result.get("fileUrl")
    if not file_url:
        return {"isError": True, "text": "DocumentServer did not return fileUrl"}

    # Download and upload to output_path
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
