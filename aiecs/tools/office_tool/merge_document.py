# deprecated: use legacy.merge_documents / word.tools.merge
from aiecs.tools.office_tool.legacy.merge_documents import (  # noqa: F401
    OFFICE_MERGE_DOCUMENTS_TOOL,
    office_merge_documents,
)
from aiecs.tools.office_tool.word.builder.merge import build_merge_script as _build_merge_script_impl


def _build_merge_script(signed_urls, file_exts, add_page_break, add_toc, output_path="out.docx"):
    """Backward-compatible wrapper for tests (W3 adds output_path ext)."""
    return _build_merge_script_impl(
        signed_urls,
        file_exts,
        output_path=output_path,
        add_page_break=add_page_break,
        add_toc=add_toc,
    )


__all__ = ["OFFICE_MERGE_DOCUMENTS_TOOL", "office_merge_documents", "_build_merge_script"]
