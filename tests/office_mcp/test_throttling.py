"""
Tests for throttling integration with FastMCP.
"""

import pytest
import asyncio
import httpx
from unittest.mock import Mock, patch, AsyncMock

# Throttling tests don't require FastMCP - they test the throttling middleware itself

from aiecs.mcp.throttling_middleware import ThrottlingMiddleware
from aiecs.mcp.concurrency import RequestThrottler, initialize_throttler, get_throttler


@pytest.fixture
def throttler():
    """Create a throttler for testing."""
    return RequestThrottler(
        requests_per_second=10.0,
        max_concurrent=2,
        burst_size=5
    )


@pytest.fixture(autouse=True)
def reset_throttler():
    """Reset global throttler before each test."""
    from aiecs.mcp.concurrency import _throttler
    global _throttler
    _throttler = None
    yield
    _throttler = None


@pytest.mark.asyncio
async def test_throttler_rate_limiting(throttler):
    """Test rate limiting functionality."""
    # Acquire multiple requests quickly
    results = []
    for i in range(5):
        acquired = await throttler.acquire()
        results.append(acquired)
    
    # First few should succeed (within burst size of 5)
    # Rate limiter allows burst_size tokens initially
    assert sum(results) >= 2  # At least some should succeed (burst allows initial requests)
    
    # Release all
    for _ in range(sum(results)):
        throttler.release()


@pytest.mark.asyncio
async def test_throttler_concurrency_limiting(throttler):
    """Test concurrency limiting functionality."""
    # Acquire up to max_concurrent
    acquired = []
    for i in range(3):  # max_concurrent is 2
        result = await throttler.acquire()
        acquired.append(result)
    
    # Only max_concurrent should succeed
    assert sum(acquired) == 2
    
    # Release all
    for _ in range(sum(acquired)):
        throttler.release()


@pytest.mark.asyncio
async def test_throttler_release():
    """Test throttler release after request completion."""
    throttler = RequestThrottler(
        requests_per_second=100.0,
        max_concurrent=1,
    )
    
    # Acquire one request
    acquired = await throttler.acquire()
    assert acquired is True
    
    # Check active count
    assert throttler.concurrency_limiter.active_count == 1
    
    # Release
    throttler.release()
    
    # Check active count is back to 0
    assert throttler.concurrency_limiter.active_count == 0


@pytest.mark.asyncio
async def test_throttling_middleware_without_throttler():
    """Test middleware when throttler is not initialized."""
    middleware = ThrottlingMiddleware(Mock())
    request = Mock()
    request.method = "POST"
    request.url.path = "/mcp/v1/"
    
    call_next = AsyncMock(return_value=Mock(status_code=200))
    
    # Should pass through when throttler is None
    response = await middleware.dispatch(request, call_next)
    
    assert response.status_code == 200
    call_next.assert_called_once()


@pytest.mark.asyncio
async def test_throttling_middleware_with_throttler():
    """Test middleware with throttler initialized."""
    initialize_throttler(
        requests_per_second=100.0,
        max_concurrent=1,
    )
    
    middleware = ThrottlingMiddleware(Mock())
    request = Mock()
    request.method = "POST"
    request.url.path = "/mcp/v1/"
    
    call_next = AsyncMock(return_value=Mock(status_code=200))
    
    # First request should succeed
    response = await middleware.dispatch(request, call_next)
    assert response.status_code == 200
    
    # Second request should also succeed (within limits)
    response = await middleware.dispatch(request, call_next)
    assert response.status_code == 200
    
    # Cleanup
    throttler = get_throttler()
    if throttler:
        throttler.release()
        throttler.release()
