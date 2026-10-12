"""office_parse_document / status (ADR-048)."""

from unittest.mock import AsyncMock, patch

import pytest

from aiecs.config.config import get_parse_job_config
from aiecs.tools.office_tool.core.parse_job import (
    MemoryParseJobBackend,
    authenticate_job,
    create_queued_job,
    recover_stale_running,
    set_parse_job_backend,
    update_job,
)
from aiecs.tools.office_tool.parse.tools.status import office_parse_document_status
from aiecs.tools.office_tool.parse.tools.submit import office_parse_document

pytestmark = pytest.mark.asyncio


@pytest.fixture
def memory_jobs(monkeypatch):
    backend = MemoryParseJobBackend()
    set_parse_job_backend(backend)
    monkeypatch.setenv("PARSE_OUTPUT_ALLOWED_PREFIXES", "s3://allowed/derived/")
    get_parse_job_config.cache_clear()
    yield backend
    set_parse_job_backend(None)
    get_parse_job_config.cache_clear()


async def test_submit_requires_output_path(memory_jobs):
    result = await office_parse_document(source_path="s3://allowed/in/doc.pdf")
    assert result.get("isError") is True


async def test_submit_unsupported_md(memory_jobs):
    result = await office_parse_document(
        source_path="s3://allowed/in/notes.md",
        output_path="s3://allowed/derived/e/canonical.md",
    )
    assert result.get("isError") is True
    assert "unsupported" in result.get("text", "")


async def test_submit_xlsx_unsupported(memory_jobs):
    result = await office_parse_document(
        source_path="s3://b/file.xlsx",
        output_path="s3://allowed/derived/e/canonical.md",
    )
    assert result.get("isError") is True


async def test_submit_djvu_unsupported(memory_jobs):
    result = await office_parse_document(
        source_path="s3://b/scan.djvu",
        output_path="s3://allowed/derived/e/canonical.md",
    )
    assert result.get("isError") is True


async def test_submit_epub_unsupported(memory_jobs):
    result = await office_parse_document(
        source_path="s3://b/book.epub",
        output_path="s3://allowed/derived/e/canonical.md",
    )
    assert result.get("isError") is True


async def test_output_path_equals_source(memory_jobs):
    result = await office_parse_document(
        source_path="s3://allowed/derived/e/file.pdf",
        output_path="s3://allowed/derived/e/file.pdf",
    )
    assert result.get("isError") is True


async def test_callback_url_rejected_when_webhook_disabled(memory_jobs):
    result = await office_parse_document(
        source_path="s3://allowed/in/file.pdf",
        output_path="s3://allowed/derived/e/canonical.md",
        callback_url="https://hooks.scholar-kg.example/cb",
    )
    assert result.get("isError") is True


async def test_submit_doc_ok(memory_jobs):
    result = await office_parse_document(
        source_path="s3://allowed/in/file.doc",
        output_path="s3://allowed/derived/e/canonical.md",
    )
    assert result.get("success") is True
    assert result.get("status") == "queued"
    assert len(result["job_id"]) >= 32
    assert result["job_secret"]


async def test_output_path_outside_prefix(memory_jobs):
    result = await office_parse_document(
        source_path="s3://allowed/in/file.pdf",
        output_path="s3://other/derived/e/canonical.md",
    )
    assert result.get("isError") is True


async def test_status_missing_secret(memory_jobs):
    created = await office_parse_document(
        source_path="s3://allowed/in/file.pdf",
        output_path="s3://allowed/derived/e/canonical.md",
    )
    result = await office_parse_document_status(job_id=created["job_id"])
    assert result.get("isError") is True
    assert "not found" in result.get("text", "").lower()


async def test_status_without_secret(memory_jobs):
    created = await office_parse_document(
        source_path="s3://allowed/in/file.pdf",
        output_path="s3://allowed/derived/e/canonical.md",
    )
    result = await office_parse_document_status(job_id=created["job_id"], job_secret="wrong")
    assert result.get("isError") is True
    assert "not found" in result.get("text", "").lower()


async def test_status_guessable_id(memory_jobs):
    result = await office_parse_document_status(job_id="1", job_secret="x")
    assert result.get("isError") is True


async def test_require_object_source_rejects_url(memory_jobs, monkeypatch):
    monkeypatch.setenv("PARSE_REQUIRE_OBJECT_SOURCE", "true")
    get_parse_job_config.cache_clear()
    result = await office_parse_document(
        source_url="https://example.com/a.pdf",
        output_path="s3://allowed/derived/e/canonical.md",
    )
    assert result.get("isError") is True
    get_parse_job_config.cache_clear()


async def test_stale_running_recovered(memory_jobs):
    job_id, secret = await create_queued_job({"output_path": "s3://allowed/derived/e/canonical.md"})
    await update_job(job_id, status="running", updated_at="0")
    n = await recover_stale_running()
    assert n == 1
    job = await authenticate_job(job_id, secret)
    assert job["status"] == "failed"
    assert job["error_code"] == "worker_restarted"


async def test_running_with_operation_requeued(memory_jobs):
    job_id, secret = await create_queued_job({"output_path": "s3://allowed/derived/e/canonical.md"})
    await update_job(job_id, status="running", updated_at="0", operation="operations/op1")
    n = await recover_stale_running()
    assert n == 0
    job = await authenticate_job(job_id, secret)
    assert job["status"] == "running"
    assert job_id in memory_jobs.lists.get("office:parse:queue", [])


async def test_status_default_no_structure_body(memory_jobs):
    job_id, secret = await create_queued_job({})
    huge = [{"kind": "page", "blocks": [{"text": "x" * 100}]} for _ in range(20)]
    await update_job(
        job_id,
        status="succeeded",
        parser_json='{"name":"document_ai","version":"v"}',
        canonical_ref_json='{"output_path":"s3://allowed/derived/e/canonical.md","bytes":10,"sha256":"aa"}',
        structure_ref_json='{"output_path":"s3://allowed/derived/e/canonical.structure.json","bytes":999999,"sha256":"bb"}',
    )
    result = await office_parse_document_status(job_id=job_id, job_secret=secret)
    assert result.get("success") is True
    assert "structure" not in result
    assert "markdown" not in result
    assert result["structure_ref"]["output_path"].endswith(".structure.json")
    _ = huge


async def test_worker_online_limit_batches_once(memory_jobs):
    from aiecs.clients.documentai_client import DocumentAIOnlineLimitError
    from aiecs.tools.office_tool.core.parse_worker import run_parse_job

    job_id, _secret = await create_queued_job({
        "source_path": "gs://b/doc.pdf",
        "engine": "document_ai",
        "output_path": "s3://allowed/derived/e/canonical.md",
        "output_format": ["markdown", "structured"],
    })
    client = AsyncMock()
    client.process_pdf_online = AsyncMock(side_effect=DocumentAIOnlineLimitError("15 pages"))
    client.submit_pdf_batch = AsyncMock(return_value="operations/op1")
    client.poll_batch_operation = AsyncMock(return_value={"documentLayout": {"blocks": []}, "done": True})

    with patch("aiecs.tools.office_tool.core.parse_worker.get_documentai_client", return_value=client), \
         patch("aiecs.tools.office_tool.core.parse_worker.get_documentai_config") as dai_cfg, \
         patch("aiecs.tools.office_tool.core.dai_batch.get_documentai_config") as batch_cfg, \
         patch("aiecs.tools.office_tool.core.parse_worker.stat_object_size", new=AsyncMock(return_value=1000)), \
         patch("aiecs.tools.office_tool.core.dai_batch.upload_to_storage", new=AsyncMock()), \
         patch("aiecs.tools.office_tool.core.dai_batch.delete_object", new=AsyncMock()), \
         patch("aiecs.tools.office_tool.core.dai_batch.delete_prefix", new=AsyncMock()), \
         patch("aiecs.tools.office_tool.core.parse_worker.download_object_bytes", new=AsyncMock(return_value=b"%PDF-1.4")):
        for cfg in (dai_cfg, batch_cfg):
            cfg.return_value.batch_output_prefix = "gs://staging/batch/"
            cfg.return_value.processor_version = "v1"
            cfg.return_value.is_configured.return_value = True
        await run_parse_job(job_id)

    assert client.process_pdf_online.await_count == 1
    assert client.submit_pdf_batch.await_count == 1
    assert client.poll_batch_operation.await_count == 1


async def test_page_limit_exceeded(memory_jobs):
    from aiecs.tools.office_tool.core.parse_worker import run_parse_job

    job_id, secret = await create_queued_job({
        "source_path": "gs://b/doc.pdf",
        "engine": "document_ai",
        "output_path": "s3://allowed/derived/e/canonical.md",
        "output_format": ["markdown"],
    })
    with patch("aiecs.tools.office_tool.core.parse_worker.get_documentai_config") as dai_cfg, \
         patch("aiecs.tools.office_tool.core.parse_worker.stat_object_size", new=AsyncMock(return_value=1000)), \
         patch("aiecs.tools.office_tool.core.parse_worker.download_object_bytes", new=AsyncMock(return_value=b"%PDF-1.4")), \
         patch("aiecs.tools.office_tool.core.parse_worker.estimate_pdf_pages", return_value=501):
        dai_cfg.return_value.is_configured.return_value = True
        dai_cfg.return_value.batch_output_prefix = "gs://staging/batch/"
        dai_cfg.return_value.processor_version = "v1"
        await run_parse_job(job_id)
    job = await authenticate_job(job_id, secret)
    assert job["status"] == "failed"
    assert job["error_code"] == "page_limit_exceeded"


async def test_dai_not_configured_fails_job(memory_jobs):
    from aiecs.tools.office_tool.core.parse_worker import run_parse_job

    job_id, secret = await create_queued_job({
        "source_path": "gs://b/doc.pdf",
        "engine": "document_ai",
        "output_path": "s3://allowed/derived/e/canonical.md",
        "output_format": ["markdown"],
    })
    with patch("aiecs.tools.office_tool.core.parse_worker.get_documentai_config") as dai_cfg, \
         patch("aiecs.tools.office_tool.core.parse_worker.stat_object_size", new=AsyncMock(return_value=1000)), \
         patch("aiecs.tools.office_tool.core.parse_worker.download_object_bytes", new=AsyncMock(return_value=b"%PDF-1.4")):
        dai_cfg.return_value.is_configured.return_value = False
        await run_parse_job(job_id)
    job = await authenticate_job(job_id, secret)
    assert job["status"] == "failed"
