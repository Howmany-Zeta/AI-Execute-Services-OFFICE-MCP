"""
office_execute_builder: Execute Builder via DocumentServer.

Document Server requires script in .docbuilder file at url. Provide url directly,
or script (requires DOCBUILDER_SCRIPT_GCS_PATH or MCP_PUBLIC_URL for conversion).
"""

import logging
from typing import Any, Dict, Optional

import httpx

from aiecs.clients.documentserver_client import (
    DocumentServerClient,
    get_documentserver_client,
    BUILDER_TIMEOUT,
)
from aiecs.tools.office_tool.storage import upload_to_storage
from aiecs.tools.office_tool.docbuilder_script import script_to_url

logger = logging.getLogger(__name__)


def _is_http_url(s: str) -> bool:
    s = (s or "").strip()
    return s.startswith("http://") or s.startswith("https://")


# MCP tool definition for office_execute_builder
OFFICE_EXECUTE_BUILDER_TOOL = {
    "name": "office_execute_builder",
    "description": (
        "Execute Document Builder to create a document. Provide url (to .docbuilder file) OR script. "
        "Document Server requires script in .docbuilder file at url. When script is provided, "
        "set DOCBUILDER_SCRIPT_GCS_PATH or MCP_PUBLIC_URL for conversion. "
        "If output_path is set, downloads result and uploads to that path."
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
        return {"isError": True, "text": "Provide url OR script, not both"}
    if not url_val and not script_val:
        return {"isError": True, "text": "Provide url (to .docbuilder file) or script"}

    if url_val and not _is_http_url(url_val):
        return {"isError": True, "text": "url must be HTTP or HTTPS"}

    ds_client = client or get_documentserver_client()

    if script_val:
        try:
            url_val = await script_to_url(script_val)
        except ValueError as e:
            return {"isError": True, "text": str(e)}

    try:
        result = await ds_client.execute_builder(url=url_val, argument=argument)
    except httpx.HTTPStatusError as e:
        logger.error(f"DocumentServer Builder error: {e}")
        return {"isError": True, "text": f"DocumentServer error: {e.response.status_code} {e.response.text[:500]}"}
    except httpx.TimeoutException as e:
        logger.error(f"DocumentServer Builder timeout: {e}")
        return {"isError": True, "text": f"DocumentServer timeout (>{BUILDER_TIMEOUT}s)"}
    except Exception as e:
        logger.exception("office_execute_builder failed")
        return {"isError": True, "text": str(e)}

    file_url = result.get("fileUrl")
    if not file_url:
        logger.warning(
            "DocumentServer did not return fileUrl. Raw response: %s",
            result,
        )
        return {"isError": True, "text": "DocumentServer did not return fileUrl"}

    if not output_path:
        return {"success": True, "file_url": file_url}

    # Download from fileUrl and upload to output_path
    try:
        async with httpx.AsyncClient(timeout=BUILDER_TIMEOUT) as http_client:
            response = await http_client.get(file_url)
            response.raise_for_status()
            content = response.content

        await upload_to_storage(content, output_path)
        return {"success": True, "output_path": output_path}
    except NotImplementedError as e:
        return {"isError": True, "text": str(e)}
    except Exception as e:
        logger.exception(f"Failed to download/upload to {output_path}")
        return {"isError": True, "text": str(e)}
