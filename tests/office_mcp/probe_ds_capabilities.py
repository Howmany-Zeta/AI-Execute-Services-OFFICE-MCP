"""
DocumentServer capability probe (ADR-021).

Session-scoped cache for DS feature detection. Builder smoke tests gate:
- GetSheetsCount → spreadsheet fine read E2E
- CreateFile("pdf") → PDF native create E2E

Env overrides (skip builder smoke):
- OFFICE_DS_GET_SHEETS_COUNT=0|1
- OFFICE_DS_PDF_NATIVE=0|1

When Builder script hosting is unavailable (no MCP_PUBLIC_URL / storage path),
falls back to reachable=true assumption for capability flags unless overridden.
"""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass, field
from typing import Any, Optional

import httpx

logger = logging.getLogger(__name__)

_probe_cache: Optional["DSCapabilities"] = None

_GET_SHEETS_COUNT_PROBE_SCRIPT = """
builder.CreateFile("xlsx");
Api.GetSheetsCount();
builder.SaveFile("xlsx", "probe.xlsx");
builder.CloseFile();
""".strip()

_PDF_NATIVE_PROBE_SCRIPT = """
builder.CreateFile("pdf");
builder.SaveFile("pdf", "probe.pdf");
builder.CloseFile();
""".strip()


@dataclass
class DSCapabilities:
    """Cached DocumentServer capability flags."""

    documentserver_url: str = ""
    reachable: bool = False
    builder_available: bool = False
    conversion_available: bool = False
    get_sheets_count: bool = False  # M5 spreadsheet fine read gate (ADR-013)
    pdf_native_create: bool = False  # M6 PDF gate (ADR-017 / DS 9.3+)
    builder_probe_ran: bool = False
    raw: dict[str, Any] = field(default_factory=dict)


def _env_override(name: str) -> Optional[bool]:
    val = os.environ.get(name, "").strip().lower()
    if val in ("0", "false", "no"):
        return False
    if val in ("1", "true", "yes"):
        return True
    return None


def _builder_probe_configured() -> bool:
    from aiecs.tools.office_tool.core.docbuilder_script import _docbuilder_script_base_path

    if _docbuilder_script_base_path():
        return True
    return bool(os.environ.get("MCP_PUBLIC_URL", "").strip())


async def _run_builder_smoke(script: str) -> bool:
    """Return True when DocumentServer executes the probe script successfully."""
    try:
        from aiecs.tools.office_tool.core.builder_runtime import run_builder_script

        result = await run_builder_script(script=script)
        if result.get("isError"):
            logger.debug("Builder probe failed: %s", result.get("text"))
            return False
        return bool(result.get("success") or result.get("file_url"))
    except Exception as exc:
        logger.debug("Builder probe exception: %s", exc)
        return False


async def _probe_builder_capabilities(caps: DSCapabilities) -> None:
    """Run Builder smoke scripts when script hosting is configured."""
    if not caps.reachable or not _builder_probe_configured():
        return

    caps.builder_probe_ran = True
    caps.builder_available = await _run_builder_smoke(
        'builder.CreateFile("docx");\nbuilder.SaveFile("docx", "probe.docx");\nbuilder.CloseFile();'
    )
    if not caps.builder_available:
        caps.get_sheets_count = False
        caps.pdf_native_create = False
        return

    sheets_override = _env_override("OFFICE_DS_GET_SHEETS_COUNT")
    if sheets_override is not None:
        caps.get_sheets_count = sheets_override
    else:
        caps.get_sheets_count = await _run_builder_smoke(_GET_SHEETS_COUNT_PROBE_SCRIPT)

    pdf_override = _env_override("OFFICE_DS_PDF_NATIVE")
    if pdf_override is not None:
        caps.pdf_native_create = pdf_override
    else:
        caps.pdf_native_create = await _run_builder_smoke(_PDF_NATIVE_PROBE_SCRIPT)


def _apply_env_overrides(caps: DSCapabilities) -> None:
    """Apply env overrides when builder smoke did not run."""
    if caps.builder_probe_ran:
        return
    sheets_override = _env_override("OFFICE_DS_GET_SHEETS_COUNT")
    if sheets_override is not None:
        caps.get_sheets_count = sheets_override
    elif caps.reachable:
        caps.get_sheets_count = True

    pdf_override = _env_override("OFFICE_DS_PDF_NATIVE")
    if pdf_override is not None:
        caps.pdf_native_create = pdf_override
    elif caps.reachable:
        caps.pdf_native_create = True


async def probe_ds_capabilities(documentserver_url: str) -> DSCapabilities:
    """
    Probe DocumentServer capabilities (session-cached).

    1. GET /healthcheck → reachable
    2. When script hosting configured → Builder smoke for GetSheetsCount / PDF native
    3. Env overrides always win for get_sheets_count / pdf_native_create
    """
    global _probe_cache
    if _probe_cache is not None and _probe_cache.documentserver_url == documentserver_url:
        return _probe_cache

    caps = DSCapabilities(documentserver_url=documentserver_url)
    url = (documentserver_url or "").strip().rstrip("/")
    if url:
        try:
            r = httpx.get(f"{url}/healthcheck", timeout=5)
            caps.reachable = r.text.strip() == "true"
            caps.conversion_available = caps.reachable
        except Exception:
            caps.reachable = False

    await _probe_builder_capabilities(caps)
    _apply_env_overrides(caps)

    caps.raw = {
        "reachable": caps.reachable,
        "builder_available": caps.builder_available,
        "conversion_available": caps.conversion_available,
        "get_sheets_count": caps.get_sheets_count,
        "pdf_native_create": caps.pdf_native_create,
        "builder_probe_ran": caps.builder_probe_ran,
        "builder_probe_configured": _builder_probe_configured(),
        "probe_version": "m7-full",
    }
    _probe_cache = caps
    return caps


def clear_probe_cache() -> None:
    """Clear session probe cache (for tests)."""
    global _probe_cache
    _probe_cache = None
