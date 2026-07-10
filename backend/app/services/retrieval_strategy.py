"""检索策略管理器 - 根据查询意图动态调整检索参数

功能：
- 根据意图类型返回对应的检索配置
- 支持4种意图类型的差异化检索策略：
  * RULE_QUERY: top_k=3, BM25权重50%, 向量权重50%
  * CONCEPT_QUERY: top_k=8, BM25权重20%, 向量权重80%
  * COMPARE_QUERY: top_k=10, BM25权重40%, 向量权重60%
  * OPERATION_QUERY: top_k=5, BM25权重60%, 向量权重40%
- 统一接口：get_strategy(intent_type) -> RetrievalConfig
- 支持自定义策略和策略扩展

设计原则：
- 策略模式：每种意图对应一个预定义的检索配置
- 开闭原则：对扩展开放，对修改封闭
- 单一职责：只负责策略管理，不执行检索
"""
import logging
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, Optional, Any

from app.services.intent_classifier import IntentType

logger = logging.getLogger(__name__)


@dataclass
class RetrievalConfig:
    """检索配置数据类

    包含所有检索相关的参数，供检索引擎使用。

    Attributes:
        top_k: 返回结果数量
        bm25_weight: BM25检索权重（0.0-1.0）
        vector_weight: 向量检索权重（0.0-1.0）
        enable_rerank: 是否启用重排序
        rerank_top_k: 重排序候选数量
        min_score_threshold: 最低相关性阈值
        use_hybrid: 是否使用混合检索
        intent_type: 对应的意图类型
        description: 策略描述
        extra_params: 额外参数（用于扩展）
    """
    top_k: int = 5
    bm25_weight: float = 0.3
    vector_weight: float = 0.7
    enable_rerank: bool = False
    rerank_top_k: int = 20
    min_score_threshold: float = 0.0
    use_hybrid: bool = True
    intent_type: Optional[IntentType] = None
    description: str = ""
    extra_params: Dict[str, Any] = field(default_factory=dict)

    def validate(self) -> bool:
        """验证配置参数的有效性

        Returns:
            bool: 配置是否有效
        """
        if self.top_k <= 0:
            logger.warning(f"top_k 必须大于0: {self.top_k}")
            return False

        if not (0.0 <= self.bm25_weight <= 1.0):
            logger.warning(f"bm25_weight 必须在[0,1]范围: {self.bm25_weight}")
            return False

        if not (0.0 <= self.vector_weight <= 1.0):
            logger.warning(f"vector_weight 必须在[0,1]范围: {self.vector_weight}")
            return False

        if self.rerank_top_k < self.top_k:
            logger.warning(f"rerank_top_k 应 >= top_k: {self.rerank_top_k} < {self.top_k}")
            return False

        return True


class RetrievalStrategy:
    """检索策略管理器

    根据查询意图类型提供对应的检索配置。

    使用方式：
        strategy = RetrievalStrategy()
        config = strategy.get_strategy(IntentType.RULE_QUERY)
        # 使用 config 进行检索
    """

    def __init__(self):
        self.strategies: Dict[IntentType, RetrievalConfig] = self._build_default_strategies()

    def _build_default_strategies(self) -> Dict[IntentType, RetrievalConfig]:
        """构建默认的检索策略配置

        根据4种意图类型的特点，设计差异化的检索参数：

        RULE_QUERY（规则查询）:
            - top_k=3: 精确术语匹配，少量高相关结果即可
            - BM25=50%, Vector=50%: 均衡匹配，术语精确+语义理解

        CONCEPT_QUERY（概念查询）:
            - top_k=8: 抽象概念需要更多上下文
            - BM25=20%, Vector=80%: 侧重语义理解

        COMPARE_QUERY（对比查询）:
            - top_k=10: 对比需要更多候选项
            - BM25=40%, Vector=60%: 语义为主，术语为辅

        OPERATION_QUERY（操作查询）:
            - top_k=5: 操作步骤需要适量结果
            - BM25=60%, Vector=40%: 侧重关键词匹配

        Returns:
            Dict[IntentType, RetrievalConfig]: 各意图类型的检索配置
        """
        return {
            IntentType.RULE_QUERY: RetrievalConfig(
                top_k=3,
                bm25_weight=0.5,
                vector_weight=0.5,
                enable_rerank=True,
                rerank_top_k=10,
                min_score_threshold=0.3,
                use_hybrid=True,
                intent_type=IntentType.RULE_QUERY,
                description="规则查询策略：精确术语匹配，BM25和向量均衡权重",
                extra_params={
                    "focus": "exact_match",
                    "context_length": "short",
                },
            ),
            IntentType.CONCEPT_QUERY: RetrievalConfig(
                top_k=8,
                bm25_weight=0.2,
                vector_weight=0.8,
                enable_rerank=True,
                rerank_top_k=20,
                min_score_threshold=0.2,
                use_hybrid=True,
                intent_type=IntentType.CONCEPT_QUERY,
                description="概念查询策略：抽象概念理解，侧重向量语义检索",
                extra_params={
                    "focus": "semantic_understanding",
                    "context_length": "long",
                },
            ),
            IntentType.COMPARE_QUERY: RetrievalConfig(
                top_k=10,
                bm25_weight=0.4,
                vector_weight=0.6,
                enable_rerank=True,
                rerank_top_k=25,
                min_score_threshold=0.2,
                use_hybrid=True,
                intent_type=IntentType.COMPARE_QUERY,
                description="对比查询策略：多候选项对比，语义为主术语为辅",
                extra_params={
                    "focus": "comparison",
                    "context_length": "medium",
                    "need_multiple_entities": True,
                },
            ),
            IntentType.OPERATION_QUERY: RetrievalConfig(
                top_k=5,
                bm25_weight=0.6,
                vector_weight=0.4,
                enable_rerank=True,
                rerank_top_k=15,
                min_score_threshold=0.25,
                use_hybrid=True,
                intent_type=IntentType.OPERATION_QUERY,
                description="操作查询策略：操作步骤指导，侧重关键词精确匹配",
                extra_params={
                    "focus": "procedural",
                    "context_length": "medium",
                    "need_step_info": True,
                },
            ),
        }

    def get_strategy(self, intent_type: IntentType) -> RetrievalConfig:
        """根据意图类型获取检索策略

        Args:
            intent_type: 查询意图类型

        Returns:
            RetrievalConfig: 对应的检索配置

        Raises:
            ValueError: 当意图类型不支持时抛出异常
        """
        if intent_type is None or intent_type not in self.strategies:
            logger.warning(f"不支持的意图类型: {intent_type.value if intent_type else 'None'}")
            return self.get_default_strategy()

        config = self.strategies[intent_type]
        if not config.validate():
            logger.warning(f"检索配置验证失败: {intent_type.value}，使用默认配置")
            return self.get_default_strategy()

        return config

    def get_default_strategy(self) -> RetrievalConfig:
        """获取默认检索策略

        用于未知意图类型或配置验证失败时的降级方案。

        Returns:
            RetrievalConfig: 默认检索配置
        """
        return RetrievalConfig(
            top_k=5,
            bm25_weight=0.3,
            vector_weight=0.7,
            enable_rerank=False,
            rerank_top_k=15,
            min_score_threshold=0.2,
            use_hybrid=True,
            intent_type=None,
            description="默认检索策略：标准权重配置",
            extra_params={
                "focus": "balanced",
                "context_length": "medium",
            },
        )

    def register_strategy(
        self,
        intent_type: IntentType,
        config: RetrievalConfig,
    ):
        """注册新的检索策略

        Args:
            intent_type: 意图类型
            config: 检索配置
        """
        if not config.validate():
            logger.warning(f"注册策略验证失败: {intent_type.value}")
            return

        self.strategies[intent_type] = config
        config.intent_type = intent_type
        logger.info(f"已注册检索策略: {intent_type.value}")

    def update_strategy(
        self,
        intent_type: IntentType,
        **kwargs,
    ):
        """更新现有检索策略的参数

        Args:
            intent_type: 意图类型
            **kwargs: 要更新的参数
        """
        if intent_type not in self.strategies:
            logger.warning(f"意图类型不存在: {intent_type.value}")
            return

        config = self.strategies[intent_type]
        for key, value in kwargs.items():
            if hasattr(config, key):
                setattr(config, key, value)

        if not config.validate():
            logger.warning(f"更新后配置验证失败: {intent_type.value}")

    def get_all_strategies(self) -> Dict[IntentType, RetrievalConfig]:
        """获取所有检索策略

        Returns:
            Dict[IntentType, RetrievalConfig]: 所有策略配置
        """
        return self.strategies.copy()

    def get_strategy_summary(self) -> Dict[str, Dict[str, Any]]:
        """获取所有策略的摘要信息

        Returns:
            Dict[str, Dict[str, Any]]: 策略摘要，key为意图类型名称
        """
        summary = {}
        for intent_type, config in self.strategies.items():
            summary[intent_type.value] = {
                "top_k": config.top_k,
                "bm25_weight": config.bm25_weight,
                "vector_weight": config.vector_weight,
                "enable_rerank": config.enable_rerank,
                "description": config.description,
            }
        return summary


strategy_manager = RetrievalStrategy()


def get_strategy(intent_type: IntentType) -> RetrievalConfig:
    """便捷函数：获取检索策略

    Args:
        intent_type: 查询意图类型

    Returns:
        RetrievalConfig: 对应的检索配置
    """
    return strategy_manager.get_strategy(intent_type)


def get_default_strategy() -> RetrievalConfig:
    """便捷函数：获取默认检索策略

    Returns:
        RetrievalConfig: 默认检索配置
    """
    return strategy_manager.get_default_strategy()
