"""
混合检索优化器 - 优化点2的前2个细分方向
预计提升：20-30% | 时间成本：2-3小时

实现：
1. BM25+向量混合检索权重调优
2. 跨知识库检索增强
"""
import time
from typing import List, Dict, Any, Tuple, Optional
from dataclasses import dataclass
from app.services.query_optimizer import get_query_optimizer


@dataclass
class RetrievalResult:
    """检索结果"""
    content: str
    score: float
    source: str
    metadata: Dict[str, Any]


@dataclass
class HybridSearchConfig:
    """混合搜索配置"""
    bm25_weight: float = 0.4
    vector_weight: float = 0.6
    enable_rrf: bool = True
    rrf_k: int = 60
    cross_db_search: bool = True
    max_results: int = 10


class HybridRetriever:
    """
    混合检索优化器
    实现优化点2的前2个细分方向
    """

    def __init__(self, config: Optional[HybridSearchConfig] = None):
        self.config = config or HybridSearchConfig()
        self.query_optimizer = get_query_optimizer()

    def hybrid_search(
        self,
        query: str,
        vector_rag,
        bm25_rag=None,
        dm_rag=None
    ) -> List[RetrievalResult]:
        """
        混合搜索入口
        
        Args:
            query: 查询文本
            vector_rag: 向量检索器
            bm25_rag: BM25检索器（可选）
            dm_rag: DM知识库检索器（可选）
            
        Returns:
            混合排序后的检索结果
        """
        # 1. 查询优化
        optimized_queries = self.query_optimizer.get_retrieval_queries(query)
        best_query = self.query_optimizer.get_best_query_for_retrieval(query)
        
        # 2. 多源检索
        all_results = []
        
        # 向量检索
        if vector_rag:
            vector_results = self._search_with_query_list(
                optimized_queries, vector_rag, 'vector'
            )
            all_results.extend(vector_results)
        
        # BM25检索（如果有）
        if bm25_rag:
            bm25_results = self._search_with_query_list(
                optimized_queries, bm25_rag, 'bm25'
            )
            all_results.extend(bm25_results)
        
        # 跨知识库检索
        if self.config.cross_db_search and dm_rag:
            dm_results = self._search_with_query_list(
                optimized_queries, dm_rag, 'dm'
            )
            all_results.extend(dm_results)
        
        # 3. 混合排序
        if all_results:
            sorted_results = self._fuse_results(all_results)
            return sorted_results[:self.config.max_results]
        
        return []

    def _search_with_query_list(
        self,
        queries: List[str],
        rag,
        source: str
    ) -> List[RetrievalResult]:
        """
        使用多个查询进行搜索并合并结果
        """
        results = []
        
        for q in queries[:3]:  # 最多使用前3个查询
            try:
                search_results = rag.search(q, top_k=5)
                
                for i, result in enumerate(search_results):
                    content = result.get('content', '') if isinstance(result, dict) else str(result)
                    score = result.get('score', 1.0 - i*0.1) if isinstance(result, dict) else 1.0 - i*0.1
                    metadata = result.get('metadata', {}) if isinstance(result, dict) else {}
                    
                    results.append(RetrievalResult(
                        content=content,
                        score=score,
                        source=source,
                        metadata=metadata
                    ))
            except Exception:
                continue
        
        return results

    def _fuse_results(self, results: List[RetrievalResult]) -> List[RetrievalResult]:
        """
        融合排序结果
        
        根据配置使用：
        - 加权融合
        - RRF融合
        """
        if self.config.enable_rrf:
            return self._rrf_fusion(results)
        else:
            return self._weighted_fusion(results)

    def _rrf_fusion(self, results: List[RetrievalResult]) -> List[RetrievalResult]:
        """
        Reciprocal Rank Fusion 算法
        
        细分方向1：混合检索权重调优（通过RRF）
        """
        # 首先对结果进行分组
        content_groups = {}
        for result in results:
            content_key = result.content[:100]  # 使用前100字符作为key去重
            if content_key not in content_groups:
                content_groups[content_key] = []
            content_groups[content_key].append(result)
        
        # 计算RRF分数
        fused_results = []
        for content_key, group in content_groups.items():
            # 取该组分数最高的结果
            best_result = max(group, key=lambda x: x.score)
            
            # 计算RRF分数
            rrf_score = 0.0
            for i, result in enumerate(sorted(group, key=lambda x: x.score, reverse=True)):
                rrf_score += 1.0 / (self.config.rrf_k + i)
            
            best_result.score = rrf_score
            fused_results.append(best_result)
        
        # 按RRF分数排序
        return sorted(fused_results, key=lambda x: x.score, reverse=True)

    def _weighted_fusion(self, results: List[RetrievalResult]) -> List[RetrievalResult]:
        """
        加权融合算法
        
        细分方向1：混合检索权重调优（通过配置的权重）
        """
        # 先按内容分组
        content_groups = {}
        for result in results:
            content_key = result.content[:100]
            if content_key not in content_groups:
                content_groups[content_key] = []
            content_groups[content_key].append(result)
        
        # 计算加权分数
        fused_results = []
        for content_key, group in content_groups.items():
            best_result = max(group, key=lambda x: x.score)
            
            # 根据来源应用权重
            weighted_score = 0.0
            for result in group:
                if result.source == 'bm25':
                    weighted_score += result.score * self.config.bm25_weight
                elif result.source == 'vector':
                    weighted_score += result.score * self.config.vector_weight
                elif result.source == 'dm':
                    weighted_score += result.score * 0.5  # DM知识库较低权重
            
            best_result.score = weighted_score
            fused_results.append(best_result)
        
        return sorted(fused_results, key=lambda x: x.score, reverse=True)

    def dynamic_weight_adjustment(
        self,
        query: str,
        performance_history: List[Dict[str, float]]
    ) -> HybridSearchConfig:
        """
        动态权重调整
        
        根据历史性能自动调整BM25和向量权重
        """
        if not performance_history:
            return self.config
        
        # 分析历史表现
        recent_history = performance_history[-10:]
        
        # 简单策略：根据哪类检索效果更好调整权重
        vector_success = sum(1 for h in recent_history if h.get('vector_better', False))
        bm25_success = sum(1 for h in recent_history if h.get('bm25_better', False))
        
        total = vector_success + bm25_success
        if total > 0:
            # 动态调整权重
            vector_ratio = vector_success / total
            bm25_ratio = bm25_success / total
            
            # 归一化
            total_ratio = vector_ratio + bm25_ratio
            if total_ratio > 0:
                new_vector_weight = vector_ratio / total_ratio
                new_bm25_weight = bm25_ratio / total
                
                # 确保权重在合理范围内
                new_vector_weight = max(0.3, min(0.7, new_vector_weight))
                new_bm25_weight = 1.0 - new_vector_weight
                
                return HybridSearchConfig(
                    bm25_weight=new_bm25_weight,
                    vector_weight=new_vector_weight,
                    enable_rrf=self.config.enable_rrf,
                    cross_db_search=self.config.cross_db_search
                )
        
        return self.config


# 全局实例
_hybrid_retriever = None

def get_hybrid_retriever(config: Optional[HybridSearchConfig] = None) -> HybridRetriever:
    """获取混合检索器单例"""
    global _hybrid_retriever
    if _hybrid_retriever is None:
        _hybrid_retriever = HybridRetriever(config)
    return _hybrid_retriever
