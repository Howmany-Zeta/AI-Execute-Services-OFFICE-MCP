"""
Snapshot tests for office_read_document MinIO source_path responses.

Uses fixtures/office_read_document_minio_structured.json as the canonical
structured response shape when reading from s3:// paths.
"""

import json
from pathlib import Path

import pytest
from unittest.mock import AsyncMock, patch

from aiecs.tools.office_tool import office_read_document

FIXTURES_DIR = Path(__file__).parent / "fixtures"
MINIO_FIXTURE = FIXTURES_DIR / "office_read_document_minio_structured.json"


@pytest.mark.asyncio
async def test_minio_structured_response_matches_fixture():
    """Mocked MinIO read returns fields matching the saved fixture snapshot."""
    fixture = json.loads(MINIO_FIXTURE.read_text(encoding="utf-8"))
    sidecar = {
        "sections": [{
            "break_type": "continuous",
            "header": [],
            "footer": [],
            "body": [
                {"class": "paragraph", "style_names": ["Heading 1"], "text": "Sample Document", "page_breaks": 0},
                {
                    "class": "paragraph",
                    "style_names": ["Normal"],
                    "text": "This paragraph was read from MinIO via DocumentServer Builder sidecar.",
                    "page_breaks": 0,
                },
                {"class": "paragraph", "style_names": ["Heading 2"], "text": "Section One", "page_breaks": 0},
                {"class": "paragraph", "style_names": ["Normal"], "text": "Content under section one.", "page_breaks": 0},
            ],
        }],
        "footnotes": [],
    }

    with patch(
        "aiecs.tools.office_tool.core.coarse_read.resolve_document_source",
        new_callable=AsyncMock,
        return_value=(
            "http://100.81.172.125:9000/chatbot-use/path/to/document.docx?X-Amz-Signature=x",
            "docx",
            fixture["source_path"],
            fixture["source_path_format"],
        ),
    ), patch(
        "aiecs.tools.office_tool.core.structured_read.read_sidecar_json",
        new_callable=AsyncMock,
        return_value=(sidecar, None),
    ):
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
    assert result["elements"][0]["level"] == 1
    assert result["conversion_output_type"] == "builder_json"
    assert "slides" not in result
    assert "_note" in result
