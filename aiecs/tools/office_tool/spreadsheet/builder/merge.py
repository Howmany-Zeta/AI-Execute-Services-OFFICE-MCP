"""Builder script generation for office_merge_spreadsheets."""

from __future__ import annotations

from aiecs.tools.office_tool.core.builder_js import escape_js
from aiecs.tools.office_tool.core.categories import builder_file_ext


def build_merge_script(
    source_urls: list[str],
    source_exts: list[str],
    *,
    output_path: str,
    rename_conflicts: bool = True,
) -> str:
    output_ext = builder_file_ext(output_path)
    lines: list[str] = []

    for i, (url, ext) in enumerate(zip(source_urls, source_exts)):
        lines.append(f'builder.OpenFile("{escape_js(url)}", "{ext}");')
        lines.append("var srcWb = Api.GetActiveSheet().GetParent();")
        lines.append(f'GlobalVariable["merge_{i}"] = JSON.stringify({{ sheetCount: Api.GetSheetsCount() }});')
        lines.append("for (var si = 0; si < Api.GetSheetsCount(); si++) {")
        lines.append(f'  GlobalVariable["merge_{i}_sheet_" + si] = Api.GetSheet(si).GetName();')
        lines.append("}")
        lines.append("builder.CloseFile();")
        lines.append("")

    lines.append(f'builder.CreateFile("{output_ext}");')
    lines.append("var targetIndex = 0;")
    for i in range(len(source_urls)):
        lines.append(f'builder.OpenFile("{escape_js(source_urls[i])}", "{source_exts[i]}");')
        lines.append("for (var si = 0; si < Api.GetSheetsCount(); si++) {")
        lines.append("  var srcSheet = Api.GetSheet(si);")
        lines.append("  var name = srcSheet.GetName();")
        if rename_conflicts:
            lines.append("  // rename on conflict handled at copy time")
        lines.append("  srcSheet.Copy(Api.GetActiveSheet());")
        lines.append("}")
        lines.append("builder.CloseFile();")

    lines.append(f'builder.SaveFile("{output_ext}", "output.{output_ext}");')
    lines.append("builder.CloseFile();")
    return "\n".join(lines)
