"""Extract a file extension from a path or URL.

Presigned HTTP URLs keep query/fragment out of the extension so
``file.docx?X-Amz-...`` is ``docx``, not ``docx?x-amz-...``.
Only the extension is lowercased; the original URL is never mutated.
"""

from urllib.parse import unquote, urlparse


def extract_path_file_ext(path_or_url: str) -> str:
    """Return the last path-segment extension, or empty string if none.

    Query strings and fragments are ignored. The original string is not
    modified; only the extracted extension is lowercased.
    """
    raw = (path_or_url or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw)
    path = unquote(parsed.path or "")
    if not path and not parsed.scheme:
        path = raw.split("?", 1)[0].split("#", 1)[0]
    name = path.rstrip("/").rsplit("/", 1)[-1]
    if "." not in name:
        return ""
    ext = name.rsplit(".", 1)[-1]
    if not ext or any(ch in ext for ch in "/?#"):
        return ""
    return ext.lower()


def path_basename(path_or_url: str) -> str:
    """Last path segment without query/fragment."""
    raw = (path_or_url or "").strip()
    if not raw:
        return ""
    parsed = urlparse(raw)
    path = unquote(parsed.path or "")
    if not path and not parsed.scheme:
        path = raw.split("?", 1)[0].split("#", 1)[0]
    return path.rstrip("/").rsplit("/", 1)[-1]


def logical_filename(output_path: str | None, file_type: str | None = None) -> tuple[str, str]:
    """Optional output_path is a logical name only; never a write target.

    Returns (filename, format_ext). ``s3://`` / ``gs://`` / local paths are
    treated as names, not storage destinations.
    """
    ext = extract_path_file_ext(output_path or "") or (file_type or "docx").lstrip(".").lower()
    if not ext:
        ext = "docx"
    name = path_basename(output_path or "")
    if name and "." in name:
        return name, extract_path_file_ext(name) or ext
    if name:
        return f"{name}.{ext}", ext
    return f"output.{ext}", ext


def guess_media_type(filename_or_ext: str) -> str:
    ext = extract_path_file_ext(filename_or_ext) or (filename_or_ext or "").lower().lstrip(".")
    return {
        "docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        "doc": "application/msword",
        "xlsx": "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        "xls": "application/vnd.ms-excel",
        "pptx": "application/vnd.openxmlformats-officedocument.presentationml.presentation",
        "ppt": "application/vnd.ms-powerpoint",
        "pdf": "application/pdf",
        "odt": "application/vnd.oasis.opendocument.text",
        "odp": "application/vnd.oasis.opendocument.presentation",
        "ods": "application/vnd.oasis.opendocument.spreadsheet",
        "html": "text/html",
        "txt": "text/plain",
    }.get(ext, "application/octet-stream")
