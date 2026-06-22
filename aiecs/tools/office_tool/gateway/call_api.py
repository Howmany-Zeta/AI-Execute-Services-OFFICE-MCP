"""
office_call_api: Call DocumentServer Conversion or Command API directly.

Routes by action: convert -> Conversion API; forcesave | info -> Command API.
JWT placed in body (JWT_IN_BODY=true). Returns API response as-is.
"""

import logging
from typing import Any, Dict, Optional

import httpx

from aiecs.clients.documentserver_client import (
    DocumentServerClient,
    get_documentserver_client,
    CONVERT_TIMEOUT,
    COMMAND_TIMEOUT,
)
from aiecs.tools.office_tool.core.errors import err

logger = logging.getLogger(__name__)

TOOL_NAME = "office_call_api"

CALL_API_DESCRIPTION = """[Gateway] Call DocumentServer Conversion or Command API directly.

**Actions and params:**
- **convert**: Conversion API. params: url (file URL), filetype (e.g. docx), outputtype (e.g. pdf), key (unique per conversion)
- **forcesave**: Command API. params: key (document key)
- **info**: Command API. params: key (document key)

Example convert: {"action": "convert", "params": {"url": "https://signed-url/file.docx", "filetype": "docx", "outputtype": "pdf", "key": "unique-key"}}
Example forcesave: {"action": "forcesave", "params": {"key": "doc-key"}}
Example info: {"action": "info", "params": {"key": "doc-key"}}

Security: convert passes user-supplied url to DocumentServer — no URL allowlist. Restrict MCP access or egress when exposed publicly (SSRF risk).
"""

TOOL_DEF = {
    "name": TOOL_NAME,
    "description": CALL_API_DESCRIPTION,
    "inputSchema": {
        "type": "object",
        "properties": {
            "action": {
                "type": "string",
                "enum": ["convert", "forcesave", "info"],
                "description": "convert: Conversion API; forcesave: Command API; info: Command API",
            },
            "params": {
                "type": "object",
                "description": (
                    "convert: url, filetype, outputtype, key (all required). "
                    "forcesave/info: key (required)"
                ),
                "properties": {
                    "url": {"type": "string", "description": "File URL (convert only)"},
                    "filetype": {"type": "string", "description": "Source format e.g. docx (convert only)"},
                    "outputtype": {"type": "string", "description": "Target format e.g. pdf (convert only)"},
                    "key": {"type": "string", "description": "Document/conversion key (required for all)"},
                },
            },
        },
        "required": ["action", "params"],
    },
}

OFFICE_CALL_API_TOOL = TOOL_DEF


def _validate_convert_params(params: Dict[str, Any]) -> Optional[str]:
    """Return error message if invalid, else None."""
    required = ["url", "filetype", "outputtype", "key"]
    for r in required:
        if not params.get(r):
            return f"convert requires params: {', '.join(required)}; missing or empty: {r}"
    return None


def _validate_command_params(params: Dict[str, Any], action: str) -> Optional[str]:
    """Return error message if invalid, else None."""
    if not params.get("key"):
        return f"{action} requires params.key"
    return None


async def office_call_api(
    action: str,
    params: Dict[str, Any],
    client: Optional[DocumentServerClient] = None,
) -> Dict[str, Any]:
    """
    Call DocumentServer Conversion or Command API.

    Args:
        action: "convert" | "forcesave" | "info"
        params: Action-specific params (see tool description)
        client: Optional DocumentServerClient

    Returns:
        API response dict (or {"isError": True, "text": str} on error)
    """
    if not action or not action.strip():
        return err("action is required")
    if not isinstance(params, dict):
        return err("params must be an object")

    action = action.strip().lower()
    if action not in ("convert", "forcesave", "info"):
        return err(f"action must be convert, forcesave, or info; got: {action}")

    ds_client = client or get_documentserver_client()

    if action == "convert":
        param_err = _validate_convert_params(params)
        if param_err:
            return err(param_err)
        api_params = {k: v for k, v in params.items() if k in ("url", "filetype", "outputtype", "key")}
        try:
            result = await ds_client.convert(api_params)
            return result
        except httpx.HTTPStatusError as e:
            logger.error(f"Conversion API error: {e}")
            return err(f"Conversion API error: {e.response.status_code} {e.response.text[:500]}")
        except httpx.TimeoutException:
            return err(f"Conversion API timeout (>{CONVERT_TIMEOUT}s)")
        except Exception as e:
            logger.exception("office_call_api convert failed")
            return err(str(e))

    param_err = _validate_command_params(params, action)
    if param_err:
        return err(param_err)
    cmd_params = {"c": action, "key": params["key"]}
    if params.get("userdata"):
        cmd_params["userdata"] = params["userdata"]
    try:
        result = await ds_client.command(cmd_params)
        return result
    except httpx.HTTPStatusError as e:
        logger.error(f"Command API error: {e}")
        return err(f"Command API error: {e.response.status_code} {e.response.text[:500]}")
    except httpx.TimeoutException:
        return err(f"Command API timeout (>{COMMAND_TIMEOUT}s)")
    except Exception as e:
        logger.exception("office_call_api command failed")
        return err(str(e))


handler = office_call_api

__all__ = [
    "TOOL_NAME",
    "TOOL_DEF",
    "OFFICE_CALL_API_TOOL",
    "CALL_API_DESCRIPTION",
    "handler",
    "office_call_api",
]
