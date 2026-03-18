"""Infrastructure layer module

Contains external system integrations and technical concerns.
"""

# Only import modules that exist - messaging and monitoring modules are optional
# and may not be available in all deployment contexts (e.g., MCP server)

# Persistence - always available
from .persistence.redis_client import RedisClient

# Optional imports with graceful fallback
try:
    from .persistence.database_manager import DatabaseManager
except ImportError:
    DatabaseManager = None  # type: ignore

try:
    from .messaging.celery_task_manager import CeleryTaskManager
    from .messaging.websocket_manager import WebSocketManager, UserConfirmation
except ImportError:
    # Messaging modules not available (e.g., in MCP server deployment)
    CeleryTaskManager = None  # type: ignore
    WebSocketManager = None  # type: ignore
    UserConfirmation = None  # type: ignore

try:
    from .monitoring.executor_metrics import ExecutorMetrics
    from .monitoring.tracing_manager import TracingManager
except ImportError:
    # Monitoring modules not available
    ExecutorMetrics = None  # type: ignore
    TracingManager = None  # type: ignore

__all__ = [
    # Persistence (always available)
    "RedisClient",
    # Optional components (may be None if modules not available)
    "DatabaseManager",
    "CeleryTaskManager",
    "WebSocketManager",
    "UserConfirmation",
    "ExecutorMetrics",
    "TracingManager",
]
