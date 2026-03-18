"""
Unified Configuration Module for MCP Server

Provides centralized configuration management using Pydantic Settings.
Configuration can be loaded from environment variables or .env files.

This module combines functionality from the old config.py and tool_config.py,
but simplified for MCP server needs (no database, no LLM, no Celery, etc.).
"""

import logging
from pathlib import Path
from typing import Any, Dict, Optional
from functools import lru_cache
from dotenv import load_dotenv
from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)


# ============================================================================
# Environment Variable Loading
# ============================================================================


def load_env_files(env_files: Optional[list] = None) -> None:
    """
    Load environment variables from .env files.

    Args:
        env_files: List of .env file names to load. If None, uses default order:
            [".env", ".env.local", ".env.mcp"]

    This function ensures .env files are loaded before Pydantic Settings
    reads environment variables, allowing BaseSettings to pick them up.
    """
    if env_files is None:
        env_files = [".env", ".env.local", ".env.mcp"]

    for env_file in env_files:
        env_path = Path(env_file)
        if env_path.exists():
            try:
                load_dotenv(env_path, override=False)  # Don't override already loaded vars
                logger.debug(f"Loaded environment variables from {env_path}")
            except Exception as e:
                logger.warning(f"Failed to load {env_path}: {e}")


# ============================================================================
# MCP Server Configuration
# ============================================================================


class MCPServerConfig(BaseSettings):
    """
    MCP Server configuration using Pydantic Settings.

    Configuration is loaded from environment variables with MCP_ prefix.
    Example: MCP_HOST, MCP_PORT, MCP_LOG_LEVEL

    Attributes:
        host: Server host address (default: 0.0.0.0)
        port: Server port (default: 5040)
        log_level: Logging level (default: info)
        reload: Enable auto-reload for development (default: False)
        cors_origins: Comma-separated list of allowed origins, or "*" for all
        max_request_size: Maximum request size in bytes (default: 10MB)
    """

    model_config = SettingsConfigDict(env_prefix="MCP_", case_sensitive=False, extra="ignore")

    host: str = "0.0.0.0"
    port: int = 5040
    log_level: str = "info"
    reload: bool = False

    # Optional: Additional server configuration
    workers: Optional[int] = None
    timeout_keep_alive: int = 5
    timeout_graceful_shutdown: int = 30

    # Security configuration
    cors_origins: str = "*"  # Comma-separated list of allowed origins, or "*" for all
    max_request_size: int = 10 * 1024 * 1024  # 10MB default


class DocumentServerConfig(BaseSettings):
    """
    DocumentServer (ONLYOFFICE) configuration.

    Reads from DOCUMENTSERVER_* environment variables.
    """

    model_config = SettingsConfigDict(env_prefix="DOCUMENTSERVER_", case_sensitive=False, extra="ignore")

    url: str = Field(default="http://localhost:8000", description="DocumentServer base URL")
    jwt_secret: str = Field(default="", description="JWT secret for API authentication")
    jwt_in_body: bool = Field(default=True, description="Send JWT in body for Conversion/Command API")


@lru_cache()
def get_documentserver_config() -> DocumentServerConfig:
    """Get DocumentServer configuration."""
    load_env_files()
    return DocumentServerConfig()


@lru_cache()
def get_server_config() -> MCPServerConfig:
    """
    Get MCP server configuration instance.

    Loads .env files first, then creates config from environment variables.

    Returns:
        MCPServerConfig: Configuration instance loaded from environment variables
    """
    # Load .env files before creating config
    load_env_files()
    return MCPServerConfig()


# ============================================================================
# Tool Configuration Loader (Simplified - Only for .env loading)
# ============================================================================


class ToolConfigLoader:
    """
    Simplified tool configuration loader for MCP server.

    Only provides .env file loading functionality.
    YAML config loading removed (not needed for MCP server).

    This is kept for backward compatibility with providers that may use it
    to ensure .env files are loaded.
    """

    _instance: Optional["ToolConfigLoader"] = None
    _initialized: bool = False

    def __new__(cls):
        """Ensure singleton instance"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self) -> None:
        """Initialize the configuration loader"""
        if self._initialized:
            return
        self._initialized = True
        logger.debug("ToolConfigLoader initialized")

    def load_env_config(self) -> Dict[str, Any]:
        """
        Load sensitive configuration from .env files via dotenv.

        Supports multiple .env files in order:
        1. .env (base)
        2. .env.local (local overrides)
        3. .env.mcp (MCP-specific)

        Returns:
            Empty dictionary (dotenv modifies os.environ directly)
        """
        load_env_files()
        return {}


# Global singleton instance
_tool_config_loader = ToolConfigLoader()


def get_tool_config_loader() -> ToolConfigLoader:
    """
    Get the global tool configuration loader instance.

    Returns:
        ToolConfigLoader: Global singleton instance
    """
    return _tool_config_loader


# ============================================================================
# Settings (Legacy - Kept for backward compatibility, but minimal)
# ============================================================================


class Settings(BaseSettings):
    """
    Legacy Settings class - kept for backward compatibility.

    Most fields removed - MCP server doesn't need database, LLM, Celery, etc.
    Only minimal fields kept for any code that might still reference it.
    """

    model_config = SettingsConfigDict(case_sensitive=False, extra="ignore")

    # CORS Configuration (minimal)
    cors_allowed_origins: str = Field(
        default="*",
        alias="CORS_ALLOWED_ORIGINS",
    )

    # Development/Server Configuration
    reload: bool = Field(default=False, alias="RELOAD")
    port: int = Field(default=8000, alias="PORT")


@lru_cache()
def get_settings() -> Settings:
    """
    Get legacy settings instance (for backward compatibility).

    Returns:
        Settings: Minimal settings instance
    """
    load_env_files()
    return Settings()


def validate_required_settings() -> bool:
    """
    Validate that required settings are present.

    For MCP server, no settings are strictly required (all have defaults).

    Returns:
        True (always passes for MCP server)
    """
    return True
