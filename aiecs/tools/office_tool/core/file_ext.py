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
