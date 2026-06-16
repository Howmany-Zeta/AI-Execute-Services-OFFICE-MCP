"""
MCP Server Entry Point

Standalone FastAPI application for Model Context Protocol (MCP) server.
Exposes office document tools as MCP tools via JSON-RPC 2.0 over HTTP.

This implementation uses FastMCP SDK for MCP protocol handling.
"""

import logging
import sys
from pathlib import Path
from contextlib import asynccontextmanager
from typing import Dict, Any, Optional

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, Response

try:
    from fastmcp import FastMCP
    FASTMCP_AVAILABLE = True
except ImportError:
    FASTMCP_AVAILABLE = False
    FastMCP = None

from aiecs.mcp.office_tool_adapter import OfficeToolAdapter
from aiecs.mcp.config import get_server_config
from aiecs.mcp.concurrency import initialize_throttler, get_throttler
from aiecs.mcp.fastmcp_integration import create_fastmcp_server

# Setup logging
# Try to use log file if logs directory exists, otherwise use stdout
log_dir = Path("/app/logs")
log_file = None
try:
    if log_dir.exists():
        log_dir.mkdir(parents=True, exist_ok=True)
        log_file = log_dir / "mcp-server.log"
        handlers = [
            logging.FileHandler(log_file, encoding='utf-8'),
            logging.StreamHandler(sys.stdout)  # Also output to stdout for docker logs
        ]
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=handlers
        )
        logger = logging.getLogger(__name__)
        logger.info(f"Logging to file: {log_file}")
    else:
        # Fallback to stdout only if logs directory doesn't exist
        handlers = [logging.StreamHandler(sys.stdout)]
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=handlers
        )
        logger = logging.getLogger(__name__)
except Exception as e:
    # Fallback to stdout if file logging fails
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)]
    )
    logger = logging.getLogger(__name__)
    logger.warning(f"Failed to setup file logging: {e}, using stdout only")

# Global instances (initialized at module load)
tool_adapter: Optional[OfficeToolAdapter] = None
fastmcp_server: Optional[FastMCP] = None
mcp_app = None  # FastMCP ASGI app


def create_app_lifespan(mcp_app_lifespan):
    """
    Create FastAPI lifespan that combines app initialization with FastMCP lifespan.
    
    Args:
        mcp_app_lifespan: FastMCP app lifespan context manager
    
    Returns:
        Combined lifespan context manager
    """
    @asynccontextmanager
    async def app_lifespan(app: FastAPI):
        """
        Combined lifespan manager for FastAPI and FastMCP.
        
        Initializes Redis client and request throttler on startup.
        Cleans up resources on shutdown.
        """
        global tool_adapter

        # Startup - enter FastMCP lifespan first, then app initialization
        async with mcp_app_lifespan(app):
            logger.info("Starting Office MCP server with FastMCP...")

            try:
                # Initialize Redis client (required for production caching)
                try:
                    from aiecs.infrastructure.persistence import initialize_redis_client, close_redis_client

                    await initialize_redis_client()
                    logger.info("Redis client initialized successfully for caching")
                except Exception as e:
                    logger.error(f"Redis client initialization failed: {e}")
                    logger.warning("Server will continue with LRU cache only (degraded performance)")

                # tool_adapter is initialized at module load (see below)

                # Initialize request throttler for high concurrency handling
                # Note: FastMCP middleware integration will be handled separately
                server_config = get_server_config()
                initialize_throttler(
                    requests_per_second=server_config.max_requests_per_second,
                    max_concurrent=server_config.max_concurrent_requests,
                    burst_size=server_config.request_burst_size,
                )
                logger.info("Initialized request throttler")

                logger.info("MCP server started successfully")

                yield

            except Exception as e:
                logger.error(f"Failed to initialize MCP server: {e}", exc_info=True)
                raise

            # Shutdown
            logger.info("Shutting down MCP server...")
            try:
                from aiecs.infrastructure.persistence import close_redis_client

                await close_redis_client()
                logger.info("Redis client closed")
            except Exception as e:
                logger.warning(f"Error closing Redis client: {e}")
            logger.info("MCP server shutdown complete")
    
    return app_lifespan


# Initialize FastMCP server and app BEFORE creating FastAPI app
# This is required because FastAPI needs mcp_app.lifespan
if not FASTMCP_AVAILABLE:
    raise ImportError("FastMCP is not available. Install with: pip install 'fastmcp>=3.0.0b1'")

logger.info("Initializing FastMCP server...")

# Initialize office tool adapter (six office tools)
tool_adapter = OfficeToolAdapter()
logger.info("Initialized OfficeToolAdapter (six office tools)")

# Create FastMCP server
fastmcp_server = create_fastmcp_server(
    tool_adapter=tool_adapter,
    name="Office MCP Server",
)

if fastmcp_server is None:
    raise RuntimeError("Failed to create FastMCP server")

logger.info("Initialized FastMCP server")

# Create FastMCP ASGI app with throttling middleware
# Use path="/" since we'll mount it at /mcp/v1 in FastAPI
# Enable stateless mode for backward compatibility with existing clients
from starlette.middleware import Middleware
from aiecs.mcp.throttling_middleware import ThrottlingMiddleware

# Add throttling middleware to FastMCP app
# This ensures throttling applies before tool execution
mcp_app = fastmcp_server.http_app(
    path="/",
    stateless_http=True,
    middleware=[Middleware(ThrottlingMiddleware)],
)
logger.info("Created FastMCP ASGI app (stateless mode with throttling middleware)")

# Create FastAPI app with FastMCP lifespan
app = FastAPI(
    title="Office MCP Server",
    description="Model Context Protocol server for office document tools",
    version="1.0.0",
    lifespan=create_app_lifespan(mcp_app.lifespan),
)

# Mount FastMCP app to FastAPI at /mcp/v1 for backward compatibility
app.mount("/mcp/v1", mcp_app)
logger.info("Mounted FastMCP app to FastAPI at /mcp/v1")

# Configure CORS - allow all origins for MCP compatibility
# Note: In production, consider restricting origins for better security
cors_origins = get_server_config().cors_origins
if cors_origins == "*":
    # Allow all origins (default for MCP compatibility)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["POST", "GET", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "mcp-protocol-version", "mcp-session-id"],
    )
else:
    # Use configured origins
    origins_list = [origin.strip() for origin in cors_origins.split(",")]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins_list,
        allow_credentials=True,
        allow_methods=["POST", "GET", "OPTIONS"],
        allow_headers=["Content-Type", "Authorization", "mcp-protocol-version", "mcp-session-id"],
    )


# FastMCP app will be mounted in lifespan after creation


@app.get("/openai/v1/tools")
async def openai_tools_endpoint() -> Dict[str, Any]:
    """
    OpenAI function calling format tools endpoint.
    
    Returns all available tools in OpenAI function calling format.
    This endpoint is only available if MCP_ENABLE_OPENAI_FORMAT=true.
    
    Returns:
        JSON array of tools in OpenAI function calling format:
        [
            {
                "type": "function",
                "function": {
                    "name": "tool_name",
                    "description": "Tool description",
                    "parameters": {...}
                }
            },
            ...
        ]
    
    Raises:
        404: If OpenAI format endpoint is disabled
    """
    server_config = get_server_config()
    
    if not server_config.enable_openai_format:
        from fastapi import HTTPException
        raise HTTPException(status_code=404, detail="OpenAI format endpoint is disabled. Set MCP_ENABLE_OPENAI_FORMAT=true to enable.")
    
    if tool_adapter is None:
        from fastapi import HTTPException
        raise HTTPException(status_code=503, detail="Tool adapter not initialized")
    
    try:
        # Get tools in OpenAI format
        openai_tools = tool_adapter.list_tools_openai_format()
        
        return {"tools": openai_tools}
    except Exception as e:
        logger.error(f"Error retrieving OpenAI format tools: {e}", exc_info=True)
        from fastapi import HTTPException
        raise HTTPException(status_code=500, detail="Failed to retrieve tools")


@app.get("/docbuilder-scripts/{script_id}", response_class=PlainTextResponse)
async def get_docbuilder_script(script_id: str) -> str:
    """
    Serve .docbuilder script by id (for Document Server url parameter).

    When MCP_PUBLIC_URL is set, script_to_url stores scripts here.
    Document Server fetches the script via this URL.
    """
    from aiecs.tools.office_tool.docbuilder_script import get_script

    content = get_script(script_id)
    if content is None:
        raise HTTPException(status_code=404, detail="Script not found")
    return content


@app.api_route("/storage-objects/{token}", methods=["GET", "HEAD"])
async def get_storage_object(token: str, request: Request) -> Response:
    """
    Stream object storage file for DocumentServer fetch.

    Registered by resolve_fetch_url for s3:// (and gs:// via proxy) when
    MCP_PUBLIC_URL is configured. Supports HEAD for ONLYOFFICE download probes.
    """
    from aiecs.tools.office_tool.object_fetch import fetch_object_bytes

    fetched = await fetch_object_bytes(token)
    if fetched is None:
        raise HTTPException(status_code=404, detail="Object not found or expired")
    content, content_type = fetched
    headers = {"Content-Length": str(len(content))}
    body = b"" if request.method == "HEAD" else content
    return Response(content=body, media_type=content_type, headers=headers)


@app.get("/health/live")
async def health_live() -> Dict[str, Any]:
    """Liveness: HTTP process up only; no DocumentServer, Redis, or tool wiring I/O."""
    return {
        "status": "alive",
        "version": "1.0.0",
        "probe": "liveness",
        "server_type": "office_mcp",
    }


async def _readiness_health() -> Dict[str, Any]:
    """
    Readiness-style check: tool list, DocumentServer reachability, optional Redis/throttler.
    Suitable for orchestration "is the service useful" probes (not Docker liveness).
    """
    try:
        if tool_adapter is None:
            return {
                "status": "unhealthy",
                "version": "1.0.0",
                "server_type": "office_mcp",
                "probe": "readiness",
                "error": "Tool adapter not initialized",
            }

        tools = tool_adapter.list_tools()
        tool_names = [t.get("name", "") for t in tools if t.get("name")]

        result = {
            "status": "healthy",
            "version": "1.0.0",
            "server_type": "office_mcp",
            "probe": "readiness",
            "tools": tool_names,
            "tool_count": len(tool_names),
        }

        try:
            from aiecs.clients.documentserver_client import get_documentserver_client

            ds_client = get_documentserver_client()
            result["documentserver_reachable"] = await ds_client.healthcheck()
        except Exception:
            result["documentserver_reachable"] = False

        throttler = get_throttler()
        if throttler:
            result["throttler"] = throttler.get_stats()

        try:
            from aiecs.infrastructure.persistence import get_redis_client

            redis_client = await get_redis_client()
            result["redis"] = redis_client.get_connection_stats()
        except Exception:
            pass

        return result

    except Exception as e:
        logger.error(f"Error in readiness health check: {e}", exc_info=True)
        return {
            "status": "unhealthy",
            "version": "1.0.0",
            "server_type": "office_mcp",
            "probe": "readiness",
            "error": str(e),
        }


@app.get("/health")
async def health_check() -> Dict[str, Any]:
    """
    Readiness / deep health: tools, Document Server, optional Redis and throttler.

    For cheap container liveness use ``GET /health/live`` instead.
    """
    return await _readiness_health()


@app.get("/health/probe")
async def health_probe() -> Dict[str, Any]:
    """Same body as ``GET /health`` (alias for parity with other MCP services)."""
    return await _readiness_health()


if __name__ == "__main__":
    import uvicorn

    # Get configuration from Pydantic Settings
    config = get_server_config()

    logger.info(f"Starting MCP server on {config.host}:{config.port}")

    uvicorn.run(
        "aiecs.main_mcp:app",
        host=config.host,
        port=config.port,
        log_level=config.log_level,
        reload=config.reload,
    )
