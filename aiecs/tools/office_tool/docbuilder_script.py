"""
Convert Builder script to fetchable URL for Document Server.

Document Server requires script in .docbuilder file at url, not inline script.
When script is provided, we must host it. Supports:
- GCS: DOCBUILDER_SCRIPT_GCS_PATH=gs://bucket/temp/docbuilder
- Script server: MCP_PUBLIC_URL + in-memory store (GET /docbuilder-scripts/{id})
"""

import logging
import os
import uuid
from typing import Optional

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


async def _script_to_url_gcs(script: str) -> str:
    """Upload script to GCS, return signed URL."""
    from aiecs.tools.office_tool.storage import get_signed_url, upload_to_storage

    base = os.environ.get("DOCBUILDER_SCRIPT_GCS_PATH", "").strip()
    if not base or not base.startswith("gs://"):
        raise ValueError(
            "DOCBUILDER_SCRIPT_GCS_PATH (gs://bucket/path) required for script-to-url. "
            "Set it or provide url to .docbuilder file directly."
        )
    base = base.rstrip("/")
    path = f"{base}/{uuid.uuid4().hex}.docbuilder"
    await upload_to_storage(script.encode("utf-8"), path)
    return await get_signed_url(path, expiry_seconds=300)


def _script_to_url_server(script: str) -> str:
    """Store script, return MCP script server URL."""
    base = os.environ.get("MCP_PUBLIC_URL", "").strip()
    if not base:
        raise ValueError(
            "MCP_PUBLIC_URL required for script-to-url (e.g. http://host:5040). "
            "Set it or use DOCBUILDER_SCRIPT_GCS_PATH or provide url directly."
        )
    base = base.rstrip("/")
    sid = store_script(script)
    return f"{base}/docbuilder-scripts/{sid}"


async def script_to_url(script: str) -> str:
    """
    Convert Builder script to fetchable URL.

    Tries DOCBUILDER_SCRIPT_GCS_PATH first, then MCP_PUBLIC_URL (script server).
    """
    gcs_path = os.environ.get("DOCBUILDER_SCRIPT_GCS_PATH", "").strip()
    if gcs_path and gcs_path.startswith("gs://"):
        return await _script_to_url_gcs(script)
    mcp_url = os.environ.get("MCP_PUBLIC_URL", "").strip()
    if mcp_url:
        return _script_to_url_server(script)
    raise ValueError(
        "Provide url to .docbuilder file, or set DOCBUILDER_SCRIPT_GCS_PATH (gs://) "
        "or MCP_PUBLIC_URL for script-to-url conversion."
    )
