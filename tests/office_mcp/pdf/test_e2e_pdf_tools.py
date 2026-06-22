"""
E2E tests for PDF vertical tools.

Requires DOCUMENTSERVER_URL and JWT from `.env.test`.
Native create E2E skipped when pdf_native_create unavailable (ADR-021).
"""

import os

import pytest

from tests.office_mcp.e2e_support import documentserver_reachable
from tests.office_mcp.probe_ds_capabilities import clear_probe_cache, probe_ds_capabilities

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.pdf,
    pytest.mark.e2e,
    pytest.mark.skipif(not documentserver_reachable(), reason="DocumentServer not reachable"),
]


async def _pdf_native_available() -> bool:
    url = os.environ.get("DOCUMENTSERVER_URL", "").strip()
    if not url:
        return False
    clear_probe_cache()
    caps = await probe_ds_capabilities(url)
    return caps.pdf_native_create


@pytest.mark.asyncio
async def test_e2e_read_pdf_coarse_placeholder():
    pytest.skip("PDF E2E requires storage paths in .env.test (run manually)")


@pytest.mark.asyncio
async def test_e2e_native_create_skipped_without_pdf_native():
    if not await _pdf_native_available():
        pytest.skip("PDF native API not available on DocumentServer (ADR-021)")
    pytest.skip("Native create E2E requires storage paths in .env.test (run manually)")
