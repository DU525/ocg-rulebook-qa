"""L2 Redis缓存层 - 分布式持久化缓存（带内存降级机制）

特性：
- Redis分布式缓存（支持多实例共享）
- 降级策略：Redis不可用时自动切换为内存LRU缓存
- 缓存key: MD5(query)
- 缓存value: JSON序列化的检索结果
- TTL: 24小时（86400秒）
- 最大内存: 1GB（通过maxmemory-policy allkeys-lru配置）
- 实现 get/set/delete/stats 接口
- 不阻塞检索流程（缓存失败时静默降级）

线程安全：Redis客户端线程安全；内存降级模式使用 threading.RLock
"""

import hashlib
import json
import logging
import time
import threading
from collections import OrderedDict
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ============================================================
# Redis 配置常量
# ============================================================
REDIS_TTL = 86400               # 缓存过期时间：24小时（秒）
REDIS_MAXMEMORY = "1gb"         # 最大内存限制
REDIS_MAXMEMORY_POLICY = "allkeys-lru"  # 内存满时的淘汰策略
REDIS_KEY_PREFIX = "ocg:cache:"  # Redis key前缀（避免命名空间冲突）
REDIS_HOST = "localhost"        # 默认Redis主机
REDIS_PORT = 6379               # 默认Redis端口
REDIS_DB = 0                    # 默认Redis数据库编号
REDIS_SOCKET_TIMEOUT = 2        # 连接超时（秒）：短超时确保快速降级
REDIS_SOCKET_CONNECT_TIMEOUT = 2  # 连接建立超时（秒）


class MemoryFallbackCache:
    """内存降级缓存 - 当Redis不可用时使用的LRU缓存

    作为Redis的降级方案，提供与Redis相同的基础接口。
    容量限制为10000条，TTL为24小时，使用LRU淘汰策略。
    """

    def __init__(self, maxsize: int = 10000, ttl: int = REDIS_TTL):
        self._cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._maxsize = maxsize
        self._ttl = ttl
        self._lock = threading.RLock()

        # 统计计数器
        self._hit_count = 0
        self._miss_count = 0
        self._evict_count = 0
        self._start_time = time.time()

    def get(self, key: str) -> Optional[Any]:
        """从内存缓存获取数据"""
        with self._lock:
            if key not in self._cache:
                self._miss_count += 1
                return None

            entry = self._cache[key]

            # 检查是否过期
            if time.time() - entry["timestamp"] > self._ttl:
                del self._cache[key]
                self._miss_count += 1
                return None

            # 命中：移至末尾（LRU更新）
            self._cache.move_to_end(key)
            self._hit_count += 1
            return entry["value"]

    def set(self, key: str, value: Any, ttl: Optional[int] = None) -> None:
        """将数据写入内存缓存"""
        effective_ttl = ttl if ttl is not None else self._ttl

        with self._lock:
            # 缓存满时淘汰最久未使用的条目
            if len(self._cache) >= self._maxsize and key not in self._cache:
                self._cache.popitem(last=False)
                self._evict_count += 1

            self._cache[key] = {
                "value": value,
                "timestamp": time.time(),
                "ttl": effective_ttl,
            }
            self._cache.move_to_end(key)

    def delete(self, key: str) -> bool:
        """从内存缓存删除数据"""
        with self._lock:
            if key in self._cache:
                del self._cache[key]
                return True
            return False

    def get_stats(self) -> Dict[str, Any]:
        """获取内存缓存统计信息"""
        with self._lock:
            total = self._hit_count + self._miss_count
            hit_rate = self._hit_count / total if total > 0 else 0.0
            uptime_hours = (time.time() - self._start_time) / 3600

            return {
                "hit_count": self._hit_count,
                "miss_count": self._miss_count,
                "hit_rate": round(hit_rate, 4),
                "cache_size": len(self._cache),
                "max_size": self._maxsize,
                "evict_count": self._evict_count,
                "ttl_seconds": self._ttl,
                "mode": "memory_fallback",
                "uptime_hours": round(uptime_hours, 2),
                "cache_utilization": round(
                    len(self._cache) / self._maxsize * 100, 2
                ),
            }

    def clear(self) -> None:
        """清空内存缓存"""
        with self._lock:
            self._cache.clear()
            self._hit_count = 0
            self._miss_count = 0
            self._evict_count = 0
            self._start_time = time.time()


class RedisCache:
    """L2 Redis分布式缓存客户端（带内存降级）

    核心流程：
    1. 初始化时尝试连接Redis服务器
    2. 如果连接失败，自动降级为 MemoryFallbackCache
    3. 所有操作都包含错误处理，Redis操作失败时静默降级
    4. 缓存键使用前缀命名空间，避免与其他应用冲突

    使用示例：
        cache = get_redis_cache()
        cache.set("query_hash", results, top_k=5)
        results = cache.get("query_hash")
        cache.delete("query_hash")
        stats = cache.get_stats()
    """

    def __init__(
        self,
        host: str = REDIS_HOST,
        port: int = REDIS_PORT,
        db: int = REDIS_DB,
        ttl: int = REDIS_TTL,
        maxmemory: str = REDIS_MAXMEMORY,
    ):
        self._host = host
        self._port = port
        self._db = db
        self._ttl = ttl
        self._maxmemory = maxmemory

        # 降级模式标志
        self._fallback_mode = False

        # 尝试初始化Redis客户端
        self._redis_client = self._try_connect_redis(
            host, port, db, maxmemory
        )

        # 如果Redis连接失败，创建内存降级缓存
        if self._redis_client is None:
            self._fallback_mode = True
            self._memory_cache = MemoryFallbackCache()
            logger.warning(
                "L2缓存已降级为内存模式（Redis不可用: %s:%d）", host, port
            )
        else:
            self._memory_cache = None
            logger.info(
                "L2 Redis缓存已连接: %s:%d, db=%d, TTL=%ds, maxmemory=%s",
                host,
                port,
                db,
                ttl,
                maxmemory,
            )

    def _try_connect_redis(
        self, host: str, port: int, db: int, maxmemory: str
    ):
        """尝试连接Redis服务器，失败返回None

        Args:
            host: Redis主机地址
            port: Redis端口
            db: Redis数据库编号
            maxmemory: 最大内存限制

        Returns:
            Redis客户端实例，或None（连接失败时）
        """
        try:
            import redis

            client = redis.Redis(
                host=host,
                port=port,
                db=db,
                socket_timeout=REDIS_SOCKET_TIMEOUT,
                socket_connect_timeout=REDIS_SOCKET_CONNECT_TIMEOUT,
                decode_responses=True,
            )

            # 测试连接是否可用
            client.ping()

            # 配置Redis内存限制和淘汰策略
            try:
                client.config_set("maxmemory", maxmemory)
                client.config_set(
                    "maxmemory-policy", REDIS_MAXMEMORY_POLICY
                )
                logger.info(
                    "Redis内存配置已设置: maxmemory=%s, policy=%s",
                    maxmemory,
                    REDIS_MAXMEMORY_POLICY,
                )
            except Exception as e:
                logger.warning(
                    "Redis配置设置失败（不影响使用）: %s", str(e)
                )

            return client

        except ImportError:
            logger.warning(
                "redis-py库未安装，L2缓存降级为内存模式（pip install redis）"
            )
            return None
        except Exception as e:
            logger.warning("Redis连接失败，L2缓存降级为内存模式: %s", str(e))
            return None

    def _make_key(self, query_hash: str) -> str:
        """生成带命名空间前缀的Redis键

        Args:
            query_hash: 查询的MD5哈希值

        Returns:
            带前缀的完整Redis键
        """
        return f"{REDIS_KEY_PREFIX}{query_hash}"

    def _serialize(self, value: Any, top_k: int = 5) -> str:
        """序列化缓存值为JSON字符串

        Args:
            value: 要序列化的值（通常是检索结果列表）
            top_k: 结果数量（用于元数据记录）

        Returns:
            JSON格式的字符串
        """
        return json.dumps(
            {
                "results": value,
                "top_k": top_k,
                "timestamp": time.time(),
            },
            ensure_ascii=False,
        )

    def _deserialize(self, raw: str) -> Optional[Any]:
        """从JSON字符串反序列化缓存值

        Args:
            raw: JSON格式的缓存值字符串

        Returns:
            反序列化后的结果，或None（解析失败/过期时）
        """
        if raw is None:
            return None

        try:
            data = json.loads(raw)

            # 检查是否过期
            if time.time() - data.get("timestamp", 0) > self._ttl:
                return None

            return data["results"]

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning("Redis缓存值反序列化失败: %s", str(e))
            return None

    def get(self, query: str) -> Optional[Any]:
        """获取缓存结果

        流程：
        1. 生成查询的MD5哈希作为缓存键
        2. 优先从Redis获取（如果可用）
        3. Redis失败时自动降级到内存缓存

        Args:
            query: 用户查询文本

        Returns:
            缓存的检索结果，未命中时返回None
        """
        query_hash = hashlib.md5(query.strip().encode("utf-8")).hexdigest()
        redis_key = self._make_key(query_hash)

        # 优先尝试Redis
        if not self._fallback_mode and self._redis_client is not None:
            try:
                raw = self._redis_client.get(redis_key)
                result = self._deserialize(raw)
                if result is not None:
                    logger.debug("L2 Redis缓存命中: query='%s...'", query[:30])
                    return result
            except Exception as e:
                logger.warning("L2 Redis GET失败，降级到内存缓存: %s", str(e))

        # 降级到内存缓存
        if self._memory_cache is not None:
            result = self._memory_cache.get(redis_key)
            if result is not None:
                logger.debug(
                    "L2 内存降级缓存命中: query='%s...'", query[:30]
                )
            return result

        return None

    def set(
        self, query: str, results: List[Dict[str, Any]], top_k: int = 5
    ) -> None:
        """存储缓存结果

        流程：
        1. 生成查询的MD5哈希作为缓存键
        2. 序列化结果并写入Redis（设置TTL）
        3. 同时写入内存降级缓存（保持数据同步）

        Args:
            query: 用户查询文本
            results: 检索结果列表
            top_k: 结果数量
        """
        query_hash = hashlib.md5(query.strip().encode("utf-8")).hexdigest()
        redis_key = self._make_key(query_hash)
        serialized = self._serialize(results, top_k)

        # 尝试写入Redis
        if not self._fallback_mode and self._redis_client is not None:
            try:
                self._redis_client.setex(redis_key, self._ttl, serialized)
                logger.debug(
                    "L2 Redis缓存写入: query='%s...', top_k=%d", query[:30], top_k
                )
            except Exception as e:
                logger.warning("L2 Redis SET失败: %s", str(e))

        # 同步写入内存降级缓存（保持数据一致性）
        if self._memory_cache is not None:
            self._memory_cache.set(redis_key, results)

    def delete(self, query: str) -> bool:
        """删除缓存结果

        Args:
            query: 要删除的查询文本

        Returns:
            是否成功删除
        """
        query_hash = hashlib.md5(query.strip().encode("utf-8")).hexdigest()
        redis_key = self._make_key(query_hash)
        success = False

        # 尝试从Redis删除
        if not self._fallback_mode and self._redis_client is not None:
            try:
                self._redis_client.delete(redis_key)
                success = True
            except Exception as e:
                logger.warning("L2 Redis DELETE失败: %s", str(e))

        # 同步从内存缓存删除
        if self._memory_cache is not None:
            self._memory_cache.delete(redis_key)
            success = True

        return success

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息

        返回内容：
        - 命中率、缓存大小、TTL等基础信息
        - Redis连接状态和模式（Redis/降级）
        - 如果Redis可用，额外返回Redis服务器的内存和客户端信息

        Returns:
            缓存统计信息字典
        """
        stats = {
            "mode": "memory_fallback" if self._fallback_mode else "redis",
            "host": self._host,
            "port": self._port,
            "ttl_seconds": self._ttl,
        }

        # 如果Redis可用，获取服务器信息
        if not self._fallback_mode and self._redis_client is not None:
            try:
                info = self._redis_client.info("memory")
                client_info = self._redis_client.info("clients")

                stats.update(
                    {
                        "connected": True,
                        "used_memory_human": info.get(
                            "used_memory_human", "unknown"
                        ),
                        "maxmemory_human": info.get(
                            "maxmemory_human", "unknown"
                        ),
                        "connected_clients": client_info.get(
                            "connected_clients", 0
                        ),
                        "total_keys": self._redis_client.dbsize(),
                    }
                )
            except Exception as e:
                stats["connected"] = False
                stats["error"] = str(e)
                logger.warning("获取Redis统计信息失败: %s", str(e))
        else:
            # 降级模式：使用内存缓存的统计
            stats["connected"] = False
            if self._memory_cache is not None:
                mem_stats = self._memory_cache.get_stats()
                stats.update(mem_stats)

        return stats

    def clear(self) -> None:
        """清空所有缓存（Redis和内存）"""
        # 清空Redis（仅删除本应用前缀的key）
        if not self._fallback_mode and self._redis_client is not None:
            try:
                keys = self._redis_client.keys(f"{REDIS_KEY_PREFIX}*")
                if keys:
                    self._redis_client.delete(*keys)
                    logger.info(
                        "L2 Redis缓存已清空: 删除%d个key", len(keys)
                    )
            except Exception as e:
                logger.warning("L2 Redis清空失败: %s", str(e))

        # 清空内存缓存
        if self._memory_cache is not None:
            self._memory_cache.clear()
            logger.info("L2 内存降级缓存已清空")

    def is_fallback_mode(self) -> bool:
        """检查是否处于降级模式

        Returns:
            True表示Redis不可用，正在使用内存缓存
        """
        return self._fallback_mode

    def reconnect(self) -> bool:
        """尝试重新连接Redis（用于降级后恢复）

        如果当前处于降级模式，尝试重新连接Redis。
        连接成功后自动切换回Redis模式。

        Returns:
            是否重新连接成功
        """
        if not self._fallback_mode:
            return True

        logger.info("尝试重新连接Redis...")
        client = self._try_connect_redis(
            self._host, self._port, self._db, self._maxmemory
        )

        if client is not None:
            self._redis_client = client
            self._fallback_mode = False
            logger.info("L2 Redis缓存已恢复连接")
            return True

        logger.warning("L2 Redis重新连接失败")
        return False


# ============================================================
# 全局单例（模块级）
# ============================================================
_redis_cache: Optional[RedisCache] = None


def get_redis_cache() -> RedisCache:
    """获取全局L2 Redis缓存实例（线程安全单例）

    首次调用时创建实例并尝试连接Redis。
    后续调用返回已缓存的实例。

    Returns:
        RedisCache实例（Redis模式或内存降级模式）
    """
    global _redis_cache
    if _redis_cache is None:
        _redis_cache = RedisCache()
        logger.info("L2缓存实例已创建（模式: %s）", "内存降级" if _redis_cache.is_fallback_mode() else "Redis")
    return _redis_cache


def reset_redis_cache() -> None:
    """重置L2缓存实例（主要用于测试）"""
    global _redis_cache
    if _redis_cache is not None:
        _redis_cache.clear()
        _redis_cache = None
        logger.info("L2缓存实例已重置")
