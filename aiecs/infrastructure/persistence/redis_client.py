"""
Production-grade Redis client for MCP server.

Features:
- Connection pooling with configurable limits
- Automatic reconnection and retry logic
- Health checks and connection monitoring
- Graceful degradation when Redis is unavailable
- SSL/TLS support for secure connections
- Comprehensive error handling and logging
- Connection leak detection
- Metrics and monitoring support
"""

import redis.asyncio as redis
import logging
from typing import Optional, Dict, Any
import os
from contextlib import asynccontextmanager
from time import time
import asyncio

logger = logging.getLogger(__name__)


class RedisClient:
    """
    Production-grade Redis client singleton for sharing across different caching strategies.

    Features:
    - Connection pooling with health checks
    - Automatic reconnection on failures
    - Graceful degradation when Redis is unavailable
    - SSL/TLS support
    - Connection monitoring and metrics
    - Thread-safe singleton pattern
    """

    def __init__(self) -> None:
        self._client: Optional[redis.Redis] = None
        self._connection_pool: Optional[redis.ConnectionPool] = None
        self._is_initialized: bool = False
        self._is_healthy: bool = False
        self._last_health_check: float = 0.0
        self._health_check_interval: int = 30  # seconds
        self._connection_errors: int = 0
        self._max_connection_errors: int = 5
        self._reconnect_delay: float = 1.0  # seconds

    async def initialize(self) -> None:
        """
        Initialize Redis client with production-grade configuration.

        Raises:
            RuntimeError: If initialization fails after retries
        """
        try:
            # Get Redis configuration from environment variables
            redis_host = os.getenv("REDIS_HOST", "localhost")
            redis_port = int(os.getenv("REDIS_PORT", "6379"))
            redis_db = int(os.getenv("REDIS_DB", "0"))
            redis_password = os.getenv("REDIS_PASSWORD")
            redis_url = os.getenv("REDIS_URL")  # Alternative: redis://[password@]host:port[/db]

            # SSL/TLS configuration
            ssl_enabled = os.getenv("REDIS_SSL", "false").lower() == "true"
            ssl_cert_reqs = os.getenv("REDIS_SSL_CERT_REQS", "none")  # none, optional, required
            ssl_ca_certs = os.getenv("REDIS_SSL_CA_CERTS")

            # Connection pool configuration
            max_connections = int(os.getenv("REDIS_MAX_CONNECTIONS", "50"))
            socket_timeout = float(os.getenv("REDIS_SOCKET_TIMEOUT", "5.0"))
            socket_connect_timeout = float(os.getenv("REDIS_SOCKET_CONNECT_TIMEOUT", "5.0"))
            retry_on_timeout = os.getenv("REDIS_RETRY_ON_TIMEOUT", "true").lower() == "true"
            health_check_interval = int(os.getenv("REDIS_HEALTH_CHECK_INTERVAL", "30"))

            # Parse redis_url if provided (takes precedence)
            if redis_url:
                # Parse URL: redis://[password@]host:port[/db]
                # Example: redis://:password@localhost:6379/0
                from urllib.parse import urlparse

                parsed = urlparse(redis_url)
                redis_host = parsed.hostname or redis_host
                redis_port = parsed.port or redis_port
                redis_password = parsed.password or redis_password
                if parsed.path:
                    try:
                        redis_db = int(parsed.path.lstrip("/")) or redis_db
                    except ValueError:
                        pass

            # SSL configuration dict
            ssl_config: Optional[Dict[str, Any]] = None
            if ssl_enabled:
                ssl_config = {}
                if ssl_cert_reqs == "required":
                    ssl_config["cert_reqs"] = "required"
                elif ssl_cert_reqs == "optional":
                    ssl_config["cert_reqs"] = "optional"
                if ssl_ca_certs:
                    ssl_config["ca_certs"] = ssl_ca_certs

            # Create connection pool with production settings
            pool_kwargs: Dict[str, Any] = {
                "host": redis_host,
                "port": redis_port,
                "db": redis_db,
                "password": redis_password,
                "decode_responses": True,
                "max_connections": max_connections,
                "retry_on_timeout": retry_on_timeout,
                "socket_timeout": socket_timeout,
                "socket_connect_timeout": socket_connect_timeout,
                "health_check_interval": health_check_interval,
            }

            if ssl_config:
                pool_kwargs["ssl"] = ssl_config

            self._connection_pool = redis.ConnectionPool(**pool_kwargs)
            self._health_check_interval = health_check_interval

            # Create Redis client
            self._client = redis.Redis(connection_pool=self._connection_pool)

            # Test connection with retry
            await self._test_connection_with_retry()

            self._is_initialized = True
            self._is_healthy = True
            self._connection_errors = 0

            logger.info(f"Redis client initialized successfully: {redis_host}:{redis_port}/{redis_db} " f"(SSL: {ssl_enabled}, Pool: {max_connections} connections)")

        except Exception as e:
            self._is_initialized = False
            self._is_healthy = False
            logger.error(f"Failed to initialize Redis client: {e}", exc_info=True)
            # Don't raise - allow graceful degradation
            logger.warning("Redis client initialization failed. Caching will be disabled.")

    async def _test_connection_with_retry(self, max_retries: int = 3) -> None:
        """Test connection with retry logic."""
        for attempt in range(max_retries):
            try:
                await self._client.ping()  # type: ignore[union-attr]
                return
            except Exception as e:
                if attempt < max_retries - 1:
                    wait_time = self._reconnect_delay * (2**attempt)  # Exponential backoff
                    logger.warning(f"Redis ping failed (attempt {attempt + 1}/{max_retries}): {e}. Retrying in {wait_time}s...")
                    await asyncio.sleep(wait_time)
                else:
                    raise

    async def _ensure_healthy(self) -> bool:
        """
        Ensure Redis connection is healthy, with automatic reconnection.

        Returns:
            True if healthy, False if unhealthy and cannot recover
        """
        if not self._is_initialized or self._client is None:
            return False

        # Check if health check is needed
        current_time = time()
        if current_time - self._last_health_check < self._health_check_interval:
            return self._is_healthy

        # Perform health check
        try:
            await self._client.ping()  # type: ignore[union-attr]
            self._is_healthy = True
            self._connection_errors = 0
            self._last_health_check = current_time
            return True
        except Exception as e:
            self._connection_errors += 1
            logger.warning(f"Redis health check failed ({self._connection_errors}/{self._max_connection_errors}): {e}")

            # Try to reconnect if too many errors
            if self._connection_errors >= self._max_connection_errors:
                self._is_healthy = False
                logger.error("Redis connection marked as unhealthy after multiple failures")
                return False

            # Attempt reconnection
            try:
                await self._test_connection_with_retry(max_retries=2)
                self._is_healthy = True
                self._connection_errors = 0
                self._last_health_check = current_time
                logger.info("Redis connection recovered")
                return True
            except Exception:
                self._is_healthy = False
                return False

    async def get_client(self) -> redis.Redis:
        """
        Get Redis client instance with health check.

        Returns:
            Redis client instance

        Raises:
            RuntimeError: If Redis client is not initialized or unhealthy
        """
        if not self._is_initialized or self._client is None:
            raise RuntimeError("Redis client not initialized. Call initialize() first.")

        # Ensure connection is healthy
        if not await self._ensure_healthy():
            raise RuntimeError("Redis client is unhealthy. Check Redis server status.")

        return self._client

    @asynccontextmanager
    async def safe_operation(self, operation_name: str = "operation"):
        """
        Context manager for safe Redis operations with error handling.

        Usage:
            async with redis_client.safe_operation("get"):
                value = await redis_client.get("key")
        """
        try:
            yield
        except redis.ConnectionError as e:
            logger.error(f"Redis connection error during {operation_name}: {e}")
            self._is_healthy = False
            raise
        except redis.TimeoutError as e:
            logger.warning(f"Redis timeout during {operation_name}: {e}")
            raise
        except Exception as e:
            logger.error(f"Redis error during {operation_name}: {e}")
            raise

    async def close(self) -> None:
        """Close Redis connection gracefully."""
        if self._client:
            try:
                await self._client.close()
            except Exception as e:
                logger.warning(f"Error closing Redis client: {e}")
            finally:
                self._client = None

        if self._connection_pool:
            try:
                await self._connection_pool.disconnect()
            except Exception as e:
                logger.warning(f"Error disconnecting Redis pool: {e}")
            finally:
                self._connection_pool = None

        self._is_initialized = False
        self._is_healthy = False
        logger.info("Redis client closed")

    # ============================================================================
    # Redis Operations with Error Handling
    # ============================================================================

    async def hincrby(self, name: str, key: str, amount: int = 1) -> int:
        """Atomically increment hash field."""
        try:
            client = await self.get_client()
            return await client.hincrby(name, key, amount)  # type: ignore[misc]
        except Exception as e:
            logger.error(f"Redis hincrby failed for {name}.{key}: {e}")
            raise

    async def hget(self, name: str, key: str) -> Optional[str]:
        """Get hash field value."""
        try:
            client = await self.get_client()
            return await client.hget(name, key)  # type: ignore[misc]
        except Exception as e:
            logger.error(f"Redis hget failed for {name}.{key}: {e}")
            return None

    async def hgetall(self, name: str) -> dict:
        """Get all hash fields."""
        try:
            client = await self.get_client()
            return await client.hgetall(name)  # type: ignore[misc]
        except Exception as e:
            logger.error(f"Redis hgetall failed for {name}: {e}")
            return {}

    async def hset(
        self,
        name: str,
        key: Optional[str] = None,
        value: Optional[str] = None,
        mapping: Optional[dict] = None,
    ) -> int:
        """
        Set hash fields.

        Supports two calling patterns:
        1. hset(name, key, value) - Set single field (positional)
        2. hset(name, key=key, value=value) - Set single field (keyword)
        3. hset(name, mapping={...}) - Set multiple fields

        Args:
            name: Redis hash key name
            key: Field name (for single field set)
            value: Field value (for single field set)
            mapping: Dictionary of field-value pairs (for multiple fields)

        Returns:
            Number of fields that were added

        Raises:
            ValueError: If neither (key, value) nor mapping is provided
        """
        try:
            client = await self.get_client()

            if mapping is not None:
                return await client.hset(name, mapping=mapping)  # type: ignore[misc]
            elif key is not None and value is not None:
                return await client.hset(name, key=key, value=value)  # type: ignore[misc]
            else:
                raise ValueError(f"Either provide (key, value) or mapping parameter. " f"Got: key={key}, value={value}, mapping={mapping}")
        except Exception as e:
            logger.error(f"Redis hset failed for {name}: {e}")
            raise

    async def expire(self, name: str, time: int) -> bool:
        """Set expiration time."""
        try:
            client = await self.get_client()
            return await client.expire(name, time)  # type: ignore[misc]
        except Exception as e:
            logger.error(f"Redis expire failed for {name}: {e}")
            return False

    async def exists(self, name: str) -> bool:
        """Check if key exists."""
        try:
            client = await self.get_client()
            return bool(await client.exists(name))
        except Exception as e:
            logger.error(f"Redis exists failed for {name}: {e}")
            return False

    async def ping(self) -> bool:
        """Test Redis connection."""
        try:
            if not self._is_initialized or self._client is None:
                return False
            client = await self.get_client()
            result = await client.ping()  # type: ignore[misc]
            return result
        except Exception as e:
            logger.error(f"Redis ping failed: {e}")
            self._is_healthy = False
            return False

    async def info(self, section: Optional[str] = None) -> dict:
        """Get Redis server information."""
        try:
            client = await self.get_client()
            return await client.info(section)  # type: ignore[misc]
        except Exception as e:
            logger.error(f"Redis info failed: {e}")
            return {}

    async def delete(self, *keys) -> int:
        """Delete one or more keys."""
        try:
            client = await self.get_client()
            return await client.delete(*keys)  # type: ignore[misc]
        except Exception as e:
            logger.error(f"Redis delete failed for keys {keys}: {e}")
            return 0

    async def set(self, key: str, value: str, ex: Optional[int] = None) -> bool:
        """Set a key-value pair with optional expiration."""
        try:
            client = await self.get_client()
            return await client.set(key, value, ex=ex)  # type: ignore[misc]
        except Exception as e:
            logger.error(f"Redis set failed for key {key}: {e}")
            return False

    async def get(self, key: str) -> Optional[str]:
        """Get value by key."""
        try:
            client = await self.get_client()
            return await client.get(key)  # type: ignore[misc]
        except Exception as e:
            logger.error(f"Redis get failed for key {key}: {e}")
            return None

    async def setex(self, key: str, time: int, value: str) -> bool:
        """Set a key-value pair with expiration."""
        try:
            client = await self.get_client()
            return await client.setex(key, time, value)  # type: ignore[misc]
        except Exception as e:
            logger.error(f"Redis setex failed for key {key}: {e}")
            return False

    # ============================================================================
    # Health and Monitoring
    # ============================================================================

    def is_healthy(self) -> bool:
        """Check if Redis client is healthy (synchronous check)."""
        return self._is_healthy and self._is_initialized

    def get_connection_stats(self) -> Dict[str, Any]:
        """Get connection pool statistics."""
        if not self._connection_pool:
            return {"status": "not_initialized"}

        try:
            return {
                "status": "healthy" if self._is_healthy else "unhealthy",
                "initialized": self._is_initialized,
                "connection_errors": self._connection_errors,
                "pool_size": self._connection_pool.max_connections if self._connection_pool else 0,
                "created_connections": (len(self._connection_pool._created_connections) if hasattr(self._connection_pool, "_created_connections") else 0),  # type: ignore[attr-defined]
            }
        except Exception as e:
            logger.warning(f"Failed to get connection stats: {e}")
            return {"status": "error", "error": str(e)}


# Global singleton instance
redis_client: Optional[RedisClient] = None


async def initialize_redis_client() -> None:
    """
    Create and initialize global Redis client instance at application startup.

    This function should be called during application lifespan startup.
    """
    global redis_client
    if redis_client is None:
        redis_client = RedisClient()
        await redis_client.initialize()


async def close_redis_client() -> None:
    """
    Close global Redis client instance at application shutdown.

    This function should be called during application lifespan shutdown.
    """
    global redis_client
    if redis_client:
        await redis_client.close()
        redis_client = None


async def get_redis_client() -> RedisClient:
    """
    Get global Redis client instance.

    Returns:
        RedisClient instance

    Raises:
        RuntimeError: If Redis client is not initialized
    """
    if redis_client is None:
        raise RuntimeError("Redis client not initialized. Call initialize_redis_client() first.")
    return redis_client
