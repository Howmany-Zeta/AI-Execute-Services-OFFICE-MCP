"""
Throttling Middleware for FastMCP

Integrates RequestThrottler with FastMCP HTTP requests to provide
rate limiting and concurrency control.
"""

import logging
from typing import Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse, Response

from aiecs.mcp.concurrency import get_throttler

logger = logging.getLogger(__name__)


class ThrottlingMiddleware(BaseHTTPMiddleware):
    """
    Middleware that applies request throttling to FastMCP requests.
    
    Integrates RequestThrottler with FastMCP's request handling lifecycle,
    ensuring rate limiting and concurrency control apply before tool execution.
    """
    
    async def dispatch(self, request: Request, call_next: Callable) -> Response:
        """
        Process request with throttling.
        
        Args:
            request: Starlette request
            call_next: Next middleware/handler
        
        Returns:
            Response with throttling applied
        """
        # Get throttler instance
        throttler = get_throttler()
        
        # If throttler is not initialized, skip throttling
        if throttler is None:
            logger.debug("Throttler not initialized, skipping throttling")
            return await call_next(request)
        
        # Try to acquire throttling permission
        acquired = await throttler.acquire()
        
        if not acquired:
            # Request throttled - return 429 Too Many Requests
            logger.warning(f"Request throttled: {request.method} {request.url.path}")
            return JSONResponse(
                content={
                    "jsonrpc": "2.0",
                    "id": None,
                    "error": {
                        "code": -32000,
                        "message": "Request throttled. Please retry later.",
                    },
                },
                status_code=429,  # Too Many Requests
            )
        
        try:
            # Process request
            response = await call_next(request)
            return response
        finally:
            # Always release throttler resources
            throttler.release()
