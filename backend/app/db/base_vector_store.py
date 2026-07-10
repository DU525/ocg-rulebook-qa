"""统一向量存储基类 - 同时支持OCG和DM领域"""
import os
import json
import logging
import faiss
from typing import List, Optional, Dict, Any, Callable
from app.services.vector_rag import get_shared_embedding_model
from app.db.faiss_quantized_index import QuantizedIndexConfig, QuantizedVectorRAG

logger = logging.getLogger(__name__)


class BaseVectorRAG:
    """基础向量检索RAG系统——支持 10w+ 数据量扩展"""

    HNSW_M = 16
    HNSW_EF_CONSTRUCTION = 200
    HNSW_EF_SEARCH = 50

    # 批量嵌入参数：避免 10w+ 块一次性加载导致 OOM
    DEFAULT_BATCH_SIZE = 512

    def __init__(self, chunks_file: str = None, index_file: str = None, collection_name: str = "rules"):
        self.chunks_file = chunks_file
        self.index_file = index_file or chunks_file.replace('.json', '_index.bin') if chunks_file else None
        self.chunks = []
        self.index = None
        self.collection_name = collection_name
        self._load_or_build_index()

    @property
    def embedding_dimension(self) -> int:
        return 768

    def _load_or_build_index(self):
        if self.chunks_file and os.path.exists(self.chunks_file):
            with open(self.chunks_file, 'r', encoding='utf-8') as f:
                self.chunks = json.load(f)
            print(f"[{self.collection_name}] Loaded {len(self.chunks)} chunks from {self.chunks_file}")

        if self.index_file and os.path.exists(self.index_file):
            try:
                self.index = faiss.read_index(self.index_file)
                print(f"[{self.collection_name}] Loaded FAISS index from {self.index_file}")
            except Exception as e:
                print(f"[{self.collection_name}] Failed to load index: {e}")
                self.index = None

        if self.index is None and self.chunks:
            self._build_index()

    def _build_index(self, batch_size: int = None, progress_callback: Callable = None):
        """构建FAISS HNSW索引（支持 10w+ 向量，分批处理避免 OOM）
        
        Args:
            batch_size: 每批处理的块数，默认 DEFAULT_BATCH_SIZE (512)
            progress_callback: 进度回调函数，签名: callback(current, total, stage)
        """
        if not self.chunks:
            print(f"[{self.collection_name}] No chunks to index")
            return

        import numpy as np
        batch_size = batch_size or self.DEFAULT_BATCH_SIZE
        total = len(self.chunks)
        print(f"[{self.collection_name}] Building FAISS HNSW index for {total} chunks (batch_size={batch_size})...")

        texts = [chunk['content'] for chunk in self.chunks]
        
        if progress_callback:
            progress_callback(0, total, 'encoding')

        # 分批处理，避免 OOM
        all_embeddings = []
        for i in range(0, total, batch_size):
            batch = texts[i:i+batch_size]
            batch_embeddings = get_shared_embedding_model().encode(batch)
            all_embeddings.append(batch_embeddings)
            
            if progress_callback:
                progress_callback(min(i + batch_size, total), total, 'encoding')
            
            print(f"  [{min(i + batch_size, total)}/{total}] embeddings computed")

        embeddings = np.vstack(all_embeddings)
        
        if len(embeddings.shape) == 1:
            embeddings = embeddings.reshape(1, -1)

        dimension = embeddings.shape[1]
        self.index = faiss.IndexHNSWFlat(dimension, self.HNSW_M)
        self.index.hnsw.efConstruction = self.HNSW_EF_CONSTRUCTION
        self.index.add(embeddings.astype('float32'))

        print(f"[{self.collection_name}] Built HNSW index with {self.index.ntotal} vectors (M={self.HNSW_M}, ef_construction={self.HNSW_EF_CONSTRUCTION})")

        if self.index_file:
            faiss.write_index(self.index, self.index_file)
            if progress_callback:
                progress_callback(total, total, 'saved')
            print(f"[{self.collection_name}] Saved index to {self.index_file}")

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        if self.index is None or self.index.ntotal == 0:
            return []

        if hasattr(self.index, 'hnsw'):
            self.index.hnsw.efSearch = self.HNSW_EF_SEARCH

        query_embedding = get_shared_embedding_model().encode([query])
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

        return results

    def add_chunks(self, chunks: List[Dict], batch_size: int = None, progress_callback: Callable = None):
        """增量添加新文档块并更新FAISS HNSW索引
        
        Args:
            chunks: 要添加的文档块列表
            batch_size: 每批处理的块数，默认 DEFAULT_BATCH_SIZE (512)
            progress_callback: 进度回调函数，签名: callback(current, total, stage)
        """
        import numpy as np
        batch_size = batch_size or self.DEFAULT_BATCH_SIZE
        self.chunks.extend(chunks)

        texts = [chunk['content'] for chunk in chunks]
        total_texts = len(texts)
        
        for i in range(0, total_texts, batch_size):
            batch = texts[i:i+batch_size]
            embeddings = get_shared_embedding_model().encode(batch)
            
            if len(embeddings.shape) == 1:
                embeddings = embeddings.reshape(1, -1)

            if self.index is not None:
                self.index.add(embeddings.astype('float32'))
            else:
                dimension = embeddings.shape[1]
                self.index = faiss.IndexHNSWFlat(dimension, self.HNSW_M)
                self.index.hnsw.efConstruction = self.HNSW_EF_CONSTRUCTION
                self.index.add(embeddings.astype('float32'))
            
            if progress_callback:
                progress_callback(min(i + batch_size, total_texts), total_texts, 'indexing')
            
            print(f"  Indexed {min(i + batch_size, total_texts)}/{total_texts} new chunks")

        if self.chunks_file:
            with open(self.chunks_file, 'w', encoding='utf-8') as f:
                json.dump(self.chunks, f, ensure_ascii=False, indent=2)

        if self.index_file:
            faiss.write_index(self.index, self.index_file)
            print(f"[{self.collection_name}] Saved updated index to {self.index_file}")

    def delete_by_source(self, source: str, batch_size: int = None, progress_callback: Callable = None):
        """按来源删除文档块（通过过滤 + 重建索引）
        
        Args:
            source: 要删除的文档来源
            batch_size: 重建索引时的批次大小
            progress_callback: 进度回调函数
        """
        logger.warning(f"[{self.collection_name}] FAISS 不支持直接删除，正在通过过滤 + 重建索引来完成...")
        if progress_callback:
            progress_callback(0, len(self.chunks), 'filtering')
        
        filtered = [c for c in self.chunks if c.get('metadata', {}).get('source') != source]
        removed = len(self.chunks) - len(filtered)
        logger.info(f"[{self.collection_name}] 已移除 {removed} 个 source='{source}' 的 chunks")
        self.chunks = filtered
        
        if progress_callback:
            progress_callback(len(filtered), len(self.chunks), 'rebuilding')
        
        self._build_index(batch_size=batch_size, progress_callback=progress_callback)
        if self.chunks_file:
            with open(self.chunks_file, 'w', encoding='utf-8') as f:
                json.dump(self.chunks, f, ensure_ascii=False, indent=2)

    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息，包括文档来源分布"""
        # 统计每个 source 的 chunk 数量
        source_counts = {}
        for chunk in self.chunks:
            source = chunk.get('metadata', {}).get('source', 'unknown')
            source_counts[source] = source_counts.get(source, 0) + 1
        
        return {
            'chunk_count': len(self.chunks),
            'index_size': self.index.ntotal if self.index else 0,
            'dimension': self.embedding_dimension,
            'source_distribution': source_counts,
            'unique_sources': len(source_counts)
        }


class BaseVectorStore:
    """统一向量存储管理基类"""

    def __init__(self, persist_directory: str, chunks_file: str, index_file: str, collection_name: str, rag_class=None):
        os.makedirs(persist_directory, exist_ok=True)
        self.persist_directory = persist_directory
        self._cached_rag = None
        self._chunks_file = chunks_file
        self._index_file = index_file
        self._collection_name = collection_name
        self._rag_class = rag_class or BaseVectorRAG

    def _get_or_init_rag(self) -> BaseVectorRAG:
        if self._cached_rag is None:
            self._cached_rag = self._rag_class(
                chunks_file=self._chunks_file,
                index_file=self._index_file,
                collection_name=self._collection_name
            )
        return self._cached_rag

    @property
    def embedding_dimension(self) -> int:
        return 768

    def add_chunks(self, chunks: List[dict]) -> None:
        from app.services.document_processor import DocumentChunk
        rag = self._get_or_init_rag()
        chunk_dicts = []
        for chunk in chunks:
            if isinstance(chunk, DocumentChunk):
                chunk_dicts.append({'id': chunk.id, 'content': chunk.content, 'metadata': chunk.metadata})
            else:
                chunk_dicts.append(chunk)
        rag.add_chunks(chunk_dicts)

    def search(self, query: str, n_results: int = 5, filter_metadata: Optional[dict] = None) -> List[dict]:
        rag = self._get_or_init_rag()
        results = rag.search(query, top_k=n_results)
        formatted_results = []
        for r in results:
            formatted_results.append({
                'id': r.get('metadata', {}).get('source', 'unknown'),
                'content': r['content'],
                'metadata': r['metadata'],
                'distance': 1.0 / (1.0 + r['score'])
            })
        return formatted_results

    def delete_by_source(self, source: str) -> None:
        rag = self._get_or_init_rag()
        rag.delete_by_source(source)

    def delete_by_ids(self, ids: List[str]) -> None:
        logger.warning(f"[{self._collection_name}] FAISS 不支持直接删除，正在通过过滤 + 重建索引来完成...")
        rag = self._get_or_init_rag()
        ids_set = set(ids)
        filtered = [c for c in rag.chunks if c.get('id') not in ids_set]
        removed = len(rag.chunks) - len(filtered)
        logger.info(f"[{self._collection_name}] 已移除 {removed} 个指定 ID 的 chunks")
        rag.chunks = filtered
        rag._build_index()
        if rag.chunks_file:
            with open(rag.chunks_file, 'w', encoding='utf-8') as f:
                json.dump(rag.chunks, f, ensure_ascii=False, indent=2)

    def get_collection_stats(self) -> dict:
        try:
            rag = self._get_or_init_rag()
            stats = rag.get_stats()
            return {'count': stats.get('index_size', 0), 'name': self._collection_name, 'index_type': 'HNSW'}
        except Exception:
            return {'count': 0, 'name': self._collection_name, 'index_type': 'HNSW'}


class QuantizedBaseVectorStore(BaseVectorStore):
    """支持多种索引类型的向量存储管理"""
    
    def __init__(
        self,
        persist_directory: str,
        chunks_file: str,
        index_file: str,
        collection_name: str,
        index_type: str = QuantizedIndexConfig.INDEX_TYPE_IVFPQ,
        rag_class=None
    ):
        super().__init__(
            persist_directory,
            chunks_file,
            index_file,
            collection_name,
            rag_class
        )
        self.index_type = index_type
        self._quantized_rag = None
    
    def _get_or_init_rag(self):
        if self._quantized_rag is None:
            self._quantized_rag = QuantizedVectorRAG(
                chunks_file=self._chunks_file,
                index_file=self._index_file,
                collection_name=self._collection_name,
                index_type=self.index_type
            )
        return self._quantized_rag
    
    def get_collection_stats(self) -> dict:
        try:
            rag = self._get_or_init_rag()
            stats = rag.get_stats()
            return {
                'count': stats.get('index_size', 0),
                'name': self._collection_name,
                'index_type': stats.get('index_type', self.index_type),
                'memory_usage_mb': stats.get('memory_usage_mb', {})
            }
        except Exception as e:
            logger.error(f"Failed to get collection stats: {e}")
            return {'count': 0, 'name': self._collection_name, 'index_type': self.index_type}
    
    def switch_index_type(
        self,
        new_index_type: str,
        new_index_file: Optional[str] = None
    ):
        """切换索引类型
        
        Args:
            new_index_type: 新的索引类型 (hnsw/ivf/ivfpq)
            new_index_file: 新的索引文件路径（可选）
        """
        if new_index_type not in [
            QuantizedIndexConfig.INDEX_TYPE_HNSW,
            QuantizedIndexConfig.INDEX_TYPE_IVF,
            QuantizedIndexConfig.INDEX_TYPE_IVFPQ
        ]:
            raise ValueError(f"Invalid index type: {new_index_type}")
        
        self.index_type = new_index_type
        if new_index_file:
            self._index_file = new_index_file
        
        self._quantized_rag = None
        rag = self._get_or_init_rag()
        return rag
