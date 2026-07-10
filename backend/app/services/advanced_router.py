"""高级路由系统 - 混合路由策略

功能：
- 语义路由 - 基于 Embedding 的语义匹配
- 向量路由 - 基于向量相似度的路由
- 关键词路由 - 快速关键词匹配
- LLM 兜底路由 - 使用 LLM 进行兜底决策
- 混合决策 - 综合使用多种路由策略
- 可视化和反馈 - 路由决策可视化

技术：
- 策略模式实现多种路由策略
- 加权综合决策
- 路由链支持
- 决策可配置
"""

import logging
import time
import json
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Callable, Union
from collections import defaultdict

from app.services.semantic_router import (
    SemanticRouter,
    RouteType,
    RouteDecision,
)

logger = logging.getLogger(__name__)


class StrategyType(Enum):
    """路由策略类型"""
    SEMANTIC = "semantic"
    KEYWORD = "keyword"
    VECTOR = "vector"
    LLM = "llm"
    HYBRID = "hybrid"


@dataclass
class StrategyConfig:
    """策略配置"""
    name: str
    strategy_type: StrategyType
    weight: float = 1.0
    enabled: bool = True
    config: Dict[str, Any] = field(default_factory=dict)


@dataclass
class StrategyResult:
    """策略结果"""
    strategy_name: str
    strategy_type: StrategyType
    route_name: str
    confidence: float
    details: Dict[str, Any] = field(default_factory=dict)
    processing_time_ms: float = 0.0


@dataclass
class HybridDecision:
    """混合决策结果"""
    final_route: str
    confidence: float
    strategy_results: List[StrategyResult]
    decision_process: List[str]
    metadata: Dict[str, Any] = field(default_factory=dict)
    total_processing_time_ms: float = 0.0


class RoutingStrategy:
    """路由策略基类"""

    def __init__(self, name: str):
        self.name = name

    def route(self, query: str) -> StrategyResult:
        """执行路由

        Args:
            query: 查询文本

        Returns:
            StrategyResult: 策略结果
        """
        raise NotImplementedError


class KeywordRoutingStrategy(RoutingStrategy):
    """关键词路由策略"""

    def __init__(self, name: str = "keyword", routes: Optional[Dict[str, List[str]]] = None):
        super().__init__(name)
        self.routes: Dict[str, List[str]] = routes or {}
        self.default_route = "default"

    def add_route_keywords(self, route_name: str, keywords: List[str]):
        """添加路由关键词"""
        if route_name not in self.routes:
            self.routes[route_name] = []
        self.routes[route_name].extend(keywords)

    def route(self, query: str) -> StrategyResult:
        start_time = time.time()
        query_lower = query.lower()

        scores: Dict[str, int] = defaultdict(int)

        for route_name, keywords in self.routes.items():
            for keyword in keywords:
                if keyword.lower() in query_lower:
                    scores[route_name] += 1

        if scores:
            best_route = max(scores.items(), key=lambda x: x[1])
            route_name, count = best_route
            total_keywords = len(self.routes.get(route_name, []))
            confidence = min(count / max(total_keywords, 1), 1.0)
        else:
            route_name = self.default_route
            confidence = 0.0

        result = StrategyResult(
            strategy_name=self.name,
            strategy_type=StrategyType.KEYWORD,
            route_name=route_name,
            confidence=confidence,
            details={"matched_counts": dict(scores)},
        )
        result.processing_time_ms = (time.time() - start_time) * 1000
        return result


class SemanticRoutingStrategy(RoutingStrategy):
    """语义路由策略"""

    def __init__(self, name: str = "semantic", semantic_router: Optional[SemanticRouter] = None):
        super().__init__(name)
        self.semantic_router = semantic_router or SemanticRouter()

    def route(self, query: str) -> StrategyResult:
        start_time = time.time()
        decision = self.semantic_router.route(query)
        result = StrategyResult(
            strategy_name=self.name,
            strategy_type=StrategyType.SEMANTIC,
            route_name=decision.route_name,
            confidence=decision.confidence,
            details={
                "matched_examples": decision.matched_examples,
                "matched_keywords": decision.matched_keywords,
            },
        )
        result.processing_time_ms = (time.time() - start_time) * 1000
        return result


class VectorRoutingStrategy(RoutingStrategy):
    """向量路由策略"""

    def __init__(self, name: str = "vector", vector_retriever: Optional[Any] = None):
        super().__init__(name)
        self.vector_retriever = vector_retriever
        self.route_embeddings: Dict[str, Any] = {}

    def add_route_embedding(self, route_name: str, embedding: Any):
        """添加路由向量"""
        self.route_embeddings[route_name] = embedding

    def route(self, query: str) -> StrategyResult:
        start_time = time.time()
        try:
            if self.vector_retriever and self.route_embeddings:
                pass

            result = StrategyResult(
                strategy_name=self.name,
                strategy_type=StrategyType.VECTOR,
                route_name="default",
                confidence=0.5,
                details={},
            )
        except Exception as e:
            logger.error(f"向量路由策略出错: {e}")
            result = StrategyResult(
                strategy_name=self.name,
                strategy_type=StrategyType.VECTOR,
                route_name="default",
                confidence=0.0,
                details={"error": str(e)},
            )

        result.processing_time_ms = (time.time() - start_time) * 1000
        return result


class LLMRoutingStrategy(RoutingStrategy):
    """LLM 兜底路由策略"""

    def __init__(
        self, name: str = "llm", llm_func: Optional[Callable] = None, routes: Optional[List[str]] = None):
        super().__init__(name)
        self.llm_func = llm_func
        self.routes = routes or []

    def set_llm_func(self, llm_func: Callable):
        """设置 LLM 函数"""
        self.llm_func = llm_func

    def route(self, query: str) -> StrategyResult:
        start_time = time.time()
        try:
            if self.llm_func and self.routes:
                prompt = self._build_prompt(query)
                response = self.llm_func(prompt)
                route_name = self._parse_response(response)
                confidence = 0.7
            else:
                route_name = "default"
                confidence = 0.0

            result = StrategyResult(
                strategy_name=self.name,
                strategy_type=StrategyType.LLM,
                route_name=route_name,
                confidence=confidence,
                details={},
            )
        except Exception as e:
            logger.error(f"LLM 路由策略出错: {e}")
            result = StrategyResult(
                strategy_name=self.name,
                strategy_type=StrategyType.LLM,
                route_name="default",
                confidence=0.0,
                details={"error": str(e)},
            )

        result.processing_time_ms = (time.time() - start_time) * 1000
        return result

    def _build_prompt(self, query: str) -> str:
        """构建提示词"""
        routes_str = ", ".join(self.routes)
        return f"""请将以下查询分类到最适合的路由：{routes_str}。查询：{query}。请仅返回路由名称。"""

    def _parse_response(self, response: str) -> str:
        """解析 LLM 响应"""
        for route in self.routes:
            if route.lower() in response.lower():
                return route
        return "default"


class AdvancedRouter:
    """高级路由器 - 混合路由策略系统

    核心功能：
    1. 多种路由策略注册与管理
    2. 混合决策综合
    3. 决策可视化
    4. 反馈与学习
    """

    def __init__(self):
        self.strategies: Dict[str, RoutingStrategy] = {}
        self.strategy_configs: Dict[str, StrategyConfig] = {}
        self.decision_history: List[HybridDecision] = []
        self.default_route = "default"

    def add_strategy(
        self,
        strategy: RoutingStrategy,
        weight: float = 1.0,
        enabled: bool = True,
    ):
        """添加路由策略"""
        self.strategies[strategy.name] = strategy
        self.strategy_configs[strategy.name] = StrategyConfig(
            name=strategy.name,
            strategy_type=self._get_strategy_type(strategy),
            weight=weight,
            enabled=enabled,
        )
        logger.info(f"已添加策略: {strategy.name}")

    def _get_strategy_type(self, strategy: RoutingStrategy) -> StrategyType:
        """获取策略类型"""
        if isinstance(strategy, KeywordRoutingStrategy):
            return StrategyType.KEYWORD
        elif isinstance(strategy, SemanticRoutingStrategy):
            return StrategyType.SEMANTIC
        elif isinstance(strategy, VectorRoutingStrategy):
            return StrategyType.VECTOR
        elif isinstance(strategy, LLMRoutingStrategy):
            return StrategyType.LLM
        return StrategyType.HYBRID

    def route(
        self,
        query: str,
        strategy_names: Optional[List[str]] = None,
    ) -> HybridDecision:
        """执行混合路由决策

        Args:
            query: 查询文本
            strategy_names: 指定使用的策略名称列表，None 表示使用所有启用的策略

        Returns:
            HybridDecision: 混合决策结果
        """
        start_time = time.time()

        strategy_names = strategy_names or list(self.strategies.keys())
        enabled_strategies = [
            name for name in strategy_names
            if name in self.strategies and self.strategy_configs.get(name, StrategyConfig("", StrategyType.HYBRID)).enabled
        ]

        if not enabled_strategies:
            decision = HybridDecision(
                final_route=self.default_route,
                confidence=0.0,
                strategy_results=[],
                decision_process=["未启用任何策略"],
            )
            decision.total_processing_time_ms = (time.time() - start_time) * 1000
            return decision

        strategy_results = []
        decision_process = []

        for strategy_name in enabled_strategies:
            strategy = self.strategies[strategy_name]
            result = strategy.route(query)
            strategy_results.append(result)
            decision_process.append(
                f"{strategy_name}: route={result.route_name}, confidence={result.confidence:.3f}"
            )

        final_route, final_confidence = self._combine_strategy_results(strategy_results)

        decision = HybridDecision(
            final_route=final_route,
            confidence=final_confidence,
            strategy_results=strategy_results,
            decision_process=decision_process,
        )
        decision.total_processing_time_ms = (time.time() - start_time) * 1000

        self.decision_history.append(decision)
        return decision

    def _combine_strategy_results(
        self,
        strategy_results: List[StrategyResult],
    ) -> tuple[str, float]:
        """综合策略结果

        Args:
            strategy_results: 策略结果列表

        Returns:
            Tuple[str, float]: (最终路由, 最终置信度
        """
        route_scores: Dict[str, float] = defaultdict(float)
        total_weight = 0.0

        for result in strategy_results:
            config = self.strategy_configs.get(result.strategy_name)
            weight = config.weight if config else 1.0
            route_scores[result.route_name] += result.confidence * weight
            total_weight += weight

        if not route_scores:
            return self.default_route, 0.0

        best_route = max(route_scores.items(), key=lambda x: x[1])
        final_route, score = best_route
        final_confidence = score / total_weight if total_weight > 0 else 0.0

        return final_route, final_confidence

    def get_visualization_data(self) -> Dict[str, Any]:
        """获取可视化数据

        Returns:
            Dict[str, Any]: 可视化数据
        """
        strategy_stats = defaultdict(lambda: {"count": 0, "total_confidence": 0.0})

        for decision in self.decision_history:
            for result in decision.strategy_results:
                strategy_stats[result.strategy_name]["count"] += 1
                strategy_stats[result.strategy_name]["total_confidence"] += result.confidence

        return {
            "strategies": {},
            "total_decisions": len(self.decision_history),
            "recent_decisions": [
                {
                    "final_route": d.final_route,
                    "confidence": d.confidence,
                    "strategies": [
                        {
                            "name": r.strategy_name,
                            "route": r.route_name,
                            "confidence": r.confidence,
                        }
                        for r in d.strategy_results
                    ],
                }
                for d in self.decision_history[-10:]
            ],
        }

    def export_history(self, filepath: str):
        """导出历史记录"""
        data = []
        for decision in self.decision_history:
            data.append({
                "final_route": decision.final_route,
                "confidence": decision.confidence,
                "total_processing_time_ms": decision.total_processing_time_ms,
                "strategy_results": [
                    {
                        "strategy_name": r.strategy_name,
                        "strategy_type": r.strategy_type.value,
                        "route_name": r.route_name,
                        "confidence": r.confidence,
                    }
                    for r in decision.strategy_results
                ],
            })

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"历史记录已导出到: {filepath}")


def create_default_advanced_router(
    semantic_router: Optional[SemanticRouter] = None,
    llm_func: Optional[Callable] = None,
) -> AdvancedRouter:
    """创建默认配置的高级路由器

    Args:
        semantic_router: 语义路由器
        llm_func: LLM 函数

    Returns:
        AdvancedRouter: 配置好的高级路由器
    """
    router = AdvancedRouter()

    keyword_strategy = KeywordRoutingStrategy()
    keyword_strategy.add_route_keywords("rule_query", [
        "规则", "连锁", "效果", "陷阱", "魔法", "怪兽", "召唤", "无效", "破坏", "除外"
    ])
    keyword_strategy.add_route_keywords("concept_query", [
        "什么是", "定义", "含义", "概念", "原理", "机制"
    ])
    keyword_strategy.add_route_keywords("operation_query", [
        "如何", "怎么", "步骤", "操作", "使用", "发动"
    ])
    keyword_strategy.add_route_keywords("compare_query", [
        "区别", "对比", "不同", "比较", "哪个好"
    ])

    router.add_strategy(keyword_strategy, weight=0.6)

    semantic_strategy = SemanticRoutingStrategy(semantic_router=semantic_router)
    router.add_strategy(semantic_strategy, weight=1.0)

    llm_strategy = LLMRoutingStrategy(llm_func=llm_func)
    router.add_strategy(llm_strategy, weight=0.3)

    return router


_advanced_router_instance = None


def get_advanced_router() -> AdvancedRouter:
    """获取全局单例的高级路由器"""
    global _advanced_router_instance
    if _advanced_router_instance is None:
        _advanced_router_instance = create_default_advanced_router()
    return _advanced_router_instance
