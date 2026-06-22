"""
Unit tests for storage path parsing and MinIO presigned URL generation.
"""

import pytest
from unittest.mock import patch, MagicMock

from aiecs.tools.office_tool.storage_paths import (
    parse_storage_path,
    validate_source_path,
    is_object_storage_path,
    ACCEPTED_SOURCE_PATH_FORMATS,
    SOURCE_PATH_FORMAT_S3,
)
from aiecs.tools.office_tool.storage import (
    resolve_fetch_url,
    upload_to_storage,
    copy_storage_file,
    _parse_gcs_path,
)


class TestStoragePaths:
    def test_parse_s3_path(self):
        parsed = parse_storage_path("s3://chatbot-use/user/docs/file.docx")
        assert parsed.scheme == "s3"
        assert parsed.bucket == "chatbot-use"
        assert parsed.key == "user/docs/file.docx"

    def test_parse_gs_path(self):
        parsed = parse_storage_path("gs://my-bucket/path/to/file.docx")
        assert parsed.scheme == "gs"
        assert parsed.bucket == "my-bucket"
        assert parsed.key == "path/to/file.docx"

    def test_is_object_storage_path(self):
        assert is_object_storage_path("s3://b/k")
        assert is_object_storage_path("gs://b/k")
        assert not is_object_storage_path("/local")

    def test_validate_source_path_rejects_local(self):
        err = validate_source_path("/local/file.docx")
        assert err is not None
        assert "gs://" in err or "s3://" in err

    def test_validate_source_path_accepts_s3(self):
        assert validate_source_path("s3://chatbot-use/a.docx") is None


class TestMinIOStorage:
    @pytest.mark.asyncio
    async def test_resolve_fetch_url_s3_presign(self):
        with patch.dict("os.environ", {"MCP_PUBLIC_URL": "", "MINIO_FETCH_MODE": "presign"}), \
             patch("aiecs.tools.office_tool.core.storage.backend._get_s3_client") as mock_get:
            mock_client = MagicMock()
            mock_client.generate_presigned_url.return_value = (
                "http://100.81.172.125:9000/chatbot-use/doc.docx?X-Amz-Signature=abc"
            )
            mock_get.return_value = mock_client

            url = await resolve_fetch_url("s3://chatbot-use/doc.docx")

        assert url.startswith("http://100.81.172.125:9000")
        mock_client.generate_presigned_url.assert_called_once()
        call_kw = mock_client.generate_presigned_url.call_args
        assert call_kw[1]["Params"]["Bucket"] == "chatbot-use"
        assert call_kw[1]["Params"]["Key"] == "doc.docx"

    @pytest.mark.asyncio
    async def test_upload_to_storage_s3(self):
        with patch("aiecs.tools.office_tool.core.storage.backend._get_s3_client") as mock_get:
            mock_client = MagicMock()
            mock_get.return_value = mock_client

            await upload_to_storage(b"data", "s3://chatbot-use/out.docx")

        mock_client.put_object.assert_called_once_with(
            Bucket="chatbot-use",
            Key="out.docx",
            Body=b"data",
        )

    @pytest.mark.asyncio
    async def test_copy_storage_file_s3(self):
        with patch("aiecs.tools.office_tool.core.storage.backend._get_s3_client") as mock_get:
            mock_client = MagicMock()
            mock_get.return_value = mock_client

            await copy_storage_file(
                "s3://chatbot-use/source.docx",
                "s3://chatbot-use/dest.docx",
            )

        mock_client.copy_object.assert_called_once()

    def test_parse_gcs_path_still_works(self):
        bucket, key = _parse_gcs_path("gs://b/path/file.docx")
        assert bucket == "b"
        assert key == "path/file.docx"

    def test_accepted_formats_document_s3(self):
        assert "s3://" in ACCEPTED_SOURCE_PATH_FORMATS
        assert SOURCE_PATH_FORMAT_S3 == "s3://bucket/path/to/file.ext"
