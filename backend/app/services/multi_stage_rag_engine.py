"""多阶段RAG引擎 - 生产级完整Pipeline

整合：
1. 意图分类（QueryClassifier）
2. BM25关键词检索
3. 向量检索（FAISS HNSW）
4. RRF融合排序（Reciprocal Rank Fusion）
5. Cross-Encoder精排

这是生产环境的完整检索链路，替代原来的纯FAISS检索。
"""

from typing import List, Dict, Any, Optional
from dataclasses import dataclass
import logging

logger = logging.getLogger(__name__)


@dataclass
class MultiStageRetrievalResult:
    """多阶段检索结果"""
    content: str
    source: str
    chapter: str
    section: str
    similarity: float
    rrf_score: float = 0.0
    cross_encoder_score: float = 0.0
    vector_rank: int = 0
    bm25_rank: int = 0
    source_type: str = 'vector'  # 'vector', 'bm25', 'both'


class MultiStageRAGEngine:
    """多阶段RAG检索引擎
    
    检索流程：
    1. 意图分类 → 确定查询类型
    2. 双路检索 → BM25 + 向量检索
    3. RRF融合 → 合并两路结果
    4. Cross-Encoder精排 → 提高Top结果准确性
    """

    def __init__(
        self,
        vector_store: Any,
        bm25_engine: Any = None,
        cross_encoder_reranker: Any = None,
        top_k: int = 5,
        bm25_top_k: int = 50,
        vector_top_k: int = 50,
        rerank_top_n: int = 10,
    ):
        """初始化多阶段RAG引擎
        
        Args:
            vector_store: FAISS向量存储
            bm25_engine: BM25检索引擎
            cross_encoder_reranker: Cross-Encoder精排器
            top_k: 最终返回结果数量
            bm25_top_k: BM25检索返回数量
            vector_top_k: 向量检索返回数量
            rerank_top_n: Cross-Encoder精排候选数量
        """
        self.vector_store = vector_store
        self.bm25_engine = bm25_engine
        self.cross_encoder_reranker = cross_encoder_reranker
        self.top_k = top_k
        self.bm25_top_k = bm25_top_k
        self.vector_top_k = vector_top_k
        self.rerank_top_n = rerank_top_n
        
        logger.info(
            f"多阶段RAG引擎初始化: top_k={top_k}, "
            f"bm25_top_k={bm25_top_k}, vector_top_k={vector_top_k}, "
            f"rerank_top_n={rerank_top_n}"
        )

    def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        use_multi_stage: bool = True,
        vector_weight: Optional[float] = None,
        bm25_weight: Optional[float] = None,
    ) -> List[MultiStageRetrievalResult]:
        """执行多阶段检索
        
        Args:
            query: 用户查询
            top_k: 返回结果数量
            use_multi_stage: 是否使用多阶段检索
            vector_weight: 向量检索权重（可选，自动分类）
            bm25_weight: BM25权重（可选，自动分类）
            
        Returns:
            List[MultiStageRetrievalResult]: 检索结果列表
        """
        if not use_multi_stage or self.bm25_engine is None:
            # 降级：仅使用向量检索
            return self._vector_only_retrieve(query, top_k or self.top_k)
        
        # 1. 意图分类
        from app.services.rrf_fusion import QueryClassifier
        query_type, auto_weights = QueryClassifier.classify(query)
        
        if vector_weight is None:
            vector_weight = auto_weights['vector_weight']
        if bm25_weight is None:
            bm25_weight = auto_weights['bm25_weight']
        
        logger.info(
            f"[多阶段检索] query='{query[:30]}...', "
            f"type={query_type}, "
            f"weights=(vector={vector_weight}, bm25={bm25_weight})"
        )
        
        # 2. 双路检索
        effective_top_k = top_k or self.top_k
        
        # 向量检索
        try:
            vector_results = self.vector_store.search(
                query, n_results=self.vector_top_k
            )
            logger.info(f"[向量检索] found={len(vector_results)} results")
        except Exception as e:
            logger.error(f"向量检索失败: {e}")
            vector_results = []
        
        # BM25检索
        try:
            bm25_results = self.bm25_engine.search(
                query, top_k=self.bm25_top_k
            )
            logger.info(f"[BM25检索] found={len(bm25_results)} results")
        except Exception as e:
            logger.error(f"BM25检索失败: {e}")
            bm25_results = []
        
        # 3. RRF融合
        try:
            from app.services.rrf_fusion import reciprocal_rank_fusion
            
            fusion_results = reciprocal_rank_fusion(
                vector_results=vector_results,
                bm25_results=bm25_results,
                top_k=self.rerank_top_n,
                vector_weight=vector_weight,
                bm25_weight=bm25_weight,
            )
            logger.info(f"[RRF融合] fusion_results={len(fusion_results)}")
        except Exception as e:
            logger.error(f"RRF融合失败: {e}")
            fusion_results = vector_results[:self.rerank_top_n]
        
        # 4. Cross-Encoder精排
        try:
            if self.cross_encoder_reranker and len(fusion_results) > effective_top_k:
                final_results = self.cross_encoder_reranker.rerank(
                    query=query,
                    documents=fusion_results,
                    top_k=effective_top_k,
                )
                logger.info(f"[Cross-Encoder精排] top_k={effective_top_k}")
            else:
                final_results = fusion_results[:effective_top_k]
        except Exception as e:
            logger.error(f"Cross-Encoder精排失败: {e}")
            final_results = fusion_results[:effective_top_k]
        
        # 5. 转换为统一格式
        return self._format_results(final_results)

    def _vector_only_retrieve(
        self, query: str, top_k: int
    ) -> List[MultiStageRetrievalResult]:
        """仅使用向量检索（降级方案）"""
        results = self.vector_store.search(query, n_results=top_k)
        
        retrieval_results = []
        for result in results:
            similarity = 1 - result.get('distance', 0)
            metadata = result.get('metadata', {})
            retrieval_results.append(MultiStageRetrievalResult(
                content=result.get('content', ''),
                source=metadata.get('source', 'unknown'),
                chapter=metadata.get('chapter', ''),
                section=metadata.get('section', ''),
                similarity=similarity,
                source_type='vector'
            ))
        
        return retrieval_results

    def _format_results(
        self, results: List[Dict[str, Any]]
    ) -> List[MultiStageRetrievalResult]:
        """将检索结果转换为统一格式"""
        retrieval_results = []
        
        for result in results:
            metadata = result.get('metadata', {})
            
            # 计算综合相似度
            similarity = result.get('score', 0)
            rrf_score = result.get('rrf_score', 0)
            cross_encoder_score = result.get('cross_encoder_score', 0)
            
            # 如果有Cross-Encoder分数，优先使用
            if cross_encoder_score > 0:
                similarity = cross_encoder_score
            
            retrieval_results.append(MultiStageRetrievalResult(
                content=result.get('content', ''),
                source=metadata.get('source', 'unknown'),
                chapter=metadata.get('chapter', ''),
                section=metadata.get('section', ''),
                similarity=similarity,
                rrf_score=rrf_score,
                cross_encoder_score=cross_encoder_score,
                vector_rank=result.get('vector_rank', 0),
                bm25_rank=result.get('bm25_rank', 0),
                source_type=result.get('source', 'vector')
            ))
        
        return retrieval_results
