"""
Snapshot tests for office_read_document MinIO source_path responses.

Uses fixtures/office_read_document_minio_structured.json as the canonical
structured response shape when reading from s3:// paths.
"""

import json
from pathlib import Path

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from aiecs.tools.office_tool import office_read_document

FIXTURES_DIR = Path(__file__).parent / "fixtures"
MINIO_FIXTURE = FIXTURES_DIR / "office_read_document_minio_structured.json"


@pytest.mark.asyncio
async def test_minio_structured_response_matches_fixture():
    """Mocked MinIO read returns fields matching the saved fixture snapshot."""
    fixture = json.loads(MINIO_FIXTURE.read_text(encoding="utf-8"))
    mock_convert = {"endConvert": True, "fileUrl": "http://ds/out.html"}
    mock_html = """
    <html><body>
    <h1>Sample Document</h1>
    <p>This paragraph was read from MinIO via DocumentServer Conversion API.</p>
    <h2>Section One</h2>
    <p>Content under section one.</p>
    </body></html>
    """

    with patch(
        "aiecs.tools.office_tool.read_document.resolve_document_source",
        new_callable=AsyncMock,
        return_value=(
            "http://100.81.172.125:9000/chatbot-use/path/to/document.docx?X-Amz-Signature=x",
            "docx",
            fixture["source_path"],
            fixture["source_path_format"],
        ),
    ), patch("aiecs.tools.office_tool.read_document.get_documentserver_client") as mock_get:
        mock_client = AsyncMock()
        mock_client.convert = AsyncMock(return_value=mock_convert)
        mock_get.return_value = mock_client

        with patch("httpx.AsyncClient") as mock_http:
            mock_response = MagicMock()
            mock_response.text = mock_html
            mock_response.raise_for_status = MagicMock()
            mock_http.return_value.__aenter__.return_value.get = AsyncMock(return_value=mock_response)

            result = await office_read_document(
                source_path=fixture["source_path"],
                format="structured",
            )

    assert not result.get("isError"), result.get("text")
    assert result["source_path"] == fixture["source_path"]
    assert result["source_path_format"] == fixture["source_path_format"]
    assert result["accepted_source_path_formats"] == fixture["accepted_source_path_formats"]
    assert result["title"] == fixture["title"]
    assert result["word_count"] == fixture["word_count"]
    assert len(result["elements"]) == len(fixture["elements"])
    assert result["elements"][0]["type"] == fixture["elements"][0]["type"]
    assert "_note" in result
