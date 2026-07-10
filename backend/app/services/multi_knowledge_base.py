"""
多知识库管理器 - 支持 OCG/DM 两套规则书切换
功能：
- 多知识库注册与切换
- 自动选择合适的知识库
- 知识库元数据管理
"""
import os
import logging
from typing import Dict, Any, Optional, List
from dataclasses import dataclass
from app.services.vector_rag import VectorRAG
from app.db.dm_vector_store import DMVectorRAG

logger = logging.getLogger(__name__)


@dataclass
class KnowledgeBase:
    """知识库配置"""
    id: str
    name: str
    description: str
    rag_class: type
    config: Dict[str, Any]
    enabled: bool = True


class MultiKnowledgeBaseManager:
    """多知识库管理器"""

    # 预定义知识库
    DEFAULT_KBS = [
        KnowledgeBase(
            id="ocg",
            name="游戏王OCG规则",
            description="游戏王OCG完整规则书",
            rag_class=VectorRAG,
            config={
                "chunks_file": "data/chunks/ocg_rules_chunks.json",
                "index_file": "data/chunks/ocg_rules_index.bin",
            },
        ),
        KnowledgeBase(
            id="dm",
            name="数码宝贝卡牌游戏规则",
            description="数码宝贝卡牌游戏(Digimon Card Game)规则",
            rag_class=DMVectorRAG,
            config={
                "chunks_file": "data/chunks/dm_rules_chunks.json",
                "index_file": "data/chunks/dm_rules_index.bin",
            },
        ),
    ]

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self.knowledge_bases: Dict[str, KnowledgeBase] = {}
        self._rag_instances: Dict[str, Any] = {}
        self._default_kb_id: str = "ocg"
        self._load_default_kbs()
        logger.info("多知识库管理器初始化完成")

    def _load_default_kbs(self) -> None:
        """加载默认知识库"""
        for kb in self.DEFAULT_KBS:
            self.knowledge_bases[kb.id] = kb
            logger.info(f"知识库已注册: {kb.id} ({kb.name})")

    def register_knowledge_base(self, kb: KnowledgeBase) -> None:
        """注册新的知识库"""
        self.knowledge_bases[kb.id] = kb
        logger.info(f"新知识库已注册: {kb.id} ({kb.name})")

    def get_knowledge_base(self, kb_id: str) -> Optional[KnowledgeBase]:
        """获取知识库"""
        return self.knowledge_bases.get(kb_id)

    def list_knowledge_bases(self) -> List[Dict[str, Any]]:
        """列出所有知识库"""
        return [
            {
                "id": kb.id,
                "name": kb.name,
                "description": kb.description,
                "enabled": kb.enabled,
            }
            for kb in self.knowledge_bases.values()
        ]

    def get_rag_instance(self, kb_id: Optional[str] = None) -> Any:
        """获取 RAG 实例（懒加载）"""
        target_kb_id = kb_id or self._default_kb_id

        if target_kb_id not in self.knowledge_bases:
            logger.warning(f"知识库不存在: {target_kb_id}, 使用默认知识库")
            target_kb_id = self._default_kb_id

        if target_kb_id not in self._rag_instances:
            kb = self.knowledge_bases[target_kb_id]
            project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../'))

            # 构建完整路径
            config = kb.config.copy()
            for key, path in config.items():
                if isinstance(path, str) and not os.path.isabs(path):
                    config[key] = os.path.join(project_root, path)

            try:
                self._rag_instances[target_kb_id] = kb.rag_class(**config)
                logger.info(f"RAG 实例已加载: {target_kb_id}")
            except Exception as e:
                logger.error(f"加载 RAG 实例失败: {target_kb_id}, 错误: {e}")
                if target_kb_id != self._default_kb_id:
                    logger.info(f"回退到默认知识库: {self._default_kb_id}")
                    return self.get_rag_instance(self._default_kb_id)
                raise

        return self._rag_instances[target_kb_id]

    def set_default_knowledge_base(self, kb_id: str) -> bool:
        """设置默认知识库"""
        if kb_id in self.knowledge_bases:
            self._default_kb_id = kb_id
            logger.info(f"默认知识库已设置: {kb_id}")
            return True
        logger.warning(f"无法设置默认知识库: {kb_id} 不存在")
        return False

    def get_default_knowledge_base_id(self) -> str:
        """获取默认知识库 ID"""
        return self._default_kb_id

    def auto_select_knowledge_base(self, query: str) -> str:
        """根据查询内容自动选择知识库"""
        query_lower = query.lower()

        # 关键词匹配
        dm_keywords = ["数码宝贝", "digimon", "dm", "数码暴龙", "数码兽"]
        ocg_keywords = ["游戏王", "ocg", "yugioh", "遊戯王"]

        has_dm = any(kw in query_lower for kw in dm_keywords)
        has_ocg = any(kw in query_lower for kw in ocg_keywords)

        if has_dm and not has_ocg:
            return "dm"
        elif has_ocg and not has_dm:
            return "ocg"

        # 默认返回
        return self._default_kb_id

    def search(self, query: str, kb_id: Optional[str] = None, top_k: int = 5) -> Dict[str, Any]:
        """搜索知识库（统一接口）"""
        selected_kb = kb_id or self.auto_select_knowledge_base(query)
        rag = self.get_rag_instance(selected_kb)

        try:
            results = rag.search(query, top_k=top_k)
            return {
                "success": True,
                "kb_id": selected_kb,
                "kb_name": self.knowledge_bases[selected_kb].name,
                "results": results,
            }
        except Exception as e:
            logger.error(f"搜索失败: {selected_kb}, 错误: {e}")
            return {
                "success": False,
                "kb_id": selected_kb,
                "error": str(e),
                "results": [],
            }

    def reload_knowledge_base(self, kb_id: str) -> bool:
        """重新加载知识库"""
        if kb_id in self._rag_instances:
            del self._rag_instances[kb_id]
            logger.info(f"知识库已卸载: {kb_id}")

        # 重新加载
        try:
            self.get_rag_instance(kb_id)
            logger.info(f"知识库已重新加载: {kb_id}")
            return True
        except Exception as e:
            logger.error(f"重新加载知识库失败: {kb_id}, 错误: {e}")
            return False


def get_multi_kb_manager() -> MultiKnowledgeBaseManager:
    """获取多知识库管理器单例"""
    return MultiKnowledgeBaseManager()

