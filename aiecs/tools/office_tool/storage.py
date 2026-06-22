# deprecated: use core.storage
from aiecs.tools.office_tool.core.storage import *  # noqa: F403,F401
from aiecs.tools.office_tool.core.storage.backend import (  # noqa: F401
    _get_gcs_client,
    _get_s3_client,
    _parse_gcs_path,
)
