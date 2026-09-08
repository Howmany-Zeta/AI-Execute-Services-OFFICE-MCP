"""Parse job store: Redis refs only, injectable backend for tests (ADR-048)."""

from __future__ import annotations

import json
import logging
import secrets
import time
from typing import Any, Protocol

from aiecs.config import get_parse_job_config
from aiecs.tools.office_tool.core.parse_security import hash_secret, secrets_equal

logger = logging.getLogger(__name__)

QUEUE_KEY = "office:parse:queue"


class ParseJobBackend(Protocol):
    async def hset(self, key: str, mapping: dict[str, str], ttl: int) -> None: ...
    async def hgetall(self, key: str) -> dict[str, str]: ...
    async def hset_fields(self, key: str, mapping: dict[str, str]) -> None: ...
    async def lpush(self, key: str, value: str) -> None: ...
    async def rpop(self, key: str) -> str | None: ...
    async def scan_job_keys(self, pattern: str) -> list[str]: ...


class MemoryParseJobBackend:
    def __init__(self) -> None:
        self.hashes: dict[str, dict[str, str]] = {}
        self.lists: dict[str, list[str]] = {}

    async def hset(self, key: str, mapping: dict[str, str], ttl: int) -> None:
        self.hashes[key] = dict(mapping)

    async def hgetall(self, key: str) -> dict[str, str]:
        return dict(self.hashes.get(key) or {})

    async def hset_fields(self, key: str, mapping: dict[str, str]) -> None:
        self.hashes.setdefault(key, {}).update(mapping)

    async def lpush(self, key: str, value: str) -> None:
        self.lists.setdefault(key, []).insert(0, value)

    async def rpop(self, key: str) -> str | None:
        lst = self.lists.get(key) or []
        if not lst:
            return None
        return lst.pop()

    async def scan_job_keys(self, pattern: str) -> list[str]:
        prefix = pattern.replace("*", "")
        return [k for k in self.hashes if k.startswith(prefix)]


class RedisParseJobBackend:
    async def _redis(self):
        from aiecs.infrastructure.persistence import get_redis_client

        wrapper = await get_redis_client()
        return await wrapper.get_client()

    async def hset(self, key: str, mapping: dict[str, str], ttl: int) -> None:
        r = await self._redis()
        await r.hset(key, mapping=mapping)
        await r.expire(key, ttl)

    async def hgetall(self, key: str) -> dict[str, str]:
        r = await self._redis()
        raw = await r.hgetall(key)
        out = {}
        for k, v in (raw or {}).items():
            ks = k.decode() if isinstance(k, bytes) else k
            vs = v.decode() if isinstance(v, bytes) else v
            out[ks] = vs
        return out

    async def hset_fields(self, key: str, mapping: dict[str, str]) -> None:
        r = await self._redis()
        await r.hset(key, mapping=mapping)

    async def lpush(self, key: str, value: str) -> None:
        r = await self._redis()
        await r.lpush(key, value)

    async def rpop(self, key: str) -> str | None:
        r = await self._redis()
        val = await r.rpop(key)
        if val is None:
            return None
        return val.decode() if isinstance(val, bytes) else val

    async def scan_job_keys(self, pattern: str) -> list[str]:
        r = await self._redis()
        keys: list[str] = []
        async for key in r.scan_iter(match=pattern):
            keys.append(key.decode() if isinstance(key, bytes) else key)
        return keys


_backend: ParseJobBackend | None = None


def job_store_ready() -> bool:
    """True when tests injected a backend or Redis is the configured store."""
    return _backend is not None


def set_parse_job_backend(backend: ParseJobBackend | None) -> None:
    global _backend
    _backend = backend


def get_parse_job_backend() -> ParseJobBackend:
    if _backend is not None:
        return _backend
    return RedisParseJobBackend()


def _job_key(job_id: str) -> str:
    tenant = get_parse_job_config().tenant_id or "global"
    return f"office:parse:{tenant}:{job_id}"


async def create_queued_job(payload: dict[str, Any]) -> tuple[str, str]:
    cfg = get_parse_job_config()
    job_id = secrets.token_urlsafe(32)
    job_secret = secrets.token_urlsafe(32)
    now = str(time.time())
    record = {
        "job_id": job_id,
        "secret_hash": hash_secret(job_secret),
        "status": "queued",
        "created_at": now,
        "updated_at": now,
        "payload": json.dumps(payload, separators=(",", ":")),
        "error": "",
        "error_code": "",
        "operation": "",
        "parser_json": "",
        "canonical_ref_json": "",
        "structure_ref_json": "",
    }
    backend = get_parse_job_backend()
    await backend.hset(_job_key(job_id), record, cfg.job_ttl_sec)
    await backend.lpush(QUEUE_KEY, job_id)
    return job_id, job_secret


async def load_job(job_id: str) -> dict[str, str] | None:
    data = await get_parse_job_backend().hgetall(_job_key(job_id))
    return data or None


async def authenticate_job(job_id: str, job_secret: str) -> dict[str, str] | None:
    job = await load_job(job_id)
    if not job or not secrets_equal(job_secret, job.get("secret_hash", "")):
        return None
    return job


async def update_job(job_id: str, **fields: str) -> None:
    if "updated_at" not in fields:
        fields["updated_at"] = str(time.time())
    await get_parse_job_backend().hset_fields(_job_key(job_id), fields)


async def claim_next_job_id() -> str | None:
    return await get_parse_job_backend().rpop(QUEUE_KEY)


async def recover_stale_running() -> int:
    cfg = get_parse_job_config()
    tenant = cfg.tenant_id or "global"
    keys = await get_parse_job_backend().scan_job_keys(f"office:parse:{tenant}:*")
    now = time.time()
    marked = 0
    for key in keys:
        job = await get_parse_job_backend().hgetall(key)
        if job.get("status") != "running":
            continue
        job_id = job.get("job_id") or key.rsplit(":", 1)[-1]
        if job.get("operation"):
            await get_parse_job_backend().lpush(QUEUE_KEY, job_id)
            continue
        updated = float(job.get("updated_at") or 0)
        if now - updated < cfg.running_stale_sec:
            continue
        await update_job(job_id, status="failed", error_code="worker_restarted", error="worker_restarted")
        marked += 1
    return marked
