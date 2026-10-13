"""
office_execute_builder: Execute Builder via DocumentServer.

Document Server requires script in .docbuilder file at url. Provide url directly,
or script (requires DOCBUILDER_SCRIPT_GCS_PATH or MCP_PUBLIC_URL for conversion).

When output_path is omitted, success returns the generated file as
content_base64 (plus a short-lived DocumentServer file_url). Passing s3://
or gs:// keeps the old upload-to-MCP-storage behavior for internal callers.
"""

import logging
from typing import Any, Dict, Optional

import httpx

from aiecs.clients.documentserver_client import BUILDER_TIMEOUT, DocumentServerClient
from aiecs.tools.office_tool.core.builder_runtime import run_builder_script
from aiecs.tools.office_tool.core.caller_io import file_success, is_storage_output_path
from aiecs.tools.office_tool.core.errors import err, is_error
from aiecs.tools.office_tool.core.file_ext import logical_filename

logger = logging.getLogger(__name__)

TOOL_NAME = "office_execute_builder"


def _is_http_url(s: str) -> bool:
    s = (s or "").strip()
    return s.startswith("http://") or s.startswith("https://")


def _max_result_bytes() -> int:
    from aiecs.config import get_parse_job_config

    return int(get_parse_job_config().max_source_bytes)


TOOL_DEF = {
    "name": TOOL_NAME,
    "description": (
        "[Gateway] Execute Document Builder to create a document. Provide url (to .docbuilder file) OR script. "
        "Document Server requires script in .docbuilder file at url. When script is provided, "
        "set DOCBUILDER_SCRIPT_GCS_PATH or MCP_PUBLIC_URL for conversion. "
        "output_path is optional. Omit it to get content_base64 + filename + format "
        "(plus a short-lived file_url); the caller writes their own storage. "
        "Pass s3:// or gs:// to keep the old internal upload. "
        "Security: accepts arbitrary HTTP(S) URLs — restrict MCP access or network egress when exposed publicly (SSRF risk)."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "url": {
                "type": "string",
                "description": "Absolute URL to .docbuilder file (script in that file). Use when you have a hosted .docbuilder file.",
            },
            "script": {
                "type": "string",
                "description": "Builder JavaScript script. Requires DOCBUILDER_SCRIPT_GCS_PATH or MCP_PUBLIC_URL. Example: builder.CreateFile('docx'); builder.SaveFile('docx', 'out.docx'); builder.CloseFile();",
            },
            "argument": {
                "type": "object",
                "description": "Optional params for script (builder.GetArgument etc.)",
            },
            "output_path": {
                "type": "string",
                "description": (
                    "Optional. Omit to return content_base64. "
                    "s3:// or gs:// keeps the old internal upload. "
                    "Any other value is a logical filename only."
                ),
            },
        },
        "required": [],
    },
}

OFFICE_EXECUTE_BUILDER_TOOL = TOOL_DEF


async def _download_builder_file(file_url: str) -> bytes:
    async with httpx.AsyncClient(timeout=BUILDER_TIMEOUT) as http_client:
        response = await http_client.get(file_url)
        response.raise_for_status()
        return response.content


async def office_execute_builder(
    url: Optional[str] = None,
    script: Optional[str] = None,
    argument: Optional[Dict[str, Any]] = None,
    output_path: Optional[str] = None,
    client: Optional[DocumentServerClient] = None,
) -> Dict[str, Any]:
    """
    Execute Builder via DocumentServer /docbuilder.

    Omit output_path to get content_base64. s3:// / gs:// still uploads.
    """
    url_val = (url or "").strip()
    script_val = (script or "").strip()

    if url_val and script_val:
        return err("Provide url OR script, not both")
    if not url_val and not script_val:
        return err("Provide url (to .docbuilder file) or script")

    if url_val and not _is_http_url(url_val):
        return err("url must be HTTP or HTTPS")

    write_path = output_path if is_storage_output_path(output_path) else None
    built = await run_builder_script(
        script_val or None,
        url=url_val or None,
        argument=argument,
        output_path=write_path,
        client=client,
    )
    if is_error(built):
        return built
    if write_path:
        return built

    file_url = built.get("file_url") or ""
    if not file_url:
        return err("DocumentServer did not return fileUrl")

    try:
        content = await _download_builder_file(file_url)
    except Exception as e:
        logger.exception("Failed to download Builder result")
        return err(f"Failed to download generated file: {e}")

    max_bytes = _max_result_bytes()
    if len(content) > max_bytes:
        return err(f"generated file too large: {len(content)} > {max_bytes}")

    filename, fmt = logical_filename(output_path, built.get("file_type"))
    return file_success(content, filename, fmt, file_url=file_url)


handler = office_execute_builder

__all__ = [
    "TOOL_NAME",
    "TOOL_DEF",
    "OFFICE_EXECUTE_BUILDER_TOOL",
    "handler",
    "office_execute_builder",
]
