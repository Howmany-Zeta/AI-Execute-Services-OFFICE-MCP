"""
E2E tests for Spreadsheet vertical tools.

Requires DOCUMENTSERVER_URL and JWT from `.env.test`.
Fine read E2E skipped when GetSheetsCount unavailable (ADR-013/ADR-021).
"""

import os

import pytest

from tests.office_mcp.e2e_support import documentserver_reachable
from tests.office_mcp.probe_ds_capabilities import clear_probe_cache, probe_ds_capabilities

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.spreadsheet,
    pytest.mark.e2e,
    pytest.mark.skipif(not documentserver_reachable(), reason="DocumentServer not reachable"),
]


async def _get_sheets_count_available() -> bool:
    url = os.environ.get("DOCUMENTSERVER_URL", "").strip()
    if not url:
        return False
    clear_probe_cache()
    caps = await probe_ds_capabilities(url)
    return caps.get_sheets_count


@pytest.mark.asyncio
async def test_e2e_read_spreadsheet_coarse_placeholder():
    """Coarse csv read E2E placeholder."""
    pytest.skip("Spreadsheet E2E requires storage paths in .env.test (run manually)")


@pytest.mark.asyncio
@pytest.mark.skipif(
    not documentserver_reachable(),
    reason="DocumentServer not reachable",
)
async def test_e2e_fine_read_skipped_without_get_sheets_count():
    """Fine read E2E gated on GetSheetsCount probe (OT-111)."""
    if not await _get_sheets_count_available():
        pytest.skip("GetSheetsCount not available on DocumentServer (ADR-021)")
    pytest.skip("Fine read E2E requires storage paths in .env.test (run manually)")
