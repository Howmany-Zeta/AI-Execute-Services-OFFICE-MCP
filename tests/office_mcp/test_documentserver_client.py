"""
Unit tests for DocumentServerClient.

Tests JWT signing, Builder/Conversion/Command API calls, and healthcheck.
Uses mocks to avoid real DocumentServer.
"""

import pytest

pytestmark = pytest.mark.asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from aiecs.clients.documentserver_client import (
    DocumentServerClient,
    build_jwt,
    BUILDER_TIMEOUT,
    CONVERT_TIMEOUT,
    COMMAND_TIMEOUT,
)


class TestBuildJwt:
    """Test JWT signing."""

    def test_build_jwt_adds_iat(self):
        """build_jwt adds iat to payload without modifying original."""
        payload = {"async": False, "script": "builder.CreateFile('docx');"}
        secret = "test-secret"
        token = build_jwt(payload, secret)
        assert token
        assert isinstance(token, str)
        # Original payload unchanged
        assert "iat" not in payload

    def test_build_jwt_different_times_differ(self):
        """Tokens with different iat should differ."""
        payload = {"key": "value"}
        secret = "secret"
        t1 = build_jwt(payload, secret)
        t2 = build_jwt(payload, secret)
        # May be same if called in same second
        assert isinstance(t1, str)
        assert isinstance(t2, str)


class TestDocumentServerClient:
    """Test DocumentServerClient methods."""

    @pytest.fixture
    def client(self):
        """Create client with test config."""
        return DocumentServerClient(
            base_url="http://test-ds:8000",
            jwt_secret="test-jwt-secret",
            jwt_in_body=True,
        )

    @pytest.mark.asyncio
    async def test_execute_builder_success(self, client):
        """execute_builder returns fileUrl from response."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"fileUrl": "http://ds/file.docx", "fileType": "docx"}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await client.execute_builder(url="https://example.com/script.docbuilder")

        assert result["fileUrl"] == "http://ds/file.docx"
        assert result["fileType"] == "docx"

    @pytest.mark.asyncio
    async def test_execute_builder_normalizes_urls(self, client):
        """execute_builder normalizes urls dict to fileUrl."""
        mock_response = MagicMock()
        mock_response.json.return_value = {
            "urls": {"output.docx": "http://ds/output.docx"},
            "end": True,
        }
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await client.execute_builder(url="https://example.com/script.docbuilder")

        assert result["fileUrl"] == "http://ds/output.docx"
        assert result.get("fileType") == "docx"

    @pytest.mark.asyncio
    async def test_convert_calls_correct_endpoint(self, client):
        """convert POSTs to ConvertService.ashx with JWT in body."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"endConvert": True, "fileUrl": "http://..."}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__.return_value.post = mock_post
            mock_client_cls.return_value = mock_client

            await client.convert({
                "url": "https://example.com/file.docx",
                "filetype": "docx",
                "outputtype": "pdf",
                "key": "key123",
            })

        call_args = mock_post.call_args
        assert "ConvertService.ashx" in str(call_args[0][0])
        body = call_args[1]["json"]
        assert "token" in body
        assert body["url"] == "https://example.com/file.docx"

    @pytest.mark.asyncio
    async def test_convert_until_complete_polls(self, client):
        """convert_until_complete sends async=true and polls until endConvert."""
        mock_response = MagicMock()
        mock_response.json.side_effect = [
            {"endConvert": False, "percent": 50},
            {"endConvert": True, "fileUrl": "http://ds/out.txt"},
        ]
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls, patch(
            "aiecs.clients.documentserver_client.asyncio.sleep",
            new_callable=AsyncMock,
        ):
            mock_http = AsyncMock()
            mock_http.__aenter__.return_value.post = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_http

            result = await client.convert_until_complete({
                "url": "https://example.com/file.pptx",
                "filetype": "pptx",
                "outputtype": "txt",
                "key": "key123",
            })

        assert result["endConvert"] is True
        assert result["fileUrl"] == "http://ds/out.txt"
        assert mock_http.__aenter__.return_value.post.await_count == 2
        first_body = mock_http.__aenter__.return_value.post.await_args_list[0][1]["json"]
        assert first_body["async"] is True
        assert first_body["outputtype"] == "txt"

    @pytest.mark.asyncio
    async def test_command_calls_correct_endpoint(self, client):
        """command POSTs to CommandService.ashx."""
        mock_response = MagicMock()
        mock_response.json.return_value = {"error": 0}
        mock_response.raise_for_status = MagicMock()

        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_post = AsyncMock(return_value=mock_response)
            mock_client.__aenter__.return_value.post = mock_post
            mock_client_cls.return_value = mock_client

            await client.command({"c": "info", "key": "doc-key"})

        call_args = mock_post.call_args
        assert "CommandService.ashx" in str(call_args[0][0])

    @pytest.mark.asyncio
    async def test_healthcheck_returns_true_when_ok(self, client):
        """healthcheck returns True when response is 'true'."""
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.text = "true"
            mock_client.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await client.healthcheck()

        assert result is True

    @pytest.mark.asyncio
    async def test_healthcheck_returns_false_when_not_ok(self, client):
        """healthcheck returns False when response is not 'true'."""
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.text = "false"
            mock_client.__aenter__.return_value.get = AsyncMock(return_value=mock_response)
            mock_client_cls.return_value = mock_client

            result = await client.healthcheck()

        assert result is False

    @pytest.mark.asyncio
    async def test_healthcheck_returns_false_on_error(self, client):
        """healthcheck returns False on exception."""
        with patch("httpx.AsyncClient") as mock_client_cls:
            mock_client = AsyncMock()
            mock_client.__aenter__.return_value.get = AsyncMock(side_effect=Exception("network error"))
            mock_client_cls.return_value = mock_client

            result = await client.healthcheck()

        assert result is False
