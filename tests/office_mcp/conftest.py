"""Office MCP test fixtures (env loaded from repo `.env.test` via tests/conftest.py)."""

from __future__ import annotations

import json
import os
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.env_test import get_e2e_config
from tests.office_mcp.e2e_support import documentserver_reachable, mcp_reachable

MCP_TEST_HEADERS = {
    "Content-Type": "application/json",
    "Accept": "application/json, text/event-stream",
}


def parse_mcp_response(response) -> dict[str, Any]:
    """Parse JSON or SSE (text/event-stream) MCP HTTP response."""
    content_type = response.headers.get("content-type", "")
    if "application/json" in content_type:
        return response.json()
    text = response.text or ""
    for line in text.splitlines():
        if line.startswith("data: "):
            return json.loads(line[6:])
    if text.strip():
        return json.loads(text)
    raise json.JSONDecodeError("Empty MCP response body", text, 0)


def pytest_collection_modifyitems(config, items):
    """Skip e2e tests when DOCUMENTSERVER_URL is not configured (ADR-021)."""
    if os.environ.get("DOCUMENTSERVER_URL", "").strip():
        return
    skip = pytest.mark.skip(reason="DOCUMENTSERVER_URL not set (e2e skipped)")
    for item in items:
        if "e2e" in item.keywords:
            item.add_marker(skip)


@pytest.fixture(scope="session")
def mcp_test_client():
    """Single in-process TestClient for FastMCP (lifespan runs once per session)."""
    pytest.importorskip("fastmcp")
    from aiecs.main_mcp import app

    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture(scope="session")
def client(mcp_test_client):
    """Alias for integration/provider tests."""
    return mcp_test_client


@pytest.fixture(scope="session")
def office_e2e_config():
    return get_e2e_config()


@pytest.fixture(scope="session")
def ds_reachable():
    return documentserver_reachable()


@pytest.fixture(scope="session")
def mcp_server_reachable():
    return mcp_reachable()


@pytest.fixture(scope="session")
def ds_capabilities():
    """
    Session-scoped DocumentServer capability probe (ADR-021).

    Cached in probe_ds_capabilities; used by spreadsheet/pdf E2E to skip
    fine read or native create when DS lacks GetSheetsCount / PDF native API.

    Override: OFFICE_DS_GET_SHEETS_COUNT, OFFICE_DS_PDF_NATIVE.
    """
    import asyncio

    from tests.office_mcp.probe_ds_capabilities import DSCapabilities, probe_ds_capabilities

    url = os.environ.get("DOCUMENTSERVER_URL", "").strip()
    if not url:
        return DSCapabilities()
    return asyncio.run(probe_ds_capabilities(url))
