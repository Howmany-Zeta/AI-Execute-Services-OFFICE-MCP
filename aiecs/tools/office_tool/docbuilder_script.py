"""
Convert Builder script to fetchable URL for Document Server.

Document Server requires script in .docbuilder file at url, not inline script.
When script is provided, we must host it. Supports:
- Object storage: DOCBUILDER_SCRIPT_STORAGE_PATH=gs:// or s3://bucket/temp/docbuilder
- Legacy: DOCBUILDER_SCRIPT_GCS_PATH=gs://... (alias)
- Script server: MCP_PUBLIC_URL + in-memory store (GET /docbuilder-scripts/{id})
"""

import logging
import os
import uuid
from typing import Optional

from aiecs.tools.office_tool.storage_paths import is_object_storage_path

logger = logging.getLogger(__name__)

# In-memory store for script server (when MCP_PUBLIC_URL is set)
_script_store: dict[str, str] = {}


def get_script(script_id: str) -> Optional[str]:
    """Get script by id (for script server endpoint)."""
    return _script_store.get(script_id)


def store_script(script: str) -> str:
    """Store script and return id. Used by script server."""
    sid = str(uuid.uuid4())
    _script_store[sid] = script
    return sid


def _docbuilder_script_base_path() -> str:
    """Resolve base path for temporary .docbuilder uploads."""
    for key in ("DOCBUILDER_SCRIPT_STORAGE_PATH", "DOCBUILDER_SCRIPT_GCS_PATH"):
        base = os.environ.get(key, "").strip()
        if base and is_object_storage_path(base):
            return base
    return ""


async def _script_to_url_storage(script: str) -> str:
    """Upload script to object storage, return presigned/signed URL."""
    from aiecs.tools.office_tool.storage import resolve_fetch_url, upload_to_storage

    base = _docbuilder_script_base_path()
    if not base:
        raise ValueError(
            "DOCBUILDER_SCRIPT_STORAGE_PATH (gs:// or s3://) required for script-to-url. "
            "Set it or provide url to .docbuilder file directly."
        )
    base = base.rstrip("/")
    path = f"{base}/{uuid.uuid4().hex}.docbuilder"
    await upload_to_storage(script.encode("utf-8"), path)
    return await resolve_fetch_url(path, expiry_seconds=300)


def _script_to_url_server(script: str) -> str:
    """Store script, return MCP script server URL."""
    base = os.environ.get("MCP_PUBLIC_URL", "").strip()
    if not base:
        raise ValueError(
            "MCP_PUBLIC_URL required for script-to-url (e.g. http://host:5040). "
            "Set it or use DOCBUILDER_SCRIPT_STORAGE_PATH or provide url directly."
        )
    base = base.rstrip("/")
    sid = store_script(script)
    return f"{base}/docbuilder-scripts/{sid}"


async def script_to_url(script: str) -> str:
    """
    Convert Builder script to fetchable URL.

    Tries DOCBUILDER_SCRIPT_STORAGE_PATH / DOCBUILDER_SCRIPT_GCS_PATH first,
    then MCP_PUBLIC_URL (script server).
    """
    if _docbuilder_script_base_path():
        return await _script_to_url_storage(script)
    mcp_url = os.environ.get("MCP_PUBLIC_URL", "").strip()
    if mcp_url:
        return _script_to_url_server(script)
    raise ValueError(
        "Provide url to .docbuilder file, or set DOCBUILDER_SCRIPT_STORAGE_PATH (gs:// or s3://) "
        "or MCP_PUBLIC_URL for script-to-url conversion."
    )
