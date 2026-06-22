"""
Document category classification and conversion output types.

Maps to ONLYOFFICE conversion tables:
https://api.onlyoffice.com/docs/docs-api/additional-api/conversion-api/conversion-tables/
"""

from typing import Literal

DocumentCategory = Literal["word", "presentation", "spreadsheet", "pdf", "unknown"]

WORD_EXTENSIONS = frozenset({
    "doc", "docm", "docx", "dot", "dotm", "dotx", "epub", "fb2", "fodt",
    "htm", "html", "hwp", "hwpx", "md", "mht", "mhtml", "odt", "ott",
    "rtf", "stw", "sxw", "txt", "wps", "wpt", "xml",
})

PRESENTATION_EXTENSIONS = frozenset({
    "dps", "dpt", "fodp", "key", "odg", "odp", "otp", "pot", "potm",
    "potx", "pps", "ppsm", "ppsx", "ppt", "pptm", "pptx", "sxi",
})

SPREADSHEET_EXTENSIONS = frozenset({
    "csv", "et", "ett", "fods", "ods", "ots", "sxc", "tsv",
    "xls", "xlsb", "xlsm", "xlsx", "xlt", "xltm", "xltx",
})

PDF_EXTENSIONS = frozenset({"pdf", "djvu", "xps", "oxps"})


def classify_file_ext(file_ext: str) -> DocumentCategory:
    ext = (file_ext or "").lower().lstrip(".")
    if ext in WORD_EXTENSIONS:
        return "word"
    if ext in PRESENTATION_EXTENSIONS:
        return "presentation"
    if ext in SPREADSHEET_EXTENSIONS:
        return "spreadsheet"
    if ext in PDF_EXTENSIONS:
        return "pdf"
    return "unknown"


def llm_coarse_output_type(file_ext: str) -> str:
    """
    Pick Conversion API outputtype suitable for LLM text consumption.

    Word -> html (structured DOM parsing)
    Presentation -> txt
    Spreadsheet -> csv
    PDF / unknown -> txt
    """
    category = classify_file_ext(file_ext)
    if category == "word":
        return "html"
    if category == "presentation":
        return "txt"
    if category == "spreadsheet":
        return "csv"
    return "txt"


def builder_file_ext(output_path: str) -> str:
    """Extension from output path for Builder SaveFile/OpenFile."""
    p = (output_path or "").rstrip("/")
    if "." in p:
        return p.split(".")[-1].lower()
    return "docx"


def assert_category_path(category: DocumentCategory, path: str) -> str | None:
    """Return error message if path extension does not match category, else None."""
    ext = builder_file_ext(path)
    actual = classify_file_ext(ext)
    if actual == category:
        return None
    if category == "unknown":
        return None
    return f"Expected {category} document for path {path!r}, got extension {ext!r} ({actual})"
