
"""FAISS 量化索引模块 - 支持 IVF 和 IVFPQ 索引"""
import os
import json
import logging
import faiss
import numpy as np
from typing import List, Optional, Dict, Any, Callable, Tuple, Union
from app.services.vector_rag import get_shared_embedding_model

logger = logging.getLogger(__name__)


class QuantizedIndexConfig:
    """量化索引配置"""
    
    INDEX_TYPE_HNSW = "hnsw"
    INDEX_TYPE_IVF = "ivf"
    INDEX_TYPE_IVFPQ = "ivfpq"
    
    IVF_NLIST = 1024
    IVF_NPROBE = 32
    
    IVFPQ_M = 8
    IVFPQ_NBITS = 8
    IVFPQ_NLIST = 1024
    IVFPQ_NPROBE = 32
    
    HNSW_M = 16
    HNSW_EF_CONSTRUCTION = 200
    HNSW_EF_SEARCH = 50


class QuantizedIndex:
    """FAISS 量化索引类"""
    
    def __init__(
        self,
        index_type: str = QuantizedIndexConfig.INDEX_TYPE_IVFPQ,
        dimension: int = 768,
        nlist: Optional[int] = None,
        nprobe: Optional[int] = None,
        m: Optional[int] = None,
        nbits: Optional[int] = None
    ):
        self.index_type = index_type
        self.dimension = dimension
        self.nlist = nlist or (
            QuantizedIndexConfig.IVFPQ_NLIST if index_type == QuantizedIndexConfig.INDEX_TYPE_IVFPQ
            else QuantizedIndexConfig.IVF_NLIST
        )
        self.nprobe = nprobe or (
            QuantizedIndexConfig.IVFPQ_NPROBE if index_type == QuantizedIndexConfig.INDEX_TYPE_IVFPQ
            else QuantizedIndexConfig.IVF_NPROBE
        )
        self.m = m or QuantizedIndexConfig.IVFPQ_M
        self.nbits = nbits or QuantizedIndexConfig.IVFPQ_NBITS
        self.index: Optional[faiss.Index] = None
        self.quantizer: Optional[faiss.Index] = None
        self.is_trained = False
        
    def build_ivf_index(
        self,
        embeddings: np.ndarray,
        train_embeddings: Optional[np.ndarray] = None,
        progress_callback: Optional[Callable] = None
    ) -> faiss.IndexIVFFlat:
        """构建 IVF 非量化索引
        
        Args:
            embeddings: 完整向量数据
            train_embeddings: 训练用向量（可选，默认使用全部数据）
            progress_callback: 进度回调
        
        Returns:
            构建好的 IVF 索引
        """
        if len(embeddings.shape) == 1:
            embeddings = embeddings.reshape(1, -1)
        
        dimension = embeddings.shape[1]
        if dimension != self.dimension:
            self.dimension = dimension
        
        train_data = train_embeddings if train_embeddings is not None else embeddings
        
        if progress_callback:
            progress_callback(0, 100, 'training_quantizer')
        
        quantizer = faiss.IndexFlatL2(dimension)
        index = faiss.IndexIVFFlat(quantizer, dimension, self.nlist, faiss.METRIC_L2)
        
        if progress_callback:
            progress_callback(30, 100, 'training_index')
        
        index.train(train_data.astype('float32'))
        self.is_trained = True
        
        if progress_callback:
            progress_callback(60, 100, 'adding_vectors')
        
        index.add(embeddings.astype('float32'))
        index.nprobe = self.nprobe
        
        self.index = index
        self.quantizer = quantizer
        
        if progress_callback:
            progress_callback(100, 100, 'completed')
        
        logger.info(f"Built IVF index: nlist={self.nlist}, nprobe={self.nprobe}, vectors={index.ntotal}")
        return index
    
    def build_ivfpq_index(
        self,
        embeddings: np.ndarray,
        train_embeddings: Optional[np.ndarray] = None,
        progress_callback: Optional[Callable] = None
    ) -> faiss.IndexIVFPQ:
        """构建 IVF+PQ 量化索引
        
        Args:
            embeddings: 完整向量数据
            train_embeddings: 训练用向量（可选，默认使用全部数据）
            progress_callback: 进度回调
        
        Returns:
            构建好的 IVFPQ 索引
        """
        if len(embeddings.shape) == 1:
            embeddings = embeddings.reshape(1, -1)
        
        dimension = embeddings.shape[1]
        if dimension != self.dimension:
            self.dimension = dimension
        
        train_data = train_embeddings if train_embeddings is not None else embeddings
        
        if progress_callback:
            progress_callback(0, 100, 'training_quantizer')
        
        quantizer = faiss.IndexFlatL2(dimension)
        index = faiss.IndexIVFPQ(quantizer, dimension, self.nlist, self.m, self.nbits)
        
        if progress_callback:
            progress_callback(30, 100, 'training_index')
        
        index.train(train_data.astype('float32'))
        self.is_trained = True
        
        if progress_callback:
            progress_callback(60, 100, 'adding_vectors')
        
        index.add(embeddings.astype('float32'))
        index.nprobe = self.nprobe
        
        self.index = index
        self.quantizer = quantizer
        
        if progress_callback:
            progress_callback(100, 100, 'completed')
        
        logger.info(f"Built IVFPQ index: nlist={self.nlist}, nprobe={self.nprobe}, m={self.m}, nbits={self.nbits}, vectors={index.ntotal}")
        return index
    
    def build_hnsw_index(
        self,
        embeddings: np.ndarray,
        progress_callback: Optional[Callable] = None
    ) -> faiss.IndexHNSWFlat:
        """构建 HNSW 索引（用于对比）
        
        Args:
            embeddings: 向量数据
            progress_callback: 进度回调
        
        Returns:
            构建好的 HNSW 索引
        """
        if len(embeddings.shape) == 1:
            embeddings = embeddings.reshape(1, -1)
        
        dimension = embeddings.shape[1]
        if dimension != self.dimension:
            self.dimension = dimension
        
        if progress_callback:
            progress_callback(0, 100, 'building_hnsw')
        
        index = faiss.IndexHNSWFlat(dimension, QuantizedIndexConfig.HNSW_M)
        index.hnsw.efConstruction = QuantizedIndexConfig.HNSW_EF_CONSTRUCTION
        
        if progress_callback:
            progress_callback(50, 100, 'adding_vectors')
        
        index.add(embeddings.astype('float32'))
        
        if progress_callback:
            progress_callback(100, 100, 'completed')
        
        self.index = index
        self.is_trained = True
        
        logger.info(f"Built HNSW index: M={QuantizedIndexConfig.HNSW_M}, ef_construction={QuantizedIndexConfig.HNSW_EF_CONSTRUCTION}, vectors={index.ntotal}")
        return index
    
    def search_quantized(
        self,
        query_embedding: np.ndarray,
        top_k: int = 5
    ) -> Tuple[np.ndarray, np.ndarray]:
        """量化索引搜索
        
        Args:
            query_embedding: 查询向量
            top_k: 返回结果数
        
        Returns:
            (distances, indices) 元组
        """
        if self.index is None:
            raise ValueError("Index not built yet")
        
        if len(query_embedding.shape) == 1:
            query_embedding = query_embedding.reshape(1, -1)
        
        if self.index_type == QuantizedIndexConfig.INDEX_TYPE_HNSW:
            if hasattr(self.index, 'hnsw'):
                self.index.hnsw.efSearch = QuantizedIndexConfig.HNSW_EF_SEARCH
        else:
            if hasattr(self.index, 'nprobe'):
                self.index.nprobe = self.nprobe
        
        distances, indices = self.index.search(query_embedding.astype('float32'), top_k)
        return distances, indices
    
    def rebuild_from_hnsw(
        self,
        hnsw_index: faiss.IndexHNSWFlat,
        embeddings: np.ndarray,
        progress_callback: Optional[Callable] = None
    ) -> faiss.Index:
        """从现有 HNSW 索引转换为量化索引
        
        Args:
            hnsw_index: 源 HNSW 索引
            embeddings: 原始向量数据
            progress_callback: 进度回调
        
        Returns:
            新构建的量化索引
        """
        if self.index_type == QuantizedIndexConfig.INDEX_TYPE_IVF:
            return self.build_ivf_index(embeddings, progress_callback=progress_callback)
        elif self.index_type == QuantizedIndexConfig.INDEX_TYPE_IVFPQ:
            return self.build_ivfpq_index(embeddings, progress_callback=progress_callback)
        else:
            raise ValueError(f"Unsupported index type: {self.index_type}")
    
    def save_index(self, filepath: str):
        """保存索引到文件"""
        if self.index is not None:
            faiss.write_index(self.index, filepath)
            logger.info(f"Saved {self.index_type} index to {filepath}")
    
    def load_index(self, filepath: str):
        """从文件加载索引"""
        if os.path.exists(filepath):
            self.index = faiss.read_index(filepath)
            self.is_trained = True
            if hasattr(self.index, 'nprobe'):
                self.index.nprobe = self.nprobe
            logger.info(f"Loaded {self.index_type} index from {filepath}")
            return self.index
        else:
            raise FileNotFoundError(f"Index file not found: {filepath}")
    
    def estimate_memory_usage(self) -> Dict[str, float]:
        """估算索引内存占用（MB）
        
        Returns:
            内存使用信息字典
        """
        if self.index is None or not hasattr(self.index, 'ntotal'):
            return {'total_mb': 0.0}
        
        n_total = self.index.ntotal
        dim = self.dimension
        
        if self.index_type == QuantizedIndexConfig.INDEX_TYPE_HNSW:
            vectors_mb = n_total * dim * 4 / (1024 * 1024)
            hnsw_overhead_mb = n_total * 2 * 4 / (1024 * 1024)
            total_mb = vectors_mb + hnsw_overhead_mb
            return {
                'vectors_mb': vectors_mb,
                'overhead_mb': hnsw_overhead_mb,
                'total_mb': total_mb
            }
        elif self.index_type == QuantizedIndexConfig.INDEX_TYPE_IVF:
            vectors_mb = n_total * dim * 4 / (1024 * 1024)
            centroids_mb = self.nlist * dim * 4 / (1024 * 1024)
            total_mb = vectors_mb + centroids_mb
            return {
                'vectors_mb': vectors_mb,
                'centroids_mb': centroids_mb,
                'total_mb': total_mb
            }
        elif self.index_type == QuantizedIndexConfig.INDEX_TYPE_IVFPQ:
            pq_vectors_mb = n_total * self.m / (1024 * 1024)
            centroids_mb = self.nlist * dim * 4 / (1024 * 1024)
            pq_centroids_mb = self.m * (2 ** self.nbits) * (dim // self.m) * 4 / (1024 * 1024)
            total_mb = pq_vectors_mb + centroids_mb + pq_centroids_mb
            return {
                'pq_vectors_mb': pq_vectors_mb,
                'centroids_mb': centroids_mb,
                'pq_centroids_mb': pq_centroids_mb,
                'total_mb': total_mb
            }
        
        return {'total_mb': 0.0}


class QuantizedVectorRAG:
    """支持多种索引类型的向量 RAG 系统"""
    
    DEFAULT_BATCH_SIZE = 512
    
    def __init__(
        self,
        chunks_file: str = None,
        index_file: str = None,
        collection_name: str = "rules",
        index_type: str = QuantizedIndexConfig.INDEX_TYPE_IVFPQ
    ):
        self.chunks_file = chunks_file
        self.index_file = index_file
        self.collection_name = collection_name
        self.index_type = index_type
        self.chunks = []
        self.quantized_index: Optional[QuantizedIndex] = None
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
                self.quantized_index = QuantizedIndex(index_type=self.index_type, dimension=self.embedding_dimension)
                self.quantized_index.load_index(self.index_file)
                print(f"[{self.collection_name}] Loaded {self.index_type} index from {self.index_file}")
            except Exception as e:
                print(f"[{self.collection_name}] Failed to load index: {e}")
                self.quantized_index = None
        
        if self.quantized_index is None and self.chunks:
            self._build_index()
    
    def _build_index(self, batch_size: int = None, progress_callback: Callable = None):
        """构建量化索引"""
        if not self.chunks:
            print(f"[{self.collection_name}] No chunks to index")
            return
        
        batch_size = batch_size or self.DEFAULT_BATCH_SIZE
        total = len(self.chunks)
        print(f"[{self.collection_name}] Building {self.index_type} index for {total} chunks...")
        
        texts = [chunk['content'] for chunk in self.chunks]
        
        if progress_callback:
            progress_callback(0, total, 'encoding')
        
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
        
        self.quantized_index = QuantizedIndex(index_type=self.index_type, dimension=embeddings.shape[1])
        
        if self.index_type == QuantizedIndexConfig.INDEX_TYPE_HNSW:
            self.quantized_index.build_hnsw_index(embeddings, progress_callback=progress_callback)
        elif self.index_type == QuantizedIndexConfig.INDEX_TYPE_IVF:
            self.quantized_index.build_ivf_index(embeddings, progress_callback=progress_callback)
        elif self.index_type == QuantizedIndexConfig.INDEX_TYPE_IVFPQ:
            self.quantized_index.build_ivfpq_index(embeddings, progress_callback=progress_callback)
        
        if self.index_file:
            self.quantized_index.save_index(self.index_file)
            if progress_callback:
                progress_callback(total, total, 'saved')
            print(f"[{self.collection_name}] Saved {self.index_type} index to {self.index_file}")
        
        mem_info = self.quantized_index.estimate_memory_usage()
        print(f"[{self.collection_name}] Estimated memory usage: {mem_info['total_mb']:.2f} MB")
    
    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        if self.quantized_index is None or self.quantized_index.index is None:
            return []
        
        query_embedding = get_shared_embedding_model().encode([query])
        distances, indices = self.quantized_index.search_quantized(query_embedding, top_k)
        
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
    
    def get_stats(self) -> Dict[str, Any]:
        source_counts = {}
        for chunk in self.chunks:
            source = chunk.get('metadata', {}).get('source', 'unknown')
            source_counts[source] = source_counts.get(source, 0) + 1
        
        mem_info = {}
        if self.quantized_index:
            mem_info = self.quantized_index.estimate_memory_usage()
        
        return {
            'chunk_count': len(self.chunks),
            'index_size': self.quantized_index.index.ntotal if self.quantized_index and self.quantized_index.index else 0,
            'dimension': self.embedding_dimension,
            'index_type': self.index_type,
            'source_distribution': source_counts,
            'unique_sources': len(source_counts),
            'memory_usage_mb': mem_info
        }

