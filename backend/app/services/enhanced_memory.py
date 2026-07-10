"""
增强记忆管理系统 - Enhanced Memory System

实现分层记忆架构：
- 短期记忆 (Short-Term Memory): 最近对话，快速访问
- 长期记忆 (Long-Term Memory): 压缩摘要，持久存储
- 工作记忆 (Working Memory): 当前激活的上下文

功能特性：
- 记忆存储与分层管理
- 记忆压缩与摘要生成
- 记忆去重 (SimHash 检测)
- 重要性权重计算
- 自动迁移与衰减
"""

import json
import logging
import time
import threading
import hashlib
import numpy as np
from typing import Any, Dict, List, Optional, Set, Tuple
from datetime import datetime, timedelta
from collections import OrderedDict
from dataclasses import dataclass, asdict
from enum import Enum

logger = logging.getLogger(__name__)


class MemoryType(Enum):
    """记忆类型枚举"""
    SHORT_TERM = "short_term"
    LONG_TERM = "long_term"
    WORKING = "working"
    EPISODIC = "episodic"
    SEMANTIC = "semantic"


@dataclass
class MemoryItem:
    """记忆项数据结构"""
    id: str
    content: str
    memory_type: MemoryType
    importance: float = 0.5  # 重要性权重 0.0-1.0
    timestamp: float = 0.0
    access_count: int = 0
    last_access: float = 0.0
    embedding: Optional[List[float]] = None
    metadata: Dict[str, Any] = None
    tags: Set[str] = None
    simhash: str = ""  # 用于去重
    
    def __post_init__(self):
        if self.timestamp == 0.0:
            self.timestamp = time.time()
        if self.last_access == 0.0:
            self.last_access = self.timestamp
        if self.metadata is None:
            self.metadata = {}
        if self.tags is None:
            self.tags = set()
        if not self.simhash:
            self.simhash = self._compute_simhash()
    
    def _compute_simhash(self) -> str:
        """计算 SimHash 用于去重"""
        content_hash = hashlib.md5(self.content.encode('utf-8')).hexdigest()
        return content_hash[:16]
    
    def to_dict(self) -> Dict:
        """转换为字典"""
        return {
            "id": self.id,
            "content": self.content,
            "memory_type": self.memory_type.value,
            "importance": self.importance,
            "timestamp": self.timestamp,
            "access_count": self.access_count,
            "last_access": self.last_access,
            "embedding": self.embedding,
            "metadata": self.metadata,
            "tags": list(self.tags),
            "simhash": self.simhash,
        }
    
    @classmethod
    def from_dict(cls, data: Dict) -> 'MemoryItem':
        """从字典创建"""
        return cls(
            id=data["id"],
            content=data["content"],
            memory_type=MemoryType(data["memory_type"]),
            importance=data.get("importance", 0.5),
            timestamp=data.get("timestamp", 0.0),
            access_count=data.get("access_count", 0),
            last_access=data.get("last_access", 0.0),
            embedding=data.get("embedding"),
            metadata=data.get("metadata", {}),
            tags=set(data.get("tags", [])),
            simhash=data.get("simhash", ""),
        )
    
    def age_decay(self, current_time: float, half_life_hours: float = 24.0) -> float:
        """计算年龄衰减因子"""
        age_seconds = current_time - self.timestamp
        age_hours = age_seconds / 3600.0
        decay_factor = np.exp(-age_hours / half_life_hours)
        return decay_factor
    
    def relevance_score(self, current_time: float) -> float:
        """计算综合相关性分数"""
        age_factor = self.age_decay(current_time)
        access_factor = min(1.0, self.access_count / 10.0)
        recency_factor = self.age_decay(current_time, half_life_hours=1.0)
        
        return (
            self.importance * 0.4 +
            age_factor * 0.2 +
            access_factor * 0.2 +
            recency_factor * 0.2
        )


class SimHashDeduplicator:
    """SimHash 去重器"""
    
    def __init__(self, threshold: int = 3):
        self.threshold = threshold
        self._hashes: Dict[str, Set[str]] = {}  # 桶 -> 记忆ID集合
        self._memory_map: Dict[str, str] = {}  # 记忆ID -> simhash
    
    def add(self, memory_id: str, simhash: str) -> bool:
        """添加记忆，返回是否为新记忆（未重复）"""
        if memory_id in self._memory_map:
            return False
        
        for bucket in self._get_buckets(simhash):
            if bucket in self._hashes:
                for existing_id in self._hashes[bucket]:
                    existing_hash = self._memory_map[existing_id]
                    if self._hamming_distance(simhash, existing_hash) <= self.threshold:
                        return False
        
        for bucket in self._get_buckets(simhash):
            if bucket not in self._hashes:
                self._hashes[bucket] = set()
            self._hashes[bucket].add(memory_id)
        
        self._memory_map[memory_id] = simhash
        return True
    
    def remove(self, memory_id: str):
        """移除记忆"""
        if memory_id not in self._memory_map:
            return
        
        simhash = self._memory_map[memory_id]
        for bucket in self._get_buckets(simhash):
            if bucket in self._hashes and memory_id in self._hashes[bucket]:
                self._hashes[bucket].remove(memory_id)
                if not self._hashes[bucket]:
                    del self._hashes[bucket]
        
        del self._memory_map[memory_id]
    
    def find_duplicates(self, simhash: str) -> List[str]:
        """查找重复记忆的ID列表"""
        duplicates = []
        for bucket in self._get_buckets(simhash):
            if bucket in self._hashes:
                for existing_id in self._hashes[bucket]:
                    existing_hash = self._memory_map[existing_id]
                    if self._hamming_distance(simhash, existing_hash) <= self.threshold:
                        duplicates.append(existing_id)
        return duplicates
    
    def _get_buckets(self, simhash: str) -> List[str]:
        """获取分桶键"""
        if len(simhash) < 4:
            return [simhash]
        return [
            simhash[:4],
            simhash[4:8],
            simhash[8:12],
            simhash[12:],
        ]
    
    def _hamming_distance(self, hash1: str, hash2: str) -> int:
        """计算汉明距离"""
        distance = 0
        for c1, c2 in zip(hash1.ljust(16, '0'), hash2.ljust(16, '0')):
            if c1 != c2:
                distance += 1
        return distance


class ShortTermMemory:
    """短期记忆 - 最近对话，LRU 缓存"""
    
    def __init__(self, max_size: int = 50, ttl_seconds: int = 3600):
        self.max_size = max_size
        self.ttl_seconds = ttl_seconds
        self._memories: OrderedDict[str, MemoryItem] = OrderedDict()
        self._lock = threading.RLock()
    
    def add(self, memory: MemoryItem) -> bool:
        """添加记忆"""
        with self._lock:
            if memory.id in self._memories:
                self._memories.move_to_end(memory.id)
                return False
            
            if len(self._memories) >= self.max_size:
                self._evict_oldest()
            
            self._memories[memory.id] = memory
            self._memories.move_to_end(memory.id)
            return True
    
    def get(self, memory_id: str) -> Optional[MemoryItem]:
        """获取记忆"""
        with self._lock:
            if memory_id in self._memories:
                memory = self._memories[memory_id]
                self._update_access(memory)
                self._memories.move_to_end(memory_id)
                return memory
            return None
    
    def get_all(self, limit: Optional[int] = None) -> List[MemoryItem]:
        """获取所有记忆（按最近访问排序）"""
        with self._lock:
            current_time = time.time()
            self._cleanup_expired(current_time)
            
            memories = list(reversed(self._memories.values()))
            if limit:
                memories = memories[:limit]
            return memories
    
    def remove(self, memory_id: str) -> bool:
        """移除记忆"""
        with self._lock:
            if memory_id in self._memories:
                del self._memories[memory_id]
                return True
            return False
    
    def clear(self):
        """清空记忆"""
        with self._lock:
            self._memories.clear()
    
    def _evict_oldest(self):
        """逐出最早的记忆"""
        if self._memories:
            oldest_id = next(iter(self._memories))
            del self._memories[oldest_id]
    
    def _cleanup_expired(self, current_time: float):
        """清理过期记忆"""
        expired_ids = []
        for memory_id, memory in self._memories.items():
            if current_time - memory.timestamp > self.ttl_seconds:
                expired_ids.append(memory_id)
        
        for memory_id in expired_ids:
            del self._memories[memory_id]
    
    def _update_access(self, memory: MemoryItem):
        """更新访问信息"""
        memory.access_count += 1
        memory.last_access = time.time()


class LongTermMemory:
    """长期记忆 - 压缩摘要，持久存储"""
    
    def __init__(self, max_size: int = 1000):
        self.max_size = max_size
        self._memories: Dict[str, MemoryItem] = {}
        self._deduplicator = SimHashDeduplicator()
        self._lock = threading.RLock()
    
    def add(self, memory: MemoryItem) -> bool:
        """添加记忆"""
        with self._lock:
            if not self._deduplicator.add(memory.id, memory.simhash):
                return False
            
            if len(self._memories) >= self.max_size:
                self._evict_least_relevant()
            
            self._memories[memory.id] = memory
            return True
    
    def get(self, memory_id: str) -> Optional[MemoryItem]:
        """获取记忆"""
        with self._lock:
            if memory_id in self._memories:
                memory = self._memories[memory_id]
                self._update_access(memory)
                return memory
            return None
    
    def search(self, query: Optional[str] = None, 
               tags: Optional[Set[str]] = None,
               memory_type: Optional[MemoryType] = None,
               limit: int = 20) -> List[MemoryItem]:
        """搜索记忆"""
        with self._lock:
            current_time = time.time()
            memories = list(self._memories.values())
            
            if memory_type:
                memories = [m for m in memories if m.memory_type == memory_type]
            
            if tags:
                memories = [m for m in memories if m.tags & tags]
            
            memories.sort(key=lambda m: m.relevance_score(current_time), reverse=True)
            
            return memories[:limit]
    
    def remove(self, memory_id: str) -> bool:
        """移除记忆"""
        with self._lock:
            if memory_id in self._memories:
                self._deduplicator.remove(memory_id)
                del self._memories[memory_id]
                return True
            return False
    
    def get_all(self) -> List[MemoryItem]:
        """获取所有记忆"""
        with self._lock:
            return list(self._memories.values())
    
    def clear(self):
        """清空记忆"""
        with self._lock:
            self._memories.clear()
            self._deduplicator = SimHashDeduplicator()
    
    def compress(self, compress_ratio: float = 0.5) -> int:
        """压缩记忆（移除低相关性的）"""
        with self._lock:
            current_time = time.time()
            memories = sorted(
                self._memories.values(),
                key=lambda m: m.relevance_score(current_time)
            )
            
            remove_count = int(len(memories) * compress_ratio)
            for memory in memories[:remove_count]:
                self._deduplicator.remove(memory.id)
                del self._memories[memory.id]
            
            return remove_count
    
    def _evict_least_relevant(self):
        """逐出最不相关的记忆"""
        if not self._memories:
            return
        
        current_time = time.time()
        least_relevant = min(
            self._memories.values(),
            key=lambda m: m.relevance_score(current_time)
        )
        self._deduplicator.remove(least_relevant.id)
        del self._memories[least_relevant.id]
    
    def _update_access(self, memory: MemoryItem):
        """更新访问信息"""
        memory.access_count += 1
        memory.last_access = time.time()


class WorkingMemory:
    """工作记忆 - 当前激活的上下文"""
    
    def __init__(self, max_size: int = 20):
        self.max_size = max_size
        self._memories: List[MemoryItem] = []
        self._lock = threading.RLock()
    
    def add(self, memory: MemoryItem):
        """添加到工作记忆"""
        with self._lock:
            for i, existing in enumerate(self._memories):
                if existing.id == memory.id:
                    self._memories.pop(i)
                    break
            
            self._memories.append(memory)
            
            if len(self._memories) > self.max_size:
                self._memories.pop(0)
    
    def get_all(self) -> List[MemoryItem]:
        """获取所有工作记忆"""
        with self._lock:
            return list(self._memories)
    
    def clear(self):
        """清空工作记忆"""
        with self._lock:
            self._memories.clear()
    
    def remove(self, memory_id: str) -> bool:
        """移除特定记忆"""
        with self._lock:
            for i, memory in enumerate(self._memories):
                if memory.id == memory_id:
                    self._memories.pop(i)
                    return True
            return False


class EnhancedMemorySystem:
    """增强记忆系统 - 整合三层记忆架构"""
    
    def __init__(self, 
                 short_term_max: int = 50,
                 short_term_ttl: int = 3600,
                 long_term_max: int = 1000,
                 working_max: int = 20):
        self.short_term = ShortTermMemory(max_size=short_term_max, ttl_seconds=short_term_ttl)
        self.long_term = LongTermMemory(max_size=long_term_max)
        self.working = WorkingMemory(max_size=working_max)
        self._lock = threading.RLock()
        self._id_counter = 0
    
    def add_memory(self, 
                   content: str,
                   memory_type: MemoryType = MemoryType.EPISODIC,
                   importance: float = 0.5,
                   tags: Optional[Set[str]] = None,
                   metadata: Optional[Dict] = None,
                   embedding: Optional[List[float]] = None) -> str:
        """
        添加新记忆
        
        Args:
            content: 记忆内容
            memory_type: 记忆类型
            importance: 重要性 0.0-1.0
            tags: 标签集合
            metadata: 元数据
            embedding: 向量嵌入（可选）
        
        Returns:
            memory_id: 记忆ID
        """
        with self._lock:
            memory_id = self._generate_id()
            
            memory = MemoryItem(
                id=memory_id,
                content=content,
                memory_type=memory_type,
                importance=importance,
                tags=tags or set(),
                metadata=metadata or {},
                embedding=embedding,
            )
            
            self.short_term.add(memory)
            
            if importance >= 0.7:
                self.long_term.add(memory)
            
            logger.debug(f"Added memory: {memory_id}, type={memory_type.value}")
            return memory_id
    
    def get_memory(self, memory_id: str) -> Optional[MemoryItem]:
        """获取记忆"""
        memory = self.short_term.get(memory_id)
        if memory:
            return memory
        
        memory = self.long_term.get(memory_id)
        if memory:
            self.short_term.add(memory)
            return memory
        
        return None
    
    def retrieve_relevant(self, 
                         query: Optional[str] = None,
                         tags: Optional[Set[str]] = None,
                         limit: int = 10,
                         include_working: bool = True) -> List[MemoryItem]:
        """
        检索相关记忆
        
        Args:
            query: 查询文本（用于语义匹配）
            tags: 标签过滤
            limit: 返回数量限制
            include_working: 是否包含工作记忆
        
        Returns:
            相关记忆列表
        """
        with self._lock:
            current_time = time.time()
            results: List[Tuple[MemoryItem, float]] = []
            
            working_memories = self.working.get_all()
            short_memories = self.short_term.get_all()
            long_memories = self.long_term.search(query, tags, limit=limit)
            
            for memory in working_memories:
                if include_working:
                    score = memory.relevance_score(current_time) * 1.5
                    results.append((memory, score))
            
            for memory in short_memories:
                score = memory.relevance_score(current_time) * 1.2
                results.append((memory, score))
            
            for memory in long_memories:
                score = memory.relevance_score(current_time)
                results.append((memory, score))
            
            seen_ids = set()
            unique_results = []
            for memory, score in sorted(results, key=lambda x: x[1], reverse=True):
                if memory.id not in seen_ids:
                    seen_ids.add(memory.id)
                    unique_results.append(memory)
                    if len(unique_results) >= limit:
                        break
            
            return unique_results
    
    def activate_in_working(self, memory_id: str) -> bool:
        """激活记忆到工作记忆"""
        memory = self.get_memory(memory_id)
        if memory:
            self.working.add(memory)
            return True
        return False
    
    def consolidate_to_long_term(self, memory_id: Optional[str] = None) -> int:
        """
        将短期记忆巩固到长期记忆
        
        Args:
            memory_id: 特定记忆ID，None表示所有短期记忆
        
        Returns:
            巩固的记忆数量
        """
        with self._lock:
            count = 0
            
            if memory_id:
                memory = self.short_term.get(memory_id)
                if memory:
                    if self.long_term.add(memory):
                        count = 1
            else:
                for memory in self.short_term.get_all():
                    if self.long_term.add(memory):
                        count += 1
            
            logger.debug(f"Consolidated {count} memories to long-term")
            return count
    
    def summarize_memories(self, memory_ids: Optional[List[str]] = None) -> str:
        """
        生成记忆摘要
        
        Args:
            memory_ids: 要摘要的记忆ID列表，None表示所有
        
        Returns:
            摘要文本
        """
        if memory_ids:
            memories = [self.get_memory(mid) for mid in memory_ids if self.get_memory(mid)]
        else:
            memories = (
                self.short_term.get_all() + 
                self.long_term.get_all()
            )
        
        if not memories:
            return "No memories to summarize."
        
        contents = [m.content for m in memories[:50]]
        summary = self._generate_simple_summary(contents)
        return summary
    
    def _generate_simple_summary(self, contents: List[str]) -> str:
        """简单的摘要生成（可替换为LLM摘要）"""
        if len(contents) == 0:
            return "No content."
        
        if len(contents) == 1:
            return contents[0][:500]
        
        summary = f"Summary of {len(contents)} memories:\n"
        for i, content in enumerate(contents[:5]):
            preview = content[:100] + "..." if len(content) > 100 else content
            summary += f"{i+1}. {preview}\n"
        
        if len(contents) > 5:
            summary += f"... and {len(contents) - 5} more memories."
        
        return summary
    
    def compress_long_term(self, compress_ratio: float = 0.3) -> int:
        """压缩长期记忆"""
        return self.long_term.compress(compress_ratio)
    
    def clear_memory(self, memory_type: Optional[MemoryType] = None):
        """清空记忆"""
        if memory_type in (None, MemoryType.SHORT_TERM):
            self.short_term.clear()
        if memory_type in (None, MemoryType.LONG_TERM):
            self.long_term.clear()
        if memory_type in (None, MemoryType.WORKING):
            self.working.clear()
    
    def get_stats(self) -> Dict[str, Any]:
        """获取记忆统计"""
        return {
            "short_term_count": len(self.short_term.get_all()),
            "long_term_count": len(self.long_term.get_all()),
            "working_count": len(self.working.get_all()),
        }
    
    def _generate_id(self) -> str:
        """生成唯一记忆ID"""
        self._id_counter += 1
        timestamp = int(time.time() * 1000)
        return f"mem_{timestamp}_{self._id_counter}"


_global_enhanced_memory: Optional[EnhancedMemorySystem] = None


def get_enhanced_memory() -> EnhancedMemorySystem:
    """获取全局增强记忆实例"""
    global _global_enhanced_memory
    if _global_enhanced_memory is None:
        _global_enhanced_memory = EnhancedMemorySystem()
        logger.info("Enhanced memory system initialized")
    return _global_enhanced_memory


def reset_enhanced_memory():
    """重置增强记忆实例（用于测试）"""
    global _global_enhanced_memory
    _global_enhanced_memory = None
