"""Hierarchical RAG - 分层检索增强生成系统"""
import os
import json
import logging
import faiss
import numpy as np
from typing import List, Dict, Any, Optional, Tuple
from dataclasses import dataclass, field
from app.services.vector_rag import get_shared_embedding_model
from app.services.cross_encoder_reranker import get_cross_encoder_reranker

logger = logging.getLogger(__name__)


@dataclass
class HierarchicalChunk:
    """分层分块数据结构 - 包含父子块关系"""
    id: str
    content: str
    level: int  # 0: 父块, 1: 子块
    parent_id: Optional[str] = None  # 父块ID（仅子块有）
    child_ids: List[str] = field(default_factory=list)  # 子块ID列表（仅父块有）
    metadata: Dict[str, Any] = field(default_factory=dict)
    embedding: Optional[np.ndarray] = None


@dataclass
class HierarchicalSearchResult:
    """分层检索结果"""
    parent_chunk: HierarchicalChunk
    child_chunks: List[HierarchicalChunk]
    parent_score: float
    child_scores: Dict[str, float]
    combined_score: float


class HierarchicalRAG:
    """分层检索RAG系统
    
    实现策略：
    1. 父块检索：大粒度分块（2048-4096字符），快速召回相关文档
    2. 子块精排：小粒度分块（256-512字符），基于父块结果进行精细排序
    3. 元数据继承：子块继承父块的元数据
    """
    
    # 父块参数
    PARENT_CHUNK_SIZE = 3072
    PARENT_CHUNK_OVERLAP = 512
    
    # 子块参数
    CHILD_CHUNK_SIZE = 384
    CHILD_CHUNK_OVERLAP = 64
    
    # HNSW索引参数
    HNSW_M = 8
    HNSW_EF_CONSTRUCTION = 128
    HNSW_EF_SEARCH = 32
    
    # 批量嵌入参数
    DEFAULT_BATCH_SIZE = 512
    
    def __init__(
        self,
        chunks_file: str = None,
        parent_index_file: str = None,
        child_index_file: str = None,
        collection_name: str = "hierarchical"
    ):
        self.chunks_file = chunks_file
        self.parent_index_file = parent_index_file
        self.child_index_file = child_index_file
        self.collection_name = collection_name
        
        # 存储结构
        self.parent_chunks: List[HierarchicalChunk] = []
        self.child_chunks: List[HierarchicalChunk] = []
        self.parent_index: Optional[faiss.IndexHNSWFlat] = None
        self.child_index: Optional[faiss.IndexHNSWFlat] = None
        
        # 快速查找映射
        self.parent_id_map: Dict[str, HierarchicalChunk] = {}
        self.child_id_map: Dict[str, HierarchicalChunk] = {}
        
        # 加载或构建索引
        self._load_or_build_index()
    
    @property
    def embedding_dimension(self) -> int:
        return 768
    
    @property
    def embedding_model(self):
        return get_shared_embedding_model()
    
    def _load_or_build_index(self):
        """加载已有索引或构建新索引"""
        # 尝试加载分块数据
        if self.chunks_file and os.path.exists(self.chunks_file):
            self._load_chunks()
        
        # 尝试加载父块索引
        if self.parent_index_file and os.path.exists(self.parent_index_file):
            try:
                self.parent_index = faiss.read_index(self.parent_index_file)
                logger.info(f"[{self.collection_name}] Loaded parent FAISS index from {self.parent_index_file}")
            except Exception as e:
                logger.warning(f"[{self.collection_name}] Failed to load parent index: {e}")
                self.parent_index = None
        
        # 尝试加载子块索引
        if self.child_index_file and os.path.exists(self.child_index_file):
            try:
                self.child_index = faiss.read_index(self.child_index_file)
                logger.info(f"[{self.collection_name}] Loaded child FAISS index from {self.child_index_file}")
            except Exception as e:
                logger.warning(f"[{self.collection_name}] Failed to load child index: {e}")
                self.child_index = None
        
        # 如果有分块但没有索引，构建索引
        if (self.parent_chunks and self.parent_index is None) or \
           (self.child_chunks and self.child_index is None):
            self._build_index()
    
    def _load_chunks(self):
        """从文件加载分块数据"""
        with open(self.chunks_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
        
        # 重建父块
        for chunk_data in data.get('parents', []):
            chunk = HierarchicalChunk(
                id=chunk_data['id'],
                content=chunk_data['content'],
                level=0,
                child_ids=chunk_data.get('child_ids', []),
                metadata=chunk_data.get('metadata', {})
            )
            self.parent_chunks.append(chunk)
            self.parent_id_map[chunk.id] = chunk
        
        # 重建子块
        for chunk_data in data.get('children', []):
            chunk = HierarchicalChunk(
                id=chunk_data['id'],
                content=chunk_data['content'],
                level=1,
                parent_id=chunk_data.get('parent_id'),
                metadata=chunk_data.get('metadata', {})
            )
            self.child_chunks.append(chunk)
            self.child_id_map[chunk.id] = chunk
        
        logger.info(f"[{self.collection_name}] Loaded {len(self.parent_chunks)} parent chunks, {len(self.child_chunks)} child chunks")
    
    def _save_chunks(self):
        """保存分块数据到文件"""
        if not self.chunks_file:
            return
        
        data = {
            'parents': [
                {
                    'id': chunk.id,
                    'content': chunk.content,
                    'child_ids': chunk.child_ids,
                    'metadata': chunk.metadata
                }
                for chunk in self.parent_chunks
            ],
            'children': [
                {
                    'id': chunk.id,
                    'content': chunk.content,
                    'parent_id': chunk.parent_id,
                    'metadata': chunk.metadata
                }
                for chunk in self.child_chunks
            ]
        }
        
        os.makedirs(os.path.dirname(self.chunks_file), exist_ok=True)
        with open(self.chunks_file, 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        
        logger.info(f"[{self.collection_name}] Saved chunks to {self.chunks_file}")
    
    def _build_index(self, batch_size: int = None):
        """构建FAISS HNSW索引
        
        Args:
            batch_size: 每批处理的块数
        """
        batch_size = batch_size or self.DEFAULT_BATCH_SIZE
        
        # 构建父块索引
        if self.parent_chunks:
            self._build_parent_index(batch_size)
        
        # 构建子块索引
        if self.child_chunks:
            self._build_child_index(batch_size)
    
    def _build_parent_index(self, batch_size: int):
        """构建父块索引"""
        logger.info(f"[{self.collection_name}] Building parent index for {len(self.parent_chunks)} chunks")
        
        texts = [chunk.content for chunk in self.parent_chunks]
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            batch_embeddings = self.embedding_model.encode(batch)
            all_embeddings.append(batch_embeddings)
            logger.info(f"  Parent [{min(i+batch_size, len(texts))}/{len(texts)}] embeddings computed")
        
        embeddings = np.vstack(all_embeddings)
        if len(embeddings.shape) == 1:
            embeddings = embeddings.reshape(1, -1)
        
        dimension = embeddings.shape[1]
        self.parent_index = faiss.IndexHNSWFlat(dimension, self.HNSW_M)
        self.parent_index.hnsw.efConstruction = self.HNSW_EF_CONSTRUCTION
        self.parent_index.add(embeddings.astype('float32'))
        
        # 存储嵌入向量
        for i, chunk in enumerate(self.parent_chunks):
            chunk.embedding = embeddings[i]
        
        logger.info(f"[{self.collection_name}] Built parent index with {self.parent_index.ntotal} vectors")
        
        if self.parent_index_file:
            faiss.write_index(self.parent_index, self.parent_index_file)
            logger.info(f"[{self.collection_name}] Saved parent index to {self.parent_index_file}")
    
    def _build_child_index(self, batch_size: int):
        """构建子块索引"""
        logger.info(f"[{self.collection_name}] Building child index for {len(self.child_chunks)} chunks")
        
        texts = [chunk.content for chunk in self.child_chunks]
        all_embeddings = []
        
        for i in range(0, len(texts), batch_size):
            batch = texts[i:i+batch_size]
            batch_embeddings = self.embedding_model.encode(batch)
            all_embeddings.append(batch_embeddings)
            logger.info(f"  Child [{min(i+batch_size, len(texts))}/{len(texts)}] embeddings computed")
        
        embeddings = np.vstack(all_embeddings)
        if len(embeddings.shape) == 1:
            embeddings = embeddings.reshape(1, -1)
        
        dimension = embeddings.shape[1]
        self.child_index = faiss.IndexHNSWFlat(dimension, self.HNSW_M)
        self.child_index.hnsw.efConstruction = self.HNSW_EF_CONSTRUCTION
        self.child_index.add(embeddings.astype('float32'))
        
        # 存储嵌入向量
        for i, chunk in enumerate(self.child_chunks):
            chunk.embedding = embeddings[i]
        
        logger.info(f"[{self.collection_name}] Built child index with {self.child_index.ntotal} vectors")
        
        if self.child_index_file:
            faiss.write_index(self.child_index, self.child_index_file)
            logger.info(f"[{self.collection_name}] Saved child index to {self.child_index_file}")
    
    def add_document(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        document_id: Optional[str] = None
    ) -> Tuple[HierarchicalChunk, List[HierarchicalChunk]]:
        """添加文档并创建分层分块
        
        Args:
            content: 文档内容
            metadata: 文档元数据
            document_id: 文档ID（可选）
            
        Returns:
            (父块, 子块列表)
        """
        import uuid
        from typing import List as TypingList
        
        doc_id = document_id or f"doc_{uuid.uuid4().hex[:8]}"
        metadata = metadata or {}
        
        # 步骤1: 创建父块（大粒度）
        parent_chunks = self._split_text(
            content,
            chunk_size=self.PARENT_CHUNK_SIZE,
            chunk_overlap=self.PARENT_CHUNK_OVERLAP
        )
        
        all_parents = []
        all_children = []
        
        for i, parent_text in enumerate(parent_chunks):
            parent_id = f"{doc_id}_parent_{i}"
            
            # 创建父块元数据（继承文档元数据）
            parent_metadata = metadata.copy()
            parent_metadata.update({
                'document_id': doc_id,
                'chunk_index': i,
                'is_parent': True
            })
            
            parent_chunk = HierarchicalChunk(
                id=parent_id,
                content=parent_text,
                level=0,
                metadata=parent_metadata
            )
            
            # 步骤2: 为每个父块创建子块（小粒度）
            child_chunks = self._split_text(
                parent_text,
                chunk_size=self.CHILD_CHUNK_SIZE,
                chunk_overlap=self.CHILD_CHUNK_OVERLAP
            )
            
            child_list = []
            for j, child_text in enumerate(child_chunks):
                child_id = f"{doc_id}_child_{i}_{j}"
                
                # 子块元数据：继承父块元数据
                child_metadata = parent_metadata.copy()
                child_metadata.update({
                    'parent_id': parent_id,
                    'child_index': j,
                    'is_parent': False
                })
                
                child_chunk = HierarchicalChunk(
                    id=child_id,
                    content=child_text,
                    level=1,
                    parent_id=parent_id,
                    metadata=child_metadata
                )
                
                child_list.append(child_chunk)
                all_children.append(child_chunk)
                self.child_id_map[child_id] = child_chunk
            
            # 更新父块的子块ID列表
            parent_chunk.child_ids = [child.id for child in child_list]
            
            all_parents.append(parent_chunk)
            self.parent_chunks.append(parent_chunk)
            self.parent_id_map[parent_id] = parent_chunk
        
        self.child_chunks.extend(all_children)
        
        # 保存并重建索引
        self._save_chunks()
        self._build_index()
        
        if len(all_parents) == 1:
            return all_parents[0], all_children
        return all_parents, all_children
    
    def _split_text(self, text: str, chunk_size: int, chunk_overlap: int) -> List[str]:
        """智能文本分块，保留句子完整性
        
        Args:
            text: 输入文本
            chunk_size: 块大小
            chunk_overlap: 块重叠大小
            
        Returns:
            分块列表
        """
        import re
        
        chunks = []
        paragraphs = text.split('\n\n')
        current_chunk = ""
        
        for para in paragraphs:
            para = para.strip()
            if not para:
                continue
            
            if len(para) > chunk_size:
                # 段落过长，按句子拆分
                if current_chunk:
                    chunks.append(current_chunk)
                    current_chunk = ""
                
                sentences = re.split(r'([。！？；.!?;])', para)
                for i in range(0, len(sentences) - 1, 2):
                    sentence = sentences[i] + (sentences[i+1] if i+1 < len(sentences) else '')
                    if len(current_chunk) + len(sentence) > chunk_size:
                        if current_chunk:
                            chunks.append(current_chunk)
                        # 保留重叠
                        current_chunk = sentence[-chunk_overlap:] if len(sentence) > chunk_overlap else sentence
                    else:
                        current_chunk += sentence
            else:
                # 段落较短，直接添加
                if len(current_chunk) + len(para) > chunk_size:
                    chunks.append(current_chunk)
                    current_chunk = para
                else:
                    current_chunk += '\n\n' + para if current_chunk else para
        
        if current_chunk:
            chunks.append(current_chunk)
        
        return chunks
    
    def search(
        self,
        query: str,
        top_k: int = 5,
        parent_top_k: int = 10,
        enable_rerank: bool = True,
        force_cpu: bool = False
    ) -> List[HierarchicalSearchResult]:
        """分层检索：父块召回 + 子块精排
        
        Args:
            query: 查询字符串
            top_k: 返回结果数量
            parent_top_k: 父块召回数量
            enable_rerank: 是否启用Cross-Encoder重排
            force_cpu: 是否强制使用CPU
            
        Returns:
            分层检索结果列表
        """
        # 步骤1: 父块检索（快速召回）
        parent_results = self._search_parents(query, parent_top_k)
        if not parent_results:
            return []
        
        # 步骤2: 对召回的父块，检索其子块
        all_child_results = []
        for parent_chunk, parent_score in parent_results:
            child_results = self._search_children_of_parent(query, parent_chunk)
            all_child_results.extend([
                (child_chunk, parent_chunk, child_score, parent_score)
                for child_chunk, child_score in child_results
            ])
        
        if not all_child_results:
            # 如果没有子块结果，返回父块结果
            return [
                HierarchicalSearchResult(
                    parent_chunk=parent_chunk,
                    child_chunks=[],
                    parent_score=parent_score,
                    child_scores={},
                    combined_score=parent_score
                )
                for parent_chunk, parent_score in parent_results[:top_k]
            ]
        
        # 步骤3: 按父块分组
        parent_groups: Dict[str, Dict] = {}
        for child_chunk, parent_chunk, child_score, parent_score in all_child_results:
            if parent_chunk.id not in parent_groups:
                parent_groups[parent_chunk.id] = {
                    'parent': parent_chunk,
                    'parent_score': parent_score,
                    'children': []
                }
            parent_groups[parent_chunk.id]['children'].append((child_chunk, child_score))
        
        # 步骤4: 构建结果并计算综合分数
        results = []
        for group in parent_groups.values():
            parent_chunk = group['parent']
            parent_score = group['parent_score']
            children_with_scores = group['children']
            
            # 取最高分数的子块
            children_with_scores.sort(key=lambda x: x[1], reverse=True)
            top_child_score = children_with_scores[0][1] if children_with_scores else 0.0
            
            # 综合分数：父块分数 * 0.4 + 子块分数 * 0.6
            combined_score = parent_score * 0.4 + top_child_score * 0.6
            
            results.append(HierarchicalSearchResult(
                parent_chunk=parent_chunk,
                child_chunks=[child for child, _ in children_with_scores],
                parent_score=parent_score,
                child_scores={child.id: score for child, score in children_with_scores},
                combined_score=combined_score
            ))
        
        # 按综合分数排序
        results.sort(key=lambda x: x.combined_score, reverse=True)
        
        # 步骤5: Cross-Encoder重排（可选）
        if enable_rerank and len(results) > 0:
            results = self._rerank_results(query, results, top_k, force_cpu)
        
        return results[:top_k]
    
    def _search_parents(self, query: str, top_k: int) -> List[Tuple[HierarchicalChunk, float]]:
        """检索父块"""
        if self.parent_index is None or self.parent_index.ntotal == 0:
            return []
        
        if hasattr(self.parent_index, 'hnsw'):
            self.parent_index.hnsw.efSearch = self.HNSW_EF_SEARCH
        
        query_embedding = self.embedding_model.encode([query])
        if len(query_embedding.shape) == 1:
            query_embedding = query_embedding.reshape(1, -1)
        
        distances, indices = self.parent_index.search(query_embedding.astype('float32'), top_k)
        
        results = []
        for i, idx in enumerate(indices[0]):
            if 0 <= idx < len(self.parent_chunks):
                chunk = self.parent_chunks[idx]
                score = 1.0 / (1.0 + float(distances[0][i]))
                results.append((chunk, score))
        
        return results
    
    def _search_children_of_parent(
        self,
        query: str,
        parent_chunk: HierarchicalChunk
    ) -> List[Tuple[HierarchicalChunk, float]]:
        """检索指定父块的子块"""
        if not parent_chunk.child_ids:
            return []
        
        # 获取该父块的所有子块
        children = [self.child_id_map[child_id] for child_id in parent_chunk.child_ids if child_id in self.child_id_map]
        if not children:
            return []
        
        # 计算子块与查询的相似度
        query_embedding = self.embedding_model.encode([query])[0]
        
        results = []
        for child in children:
            if child.embedding is None:
                # 如果没有预计算嵌入，实时计算
                child.embedding = self.embedding_model.encode([child.content])[0]
            
            # 计算余弦相似度
            similarity = self._cosine_similarity(query_embedding, child.embedding)
            results.append((child, similarity))
        
        # 按相似度排序
        results.sort(key=lambda x: x[1], reverse=True)
        return results
    
    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """计算余弦相似度"""
        dot = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot / (norm1 * norm2)
    
    def _rerank_results(
        self,
        query: str,
        results: List[HierarchicalSearchResult],
        top_k: int,
        force_cpu: bool
    ) -> List[HierarchicalSearchResult]:
        """使用Cross-Encoder重排结果"""
        reranker = get_cross_encoder_reranker(force_cpu=force_cpu)
        if not reranker or not reranker.is_loaded:
            logger.warning(f"[{self.collection_name}] Cross-Encoder not available, skipping rerank")
            return results
        
        # 准备重排文档：使用父块+最佳子块组合
        docs_for_rerank = []
        for result in results:
            doc_content = result.parent_chunk.content
            if result.child_chunks:
                doc_content += "\n\n" + result.child_chunks[0].content
            
            docs_for_rerank.append({
                'id': result.parent_chunk.id,
                'content': doc_content,
                'metadata': result.parent_chunk.metadata
            })
        
        # 重排
        reranked = reranker.rerank(query, docs_for_rerank, top_k=len(results))
        
        # 重建结果顺序
        reranked_ids = [doc['id'] for doc in reranked]
        id_to_result = {result.parent_chunk.id: result for result in results}
        
        final_results = []
        for doc_id in reranked_ids:
            if doc_id in id_to_result:
                result = id_to_result[doc_id]
                # 更新综合分数为重排分数
                result.combined_score = doc.get('rerank_score', result.combined_score)
                final_results.append(result)
        
        return final_results[:top_k]
    
    def get_stats(self) -> Dict[str, Any]:
        """获取统计信息"""
        return {
            'parent_chunk_count': len(self.parent_chunks),
            'child_chunk_count': len(self.child_chunks),
            'parent_index_size': self.parent_index.ntotal if self.parent_index else 0,
            'child_index_size': self.child_index.ntotal if self.child_index else 0,
            'dimension': self.embedding_dimension,
            'collection_name': self.collection_name
        }
