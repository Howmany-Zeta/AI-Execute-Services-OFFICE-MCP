"""
E2E tests for Word vertical tools.

Requires DOCUMENTSERVER_URL and JWT from `.env.test`.
"""

import pytest

from tests.office_mcp.e2e_support import documentserver_reachable

pytestmark = [
    pytest.mark.asyncio,
    pytest.mark.word,
    pytest.mark.e2e,
    pytest.mark.skipif(not documentserver_reachable(), reason="DocumentServer not reachable"),
]


@pytest.mark.asyncio
async def test_e2e_create_and_read_word_placeholder():
    """Placeholder E2E — full create/read/edit loop when DS + storage configured."""
    pytest.skip("Word E2E requires storage paths in .env.test (run manually with E2E_SOURCE_PATH)")
