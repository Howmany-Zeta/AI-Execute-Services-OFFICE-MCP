"""Caller I/O helpers: inline bytes and storage output detection."""

import base64

from aiecs.tools.office_tool.core.caller_io import (
    decode_inline_file,
    is_storage_output_path,
    sniff_office_ext,
)
from aiecs.tools.office_tool.word.schemas.read import WordReadArgs


def test_is_storage_output_path():
    assert is_storage_output_path("s3://bucket/key.docx")
    assert is_storage_output_path("gs://bucket/key.docx")
    assert not is_storage_output_path("report.docx")
    assert not is_storage_output_path("")
    assert not is_storage_output_path(None)


def test_decode_inline_file():
    data, err = decode_inline_file(base64.b64encode(b"abc").decode("ascii"))
    assert err is None
    assert data == b"abc"
    data, err = decode_inline_file(source_bytes=b"raw")
    assert data == b"raw"
    data, err = decode_inline_file()
    assert data is None and err is None


def test_sniff_office_ext():
    assert sniff_office_ext(b"%PDF-1.4", None) == "pdf"
    assert sniff_office_ext(b"PK\x03\x04xxxx", "notes.docx") == "docx"


def test_word_read_args_accepts_content_base64():
    args = WordReadArgs.model_validate({"content_base64": "YQ==", "filename": "a.docx"})
    assert args.content_base64 == "YQ=="
    try:
        WordReadArgs.model_validate({})
    except Exception as exc:
        assert "content_base64" in str(exc) or "source_url" in str(exc)
    else:
        raise AssertionError("expected validation error")
