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
