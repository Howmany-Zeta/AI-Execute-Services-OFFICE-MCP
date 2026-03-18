"""
Utils module for the Python middleware application.

This module provides utility functions including:
- Execution utilities
- Cache provider interfaces and implementations
"""

from .execution_utils import ExecutionUtils
from .cache_provider import (
    ICacheProvider,
    LRUCacheProvider,
    DualLayerCacheProvider,
    RedisCacheProvider,
)

__all__ = [
    "ExecutionUtils",
    "ICacheProvider",
    "LRUCacheProvider",
    "DualLayerCacheProvider",
    "RedisCacheProvider",
]

# Version information
__version__ = "1.0.0"
__author__ = "Python Middleware Team"
__description__ = "Utility functions for the middleware application"
