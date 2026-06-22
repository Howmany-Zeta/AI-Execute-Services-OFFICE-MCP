"""Tests for probe_ds_capabilities (ADR-021)."""

from unittest.mock import AsyncMock, patch

import pytest

from tests.office_mcp.probe_ds_capabilities import (
    clear_probe_cache,
    probe_ds_capabilities,
)


@pytest.mark.asyncio
async def test_probe_returns_capabilities_when_unreachable():
    clear_probe_cache()
    caps = await probe_ds_capabilities("")
    assert caps.get_sheets_count is False
    assert caps.reachable is False
    assert caps.raw["probe_version"] == "m7-full"


@pytest.mark.asyncio
async def test_probe_get_sheets_count_field_exists():
    clear_probe_cache()
    caps = await probe_ds_capabilities("http://localhost:9999")
    assert hasattr(caps, "get_sheets_count")
    assert isinstance(caps.get_sheets_count, bool)


@pytest.mark.asyncio
async def test_probe_env_override_get_sheets_count(monkeypatch):
    clear_probe_cache()
    monkeypatch.setenv("OFFICE_DS_GET_SHEETS_COUNT", "0")
    caps = await probe_ds_capabilities("http://localhost:9999")
    assert caps.get_sheets_count is False


@pytest.mark.asyncio
async def test_probe_env_override_pdf_native(monkeypatch):
    clear_probe_cache()
    monkeypatch.setenv("OFFICE_DS_PDF_NATIVE", "1")
    caps = await probe_ds_capabilities("")
    assert caps.pdf_native_create is True


@pytest.mark.asyncio
async def test_probe_builder_smoke_sets_flags(monkeypatch):
    clear_probe_cache()
    monkeypatch.setenv("MCP_PUBLIC_URL", "http://mcp.test:5040")

    async def fake_healthcheck_url(url):
        return True

    async def fake_smoke(script):
        return "GetSheetsCount" in script or 'CreateFile("pdf")' in script or "docx" in script

    with patch(
        "tests.office_mcp.probe_ds_capabilities._run_builder_smoke",
        new=AsyncMock(side_effect=fake_smoke),
    ):
        with patch("httpx.get") as mock_get:
            mock_get.return_value.text = "true"
            caps = await probe_ds_capabilities("http://ds.test")
            assert caps.reachable is True
            assert caps.builder_probe_ran is True
            assert caps.get_sheets_count is True
            assert caps.pdf_native_create is True
