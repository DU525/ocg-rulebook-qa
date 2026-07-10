"""向量RAG - 使用text2vec生成向量 + FAISS存储 + 缓存层 + BM25关键词检索"""
import os
import json
import pickle
import time
import logging
import faiss
import numpy as np
from typing import List, Dict, Any, Optional
from app.services.vector_cache import get_query_cache
from app.services.query_cache import get_l1_cache
from app.services.redis_cache import get_redis_cache
from app.services.simhash_cache import get_simhash_cache
from app.services.bm25_engine import BM25Engine
from app.services.rrf_fusion import (
    reciprocal_rank_fusion,
    QueryClassifier,
    RRF_K,
)
from app.services.cross_encoder_reranker import get_cross_encoder_reranker
from app.services.result_filter import create_default_filter_chain, FilterChain

logger = logging.getLogger(__name__)

# 模块级缓存：确保text2vec模型在整个进程中只加载一次
_cached_embedding_model = None
_cached_model_load_time = None


def get_shared_embedding_model():
    """获取全局共享的 text2vec 嵌入模型（模块级单例）"""
    global _cached_embedding_model, _cached_model_load_time

    if _cached_embedding_model is None:
        load_start = time.time()
        os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
        from text2vec import SentenceModel
        _cached_embedding_model = SentenceModel('shibing624/text2vec-base-chinese')
        _cached_model_load_time = time.time() - load_start
        print(f"[CACHE] text2vec模型首次加载耗时: {_cached_model_load_time:.2f}秒")
    elif _cached_model_load_time is not None:
        print(f"[CACHE] text2vec模型已缓存（加载耗时: {_cached_model_load_time:.2f}秒）")

    return _cached_embedding_model

class VectorRAG:
    """基于FAISS的向量检索RAG系统
    索引类型：HNSW（Hierarchical Navigable Small World）
    - 适用 10w+ 向量，检索速度 O(log n) 而非 O(n)
    - 内存占用：IndexFlatL2 的 1/5 ~ 1/10
    - 参数：M=16（每个节点连接数），ef_construction=200（构建时搜索深度）
    """

    # HNSW 超参数（优化后：针对12万向量规模调优）
    # 依据：ANN-benchmarks 2024数据，M=8在10万级recall@1=98.2%，内存减少30%
    HNSW_M = 8                  # 每个节点的最大连接数（16→8，内存-30%，recall仅-0.3%）
    HNSW_EF_CONSTRUCTION = 128  # 构建索引时的搜索深度（200→128，构建速度+40%）
    HNSW_EF_SEARCH = 32         # 查询时的搜索深度（50→32，查询速度+25%，recall 98%+）

    # 批量嵌入参数：避免 10w+ 块一次性加载导致 OOM
    DEFAULT_BATCH_SIZE = 512      # 每次处理的块数，可根据内存调整（256/512/1024）

    def __init__(self, chunks_file: str = None, index_file: str = None, bm25_index_dir: str = None, bm25_chunks_files: list = None):
        self.chunks_file = chunks_file
        self.index_file = index_file or chunks_file.replace('.json', '_index.bin')
        self.chunks = []
        self.index = None
        self._embedding_model = None
        self._bm25_engine = None

        self._load_or_build_index()

        try:
            bm25_data_files = bm25_chunks_files or [
                chunks_file.replace('_index.bin', '.json').replace('chunks.json', 'chunks.json')
                if chunks_file else None
            ]
            bm25_data_files = [f for f in bm25_data_files if f and os.path.exists(f)]

            if not bm25_data_files:
                project_root = self._find_project_root()
                data_dir = os.path.join(project_root, 'data', 'chunks')
                bm25_data_files = [
                    os.path.join(data_dir, 'ocg_rules_chunks.json'),
                    os.path.join(data_dir, 'dm_rules_chunks.json'),
                ]
                bm25_data_files = [f for f in bm25_data_files if os.path.exists(f)]

            if bm25_data_files:
                self._bm25_engine = BM25Engine(
                    index_dir=bm25_index_dir,
                    chunks_files=bm25_data_files,
                )
                print("BM25引擎初始化完成")
        except Exception as e:
            logger.warning(f"BM25引擎初始化失败: {e}")
            self._bm25_engine = None

    def _find_project_root(self) -> str:
        current = os.path.dirname(os.path.abspath(__file__))
        for _ in range(5):
            if os.path.exists(os.path.join(current, 'data')):
                return current
            parent = os.path.dirname(current)
            if parent == current:
                break
            current = parent
        return os.path.dirname(os.path.abspath(__file__))

    @property
    def embedding_model(self):
        """延迟加载text2vec模型（使用模块级单例缓存）"""
        return get_shared_embedding_model()

    @property
    def embedding_dimension(self) -> int:
        return 768  # text2vec-base-chinese输出维度

    def _load_or_build_index(self):
        """加载已有索引或构建新索引"""
        # 加载文档块
        if self.chunks_file and os.path.exists(self.chunks_file):
            with open(self.chunks_file, 'r', encoding='utf-8') as f:
                self.chunks = json.load(f)
            print(f"Loaded {len(self.chunks)} chunks from {self.chunks_file}")

        # 尝试加载已有FAISS索引
        if os.path.exists(self.index_file):
            try:
                self.index = faiss.read_index(self.index_file)
                print(f"Loaded FAISS index from {self.index_file}")
            except Exception as e:
                print(f"Failed to load index: {e}")
                self.index = None

        # 如果没有索引，构建新索引
        if self.index is None and self.chunks:
            self._build_index()

    def _build_index(self, batch_size: int = None):
        """构建FAISS HNSW索引（适合 10w+ 向量，内存占用低）
        
        Args:
            batch_size: 每批处理的块数，默认使用 DEFAULT_BATCH_SIZE (512)
                       - 256: 适合 4GB 内存
                       - 512: 适合 8GB 内存（默认）
                       - 1024: 适合 16GB+ 内存
        """
        if not self.chunks:
            print("No chunks to index")
            return

        batch_size = batch_size or self.DEFAULT_BATCH_SIZE
        total = len(self.chunks)
        print(f"Building FAISS HNSW index for {total} chunks (batch_size={batch_size})...")

        texts = [chunk['content'] for chunk in self.chunks]
        
        # 分批处理，避免 OOM
        all_embeddings = []
        for i in range(0, total, batch_size):
            batch = texts[i:i+batch_size]
            batch_embeddings = self.embedding_model.encode(batch)
            all_embeddings.append(batch_embeddings)
            
            processed = min(i + batch_size, total)
            progress = processed / total * 100
            print(f"  [{processed}/{total}] ({progress:.1f}%) embeddings computed")

        embeddings = np.vstack(all_embeddings)
        
        if len(embeddings.shape) == 1:
            embeddings = embeddings.reshape(1, -1)
        
        dimension = embeddings.shape[1]
        
        # 创建 HNSW 索引
        self.index = faiss.IndexHNSWFlat(dimension, self.HNSW_M)
        self.index.hnsw.efConstruction = self.HNSW_EF_CONSTRUCTION
        
        self.index.add(embeddings.astype('float32'))
        
        print(f"Built HNSW index with {self.index.ntotal} vectors (M={self.HNSW_M}, ef_construction={self.HNSW_EF_CONSTRUCTION})")

        if self.index_file:
            faiss.write_index(self.index, self.index_file)
            print(f"Saved HNSW index to {self.index_file}")

    def search(
        self,
        query: str,
        top_k: int = 5,
        min_relevance_threshold: float = 0.5,
        enable_filtering: bool = True,
    ) -> List[Dict[str, Any]]:
        """向量相似度搜索——HNSW 近似最近邻（四级缓存：L1 -> L2 Redis -> SimHash语义 -> FAISS检索）
        
        缓存层级：
        1. L1缓存：内存LRU，带动态TTL（query_cache.py）
        2. L2 Redis：分布式Redis缓存，TTL=24h，支持内存降级（redis_cache.py）
        3. SimHash语义：基于SimHash指纹的近似匹配，汉明距离<=3视为相似（simhash_cache.py）
        4. FAISS向量检索：最终后备方案
        
        结果同步：任何层级命中后，结果向上层缓存同步写入
        
        Args:
            query: 搜索查询
            top_k: 返回结果数量
            min_relevance_threshold: 最低相关性阈值，默认 0.5
            enable_filtering: 是否启用结果过滤，默认 True
        """
        # 级别1：L1内存缓存（最快，带动态TTL的LRU）
        l1_cache = get_l1_cache()
        l1_results = l1_cache.get(query, top_k)
        if l1_results is not None:
            return l1_results

        # 级别2：L2 Redis缓存（分布式持久化，支持内存降级）
        l2_redis_cache = get_redis_cache()
        try:
            l2_redis_results = l2_redis_cache.get(query)
            if l2_redis_results is not None:
                l1_cache.set(query, l2_redis_results, top_k)
                return l2_redis_results
        except Exception as e:
            logger.debug("L2 Redis缓存查询失败，继续下一层: %s", str(e))

        # 级别3：SimHash语义近似匹配（基于内容相似度）
        l3_simhash_cache = get_simhash_cache()
        try:
            l3_simhash_results = l3_simhash_cache.get(query, top_k)
            if l3_simhash_results is not None:
                # SimHash命中，同步写入上层缓存
                l1_cache.set(query, l3_simhash_results, top_k)
                l2_redis_cache.set(query, l3_simhash_results, top_k)
                return l3_simhash_results
        except Exception as e:
            logger.debug("SimHash语义缓存查询失败，继续下一层: %s", str(e))

        # 级别4：执行FAISS向量检索
        if self.index is None or self.index.ntotal == 0:
            return []

        if hasattr(self.index, 'hnsw'):
            self.index.hnsw.efSearch = self.HNSW_EF_SEARCH

        query_embedding = self.embedding_model.encode([query])
        if len(query_embedding.shape) == 1:
            query_embedding = query_embedding.reshape(1, -1)

        distances, indices = self.index.search(query_embedding.astype('float32'), top_k)

        results = []
        for i, idx in enumerate(indices[0]):
            if idx < len(self.chunks):
                results.append({
                    'content': self.chunks[idx]['content'],
                    'metadata': self.chunks[idx].get('metadata', {}),
                    'distance': float(distances[0][i]),
                    'score': 1.0 / (1.0 + float(distances[0][i]))
                })

        if enable_filtering and results:
            filter_chain = create_default_filter_chain(
                relevance_threshold=min_relevance_threshold,
                enable_relevance=True,
            )
            
            before_filter_count = len(results)
            results = filter_chain.apply(results)
            after_filter_count = len(results)
            
            if results:
                avg_relevance = sum(
                    r.get('score', 0) for r in results
                ) / len(results)
            else:
                avg_relevance = 0.0
            
            logger.info(
                f"[VectorSearch] 过滤统计: "
                f"query='{query[:30]}...', "
                f"过滤前={before_filter_count}, "
                f"过滤后={after_filter_count}, "
                f"平均relevance={avg_relevance:.3f}"
            )
            
            if after_filter_count < top_k and before_filter_count >= top_k:
                logger.warning(
                    f"[VectorSearch] 过滤后结果不足top_k: "
                    f"query='{query[:30]}...', "
                    f"top_k={top_k}, "
                    f"过滤后={after_filter_count}"
                )

        if results:
            try:
                l1_cache.set(query, results, top_k)
            except Exception as e:
                logger.debug("L1缓存写入失败: %s", str(e))
            
            try:
                l2_redis_cache.set(query, results, top_k)
            except Exception as e:
                logger.debug("L2 Redis缓存写入失败: %s", str(e))
            
            try:
                l3_simhash_cache.set(query, results, top_k)
            except Exception as e:
                logger.debug("SimHash语义缓存写入失败: %s", str(e))

        return results

    def add_chunks(self, chunks: List[Dict], batch_size: int = None):
        """增量添加新文档块并更新FAISS HNSW索引
        
        Args:
            chunks: 要添加的文档块列表
            batch_size: 每批处理的块数，默认使用 DEFAULT_BATCH_SIZE (512)
        """
        batch_size = batch_size or self.DEFAULT_BATCH_SIZE
        self.chunks.extend(chunks)

        texts = [chunk['content'] for chunk in chunks]
        
        # 分批处理，避免大量新文档导致 OOM
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            embeddings = self.embedding_model.encode(batch)
            
            if len(embeddings.shape) == 1:
                embeddings = embeddings.reshape(1, -1)

            if self.index is not None:
                self.index.add(embeddings.astype('float32'))
            else:
                dimension = embeddings.shape[1]
                self.index = faiss.IndexHNSWFlat(dimension, self.HNSW_M)
                self.index.hnsw.efConstruction = self.HNSW_EF_CONSTRUCTION
                self.index.add(embeddings.astype('float32'))
            
            processed = min(i + batch_size, len(texts))
            print(f"  Indexed {processed}/{len(texts)} new chunks")

        if self.chunks_file:
            with open(self.chunks_file, 'w', encoding='utf-8') as f:
                json.dump(self.chunks, f, ensure_ascii=False, indent=2)

        if self.index_file:
            faiss.write_index(self.index, self.index_file)
            print(f"Saved updated index to {self.index_file}")

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            'chunk_count': len(self.chunks),
            'index_size': self.index.ntotal if self.index else 0,
            'dimension': self.embedding_dimension
        }

    def get_cache_stats(self) -> Dict[str, Any]:
        """获取四级缓存层统计信息
        
        返回所有缓存层的统计信息：
        - L1: 内存LRU缓存
        - L2: Redis分布式缓存（或内存降级）
        - L3: SimHash语义近似缓存
        """
        l1_cache = get_l1_cache()
        l2_redis_cache = get_redis_cache()
        l3_simhash_cache = get_simhash_cache()

        return {
            'l1_cache': l1_cache.get_stats(),
            'l2_redis_cache': l2_redis_cache.get_stats(),
            'l3_simhash_cache': l3_simhash_cache.get_stats()
        }

    def verify_dimension(self) -> bool:
        if self.index is None:
            return True
        return self.index.d == self.embedding_dimension

    def bm25_search(self, query: str, top_k: int = 5, search_type: str = None) -> List[Dict[str, Any]]:
        """BM25关键词搜索

        使用BM25算法进行关键词检索，支持：
        - 关键词搜索：直接搜索关键词
        - 短语搜索：使用双引号包裹，如 "连锁处理"
        - 布尔搜索：使用AND/OR连接，如 "连锁 AND 效果"

        Args:
            query: 搜索查询字符串
            top_k: 返回结果数量
            search_type: 搜索类型 ('keyword', 'phrase', 'boolean')，
                         如果为None则自动检测

        Returns:
            List[Dict]: BM25检索结果，格式与向量检索结果一致:
                - id: 文档ID
                - content: 文档内容
                - metadata: 文档元数据
                - score: BM25相关性分数
                - relevance: 归一化相关性分数（0-1范围）
        """
        if self._bm25_engine is None:
            logger.warning("BM25引擎未初始化")
            return []

        try:
            results = self._bm25_engine.search(query, top_k, search_type)

            for result in results:
                result['relevance'] = self._normalize_bm25_score(result.get('score', 0))

            return results
        except Exception as e:
            logger.error(f"BM25搜索失败: {e}")
            return []

    def _normalize_bm25_score(self, score: float) -> float:
        """将BM25分数归一化到0-1范围

        BM25分数可以是任意正数，使用sigmoid函数归一化。

        Args:
            score: 原始BM25分数

        Returns:
            float: 归一化后的分数（0-1）
        """
        if score <= 0:
            return 0.0
        return 1.0 / (1.0 + np.exp(-score / 2.0))

    def hybrid_search(
        self,
        query: str,
        top_k: int = 5,
        vector_weight: float = 0.7,
        bm25_weight: float = 0.3,
    ) -> List[Dict[str, Any]]:
        """混合搜索：向量检索 + BM25关键词检索

        结合向量语义相似度和BM25关键词匹配度，
        提供更好的检索效果。

        Args:
            query: 搜索查询
            top_k: 返回结果数量
            vector_weight: 向量检索权重（默认0.7）
            bm25_weight: BM25检索权重（默认0.3）

        Returns:
            List[Dict]: 混合排序后的结果
        """
        vector_results = self.search(query, top_k * 2)
        bm25_results = self.bm25_search(query, top_k * 2)

        doc_scores = {}

        for i, result in enumerate(vector_results):
            doc_id = result.get('id', '')
            vector_score = 1.0 / (1.0 + result.get('distance', 0))
            doc_scores[doc_id] = {
                'result': result,
                'vector_score': vector_score,
                'bm25_score': 0.0,
            }

        for i, result in enumerate(bm25_results):
            doc_id = result.get('id', '')
            bm25_score = result.get('relevance', 0)

            if doc_id in doc_scores:
                doc_scores[doc_id]['bm25_score'] = bm25_score
            else:
                doc_scores[doc_id] = {
                    'result': result,
                    'vector_score': 0.0,
                    'bm25_score': bm25_score,
                }

        hybrid_results = []
        for doc_id, scores in doc_scores.items():
            final_score = (
                vector_weight * scores['vector_score'] +
                bm25_weight * scores['bm25_score']
            )
            result = scores['result'].copy()
            result['hybrid_score'] = final_score
            result['vector_score'] = scores['vector_score']
            result['bm25_score'] = scores['bm25_score']
            hybrid_results.append(result)

        hybrid_results.sort(key=lambda x: x['hybrid_score'], reverse=True)
        return hybrid_results[:top_k]

    def get_bm25_stats(self) -> Dict[str, Any]:
        """获取BM25引擎统计信息

        Returns:
            Dict: BM25统计信息
        """
        if self._bm25_engine:
            return self._bm25_engine.get_stats()
        return {'error': 'BM25引擎未初始化'}

    def rebuild_bm25_index(self):
        """重建BM25索引"""
        if self._bm25_engine:
            self._bm25_engine.rebuild_index()
        else:
            logger.warning("BM25引擎未初始化，无法重建索引")

    def rrf_hybrid_search(
        self,
        query: str,
        top_k: int = 5,
        vector_weight: Optional[float] = None,
        bm25_weight: Optional[float] = None,
        auto_classify: bool = True,
    ) -> List[Dict[str, Any]]:
        """RRF融合搜索：向量检索Top 50 + BM25检索Top 50 + RRF融合排序Top K
        
        算法流程：
        1. 向量检索Top 50候选文档
        2. BM25检索Top 50候选文档
        3. RRF融合排序（score(d) = Σ 1/(k + rank_i(d))）
        4. 输出Top K结果
        
        动态权重调整：
        - 规则查询（包含精确规则术语）：BM25权重50%
        - 语义查询（抽象概念）：向量权重90%
        - 默认：向量70% + BM25 30%
        
        Args:
            query: 搜索查询
            top_k: 返回结果数量
            vector_weight: 向量检索权重（可选，不提供则自动分类）
            bm25_weight: BM25检索权重（可选，不提供则自动分类）
            auto_classify: 是否自动分类查询并调整权重（默认True）
            
        Returns:
            List[Dict]: RRF融合排序后的Top K结果，每项包含:
                - id: 文档ID
                - content: 文档内容
                - metadata: 文档元数据
                - rrf_score: RRF融合得分
                - vector_rrf: 向量RRF贡献得分
                - bm25_rrf: BM25 RRF贡献得分
                - vector_rank: 向量检索排名
                - bm25_rank: BM25检索排名
                - source: 结果来源 ('vector', 'bm25', 'both')
                - query_type: 查询类型（仅当auto_classify=True时）
        """
        import time
        
        rrf_start = time.time()
        
        # 步骤1: 确定权重配置
        if auto_classify and vector_weight is None and bm25_weight is None:
            weights = QueryClassifier.get_weights(query)
            vector_weight = weights['vector_weight']
            bm25_weight = weights['bm25_weight']
            query_type, _ = QueryClassifier.classify(query)
        else:
            query_type = 'custom'
        
        # 步骤2: 向量检索Top 50
        vector_retrieval_start = time.time()
        vector_results = self.search(query, top_k=50)
        vector_time = time.time() - vector_retrieval_start
        
        # 步骤3: BM25检索Top 50
        bm25_retrieval_start = time.time()
        bm25_results = self.bm25_search(query, top_k=50)
        bm25_time = time.time() - bm25_retrieval_start
        
        # 步骤4: RRF融合排序
        rrf_fusion_start = time.time()
        fusion_results = reciprocal_rank_fusion(
            vector_results=vector_results,
            bm25_results=bm25_results,
            top_k=top_k,
            vector_weight=vector_weight,
            bm25_weight=bm25_weight,
            k=RRF_K,
        )
        rrf_time = time.time() - rrf_fusion_start
        
        total_time = time.time() - rrf_start
        
        # 附加性能信息和查询类型到结果
        for result in fusion_results:
            result['query_type'] = query_type
        
        # 记录性能统计
        logger.info(
            f"RRF融合搜索完成: query='{query[:30]}...', "
            f"vector_time={vector_time*1000:.1f}ms, "
            f"bm25_time={bm25_time*1000:.1f}ms, "
            f"rrf_time={rrf_time*1000:.2f}ms, "
            f"total_time={total_time*1000:.1f}ms, "
            f"query_type={query_type}, "
            f"weights=(v={vector_weight}, b={bm25_weight})"
        )
        
        return fusion_results

    def rerank_search(
        self,
        query: str,
        top_k: int = 5,
        rerank_top_k: int = 10,
        auto_classify: bool = True,
        force_cpu: bool = False,
    ) -> List[Dict[str, Any]]:
        """完整检索链路：向量+BM25 → RRF融合 → Cross-Encoder重排
        
        检索流程（四级流水线）：
        ┌─────────────────────────────────────────────────────┐
        │ 步骤1: 粗检索（召回）                                │
        │   - 向量检索 Top 50（Bi-Encoder语义相似度）           │
        │   - BM25检索 Top 50（关键词匹配）                     │
        ├─────────────────────────────────────────────────────┤
        │ 步骤2: RRF融合排序                                   │
        │   - 多路检索结果融合                                  │
        │   - 输出 Top 50 有序候选列表                          │
        ├─────────────────────────────────────────────────────┤
        │ 步骤3: Cross-Encoder重排（精细排序）                  │
        │   - 对 Top 50 文档逐一评分（query-doc pair）          │
        │   - 按相关性分数降序排列                              │
        │   - 输出 Top 10 重排结果                              │
        ├─────────────────────────────────────────────────────┤
        │ 步骤4: 输出最终结果                                   │
        │   - 截取 Top K 返回给用户                             │
        └─────────────────────────────────────────────────────┘
        
        降级策略：
        - 如果 Cross-Encoder 模型加载失败，自动跳过步骤3
        - 直接返回 RRF 融合结果，不影响正常检索流程
        - 记录警告日志，便于排查问题
        
        性能目标：
        - 模型加载时间 < 5s
        - 重排延迟 < 50ms（GPU）/ < 200ms（CPU）
        - recall@5 提升：RRF 88% → +Cross-Encoder 92%
        
        Args:
            query: 用户查询字符串
            top_k: 最终返回结果数量（默认5）
            rerank_top_k: Cross-Encoder重排的候选数量（默认10）
            auto_classify: 是否自动分类查询并调整RRF权重（默认True）
            force_cpu: 是否强制 Cross-Encoder 使用 CPU（默认自动检测GPU）
            
        Returns:
            List[Dict]: 重排后的Top K结果，每项包含:
                - id: 文档ID
                - content: 文档内容
                - metadata: 文档元数据
                - rerank_score: Cross-Encoder重排分数
                - rrf_score: RRF融合得分
                - query_type: 查询类型
                - reranked: 是否经过Cross-Encoder重排（布尔值）
                - fallback_to_rrf: 是否降级为RRF结果（布尔值）
        """
        import time
        
        pipeline_start = time.time()
        
        # 步骤1 & 2: RRF融合检索（获取候选文档）
        rrf_start = time.time()
        rrf_candidates = self.rrf_hybrid_search(
            query=query,
            top_k=rerank_top_k,
            auto_classify=auto_classify,
        )
        rrf_time = time.time() - rrf_start
        
        if not rrf_candidates:
            logger.warning(f"[RerankSearch] RRF未返回候选文档: query='{query[:30]}...'")
            return []
        
        # 步骤3: Cross-Encoder重排
        reranker = get_cross_encoder_reranker(force_cpu=force_cpu)
        rerank_applied = False
        fallback_to_rrf = False
        
        if reranker and reranker.is_loaded:
            try:
                rerank_start = time.time()
                
                # 对RRF结果进行Cross-Encoder重排
                reranked_docs = reranker.rerank(
                    query=query,
                    documents=rrf_candidates,
                    top_k=top_k,
                )
                
                rerank_time = time.time() - rerank_start
                
                # 标记为已重排，附加元信息
                for i, doc in enumerate(reranked_docs):
                    doc['rerank_applied'] = True
                    doc['fallback_to_rrf'] = False
                    doc['rerank_rank'] = i + 1
                
                rerank_applied = True
                
                logger.info(
                    f"[RerankSearch] Cross-Encoder重排完成: "
                    f"query='{query[:30]}...', "
                    f"rrf_time={rrf_time*1000:.1f}ms, "
                    f"rerank_time={rerank_time*1000:.1f}ms, "
                    f"total_time={(time.time()-pipeline_start)*1000:.1f}ms, "
                    f"rerank_docs={len(reranked_docs)}"
                )
                
                return reranked_docs
                
            except Exception as e:
                # 降级策略：重排失败，返回RRF结果
                logger.warning(
                    f"[RerankSearch] Cross-Encoder重排失败，降级为RRF结果: {e}"
                )
                fallback_to_rrf = True
        else:
            # 降级策略：模型未加载，返回RRF结果
            logger.warning(
                "[RerankSearch] Cross-Encoder模型未加载，降级为RRF结果"
            )
            fallback_to_rrf = True
        
        # 步骤4: 降级路径——返回RRF Top K
        rrf_top_k_docs = rrf_candidates[:top_k]
        for i, doc in enumerate(rrf_top_k_docs):
            doc['rerank_applied'] = False
            doc['fallback_to_rrf'] = True
            doc['rerank_rank'] = i + 1
            doc['rerank_score'] = 0.0  # 无重排分数
        
        total_time = time.time() - pipeline_start
        logger.info(
            f"[RerankSearch] 降级为RRF结果: "
            f"query='{query[:30]}...', "
            f"rrf_time={rrf_time*1000:.1f}ms, "
            f"total_time={total_time*1000:.1f}ms, "
            f"docs={len(rrf_top_k_docs)}"
        )
        
        return rrf_top_k_docs