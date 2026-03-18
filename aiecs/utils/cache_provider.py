"""
Cache Provider Interface and Implementations

提供统一的缓存接口，支持多种缓存策略和存储后端。
所有缓存实现都应该实现 ICacheProvider 接口，以便与 ToolExecutor 和其他组件集成。

Architecture:
    ICacheProvider (Interface)
        ├── LRUCacheProvider (Default: wraps ExecutionUtils)
        ├── DualLayerCacheProvider (L1: Memory + L2: Custom)
        └── Custom implementations (e.g., IntelligentCacheProvider)

Usage:
    # Use default LRU cache
    from aiecs.utils.cache_provider import LRUCacheProvider
    cache = LRUCacheProvider(execution_utils)

    # Use dual-layer cache
    from aiecs.utils.cache_provider import DualLayerCacheProvider
    cache = DualLayerCacheProvider(l1_provider, l2_provider)
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, Optional
import logging
import threading

logger = logging.getLogger(__name__)


class ICacheProvider(ABC):
    """
    缓存提供者接口

    所有缓存实现都应该实现这个接口，以便与 ToolExecutor 和其他组件集成。
    这个接口定义了缓存的核心操作：获取、设置、失效和统计。

    支持同步和异步两种接口：
    - 同步接口 (get, set, invalidate): 用于向后兼容和简单场景
    - 异步接口 (get_async, set_async, invalidate_async): 用于异步操作和高性能场景

    Example:
        class MyCacheProvider(ICacheProvider):
            def get(self, key: str) -> Optional[Any]:
                # 实现同步获取逻辑
                pass

            async def get_async(self, key: str) -> Optional[Any]:
                # 实现异步获取逻辑
                pass

            def set(self, key: str, value: Any, ttl: Optional[int] = None):
                # 实现同步设置逻辑
                pass

            async def set_async(self, key: str, value: Any, ttl: Optional[int] = None):
                # 实现异步设置逻辑
                pass
    """

    @abstractmethod
    def get(self, key: str) -> Optional[Any]:
        """
        获取缓存值（同步接口）

        Args:
            key: 缓存键

        Returns:
            缓存的值，如果不存在或已过期则返回 None
        """

    @abstractmethod
    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """
        设置缓存值（同步接口）

        Args:
            key: 缓存键
            value: 要缓存的值
            ttl: 过期时间（秒），None 表示使用默认 TTL
        """

    @abstractmethod
    def invalidate(self, key: str):
        """
        使缓存失效（同步接口）

        Args:
            key: 缓存键
        """

    @abstractmethod
    def get_stats(self) -> Dict[str, Any]:
        """
        获取缓存统计信息

        Returns:
            包含缓存统计的字典，至少应包含：
            - type: 缓存类型
            - hits: 命中次数（可选）
            - misses: 未命中次数（可选）
            - hit_rate: 命中率（可选）
        """

    def clear(self):
        """
        清空所有缓存（可选实现）

        默认实现为空操作，子类可以根据需要覆盖。
        """

    # Async interface (optional, with default implementations)
    async def get_async(self, key: str) -> Optional[Any]:
        """
        获取缓存值（异步接口）

        默认实现调用同步方法。子类应该覆盖此方法以提供真正的异步实现。

        Args:
            key: 缓存键

        Returns:
            缓存的值，如果不存在或已过期则返回 None
        """
        return self.get(key)

    async def set_async(self, key: str, value: Any, ttl: Optional[int] = None):
        """
        设置缓存值（异步接口）

        默认实现调用同步方法。子类应该覆盖此方法以提供真正的异步实现。

        Args:
            key: 缓存键
            value: 要缓存的值
            ttl: 过期时间（秒），None 表示使用默认 TTL
        """
        self.set(key, value, ttl)

    async def invalidate_async(self, key: str):
        """
        使缓存失效（异步接口）

        默认实现调用同步方法。子类应该覆盖此方法以提供真正的异步实现。

        Args:
            key: 缓存键
        """
        self.invalidate(key)


class LRUCacheProvider(ICacheProvider):
    """
    基于 ExecutionUtils 的 LRU 缓存提供者

    这是默认的缓存实现，包装了现有的 ExecutionUtils 缓存逻辑。
    使用 LRU (Least Recently Used) 淘汰策略和 TTL 过期机制。

    Features:
        - LRU 淘汰策略
        - TTL 过期机制
        - 线程安全
        - 内存缓存

    Example:
        from aiecs.utils.execution_utils import ExecutionUtils
        from aiecs.utils.cache_provider import LRUCacheProvider

        execution_utils = ExecutionUtils(cache_size=100, cache_ttl=3600)
        cache = LRUCacheProvider(execution_utils)

        # 使用缓存
        cache.set("key1", "value1", ttl=300)
        value = cache.get("key1")
    """

    def __init__(self, execution_utils):
        """
        初始化 LRU 缓存提供者

        Args:
            execution_utils: ExecutionUtils 实例
        """
        self.execution_utils = execution_utils
        self._hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        """从 ExecutionUtils 缓存获取值"""
        result = self.execution_utils.get_from_cache(key)
        if result is not None:
            self._hits += 1
            logger.debug(f"Cache hit: {key}")
        else:
            self._misses += 1
            logger.debug(f"Cache miss: {key}")
        return result

    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """设置值到 ExecutionUtils 缓存"""
        self.execution_utils.add_to_cache(key, value, ttl)
        logger.debug(f"Cache set: {key} (ttl={ttl})")

    def invalidate(self, key: str):
        """
        使缓存失效

        ExecutionUtils 没有直接的 invalidate 方法，
        通过直接删除缓存条目来实现。
        """
        if hasattr(self.execution_utils, "_cache") and self.execution_utils._cache:
            with self.execution_utils._cache_lock:
                if key in self.execution_utils._cache:
                    del self.execution_utils._cache[key]
                    logger.debug(f"Cache invalidated: {key}")
                if key in self.execution_utils._cache_ttl_dict:
                    del self.execution_utils._cache_ttl_dict[key]

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        cache_size = 0
        if hasattr(self.execution_utils, "_cache") and self.execution_utils._cache:
            cache_size = len(self.execution_utils._cache)

        total_requests = self._hits + self._misses
        hit_rate = self._hits / total_requests if total_requests > 0 else 0.0

        return {
            "type": "lru",
            "backend": "memory",
            "size": cache_size,
            "max_size": self.execution_utils.cache_size,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
        }

    def clear(self):
        """清空所有缓存"""
        if hasattr(self.execution_utils, "_cache") and self.execution_utils._cache:
            with self.execution_utils._cache_lock:
                self.execution_utils._cache.clear()
                self.execution_utils._cache_ttl_dict.clear()
                logger.info("LRU cache cleared")


class DualLayerCacheProvider(ICacheProvider):
    """
    双层缓存提供者

    实现两层缓存架构：
    - L1: 快速内存缓存（通常是 LRUCacheProvider）
    - L2: 智能缓存（如 Redis + Intent-aware TTL）

    缓存策略：
    1. 读取时先查 L1，命中则直接返回
    2. L1 未命中则查 L2，命中则回填 L1
    3. 写入时同时写入 L1 和 L2

    这是为 SearchTool 等需要高级缓存策略的工具设计的。

    Example:
        from aiecs.utils.cache_provider import DualLayerCacheProvider, LRUCacheProvider

        l1_cache = LRUCacheProvider(execution_utils)
        l2_cache = IntelligentCacheProvider(redis_client)

        dual_cache = DualLayerCacheProvider(
            l1_provider=l1_cache,
            l2_provider=l2_cache,
            l1_ttl=300  # L1 缓存 5 分钟
        )

        # 使用双层缓存
        dual_cache.set("key1", "value1")  # 写入 L1 和 L2
        value = dual_cache.get("key1")    # 先查 L1，再查 L2
    """

    def __init__(
        self,
        l1_provider: ICacheProvider,
        l2_provider: ICacheProvider,
        l1_ttl: int = 300,
    ):
        """
        初始化双层缓存

        Args:
            l1_provider: L1 缓存提供者（通常是 LRUCacheProvider）
            l2_provider: L2 缓存提供者（如 IntelligentCacheProvider）
            l1_ttl: L1 缓存的 TTL（秒），默认 5 分钟
        """
        self.l1 = l1_provider
        self.l2 = l2_provider
        self.l1_ttl = l1_ttl
        self._l1_hits = 0
        self._l2_hits = 0
        self._misses = 0

    def get(self, key: str) -> Optional[Any]:
        """
        双层缓存获取

        1. 先查 L1 缓存
        2. L1 未命中则查 L2 缓存
        3. L2 命中则回填 L1
        """
        # 尝试 L1
        result = self.l1.get(key)
        if result is not None:
            self._l1_hits += 1
            logger.debug(f"L1 cache hit: {key}")
            return result

        # 尝试 L2
        result = self.l2.get(key)
        if result is not None:
            self._l2_hits += 1
            logger.debug(f"L2 cache hit: {key}, warming L1")
            # 回填 L1（使用较短的 TTL）
            self.l1.set(key, result, ttl=self.l1_ttl)
            return result

        self._misses += 1
        logger.debug(f"Cache miss (L1 + L2): {key}")
        return None

    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """
        双层缓存设置

        同时写入 L1 和 L2：
        - L2 使用传入的 TTL（可能是智能计算的）
        - L1 使用固定的短 TTL
        """
        # 写入 L2（使用智能 TTL）
        self.l2.set(key, value, ttl)
        logger.debug(f"L2 cache set: {key} (ttl={ttl})")

        # 写入 L1（使用短 TTL）
        self.l1.set(key, value, ttl=self.l1_ttl)
        logger.debug(f"L1 cache set: {key} (ttl={self.l1_ttl})")

    def invalidate(self, key: str):
        """使两层缓存都失效"""
        self.l1.invalidate(key)
        self.l2.invalidate(key)
        logger.debug(f"Cache invalidated (L1 + L2): {key}")

    def get_stats(self) -> Dict[str, Any]:
        """获取双层缓存统计"""
        l1_stats = self.l1.get_stats()
        l2_stats = self.l2.get_stats()

        total_hits = self._l1_hits + self._l2_hits
        total_requests = total_hits + self._misses

        return {
            "type": "dual_layer",
            "l1": l1_stats,
            "l2": l2_stats,
            "l1_hits": self._l1_hits,
            "l2_hits": self._l2_hits,
            "misses": self._misses,
            "total_requests": total_requests,
            "hit_rate": (total_hits / total_requests if total_requests > 0 else 0.0),
            "l1_hit_rate": (self._l1_hits / total_requests if total_requests > 0 else 0.0),
            "l2_hit_rate": (self._l2_hits / total_requests if total_requests > 0 else 0.0),
        }

    def clear(self):
        """清空两层缓存"""
        self.l1.clear()
        self.l2.clear()
        logger.info("Dual-layer cache cleared")

    # Async interface
    async def get_async(self, key: str) -> Optional[Any]:
        """
        双层缓存异步获取

        1. 先查 L1 缓存（同步）
        2. L1 未命中则查 L2 缓存（异步）
        3. L2 命中则回填 L1
        """
        # 尝试 L1 (同步)
        result = self.l1.get(key)
        if result is not None:
            self._l1_hits += 1
            logger.debug(f"L1 cache hit (async): {key}")
            return result

        # 尝试 L2 (异步)
        result = await self.l2.get_async(key)
        if result is not None:
            self._l2_hits += 1
            logger.debug(f"L2 cache hit (async): {key}, warming L1")
            # 回填 L1（使用较短的 TTL）
            self.l1.set(key, result, ttl=self.l1_ttl)
            return result

        self._misses += 1
        logger.debug(f"Cache miss (L1 + L2, async): {key}")
        return None

    async def set_async(self, key: str, value: Any, ttl: Optional[int] = None):
        """
        双层缓存异步设置

        同时写入 L1 和 L2：
        - L2 使用传入的 TTL（可能是智能计算的）- 异步写入
        - L1 使用固定的短 TTL - 同步写入
        """
        # 写入 L2（异步，使用智能 TTL）
        await self.l2.set_async(key, value, ttl)
        logger.debug(f"L2 cache set (async): {key} (ttl={ttl})")

        # 写入 L1（同步，使用短 TTL）
        self.l1.set(key, value, ttl=self.l1_ttl)
        logger.debug(f"L1 cache set (async): {key} (ttl={self.l1_ttl})")

    async def invalidate_async(self, key: str):
        """使两层缓存都失效（异步）"""
        self.l1.invalidate(key)
        await self.l2.invalidate_async(key)
        logger.debug(f"Cache invalidated (L1 + L2, async): {key}")

    async def clear_async(self):
        """异步清空两层缓存"""
        self.l1.clear()
        if hasattr(self.l2, "clear_async"):
            await self.l2.clear_async()
        else:
            self.l2.clear()
        logger.info("Dual-layer cache cleared (async)")


class RedisCacheProvider(ICacheProvider):
    """
    基于全局 Redis 的缓存提供者

    使用全局 RedisClient 单例，避免重复创建连接池。
    适用于需要持久化缓存或分布式缓存共享的场景。

    Features:
        - 使用全局 Redis 单例
        - 持久化缓存
        - 分布式共享
        - 支持 TTL

    Example:
        from aiecs.utils.cache_provider import RedisCacheProvider

        # 使用全局 Redis 客户端
        cache = await RedisCacheProvider.create(
            prefix="my_app:",
            default_ttl=3600
        )

        # 使用缓存
        await cache.set_async("key1", "value1", ttl=300)
        value = await cache.get_async("key1")

    Note:
        - 需要先调用 initialize_redis_client() 初始化全局 Redis
        - 提供同步接口（使用内存回退）和异步接口（使用 Redis）
    """

    _instance: Optional["RedisCacheProvider"] = None
    _lock = threading.Lock()

    def __init__(self, redis_client, prefix: str = "", default_ttl: int = 3600):
        """
        初始化 Redis 缓存提供者

        Args:
            redis_client: RedisClient 实例
            prefix: 缓存键前缀
            default_ttl: 默认 TTL（秒）
        """
        self.redis_client = redis_client
        self.prefix = prefix
        self.default_ttl = default_ttl
        self._sync_cache: Dict[str, Any] = {}  # 同步接口的内存回退
        self._hits = 0
        self._misses = 0

    @classmethod
    async def create(
        cls,
        prefix: str = "",
        default_ttl: int = 3600,
        use_singleton: bool = True,
    ) -> "RedisCacheProvider":
        """
        创建 RedisCacheProvider 实例

        Args:
            prefix: 缓存键前缀
            default_ttl: 默认 TTL（秒）
            use_singleton: 是否使用单例模式

        Returns:
            RedisCacheProvider 实例

        Raises:
            RuntimeError: 如果全局 Redis 客户端未初始化
        """
        if use_singleton and cls._instance is not None:
            return cls._instance

        try:
            # get_redis_client may not be available in all installations
            from aiecs.infrastructure.persistence import get_redis_client  # type: ignore[attr-defined]

            redis_client = await get_redis_client()

            instance = cls(redis_client, prefix, default_ttl)

            if use_singleton:
                with cls._lock:
                    cls._instance = instance

            logger.info(f"RedisCacheProvider created (prefix={prefix}, ttl={default_ttl})")
            return instance

        except Exception as e:
            logger.error(f"Failed to create RedisCacheProvider: {e}")
            raise

    def _make_key(self, key: str) -> str:
        """生成带前缀的缓存键"""
        return f"{self.prefix}{key}"

    # 同步接口（ICacheProvider 要求）
    def get(self, key: str) -> Optional[Any]:
        """
        同步获取（使用内存回退）

        Note: 对于 Redis 操作，建议使用 get_async()
        """
        result = self._sync_cache.get(key)
        if result is not None:
            self._hits += 1
        else:
            self._misses += 1
        return result

    def set(self, key: str, value: Any, ttl: Optional[int] = None):
        """
        同步设置（使用内存回退）

        Note: 对于 Redis 操作，建议使用 set_async()
        """
        self._sync_cache[key] = value

    def invalidate(self, key: str):
        """同步失效（使用内存回退）"""
        if key in self._sync_cache:
            del self._sync_cache[key]

    # 异步接口（推荐使用）
    async def get_async(self, key: str) -> Optional[Any]:
        """
        异步获取缓存值

        Args:
            key: 缓存键

        Returns:
            缓存的值，如果不存在或已过期则返回 None
        """
        try:
            redis = await self.redis_client.get_client()
            full_key = self._make_key(key)

            value = await redis.get(full_key)
            if value is not None:
                self._hits += 1
                logger.debug(f"Redis cache hit: {key}")
                # 尝试反序列化 JSON
                try:
                    import json

                    return json.loads(value)
                except (json.JSONDecodeError, TypeError):
                    return value
            else:
                self._misses += 1
                logger.debug(f"Redis cache miss: {key}")
                return None

        except Exception as e:
            logger.warning(f"Redis get error for key {key}: {e}")
            self._misses += 1
            return None

    async def set_async(self, key: str, value: Any, ttl: Optional[int] = None):
        """
        异步设置缓存值

        Args:
            key: 缓存键
            value: 要缓存的值
            ttl: 过期时间（秒），None 表示使用默认 TTL
        """
        try:
            redis = await self.redis_client.get_client()
            full_key = self._make_key(key)
            ttl = ttl if ttl is not None else self.default_ttl

            # 序列化为 JSON
            import json

            try:
                serialized_value = json.dumps(value)
            except (TypeError, ValueError):
                serialized_value = str(value)

            if ttl > 0:
                await redis.setex(full_key, ttl, serialized_value)
            else:
                await redis.set(full_key, serialized_value)

            logger.debug(f"Redis cache set: {key} (ttl={ttl})")

        except Exception as e:
            logger.warning(f"Redis set error for key {key}: {e}")

    async def invalidate_async(self, key: str):
        """
        异步使缓存失效

        Args:
            key: 缓存键
        """
        try:
            redis = await self.redis_client.get_client()
            full_key = self._make_key(key)
            await redis.delete(full_key)
            logger.debug(f"Redis cache invalidated: {key}")

        except Exception as e:
            logger.warning(f"Redis invalidate error for key {key}: {e}")

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计"""
        total_requests = self._hits + self._misses
        hit_rate = self._hits / total_requests if total_requests > 0 else 0.0

        return {
            "type": "redis",
            "backend": "redis",
            "prefix": self.prefix,
            "default_ttl": self.default_ttl,
            "hits": self._hits,
            "misses": self._misses,
            "hit_rate": hit_rate,
            "sync_cache_size": len(self._sync_cache),
        }

    def clear(self):
        """清空同步缓存（Redis 缓存需要使用 clear_async）"""
        self._sync_cache.clear()

    async def clear_async(self, pattern: Optional[str] = None):
        """
        异步清空缓存

        Args:
            pattern: 键模式，None 表示清空所有带前缀的键
        """
        try:
            redis = await self.redis_client.get_client()
            pattern = pattern or f"{self.prefix}*"

            keys_to_delete = []
            async for key in redis.scan_iter(match=pattern):
                keys_to_delete.append(key)

            if keys_to_delete:
                await redis.delete(*keys_to_delete)
                logger.info(f"Redis cache cleared: {len(keys_to_delete)} keys deleted")

        except Exception as e:
            logger.warning(f"Redis clear error: {e}")


# 导出接口和实现
__all__ = [
    "ICacheProvider",
    "LRUCacheProvider",
    "DualLayerCacheProvider",
    "RedisCacheProvider",
]
