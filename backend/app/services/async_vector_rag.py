"""
异步向量检索模块 - Async Vector RAG

功能特性：
1. 使用 asyncio.to_thread() 包装 FAISS 搜索，避免阻塞事件循环
2. 异步 BM25 检索，支持并发检索优化
3. 异步 RRF 融合排序
4. 支持向量检索和关键词检索并发执行
5. 与现有 VectorRAG 接口兼容，便于迁移

使用示例：
```python
from app.services.async_vector_rag import AsyncVectorRAG

# 初始化
rag = AsyncVectorRAG(
    chunks_file='data/chunks/ocg_rules_chunks.json',
    index_file='data/chunks/ocg_rules_index.bin'
)

# 异步向量搜索
results = await rag.search("什么是连锁处理？", top_k=5)

# 异步混合搜索 (RRF融合)
hybrid_results = await rag.rrf_hybrid_search("连锁处理的规则", top_k=5)
```
"""
import os
import asyncio
import logging
import time
from typing import List, Dict, Any, Optional
from functools import partial

logger = logging.getLogger(__name__)

# 全局缓存：确保 text2vec 模型只加载一次
_cached_embedding_model = None
_cached_model_load_time = None
_embedding_model_lock = asyncio.Lock()


async def get_shared_embedding_model():
    """异步获取全局共享的 text2vec 嵌入模型（线程安全）"""
    global _cached_embedding_model, _cached_model_load_time
    
    async with _embedding_model_lock:
        if _cached_embedding_model is None:
            # 在单独的线程中加载模型，避免阻塞事件循环
            await asyncio.to_thread(_load_embedding_model_sync)
        
        return _cached_embedding_model


def _load_embedding_model_sync():
    """同步加载嵌入模型（在线程中执行）"""
    global _cached_embedding_model, _cached_model_load_time
    
    os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'
    from text2vec import SentenceModel
    
    load_start = time.time()
    _cached_embedding_model = SentenceModel('shibing624/text2vec-base-chinese')
    _cached_model_load_time = time.time() - load_start
    print(f"[CACHE] text2vec模型首次加载耗时: {_cached_model_load_time:.2f}秒")


class AsyncVectorRAG:
    """
    异步向量检索 RAG 系统
    
    基于 FAISS 索引，支持：
    - 异步向量相似度搜索
    - 异步 BM25 关键词搜索
    - 并发检索优化
    - RRF 融合排序
    """
    
    # HNSW 超参数
    HNSW_M = 8
    HNSW_EF_CONSTRUCTION = 128
    HNSW_EF_SEARCH = 32
    
    DEFAULT_BATCH_SIZE = 512
    
    def __init__(
        self,
        chunks_file: str = None,
        index_file: str = None,
        bm25_index_dir: str = None,
        bm25_chunks_files: List[str] = None,
    ):
        self.chunks_file = chunks_file
        self.index_file = index_file or (
            chunks_file.replace('.json', '_index.bin') if chunks_file else None
        )
        self.chunks = []
        self.index = None
        self._bm25_engine = None
        
        # 初始化同步加载数据（在 __init__ 中完成）
        self._load_or_build_index_sync()
        self._init_bm25_sync(
            bm25_index_dir=bm25_index_dir,
            bm25_chunks_files=bm25_chunks_files
        )
    
    def _find_project_root(self) -> str:
        """查找项目根目录"""
        current = os.path.dirname(os.path.abspath(__file__))
        for _ in range(5):
            if os.path.exists(os.path.join(current, 'data')):
                return current
            parent = os.path.dirname(current)
            if parent == current:
                break
            current = parent
        return os.path.dirname(os.path.abspath(__file__))
    
    def _load_or_build_index_sync(self):
        """同步加载已有索引或构建新索引"""
        import json
        import faiss
        import numpy as np
        
        if self.chunks_file and os.path.exists(self.chunks_file):
            with open(self.chunks_file, 'r', encoding='utf-8') as f:
                self.chunks = json.load(f)
            print(f"Loaded {len(self.chunks)} chunks from {self.chunks_file}")
        
        if os.path.exists(self.index_file):
            try:
                self.index = faiss.read_index(self.index_file)
                print(f"Loaded FAISS index from {self.index_file}")
            except Exception as e:
                print(f"Failed to load index: {e}")
                self.index = None
        
        if self.index is None and self.chunks:
            self._build_index_sync()
    
    def _build_index_sync(self, batch_size: int = None):
        """同步构建 FAISS HNSW 索引"""
        import faiss
        import numpy as np
        
        if not self.chunks:
            print("No chunks to index")
            return
        
        batch_size = batch_size or self.DEFAULT_BATCH_SIZE
        total = len(self.chunks)
        print(f"Building FAISS HNSW index for {total} chunks...")
        
        texts = [chunk['content'] for chunk in self.chunks]
        
        # 获取嵌入模型
        embedding_model = get_shared_embedding_model_sync()
        
        # 分批嵌入
        all_embeddings = []
        for i in range(0, total, batch_size):
            batch = texts[i:i+batch_size]
            batch_embeddings = embedding_model.encode(batch)
            all_embeddings.append(batch_embeddings)
            
            processed = min(i + batch_size, total)
            progress = processed / total * 100
            print(f"  [{processed}/{total}] ({progress:.1f}%) embeddings computed")
        
        embeddings = np.vstack(all_embeddings)
        
        if len(embeddings.shape) == 1:
            embeddings = embeddings.reshape(1, -1)
        
        dimension = embeddings.shape[1]
        
        self.index = faiss.IndexHNSWFlat(dimension, self.HNSW_M)
        self.index.hnsw.efConstruction = self.HNSW_EF_CONSTRUCTION
        self.index.add(embeddings.astype('float32'))
        
        print(f"Built HNSW index with {self.index.ntotal} vectors")
        
        if self.index_file:
            faiss.write_index(self.index, self.index_file)
            print(f"Saved HNSW index to {self.index_file}")
    
    def _init_bm25_sync(
        self,
        bm25_index_dir: str = None,
        bm25_chunks_files: List[str] = None,
    ):
        """同步初始化 BM25 引擎"""
        try:
            from app.services.bm25_engine import BM25Engine
            
            bm25_data_files = bm25_chunks_files or []
            if not bm25_data_files and self.chunks_file:
                bm25_data_files = [self.chunks_file.replace('_index.bin', '.json')]
            
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
    
    @property
    def embedding_dimension(self) -> int:
        return 768
    
    async def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """
        异步向量相似度搜索
        
        使用 asyncio.to_thread() 包装 FAISS 搜索操作，避免阻塞事件循环
        
        Args:
            query: 搜索查询
            top_k: 返回结果数量
            
        Returns:
            搜索结果列表
        """
        import numpy as np
        
        if self.index is None or self.index.ntotal == 0:
            return []
        
        # 获取嵌入模型
        embedding_model = await get_shared_embedding_model()
        
        # 在单独线程中计算查询嵌入
        query_embedding = await asyncio.to_thread(
            embedding_model.encode, [query]
        )
        
        if len(query_embedding.shape) == 1:
            query_embedding = query_embedding.reshape(1, -1)
        
        # 在单独线程中执行 FAISS 搜索
        distances, indices = await asyncio.to_thread(
            self._faiss_search_sync,
            query_embedding.astype('float32'),
            top_k
        )
        
        results = []
        for i, idx in enumerate(indices[0]):
            if idx < len(self.chunks):
                results.append({
                    'id': self.chunks[idx].get('id', ''),
                    'content': self.chunks[idx]['content'],
                    'metadata': self.chunks[idx].get('metadata', {}),
                    'distance': float(distances[0][i]),
                    'score': 1.0 / (1.0 + float(distances[0][i]))
                })
        
        return results
    
    def _faiss_search_sync(self, query_embedding, top_k):
        """同步执行 FAISS 搜索（在线程中调用）"""
        import faiss
        
        if hasattr(self.index, 'hnsw'):
            self.index.hnsw.efSearch = self.HNSW_EF_SEARCH
        
        return self.index.search(query_embedding, top_k)
    
    async def bm25_search(
        self,
        query: str,
        top_k: int = 5,
        search_type: str = None,
    ) -> List[Dict[str, Any]]:
        """
        异步 BM25 关键词搜索
        
        Args:
            query: 搜索查询
            top_k: 返回结果数量
            search_type: 搜索类型 ('keyword', 'phrase', 'boolean')
            
        Returns:
            搜索结果列表
        """
        if self._bm25_engine is None:
            logger.warning("BM25引擎未初始化")
            return []
        
        try:
            # 在单独线程中执行 BM25 搜索
            results = await asyncio.to_thread(
                self._bm25_engine.search,
                query,
                top_k,
                search_type
            )
            
            # 归一化 BM25 分数
            for result in results:
                result['relevance'] = self._normalize_bm25_score(result.get('score', 0))
            
            return results
        except Exception as e:
            logger.error(f"BM25搜索失败: {e}")
            return []
    
    def _normalize_bm25_score(self, score: float) -> float:
        """归一化 BM25 分数"""
        import numpy as np
        if score <= 0:
            return 0.0
        return 1.0 / (1.0 + np.exp(-score / 2.0))
    
    async def rrf_hybrid_search(
        self,
        query: str,
        top_k: int = 5,
        vector_weight: Optional[float] = None,
        bm25_weight: Optional[float] = None,
        auto_classify: bool = True,
    ) -> List[Dict[str, Any]]:
        """
        异步 RRF 融合混合搜索
        
        优化：向量检索和 BM25 检索并发执行，然后异步融合
        
        Args:
            query: 搜索查询
            top_k: 返回结果数量
            vector_weight: 向量检索权重
            bm25_weight: BM25 检索权重
            auto_classify: 是否自动分类查询
            
        Returns:
            融合后的搜索结果列表
        """
        from app.services.rrf_fusion import QueryClassifier, RRF_K, reciprocal_rank_fusion
        
        rrf_start = time.time()
        
        # 确定权重配置
        if auto_classify and vector_weight is None and bm25_weight is None:
            weights = QueryClassifier.get_weights(query)
            vector_weight = weights['vector_weight']
            bm25_weight = weights['bm25_weight']
            query_type, _ = QueryClassifier.classify(query)
        else:
            query_type = 'custom'
        
        # 并发执行向量检索和 BM25 检索（优化点）
        vector_task = self.search(query, top_k=50)
        bm25_task = self.bm25_search(query, top_k=50)
        
        vector_results, bm25_results = await asyncio.gather(
            vector_task,
            bm25_task
        )
        
        # 在单独线程中执行 RRF 融合
        fusion_results = await asyncio.to_thread(
            reciprocal_rank_fusion,
            vector_results=vector_results,
            bm25_results=bm25_results,
            top_k=top_k,
            vector_weight=vector_weight,
            bm25_weight=bm25_weight,
            k=RRF_K
        )
        
        # 添加查询类型信息
        for result in fusion_results:
            result['query_type'] = query_type
        
        total_time = time.time() - rrf_start
        logger.info(f"Async RRF融合搜索完成: {total_time*1000:.1f}ms")
        
        return fusion_results
    
    async def hybrid_search(
        self,
        query: str,
        top_k: int = 5,
        vector_weight: float = 0.7,
        bm25_weight: float = 0.3,
    ) -> List[Dict[str, Any]]:
        """
        异步混合搜索（简单加权版本）
        
        Args:
            query: 搜索查询
            top_k: 返回结果数量
            vector_weight: 向量权重
            bm25_weight: BM25 权重
            
        Returns:
            混合搜索结果
        """
        # 并发执行两个检索
        vector_results, bm25_results = await asyncio.gather(
            self.search(query, top_k * 2),
            self.bm25_search(query, top_k * 2)
        )
        
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
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            'chunk_count': len(self.chunks),
            'index_size': self.index.ntotal if self.index else 0,
            'dimension': self.embedding_dimension
        }
    
    def get_bm25_stats(self) -> Dict[str, Any]:
        """获取 BM25 统计信息"""
        if self._bm25_engine:
            return self._bm25_engine.get_stats()
        return {'error': 'BM25引擎未初始化'}


# 同步版本的辅助函数（用于 __init__ 中的同步加载）
def get_shared_embedding_model_sync():
    """同步获取共享嵌入模型"""
    global _cached_embedding_model, _cached_model_load_time
    
    if _cached_embedding_model is None:
        _load_embedding_model_sync()
    
    return _cached_embedding_model
