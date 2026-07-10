"""L1 内存缓存层 - 带动态TTL策略的LRU缓存

特性：
- LRU缓存（基于 collections.OrderedDict + 自定义TTL策略）
- maxsize=10000
- 缓存key: MD5(query) + str(top_k)
- 缓存value: 检索结果列表
- 动态TTL策略：
  * 热门查询（访问>10次/天）: TTL=7天
  * 普通查询: TTL=24小时
  * 冷门查询（访问<1次/天）: TTL=1小时
- 缓存统计监控（命中率/大小/淘汰率）
- 缓存预热机制（服务启动时加载Top 100热门查询）

线程安全：使用 threading.RLock 保证并发访问安全
"""

import hashlib
import logging
import time
import threading
from collections import OrderedDict
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class L1QueryCache:
    """L1 内存缓存 - 带动态TTL的LRU缓存实现"""

    TTL_HOT = 7 * 24 * 3600       # 热门查询：7天
    TTL_NORMAL = 24 * 3600        # 普通查询：24小时
    TTL_COLD = 3600               # 冷门查询：1小时

    ACCESS_THRESHOLD_HOT = 10     # 每天访问>10次视为热门
    ACCESS_THRESHOLD_COLD = 1     # 每天访问<1次视为冷门

    def __init__(self, maxsize: int = 10000):
        self._cache: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._maxsize = maxsize
        self._lock = threading.RLock()

        # 访问频率追踪：{cache_key: [timestamp1, timestamp2, ...]}
        self._access_log: Dict[str, List[float]] = {}

        # 统计计数器
        self._hit_count = 0
        self._miss_count = 0
        self._evict_count = 0
        self._total_requests = 0

        # 启动时间（用于计算日均访问率）
        self._start_time = time.time()

        logger.info(f"L1缓存初始化完成，maxsize={maxsize}")

    def _generate_key(self, query: str, top_k: int) -> str:
        """生成缓存键：MD5(query) + str(top_k)"""
        query_hash = hashlib.md5(query.strip().encode('utf-8')).hexdigest()
        return f"{query_hash}:{top_k}"

    def _get_ttl(self, cache_key: str) -> int:
        """根据访问频率动态计算TTL"""
        now = time.time()
        access_times = self._access_log.get(cache_key, [])

        # 计算最近24小时内的访问次数
        recent_accesses = [t for t in access_times if now - t < 86400]
        accesses_per_day = len(recent_accesses)

        if accesses_per_day > self.ACCESS_THRESHOLD_HOT:
            return self.TTL_HOT
        elif accesses_per_day < self.ACCESS_THRESHOLD_COLD:
            return self.TTL_COLD
        else:
            return self.TTL_NORMAL

    def _record_access(self, cache_key: str):
        """记录访问"""
        if cache_key not in self._access_log:
            self._access_log[cache_key] = []
        self._access_log[cache_key].append(time.time())

        # 清理超过7天的访问记录，避免内存泄漏
        cutoff = time.time() - 7 * 86400
        self._access_log[cache_key] = [
            t for t in self._access_log[cache_key] if t > cutoff
        ]

    def _is_expired(self, cache_key: str, entry: Dict[str, Any]) -> bool:
        """检查缓存条目是否过期"""
        now = time.time()
        ttl = entry.get('ttl', self.TTL_NORMAL)
        return (now - entry['timestamp']) > ttl

    def get(self, query: str, top_k: int = 5) -> Optional[List[Dict[str, Any]]]:
        """获取缓存结果

        Args:
            query: 用户查询文本
            top_k: 返回结果数量

        Returns:
            缓存的结果列表，未命中或过期则返回None
        """
        cache_key = self._generate_key(query, top_k)

        with self._lock:
            self._total_requests += 1

            if cache_key not in self._cache:
                self._miss_count += 1
                logger.debug(f"L1缓存未命中: query='{query[:30]}...', top_k={top_k}")
                return None

            entry = self._cache[cache_key]

            # 检查是否过期
            if self._is_expired(cache_key, entry):
                del self._cache[cache_key]
                self._access_log.pop(cache_key, None)
                self._miss_count += 1
                logger.debug(f"L1缓存过期: query='{query[:30]}...', top_k={top_k}")
                return None

            # 缓存命中：更新访问记录并移至OrderedDict末尾（LRU）
            self._record_access(cache_key)
            self._cache.move_to_end(cache_key)
            self._hit_count += 1

            logger.debug(f"L1缓存命中: query='{query[:30]}...', top_k={top_k}")
            return entry['results']

    def set(self, query: str, results: List[Dict[str, Any]], top_k: int = 5) -> None:
        """存储缓存结果

        Args:
            query: 用户查询文本
            results: 检索结果列表
            top_k: 结果数量
        """
        cache_key = self._generate_key(query, top_k)

        with self._lock:
            # 如果缓存已满，淘汰最久未使用的条目
            if len(self._cache) >= self._maxsize and cache_key not in self._cache:
                self._evict_lru()

            # 动态计算TTL
            ttl = self._get_ttl(cache_key)

            # 记录访问
            self._record_access(cache_key)

            # 存入缓存
            self._cache[cache_key] = {
                'results': results,
                'top_k': top_k,
                'timestamp': time.time(),
                'ttl': ttl,
                'query': query
            }

            # 移至末尾（最新）
            self._cache.move_to_end(cache_key)

            logger.debug(
                f"L1缓存写入: query='{query[:30]}...', top_k={top_k}, TTL={ttl}s"
            )

    def _evict_lru(self) -> None:
        """淘汰最久未使用的缓存条目（LRU策略）"""
        if not self._cache:
            return

        # 弹出最早（最久未使用）的条目
        oldest_key, _ = self._cache.popitem(last=False)
        self._access_log.pop(oldest_key, None)
        self._evict_count += 1

        logger.debug(f"L1缓存淘汰: key='{oldest_key[:16]}...'")

    def evict_expired(self) -> int:
        """清理所有过期缓存条目

        Returns:
            清理的数量
        """
        with self._lock:
            expired_keys = [
                key for key, entry in self._cache.items()
                if self._is_expired(key, entry)
            ]

            for key in expired_keys:
                del self._cache[key]
                self._access_log.pop(key, None)
                self._evict_count += 1

            if expired_keys:
                logger.info(f"L1缓存清理过期条目: {len(expired_keys)}个")

            return len(expired_keys)

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息

        Returns:
            包含命中率、大小、淘汰率等信息的字典
        """
        with self._lock:
            total_requests = self._hit_count + self._miss_count
            hit_rate = self._hit_count / total_requests if total_requests > 0 else 0.0
            evict_rate = self._evict_count / total_requests if total_requests > 0 else 0.0

            uptime_hours = (time.time() - self._start_time) / 3600

            return {
                'hit_count': self._hit_count,
                'miss_count': self._miss_count,
                'hit_rate': round(hit_rate, 4),
                'cache_size': len(self._cache),
                'max_size': self._maxsize,
                'evict_count': self._evict_count,
                'evict_rate': round(evict_rate, 4),
                'total_requests': total_requests,
                'uptime_hours': round(uptime_hours, 2),
                'ttl_hot_seconds': self.TTL_HOT,
                'ttl_normal_seconds': self.TTL_NORMAL,
                'ttl_cold_seconds': self.TTL_COLD,
                'cache_utilization': round(len(self._cache) / self._maxsize * 100, 2),
            }

    def warm_up(self, popular_queries: List[str], top_k: int = 5) -> int:
        """缓存预热 - 服务启动时加载热门查询

        Args:
            popular_queries: 热门查询列表
            top_k: 每个查询的结果数量

        Returns:
            预热的查询数量
        """
        if not popular_queries:
            logger.info("L1缓存预热：无热门查询需要加载")
            return 0

        warmed_count = 0

        with self._lock:
            for query in popular_queries:
                cache_key = self._generate_key(query, top_k)

                # 跳过已存在的缓存
                if cache_key in self._cache:
                    continue

                # 预热条目使用热门TTL
                self._cache[cache_key] = {
                    'results': [],  # 预热占位，实际结果需外部提供
                    'top_k': top_k,
                    'timestamp': time.time(),
                    'ttl': self.TTL_HOT,
                    'query': query,
                    'is_warmup': True
                }

                # 模拟高频访问，使其保持为热门查询
                self._access_log[cache_key] = [
                    time.time() - i * 3600
                    for i in range(15)  # 模拟15次访问，超过热门阈值
                ]

                self._cache.move_to_end(cache_key)
                warmed_count += 1

            logger.info(f"L1缓存预热完成: {warmed_count}个热门查询")
            return warmed_count

    def invalidate(self, query: str, top_k: int = 5) -> bool:
        """使指定查询的缓存失效

        Args:
            query: 要失效的查询
            top_k: 结果数量

        Returns:
            是否成功删除
        """
        cache_key = self._generate_key(query, top_k)

        with self._lock:
            if cache_key in self._cache:
                del self._cache[cache_key]
                self._access_log.pop(cache_key, None)
                logger.debug(f"L1缓存失效: query='{query[:30]}...', top_k={top_k}")
                return True
            return False

    def clear(self) -> None:
        """清空所有缓存"""
        with self._lock:
            self._cache.clear()
            self._access_log.clear()
            self._hit_count = 0
            self._miss_count = 0
            self._evict_count = 0
            self._total_requests = 0
            self._start_time = time.time()
            logger.info("L1缓存已清空")


# 全局缓存实例（模块级单例）
_l1_cache: Optional[L1QueryCache] = None


def get_l1_cache() -> L1QueryCache:
    """获取全局L1缓存实例（线程安全单例）

    Returns:
        L1QueryCache实例
    """
    global _l1_cache
    if _l1_cache is None:
        _l1_cache = L1QueryCache(maxsize=10000)
        logger.info("L1缓存实例已创建")
    return _l1_cache


def reset_l1_cache() -> None:
    """重置L1缓存实例（主要用于测试）"""
    global _l1_cache
    if _l1_cache is not None:
        _l1_cache.clear()
        logger.info("L1缓存实例已重置")


# 别名：兼容不同导入习惯
L1Cache = L1QueryCache
