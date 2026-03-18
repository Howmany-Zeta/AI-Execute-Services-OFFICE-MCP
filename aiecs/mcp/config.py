"""
MCP Server Configuration

Re-exports MCPServerConfig from unified config module with concurrency extensions.
"""

# Import from unified config module
from aiecs.config import MCPServerConfig as BaseMCPServerConfig
from pydantic import Field
from typing import Optional
from functools import lru_cache


class MCPServerConfig(BaseMCPServerConfig):
    """Extended MCP server config with concurrency settings."""

    # Concurrency and rate limiting
    max_requests_per_second: float = Field(
        default=100.0,
        alias="MCP_MAX_REQUESTS_PER_SECOND",
        description="Maximum requests per second (rate limiting)",
    )
    max_concurrent_requests: int = Field(
        default=100,
        alias="MCP_MAX_CONCURRENT_REQUESTS",
        description="Maximum concurrent requests (concurrency limiting)",
    )
    request_burst_size: Optional[int] = Field(
        default=None,
        alias="MCP_REQUEST_BURST_SIZE",
        description="Maximum burst size for rate limiter (defaults to 2x requests_per_second)",
    )
    
    # OpenAI format endpoint
    enable_openai_format: bool = Field(
        default=False,
        alias="MCP_ENABLE_OPENAI_FORMAT",
        description="Enable OpenAI function calling format endpoint at /openai/v1/tools",
    )


@lru_cache()
def get_server_config() -> MCPServerConfig:
    """Get extended MCP server configuration."""
    from aiecs.config import load_env_files

    # Load .env files before creating config
    load_env_files()
    return MCPServerConfig()


__all__ = ["MCPServerConfig", "get_server_config"]
