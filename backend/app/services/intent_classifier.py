"""查询意图分类器 - 基于规则匹配的查询意图识别

功能：
- 识别4种查询意图类型：
  * RULE_QUERY（规则查询）- 精确术语查询
  * CONCEPT_QUERY（概念查询）- 抽象概念理解
  * COMPARE_QUERY（对比查询）- 对比差异分析
  * OPERATION_QUERY（操作查询）- 操作步骤指导
- 基于关键词规则匹配，无需训练模型
- 返回意图类型 + 置信度
- 支持通过注册新规则扩展

技术：
- 使用 re 模块进行正则表达式匹配
- 支持权重加权的综合评分
- 提供置信度计算（基于匹配词数量和覆盖度）
"""
import re
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple, Set

logger = logging.getLogger(__name__)


class IntentType(Enum):
    """查询意图类型枚举"""
    RULE_QUERY = "rule_query"
    CONCEPT_QUERY = "concept_query"
    COMPARE_QUERY = "compare_query"
    OPERATION_QUERY = "operation_query"


@dataclass
class IntentResult:
    """意图分类结果"""
    intent_type: IntentType
    confidence: float
    matched_terms: List[str] = field(default_factory=list)
    details: Dict[str, float] = field(default_factory=dict)


@dataclass
class IntentRule:
    """意图匹配规则"""
    name: str
    keywords: List[str]
    regex_patterns: List[str] = field(default_factory=list)
    weight: float = 1.0
    min_matches: int = 1


class IntentClassifier:
    """基于规则的查询意图分类器

    分类策略：
    1. 预定义4种意图类型的关键词和正则模式
    2. 对查询进行多维度匹配（关键词 + 正则）
    3. 计算各意图类型的得分和置信度
    4. 返回得分最高的意图类型

    扩展机制：
    - 通过 register_rule() 方法添加新规则
    - 通过 update_keywords() 更新现有规则的关键词
    """

    def __init__(self):
        self.rules: Dict[IntentType, IntentRule] = self._build_default_rules()
        self._compiled_patterns: Dict[IntentType, List[re.Pattern]] = {}
        self._compile_all_patterns()

    def _build_default_rules(self) -> Dict[IntentType, IntentRule]:
        """构建默认的意图匹配规则

        Returns:
            Dict[IntentType, IntentRule]: 各意图类型的匹配规则
        """
        return {
            IntentType.RULE_QUERY: IntentRule(
                name="规则查询",
                keywords=[
                    "连锁", "反击陷阱", "反击", "陷阱卡", "魔法卡", "怪兽卡",
                    "效果", "咒语速度", "连锁处理", "连锁块", "逆顺处理",
                    "优先权", "时点", "强制效果", "选发效果", "任意发动",
                    "必发效果", "cost", "代价", "支付", "宣言", "无效",
                    "破坏", "除外", "返回卡组", "返回手牌", "特殊召唤",
                    "通常召唤", "上级召唤", "仪式召唤", "融合召唤",
                    "同步召唤", "超量召唤", "灵摆召唤", "连接召唤",
                    "游戏规则", "规则书", "裁定", "调整", "官方",
                    "处理", "发动", "响应", "连锁点", "连锁顺序",
                    "效果处理", "发动时机", "卡时点", "错过时点",
                    "取对象", "不取对象", "场发", "手发", "墓发",
                    "表侧表示", "里侧表示", "表侧守备", "表侧攻击",
                    "伤害步骤", "伤害计算", "战斗阶段", "主要阶段",
                    "结束阶段", "抽卡阶段", "准备阶段", "standby phase",
                    "end phase", "damage step",
                ],
                regex_patterns=[
                    r".*连锁.*怎么处理.*",
                    r".*效果.*能.*发动.*吗.*",
                    r".*这张卡.*效果.*是什么.*",
                    r".*裁定.*",
                    r".*规则.*规定.*",
                ],
                weight=1.5,
                min_matches=1,
            ),
            IntentType.CONCEPT_QUERY: IntentRule(
                name="概念查询",
                keywords=[
                    "什么是", "什么是", "什么叫", "含义", "定义",
                    "概念", "原理", "机制", "理解", "说明",
                    "解释", "为什么", "为何", "原因", "意义",
                    "作用", "目的", "本质", "区别", "特点",
                    "特征", "性质", "规则", "制度", "系统",
                ],
                regex_patterns=[
                    r"^什么是.*",
                    r"^什么叫.*",
                    r".*是什么意思.*",
                    r".*什么概念.*",
                    r"^为什么.*",
                    r".*为什么.*呢.*",
                    r".*原理.*",
                    r".*机制.*",
                ],
                weight=1.0,
                min_matches=1,
            ),
            IntentType.COMPARE_QUERY: IntentRule(
                name="对比查询",
                keywords=[
                    "区别", "对比", "差异", "不同", "差别",
                    "哪个好", "哪个强", "优劣", "优缺点",
                    "比较", "相比", "相对而言", "更", "vs",
                    " versus", "和.*有什么不同", "与.*区别",
                    "两者", "两种", "多个", "几种",
                    "一样吗", "相同吗", "等同", "等效",
                ],
                regex_patterns=[
                    r".*和.*有什么区别.*",
                    r".*与.*有什么不同.*",
                    r".*对比.*",
                    r".*区别.*",
                    r".*差异.*",
                    r".*哪个.*更.*",
                    r".*vs.*",
                    r".*.*和.*.*区别.*",
                ],
                weight=1.1,
                min_matches=1,
            ),
            IntentType.OPERATION_QUERY: IntentRule(
                name="操作查询",
                keywords=[
                    "怎么", "如何", "步骤", "流程", "方法",
                    "操作", "使用", "发动", "应对", "处理",
                    "怎么办", "怎样做", "怎么做", "如何做",
                    "顺序", "先后", "第一步", "然后", "接着",
                    "教程", "指南", "示范", "演示", "例子",
                    "举例", "案例", "实战", "应用",
                    "怎么发动", "如何处理", "怎样操作", "怎么应对",
                    "怎么连锁", "怎么处理连锁", "如何应对",
                ],
                regex_patterns=[
                    r"^怎么.*",
                    r"^如何.*",
                    r".*怎么发动.*",
                    r".*如何处理.*",
                    r".*步骤.*",
                    r".*流程.*",
                    r".*方法.*",
                    r".*顺序.*",
                    r"^怎样.*",
                    r".*怎么办.*",
                ],
                weight=1.0,
                min_matches=1,
            ),
        }

    def _compile_all_patterns(self):
        """预编译所有正则表达式模式"""
        for intent_type, rule in self.rules.items():
            compiled = []
            for pattern in rule.regex_patterns:
                try:
                    compiled.append(re.compile(pattern, re.IGNORECASE | re.DOTALL))
                except re.error as e:
                    logger.warning(f"正则表达式编译失败: {pattern}, 错误: {e}")
            self._compiled_patterns[intent_type] = compiled

    def classify(self, query: str) -> IntentResult:
        """对查询进行意图分类

        Args:
            query: 用户查询字符串

        Returns:
            IntentResult: 包含意图类型、置信度和匹配详情的结果
        """
        if not query or not query.strip():
            return IntentResult(
                intent_type=IntentType.CONCEPT_QUERY,
                confidence=0.0,
                matched_terms=[],
                details={t.value: 0.0 for t in IntentType},
            )

        query_clean = query.strip()
        query_lower = query_clean.lower()

        scores: Dict[IntentType, float] = {t: 0.0 for t in IntentType}
        matched_terms_map: Dict[IntentType, List[str]] = {t: [] for t in IntentType}

        for intent_type, rule in self.rules.items():
            keyword_score = self._match_keywords(query_lower, rule)
            regex_score = self._match_regex(query_clean, intent_type)

            total_score = (keyword_score + regex_score) * rule.weight
            scores[intent_type] = total_score

            matched_terms_map[intent_type] = self._get_matched_terms(
                query_lower, rule
            )

        rule_term_count = len(matched_terms_map[IntentType.RULE_QUERY])
        compare_term_count = len(matched_terms_map[IntentType.COMPARE_QUERY])
        concept_term_count = len(matched_terms_map[IntentType.CONCEPT_QUERY])
        operation_term_count = len(matched_terms_map[IntentType.OPERATION_QUERY])

        if rule_term_count >= 3:
            scores[IntentType.RULE_QUERY] *= 2.0
        elif rule_term_count >= 2:
            scores[IntentType.RULE_QUERY] *= 1.6
        elif rule_term_count >= 1 and compare_term_count >= 1:
            if rule_term_count >= compare_term_count:
                scores[IntentType.RULE_QUERY] *= 1.4

        if compare_term_count >= 3 and rule_term_count <= 1:
            scores[IntentType.COMPARE_QUERY] *= 1.5
        elif compare_term_count >= 2 and rule_term_count <= 1:
            scores[IntentType.COMPARE_QUERY] *= 1.3

        if concept_term_count >= 2 and rule_term_count == 0:
            scores[IntentType.CONCEPT_QUERY] *= 1.2

        if operation_term_count >= 2 and rule_term_count <= 1:
            scores[IntentType.OPERATION_QUERY] *= 1.3

        best_intent = max(scores, key=scores.get)
        best_score = scores[best_intent]

        confidence = self._calculate_confidence(
            best_intent, scores, matched_terms_map, best_score
        )

        details = {
            t.value: round(s, 4) for t, s in scores.items()
        }

        return IntentResult(
            intent_type=best_intent,
            confidence=round(confidence, 4),
            matched_terms=matched_terms_map[best_intent],
            details=details,
        )

    def _match_keywords(self, query_lower: str, rule: IntentRule) -> float:
        """计算关键词匹配得分

        Args:
            query_lower: 小写化的查询字符串
            rule: 意图匹配规则

        Returns:
            float: 关键词匹配得分（0.0-1.0）
        """
        matched_count = 0
        for keyword in rule.keywords:
            keyword_lower = keyword.lower()
            if keyword_lower in query_lower:
                matched_count += 1

        if matched_count == 0:
            return 0.0

        match_ratio = matched_count / len(rule.keywords)
        return min(match_ratio * 2, 1.0)

    def _match_regex(self, query: str, intent_type: IntentType) -> float:
        """计算正则表达式匹配得分

        Args:
            query: 原始查询字符串
            intent_type: 意图类型

        Returns:
            float: 正则匹配得分（0.0-1.0）
        """
        patterns = self._compiled_patterns.get(intent_type, [])
        if not patterns:
            return 0.0

        matched_count = sum(1 for p in patterns if p.search(query))
        if matched_count == 0:
            return 0.0

        match_ratio = matched_count / len(patterns)
        return min(match_ratio * 2, 1.0)

    def _get_matched_terms(self, query_lower: str, rule: IntentRule) -> List[str]:
        """获取实际匹配到的关键词列表

        Args:
            query_lower: 小写化的查询字符串
            rule: 意图匹配规则

        Returns:
            List[str]: 匹配到的关键词列表
        """
        matched = []
        for keyword in rule.keywords:
            if keyword.lower() in query_lower:
                matched.append(keyword)
        return matched

    def _calculate_confidence(
        self,
        best_intent: IntentType,
        scores: Dict[IntentType, float],
        matched_terms_map: Dict[IntentType, List[str]],
        best_score: float,
    ) -> float:
        """计算分类置信度

        置信度基于以下因素：
        1. 最佳意图的绝对得分
        2. 与其他意图的得分差距
        3. 匹配到的关键词数量

        Args:
            best_intent: 最佳意图类型
            scores: 各意图得分
            matched_terms_map: 各意图匹配词
            best_score: 最佳得分

        Returns:
            float: 置信度（0.0-1.0）
        """
        total_score = sum(scores.values())
        if total_score == 0:
            return 0.1

        base_confidence = best_score / total_score

        sorted_scores = sorted(scores.values(), reverse=True)
        if len(sorted_scores) >= 2 and sorted_scores[1] > 0:
            gap = sorted_scores[0] - sorted_scores[1]
            gap_factor = min(gap / sorted_scores[0], 1.0) if sorted_scores[0] > 0 else 0
            base_confidence = base_confidence * 0.7 + gap_factor * 0.3

        term_count = len(matched_terms_map.get(best_intent, []))
        term_bonus = min(term_count * 0.05, 0.15)

        final_confidence = min(base_confidence + term_bonus, 1.0)

        if best_score == 0 and total_score == 0:
            final_confidence = 0.1

        return max(final_confidence, 0.1)

    def register_rule(
        self,
        intent_type: IntentType,
        rule: IntentRule,
    ):
        """注册新的意图匹配规则

        Args:
            intent_type: 意图类型
            rule: 匹配规则
        """
        self.rules[intent_type] = rule
        self._compiled_patterns[intent_type] = []
        for pattern in rule.regex_patterns:
            try:
                self._compiled_patterns[intent_type].append(
                    re.compile(pattern, re.IGNORECASE | re.DOTALL)
                )
            except re.error as e:
                logger.warning(f"正则表达式编译失败: {pattern}, 错误: {e}")
        logger.info(f"已注册意图规则: {intent_type.value} - {rule.name}")

    def update_keywords(
        self,
        intent_type: IntentType,
        keywords: List[str],
        replace: bool = False,
    ):
        """更新意图规则的关键词

        Args:
            intent_type: 意图类型
            keywords: 新关键词列表
            replace: True=替换, False=追加
        """
        if intent_type not in self.rules:
            logger.warning(f"意图类型不存在: {intent_type.value}")
            return

        rule = self.rules[intent_type]
        if replace:
            rule.keywords = keywords
        else:
            existing = set(k.lower() for k in rule.keywords)
            for kw in keywords:
                if kw.lower() not in existing:
                    rule.keywords.append(kw)

    def get_supported_intents(self) -> List[IntentType]:
        """获取所有支持的意图类型

        Returns:
            List[IntentType]: 支持的意图类型列表
        """
        return list(self.rules.keys())

    def get_rule_info(self, intent_type: IntentType) -> Optional[IntentRule]:
        """获取指定意图的规则信息

        Args:
            intent_type: 意图类型

        Returns:
            Optional[IntentRule]: 规则信息，不存在则返回None
        """
        return self.rules.get(intent_type)


classifier = IntentClassifier()


def classify_query(query: str) -> IntentResult:
    """便捷函数：对查询进行意图分类

    Args:
        query: 用户查询字符串

    Returns:
        IntentResult: 意图分类结果
    """
    return classifier.classify(query)
