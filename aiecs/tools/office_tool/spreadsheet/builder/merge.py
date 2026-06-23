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

    lines.extend(
        [
            "function _sheetNameExists(name) {",
            "  for (var i = 0; i < Api.GetSheetsCount(); i++) {",
            "    if (Api.GetSheet(i).GetName() === name) return true;",
            "  }",
            "  return false;",
            "}",
            "function _resolveMergeSheetName(name, renameConflicts) {",
            "  if (!renameConflicts) {",
            '    if (_sheetNameExists(name)) throw new Error("Sheet name conflict: " + name);',
            "    return name;",
            "  }",
            "  if (!_sheetNameExists(name)) return name;",
            "  var n = 2;",
            '  while (_sheetNameExists(name + "_" + n)) n++;',
            '  return name + "_" + n;',
            "}",
            "",
            f'builder.CreateFile("{output_ext}");',
        ]
    )
    rename_literal = "true" if rename_conflicts else "false"
    for i in range(len(source_urls)):
        lines.append(f'builder.OpenFile("{escape_js(source_urls[i])}", "{source_exts[i]}");')
        lines.append("for (var si = 0; si < Api.GetSheetsCount(); si++) {")
        lines.append("  var srcSheet = Api.GetSheet(si);")
        lines.append("  var name = srcSheet.GetName();")
        lines.append(f"  var targetName = _resolveMergeSheetName(name, {rename_literal});")
        lines.append("  var copied = srcSheet.Copy(Api.GetActiveSheet());")
        lines.append("  if (copied.GetName() !== targetName) copied.SetName(targetName);")
        lines.append("}")
        lines.append("builder.CloseFile();")

    lines.append(f'builder.SaveFile("{output_ext}", "output.{output_ext}");')
    lines.append("builder.CloseFile();")
    return "\n".join(lines)
