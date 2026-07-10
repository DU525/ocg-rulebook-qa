"""
统一服务管理器 - 整合所有新功能模块

管理所有新功能模块的初始化、配置和使用。
"""

import logging
from typing import Optional
from app.db.hierarchical_vector_store import HierarchicalVectorStore
from app.services.enhanced_memory import EnhancedMemorySystem
from app.services.memory_retriever import MemoryRetriever
from app.services.semantic_router import SemanticRouter
from app.services.advanced_router import AdvancedRouter
from app.services.chunking_strategy import ChunkingStrategySystem
from app.services.tool_system import ToolRegistry

logger = logging.getLogger(__name__)


class UnifiedServiceManager:
    """统一服务管理器 - 单例模式"""

    _instance: Optional['UnifiedServiceManager'] = None

    def __init__(self):
        self.hierarchical_rag: Optional[HierarchicalVectorStore] = None
        self.memory_system: Optional[EnhancedMemorySystem] = None
        self.memory_retriever: Optional[MemoryRetriever] = None
        self.semantic_router: Optional[SemanticRouter] = None
        self.advanced_router: Optional[AdvancedRouter] = None
        self.chunking_system: Optional[ChunkingStrategySystem] = None
        self.tool_registry: Optional[ToolRegistry] = None
        self.structured_processor = None
        self.ocr_processor = None
        self.document_cleaner = None

        self._initialized = False

    @classmethod
    def get_instance(cls) -> 'UnifiedServiceManager':
        """获取单例实例"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def initialize(self, config: dict = None):
        """
        初始化所有服务

        Args:
            config: 可选的配置字典
        """
        if self._initialized:
            logger.warning("服务已初始化，跳过")
            return

        config = config or {}

        try:
            logger.info("开始初始化统一服务管理器...")

            # 1. 初始化分层 RAG
            self._init_hierarchical_rag(config)

            # 2. 初始化记忆系统
            self._init_memory_system(config)

            # 3. 初始化路由系统
            self._init_routing_system(config)

            # 4. 初始化分块系统
            self._init_chunking_system(config)

            # 5. 初始化工具系统
            self._init_tool_system(config)

            # 6. 初始化文档/表格/OCR 处理器（T1 集成）
            self._init_data_processors(config)

            self._initialized = True
            logger.info("✓ 统一服务管理器初始化完成")

        except Exception as e:
            logger.error(f"初始化失败: {e}")
            raise

    def _init_hierarchical_rag(self, config: dict):
        """初始化分层 RAG 系统"""
        try:
            persist_dir = config.get('hierarchical_rag_dir', './data/hierarchical')
            collection_name = config.get('hierarchical_collection', 'unified_hierarchical')

            self.hierarchical_rag = HierarchicalVectorStore(
                persist_directory=persist_dir,
                collection_name=collection_name
            )
            logger.info("✓ 分层 RAG 系统已初始化")
        except Exception as e:
            logger.warning(f"分层 RAG 初始化失败: {e}")
            self.hierarchical_rag = None

    def _init_memory_system(self, config: dict):
        """初始化增强记忆系统"""
        try:
            self.memory_system = EnhancedMemorySystem(
                max_short_term=config.get('max_short_term', 100),
                max_long_term=config.get('max_long_term', 1000),
                memory_ttl=config.get('memory_ttl', 3600)
            )

            self.memory_retriever = MemoryRetriever(
                memory_system=self.memory_system,
                embedding_model=config.get('embedding_model', 'text2vec')
            )
            logger.info("✓ 记忆系统已初始化")
        except Exception as e:
            logger.warning(f"记忆系统初始化失败: {e}")
            self.memory_system = None
            self.memory_retriever = None

    def _init_routing_system(self, config: dict):
        """初始化路由系统"""
        try:
            # 语义路由
            self.semantic_router = SemanticRouter(
                embedding_model=config.get('embedding_model', 'text2vec')
            )

            # 添加默认路由
            self._add_default_routes()

            # 高级路由
            self.advanced_router = AdvancedRouter(
                semantic_router=self.semantic_router,
                enable_feedback_learning=config.get('enable_feedback', True)
            )

            logger.info("✓ 路由系统已初始化")
        except Exception as e:
            logger.warning(f"路由系统初始化失败: {e}")
            self.semantic_router = None
            self.advanced_router = None

    def _add_default_routes(self):
        """添加默认路由配置"""
        if self.semantic_router is None:
            return

        # OCG 规则路由
        self.semantic_router.add_route(
            name="ocg_rules",
            description="游戏王OCG规则相关问题",
            examples=[
                "游戏王规则是什么",
                "怎么召唤怪兽",
                "陷阱卡怎么用",
                "禁止卡表",
                "召唤方式有哪些"
            ],
            keywords=["规则", "OCG", "游戏王", "召唤", "陷阱", "魔法"],
            route_type=None
        )

        # DM 规则路由
        self.semantic_router.add_route(
            name="dm_rules",
            description="游戏王DM(旧版)规则相关问题",
            examples=[
                "DM规则是什么",
                "地属性怪兽",
                "革命回合"
            ],
            keywords=["DM", "旧版", "大师规则", "地属性"],
            route_type=None
        )

        # 卡片查询路由
        self.semantic_router.add_route(
            name="card_query",
            description="卡片信息查询",
            examples=[
                "青眼白龙的效果",
                "黑魔术师怎么获得",
                "有哪些龙族卡"
            ],
            keywords=["卡片", "卡", "查卡", "效果", "怪兽"],
            route_type=None
        )

        # 策略建议路由
        self.semantic_router.add_route(
            name="strategy",
            description="游戏策略和建议",
            examples=[
                "怎么组卡组",
                "有什么战术建议",
                "新手用什么卡组好"
            ],
            keywords=["卡组", "战术", "策略", "建议", "组卡"],
            route_type=None
        )

        logger.info("✓ 默认路由已配置")

    def _init_chunking_system(self, config: dict):
        """初始化分块系统"""
        try:
            self.chunking_system = ChunkingStrategySystem(
                default_strategy=config.get('default_chunking', 'adaptive')
            )
            logger.info("✓ 分块系统已初始化")
        except Exception as e:
            logger.warning(f"分块系统初始化失败: {e}")
            self.chunking_system = None

    def _init_tool_system(self, config: dict):
        """初始化工具系统"""
        try:
            self.tool_registry = ToolRegistry()

            # 注册内置工具（如果模块可用）
            try:
                from app.services.agent_tools import (
                    RuleSearchTool,
                    CalculatorTool,
                    DateTimeTool
                )

                self.tool_registry.register_tool(RuleSearchTool())
                self.tool_registry.register_tool(CalculatorTool())
                self.tool_registry.register_tool(DateTimeTool())
            except ImportError:
                logger.warning("内置工具导入失败")

            logger.info("✓ 工具系统已初始化")
        except Exception as e:
            logger.warning(f"工具系统初始化失败: {e}")
            self.tool_registry = None

    def query_with_routing(
        self,
        query: str,
        user_id: str = None,
        enable_memory: bool = True,
        enable_hierarchical: bool = True
    ) -> dict:
        """
        统一的查询处理流程

        Args:
            query: 用户查询
            user_id: 用户ID（用于记忆）
            enable_memory: 是否启用记忆
            enable_hierarchical: 是否使用分层RAG

        Returns:
            dict: 处理结果
        """
        result = {
            'query': query,
            'route': None,
            'memory_context': None,
            'retrieved_docs': None,
            'answer': None,
            'metadata': {}
        }

        try:
            # 0. 查询预处理（智能分块接入 - 2026-06-01）
            pre = self.preprocess_query(query)
            result['metadata']['preprocess'] = pre

            # 1. 路由决策
            if self.advanced_router:
                route_result = self.advanced_router.route(query)
                result['route'] = {
                    'selected': route_result.selected_route,
                    'strategy': route_result.strategy_used.value,
                    'confidence': route_result.confidence
                }

            # 2. 记忆检索
            if enable_memory and self.memory_retriever:
                memories = self.memory_retriever.retrieve(query, limit=5)
                result['memory_context'] = [
                    {
                        'content': m.memory.content,
                        'score': m.score,
                        'type': m.memory.memory_type.value
                    }
                    for m in memories
                ]

            # 3. RAG 检索
            if enable_hierarchical and self.hierarchical_rag:
                docs = self.hierarchical_rag.search(
                    query=query,
                    top_k=5,
                    parent_top_k=10
                )
                result['retrieved_docs'] = [
                    {
                        'content': d.content,
                        'score': d.score,
                        'metadata': d.metadata
                    }
                    for d in docs
                ]

            return result

        except Exception as e:
            logger.error(f"查询处理失败: {e}")
            result['error'] = str(e)
            return result

    def add_memory(
        self,
        content: str,
        memory_type: str = 'episodic',
        importance: float = 0.5,
        tags: list = None,
        user_id: str = None
    ) -> str:
        """
        添加记忆

        Args:
            content: 记忆内容
            memory_type: 记忆类型
            importance: 重要性
            tags: 标签
            user_id: 用户ID

        Returns:
            str: 记忆ID
        """
        if not self.memory_system:
            raise RuntimeError("记忆系统未初始化")

        from app.services.enhanced_memory import MemoryType

        # 转换记忆类型
        type_map = {
            'episodic': MemoryType.EPISODIC,
            'factual': MemoryType.FACTUAL,
            'semantic': MemoryType.SEMANTIC,
            'working': MemoryType.WORKING
        }
        mem_type = type_map.get(memory_type.lower(), MemoryType.EPISODIC)

        return self.memory_system.add_memory(
            content=content,
            memory_type=mem_type,
            importance=importance,
            tags=set(tags) if tags else None,
            user_id=user_id
        )

    def _init_data_processors(self, config: dict):
        """初始化文档/表格/OCR 处理器（T1 集成 - 2026-06-01）"""
        try:
            from app.services.structured_data_processor import StructuredDataProcessor
            self.structured_processor = StructuredDataProcessor()
            logger.info("✓ 表格提取器已初始化 (StructuredDataProcessor)")
        except Exception as e:
            logger.warning(f"表格提取器初始化失败（可选模块）: {e}")
            self.structured_processor = None

        try:
            from app.services.ocr_processor import OCRProcessor
            self.ocr_processor = OCRProcessor()
            logger.info(f"✓ OCR 处理器已初始化 (available={self.ocr_processor._ocr_available})")
        except Exception as e:
            logger.warning(f"OCR 处理器初始化失败（可选模块）: {e}")
            self.ocr_processor = None

        try:
            from app.services.document_cleaner import DocumentCleaner
            self.document_cleaner = DocumentCleaner()
            logger.info("✓ 文档清理器已初始化 (DocumentCleaner)")
        except Exception as e:
            logger.warning(f"文档清理器初始化失败（可选模块）: {e}")
            self.document_cleaner = None

    def preprocess_query(self, query: str) -> dict:
        """
        查询预处理（智能分块接入主检索流程 - 2026-06-01）

        用途：在 RAG 检索前对 query 做轻量级分析，决定检索策略。
        返回一个 context dict，调用方可读 .get('strategy') 等字段。

        Args:
            query: 原始查询

        Returns:
            dict: {
                'original_query': str,
                'normalized_query': str,
                'strategy': str,            # 推荐的 chunking 策略
                'is_table_query': bool,     # 是否为表格型查询
                'is_definition_query': bool,
                'keywords': list[str],
            }
        """
        import re as _re

        result = {
            'original_query': query,
            'normalized_query': query.strip(),
            'strategy': 'adaptive',
            'is_table_query': False,
            'is_definition_query': False,
            'keywords': [],
        }

        normalized = query.strip()
        result['normalized_query'] = normalized

        # 1) 关键词提取（中文 + 英文，2 字以上）
        cn_keywords = _re.findall(r'[\u4e00-\u9fa5]{2,}', normalized)
        en_keywords = _re.findall(r'[A-Za-z]{3,}', normalized)
        result['keywords'] = list(dict.fromkeys(cn_keywords + en_keywords))[:10]

        # 2) 表格型查询识别
        table_signals = ['表格', '表 ', '效果表', '怪兽表', '魔法卡表', '陷阱卡表',
                         'table', 'list of', '一览']
        result['is_table_query'] = any(s in normalized.lower() for s in table_signals)

        # 3) 定义型查询识别
        definition_signals = ['什么是', '什么叫', '是什么', '定义', '含义',
                               'what is', 'what does', 'meaning of', '定义是']
        result['is_definition_query'] = any(s in normalized.lower() for s in definition_signals)

        # 4) 策略选择
        if result['is_table_query']:
            result['strategy'] = 'semantic'
        elif result['is_definition_query']:
            result['strategy'] = 'paragraph'
        elif len(normalized) > 80:
            result['strategy'] = 'semantic'
        else:
            result['strategy'] = 'adaptive'

        # 5) 尝试用 chunking_system 的 auto_select_strategy（如果已初始化）
        if self.chunking_system and hasattr(self.chunking_system, 'auto_select_strategy'):
            try:
                from app.services.chunking_strategy import ChunkingStrategy
                chosen = self.chunking_system.auto_select_strategy(normalized)
                result['strategy'] = chosen.value if hasattr(chosen, 'value') else str(chosen)
            except Exception as e:
                logger.debug(f"chunking_system.auto_select_strategy 跳过: {e}")

        return result

    def get_system_status(self) -> dict:
        """
        获取系统状态

        Returns:
            dict: 系统状态信息
        """
        status = {
            'initialized': self._initialized,
            'services': {}
        }

        services = [
            ('hierarchical_rag', '分层RAG'),
            ('memory_system', '记忆系统'),
            ('memory_retriever', '记忆检索'),
            ('semantic_router', '语义路由'),
            ('advanced_router', '高级路由'),
            ('chunking_system', '分块系统'),
            ('tool_registry', '工具系统'),
            ('structured_processor', '表格提取器'),
            ('ocr_processor', 'OCR处理器'),
            ('document_cleaner', '文档清理器'),
        ]

        for attr, name in services:
            service = getattr(self, attr)
            status['services'][name] = {
                'available': service is not None,
                'status': 'ready' if service else 'unavailable'
            }

            # 添加特定服务的统计信息
            if service and hasattr(service, 'get_collection_stats'):
                try:
                    if attr == 'hierarchical_rag':
                        stats = service.get_collection_stats()
                        status['services'][name]['stats'] = stats
                except:
                    pass

        return status


# 全局实例
_unified_manager: Optional[UnifiedServiceManager] = None


def get_unified_manager() -> UnifiedServiceManager:
    """获取统一服务管理器实例"""
    global _unified_manager
    if _unified_manager is None:
        _unified_manager = UnifiedServiceManager.get_instance()
    return _unified_manager


def init_unified_services(config: dict = None):
    """初始化统一服务"""
    manager = get_unified_manager()
    manager.initialize(config)
    return manager
