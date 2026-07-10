"""语义路由 - 基于 Embedding 的语义相似度路由系统

功能：
- 使用嵌入向量相似度匹配，支持多路由（路由决策
- 可自定义路由规则管理
- 支持路由决策可视化
- 反馈学习能力

技术：
- 使用 text2vec 或其他嵌入模型
- 余弦相似度计算
- 支持阈值配置
- 路由决策历史记录
"""

import os
import logging
import time
import json
from enum import Enum
from dataclasses import dataclass, field
from typing import List, Dict, Any, Optional, Tuple
from collections import defaultdict
import numpy as np

logger = logging.getLogger(__name__)


class RouteType(Enum):
    """路由类型枚举"""
    SEMANTIC = "semantic"
    KEYWORD = "keyword"
    VECTOR = "vector"
    LLM_FALLBACK = "llm_fallback"
    DEFAULT = "default"


@dataclass
class Route:
    """路由配置"""
    name: str
    route_type: RouteType
    description: str
    examples: List[str] = field(default_factory=list)
    embeddings: List[np.ndarray] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    threshold: float = 0.7
    priority: int = 0
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class RouteDecision:
    """路由决策结果"""
    route_name: str
    route_type: RouteType
    confidence: float
    matched_examples: List[str] = field(default_factory=list)
    matched_keywords: List[str] = field(default_factory=list)
    decision_path: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    processing_time_ms: float = 0.0


@dataclass
class RouteHistory:
    """路由决策历史记录"""
    query: str
    decision: RouteDecision
    timestamp: float
    feedback: Optional[bool] = None
    corrected_route: Optional[str] = None


class SemanticRouter:
    """基于 Embedding 的语义路由器

    核心功能：
    1. 语义匹配 - 使用嵌入向量计算相似度匹配
    2. 关键词匹配 - 辅助验证
    3. 路由决策 - 综合判断最佳路由
    4. 历史记录 - 存储决策历史
    5. 反馈学习 - 根据反馈调整策略
    """

    def __init__(self, embedding_model=None, embedding_func=None):
        """初始化语义路由器

        Args:
            embedding_model: 可选，预加载的嵌入模型
            embedding_func: 可选，自定义嵌入函数
        """
        self.routes: Dict[str, Route] = {}
        self.history: List[RouteHistory] = []
        self._embedding_model = embedding_model
        self._embedding_func = embedding_func
        self._embedding_cache: Dict[str, np.ndarray] = {}

    @property
    def embedding_model(self):
        """获取嵌入模型（延迟加载）"""
        if self._embedding_model is None:
            from app.services.vector_rag import get_shared_embedding_model
            self._embedding_model = get_shared_embedding_model()
        return self._embedding_model

    def _get_embedding(self, text: str) -> np.ndarray:
        """获取文本的嵌入向量

        Args:
            text: 输入文本

        Returns:
            np.ndarray: 嵌入向量
        """
        if text in self._embedding_cache:
            return self._embedding_cache[text]

        if self._embedding_func:
            embedding = self._embedding_func(text)
        else:
            model = self.embedding_model
            embedding = model.encode(text)

        self._embedding_cache[text] = embedding
        return embedding

    def _cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """计算两个向量的余弦相似度

        Args:
            vec1: 向量1
            vec2: 向量2

        Returns:
            float: 相似度（0.0-1.0）
        """
        dot_product = np.dot(vec1, vec2)
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        return dot_product / (norm1 * norm2)

    def add_route(
        self,
        name: str,
        route_type: RouteType,
        description: str = "",
        examples: Optional[List[str]] = None,
        keywords: Optional[List[str]] = None,
        threshold: float = 0.7,
        priority: int = 0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> Route:
        """添加路由

        Args:
            name: 路由名称
            route_type: 路由类型
            description: 描述
            examples: 示例文本列表
            keywords: 关键词列表
            threshold: 相似度阈值
            priority: 优先级
            metadata: 附加元数据

        Returns:
            Route: 创建的路由对象
        """
        examples = examples or []
        keywords = keywords or []
        metadata = metadata or {}

        embeddings = [self._get_embedding(example) for example in examples]

        route = Route(
            name=name,
            route_type=route_type,
            description=description,
            examples=examples,
            embeddings=embeddings,
            keywords=keywords,
            threshold=threshold,
            priority=priority,
            metadata=metadata,
        )

        self.routes[name] = route
        logger.info(f"已添加路由: {name}")
        return route

    def _calculate_semantic_match(
        self,
        query: str,
        route: Route,
    ) -> Tuple[float, List[str]]:
        """计算语义相似度

        Args:
            query: 查询文本
            route: 路由

        Returns:
            Tuple[float, List[str]]: (相似度, 匹配的示例列表
        """
        if not route.embeddings:
            return 0.0, []

        query_embedding = self._get_embedding(query)
        similarities = []
        matched_examples = []

        for i, example_embedding in enumerate(route.embeddings):
            similarity = self._cosine_similarity(query_embedding, example_embedding)
            similarities.append(similarity)
            if similarity >= route.threshold:
                matched_examples.append(route.examples[i])

        if not similarities:
            return 0.0, []

        max_similarity = max(similarities)
        return max_similarity, matched_examples

    def _calculate_keyword_match(
        self,
        query: str,
        route: Route,
    ) -> Tuple[float, List[str]]:
        """计算关键词匹配度

        Args:
            query: 查询文本
            route: 路由

        Returns:
            Tuple[float, List[str]]: (匹配度, 匹配的关键词列表
        """
        if not route.keywords:
            return 0.0, []

        query_lower = query.lower()
        matched_keywords = []

        for keyword in route.keywords:
            if keyword.lower() in query_lower:
                matched_keywords.append(keyword)

        if not matched_keywords:
            return 0.0, []

        match_ratio = len(matched_keywords) / len(route.keywords)
        return min(match_ratio * 2, 1.0), matched_keywords

    def route(
        self,
        query: str,
        fallback_route: str = "default",
    ) -> RouteDecision:
        """执行路由决策

        Args:
            query: 查询文本
            fallback_route: 兜底路由名称

        Returns:
            RouteDecision: 路由决策结果
        """
        start_time = time.time()

        if not self.routes:
            decision = RouteDecision(
                route_name=fallback_route,
                route_type=RouteType.DEFAULT,
                confidence=0.0,
            )
            decision.processing_time_ms = (time.time() - start_time) * 1000
            return decision

        scores: Dict[str, Tuple[float, List[str], List[str]]] = {}
        decision_path = []

        for route_name, route in self.routes.items():
            semantic_score, matched_examples = self._calculate_semantic_match(query, route)
            keyword_score, matched_keywords = self._calculate_keyword_match(query, route)

            combined_score = max(semantic_score, keyword_score)
            scores[route_name] = (
                combined_score, matched_examples, matched_keywords)

            decision_path.append(
                f"{route_name}: semantic={semantic_score:.3f}, keyword={keyword_score:.3f}"
            )

        sorted_routes = sorted(
            scores.items(),
            key=lambda x: (x[1][0], self.routes[x[0]].priority),
            reverse=True,
        )

        best_route_name, (best_score, matched_examples, matched_keywords) = sorted_routes[0]
        best_route = self.routes[best_route_name]

        if best_score < best_route.threshold:
            selected_route = fallback_route
            selected_type = RouteType.DEFAULT
            final_confidence = best_score
        else:
            selected_route = best_route_name
            selected_type = best_route.route_type
            final_confidence = best_score

        decision = RouteDecision(
            route_name=selected_route,
            route_type=selected_type,
            confidence=final_confidence,
            matched_examples=matched_examples,
            matched_keywords=matched_keywords,
            decision_path=decision_path,
            metadata=best_route.metadata,
        )
        decision.processing_time_ms = (time.time() - start_time) * 1000

        history = RouteHistory(
            query=query,
            decision=decision,
            timestamp=time.time(),
        )
        self.history.append(history)

        return decision

    def add_feedback(
        self,
        query: str,
        is_correct: bool,
        corrected_route: Optional[str] = None,
    ):
        """添加反馈

        Args:
            query: 查询文本
            is_correct: 决策是否正确
            corrected_route: 正确的路由名称（如果决策错误）
        """
        for history in reversed(self.history):
            if history.query == query:
                history.feedback = is_correct
                history.corrected_route = corrected_route
                logger.info(
                    f"已添加反馈: query={query}, correct={is_correct}"
                )
                break

    def get_visualization_data(self) -> Dict[str, Any]:
        """获取路由可视化数据

        Returns:
            Dict[str, Any]: 可视化数据
        """
        route_stats = defaultdict(lambda: {"count": 0, "correct": 0, "total_confidence": 0.0})

        for history in self.history:
            route_name = history.decision.route_name
            route_stats[route_name]["count"] += 1
            route_stats[route_name]["total_confidence"] += history.decision.confidence

            if history.feedback is not None:
                if history.feedback:
                    route_stats[route_name]["correct"] += 1

        visualization_data = {
            "routes": {},
            "total_decisions": len(self.history),
            "recent_decisions": [
                {
                    "query": h.query,
                    "route": h.decision.route_name,
                    "confidence": h.decision.confidence,
                    "timestamp": h.timestamp,
                    "feedback": h.feedback,
                }
                for h in self.history[-20:]
            ],
        }

        for route_name, stats in route_stats.items():
            avg_confidence = (
                stats["total_confidence"] / stats["count"]
                if stats["count"] > 0
                else 0.0
            )
            accuracy = (
                stats["correct"] / stats["count"]
                if stats["count"] > 0
                else 0.0
            )

            visualization_data["routes"][route_name] = {
                "count": stats["count"],
                "avg_confidence": avg_confidence,
                "accuracy": accuracy,
            }

        return visualization_data

    def export_history(self, filepath: str):
        """导出历史记录

        Args:
            filepath: 文件路径
        """
        data = []
        for history in self.history:
            data.append({
                "query": history.query,
                "decision": {
                    "route_name": history.decision.route_name,
                    "route_type": history.decision.route_type.value,
                    "confidence": history.decision.confidence,
                    "matched_examples": history.decision.matched_examples,
                    "matched_keywords": history.decision.matched_keywords,
                },
                "timestamp": history.timestamp,
                "feedback": history.feedback,
                "corrected_route": history.corrected_route,
            })

        with open(filepath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        logger.info(f"历史记录已导出到: {filepath}")

    def clear_cache(self):
        """清除缓存"""
        self._embedding_cache.clear()
        logger.info("嵌入向量缓存已清除")


_semantic_router_instance = None


def get_semantic_router() -> SemanticRouter:
    """获取全局单例的语义路由器

    Returns:
        SemanticRouter: 语义路由器实例
    """
    global _semantic_router_instance
    if _semantic_router_instance is None:
        _semantic_router_instance = SemanticRouter()
    return _semantic_router_instance
