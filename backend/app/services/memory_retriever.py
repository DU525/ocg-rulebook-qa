"""
记忆检索引擎 - Memory Retriever Engine

实现智能记忆检索功能：
- 语义检索 (Semantic Search)
- 时间排序 (Time-based Ranking)
- 重要性权重 (Importance Weighting)
- 记忆注入 (Memory Injection)
- 混合检索策略 (Hybrid Retrieval)
"""

import logging
import time
import re
from typing import Any, Dict, List, Optional, Set, Tuple, Callable
from dataclasses import dataclass
from enum import Enum
from collections import defaultdict

try:
    import numpy as np
    NUMPY_AVAILABLE = True
except ImportError:
    NUMPY_AVAILABLE = False

from .enhanced_memory import (
    EnhancedMemorySystem,
    MemoryItem,
    MemoryType,
    get_enhanced_memory,
)

logger = logging.getLogger(__name__)


class RetrievalStrategy(Enum):
    """检索策略枚举"""
    SEMANTIC = "semantic"
    TIME_RECENT = "time_recent"
    TIME_OLD = "time_old"
    IMPORTANCE = "importance"
    HYBRID = "hybrid"
    BM25 = "bm25"


@dataclass
class RetrievalResult:
    """检索结果项"""
    memory: MemoryItem
    score: float
    strategy: RetrievalStrategy
    explanation: str = ""
    
    def to_dict(self) -> Dict:
        return {
            "memory": self.memory.to_dict(),
            "score": self.score,
            "strategy": self.strategy.value,
            "explanation": self.explanation,
        }


class Tokenizer:
    """简单的中英文分词器"""
    
    def __init__(self):
        self.stop_words = {
            "的", "了", "在", "是", "我", "有", "和", "就", "不", "人", "都", "一",
            "一个", "上", "也", "很", "到", "说", "要", "去", "你", "会", "着", "没有",
            "看", "好", "自己", "这", "the", "a", "an", "and", "or", "but", "in", "on",
            "at", "to", "for", "of", "with", "by", "is", "was", "are", "were", "been",
            "be", "have", "has", "had", "do", "does", "did", "will", "would", "could",
            "should", "may", "might", "must", "shall", "can", "need", "dare", "ought",
        }
    
    def tokenize(self, text: str) -> List[str]:
        """分词"""
        text = text.lower()
        
        chinese_chars = re.findall(r'[\u4e00-\u9fff]', text)
        english_words = re.findall(r'[a-zA-Z]+', text)
        chinese_words = self._split_chinese(text)
        
        tokens = chinese_chars + english_words + chinese_words
        
        tokens = [t for t in tokens if t not in self.stop_words and len(t) > 0]
        
        return tokens
    
    def _split_chinese(self, text: str) -> List[str]:
        """简单的中文 n-gram 分词"""
        chars = [c for c in text if '\u4e00' <= c <= '\u9fff']
        grams = []
        
        if len(chars) >= 2:
            grams.extend([''.join(chars[i:i+2]) for i in range(len(chars)-1)])
        
        if len(chars) >= 3:
            grams.extend([''.join(chars[i:i+3]) for i in range(len(chars)-2)])
        
        return grams


class BM25Engine:
    """BM25 检索引擎"""
    
    def __init__(self, k1: float = 1.5, b: float = 0.75):
        self.k1 = k1
        self.b = b
        self.tokenizer = Tokenizer()
        self._doc_len: Dict[str, int] = {}
        self._avg_doc_len: float = 0.0
        self._term_freq: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
        self._doc_freq: Dict[str, int] = defaultdict(int)
        self._total_docs: int = 0
        self._memory_map: Dict[str, MemoryItem] = {}
    
    def add_document(self, memory_id: str, memory: MemoryItem):
        """添加文档"""
        tokens = self.tokenizer.tokenize(memory.content)
        doc_len = len(tokens)
        
        self._doc_len[memory_id] = doc_len
        self._memory_map[memory_id] = memory
        
        term_count = defaultdict(int)
        for token in tokens:
            term_count[token] += 1
        
        for token, count in term_count.items():
            self._term_freq[memory_id][token] = count
        
        for token in term_count.keys():
            self._doc_freq[token] += 1
        
        self._total_docs += 1
        
        total_len = sum(self._doc_len.values())
        self._avg_doc_len = total_len / self._total_docs if self._total_docs > 0 else 0
    
    def remove_document(self, memory_id: str):
        """移除文档"""
        if memory_id not in self._doc_len:
            return
        
        doc_len = self._doc_len[memory_id]
        
        for token, count in list(self._term_freq[memory_id].items()):
            self._doc_freq[token] -= 1
            if self._doc_freq[token] <= 0:
                del self._doc_freq[token]
        
        del self._term_freq[memory_id]
        del self._doc_len[memory_id]
        del self._memory_map[memory_id]
        
        self._total_docs -= 1
        
        if self._total_docs > 0:
            total_len = sum(self._doc_len.values())
            self._avg_doc_len = total_len / self._total_docs
        else:
            self._avg_doc_len = 0
    
    def search(self, query: str, limit: int = 20) -> List[Tuple[str, float]]:
        """BM25 搜索"""
        if self._total_docs == 0:
            return []
        
        query_tokens = self.tokenizer.tokenize(query)
        if not query_tokens:
            return []
        
        scores = defaultdict(float)
        
        for token in query_tokens:
            if token not in self._doc_freq:
                continue
            
            df = self._doc_freq[token]
            idf = np.log((self._total_docs - df + 0.5) / (df + 0.5) + 1) if NUMPY_AVAILABLE else 1.0
            
            for doc_id, term_freq in self._term_freq.items():
                if token not in term_freq:
                    continue
                
                tf = term_freq[token]
                doc_len = self._doc_len[doc_id]
                
                numerator = tf * (self.k1 + 1)
                denominator = tf + self.k1 * (1 - self.b + self.b * doc_len / max(self._avg_doc_len, 1))
                
                score = idf * (numerator / denominator)
                scores[doc_id] += score
        
        sorted_docs = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_docs[:limit]


class SemanticSearcher:
    """语义搜索器（基于向量余弦相似度）"""
    
    def __init__(self):
        self._embeddings: Dict[str, List[float]] = {}
        self._memory_map: Dict[str, MemoryItem] = {}
    
    def add_memory(self, memory_id: str, memory: MemoryItem):
        """添加记忆（如果有嵌入向量）"""
        if memory.embedding is not None:
            self._embeddings[memory_id] = memory.embedding
            self._memory_map[memory_id] = memory
    
    def remove_memory(self, memory_id: str):
        """移除记忆"""
        if memory_id in self._embeddings:
            del self._embeddings[memory_id]
        if memory_id in self._memory_map:
            del self._memory_map[memory_id]
    
    def search(self, query_embedding: List[float], limit: int = 20) -> List[Tuple[str, float]]:
        """语义搜索"""
        if not self._embeddings or not NUMPY_AVAILABLE:
            return []
        
        scores = []
        query_vec = np.array(query_embedding)
        
        for memory_id, embedding in self._embeddings.items():
            embedding_vec = np.array(embedding)
            similarity = self._cosine_similarity(query_vec, embedding_vec)
            scores.append((memory_id, similarity))
        
        scores.sort(key=lambda x: x[1], reverse=True)
        return scores[:limit]
    
    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """计算余弦相似度"""
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        
        if norm1 == 0 or norm2 == 0:
            return 0.0
        
        return dot_product / (norm1 * norm2)


class MemoryRetriever:
    """记忆检索引擎"""
    
    def __init__(self, memory_system: Optional[EnhancedMemorySystem] = None):
        self.memory_system = memory_system or get_enhanced_memory()
        self.bm25_engine = BM25Engine()
        self.semantic_searcher = SemanticSearcher()
        self._indexed_memory_ids: Set[str] = set()
        self._default_strategy = RetrievalStrategy.HYBRID
        
        self._strategy_weights = {
            RetrievalStrategy.SEMANTIC: 0.4,
            RetrievalStrategy.BM25: 0.3,
            RetrievalStrategy.TIME_RECENT: 0.15,
            RetrievalStrategy.IMPORTANCE: 0.15,
        }
        
        self._injected_memories: List[MemoryItem] = []
    
    def index_memory(self, memory: MemoryItem):
        """索引单个记忆"""
        if memory.id in self._indexed_memory_ids:
            return
        
        self.bm25_engine.add_document(memory.id, memory)
        self.semantic_searcher.add_memory(memory.id, memory)
        self._indexed_memory_ids.add(memory.id)
    
    def index_all_memories(self):
        """索引所有现有记忆"""
        all_memories = (
            self.memory_system.short_term.get_all() +
            self.memory_system.long_term.get_all()
        )
        
        for memory in all_memories:
            self.index_memory(memory)
        
        logger.info(f"Indexed {len(all_memories)} memories")
    
    def remove_from_index(self, memory_id: str):
        """从索引中移除"""
        self.bm25_engine.remove_document(memory_id)
        self.semantic_searcher.remove_memory(memory_id)
        if memory_id in self._indexed_memory_ids:
            self._indexed_memory_ids.remove(memory_id)
    
    def retrieve(self,
                query: Optional[str] = None,
                query_embedding: Optional[List[float]] = None,
                strategy: Optional[RetrievalStrategy] = None,
                tags: Optional[Set[str]] = None,
                memory_type: Optional[MemoryType] = None,
                limit: int = 10,
                include_injected: bool = True) -> List[RetrievalResult]:
        """
        检索记忆
        
        Args:
            query: 文本查询
            query_embedding: 查询向量嵌入
            strategy: 检索策略
            tags: 标签过滤
            memory_type: 记忆类型过滤
            limit: 返回数量限制
            include_injected: 是否包含注入的记忆
        
        Returns:
            检索结果列表
        """
        strategy = strategy or self._default_strategy
        current_time = time.time()
        
        candidate_memories = self._get_candidates(tags, memory_type)
        
        if not candidate_memories:
            return []
        
        results: List[RetrievalResult] = []
        
        if strategy == RetrievalStrategy.HYBRID:
            results = self._hybrid_retrieve(
                candidate_memories, query, query_embedding, current_time, limit
            )
        elif strategy == RetrievalStrategy.SEMANTIC:
            results = self._semantic_retrieve(
                candidate_memories, query_embedding, current_time, limit
            )
        elif strategy == RetrievalStrategy.BM25:
            results = self._bm25_retrieve(
                candidate_memories, query, current_time, limit
            )
        elif strategy == RetrievalStrategy.TIME_RECENT:
            results = self._time_retrieve(
                candidate_memories, current_time, newest_first=True, limit=limit
            )
        elif strategy == RetrievalStrategy.TIME_OLD:
            results = self._time_retrieve(
                candidate_memories, current_time, newest_first=False, limit=limit
            )
        elif strategy == RetrievalStrategy.IMPORTANCE:
            results = self._importance_retrieve(
                candidate_memories, current_time, limit
            )
        
        if include_injected and self._injected_memories:
            results = self._merge_injected_memories(results)
        
        return results[:limit]
    
    def _get_candidates(self,
                       tags: Optional[Set[str]] = None,
                       memory_type: Optional[MemoryType] = None) -> List[MemoryItem]:
        """获取候选记忆"""
        candidates = (
            self.memory_system.working.get_all() +
            self.memory_system.short_term.get_all() +
            self.memory_system.long_term.get_all()
        )
        
        if memory_type:
            candidates = [m for m in candidates if m.memory_type == memory_type]
        
        if tags:
            candidates = [m for m in candidates if m.tags & tags]
        
        seen_ids = set()
        unique_candidates = []
        for memory in candidates:
            if memory.id not in seen_ids:
                seen_ids.add(memory.id)
                unique_candidates.append(memory)
        
        return unique_candidates
    
    def _hybrid_retrieve(self,
                        candidates: List[MemoryItem],
                        query: Optional[str],
                        query_embedding: Optional[List[float]],
                        current_time: float,
                        limit: int) -> List[RetrievalResult]:
        """混合检索"""
        candidate_ids = {m.id for m in candidates}
        memory_map = {m.id: m for m in candidates}
        
        scores = defaultdict(float)
        
        if query and len(candidate_ids) > 0:
            bm25_results = self.bm25_engine.search(query, limit=limit*2)
            for doc_id, score in bm25_results:
                if doc_id in candidate_ids:
                    normalized_score = min(score / 10.0, 1.0)
                    scores[doc_id] += normalized_score * self._strategy_weights[RetrievalStrategy.BM25]
        
        if query_embedding and len(candidate_ids) > 0:
            semantic_results = self.semantic_searcher.search(query_embedding, limit=limit*2)
            for doc_id, similarity in semantic_results:
                if doc_id in candidate_ids:
                    scores[doc_id] += similarity * self._strategy_weights[RetrievalStrategy.SEMANTIC]
        
        for memory in candidates:
            time_score = memory.age_decay(current_time, half_life_hours=6.0)
            scores[memory.id] += time_score * self._strategy_weights[RetrievalStrategy.TIME_RECENT]
            
            imp_score = memory.importance
            scores[memory.id] += imp_score * self._strategy_weights[RetrievalStrategy.IMPORTANCE]
        
        sorted_ids = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        
        results = []
        for memory_id, score in sorted_ids[:limit]:
            if memory_id in memory_map:
                results.append(RetrievalResult(
                    memory=memory_map[memory_id],
                    score=score,
                    strategy=RetrievalStrategy.HYBRID,
                    explanation="Hybrid score combining semantic, BM25, time, and importance",
                ))
        
        return results
    
    def _semantic_retrieve(self,
                          candidates: List[MemoryItem],
                          query_embedding: Optional[List[float]],
                          current_time: float,
                          limit: int) -> List[RetrievalResult]:
        """语义检索"""
        candidate_ids = {m.id for m in candidates}
        memory_map = {m.id: m for m in candidates}
        
        if query_embedding:
            semantic_results = self.semantic_searcher.search(query_embedding, limit=limit*2)
        else:
            semantic_results = []
        
        results = []
        
        for doc_id, similarity in semantic_results:
            if doc_id in memory_map:
                memory = memory_map[doc_id]
                time_boost = memory.age_decay(current_time, half_life_hours=24.0)
                final_score = similarity * 0.8 + time_boost * 0.2
                
                results.append(RetrievalResult(
                    memory=memory,
                    score=final_score,
                    strategy=RetrievalStrategy.SEMANTIC,
                    explanation=f"Semantic similarity: {similarity:.3f}",
                ))
        
        if not results:
            results = self._time_retrieve(candidates, current_time, True, limit)
        
        return results[:limit]
    
    def _bm25_retrieve(self,
                      candidates: List[MemoryItem],
                      query: Optional[str],
                      current_time: float,
                      limit: int) -> List[RetrievalResult]:
        """BM25检索"""
        candidate_ids = {m.id for m in candidates}
        memory_map = {m.id: m for m in candidates}
        
        if query:
            bm25_results = self.bm25_engine.search(query, limit=limit*2)
        else:
            bm25_results = []
        
        results = []
        
        for doc_id, score in bm25_results:
            if doc_id in memory_map:
                memory = memory_map[doc_id]
                time_boost = memory.age_decay(current_time, half_life_hours=24.0)
                normalized_score = min(score / 10.0, 1.0)
                final_score = normalized_score * 0.8 + time_boost * 0.2
                
                results.append(RetrievalResult(
                    memory=memory,
                    score=final_score,
                    strategy=RetrievalStrategy.BM25,
                    explanation=f"BM25 score: {score:.3f}",
                ))
        
        if not results:
            results = self._time_retrieve(candidates, current_time, True, limit)
        
        return results[:limit]
    
    def _time_retrieve(self,
                      candidates: List[MemoryItem],
                      current_time: float,
                      newest_first: bool,
                      limit: int) -> List[RetrievalResult]:
        """时间排序检索"""
        sorted_memories = sorted(
            candidates,
            key=lambda m: m.timestamp,
            reverse=newest_first
        )
        
        results = []
        for memory in sorted_memories[:limit]:
            age_hours = (current_time - memory.timestamp) / 3600.0
            time_score = memory.age_decay(current_time)
            
            results.append(RetrievalResult(
                memory=memory,
                score=time_score,
                strategy=RetrievalStrategy.TIME_RECENT if newest_first else RetrievalStrategy.TIME_OLD,
                explanation=f"Age: {age_hours:.1f} hours",
            ))
        
        return results
    
    def _importance_retrieve(self,
                            candidates: List[MemoryItem],
                            current_time: float,
                            limit: int) -> List[RetrievalResult]:
        """重要性权重检索"""
        sorted_memories = sorted(
            candidates,
            key=lambda m: m.relevance_score(current_time),
            reverse=True
        )
        
        results = []
        for memory in sorted_memories[:limit]:
            score = memory.relevance_score(current_time)
            
            results.append(RetrievalResult(
                memory=memory,
                score=score,
                strategy=RetrievalStrategy.IMPORTANCE,
                explanation=f"Importance: {memory.importance:.2f}, Access: {memory.access_count}",
            ))
        
        return results
    
    def _merge_injected_memories(self, results: List[RetrievalResult]) -> List[RetrievalResult]:
        """合并注入的记忆"""
        injected_results = [
            RetrievalResult(
                memory=memory,
                score=1.0,
                strategy=RetrievalStrategy.HYBRID,
                explanation="Injected memory (high priority)",
            )
            for memory in self._injected_memories
        ]
        
        existing_ids = {r.memory.id for r in results}
        filtered_injected = [r for r in injected_results if r.memory.id not in existing_ids]
        
        return filtered_injected + results
    
    def inject_memory(self, memory: MemoryItem, priority: float = 1.0):
        """
        注入记忆（高优先级）
        
        Args:
            memory: 要注入的记忆
            priority: 优先级权重
        """
        memory.importance = max(memory.importance, priority)
        self._injected_memories.append(memory)
        logger.debug(f"Injected memory: {memory.id} with priority {priority}")
    
    def clear_injected(self):
        """清空注入的记忆"""
        self._injected_memories.clear()
    
    def set_strategy_weights(self, weights: Dict[RetrievalStrategy, float]):
        """设置混合策略权重"""
        total = sum(weights.values())
        if total > 0:
            self._strategy_weights = {
                s: w / total for s, w in weights.items()
            }
        logger.info(f"Updated strategy weights: {self._strategy_weights}")
    
    def get_retrieval_context(self,
                             query: Optional[str] = None,
                             query_embedding: Optional[List[float]] = None,
                             limit: int = 5) -> str:
        """
        获取用于提示词的记忆上下文
        
        Args:
            query: 查询文本
            query_embedding: 查询向量
            limit: 记忆数量
        
        Returns:
            格式化的上下文字符串
        """
        results = self.retrieve(query, query_embedding, limit=limit)
        
        if not results:
            return "No relevant memories found."
        
        context_parts = []
        for i, result in enumerate(results, 1):
            memory = result.memory
            context_parts.append(
                f"[Memory {i}] (Score: {result.score:.3f})\n"
                f"Content: {memory.content}\n"
                f"Type: {memory.memory_type.value}\n"
                f"Importance: {memory.importance:.2f}"
            )
        
        return "\n\n".join(context_parts)


_global_retriever: Optional[MemoryRetriever] = None


def get_memory_retriever(memory_system: Optional[EnhancedMemorySystem] = None) -> MemoryRetriever:
    """获取全局记忆检索器实例"""
    global _global_retriever
    if _global_retriever is None:
        _global_retriever = MemoryRetriever(memory_system)
        _global_retriever.index_all_memories()
        logger.info("Memory retriever initialized")
    return _global_retriever


def reset_memory_retriever():
    """重置记忆检索器（用于测试）"""
    global _global_retriever
    _global_retriever = None
