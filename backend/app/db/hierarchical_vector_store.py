"""Hierarchical Vector Store - 分层向量存储管理"""
import os
import logging
from typing import List, Dict, Any, Optional
from app.services.hierarchical_rag import (
    HierarchicalRAG,
    HierarchicalChunk,
    HierarchicalSearchResult
)

logger = logging.getLogger(__name__)


class HierarchicalVectorStore:
    """分层向量存储管理类
    
    提供与现有 VectorStore 类似的接口，用于管理分层检索的向量存储
    """
    
    def __init__(
        self,
        persist_directory: str,
        collection_name: str = "hierarchical_ocg"
    ):
        """
        Args:
            persist_directory: 持久化目录
            collection_name: 集合名称
        """
        self.persist_directory = persist_directory
        self.collection_name = collection_name
        
        # 构建文件路径
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../..'))
        self.chunks_file = os.path.join(
            project_root,
            'data',
            'chunks',
            f'{collection_name}_chunks.json'
        )
        self.parent_index_file = os.path.join(
            project_root,
            'data',
            'chunks',
            f'{collection_name}_parent_index.bin'
        )
        self.child_index_file = os.path.join(
            project_root,
            'data',
            'chunks',
            f'{collection_name}_child_index.bin'
        )
        
        # 确保数据目录存在
        os.makedirs(os.path.dirname(self.chunks_file), exist_ok=True)
        
        # 初始化 RAG 实例
        self._rag: Optional[HierarchicalRAG] = None
    
    def _get_or_init_rag(self) -> HierarchicalRAG:
        """获取或初始化 RAG 实例"""
        if self._rag is None:
            self._rag = HierarchicalRAG(
                chunks_file=self.chunks_file,
                parent_index_file=self.parent_index_file,
                child_index_file=self.child_index_file,
                collection_name=self.collection_name
            )
        return self._rag
    
    @property
    def embedding_dimension(self) -> int:
        return 768
    
    def add_document(
        self,
        content: str,
        metadata: Optional[Dict[str, Any]] = None,
        document_id: Optional[str] = None
    ):
        """添加文档到分层向量存储
        
        Args:
            content: 文档内容
            metadata: 文档元数据
            document_id: 文档ID（可选）
        """
        rag = self._get_or_init_rag()
        rag.add_document(content, metadata, document_id)
        logger.info(f"[{self.collection_name}] Document added to hierarchical store")
    
    def add_documents(
        self,
        documents: List[Dict[str, Any]]
    ):
        """批量添加文档
        
        Args:
            documents: 文档列表，每个文档包含 'content' 和可选的 'metadata'、'id'
        """
        for doc in documents:
            self.add_document(
                content=doc['content'],
                metadata=doc.get('metadata'),
                document_id=doc.get('id')
            )
    
    def search(
        self,
        query: str,
        top_k: int = 5,
        parent_top_k: int = 10,
        enable_rerank: bool = True,
        force_cpu: bool = False,
        return_formatted: bool = True
    ) -> List[Any]:
        """分层检索
        
        Args:
            query: 查询字符串
            top_k: 返回结果数量
            parent_top_k: 父块召回数量
            enable_rerank: 是否启用Cross-Encoder重排
            force_cpu: 是否强制使用CPU
            return_formatted: 是否返回格式化的字典结果
            
        Returns:
            检索结果列表
        """
        rag = self._get_or_init_rag()
        results = rag.search(
            query=query,
            top_k=top_k,
            parent_top_k=parent_top_k,
            enable_rerank=enable_rerank,
            force_cpu=force_cpu
        )
        
        if return_formatted:
            return self._format_results(results)
        
        return results
    
    def _format_results(
        self,
        results: List[HierarchicalSearchResult]
    ) -> List[Dict[str, Any]]:
        """将分层检索结果格式化为字典
        
        Args:
            results: 分层检索结果列表
            
        Returns:
            格式化后的结果列表
        """
        formatted = []
        
        for result in results:
            # 主结果使用父块内容 + 最佳子块
            main_content = result.parent_chunk.content
            if result.child_chunks:
                main_content += "\n\n" + result.child_chunks[0].content
            
            formatted_result = {
                'id': result.parent_chunk.id,
                'content': main_content,
                'metadata': result.parent_chunk.metadata,
                'parent_score': result.parent_score,
                'combined_score': result.combined_score,
                'distance': 1.0 / (1.0 + result.combined_score),
                # 子块信息
                'child_chunks': [
                    {
                        'id': child.id,
                        'content': child.content,
                        'score': result.child_scores.get(child.id, 0.0)
                    }
                    for child in result.child_chunks
                ]
            }
            formatted.append(formatted_result)
        
        return formatted
    
    def delete_by_metadata(
        self,
        key: str,
        value: Any,
        batch_size: int = None
    ):
        """根据元数据删除文档
        
        Args:
            key: 元数据键
            value: 元数据值
            batch_size: 重建索引的批次大小
        """
        rag = self._get_or_init_rag()
        
        # 过滤父块
        original_parent_count = len(rag.parent_chunks)
        rag.parent_chunks = [
            chunk for chunk in rag.parent_chunks
            if chunk.metadata.get(key) != value
        ]
        removed_parents = original_parent_count - len(rag.parent_chunks)
        
        if removed_parents == 0:
            logger.info(f"[{self.collection_name}] No parent chunks found with {key}={value}")
            return
        
        # 获取保留的父块ID
        kept_parent_ids = {chunk.id for chunk in rag.parent_chunks}
        
        # 过滤子块（只保留属于保留父块的子块）
        original_child_count = len(rag.child_chunks)
        rag.child_chunks = [
            chunk for chunk in rag.child_chunks
            if chunk.parent_id in kept_parent_ids
        ]
        removed_children = original_child_count - len(rag.child_chunks)
        
        # 重建ID映射
        rag.parent_id_map = {chunk.id: chunk for chunk in rag.parent_chunks}
        rag.child_id_map = {chunk.id: chunk for chunk in rag.child_chunks}
        
        # 重建索引
        rag._build_index(batch_size=batch_size)
        rag._save_chunks()
        
        logger.info(
            f"[{self.collection_name}] Removed {removed_parents} parent chunks, {removed_children} child chunks "
            f"where {key}={value}"
        )
    
    def delete_by_document_id(
        self,
        document_id: str,
        batch_size: int = None
    ):
        """根据文档ID删除文档
        
        Args:
            document_id: 文档ID
            batch_size: 重建索引的批次大小
        """
        self.delete_by_metadata('document_id', document_id, batch_size=batch_size)
    
    def clear(self):
        """清空所有数据"""
        rag = self._get_or_init_rag()
        rag.parent_chunks = []
        rag.child_chunks = []
        rag.parent_id_map = {}
        rag.child_id_map = {}
        rag.parent_index = None
        rag.child_index = None
        
        # 删除文件
        for file_path in [self.chunks_file, self.parent_index_file, self.child_index_file]:
            if os.path.exists(file_path):
                os.remove(file_path)
        
        rag._save_chunks()
        logger.info(f"[{self.collection_name}] Store cleared")
    
    def get_collection_stats(self) -> Dict[str, Any]:
        """获取集合统计信息
        
        Returns:
            统计信息字典
        """
        try:
            rag = self._get_or_init_rag()
            stats = rag.get_stats()
            return {
                'count': stats.get('parent_index_size', 0),
                'name': self.collection_name,
                'index_type': 'hierarchical_hnsw',
                'parent_chunk_count': stats.get('parent_chunk_count', 0),
                'child_chunk_count': stats.get('child_chunk_count', 0),
                'dimension': stats.get('dimension', 768)
            }
        except Exception as e:
            logger.error(f"[{self.collection_name}] Failed to get stats: {e}")
            return {
                'count': 0,
                'name': self.collection_name,
                'index_type': 'hierarchical_hnsw'
            }
    
    def get_parent_chunks(self) -> List[HierarchicalChunk]:
        """获取所有父块"""
        rag = self._get_or_init_rag()
        return rag.parent_chunks.copy()
    
    def get_child_chunks(self) -> List[HierarchicalChunk]:
        """获取所有子块"""
        rag = self._get_or_init_rag()
        return rag.child_chunks.copy()
