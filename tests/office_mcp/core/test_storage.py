"""Tests for core/storage (paths + backend smoke via shims)."""

import pytest

from aiecs.tools.office_tool.core.storage import (
    ACCEPTED_SOURCE_PATH_FORMATS,
    StoragePath,
    get_file_ext,
    is_object_storage_path,
    parse_storage_path,
    validate_source_path,
)


class TestStoragePaths:
    def test_parse_gcs(self):
        parsed = parse_storage_path("gs://my-bucket/path/to/file.docx")
        assert parsed == StoragePath(scheme="gs", bucket="my-bucket", key="path/to/file.docx")

    def test_parse_s3(self):
        parsed = parse_storage_path("s3://bucket/key.xlsx")
        assert parsed.scheme == "s3"

    def test_invalid_path_raises(self):
        with pytest.raises(ValueError):
            parse_storage_path("/local/path.docx")

    def test_validate_source_path_ok(self):
        assert validate_source_path("gs://b/k.docx") is None

    def test_validate_rejects_http(self):
        err = validate_source_path("https://example.com/f.docx")
        assert err is not None

    def test_is_object_storage_path(self):
        assert is_object_storage_path("gs://b/k")
        assert not is_object_storage_path("/tmp/k")


class TestGetFileExt:
    def test_docx(self):
        assert get_file_ext("gs://b/path/file.docx") == "docx"

    def test_default_docx(self):
        assert get_file_ext("gs://b/path/noext") == "docx"

    def test_accepted_formats_documented(self):
        assert "gs://" in ACCEPTED_SOURCE_PATH_FORMATS
        assert "s3://" in ACCEPTED_SOURCE_PATH_FORMATS
