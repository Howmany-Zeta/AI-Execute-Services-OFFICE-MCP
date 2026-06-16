"""
office_apply_template: Fill template with data via DocumentServer Builder.

Python generates Builder script: OpenFile template, SearchAndReplace each {{key}}
with data value (str() applied), SaveFile, upload to output_path.
Placeholder format: {{key}}
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
    get_file_ext,
    SIGNED_URL_EXPIRY_SECONDS,
)
from aiecs.tools.office_tool.storage_paths import ACCEPTED_SOURCE_PATH_FORMATS

logger = logging.getLogger(__name__)


def _escape_js(s: str) -> str:
    """Escape string for use inside JS double-quoted string."""
    return s.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n").replace("\r", "\\r")


def _build_apply_template_script(template_url: str, file_ext: str, data: Dict[str, Any]) -> str:
    """
    Generate Builder script: OpenFile template, SearchAndReplace each {{key}}, SaveFile.

    All data values are converted with str() before SetText (SearchAndReplace needs strings).
    """
    lines: list[str] = []

    lines.append(f'builder.OpenFile("{_escape_js(template_url)}", "{file_ext}");')
    lines.append("var doc = Api.GetDocument();")
    lines.append("")

    for key, value in data.items():
        search_str = "{{" + key + "}}"
        replace_str = str(value)
        lines.append(
            f'doc.SearchAndReplace({{"searchString": "{_escape_js(search_str)}", '
            f'"replaceString": "{_escape_js(replace_str)}"}});'
        )

    lines.append("")
    lines.append(f'builder.SaveFile("{file_ext}", "output.{file_ext}");')
    lines.append("builder.CloseFile();")

    return "\n".join(lines)


OFFICE_APPLY_TEMPLATE_TOOL = {
    "name": "office_apply_template",
    "description": (
        f"Fill a template document with data. Provide template_path ({ACCEPTED_SOURCE_PATH_FORMATS}) "
        "OR template_url (HTTP/HTTPS). "
        "Placeholders in {{key}} format. Data dict keys match placeholder names; values converted to strings."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "template_path": {
                "type": "string",
                "description": f"Object storage path ({ACCEPTED_SOURCE_PATH_FORMATS}). Optional if template_url provided.",
            },
            "template_url": {
                "type": "string",
                "description": "HTTP/HTTPS URL to template. Optional if template_path provided.",
            },
            "data": {
                "type": "object",
                "additionalProperties": True,
                "description": "Key-value pairs. Keys match {{key}} placeholders.",
            },
            "output_path": {
                "type": "string",
                "description": "Output path (gs://, s3://, or local)",
            },
        },
        "required": ["data", "output_path"],
    },
}


async def office_apply_template(
    data: Dict[str, Any],
    output_path: str,
    template_path: Optional[str] = None,
    template_url: Optional[str] = None,
    client: Optional[DocumentServerClient] = None,
) -> Dict[str, Any]:
    """
    Fill template with data: OpenFile, SearchAndReplace each {{key}}, SaveFile, upload.

    Args:
        template_path: GCS path (gs://bucket/path). Optional if template_url provided.
        template_url: HTTP/HTTPS URL to template. Optional if template_path provided.
        data: Dict mapping placeholder keys to values (all values passed through str())
        output_path: Output path (gs:// or local)
        client: Optional DocumentServerClient

    Returns:
        {"success": True, "output_path"} or {"isError": True, "text": str}
    """
    path_val = (template_path or "").strip()
    url_val = (template_url or "").strip()

    if not isinstance(data, dict):
        return {"isError": True, "text": "data must be an object (dict)"}
    if not output_path or not output_path.strip():
        return {"isError": True, "text": "output_path is required"}

    ds_client = client or get_documentserver_client()

    resolved = await resolve_document_source(path_val, url_val, expiry_seconds=SIGNED_URL_EXPIRY_SECONDS)
    if isinstance(resolved, dict):
        return resolved

    fetch_url, file_ext, _, _ = resolved
    script = _build_apply_template_script(fetch_url, file_ext, data)

    try:
        script_url = await script_to_url(script)
        result = await ds_client.execute_builder(url=script_url)
    except httpx.HTTPStatusError as e:
        logger.error(f"DocumentServer Builder error: {e}")
        return {"isError": True, "text": f"DocumentServer error: {e.response.status_code} {e.response.text[:500]}"}
    except httpx.TimeoutException:
        return {"isError": True, "text": f"DocumentServer timeout (>{BUILDER_TIMEOUT}s)"}
    except Exception as e:
        logger.exception("office_apply_template Builder failed")
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
