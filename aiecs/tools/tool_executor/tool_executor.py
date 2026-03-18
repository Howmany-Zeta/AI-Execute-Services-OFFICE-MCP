import os
import asyncio
import functools
import inspect
import logging
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from typing import Any, Callable, Dict, List, Optional, Type, Union
from contextlib import contextmanager

from aiecs.utils.execution_utils import ExecutionUtils
from aiecs.utils.cache_provider import ICacheProvider, LRUCacheProvider
import re
from pydantic import BaseModel, ValidationError
from pydantic_settings import BaseSettings, SettingsConfigDict

logger = logging.getLogger(__name__)

# Base exception hierarchy


class ToolExecutionError(Exception):
    """Base exception for all tool execution errors."""


class InputValidationError(ToolExecutionError):
    """Error in validating input parameters."""


class SecurityError(ToolExecutionError):
    """Security-related error."""


class OperationError(ToolExecutionError):
    """Error during operation execution."""


class TimeoutError(ToolExecutionError):
    """Operation timed out."""


# Configuration for the executor


class ExecutorConfig(BaseSettings):
    """
    Configuration for the ToolExecutor.
    
    Automatically reads from environment variables with TOOL_EXECUTOR_ prefix.
    Example: TOOL_EXECUTOR_MAX_WORKERS -> max_workers

    Attributes:
        enable_cache (bool): Enable caching of operation results.
        cache_size (int): Maximum number of cache entries.
        cache_ttl (int): Cache time-to-live in seconds.
        max_workers (int): Maximum number of thread pool workers.
        io_concurrency (int): Maximum concurrent I/O operations.
        chunk_size (int): Chunk size for processing large data.
        max_file_size (int): Maximum file size in bytes.
        log_level (str): Logging level (e.g., 'INFO', 'DEBUG').
        log_execution_time (bool): Log execution time for operations.
        enable_security_checks (bool): Enable security checks for inputs.
        retry_attempts (int): Number of retry attempts for transient errors.
        retry_backoff (float): Backoff factor for retries.
        timeout (int): Timeout for operations in seconds.
        enable_dual_cache (bool): Enable dual-layer caching (L1: LRU + L2: Redis).
        enable_redis_cache (bool): Enable Redis as L2 cache (requires enable_dual_cache=True).
        redis_cache_ttl (int): Redis cache TTL in seconds (for L2 cache).
        l1_cache_ttl (int): L1 cache TTL in seconds (for dual-layer cache).
    """

    model_config = SettingsConfigDict(env_prefix="TOOL_EXECUTOR_")

    enable_cache: bool = True
    cache_size: int = 100
    cache_ttl: int = 3600
    max_workers: int = 4
    io_concurrency: int = 8
    chunk_size: int = 10000
    max_file_size: int = 1000000
    log_level: str = "INFO"
    log_execution_time: bool = True
    enable_security_checks: bool = True
    retry_attempts: int = 3
    retry_backoff: float = 1.0
    timeout: int = 30

    # Dual-layer cache configuration
    enable_dual_cache: bool = False
    enable_redis_cache: bool = False
    redis_cache_ttl: int = 86400  # 1 day
    l1_cache_ttl: int = 300  # 5 minutes


# Metrics counter


class ToolExecutorStats:
    """
    Tracks tool executor performance statistics.
    """

    def __init__(self) -> None:
        self.requests: int = 0
        self.failures: int = 0
        self.cache_hits: int = 0
        self.processing_times: List[float] = []

    def record_request(self, processing_time: float):
        self.requests += 1
        self.processing_times.append(processing_time)

    def record_failure(self):
        self.failures += 1

    def record_cache_hit(self):
        self.cache_hits += 1

    def to_dict(self) -> Dict[str, Any]:
        return {
            "requests": self.requests,
            "failures": self.failures,
            "cache_hits": self.cache_hits,
            "avg_processing_time": (sum(self.processing_times) / len(self.processing_times) if self.processing_times else 0.0),
        }


# Decorators for tool methods


def validate_input(schema_class: Type[BaseModel]) -> Callable:
    """
    Decorator to validate input using a Pydantic schema.

    Args:
        schema_class (Type[BaseModel]): Pydantic schema class for validation.

    Returns:
        Callable: Decorated function with validated inputs.

    Raises:
        InputValidationError: If input validation fails.
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            try:
                schema = schema_class(**kwargs)
                validated_kwargs = schema.model_dump(exclude_unset=True)
                return func(self, **validated_kwargs)
            except ValidationError as e:
                raise InputValidationError(f"Invalid input parameters: {e}")

        return wrapper

    return decorator


def cache_result(ttl: Optional[int] = None) -> Callable:
    """
    Decorator to cache function results with optional TTL.

    Args:
        ttl (Optional[int]): Time-to-live for cache entry in seconds.

    Returns:
        Callable: Decorated function with caching.
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            if not hasattr(self, "_executor") or not self._executor.config.enable_cache:
                return func(self, *args, **kwargs)
            cache_key = self._executor._get_cache_key(func.__name__, args, kwargs)
            result = self._executor._get_from_cache(cache_key)
            if result is not None:
                logger.debug(f"Cache hit for {func.__name__}")
                self._executor._metrics.record_cache_hit()
                return result
            result = func(self, *args, **kwargs)
            self._executor._add_to_cache(cache_key, result, ttl)
            return result

        return wrapper

    return decorator


def cache_result_with_strategy(
    ttl_strategy: Optional[Union[int, Callable]] = None,
) -> Callable:
    """
    Decorator to cache function results with flexible TTL strategy.

    Supports multiple TTL strategy types:
    1. Fixed TTL (int): Static TTL in seconds
    2. Callable strategy: Function that calculates TTL based on result and context
    3. None: Use default TTL from executor config

    Args:
        ttl_strategy: TTL strategy, can be:
            - int: Fixed TTL in seconds
            - Callable[[Any, tuple, dict], int]: Function(result, args, kwargs) -> ttl_seconds
            - None: Use default TTL

    Returns:
        Callable: Decorated function with intelligent caching.

    Example:
        # Fixed TTL
        @cache_result_with_strategy(ttl_strategy=3600)
        def simple_operation(self, data):
            return process(data)

        # Dynamic TTL based on result
        def calculate_ttl(result, args, kwargs):
            if result.get('type') == 'static':
                return 86400  # 1 day
            return 3600  # 1 hour

        @cache_result_with_strategy(ttl_strategy=calculate_ttl)
        def smart_operation(self, query):
            return search(query)
    """

    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(self, *args, **kwargs):
            if not hasattr(self, "_executor") or not self._executor.config.enable_cache:
                return func(self, *args, **kwargs)

            # Generate cache key
            cache_key = self._executor._get_cache_key(func.__name__, args, kwargs)

            # Check cache
            cached = self._executor._get_from_cache(cache_key)
            if cached is not None:
                logger.debug(f"Cache hit for {func.__name__}")
                self._executor._metrics.record_cache_hit()
                return cached

            # Execute function
            result = func(self, *args, **kwargs)

            # Calculate TTL based on strategy
            # Support both regular callables and lambdas that need self
            if callable(ttl_strategy):
                try:
                    # Try calling with self first (for lambda self, result,
                    # args, kwargs)
                    import inspect

                    sig = inspect.signature(ttl_strategy)
                    if len(sig.parameters) == 4:  # self, result, args, kwargs
                        ttl = ttl_strategy(self, result, args, kwargs)
                    else:  # result, args, kwargs
                        ttl = ttl_strategy(result, args, kwargs)

                    if not isinstance(ttl, int) or ttl < 0:
                        logger.warning(f"TTL strategy returned invalid value: {ttl}. " f"Expected positive integer. Using default TTL.")
                        ttl = None
                except Exception as e:
                    logger.error(f"Error calculating TTL from strategy: {e}. Using default TTL.")
                    ttl = None
            else:
                ttl = self._executor._calculate_ttl_from_strategy(ttl_strategy, result, args, kwargs)

            # Cache with calculated TTL
            self._executor._add_to_cache(cache_key, result, ttl)
            return result

        return wrapper

    return decorator


def run_in_executor(func: Callable) -> Callable:
    """
    Decorator to run a synchronous function in the thread pool executor.

    Args:
        func (Callable): Function to execute.

    Returns:
        Callable: Async wrapper for the function.
    """

    @functools.wraps(func)
    async def wrapper(self, *args, **kwargs):
        if not hasattr(self, "_executor"):
            return await func(self, *args, **kwargs)
        loop = asyncio.get_event_loop()
        return await loop.run_in_executor(
            self._executor._thread_pool,
            functools.partial(func, self, *args, **kwargs),
        )

    return wrapper


def measure_execution_time(func: Callable) -> Callable:
    """
    Decorator to measure and log execution time.

    Args:
        func (Callable): Function to measure.

    Returns:
        Callable: Decorated function with timing.
    """

    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        if not hasattr(self, "_executor") or not self._executor.config.log_execution_time:
            return func(self, *args, **kwargs)
        start_time = time.time()
        try:
            result = func(self, *args, **kwargs)
            execution_time = time.time() - start_time
            logger.info(f"{func.__name__} executed in {execution_time:.4f} seconds")
            return result
        except Exception as e:
            execution_time = time.time() - start_time
            logger.error(f"{func.__name__} failed after {execution_time:.4f} seconds: {e}")
            raise

    return wrapper


def sanitize_input(func: Callable) -> Callable:
    """
    Decorator to sanitize input parameters for security.

    Args:
        func (Callable): Function to sanitize inputs for.

    Returns:
        Callable: Decorated function with sanitized inputs.
    """

    @functools.wraps(func)
    def wrapper(self, *args, **kwargs):
        if not hasattr(self, "_executor") or not self._executor.config.enable_security_checks:
            return func(self, *args, **kwargs)
        sanitized_kwargs = {}
        for k, v in kwargs.items():
            if isinstance(v, str) and re.search(r"(\bSELECT\b|\bINSERT\b|--|;|/\*)", v, re.IGNORECASE):
                raise SecurityError(f"Input parameter '{k}' contains potentially malicious content")
            sanitized_kwargs[k] = v
        return func(self, *args, **sanitized_kwargs)

    return wrapper


class ToolExecutor:
    """
    Centralized executor for tool operations, handling:
    - Input validation
    - Caching with TTL and content-based keys
    - Concurrency with dynamic thread pool
    - Error handling with retries
    - Performance optimization with metrics
    - Structured logging

    Example:
        executor = ToolExecutor(config={'max_workers': 8})
        result = executor.execute(tool_instance, 'operation_name', param1='value')
    """

    def __init__(
        self,
        config: Optional[Dict[str, Any]] = None,
        cache_provider: Optional[ICacheProvider] = None,
    ):
        """
        Initialize the executor with optional configuration.

        Args:
            config (Dict[str, Any], optional): Configuration overrides for ExecutorConfig.
            cache_provider (ICacheProvider, optional): Custom cache provider. If None, uses default based on config.

        Raises:
            ValueError: If config is invalid.
        """
        self.config = ExecutorConfig(**(config or {}))
        logging.basicConfig(
            level=getattr(logging, self.config.log_level),
            format="%(asctime)s %(levelname)s %(name)s: %(message)s",
        )
        self._thread_pool = ThreadPoolExecutor(max_workers=max(os.cpu_count() or 4, self.config.max_workers))
        self._locks: Dict[str, threading.Lock] = {}
        self._metrics = ToolExecutorStats()
        self.execution_utils = ExecutionUtils(
            cache_size=self.config.cache_size,
            cache_ttl=self.config.cache_ttl,
            retry_attempts=self.config.retry_attempts,
            retry_backoff=self.config.retry_backoff,
        )

        # Support pluggable cache provider
        if cache_provider is not None:
            # User provided custom cache provider
            self.cache_provider = cache_provider
            logger.info(f"Using custom cache provider: {cache_provider.__class__.__name__}")
        elif self.config.enable_dual_cache and self.config.enable_redis_cache:
            # Enable dual-layer cache (L1: LRU + L2: Redis)
            self.cache_provider = self._initialize_dual_cache()
        else:
            # Default: use LRUCacheProvider wrapping ExecutionUtils
            self.cache_provider = LRUCacheProvider(self.execution_utils)
            logger.debug("Using default LRUCacheProvider")

    def _initialize_dual_cache(self) -> ICacheProvider:
        """
        Initialize dual-layer cache (L1: LRU + L2: Redis).

        Returns:
            DualLayerCacheProvider instance or fallback to LRUCacheProvider
        """
        try:
            from aiecs.utils.cache_provider import (
                DualLayerCacheProvider,
                RedisCacheProvider,
            )

            # Create L1 cache (LRU)
            l1_cache = LRUCacheProvider(self.execution_utils)

            # Create L2 cache (Redis) - this requires async initialization
            # We'll use a lazy initialization approach
            try:
                # Try to get global Redis client synchronously
                # Note: This assumes Redis client is already initialized
                from aiecs.infrastructure.persistence import redis_client

                if redis_client is not None:
                    l2_cache = RedisCacheProvider(
                        redis_client,
                        prefix="tool_executor:",
                        default_ttl=self.config.redis_cache_ttl,
                    )

                    dual_cache = DualLayerCacheProvider(
                        l1_provider=l1_cache,
                        l2_provider=l2_cache,
                        l1_ttl=self.config.l1_cache_ttl,
                    )

                    logger.info("Dual-layer cache enabled (L1: LRU + L2: Redis)")
                    return dual_cache
                else:
                    logger.warning("Redis client not initialized, falling back to LRU cache")
                    return l1_cache

            except ImportError:
                logger.warning("Redis client not available, falling back to LRU cache")
                return l1_cache

        except Exception as e:
            logger.warning(f"Failed to initialize dual-layer cache: {e}, falling back to LRU")
            return LRUCacheProvider(self.execution_utils)

    def _get_cache_key(self, func_name: str, args: tuple, kwargs: Dict[str, Any]) -> str:
        """
        Generate a context-aware cache key from function name, user ID, task ID, and arguments.

        Args:
            func_name (str): Name of the function.
            args (tuple): Positional arguments.
            kwargs (Dict[str, Any]): Keyword arguments.

        Returns:
            str: Cache key.
        """
        user_id = kwargs.get("user_id", "anonymous")
        task_id = kwargs.get("task_id", "none")
        return self.execution_utils.generate_cache_key(func_name, user_id, task_id, args, kwargs)

    def _calculate_ttl_from_strategy(
        self,
        ttl_strategy: Optional[Union[int, Callable]],
        result: Any,
        args: tuple,
        kwargs: Dict[str, Any],
    ) -> Optional[int]:
        """
        Calculate TTL based on the provided strategy.

        Supports multiple strategy types:
        1. None: Use default TTL from config
        2. int: Fixed TTL in seconds
        3. Callable: Dynamic TTL calculation function

        Args:
            ttl_strategy: TTL strategy (None, int, or Callable)
            result: Function execution result
            args: Function positional arguments
            kwargs: Function keyword arguments

        Returns:
            Optional[int]: Calculated TTL in seconds, or None for default

        Example:
            # Strategy function signature
            def my_ttl_strategy(result: Any, args: tuple, kwargs: dict) -> int:
                if result.get('type') == 'permanent':
                    return 86400 * 30  # 30 days
                return 3600  # 1 hour
        """
        # Case 1: No strategy - use default
        if ttl_strategy is None:
            return None

        # Case 2: Fixed TTL (integer)
        if isinstance(ttl_strategy, int):
            return ttl_strategy

        # Case 3: Callable strategy - dynamic calculation
        if callable(ttl_strategy):
            try:
                calculated_ttl = ttl_strategy(result, args, kwargs)
                if not isinstance(calculated_ttl, int) or calculated_ttl < 0:
                    logger.warning(f"TTL strategy returned invalid value: {calculated_ttl}. " f"Expected positive integer. Using default TTL.")
                    return None
                return calculated_ttl
            except Exception as e:
                logger.error(f"Error calculating TTL from strategy: {e}. Using default TTL.")
                return None

        # Invalid strategy type
        logger.warning(f"Invalid TTL strategy type: {type(ttl_strategy)}. " f"Expected None, int, or Callable. Using default TTL.")
        return None

    def _get_from_cache(self, cache_key: str) -> Optional[Any]:
        """
        Get a result from cache if it exists and is not expired (synchronous).

        Args:
            cache_key (str): Cache key.

        Returns:
            Optional[Any]: Cached result or None.
        """
        if not self.config.enable_cache:
            return None
        return self.cache_provider.get(cache_key)

    def _add_to_cache(self, cache_key: str, result: Any, ttl: Optional[int] = None) -> None:
        """
        Add a result to the cache with optional TTL (synchronous).

        Args:
            cache_key (str): Cache key.
            result (Any): Result to cache.
            ttl (Optional[int]): Time-to-live in seconds.
        """
        if not self.config.enable_cache:
            return
        self.cache_provider.set(cache_key, result, ttl)

    async def _get_from_cache_async(self, cache_key: str) -> Optional[Any]:
        """
        Get a result from cache if it exists and is not expired (asynchronous).

        Args:
            cache_key (str): Cache key.

        Returns:
            Optional[Any]: Cached result or None.
        """
        if not self.config.enable_cache:
            return None

        # Use async interface if available
        if hasattr(self.cache_provider, "get_async"):
            return await self.cache_provider.get_async(cache_key)
        else:
            # Fallback to sync interface
            return self.cache_provider.get(cache_key)

    async def _add_to_cache_async(self, cache_key: str, result: Any, ttl: Optional[int] = None) -> None:
        """
        Add a result to the cache with optional TTL (asynchronous).

        Args:
            cache_key (str): Cache key.
            result (Any): Result to cache.
            ttl (Optional[int]): Time-to-live in seconds.
        """
        if not self.config.enable_cache:
            return

        # Use async interface if available
        if hasattr(self.cache_provider, "set_async"):
            await self.cache_provider.set_async(cache_key, result, ttl)
        else:
            # Fallback to sync interface
            self.cache_provider.set(cache_key, result, ttl)

    def get_lock(self, resource_id: str) -> threading.Lock:
        """
        Get or create a lock for a specific resource.

        Args:
            resource_id (str): Resource identifier.

        Returns:
            threading.Lock: Lock for the resource.
        """
        if resource_id not in self._locks:
            self._locks[resource_id] = threading.Lock()
        return self._locks[resource_id]

    def get_metrics(self) -> Dict[str, Any]:
        """
        Get current executor metrics.

        Returns:
            Dict[str, Any]: Metrics including request count, failures, cache hits, and average processing time.
        """
        return self._metrics.to_dict()

    @contextmanager
    def timeout_context(self, seconds: int):
        """
        Context manager for enforcing operation timeouts.

        Args:
            seconds (int): Timeout duration in seconds.

        Raises:
            TimeoutError: If operation exceeds timeout.
        """
        return self.execution_utils.timeout_context(seconds)

    async def _retry_operation(self, func: Callable, *args, **kwargs) -> Any:
        """
        Execute an operation with retries for transient errors.

        Args:
            func (Callable): Function to execute.
            *args: Positional arguments.
            **kwargs: Keyword arguments.

        Returns:
            Any: Result of the operation.

        Raises:
            OperationError: If all retries fail.
        """
        return await self.execution_utils.execute_with_retry_and_timeout(func, self.config.timeout, *args, **kwargs)

    def execute(self, tool_instance: Any, operation: str, **kwargs) -> Any:
        """
        Execute a synchronous tool operation with parameters.

        Args:
            tool_instance (Any): The tool instance to execute the operation on.
            operation (str): The name of the operation to execute.
            **kwargs: The parameters to pass to the operation.

        Returns:
            Any: The result of the operation.

        Raises:
            ToolExecutionError: If the operation fails.
            InputValidationError: If input parameters are invalid.
            SecurityError: If inputs contain malicious content.
        """
        method = getattr(tool_instance, operation, None)
        if not method or not callable(method) or operation.startswith("_"):
            available_ops = [m for m in dir(tool_instance) if not m.startswith("_") and callable(getattr(tool_instance, m))]
            raise ToolExecutionError(f"Unsupported operation: {operation}. Available operations: {', '.join(available_ops)}")
        logger.info(f"Executing {tool_instance.__class__.__name__}.{operation} with params: {kwargs}")
        start_time = time.time()
        try:
            # Sanitize inputs
            if self.config.enable_security_checks:
                for k, v in kwargs.items():
                    if isinstance(v, str) and re.search(r"(\bSELECT\b|\bINSERT\b|--|;|/\*)", v, re.IGNORECASE):
                        raise SecurityError(f"Input parameter '{k}' contains potentially malicious content")
            # Use cache if enabled
            if self.config.enable_cache:
                cache_key = self._get_cache_key(operation, (), kwargs)
                cached_result = self._get_from_cache(cache_key)
                if cached_result is not None:
                    self._metrics.record_cache_hit()
                    logger.debug(f"Cache hit for {operation}")
                    return cached_result

            result = method(**kwargs)
            self._metrics.record_request(time.time() - start_time)
            if self.config.log_execution_time:
                logger.info(f"{tool_instance.__class__.__name__}.{operation} executed in {time.time() - start_time:.4f} seconds")

            # Cache result if enabled
            if self.config.enable_cache:
                self._add_to_cache(cache_key, result)
            return result
        except Exception as e:
            self._metrics.record_failure()
            logger.error(
                f"Error executing {tool_instance.__class__.__name__}.{operation}: {str(e)}",
                exc_info=True,
            )
            raise OperationError(f"Error executing {operation}: {str(e)}") from e

    async def execute_async(self, tool_instance: Any, operation: str, **kwargs) -> Any:
        """
        Execute an asynchronous tool operation with parameters.

        Args:
            tool_instance (Any): The tool instance to execute the operation on.
            operation (str): The name of the operation to execute.
            **kwargs: The parameters to pass to the operation.

        Returns:
            Any: The result of the operation.

        Raises:
            ToolExecutionError: If the operation fails.
            InputValidationError: If input parameters are invalid.
            SecurityError: If inputs contain malicious content.
        """
        method = getattr(tool_instance, operation, None)
        if not method or not callable(method) or operation.startswith("_"):
            available_ops = [m for m in dir(tool_instance) if not m.startswith("_") and callable(getattr(tool_instance, m))]
            raise ToolExecutionError(f"Unsupported operation: {operation}. Available operations: {', '.join(available_ops)}")
        is_async = inspect.iscoroutinefunction(method)
        logger.info(f"Executing async {tool_instance.__class__.__name__}.{operation} with params: {kwargs}")
        start_time = time.time()
        try:
            # Sanitize inputs
            if self.config.enable_security_checks:
                for k, v in kwargs.items():
                    if isinstance(v, str) and re.search(r"(\bSELECT\b|\bINSERT\b|--|;|/\*)", v, re.IGNORECASE):
                        raise SecurityError(f"Input parameter '{k}' contains potentially malicious content")
            # Use cache if enabled (async)
            if self.config.enable_cache:
                cache_key = self._get_cache_key(operation, (), kwargs)
                cached_result = await self._get_from_cache_async(cache_key)
                if cached_result is not None:
                    self._metrics.record_cache_hit()
                    logger.debug(f"Cache hit for {operation} (async)")
                    return cached_result

            async def _execute():
                if is_async:
                    return await method(**kwargs)
                loop = asyncio.get_event_loop()
                return await loop.run_in_executor(self._thread_pool, functools.partial(method, **kwargs))

            result = await self._retry_operation(_execute)
            self._metrics.record_request(time.time() - start_time)
            if self.config.log_execution_time:
                logger.info(f"{tool_instance.__class__.__name__}.{operation} executed in {time.time() - start_time:.4f} seconds")

            # Cache result if enabled (async)
            if self.config.enable_cache:
                await self._add_to_cache_async(cache_key, result)
            return result
        except Exception as e:
            self._metrics.record_failure()
            logger.error(
                f"Error executing {tool_instance.__class__.__name__}.{operation}: {str(e)}",
                exc_info=True,
            )
            raise OperationError(f"Error executing {operation}: {str(e)}") from e

    async def execute_batch(self, tool_instance: Any, operations: List[Dict[str, Any]]) -> List[Any]:
        """
        Execute multiple tool operations in parallel.

        Args:
            tool_instance (Any): The tool instance to execute operations on.
            operations (List[Dict[str, Any]]): List of operation dictionaries with 'op' and 'kwargs'.

        Returns:
            List[Any]: List of operation results.

        Raises:
            ToolExecutionError: If any operation fails.
            InputValidationError: If input parameters are invalid.
        """
        tasks = []
        for op_data in operations:
            op = op_data.get("op")
            kwargs = op_data.get("kwargs", {})
            if not op:
                raise InputValidationError("Operation name missing in batch request")
            tasks.append(self.execute_async(tool_instance, op, **kwargs))
        results = await asyncio.gather(*tasks, return_exceptions=True)
        for i, result in enumerate(results):
            if isinstance(result, Exception):
                logger.error(f"Batch operation {operations[i]['op']} failed: {result}")
        return results


# Singleton executor instance (for backward compatibility)
_default_executor = None


def get_executor(config: Optional[Dict[str, Any]] = None) -> ToolExecutor:
    """
    Get or create executor instance.

    If config is provided, creates a new executor with that config.
    If config is None, returns the default singleton executor.

    Args:
        config (Dict[str, Any], optional): Configuration overrides.
            If provided, creates a new executor instance.
            If None, returns the default singleton.

    Returns:
        ToolExecutor: Executor instance.
    """
    global _default_executor

    # If config is provided, create a new executor with that config
    if config is not None:
        return ToolExecutor(config)

    # Otherwise, return the default singleton
    if _default_executor is None:
        _default_executor = ToolExecutor()
    return _default_executor
