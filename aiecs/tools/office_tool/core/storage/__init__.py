"""Office tool object storage and path utilities."""

from aiecs.tools.office_tool.core.storage.backend import (
    SIGNED_URL_EXPIRY_SECONDS,
    copy_gcs_file,
    copy_storage_file,
    get_file_ext,
    get_signed_url,
    resolve_fetch_url,
    upload_to_storage,
)
from aiecs.tools.office_tool.core.storage.object_fetch import (
    build_s3_fetch_url,
    fetch_object_bytes,
    register_fetch_path,
)
from aiecs.tools.office_tool.core.storage.paths import (
    ACCEPTED_SOURCE_PATH_FORMATS,
    SOURCE_PATH_FORMAT_GCS,
    SOURCE_PATH_FORMAT_S3,
    StoragePath,
    is_object_storage_path,
    parse_storage_path,
    source_path_format_label,
    validate_source_path,
)

__all__ = [
    "ACCEPTED_SOURCE_PATH_FORMATS",
    "SOURCE_PATH_FORMAT_GCS",
    "SOURCE_PATH_FORMAT_S3",
    "SIGNED_URL_EXPIRY_SECONDS",
    "StoragePath",
    "build_s3_fetch_url",
    "copy_gcs_file",
    "copy_storage_file",
    "fetch_object_bytes",
    "get_file_ext",
    "get_signed_url",
    "is_object_storage_path",
    "parse_storage_path",
    "register_fetch_path",
    "resolve_fetch_url",
    "source_path_format_label",
    "upload_to_storage",
    "validate_source_path",
]
