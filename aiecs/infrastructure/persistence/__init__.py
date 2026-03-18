"""Infrastructure persistence module

Contains data persistence and storage infrastructure for MCP server.

This module provides:
- Redis client for caching (production-grade with connection pooling, health checks, SSL support)

For MCP server, only Redis client is actively used.
Legacy components (DatabaseManager, ContextEngine) are not needed.
"""

from .redis_client import (
    RedisClient,
    get_redis_client,
    initialize_redis_client,
    close_redis_client,
    redis_client,
)

__all__ = [
    "RedisClient",
    "get_redis_client",
    "initialize_redis_client",
    "close_redis_client",
    "redis_client",
]
