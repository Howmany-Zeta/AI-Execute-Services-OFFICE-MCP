"""Snapshot tests for office_read_document MinIO source_path Markdown."""

from unittest.mock import AsyncMock, patch

import pytest

from aiecs.tools.office_tool import office_read_document


@pytest.mark.asyncio
async def test_minio_markdown_response_shape():
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
            ],
        }],
        "footnotes": [],
    }

    with patch(
        "aiecs.tools.office_tool.core.document_read.resolve_document_source",
        new_callable=AsyncMock,
        return_value=(
            "http://minio:9000/chatbot-use/path/to/document.docx?X-Amz-Signature=x",
            "docx",
            "s3://chatbot-use/path/to/document.docx",
            "s3://bucket/path/to/file.ext",
        ),
    ), patch(
        "aiecs.tools.office_tool.core.document_read.read_sidecar_json",
        new_callable=AsyncMock,
        return_value=(sidecar, None),
    ):
        result = await office_read_document(
            source_path="s3://chatbot-use/path/to/document.docx",
            format="markdown",
        )

    assert not result.get("isError"), result.get("text")
    assert result["source_path"] == "s3://chatbot-use/path/to/document.docx"
    assert "elements" not in result
    assert "# Sample Document" in result["markdown"]
    assert result["conversion_output_type"] == "builder_json"
    assert "_note" in result
