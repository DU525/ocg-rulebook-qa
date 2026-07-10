"""DM向量存储 - 薄包装类，使用统一的BaseVectorStore"""
from app.db.base_vector_store import BaseVectorStore, BaseVectorRAG
import os


class DMVectorRAG(BaseVectorRAG):
    """DM专用VectorRAG，仅配置路径"""
    def __init__(self, chunks_file=None, index_file=None):
        super().__init__(chunks_file, index_file, collection_name="dm_rules")


class DMVectorStore(BaseVectorStore):
    """DM向量存储管理"""

    COLLECTION_NAME = "dm_rules"
    _cached_rag = None

    def __init__(self, persist_directory: str):
        project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../'))
        chunks_file = os.path.join(project_root, 'data/chunks/dm_rules_chunks.json')
        index_file = os.path.join(project_root, 'data/chunks/dm_rules_index.bin')
        super().__init__(persist_directory, chunks_file, index_file, 'dm_rules', DMVectorRAG)

    def _get_or_init_rag(self) -> DMVectorRAG:
        if DMVectorStore._cached_rag is None:
            DMVectorStore._cached_rag = DMVectorRAG(
                chunks_file=self._chunks_file,
                index_file=self._index_file
            )
        return DMVectorStore._cached_rag
