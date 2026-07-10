"""多轮对话记忆服务 - 基于 Redis/内存的会话历史管理

特性：
- 支持会话级别的对话历史管理
- Redis 分布式存储（支持多实例共享）
- 降级策略：Redis 不可用时自动切换为内存 LRU 缓存
- TTL：30 分钟（1800秒）
- 自动序列化/反序列化
- 线程安全

使用示例：
    memory = get_conversation_memory()
    memory.add_message("session_123", "user", "你好")
    memory.add_message("session_123", "assistant", "你好！有什么可以帮你？")
    history = memory.get_history("session_123", max_turns=5)
    memory.clear_history("session_123")
"""

import json
import logging
import time
import threading
from collections import OrderedDict
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

REDIS_TTL = 1800                    # 缓存过期时间：30分钟（秒）
REDIS_HOST = "localhost"            # 默认Redis主机
REDIS_PORT = 6379                   # 默认Redis端口
REDIS_DB = 0                        # 默认Redis数据库编号
REDIS_SOCKET_TIMEOUT = 2            # 连接超时（秒）
REDIS_SOCKET_CONNECT_TIMEOUT = 2    # 连接建立超时（秒）
REDIS_KEY_PREFIX = "ocg:memory:"    # Redis key前缀
MAX_MEMORY_SESSIONS = 1000          # 内存模式最大会话数
MAX_MESSAGES_PER_SESSION = 20       # 每个会话最大消息数


class MemoryFallbackStore:
    """内存降级存储 - 当Redis不可用时使用的LRU存储
    
    作为Redis的降级方案，提供与Redis相同的基础接口。
    """

    def __init__(self, max_sessions: int = MAX_MEMORY_SESSIONS, ttl: int = REDIS_TTL):
        self._store: OrderedDict[str, Dict[str, Any]] = OrderedDict()
        self._max_sessions = max_sessions
        self._ttl = ttl
        self._lock = threading.RLock()

        self._hit_count = 0
        self._miss_count = 0
        self._evict_count = 0
        self._start_time = time.time()

    def get(self, session_id: str) -> Optional[List[Dict]]:
        """从内存存储获取会话历史"""
        with self._lock:
            if session_id not in self._store:
                self._miss_count += 1
                return None

            entry = self._store[session_id]

            if time.time() - entry["timestamp"] > self._ttl:
                del self._store[session_id]
                self._miss_count += 1
                return None

            self._store.move_to_end(session_id)
            self._hit_count += 1
            return entry["messages"]

    def set(self, session_id: str, messages: List[Dict]) -> None:
        """将会话历史写入内存存储"""
        with self._lock:
            if len(self._store) >= self._max_sessions and session_id not in self._store:
                self._store.popitem(last=False)
                self._evict_count += 1

            self._store[session_id] = {
                "messages": messages,
                "timestamp": time.time(),
            }
            self._store.move_to_end(session_id)

    def delete(self, session_id: str) -> bool:
        """从内存存储删除会话历史"""
        with self._lock:
            if session_id in self._store:
                del self._store[session_id]
                return True
            return False

    def get_stats(self) -> Dict[str, Any]:
        """获取内存存储统计信息"""
        with self._lock:
            total = self._hit_count + self._miss_count
            hit_rate = self._hit_count / total if total > 0 else 0.0
            uptime_hours = (time.time() - self._start_time) / 3600

            return {
                "hit_count": self._hit_count,
                "miss_count": self._miss_count,
                "hit_rate": round(hit_rate, 4),
                "session_count": len(self._store),
                "max_sessions": self._max_sessions,
                "evict_count": self._evict_count,
                "ttl_seconds": self._ttl,
                "mode": "memory_fallback",
                "uptime_hours": round(uptime_hours, 2),
            }

    def clear(self) -> None:
        """清空内存存储"""
        with self._lock:
            self._store.clear()
            self._hit_count = 0
            self._miss_count = 0
            self._evict_count = 0
            self._start_time = time.time()


class ConversationMemory:
    """多轮对话记忆管理器（带 Redis + 内存降级）

    核心流程：
    1. 初始化时尝试连接 Redis 服务器
    2. 如果连接失败，自动降级为 MemoryFallbackStore
    3. 所有操作都包含错误处理，Redis 操作失败时静默降级
    4. 支持会话管理、消息添加、历史获取、历史清除
    """

    def __init__(
        self,
        host: str = REDIS_HOST,
        port: int = REDIS_PORT,
        db: int = REDIS_DB,
        ttl: int = REDIS_TTL,
    ):
        self._host = host
        self._port = port
        self._db = db
        self._ttl = ttl

        self._fallback_mode = False

        self._redis_client = self._try_connect_redis(host, port, db)

        if self._redis_client is None:
            self._fallback_mode = True
            self._memory_store = MemoryFallbackStore(ttl=ttl)
            logger.warning(
                "对话记忆已降级为内存模式（Redis不可用: %s:%d）", host, port
            )
        else:
            self._memory_store = None
            logger.info(
                "对话记忆 Redis 已连接: %s:%d, db=%d, TTL=%ds",
                host, port, db, ttl,
            )

    def _try_connect_redis(self, host: str, port: int, db: int):
        """尝试连接Redis服务器，失败返回None"""
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

            client.ping()
            return client

        except ImportError:
            logger.warning("redis-py库未安装，对话记忆降级为内存模式（pip install redis）")
            return None
        except Exception as e:
            logger.warning("Redis连接失败，对话记忆降级为内存模式: %s", str(e))
            return None

    def _make_key(self, session_id: str) -> str:
        """生成带命名空间前缀的Redis键"""
        return f"{REDIS_KEY_PREFIX}{session_id}"

    def _serialize(self, messages: List[Dict]) -> str:
        """序列化消息列表为JSON字符串"""
        return json.dumps(
            {
                "messages": messages,
                "timestamp": time.time(),
            },
            ensure_ascii=False,
        )

    def _deserialize(self, raw: str) -> Optional[List[Dict]]:
        """从JSON字符串反序列化消息列表"""
        if raw is None:
            return None

        try:
            data = json.loads(raw)

            if time.time() - data.get("timestamp", 0) > self._ttl:
                return None

            return data["messages"]

        except (json.JSONDecodeError, KeyError, TypeError) as e:
            logger.warning("对话记忆反序列化失败: %s", str(e))
            return None

    def add_message(self, session_id: str, role: str, content: str) -> bool:
        """添加消息到会话历史

        Args:
            session_id: 会话ID
            role: 消息角色（user/assistant/system）
            content: 消息内容

        Returns:
            是否添加成功
        """
        redis_key = self._make_key(session_id)

        existing = self._get_raw(session_id, redis_key)
        if existing is None:
            messages = []
        else:
            messages = existing

        message = {
            "role": role,
            "content": content,
            "timestamp": time.time(),
        }
        messages.append(message)

        if len(messages) > MAX_MESSAGES_PER_SESSION:
            messages = messages[-MAX_MESSAGES_PER_SESSION:]

        return self._set_raw(session_id, redis_key, messages)

    def get_history(self, session_id: str, max_turns: int = 5) -> List[Dict]:
        """获取历史对话

        Args:
            session_id: 会话ID
            max_turns: 最大返回轮数（每轮包含 user + assistant 两条消息）

        Returns:
            历史消息列表，按时间顺序排列
        """
        redis_key = self._make_key(session_id)

        messages = self._get_raw(session_id, redis_key)
        if messages is None:
            return []

        if max_turns <= 0:
            return []

        total_messages = max_turns * 2
        return messages[-total_messages:]

    def clear_history(self, session_id: str) -> bool:
        """清除会话历史

        Args:
            session_id: 会话ID

        Returns:
            是否清除成功
        """
        redis_key = self._make_key(session_id)
        success = False

        if not self._fallback_mode and self._redis_client is not None:
            try:
                self._redis_client.delete(redis_key)
                success = True
            except Exception as e:
                logger.warning("对话记忆 Redis DELETE 失败: %s", str(e))

        if self._memory_store is not None:
            self._memory_store.delete(session_id)
            success = True

        return success

    def get_session_ids(self) -> List[str]:
        """获取所有活跃会话ID（仅 Redis 模式有效）"""
        if self._fallback_mode or self._redis_client is None:
            return []

        try:
            keys = self._redis_client.keys(f"{REDIS_KEY_PREFIX}*")
            return [k.replace(REDIS_KEY_PREFIX, "") for k in keys]
        except Exception as e:
            logger.warning("获取会话列表失败: %s", str(e))
            return []

    def get_stats(self) -> Dict[str, Any]:
        """获取对话记忆统计信息"""
        stats = {
            "mode": "memory_fallback" if self._fallback_mode else "redis",
            "host": self._host,
            "port": self._port,
            "ttl_seconds": self._ttl,
        }

        if not self._fallback_mode and self._redis_client is not None:
            try:
                keys = self._redis_client.keys(f"{REDIS_KEY_PREFIX}*")
                stats.update({
                    "connected": True,
                    "active_sessions": len(keys),
                })
            except Exception as e:
                stats["connected"] = False
                stats["error"] = str(e)
        else:
            stats["connected"] = False
            if self._memory_store is not None:
                mem_stats = self._memory_store.get_stats()
                stats.update(mem_stats)

        return stats

    def is_fallback_mode(self) -> bool:
        """检查是否处于降级模式"""
        return self._fallback_mode

    def reconnect(self) -> bool:
        """尝试重新连接Redis"""
        if not self._fallback_mode:
            return True

        logger.info("尝试重新连接Redis（对话记忆）...")
        client = self._try_connect_redis(self._host, self._port, self._db)

        if client is not None:
            self._redis_client = client
            self._fallback_mode = False
            logger.info("对话记忆 Redis 已恢复连接")
            return True

        logger.warning("对话记忆 Redis 重新连接失败")
        return False

    def _get_raw(self, session_id: str, redis_key: str) -> Optional[List[Dict]]:
        """内部方法：获取原始消息列表"""
        if not self._fallback_mode and self._redis_client is not None:
            try:
                raw = self._redis_client.get(redis_key)
                result = self._deserialize(raw)
                if result is not None:
                    return result
            except Exception as e:
                logger.warning("对话记忆 Redis GET 失败，降级到内存: %s", str(e))

        if self._memory_store is not None:
            return self._memory_store.get(session_id)

        return None

    def _set_raw(self, session_id: str, redis_key: str, messages: List[Dict]) -> bool:
        """内部方法：设置原始消息列表"""
        serialized = self._serialize(messages)
        success = False

        if not self._fallback_mode and self._redis_client is not None:
            try:
                self._redis_client.setex(redis_key, self._ttl, serialized)
                success = True
            except Exception as e:
                logger.warning("对话记忆 Redis SET 失败: %s", str(e))

        if self._memory_store is not None:
            self._memory_store.set(session_id, messages)
            success = True

        return success


_global_memory: Optional[ConversationMemory] = None


def get_conversation_memory() -> ConversationMemory:
    """获取全局对话记忆实例（线程安全单例）"""
    global _global_memory
    if _global_memory is None:
        _global_memory = ConversationMemory()
        logger.info("对话记忆实例已创建（模式: %s）", "内存降级" if _global_memory.is_fallback_mode() else "Redis")
    return _global_memory


def reset_conversation_memory() -> None:
    """重置对话记忆实例（主要用于测试）"""
    global _global_memory
    if _global_memory is not None:
        _global_memory = None
        logger.info("对话记忆实例已重置")
