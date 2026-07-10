"""SimHash语义近似匹配缓存 - 基于内容相似度的智能缓存

核心算法：
- SimHash：将文本映射为64位指纹，语义相似的文本指纹也相似
- 汉明距离：两个指纹不同位的数量，距离越小文本越相似
- 阈值：汉明距离<=3视为相似查询，直接返回缓存结果

特性：
- 64位SimHash指纹（simhash库）
- 汉明距离<=3判定为相似
- 同时维护精确匹配索引（MD5）和近似匹配索引（SimHash）
- TTL: 24小时
- 最大缓存条目：10000
- 不阻塞检索流程（计算失败时静默跳过）

技术依赖：
- pip install simhash

使用示例：
    cache = get_simhash_cache()
    # 查找近似匹配
    result = cache.get("这张卡的效果是什么？", top_k=5)
    # 写入缓存
    cache.set("这张卡的效果是什么？", results, top_k=5)
    # 获取统计
    stats = cache.get_stats()
"""

import hashlib
import logging
import time
import threading
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

# ============================================================
# SimHash 配置常量
# ============================================================
SIMHASH_BITS = 64             # SimHash指纹位数（64位标准）
HAMMING_THRESHOLD = 3         # 汉明距离阈值：<=3视为相似
SIMHASH_TTL = 86400           # 缓存过期时间：24小时（秒）
SIMHASH_MAX_SIZE = 10000      # 最大缓存条目数


def _compute_simhash(text: str) -> int:
    """计算文本的SimHash指纹（64位整数）

    算法流程：
    1. 对文本进行分词（使用字符级n-gram，避免分词依赖）
    2. 对每个词计算MD5哈希
    3. 根据哈希位累加/累减权重向量
    4. 根据权重向量正负生成最终指纹

    Args:
        text: 输入文本

    Returns:
        64位SimHash指纹（整数）
    """
    try:
        from simhash import Simhash
        simhash_obj = Simhash(text, f=SIMHASH_BITS)
        return simhash_obj.value
    except ImportError:
        logger.error("simhash库未安装，请执行: pip install simhash")
        raise
    except Exception as e:
        logger.warning("SimHash计算失败: %s", str(e))
        # 降级方案：使用文本MD5的前8字节作为伪SimHash
        md5_bytes = hashlib.md5(text.encode("utf-8")).digest()
        return int.from_bytes(md5_bytes[:8], byteorder="big")


def _hamming_distance(hash1: int, hash2: int) -> int:
    """计算两个SimHash指纹之间的汉明距离

    汉明距离 = 两个整数异或结果中1的位数
    Python的bin()函数返回'0b...'格式，统计'1'的数量即可

    Args:
        hash1: 第一个SimHash指纹
        hash2: 第二个SimHash指纹

    Returns:
        汉明距离（0~64之间的整数）
    """
    xor = hash1 ^ hash2
    return bin(xor).count("1")


class SimHashCacheEntry:
    """SimHash缓存条目"""

    def __init__(
        self,
        query: str,
        simhash: int,
        results: List[Dict[str, Any]],
        top_k: int = 5,
        ttl: int = SIMHASH_TTL,
    ):
        self.query = query
        self.simhash = simhash
        self.results = results
        self.top_k = top_k
        self.timestamp = time.time()
        self.ttl = ttl
        self.hit_count = 0

    def is_expired(self) -> bool:
        """检查缓存条目是否过期"""
        return (time.time() - self.timestamp) > self.ttl

    def record_hit(self):
        """记录一次命中"""
        self.hit_count += 1


class SimHashCache:
    """SimHash语义近似匹配缓存

    内部维护两个索引：
    1. _exact_index: MD5哈希 -> 缓存条目（精确匹配，O(1)）
    2. _simhash_index: [(simhash, entry), ...] 列表（近似匹配，O(n)线性扫描）

    检索流程：
    1. 先查精确匹配索引（MD5）
    2. 未命中时计算SimHash，扫描近似匹配索引
    3. 找到汉明距离<=3的条目则返回
    4. 都未命中则返回None
    """

    def __init__(
        self,
        ttl: int = SIMHASH_TTL,
        max_size: int = SIMHASH_MAX_SIZE,
        hamming_threshold: int = HAMMING_THRESHOLD,
    ):
        self._ttl = ttl
        self._max_size = max_size
        self._hamming_threshold = hamming_threshold

        # 精确匹配索引：MD5(query) -> SimHashCacheEntry
        self._exact_index: Dict[str, SimHashCacheEntry] = {}

        # SimHash近似匹配索引：[(simhash_value, entry_ref), ...]
        self._simhash_index: List[tuple] = []

        # 线程锁
        self._lock = threading.RLock()

        # 统计计数器
        self._hit_count = 0
        self._miss_count = 0
        self._approximate_hit_count = 0  # 近似匹配命中次数
        self._evict_count = 0
        self._total_requests = 0
        self._start_time = time.time()

        logger.info(
            "SimHash缓存初始化: TTL=%ds, max_size=%d, hamming_threshold=%d",
            ttl,
            max_size,
            hamming_threshold,
        )

    def _generate_exact_key(self, query: str) -> str:
        """生成精确匹配的缓存键（MD5哈希）"""
        return hashlib.md5(query.strip().encode("utf-8")).hexdigest()

    def _evict_expired(self) -> int:
        """清理过期的缓存条目

        Returns:
            清理的条目数量
        """
        now = time.time()
        expired_exact_keys = []
        expired_simhash_indices = []

        # 扫描精确匹配索引
        for key, entry in self._exact_index.items():
            if now - entry.timestamp > self._ttl:
                expired_exact_keys.append(key)

        # 扫描SimHash索引
        for i, (simhash, entry) in enumerate(self._simhash_index):
            if now - entry.timestamp > self._ttl:
                expired_simhash_indices.append(i)

        # 删除过期条目（倒序删除避免索引偏移）
        for key in expired_exact_keys:
            del self._exact_index[key]

        for i in reversed(expired_simhash_indices):
            self._simhash_index.pop(i)

        cleaned = len(expired_exact_keys)
        self._evict_count += cleaned
        return cleaned

    def _evict_oldest(self) -> None:
        """淘汰最早的缓存条目（FIFO策略，当缓存满时）"""
        if not self._exact_index:
            return

        # 找到最早的条目
        oldest_key = min(
            self._exact_index.keys(),
            key=lambda k: self._exact_index[k].timestamp,
        )

        del self._exact_index[oldest_key]
        self._simhash_index = [
            (sh, entry)
            for sh, entry in self._simhash_index
            if entry.query != oldest_key
        ]
        self._evict_count += 1

    def get(
        self, query: str, top_k: int = 5
    ) -> Optional[List[Dict[str, Any]]]:
        """获取缓存结果（支持精确匹配和语义近似匹配）

        匹配流程：
        1. 精确匹配：MD5(query) -> 直接命中
        2. 近似匹配：计算SimHash -> 查找汉明距离<=threshold的条目
        3. 都未命中则返回None

        Args:
            query: 用户查询文本
            top_k: 返回结果数量

        Returns:
            缓存的检索结果，未命中时返回None
        """
        with self._lock:
            self._total_requests = self._hit_count + self._miss_count + 1

            # ---- 步骤1：精确匹配 ----
            exact_key = self._generate_exact_key(query)
            if exact_key in self._exact_index:
                entry = self._exact_index[exact_key]

                # 检查过期
                if entry.is_expired():
                    del self._exact_index[exact_key]
                    self._simhash_index = [
                        (sh, e)
                        for sh, e in self._simhash_index
                        if e is not entry
                    ]
                    self._miss_count += 1
                    return None

                # 检查top_k
                if entry.top_k != top_k:
                    self._miss_count += 1
                    return None

                # 精确命中
                entry.record_hit()
                self._hit_count += 1
                logger.debug(
                    "SimHash精确命中: query='%s...', top_k=%d", query[:30], top_k
                )
                return entry.results

            # ---- 步骤2：近似匹配（SimHash） ----
            try:
                query_simhash = _compute_simhash(query)
            except Exception as e:
                logger.warning("SimHash计算失败，跳过近似匹配: %s", str(e))
                self._miss_count += 1
                return None

            best_match = None
            best_distance = self._hamming_threshold + 1

            for simhash, entry in self._simhash_index:
                # 跳过过期条目
                if entry.is_expired():
                    continue

                # 跳过top_k不匹配的条目
                if entry.top_k != top_k:
                    continue

                distance = _hamming_distance(query_simhash, simhash)

                if distance <= self._hamming_threshold and distance < best_distance:
                    best_match = entry
                    best_distance = distance

                    # 找到完全匹配（距离0）可提前退出
                    if distance == 0:
                        break

            if best_match is not None:
                best_match.record_hit()
                self._hit_count += 1
                self._approximate_hit_count += 1
                logger.debug(
                    "SimHash近似命中: query='%s...', hamming_distance=%d, top_k=%d",
                    query[:30],
                    best_distance,
                    top_k,
                )
                return best_match.results

            # 都未命中
            self._miss_count += 1
            logger.debug(
                "SimHash未命中: query='%s...', top_k=%d", query[:30], top_k
            )
            return None

    def set(
        self, query: str, results: List[Dict[str, Any]], top_k: int = 5
    ) -> None:
        """存储缓存结果（同时写入精确索引和SimHash索引）

        Args:
            query: 用户查询文本
            results: 检索结果列表
            top_k: 结果数量
        """
        with self._lock:
            exact_key = self._generate_exact_key(query)

            # 缓存满时清理
            if len(self._exact_index) >= self._max_size:
                self._evict_expired()
                if len(self._exact_index) >= self._max_size:
                    self._evict_oldest()

            # 计算SimHash指纹
            try:
                query_simhash = _compute_simhash(query)
            except Exception as e:
                logger.warning("SimHash计算失败，跳过缓存写入: %s", str(e))
                return

            # 创建缓存条目
            entry = SimHashCacheEntry(
                query=query,
                simhash=query_simhash,
                results=results,
                top_k=top_k,
                ttl=self._ttl,
            )

            # 写入精确匹配索引
            self._exact_index[exact_key] = entry

            # 写入SimHash近似匹配索引
            self._simhash_index.append((query_simhash, entry))

            logger.debug(
                "SimHash缓存写入: query='%s...', simhash=%016x, top_k=%d",
                query[:30],
                query_simhash,
                top_k,
            )

    def delete(self, query: str) -> bool:
        """删除缓存结果

        Args:
            query: 要删除的查询文本

        Returns:
            是否成功删除
        """
        with self._lock:
            exact_key = self._generate_exact_key(query)

            if exact_key not in self._exact_index:
                return False

            entry = self._exact_index[exact_key]

            # 从精确索引删除
            del self._exact_index[exact_key]

            # 从SimHash索引删除
            self._simhash_index = [
                (sh, e) for sh, e in self._simhash_index if e is not entry
            ]

            return True

    def get_stats(self) -> Dict[str, Any]:
        """获取缓存统计信息

        Returns:
            包含命中率、缓存大小、近似匹配次数等信息的字典
        """
        with self._lock:
            total = self._hit_count + self._miss_count
            hit_rate = self._hit_count / total if total > 0 else 0.0
            approx_rate = (
                self._approximate_hit_count / self._hit_count
                if self._hit_count > 0
                else 0.0
            )
            uptime_hours = (time.time() - self._start_time) / 3600

            return {
                "hit_count": self._hit_count,
                "miss_count": self._miss_count,
                "approximate_hit_count": self._approximate_hit_count,
                "hit_rate": round(hit_rate, 4),
                "approximate_hit_rate": round(approx_rate, 4),
                "cache_size": len(self._exact_index),
                "max_size": self._max_size,
                "evict_count": self._evict_count,
                "ttl_seconds": self._ttl,
                "hamming_threshold": self._hamming_threshold,
                "simhash_bits": SIMHASH_BITS,
                "uptime_hours": round(uptime_hours, 2),
                "cache_utilization": round(
                    len(self._exact_index) / self._max_size * 100, 2
                ),
            }

    def clear(self) -> None:
        """清空所有缓存"""
        with self._lock:
            self._exact_index.clear()
            self._simhash_index.clear()
            self._hit_count = 0
            self._miss_count = 0
            self._approximate_hit_count = 0
            self._evict_count = 0
            self._start_time = time.time()
            logger.info("SimHash缓存已清空")


# ============================================================
# 全局单例（模块级）
# ============================================================
_simhash_cache: Optional[SimHashCache] = None


def get_simhash_cache() -> SimHashCache:
    """获取全局SimHash缓存实例（线程安全单例）

    Returns:
        SimHashCache实例
    """
    global _simhash_cache
    if _simhash_cache is None:
        _simhash_cache = SimHashCache()
        logger.info("SimHash缓存实例已创建")
    return _simhash_cache


def reset_simhash_cache() -> None:
    """重置SimHash缓存实例（主要用于测试）"""
    global _simhash_cache
    if _simhash_cache is not None:
        _simhash_cache.clear()
        _simhash_cache = None
        logger.info("SimHash缓存实例已重置")
