"""
Unified DocumentServer Builder execution pipeline.

Used by edit (run_builder_on_source), merge, template, and execute_builder (run_builder_script).
"""

import logging
from typing import Any, Dict, Optional

import httpx

from aiecs.clients.documentserver_client import (
    DocumentServerClient,
    get_documentserver_client,
    BUILDER_TIMEOUT,
)
from aiecs.tools.office_tool.core.builder_js import close_file, open_file, save_file
from aiecs.tools.office_tool.core.docbuilder_script import script_to_url
from aiecs.tools.office_tool.core.errors import err, ok
from aiecs.tools.office_tool.core.storage import get_file_ext, upload_to_storage

logger = logging.getLogger(__name__)


async def run_builder_script(
    script: Optional[str] = None,
    *,
    url: Optional[str] = None,
    argument: Optional[Dict[str, Any]] = None,
    output_path: Optional[str] = None,
    client: Optional[DocumentServerClient] = None,
) -> Dict[str, Any]:
    """
    Execute a Builder script or hosted .docbuilder URL via DocumentServer.

    1. script_to_url(script) when script is provided, else use url directly
    2. client.execute_builder(url=..., argument=...)
    3. If output_path: download fileUrl and upload_to_storage

    Returns:
        {success, file_url?} | {success, output_path?} | {isError, text}
    """
    script_val = (script or "").strip()
    url_val = (url or "").strip()

    if script_val:
        try:
            url_val = await script_to_url(script_val)
        except ValueError as e:
            return err(str(e))
    elif not url_val:
        return err("Provide script or url")

    ds_client = client or get_documentserver_client()

    try:
        result = await ds_client.execute_builder(url=url_val, argument=argument)
    except httpx.HTTPStatusError as e:
        logger.error(f"DocumentServer Builder error: {e}")
        return err(f"DocumentServer error: {e.response.status_code} {e.response.text[:500]}")
    except httpx.TimeoutException as e:
        logger.error(f"DocumentServer Builder timeout: {e}")
        return err(f"DocumentServer timeout (>{BUILDER_TIMEOUT}s)")
    except Exception as e:
        logger.exception("run_builder_script failed")
        return err(str(e))

    file_url = result.get("fileUrl")
    if not file_url:
        logger.warning(
            "DocumentServer did not return fileUrl. Raw response: %s",
            result,
        )
        return err("DocumentServer did not return fileUrl")

    if not output_path:
        return ok(file_url=file_url)

    try:
        async with httpx.AsyncClient(timeout=BUILDER_TIMEOUT) as http_client:
            response = await http_client.get(file_url)
            response.raise_for_status()
            content = response.content

        await upload_to_storage(content, output_path)
        return ok(output_path=output_path)
    except NotImplementedError as e:
        return err(str(e))
    except Exception as e:
        logger.exception(f"Failed to download/upload to {output_path}")
        return err(str(e))


async def run_builder_on_source(
    fetch_url: str,
    file_ext: str,
    edit_script_body: str,
    output_path: str,
    *,
    client: Optional[DocumentServerClient] = None,
) -> Dict[str, Any]:
    """
    Open source file, run edit_script_body, save to output_path via Builder.

    Injects OpenFile / SaveFile / CloseFile around edit_script_body using builder_js.
    """
    out_ext = get_file_ext(output_path)
    out_filename = f"output.{out_ext}"
    full_script = "\n".join(
        [
            open_file(fetch_url, file_ext),
            edit_script_body,
            save_file(out_ext, out_filename),
            close_file(),
        ]
    )
    return await run_builder_script(full_script, output_path=output_path, client=client)
