"""
Unit tests for office_tool storage (get_signed_url, upload_to_storage, copy_gcs_file).
"""

import pytest
from unittest.mock import patch, MagicMock

from aiecs.tools.office_tool.storage import (
    get_signed_url,
    upload_to_storage,
    copy_gcs_file,
    get_file_ext,
    _parse_gcs_path,
)


class TestParseGcsPath:
    """Test _parse_gcs_path."""

    def test_valid_path(self):
        """Parse gs://bucket/path/to/file."""
        bucket, blob = _parse_gcs_path("gs://my-bucket/path/to/file.docx")
        assert bucket == "my-bucket"
        assert blob == "path/to/file.docx"

    def test_invalid_raises(self):
        """Non gs:// or s3:// path raises ValueError."""
        with pytest.raises(ValueError, match="Not an object storage path"):
            _parse_gcs_path("/local/path")


class TestGetFileExt:
    """Test get_file_ext."""

    def test_docx(self):
        assert get_file_ext("file.docx") == "docx"
    def test_xlsx(self):
        assert get_file_ext("gs://b/path/file.xlsx") == "xlsx"
    def test_default(self):
        assert get_file_ext("noext") == "docx"


class TestStorageGcs:
    """Test GCS storage functions (mocked)."""

    @pytest.mark.asyncio
    async def test_get_signed_url(self):
        """get_signed_url returns signed URL."""
        with patch("aiecs.tools.office_tool.core.storage.backend._get_gcs_client") as mock_get_client:
            mock_blob = MagicMock()
            mock_blob.generate_signed_url.return_value = "https://signed.example.com/doc"
            mock_bucket = MagicMock()
            mock_bucket.blob.return_value = mock_blob
            mock_client = MagicMock()
            mock_client.bucket.return_value = mock_bucket
            mock_get_client.return_value = mock_client

            url = await get_signed_url("gs://bucket/path/file.docx")

        assert url == "https://signed.example.com/doc"
        mock_blob.generate_signed_url.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_to_storage_gcs(self):
        """upload_to_storage uploads to GCS for gs:// path."""
        with patch("aiecs.tools.office_tool.core.storage.backend._get_gcs_client") as mock_get:
            mock_blob = MagicMock()
            mock_bucket = MagicMock()
            mock_bucket.blob.return_value = mock_blob
            mock_client = MagicMock()
            mock_client.bucket.return_value = mock_bucket
            mock_get.return_value = mock_client

            await upload_to_storage(b"content", "gs://bucket/path/out.docx")

        mock_blob.upload_from_string.assert_called_once()

    @pytest.mark.asyncio
    async def test_upload_to_storage_local(self, tmp_path):
        """upload_to_storage writes to local path."""
        out = tmp_path / "out.docx"
        await upload_to_storage(b"local content", str(out))
        assert out.read_bytes() == b"local content"

    @pytest.mark.asyncio
    async def test_copy_gcs_file(self):
        """copy_gcs_file copies blob in GCS."""
        with patch("aiecs.tools.office_tool.core.storage.backend._get_gcs_client") as mock_get:
            mock_src_bucket = MagicMock()
            mock_dest_bucket = MagicMock()
            mock_client = MagicMock()
            mock_client.bucket.side_effect = [mock_src_bucket, mock_dest_bucket]
            mock_get.return_value = mock_client

            await copy_gcs_file("gs://b1/source.docx", "gs://b2/dest.docx")

        mock_src_bucket.copy_blob.assert_called_once()
