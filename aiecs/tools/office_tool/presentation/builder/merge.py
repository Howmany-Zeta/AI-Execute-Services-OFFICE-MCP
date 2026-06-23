"""Builder script generation for office_merge_presentations."""

from __future__ import annotations

from aiecs.tools.office_tool.core.builder_js import escape_js
from aiecs.tools.office_tool.core.categories import builder_file_ext


def build_merge_script(
    source_urls: list[str],
    source_exts: list[str],
    *,
    output_path: str,
    separator_slide: bool = False,
    separator_layout: str | None = None,
) -> str:
    """Generate Builder script to merge presentation files via SlidesToJSON/FromJSON."""
    output_ext = builder_file_ext(output_path)
    lines: list[str] = []

    for i, (url, ext) in enumerate(zip(source_urls, source_exts)):
        lines.append(f'builder.OpenFile("{escape_js(url)}", "{ext}");')
        lines.append("var srcPres = Api.GetPresentation();")
        lines.append("var srcLast = srcPres.GetSlidesCount() - 1;")
        lines.append(
            f'GlobalVariable["merge_{i}"] = JSON.stringify(srcPres.SlidesToJSON(0, srcLast, false, false, false, false));'
        )
        lines.append("builder.CloseFile();")
        lines.append("")

    lines.append(f'builder.CreateFile("{output_ext}");')
    lines.append("var pres = Api.GetPresentation();")
    lines.append('pres.FromJSON(GlobalVariable["merge_0"]);')

    for i in range(1, len(source_urls)):
        if separator_slide:
            layout = escape_js(separator_layout or "")
            lines.append(f'pres.AddSlide("{layout}");')
        lines.append(f'var part = JSON.parse(GlobalVariable["merge_{i}"]);')
        lines.append(f'pres.FromJSON(JSON.stringify(part), true);')

    lines.append(f'builder.SaveFile("{output_ext}", "output.{output_ext}");')
    lines.append("builder.CloseFile();")
    return "\n".join(lines)
