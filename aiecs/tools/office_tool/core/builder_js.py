"""Builder JavaScript snippet helpers for DocumentServer scripts."""


def escape_js(s: str) -> str:
    """Escape string for use inside JS double-quoted string."""
    return (
        s.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\t", "\\t")
        .replace("\n", "\\n")
        .replace("\r", "\\r")
        .replace("\u2028", "\\u2028")
        .replace("\u2029", "\\u2029")
    )


def open_file(url: str, ext: str) -> str:
    """Return builder.OpenFile(...) line."""
    return f'builder.OpenFile("{escape_js(url)}", "{ext}");'


def save_file(ext: str, filename: str) -> str:
    """Return builder.SaveFile(...) line."""
    return f'builder.SaveFile("{ext}", "{filename}");'


def close_file() -> str:
    """Return builder.CloseFile() line."""
    return "builder.CloseFile();"


def wrap_script(body: str) -> str:
    """Append CloseFile when body does not already close the builder session."""
    body = body.rstrip()
    if "builder.CloseFile" in body:
        return body
    if body and not body.endswith(";"):
        body += ";"
    return f"{body}\n{close_file()}" if body else close_file()
