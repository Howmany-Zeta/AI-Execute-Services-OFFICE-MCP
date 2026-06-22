"""Builder script generation for office_apply_template_word."""

from typing import Any, Dict

from aiecs.tools.office_tool.core.builder_js import escape_js


def build_apply_template_script(template_url: str, file_ext: str, data: Dict[str, Any]) -> str:
    """OpenFile template, SearchAndReplace each {{key}}, SaveFile."""
    lines: list[str] = []
    lines.append(f'builder.OpenFile("{escape_js(template_url)}", "{file_ext}");')
    lines.append("var doc = Api.GetDocument();")
    lines.append("")

    for key, value in data.items():
        search_str = "{{" + key + "}}"
        replace_str = str(value)
        lines.append(
            f'doc.SearchAndReplace({{"searchString": "{escape_js(search_str)}", '
            f'"replaceString": "{escape_js(replace_str)}"}});'
        )

    lines.append("")
    lines.append(f'builder.SaveFile("{file_ext}", "output.{file_ext}");')
    lines.append("builder.CloseFile();")
    return "\n".join(lines)
