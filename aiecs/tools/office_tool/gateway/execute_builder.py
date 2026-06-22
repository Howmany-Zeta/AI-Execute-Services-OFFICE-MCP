"""
office_execute_builder: Execute Builder via DocumentServer.

Document Server requires script in .docbuilder file at url. Provide url directly,
or script (requires DOCBUILDER_SCRIPT_GCS_PATH or MCP_PUBLIC_URL for conversion).
"""

import logging
from typing import Any, Dict, Optional

from aiecs.clients.documentserver_client import DocumentServerClient
from aiecs.tools.office_tool.core.builder_runtime import run_builder_script
from aiecs.tools.office_tool.core.errors import err

logger = logging.getLogger(__name__)

TOOL_NAME = "office_execute_builder"


def _is_http_url(s: str) -> bool:
    s = (s or "").strip()
    return s.startswith("http://") or s.startswith("https://")


TOOL_DEF = {
    "name": TOOL_NAME,
    "description": (
        "[Gateway] Execute Document Builder to create a document. Provide url (to .docbuilder file) OR script. "
        "Document Server requires script in .docbuilder file at url. When script is provided, "
        "set DOCBUILDER_SCRIPT_GCS_PATH or MCP_PUBLIC_URL for conversion. "
        "If output_path is set, downloads result and uploads to that path. "
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
                "description": "Optional. If set, download the generated file and upload to this path (local or gs://).",
            },
        },
        "required": [],
    },
}

OFFICE_EXECUTE_BUILDER_TOOL = TOOL_DEF


async def office_execute_builder(
    url: Optional[str] = None,
    script: Optional[str] = None,
    argument: Optional[Dict[str, Any]] = None,
    output_path: Optional[str] = None,
    client: Optional[DocumentServerClient] = None,
) -> Dict[str, Any]:
    """
    Execute Builder via DocumentServer /docbuilder.

    Args:
        url: Absolute URL to .docbuilder file. Optional if script provided.
        script: Builder JavaScript script. Optional if url provided. Requires script-to-url config.
        argument: Optional params for script.
        output_path: Optional. If set, download file and upload to this path
        client: Optional DocumentServerClient

    Returns:
        {"success": True, "file_url": str} when output_path is None
        {"success": True, "output_path": str} when output_path is set
        {"isError": True, "text": str} on error
    """
    url_val = (url or "").strip()
    script_val = (script or "").strip()

    if url_val and script_val:
        return err("Provide url OR script, not both")
    if not url_val and not script_val:
        return err("Provide url (to .docbuilder file) or script")

    if url_val and not _is_http_url(url_val):
        return err("url must be HTTP or HTTPS")

    return await run_builder_script(
        script_val or None,
        url=url_val or None,
        argument=argument,
        output_path=output_path,
        client=client,
    )


handler = office_execute_builder

__all__ = [
    "TOOL_NAME",
    "TOOL_DEF",
    "OFFICE_EXECUTE_BUILDER_TOOL",
    "handler",
    "office_execute_builder",
]
