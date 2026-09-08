"""Exhaustive parse allow-list (ADR-048)."""

from aiecs.tools.office_tool.core.parse_routing import route_parse_engine


def test_pdf_auto_document_ai():
    engine, err = route_parse_engine("pdf", "auto")
    assert engine == "document_ai"
    assert err is None


def test_doc_auto_documentserver():
    engine, err = route_parse_engine("doc", "auto")
    assert engine == "documentserver"
    assert err is None


def test_md_unsupported():
    engine, err = route_parse_engine("md", "auto")
    assert engine is None
    assert err == "office_unsupported"


def test_xlsx_unsupported():
    _, err = route_parse_engine("xlsx", "auto")
    assert err == "office_unsupported"


def test_djvu_unsupported():
    _, err = route_parse_engine("djvu", "auto")
    assert err == "office_unsupported"


def test_epub_unsupported():
    _, err = route_parse_engine("epub", "auto")
    assert err == "office_unsupported"


def test_docx_document_ai_invalid():
    _, err = route_parse_engine("docx", "document_ai")
    assert err == "invalid_engine"
