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
from aiecs.tools.office_tool.storage import (
    get_signed_url,
    upload_to_storage,
    get_file_ext,
    SIGNED_URL_EXPIRY_SECONDS,
)

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


def _is_http_url(s: str) -> bool:
    s = (s or "").strip()
    return s.startswith("http://") or s.startswith("https://")


OFFICE_APPLY_TEMPLATE_TOOL = {
    "name": "office_apply_template",
    "description": (
        "Fill a template document with data. Provide template_path (GCS gs://) OR template_url (HTTP/HTTPS). "
        "Placeholders in {{key}} format. Data dict keys match placeholder names; values converted to strings."
    ),
    "inputSchema": {
        "type": "object",
        "properties": {
            "template_path": {
                "type": "string",
                "description": "GCS path (gs://bucket/path/template.docx). Optional if template_url provided.",
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
                "description": "Output path (gs:// or local)",
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

    if path_val and url_val:
        return {"isError": True, "text": "Provide template_path OR template_url, not both"}
    if not path_val and not url_val:
        return {"isError": True, "text": "Provide template_path (gs://) or template_url (HTTP/HTTPS)"}
    if not isinstance(data, dict):
        return {"isError": True, "text": "data must be an object (dict)"}
    if not output_path or not output_path.strip():
        return {"isError": True, "text": "output_path is required"}

    ds_client = client or get_documentserver_client()

    if path_val:
        if not path_val.startswith("gs://"):
            return {"isError": True, "text": "template_path must be a GCS path (gs://bucket/path)"}
        try:
            fetch_url = await get_signed_url(
                path_val, expiry_seconds=SIGNED_URL_EXPIRY_SECONDS
            )
        except Exception as e:
            return {"isError": True, "text": f"Failed to get signed URL: {e}"}
        file_ext = get_file_ext(path_val)
    else:
        if not _is_http_url(url_val):
            return {"isError": True, "text": "template_url must be HTTP or HTTPS URL"}
        fetch_url = url_val
        file_ext = get_file_ext(url_val)
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
