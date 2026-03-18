"""
Concurrency control and rate limiting for MCP server.

Provides:
- Request rate limiting (token bucket algorithm)
- Concurrent request limiting (semaphore-based)
- Request queuing for overload protection
"""

import asyncio
import logging
import time
from typing import Optional, Dict
from threading import Lock

logger = logging.getLogger(__name__)


class RateLimiter:
    """
    Token bucket rate limiter for request rate limiting.

    Uses token bucket algorithm to limit requests per time window.
    """

    def __init__(self, requests_per_second: float = 100.0, burst_size: Optional[int] = None):
        """
        Initialize rate limiter.

        Args:
            requests_per_second: Maximum requests per second
            burst_size: Maximum burst size (defaults to requests_per_second * 2)
        """
        self.requests_per_second = requests_per_second
        self.burst_size = burst_size or int(requests_per_second * 2)
        self.tokens = float(self.burst_size)
        self.last_update = time.time()
        self._lock = Lock()

    def acquire(self, tokens: int = 1) -> bool:
        """
        Try to acquire tokens for a request.

        Args:
            tokens: Number of tokens to acquire (default: 1)

        Returns:
            True if tokens were acquired, False if rate limit exceeded
        """
        with self._lock:
            now = time.time()
            elapsed = now - self.last_update

            # Add tokens based on elapsed time
            self.tokens = min(self.burst_size, self.tokens + elapsed * self.requests_per_second)
            self.last_update = now

            # Check if we have enough tokens
            if self.tokens >= tokens:
                self.tokens -= tokens
                return True
            else:
                return False

    def wait_time(self, tokens: int = 1) -> float:
        """
        Calculate wait time needed to acquire tokens.

        Args:
            tokens: Number of tokens needed

        Returns:
            Wait time in seconds
        """
        with self._lock:
            now = time.time()
            elapsed = now - self.last_update

            # Calculate current tokens
            current_tokens = min(self.burst_size, self.tokens + elapsed * self.requests_per_second)

            if current_tokens >= tokens:
                return 0.0

            # Calculate time needed to accumulate tokens
            needed = tokens - current_tokens
            return needed / self.requests_per_second


class ConcurrencyLimiter:
    """
    Semaphore-based concurrency limiter.

    Limits the number of concurrent requests being processed.
    """

    def __init__(self, max_concurrent: int = 100):
        """
        Initialize concurrency limiter.

        Args:
            max_concurrent: Maximum concurrent requests
        """
        self.max_concurrent = max_concurrent
        self.semaphore = asyncio.Semaphore(max_concurrent)
        self.active_count = 0
        self.total_requests = 0
        self.rejected_requests = 0

    async def acquire(self) -> bool:
        """
        Try to acquire a slot for processing.

        Returns:
            True if acquired, False if limit exceeded
        """
        try:
            await asyncio.wait_for(self.semaphore.acquire(), timeout=0.1)
            self.active_count += 1
            self.total_requests += 1
            return True
        except asyncio.TimeoutError:
            self.rejected_requests += 1
            return False

    def release(self) -> None:
        """Release a slot."""
        self.active_count -= 1
        self.semaphore.release()

    async def __aenter__(self):
        """Async context manager entry."""
        acquired = await self.acquire()
        if not acquired:
            raise RuntimeError("Concurrency limit exceeded")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        self.release()

    def get_stats(self) -> Dict[str, int]:
        """Get concurrency statistics."""
        return {
            "max_concurrent": self.max_concurrent,
            "active_count": self.active_count,
            "total_requests": self.total_requests,
            "rejected_requests": self.rejected_requests,
        }


class RequestThrottler:
    """
    Combined rate limiter and concurrency limiter for request throttling.

    Provides both rate limiting and concurrency control.
    """

    def __init__(
        self,
        requests_per_second: float = 100.0,
        max_concurrent: int = 100,
        burst_size: Optional[int] = None,
    ):
        """
        Initialize request throttler.

        Args:
            requests_per_second: Maximum requests per second
            max_concurrent: Maximum concurrent requests
            burst_size: Maximum burst size for rate limiter
        """
        self.rate_limiter = RateLimiter(requests_per_second, burst_size)
        self.concurrency_limiter = ConcurrencyLimiter(max_concurrent)

    async def acquire(self) -> bool:
        """
        Try to acquire permission to process a request.

        Returns:
            True if acquired, False if throttled
        """
        # Check rate limit first (fast check)
        if not self.rate_limiter.acquire():
            return False

        # Check concurrency limit
        return await self.concurrency_limiter.acquire()

    def release(self) -> None:
        """Release resources after request processing."""
        self.concurrency_limiter.release()

    async def __aenter__(self):
        """Async context manager entry."""
        acquired = await self.acquire()
        if not acquired:
            raise RuntimeError("Request throttled")
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit."""
        self.release()

    def get_stats(self) -> Dict[str, any]:
        """Get throttling statistics."""
        return {
            "rate_limiter": {
                "requests_per_second": self.rate_limiter.requests_per_second,
                "burst_size": self.rate_limiter.burst_size,
                "current_tokens": self.rate_limiter.tokens,
            },
            "concurrency_limiter": self.concurrency_limiter.get_stats(),
        }


# Global throttler instance (initialized from config)
_throttler: Optional[RequestThrottler] = None


def initialize_throttler(
    requests_per_second: float = 100.0,
    max_concurrent: int = 100,
    burst_size: Optional[int] = None,
) -> None:
    """
    Initialize global request throttler.

    Args:
        requests_per_second: Maximum requests per second
        max_concurrent: Maximum concurrent requests
        burst_size: Maximum burst size
    """
    global _throttler
    _throttler = RequestThrottler(requests_per_second, max_concurrent, burst_size)
    logger.info(f"Request throttler initialized: {requests_per_second} req/s, " f"max_concurrent={max_concurrent}, burst_size={burst_size or int(requests_per_second * 2)}")


def get_throttler() -> Optional[RequestThrottler]:
    """Get global request throttler instance."""
    return _throttler
