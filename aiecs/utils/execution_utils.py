import json
import asyncio
import threading
import time
from typing import Any, Callable, Dict, Optional, MutableMapping
from cachetools import LRUCache
from contextlib import contextmanager
import logging
from tenacity import retry, stop_after_attempt, wait_exponential

logger = logging.getLogger(__name__)


class ExecutionUtils:
    """
    Provides common utility set for execution layer, including caching and retry logic.
    """

    def __init__(
        self,
        cache_size: int = 100,
        cache_ttl: int = 3600,
        retry_attempts: int = 3,
        retry_backoff: float = 1.0,
    ):
        """
        Initialize execution utility class.

        Args:
            cache_size (int): Maximum number of cache entries
            cache_ttl (int): Cache time-to-live (seconds)
            retry_attempts (int): Number of retry attempts
            retry_backoff (float): Retry backoff factor
        """
        self.cache_size = cache_size
        self.cache_ttl = cache_ttl
        self.retry_attempts = retry_attempts
        self.retry_backoff = retry_backoff
        self._cache: Optional[MutableMapping[str, Any]] = LRUCache(maxsize=self.cache_size) if cache_size > 0 else None
        self._cache_lock = threading.Lock()
        self._cache_ttl_dict: Dict[str, float] = {}

    def generate_cache_key(
        self,
        func_name: str,
        user_id: str,
        task_id: str,
        args: tuple,
        kwargs: Dict[str, Any],
    ) -> str:
        """
        Generate context-based cache key including user ID, task ID, function name and parameters.

        Args:
            func_name (str): Function name
            user_id (str): User ID
            task_id (str): Task ID
            args (tuple): Positional arguments
            kwargs (Dict[str, Any]): Keyword arguments

        Returns:
            str: Cache key
        """
        key_dict = {
            "func": func_name,
            "user_id": user_id,
            "task_id": task_id,
            "args": args,
            "kwargs": {k: v for k, v in kwargs.items() if k != "self"},
        }
        try:
            key_str = json.dumps(key_dict, sort_keys=True)
        except (TypeError, ValueError):
            key_str = str(key_dict)
        return hash(key_str).__str__()

    def get_from_cache(self, cache_key: str) -> Optional[Any]:
        """
        Get result from cache if it exists and is not expired.

        Args:
            cache_key (str): Cache key

        Returns:
            Optional[Any]: Cached result or None
        """
        if self._cache is None:
            return None
        with self._cache_lock:
            if cache_key in self._cache:
                if cache_key in self._cache_ttl_dict and time.time() > self._cache_ttl_dict[cache_key]:
                    del self._cache[cache_key]
                    del self._cache_ttl_dict[cache_key]
                    return None
                return self._cache[cache_key]
        return None

    def add_to_cache(self, cache_key: str, result: Any, ttl: Optional[int] = None) -> None:
        """
        Add result to cache with optional time-to-live setting.

        Args:
            cache_key (str): Cache key
            result (Any): Cached result
            ttl (Optional[int]): Time-to-live (seconds)
        """
        if self._cache is None:
            return
        with self._cache_lock:
            self._cache[cache_key] = result
            ttl = ttl if ttl is not None else self.cache_ttl
            if ttl > 0:
                self._cache_ttl_dict[cache_key] = time.time() + ttl

    def create_retry_strategy(self, metric_name: Optional[str] = None) -> Callable:
        """
        Create retry strategy for execution operations.

        Args:
            metric_name (Optional[str]): Metric name for logging

        Returns:
            Callable: Retry decorator
        """

        def after_retry(retry_state):
            logger.warning(f"Retry {retry_state.attempt_number}/{self.retry_attempts} for {metric_name or 'operation'} after {retry_state.idle_for}s: {retry_state.outcome.exception()}")

        return retry(
            stop=stop_after_attempt(self.retry_attempts),
            wait=wait_exponential(multiplier=self.retry_backoff, min=1, max=10),
            after=after_retry,
        )

    @contextmanager
    def timeout_context(self, seconds: int):
        """
        Context manager for enforcing operation timeout.

        Args:
            seconds (int): Timeout duration (seconds)

        Raises:
            TimeoutError: If operation exceeds timeout duration
        """
        loop = asyncio.get_event_loop()
        future: asyncio.Future[None] = asyncio.Future()
        handle = loop.call_later(
            seconds,
            lambda: future.set_exception(TimeoutError(f"Operation timed out after {seconds}s")),
        )
        try:
            yield future
        finally:
            handle.cancel()

    async def execute_with_retry_and_timeout(self, func: Callable, timeout: int, *args, **kwargs) -> Any:
        """
        Execute operation with retry and timeout mechanism.

        Args:
            func (Callable): Function to execute
            timeout (int): Timeout duration (seconds)
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Any: Operation result

        Raises:
            OperationError: If all retry attempts fail
        """
        retry_strategy = self.create_retry_strategy(func.__name__)
        try:
            return await asyncio.wait_for(retry_strategy(func)(*args, **kwargs), timeout=timeout)
        except asyncio.TimeoutError:
            raise TimeoutError(f"Operation timed out after {timeout}s")
