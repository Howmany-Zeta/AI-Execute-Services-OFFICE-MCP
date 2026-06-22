"""Builder script generation for office_merge_word."""

from typing import List

from aiecs.tools.office_tool.core.builder_js import escape_js
from aiecs.tools.office_tool.core.categories import builder_file_ext


def build_merge_script(
    signed_urls: List[str],
    file_exts: List[str],
    *,
    output_path: str,
    add_page_break: bool,
    add_toc: bool,
) -> str:
    """Generate Builder script to merge Word documents."""
    output_ext = builder_file_ext(output_path)
    lines: List[str] = []

    for i, (url, ext) in enumerate(zip(signed_urls, file_exts)):
        lines.append(f'builder.OpenFile("{escape_js(url)}", "{ext}");')
        lines.append("var doc = Api.GetDocument();")
        lines.append(f'GlobalVariable["merge_{i}"] = JSON.stringify(doc.ToJSON(false, false, false, false, false, false));')
        lines.append("builder.CloseFile();")
        lines.append("")

    lines.append(f'builder.CreateFile("{output_ext}");')
    lines.append("var doc = Api.GetDocument();")
    lines.append('var content0 = Api.FromJSON(JSON.parse(GlobalVariable["merge_0"]));')
    lines.append("Api.ReplaceDocumentContent(content0);")
    lines.append("")

    for i in range(1, len(signed_urls)):
        if add_page_break:
            lines.append("var pageBreakPara = Api.CreateParagraph();")
            lines.append("var pageBreakRun = Api.CreateRun();")
            lines.append("pageBreakRun.AddPageBreak();")
            lines.append("pageBreakPara.AddElement(pageBreakRun);")
            lines.append("doc.Push(pageBreakPara);")
            lines.append("")
        lines.append(f'var content = Api.FromJSON(JSON.parse(GlobalVariable["merge_{i}"]));')
        lines.append("var elements = content.GetContent(false);")
        lines.append("for (var j = 0; j < elements.length; j++) { doc.Push(elements[j]); }")
        lines.append("")

    if add_toc:
        lines.append("doc.MoveCursorToStart();")
        lines.append("doc.AddTableOfContents({});")
        lines.append("")

    lines.append(f'builder.SaveFile("{output_ext}", "output.{output_ext}");')
    lines.append("builder.CloseFile();")
    return "\n".join(lines)
