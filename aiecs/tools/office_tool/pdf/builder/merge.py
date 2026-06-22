"""Builder script generation for office_merge_pdfs (ADR-018)."""

from __future__ import annotations

import uuid
from typing import Any

import httpx

from aiecs.clients.documentserver_client import (
    CONVERT_TIMEOUT,
    DocumentServerClient,
    get_documentserver_client,
)
from aiecs.tools.office_tool.core.builder_js import escape_js
from aiecs.tools.office_tool.core.categories import builder_file_ext
from aiecs.tools.office_tool.core.errors import err, ok


def build_merge_script_builder(
    source_urls: list[str],
    source_exts: list[str],
    *,
    output_ext: str,
) -> str:
    """Default builder engine: open sources and append pages."""
    lines: list[str] = []
    if not source_urls:
        return ""

    lines.append(f'builder.OpenFile("{escape_js(source_urls[0])}", "{source_exts[0]}");')
    lines.append("var doc = Api.GetDocument();")
    lines.append("builder.CloseFile();")
    lines.append("")

    for i in range(1, len(source_urls)):
        lines.append(f'builder.OpenFile("{escape_js(source_urls[i])}", "{source_exts[i]}");')
        lines.append("var srcDoc = Api.GetDocument();")
        lines.append("for (var p = 0; p < srcDoc.GetElementsCount(); p++) {")
        lines.append("  doc.AddPage();")
        lines.append("  var dstPage = doc.GetElement(doc.GetElementsCount() - 1);")
        lines.append("  var srcPage = srcDoc.GetElement(p);")
        lines.append("  for (var e = 0; e < srcPage.GetElementsCount(); e++) {")
        lines.append("    dstPage.Push(srcPage.GetElement(e));")
        lines.append("  }")
        lines.append("}")
        lines.append("builder.CloseFile();")
        lines.append("")

    lines.append(f'builder.OpenFile("{escape_js(source_urls[0])}", "{source_exts[0]}");')
    lines.append(f'builder.SaveFile("{output_ext}", "output.{output_ext}");')
    lines.append("builder.CloseFile();")
    return "\n".join(lines)


async def merge_pdfs_conversion(
    source_urls: list[str],
    output_path: str,
    client: DocumentServerClient | None = None,
) -> dict[str, Any]:
    """
    Explicit conversion engine (ADR-018).
    Chains Conversion API merges; may lose form fields/annotations.
    """
    if len(source_urls) < 2:
        return err("conversion merge requires at least 2 source URLs")

    ds_client = client or get_documentserver_client()
    merged_url = source_urls[0]

    try:
        for url in source_urls[1:]:
            key = str(uuid.uuid4())
            params = {
                "url": merged_url,
                "filetype": "pdf",
                "outputtype": "pdf",
                "key": key,
                "title": "merge.pdf",
                "password": "",
                "async": False,
                "url2": url,
            }
            result = await ds_client.convert(params)
            if result.get("error"):
                return err(f"Conversion merge failed: error {result.get('error')}")
            merged_url = result.get("fileUrl") or result.get("url") or merged_url

        return ok(
            output_path=output_path,
            file_url=merged_url,
            _note="Merged via Conversion API; form fields and annotations may be lost.",
        )
    except httpx.HTTPStatusError as e:
        return err(f"Conversion merge HTTP error: {e.response.status_code}")
    except httpx.TimeoutException:
        return err(f"Conversion merge timeout (>{CONVERT_TIMEOUT}s)")
    except Exception as e:
        return err(str(e))
