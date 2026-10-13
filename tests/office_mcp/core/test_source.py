"""source_url resolution: path ext + preserve presign case/query on download."""

from unittest.mock import patch

import pytest

from aiecs.tools.office_tool.core import source as source_mod
from aiecs.tools.office_tool.core.source import resolve_document_source
from aiecs.tools.office_tool.core.storage import object_fetch

PRESIGNED = (
    "http://100.80.137.86:9000/chatbot-use/user_e2e_read_files/fixtures/"
    "Premium-headphones.docx?AWSAccessKeyId=C06N238WYBZ5QFF44F2L"
    "&Signature=ZohLHXe3kiWrlRq7BBZge6pMsoQ%3D&Expires=1791856432"
)


@pytest.fixture(autouse=True)
def _clear_source_caches():
    source_mod._http_proxy_cache.clear()
    object_fetch._bytes_store.clear()
    yield
    source_mod._http_proxy_cache.clear()
    object_fetch._bytes_store.clear()


@pytest.mark.asyncio
async def test_source_url_passthrough_keeps_url_and_strips_ext(monkeypatch):
    monkeypatch.delenv("MCP_PUBLIC_URL", raising=False)
    resolved = await resolve_document_source("", PRESIGNED)
    fetch_url, file_ext, storage_path, label = resolved
    assert fetch_url == PRESIGNED
    assert file_ext == "docx"
    assert storage_path == ""
    assert "source_url" in label


@pytest.mark.asyncio
async def test_source_url_proxy_downloads_exact_url(monkeypatch):
    monkeypatch.setenv("MCP_PUBLIC_URL", "http://aiecs-office-mcp:5040")
    seen = {}

    class _Resp:
        content = b"docx-bytes"

        def raise_for_status(self):
            return None

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, **kwargs):
            seen["url"] = url
            return _Resp()

    with patch("aiecs.tools.office_tool.core.source.httpx.AsyncClient", return_value=_Client()):
        resolved = await resolve_document_source("", PRESIGNED)

    fetch_url, file_ext, _, _ = resolved
    assert seen["url"] == PRESIGNED
    assert file_ext == "docx"
    assert fetch_url.startswith("http://aiecs-office-mcp:5040/storage-objects/")
    assert "?" not in fetch_url
    token = fetch_url.rsplit("/", 1)[-1]
    staged = await object_fetch.fetch_object_bytes(token)
    assert staged is not None
    assert staged[0] == b"docx-bytes"


@pytest.mark.asyncio
async def test_source_url_proxy_cache_reuses_download(monkeypatch):
    monkeypatch.setenv("MCP_PUBLIC_URL", "http://aiecs-office-mcp:5040")
    gets = []

    class _Resp:
        content = b"once"

        def raise_for_status(self):
            return None

    class _Client:
        async def __aenter__(self):
            return self

        async def __aexit__(self, *args):
            return None

        async def get(self, url, **kwargs):
            gets.append(url)
            return _Resp()

    with patch("aiecs.tools.office_tool.core.source.httpx.AsyncClient", return_value=_Client()):
        first = await resolve_document_source("", PRESIGNED)
        second = await resolve_document_source("", PRESIGNED)

    assert gets == [PRESIGNED]
    assert first[0] == second[0]
    assert first[1] == "docx"


@pytest.mark.asyncio
async def test_rejects_both_source_path_and_url():
    result = await resolve_document_source("s3://b/k.docx", PRESIGNED)
    assert result.get("isError") is True
    assert "not both" in result.get("text", "")
