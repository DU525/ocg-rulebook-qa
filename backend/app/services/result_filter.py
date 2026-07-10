"""通用检索结果过滤器模块

提供多种过滤策略和过滤器链，用于提升检索结果质量。
支持相关性过滤、长度过滤、去重过滤等。
"""
import logging
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional

logger = logging.getLogger(__name__)


class ResultFilter(ABC):
    """结果过滤器基类"""

    @abstractmethod
    def filter(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """过滤结果列表

        Args:
            results: 原始结果列表

        Returns:
            过滤后的结果列表
        """
        pass

    @abstractmethod
    def get_name(self) -> str:
        """获取过滤器名称"""
        pass


class RelevanceFilter(ResultFilter):
    """相关性过滤 - 去除 similarity/relevance 低于阈值的文档"""

    def __init__(self, threshold: float = 0.5):
        """初始化相关性过滤器

        Args:
            threshold: 最低相关性阈值，默认 0.5
        """
        self.threshold = threshold

    def filter(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not results:
            return results

        filtered = []
        for result in results:
            relevance = self._get_relevance(result)
            if relevance >= self.threshold:
                filtered.append(result)

        before_count = len(results)
        after_count = len(filtered)
        if before_count > after_count:
            filtered_count = before_count - after_count
            logger.info(
                f"[RelevanceFilter] 过滤低相关性文档: "
                f"阈值={self.threshold}, "
                f"过滤前={before_count}, "
                f"过滤后={after_count}, "
                f"过滤掉={filtered_count}"
            )

        return filtered

    def get_name(self) -> str:
        return "RelevanceFilter"

    def _get_relevance(self, result: Any) -> float:
        """从 result 提取相关性分数，兼容 dict 和 dataclass 对象（修复 2026-06-01）"""
        def _val(key):
            if isinstance(result, dict):
                return result.get(key)
            return getattr(result, key, None)

        for key in ("relevance", "score", "similarity", "hybrid_score", "rrf_score", "rerank_score"):
            v = _val(key)
            if v is not None:
                return float(v)

        dist = _val("distance")
        if dist is not None:
            return 1.0 - float(dist)

        return 0.0


class LengthFilter(ResultFilter):
    """长度过滤 - 去除内容过短的文档"""

    def __init__(self, min_length: int = 50):
        """初始化长度过滤器

        Args:
            min_length: 最小字符长度，默认 50
        """
        self.min_length = min_length

    def filter(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not results:
            return results

        filtered = []
        for result in results:
            content = result.get("content", "")
            if len(content) >= self.min_length:
                filtered.append(result)

        before_count = len(results)
        after_count = len(filtered)
        if before_count > after_count:
            filtered_count = before_count - after_count
            logger.info(
                f"[LengthFilter] 过滤过短文档: "
                f"最小长度={self.min_length}, "
                f"过滤前={before_count}, "
                f"过滤后={after_count}, "
                f"过滤掉={filtered_count}"
            )

        return filtered

    def get_name(self) -> str:
        return "LengthFilter"


class DuplicateFilter(ResultFilter):
    """去重过滤 - 去除内容重复的文档"""

    def __init__(self, ignore_case: bool = True, strip_whitespace: bool = True):
        """初始化去重过滤器

        Args:
            ignore_case: 是否忽略大小写，默认 True
            strip_whitespace: 是否去除首尾空白，默认 True
        """
        self.ignore_case = ignore_case
        self.strip_whitespace = strip_whitespace

    def filter(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        if not results:
            return results

        seen_contents = set()
        filtered = []

        for result in results:
            content = result.get("content", "")
            normalized = self._normalize_content(content)

            if normalized not in seen_contents:
                seen_contents.add(normalized)
                filtered.append(result)

        before_count = len(results)
        after_count = len(filtered)
        if before_count > after_count:
            duplicate_count = before_count - after_count
            logger.info(
                f"[DuplicateFilter] 去除重复文档: "
                f"过滤前={before_count}, "
                f"过滤后={after_count}, "
                f"重复={duplicate_count}"
            )

        return filtered

    def get_name(self) -> str:
        return "DuplicateFilter"

    def _normalize_content(self, content: str) -> str:
        normalized = content
        if self.strip_whitespace:
            normalized = normalized.strip()
        if self.ignore_case:
            normalized = normalized.lower()
        return normalized


class FilterChain:
    """过滤器链 - 按顺序应用多个过滤器"""

    def __init__(self, filters: Optional[List[ResultFilter]] = None):
        """初始化过滤器链

        Args:
            filters: 过滤器列表，按顺序应用
        """
        self.filters = filters or []

    def add_filter(self, filter_instance: ResultFilter) -> None:
        """添加过滤器到链中

        Args:
            filter_instance: 过滤器实例
        """
        self.filters.append(filter_instance)

    def apply(self, results: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """按顺序应用所有过滤器

        Args:
            results: 原始结果列表

        Returns:
            过滤后的结果列表
        """
        if not results:
            return results

        original_count = len(results)
        current_results = results

        for filter_instance in self.filters:
            current_results = filter_instance.filter(current_results)

        final_count = len(current_results)
        if original_count != final_count:
            logger.info(
                f"[FilterChain] 过滤统计: "
                f"过滤器数量={len(self.filters)}, "
                f"过滤前={original_count}, "
                f"过滤后={final_count}, "
                f"过滤掉={original_count - final_count}"
            )

        return current_results

    def get_filter_names(self) -> List[str]:
        """获取链中所有过滤器的名称"""
        return [f.get_name() for f in self.filters]


def create_default_filter_chain(
    relevance_threshold: float = 0.5,
    min_length: int = 50,
    enable_relevance: bool = True,
    enable_length: bool = False,
    enable_duplicate: bool = False,
) -> FilterChain:
    """创建默认过滤器链

    Args:
        relevance_threshold: 相关性阈值，默认 0.5
        min_length: 最小长度，默认 50
        enable_relevance: 是否启用相关性过滤，默认 True
        enable_length: 是否启用长度过滤，默认 False
        enable_duplicate: 是否启用去重过滤，默认 False

    Returns:
        配置好的 FilterChain 实例
    """
    chain = FilterChain()

    if enable_relevance:
        chain.add_filter(RelevanceFilter(threshold=relevance_threshold))

    if enable_length:
        chain.add_filter(LengthFilter(min_length=min_length))

    if enable_duplicate:
        chain.add_filter(DuplicateFilter())

    return chain
