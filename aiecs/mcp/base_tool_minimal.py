"""
Minimal Base Tool for MCP Server

Provides only the executor initialization functionality needed for tool_executor
decorators to work, without the AIECS framework dependencies (config loading,
tool registration, etc.).

The executor configuration can be provided via:
1. Explicit executor_config parameter
2. Environment variables with TOOL_EXECUTOR_ prefix (via ExecutorConfig)
3. Default ExecutorConfig values
"""

import logging
from typing import Any, Dict, Optional

from aiecs.tools.tool_executor import get_executor

logger = logging.getLogger(__name__)


class MinimalBaseTool:
    """
    Minimal base class that only provides executor initialization.

    This class is designed to work with tool_executor decorators (@cache_result,
    @measure_execution_time, etc.) without requiring the full AIECS framework
    infrastructure (config loading, tool registry, etc.).

    Usage:
        class MyTool(MinimalBaseTool):
            def __init__(self, executor_config: Optional[Dict[str, Any]] = None):
                super().__init__(executor_config)
                # Initialize your tool here

            @cache_result(ttl=300)
            @measure_execution_time
            def my_operation(self, param: str):
                # Implementation
                pass
    """

    def __init__(self, executor_config: Optional[Dict[str, Any]] = None):
        """
        Initialize the minimal base tool with executor configuration.

        Args:
            executor_config (Dict[str, Any], optional): Configuration for the
                tool executor. If None, uses default executor configuration.
                Configuration can be provided via environment variables with
                TOOL_EXECUTOR_ prefix (e.g., TOOL_EXECUTOR_CACHE_SIZE).

        Configuration priority:
        1. Explicit executor_config parameter (highest priority)
        2. Environment variables with TOOL_EXECUTOR_ prefix
        3. Default ExecutorConfig values (lowest priority)

        Example executor_config:
            {
                "enable_cache": True,
                "cache_size": 200,
                "cache_ttl": 7200,
                "max_workers": 8,
                "timeout": 60
            }
        """
        # If executor_config is None, ExecutorConfig will automatically
        # read from environment variables with TOOL_EXECUTOR_ prefix
        # This allows configuration via environment variables without
        # explicitly passing a config dict
        self._executor = get_executor(executor_config)
        logger.debug(f"Initialized MinimalBaseTool with executor: {type(self._executor).__name__}")
