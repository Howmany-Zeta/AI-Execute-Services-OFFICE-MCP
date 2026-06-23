"""office_create_presentation — declarative presentation creation."""

from __future__ import annotations

import logging
from typing import Any, Optional

from pydantic import ValidationError

from aiecs.clients.documentserver_client import DocumentServerClient
from aiecs.tools.office_tool.core.builder_runtime import run_builder_script
from aiecs.tools.office_tool.core.categories import assert_category_path, builder_file_ext
from aiecs.tools.office_tool.core.errors import err
from aiecs.tools.office_tool.core.storage import ACCEPTED_SOURCE_PATH_FORMATS
from aiecs.tools.office_tool.presentation.builder.create import build_create_script
from aiecs.tools.office_tool.presentation.schemas.slide_spec import (
    PRESENTATION_CREATE_INPUT_SCHEMA,
    PresentationCreateArgs,
    validate_slides_layouts,
)

logger = logging.getLogger(__name__)

TOOL_NAME = "office_create_presentation"

TOOL_DEF = {
    "name": TOOL_NAME,
    "description": (
        "[Presentation] Create a presentation from declarative slides. "
        f"Output path ({ACCEPTED_SOURCE_PATH_FORMATS} or local). "
        "Each slide layout must match layouts[] from office_read_presentation (ADR-016)."
    ),
    "inputSchema": PRESENTATION_CREATE_INPUT_SCHEMA,
}


async def office_create_presentation(
    slides: list,
    output_path: str,
    options: Optional[dict] = None,
    client: Optional[DocumentServerClient] = None,
    **kwargs: Any,
) -> dict:
    try:
        args = PresentationCreateArgs.model_validate(
            {"slides": slides, "output_path": output_path, "options": options or {}, **kwargs}
        )
    except ValidationError as e:
        return err(str(e.errors()[0]["msg"]) if e.errors() else str(e))

    layout_err = validate_slides_layouts(args.slides, args.options.allowed_layouts)
    if layout_err:
        return err(layout_err)

    path_err = assert_category_path("presentation", args.output_path)
    if path_err:
        return err(path_err)

    output_ext = builder_file_ext(args.output_path)
    script = build_create_script(args.slides, output_ext=output_ext, options=args.options)
    return await run_builder_script(script, output_path=args.output_path, client=client)


handler = office_create_presentation

__all__ = ["TOOL_NAME", "TOOL_DEF", "handler", "office_create_presentation"]
