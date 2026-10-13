"""Presigned source_url extension extraction (path only, query case preserved)."""

from aiecs.tools.office_tool.core.categories import assert_category_path, builder_file_ext
from aiecs.tools.office_tool.core.file_ext import extract_path_file_ext
from aiecs.tools.office_tool.core.parse_routing import parse_file_ext
from aiecs.tools.office_tool.core.storage import get_file_ext

AWS2 = (
    "http://100.80.137.86:9000/chatbot-use/user_e2e_read_files/fixtures/"
    "Premium-headphones.docx?AWSAccessKeyId=C06N238WYBZ5QFF44F2L"
    "&Signature=ZohLHXe3kiWrlRq7BBZge6pMsoQ%3D&Expires=1791856432"
)
AWS4 = (
    "https://100.80.137.86:9000/chatbot-use/user_e2e_read_files/fixtures/"
    "file.PDF?X-Amz-Algorithm=AWS4-HMAC-SHA256"
    "&X-Amz-Credential=C06N238WYBZ5QFF44F2L%2F20261013%2Fus-east-1%2Fs3%2Faws4_request"
    "&X-Amz-Date=20261013T015331Z&X-Amz-Expires=300&X-Amz-SignedHeaders=host"
    "&X-Amz-Signature=41231d760d101789839b9e08ef8d87a59eb540408e67e2f9796fe5f48f341f37"
)
PPTX = (
    "http://example.com/deck.PPTX?X-Amz-Algorithm=AWS4-HMAC-SHA256"
    "&X-Amz-Signature=AbCdEf"
)


def test_extract_ignores_aws2_query():
    assert extract_path_file_ext(AWS2) == "docx"
    assert get_file_ext(AWS2) == "docx"
    assert parse_file_ext(AWS2) == "docx"
    assert builder_file_ext(AWS2) == "docx"


def test_extract_ignores_aws4_query_and_lowercases_ext_only():
    assert extract_path_file_ext(AWS4) == "pdf"
    assert get_file_ext(AWS4) == "pdf"
    assert "?" not in get_file_ext(AWS4)
    assert get_file_ext(AWS4) != AWS4.lower()


def test_extract_pptx_presigned():
    assert get_file_ext(PPTX) == "pptx"
    assert parse_file_ext(PPTX) == "pptx"


def test_does_not_treat_query_as_extension():
    ext = get_file_ext(AWS2)
    assert "awsaccesskeyid" not in ext
    assert "x-amz" not in ext
    assert ext == "docx"


def test_assert_category_accepts_presigned_word_url():
    assert assert_category_path("word", AWS2) is None


def test_assert_category_accepts_presigned_pdf_url():
    assert assert_category_path("pdf", AWS4) is None


def test_object_path_unchanged():
    assert get_file_ext("s3://bucket/dir/file.xlsx") == "xlsx"
    assert get_file_ext("gs://b/path/file.docx") == "docx"
    assert get_file_ext("noext") == "docx"
    assert parse_file_ext("noext") == ""
