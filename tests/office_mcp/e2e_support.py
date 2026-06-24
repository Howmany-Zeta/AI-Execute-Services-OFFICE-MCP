"""Helpers for office MCP E2E tests (env from `.env.test`)."""

from __future__ import annotations

import json
import uuid
from functools import lru_cache

import httpx

from tests.env_test import get_e2e_config


def documentserver_reachable() -> bool:
    cfg = get_e2e_config()
    if not cfg.documentserver_url:
        return False
    try:
        r = httpx.get(f"{cfg.documentserver_url.rstrip('/')}/healthcheck", timeout=5)
        return r.text.strip() == "true"
    except Exception:
        return False


def mcp_reachable() -> bool:
    cfg = get_e2e_config()
    try:
        transport = (
            httpx.HTTPTransport(local_address="0.0.0.0")
            if "localhost" in cfg.mcp_url or "127.0.0.1" in cfg.mcp_url
            else None
        )
        with httpx.Client(timeout=5, transport=transport) as client:
            r = client.get(f"{cfg.mcp_url.rstrip('/')}/health")
        return r.status_code == 200
    except Exception:
        return False


def mcp_protocol_url() -> str:
    """JSON-RPC base URL for live MCP integration tests."""
    return f"{get_e2e_config().mcp_url.rstrip('/')}/mcp/v1/"


def _mcp_http_transport() -> httpx.HTTPTransport | None:
    cfg = get_e2e_config()
    if "localhost" in cfg.mcp_url or "127.0.0.1" in cfg.mcp_url:
        return httpx.HTTPTransport(local_address="0.0.0.0")
    return None


def _parse_mcp_tool_response(resp_text: str) -> dict:
    if "data: " in resp_text:
        data = next(
            json.loads(line[6:]) for line in resp_text.split("\n") if line.startswith("data: ")
        )
    else:
        data = json.loads(resp_text)
    content = data.get("result", {}).get("content", data.get("result", []))
    if isinstance(content, list) and content:
        text = content[0].get("text", "") if isinstance(content[0], dict) else str(content[0])
    else:
        text = str(content)
    return json.loads(text)


@lru_cache(maxsize=1)
def word_odt_builder_supported() -> bool:
    """True when DocumentServer Builder can CreateFile('odt') on this installation."""
    cfg = get_e2e_config()
    if not cfg.has_jwt or not cfg.has_source_path:
        return False
    if not documentserver_reachable() or not mcp_reachable():
        return False
    base = cfg.source_path.rsplit("/", 1)[0]
    probe_path = f"{base}/.e2e-odt-capability-{uuid.uuid4().hex[:8]}.odt"
    try:
        with httpx.Client(timeout=60, transport=_mcp_http_transport()) as client:
            resp = client.post(
                mcp_protocol_url(),
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {
                        "name": "office_create_word",
                        "arguments": {
                            "sections": [{"type": "paragraph", "text": "odt capability probe"}],
                            "output_path": probe_path,
                        },
                    },
                    "id": "odt-capability-probe",
                },
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                },
            )
            resp.raise_for_status()
            result = _parse_mcp_tool_response(resp.text)
            return result.get("success") is True
    except Exception:
        return False


@lru_cache(maxsize=1)
def word_merge_builder_supported() -> bool:
    """True when DocumentServer Builder can merge two docx files on this installation."""
    cfg = get_e2e_config()
    if not cfg.has_jwt or not cfg.has_source_path:
        return False
    if not documentserver_reachable() or not mcp_reachable():
        return False
    base = cfg.source_path.rsplit("/", 1)[0]
    probe_a = f"{base}/.e2e-merge-cap-a-{uuid.uuid4().hex[:8]}.docx"
    probe_b = f"{base}/.e2e-merge-cap-b-{uuid.uuid4().hex[:8]}.docx"
    probe_out = f"{base}/.e2e-merge-cap-out-{uuid.uuid4().hex[:8]}.docx"
    try:
        with httpx.Client(timeout=180, transport=_mcp_http_transport()) as client:
            for path, text in ((probe_a, "merge cap A"), (probe_b, "merge cap B")):
                resp = client.post(
                    mcp_protocol_url(),
                    json={
                        "jsonrpc": "2.0",
                        "method": "tools/call",
                        "params": {
                            "name": "office_create_word",
                            "arguments": {
                                "sections": [{"type": "paragraph", "text": text}],
                                "output_path": path,
                            },
                        },
                        "id": "merge-capability-create",
                    },
                    headers={
                        "Content-Type": "application/json",
                        "Accept": "application/json, text/event-stream",
                    },
                )
                resp.raise_for_status()
                created = _parse_mcp_tool_response(resp.text)
                if not created.get("success"):
                    return False
            resp = client.post(
                mcp_protocol_url(),
                json={
                    "jsonrpc": "2.0",
                    "method": "tools/call",
                    "params": {
                        "name": "office_merge_word",
                        "arguments": {
                            "source_paths": [probe_a, probe_b],
                            "output_path": probe_out,
                            "options": {"add_page_break": False, "add_toc": False},
                        },
                    },
                    "id": "merge-capability-probe",
                },
                headers={
                    "Content-Type": "application/json",
                    "Accept": "application/json, text/event-stream",
                },
            )
            resp.raise_for_status()
            merged = _parse_mcp_tool_response(resp.text)
            return merged.get("success") is True
    except Exception:
        return False


def _mcp_call_tool(client: httpx.Client, tool_name: str, arguments: dict, *, req_id: str) -> dict:
    resp = client.post(
        mcp_protocol_url(),
        json={
            "jsonrpc": "2.0",
            "method": "tools/call",
            "params": {"name": tool_name, "arguments": arguments},
            "id": req_id,
        },
        headers={
            "Content-Type": "application/json",
            "Accept": "application/json, text/event-stream",
        },
    )
    resp.raise_for_status()
    return _parse_mcp_tool_response(resp.text)


def _spreadsheet_storage_base(cfg) -> str:
    """Directory prefix for spreadsheet E2E probe/output paths (E2E_SPREADSHEET_SOURCE_PATH)."""
    return cfg.spreadsheet_source_path.rsplit("/", 1)[0]


@lru_cache(maxsize=1)
def spreadsheet_ods_builder_supported() -> bool:
    """True when DocumentServer Builder can CreateFile('ods') via MCP on this installation."""
    cfg = get_e2e_config()
    if not cfg.has_jwt or not cfg.has_spreadsheet_source_path:
        return False
    if not documentserver_reachable() or not mcp_reachable():
        return False
    base = _spreadsheet_storage_base(cfg)
    probe_path = f"{base}/.e2e-ods-capability-{uuid.uuid4().hex[:8]}.ods"
    try:
        with httpx.Client(timeout=120, transport=_mcp_http_transport()) as client:
            result = _mcp_call_tool(
                client,
                "office_create_spreadsheet",
                {
                    "sheets": [{"name": "Probe", "rows": [["ok"]]}],
                    "output_path": probe_path,
                },
                req_id="ods-capability-probe",
            )
            return result.get("success") is True
    except Exception:
        return False


@lru_cache(maxsize=1)
def spreadsheet_fine_read_supported() -> bool:
    """True when GetSheetsCount sidecar fine read works via MCP (ADR-021 E2E gate)."""
    cfg = get_e2e_config()
    if not cfg.has_jwt or not cfg.has_spreadsheet_source_path:
        return False
    if not documentserver_reachable() or not mcp_reachable():
        return False
    base = _spreadsheet_storage_base(cfg)
    probe_path = f"{base}/.e2e-fine-read-capability-{uuid.uuid4().hex[:8]}.xlsx"
    try:
        with httpx.Client(timeout=180, transport=_mcp_http_transport()) as client:
            created = _mcp_call_tool(
                client,
                "office_create_spreadsheet",
                {
                    "sheets": [{"name": "Probe", "rows": [["a", "b"], ["1", "2"]]}],
                    "output_path": probe_path,
                },
                req_id="fine-read-capability-create",
            )
            if not created.get("success"):
                return False
            read = _mcp_call_tool(
                client,
                "office_read_spreadsheet",
                {
                    "source_path": probe_path,
                    "format": "structured",
                    "options": {"read_mode": "fine"},
                },
                req_id="fine-read-capability-read",
            )
            return read.get("success") is True and read.get("read_mode") == "fine"
    except Exception:
        return False


@lru_cache(maxsize=1)
def spreadsheet_merge_builder_supported() -> bool:
    """True when DocumentServer Builder can merge two xlsx workbooks via MCP."""
    cfg = get_e2e_config()
    if not cfg.has_jwt or not cfg.has_spreadsheet_source_path:
        return False
    if not documentserver_reachable() or not mcp_reachable():
        return False
    base = _spreadsheet_storage_base(cfg)
    probe_a = f"{base}/.e2e-sheet-merge-a-{uuid.uuid4().hex[:8]}.xlsx"
    probe_b = f"{base}/.e2e-sheet-merge-b-{uuid.uuid4().hex[:8]}.xlsx"
    probe_out = f"{base}/.e2e-sheet-merge-out-{uuid.uuid4().hex[:8]}.xlsx"
    sheet = {"name": "Probe", "rows": [["merge-cap"]]}
    try:
        with httpx.Client(timeout=180, transport=_mcp_http_transport()) as client:
            for path in (probe_a, probe_b):
                created = _mcp_call_tool(
                    client,
                    "office_create_spreadsheet",
                    {"sheets": [sheet], "output_path": path},
                    req_id="sheet-merge-capability-create",
                )
                if not created.get("success"):
                    return False
            merged = _mcp_call_tool(
                client,
                "office_merge_spreadsheets",
                {
                    "source_paths": [probe_a, probe_b],
                    "output_path": probe_out,
                    "options": {"rename_conflicts": True},
                },
                req_id="sheet-merge-capability-probe",
            )
            return merged.get("success") is True
    except Exception:
        return False


@lru_cache(maxsize=1)
def spreadsheet_edit_supported() -> bool:
    """True when Builder edit-on-source (edit/template) works via MCP."""
    cfg = get_e2e_config()
    if not cfg.has_jwt or not cfg.has_spreadsheet_source_path:
        return False
    if not documentserver_reachable() or not mcp_reachable():
        return False
    base = _spreadsheet_storage_base(cfg)
    source = f"{base}/.e2e-sheet-edit-src-{uuid.uuid4().hex[:8]}.xlsx"
    edited = f"{base}/.e2e-sheet-edit-out-{uuid.uuid4().hex[:8]}.xlsx"
    try:
        with httpx.Client(timeout=180, transport=_mcp_http_transport()) as client:
            created = _mcp_call_tool(
                client,
                "office_create_spreadsheet",
                {
                    "sheets": [{"name": "S1", "rows": [["x"]]}],
                    "output_path": source,
                },
                req_id="sheet-edit-capability-create",
            )
            if not created.get("success"):
                return False
            edited_result = _mcp_call_tool(
                client,
                "office_edit_spreadsheet",
                {
                    "source_path": source,
                    "output_path": edited,
                    "operations": [
                        {"op": "set_cell", "sheet_name": "S1", "cell": "A1", "value": "y"},
                    ],
                },
                req_id="sheet-edit-capability-probe",
            )
            return edited_result.get("success") is True
    except Exception:
        return False


def _presentation_storage_base(cfg) -> str:
    """Directory prefix for presentation E2E probe/output paths (E2E_SOURCE_PATH)."""
    return cfg.source_path.rsplit("/", 1)[0]


def _presentation_layouts(ext: str) -> list[str]:
    import json
    from pathlib import Path

    name = "layouts_odp.json" if ext == "odp" else "layouts_pptx.json"
    path = Path(__file__).resolve().parent / "presentation" / "fixtures" / name
    return json.loads(path.read_text())


@lru_cache(maxsize=1)
def presentation_pptx_create_supported() -> bool:
    """True when DocumentServer Builder can CreateFile('pptx') via MCP."""
    cfg = get_e2e_config()
    if not cfg.has_jwt or not cfg.has_source_path:
        return False
    if not documentserver_reachable() or not mcp_reachable():
        return False
    base = _presentation_storage_base(cfg)
    probe_path = f"{base}/.e2e-pptx-capability-{uuid.uuid4().hex[:8]}.pptx"
    try:
        with httpx.Client(timeout=120, transport=_mcp_http_transport()) as client:
            result = _mcp_call_tool(
                client,
                "office_create_presentation",
                {
                    "slides": [{"layout": "Title Slide", "title": "pptx capability probe"}],
                    "output_path": probe_path,
                    "options": {"allowed_layouts": _presentation_layouts("pptx")},
                },
                req_id="pptx-capability-probe",
            )
            return result.get("success") is True
    except Exception:
        return False


@lru_cache(maxsize=1)
def presentation_merge_supported() -> bool:
    """True when DocumentServer Builder can merge two pptx decks via MCP."""
    cfg = get_e2e_config()
    if not cfg.has_jwt or not cfg.has_source_path:
        return False
    if not documentserver_reachable() or not mcp_reachable():
        return False
    if not presentation_pptx_create_supported():
        return False
    base = _presentation_storage_base(cfg)
    layouts = _presentation_layouts("pptx")
    slide = {"layout": "Title Slide", "title": "merge cap"}
    probe_a = f"{base}/.e2e-pres-merge-a-{uuid.uuid4().hex[:8]}.pptx"
    probe_b = f"{base}/.e2e-pres-merge-b-{uuid.uuid4().hex[:8]}.pptx"
    probe_out = f"{base}/.e2e-pres-merge-out-{uuid.uuid4().hex[:8]}.pptx"
    try:
        with httpx.Client(timeout=180, transport=_mcp_http_transport()) as client:
            for path in (probe_a, probe_b):
                created = _mcp_call_tool(
                    client,
                    "office_create_presentation",
                    {"slides": [slide], "output_path": path, "options": {"allowed_layouts": layouts}},
                    req_id="pres-merge-capability-create",
                )
                if not created.get("success"):
                    return False
            merged = _mcp_call_tool(
                client,
                "office_merge_presentations",
                {"source_paths": [probe_a, probe_b], "output_path": probe_out},
                req_id="pres-merge-capability-probe",
            )
            return merged.get("success") is True
    except Exception:
        return False


@lru_cache(maxsize=1)
def presentation_odp_create_supported() -> bool:
    """True when DocumentServer Builder can CreateFile('odp') via MCP."""
    cfg = get_e2e_config()
    if not cfg.has_jwt or not cfg.has_source_path:
        return False
    if not documentserver_reachable() or not mcp_reachable():
        return False
    base = _presentation_storage_base(cfg)
    probe_path = f"{base}/.e2e-odp-capability-{uuid.uuid4().hex[:8]}.odp"
    try:
        with httpx.Client(timeout=120, transport=_mcp_http_transport()) as client:
            result = _mcp_call_tool(
                client,
                "office_create_presentation",
                {
                    "slides": [{"layout": "Title", "title": "odp capability probe"}],
                    "output_path": probe_path,
                    "options": {"allowed_layouts": _presentation_layouts("odp")},
                },
                req_id="odp-capability-probe",
            )
            return result.get("success") is True
    except Exception:
        return False


@lru_cache(maxsize=1)
def presentation_edit_supported() -> bool:
    """True when Builder edit-on-source works for presentations via MCP."""
    cfg = get_e2e_config()
    if not cfg.has_jwt or not cfg.has_source_path:
        return False
    if not documentserver_reachable() or not mcp_reachable():
        return False
    if not presentation_pptx_create_supported():
        return False
    base = _presentation_storage_base(cfg)
    source = f"{base}/.e2e-pres-edit-src-{uuid.uuid4().hex[:8]}.pptx"
    edited = f"{base}/.e2e-pres-edit-out-{uuid.uuid4().hex[:8]}.pptx"
    layouts = _presentation_layouts("pptx")
    try:
        with httpx.Client(timeout=180, transport=_mcp_http_transport()) as client:
            created = _mcp_call_tool(
                client,
                "office_create_presentation",
                {
                    "slides": [{"layout": "Title Slide", "title": "edit cap"}],
                    "output_path": source,
                    "options": {"allowed_layouts": layouts},
                },
                req_id="pres-edit-capability-create",
            )
            if not created.get("success"):
                return False
            edited_result = _mcp_call_tool(
                client,
                "office_edit_presentation",
                {
                    "source_path": source,
                    "output_path": edited,
                    "operations": [{"op": "set_title", "slide_index": 0, "text": "edited"}],
                },
                req_id="pres-edit-capability-probe",
            )
            return edited_result.get("success") is True
    except Exception:
        return False


def _pdf_storage_base(cfg) -> str:
    """Directory prefix for PDF E2E probe/output paths (E2E_SOURCE_PATH)."""
    return cfg.source_path.rsplit("/", 1)[0]


@lru_cache(maxsize=1)
def pdf_fine_read_supported() -> bool:
    """True when office_create_pdf + office_read_pdf fine (2 pages) works via MCP (ADR-021)."""
    cfg = get_e2e_config()
    if not cfg.has_jwt or not cfg.has_source_path:
        return False
    if not documentserver_reachable() or not mcp_reachable():
        return False
    base = _pdf_storage_base(cfg)
    probe_path = f"{base}/.e2e-pdf-fine-{uuid.uuid4().hex[:8]}.pdf"
    pages = [
        {"blocks": [{"type": "paragraph", "text": "PDF fine-read probe page one"}]},
        {"blocks": [{"type": "paragraph", "text": "PDF fine-read probe page two"}]},
    ]
    create_attempts = (
        {"pages": pages, "output_path": probe_path},
        {"pages": pages, "output_path": probe_path, "options": {"create_mode": "via_docx"}},
    )
    try:
        with httpx.Client(timeout=180, transport=_mcp_http_transport()) as client:
            for create_args in create_attempts:
                created = _mcp_call_tool(
                    client,
                    "office_create_pdf",
                    create_args,
                    req_id="pdf-fine-read-capability-create",
                )
                if not created.get("success"):
                    continue
                read = _mcp_call_tool(
                    client,
                    "office_read_pdf",
                    {
                        "source_path": probe_path,
                        "format": "structured",
                        "options": {"read_mode": "fine"},
                    },
                    req_id="pdf-fine-read-capability-read",
                )
                if (
                    read.get("success") is True
                    and read.get("read_mode") == "fine"
                    and read.get("page_count", 0) >= 2
                ):
                    return True
        return False
    except Exception:
        return False


@lru_cache(maxsize=1)
def pdf_edit_supported() -> bool:
    """True when office_edit_pdf add_paragraph on a created PDF works via MCP."""
    cfg = get_e2e_config()
    if not cfg.has_jwt or not cfg.has_source_path:
        return False
    if not documentserver_reachable() or not mcp_reachable():
        return False
    if not pdf_fine_read_supported():
        return False
    base = _pdf_storage_base(cfg)
    source = f"{base}/.e2e-pdf-edit-src-{uuid.uuid4().hex[:8]}.pdf"
    edited = f"{base}/.e2e-pdf-edit-out-{uuid.uuid4().hex[:8]}.pdf"
    pages = [{"blocks": [{"type": "paragraph", "text": "PDF edit probe source"}]}]
    create_attempts = (
        {"pages": pages, "output_path": source},
        {"pages": pages, "output_path": source, "options": {"create_mode": "via_docx"}},
    )
    try:
        with httpx.Client(timeout=180, transport=_mcp_http_transport()) as client:
            created_ok = False
            for create_args in create_attempts:
                created = _mcp_call_tool(
                    client,
                    "office_create_pdf",
                    create_args,
                    req_id="pdf-edit-capability-create",
                )
                if created.get("success"):
                    created_ok = True
                    break
            if not created_ok:
                return False
            edited_result = _mcp_call_tool(
                client,
                "office_edit_pdf",
                {
                    "source_path": source,
                    "output_path": edited,
                    "operations": [
                        {
                            "op": "add_paragraph",
                            "page_index": 0,
                            "text": "PDF edit probe added",
                        }
                    ],
                },
                req_id="pdf-edit-capability-probe",
            )
            return edited_result.get("success") is True
    except Exception:
        return False


def _upload_fixture_sync(storage_path: str, content: bytes) -> None:
    """Upload bytes to s3:// using project venv (sync; for capability probes)."""
    import subprocess

    from pathlib import Path

    repo_root = Path(__file__).resolve().parents[2]
    venv_python = repo_root / ".venv" / "bin" / "python"
    if not venv_python.is_file():
        raise RuntimeError("Project .venv/python required for fixture upload")

    tmp_path = repo_root / ".tmp-e2e-fixture-upload.bin"
    tmp_path.write_bytes(content)
    script = f"""
import asyncio
from pathlib import Path
from tests.env_test import load_env_test
from aiecs.tools.office_tool.core.storage import upload_to_storage

load_env_test()

async def main() -> None:
    data = Path({str(tmp_path)!r}).read_bytes()
    await upload_to_storage(data, {storage_path!r})

asyncio.run(main())
"""
    try:
        proc = subprocess.run(
            [str(venv_python), "-c", script],
            cwd=str(repo_root),
            capture_output=True,
            text=True,
        )
        if proc.returncode != 0:
            raise RuntimeError(proc.stderr or proc.stdout or "fixture upload failed")
    finally:
        tmp_path.unlink(missing_ok=True)


@lru_cache(maxsize=1)
def pdf_fill_form_supported() -> bool:
    """True when office_fill_pdf_form succeeds on acroform_template.pdf via MCP."""
    import os
    from pathlib import Path

    cfg = get_e2e_config()
    if not cfg.has_jwt or not cfg.has_source_path:
        return False
    if not documentserver_reachable() or not mcp_reachable():
        return False

    configured = os.environ.get("E2E_PDF_ACROFORM_SOURCE_PATH", "").strip()
    base = _pdf_storage_base(cfg)
    source = configured or f"{base}/.e2e-pdf-fill-src-{uuid.uuid4().hex[:8]}.pdf"
    output = f"{base}/.e2e-pdf-fill-out-{uuid.uuid4().hex[:8]}.pdf"

    if not configured:
        fixture = Path(__file__).resolve().parent / "pdf" / "fixtures" / "acroform_template.pdf"
        if not fixture.is_file():
            return False
        try:
            _upload_fixture_sync(source, fixture.read_bytes())
        except Exception:
            return False

    try:
        with httpx.Client(timeout=180, transport=_mcp_http_transport()) as client:
            result = _mcp_call_tool(
                client,
                "office_fill_pdf_form",
                {
                    "source_path": source,
                    "data": {"company_name": "PDF fill probe"},
                    "output_path": output,
                },
                req_id="pdf-fill-capability-probe",
            )
            return result.get("success") is True
    except Exception:
        return False
