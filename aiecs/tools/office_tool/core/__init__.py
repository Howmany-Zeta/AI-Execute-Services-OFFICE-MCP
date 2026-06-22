"""Office tool core shared modules."""

from aiecs.tools.office_tool.core.builder_js import (
    close_file,
    escape_js,
    open_file,
    save_file,
    wrap_script,
)
from aiecs.tools.office_tool.core.builder_runtime import (
    run_builder_on_source,
    run_builder_script,
)

__all__ = [
    "close_file",
    "escape_js",
    "open_file",
    "save_file",
    "wrap_script",
    "run_builder_on_source",
    "run_builder_script",
]
