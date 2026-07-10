"""
Few-Shot Learning 示例库管理模块

提供高质量 Few-Shot 示例的存储、检索和质量评分机制，
用于增强 RAG Prompt 的上下文学习（In-Context Learning）能力。
"""

import hashlib
import time
import math
from dataclasses import dataclass, field
from typing import List, Dict, Optional, Tuple
from collections import defaultdict


@dataclass
class FewShotExample:
    """Few-Shot 示例数据类"""
    question: str
    context: str
    answer: str
    intent_type: str
    quality_score: float = 1.0
    example_id: str = ""
    feedback_count: int = 0
    positive_feedback: int = 0
    negative_feedback: int = 0
    created_at: float = field(default_factory=time.time)
    last_updated: float = field(default_factory=time.time)

    def __post_init__(self):
        if not self.example_id:
            self.example_id = self._generate_id()

    def _generate_id(self) -> str:
        content = f"{self.question}{self.context}{self.intent_type}"
        return hashlib.md5(content.encode("utf-8")).hexdigest()[:12]

    def update_quality_from_feedback(self, is_positive: bool):
        """根据用户反馈更新质量评分"""
        self.feedback_count += 1
        if is_positive:
            self.positive_feedback += 1
        else:
            self.negative_feedback += 1

        if self.feedback_count > 0:
            positive_ratio = self.positive_feedback / self.feedback_count
            confidence = min(1.0, self.feedback_count / 10.0)
            self.quality_score = 0.5 + 0.5 * (positive_ratio * confidence)
            self.quality_score = round(max(0.0, min(1.0, self.quality_score)), 4)

        self.last_updated = time.time()

    def to_dict(self) -> dict:
        return {
            "example_id": self.example_id,
            "question": self.question,
            "context": self.context,
            "answer": self.answer,
            "intent_type": self.intent_type,
            "quality_score": self.quality_score,
            "feedback_count": self.feedback_count,
            "positive_feedback": self.positive_feedback,
            "negative_feedback": self.negative_feedback,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "FewShotExample":
        return cls(
            question=data["question"],
            context=data["context"],
            answer=data["answer"],
            intent_type=data["intent_type"],
            quality_score=data.get("quality_score", 1.0),
            example_id=data.get("example_id", ""),
            feedback_count=data.get("feedback_count", 0),
            positive_feedback=data.get("positive_feedback", 0),
            negative_feedback=data.get("negative_feedback", 0),
            created_at=data.get("created_at", time.time()),
            last_updated=data.get("last_updated", time.time()),
        )


class FewShotExampleStore:
    """
    Few-Shot 示例存储管理器

    功能：
    - 添加/删除示例
    - 按意图获取最相关示例
    - 语义搜索相似示例
    - 质量评分和自动排序
    """

    def __init__(self):
        self._examples: Dict[str, FewShotExample] = {}
        self._intent_index: Dict[str, List[str]] = defaultdict(list)
        self._load_predefined_examples()

    def add_example(self, example: FewShotExample) -> str:
        """添加示例到存储"""
        if example.example_id in self._examples:
            existing = self._examples[example.example_id]
            existing.quality_score = max(existing.quality_score, example.quality_score)
            existing.last_updated = time.time()
            return existing.example_id

        self._examples[example.example_id] = example
        self._intent_index[example.intent_type].append(example.example_id)
        return example.example_id

    def get_examples(self, intent_type: str, top_k: int = 3) -> List[FewShotExample]:
        """按意图获取最相关的 top_k 个示例（按质量评分排序）"""
        intent_type_upper = intent_type.upper()
        example_ids = self._intent_index.get(intent_type_upper, [])

        examples = []
        for eid in example_ids:
            if eid in self._examples:
                examples.append(self._examples[eid])

        examples.sort(key=lambda e: e.quality_score, reverse=True)
        return examples[:top_k]

    def search_examples(self, query: str, top_k: int = 5) -> List[FewShotExample]:
        """基于文本相似度搜索最相关的示例"""
        if not self._examples:
            return []

        query_lower = query.lower()
        scored_examples = []

        for example in self._examples.values():
            score = self._compute_similarity(query_lower, example)
            final_score = score * 0.6 + example.quality_score * 0.4
            scored_examples.append((final_score, example))

        scored_examples.sort(key=lambda x: x[0], reverse=True)
        return [ex for _, ex in scored_examples[:top_k]]

    def remove_example(self, example_id: str) -> bool:
        """删除指定示例"""
        if example_id not in self._examples:
            return False

        example = self._examples.pop(example_id)
        intent = example.intent_type
        if intent in self._intent_index:
            self._intent_index[intent] = [
                eid for eid in self._intent_index[intent] if eid != example_id
            ]
            if not self._intent_index[intent]:
                del self._intent_index[intent]

        return True

    def update_feedback(self, example_id: str, is_positive: bool) -> Optional[float]:
        """更新示例的反馈并返回新的质量评分"""
        if example_id not in self._examples:
            return None

        example = self._examples[example_id]
        example.update_quality_from_feedback(is_positive)
        return example.quality_score

    def get_stats(self) -> dict:
        """获取示例库统计信息"""
        intent_counts = {
            intent: len(ids) for intent, ids in self._intent_index.items()
        }
        avg_quality = (
            sum(e.quality_score for e in self._examples.values())
            / len(self._examples)
            if self._examples
            else 0.0
        )
        return {
            "total_examples": len(self._examples),
            "intent_distribution": intent_counts,
            "average_quality_score": round(avg_quality, 4),
        }

    def _compute_similarity(self, query: str, example: FewShotExample) -> float:
        """计算查询与示例之间的文本相似度"""
        q_tokens = set(query.split())
        question_tokens = set(example.question.lower().split())
        context_tokens = set(example.context.lower().split())

        q_question_overlap = len(q_tokens & question_tokens)
        q_context_overlap = len(q_tokens & context_tokens)

        question_weight = 0.7
        context_weight = 0.3

        question_sim = q_question_overlap / max(len(q_tokens | question_tokens), 1)
        context_sim = q_context_overlap / max(len(q_tokens | context_tokens), 1)

        return question_weight * question_sim + context_weight * context_sim

    def _load_predefined_examples(self):
        """加载预定义的高质量 Few-Shot 示例"""
        predefined = self._get_predefined_examples()
        for example in predefined:
            self.add_example(example)

    @staticmethod
    def _get_predefined_examples() -> List[FewShotExample]:
        """返回预定义的 OCG 规则问答示例"""
        return [
            FewShotExample(
                question="通常魔法和速攻魔法的区别是什么？",
                context="游戏王规则书：魔法卡分为通常魔法、速攻魔法、永续魔法等类型。通常魔法只能在主要阶段从手牌发动，发动后送入墓地。速攻魔法可以从手牌或场上发动，且可以在对方回合发动。",
                answer="通常魔法只能在己方主要阶段从手牌发动，发动后送入墓地；速攻魔法除了可以在己方主要阶段发动外，还可以在对方回合发动（需先覆盖在场）。",
                intent_type="COMPARE_QUERY",
                quality_score=0.95,
            ),
            FewShotExample(
                question="什么是连锁？",
                context="游戏王规则书：连锁是指当多个效果在同一时点发动时，按照后发先至的顺序依次处理的效果处理机制。连锁的构建从效果发动开始，每个新发动的效果添加到连锁的最顶端。",
                answer="连锁是指多个效果发动时的处理顺序机制。按照'后发先至'的原则，最后发动的效果最先处理。例如：C1 为 A 效果，C2 为 B 效果，则先处理 B 再处理 A。",
                intent_type="CONCEPT_QUERY",
                quality_score=0.92,
            ),
            FewShotExample(
                question="额外卡组可以放多少张卡？",
                context="游戏王规则书：额外卡组最多可以包含15张卡，包括融合怪兽、同调怪兽、超量怪兽和连接怪兽。额外卡组不计算在主卡组的40-60张限制内。",
                answer="额外卡组最多可以放入15张卡，包括融合、同调、超量和连接怪兽。",
                intent_type="RULE_QUERY",
                quality_score=0.98,
            ),
            FewShotExample(
                question="同调召唤的步骤是什么？",
                context="游戏王规则书：同调召唤需要将自己场上的调整怪兽和调整以外的怪兽送入墓地，然后从额外卡组特殊召唤一只等级与送入墓地怪兽的等级之和相同的同调怪兽。",
                answer="同调召唤步骤：1）确认自己场上的调整和调整以外怪兽；2）将它们的等级加起来；3）将这些怪兽送入墓地；4）从额外卡组特殊召唤一只等级之和相同的同调怪兽。",
                intent_type="OPERATION_QUERY",
                quality_score=0.90,
            ),
            FewShotExample(
                question="怪兽的攻击力如何计算？",
                context="游戏王规则书：怪兽的攻击力以卡片上记载的数值为基础。装备魔法卡、效果增益或减益会修改实际攻击力。攻击力可以为负数，但不会低于0进行战斗伤害计算。",
                answer="怪兽攻击力 = 卡片记载的基础攻击力 + 装备卡加成 + 效果增益 - 效果减益。最低按0计算战斗伤害。",
                intent_type="RULE_QUERY",
                quality_score=0.88,
            ),
            FewShotExample(
                question="超量召唤和同调召唤有什么区别？",
                context="游戏王规则书：超量召唤是将等级相同的怪兽重叠作为超量素材，从额外卡组特殊召唤超量怪兽。同调召唤是将调整和调整以外怪兽的等级求和，特殊召唤相同等级的同调怪兽。",
                answer="超量召唤：将等级相同的怪兽重叠作为素材，召唤等级小于等于素材等级的超量怪兽。同调召唤：将调整+非调整怪兽的等级求和，召唤等级恰好等于该和的同调怪兽。超量素材不参与等级计算。",
                intent_type="COMPARE_QUERY",
                quality_score=0.93,
            ),
            FewShotExample(
                question="什么是战斗阶段？",
                context="游戏王规则书：战斗阶段是回合的第三个阶段，位于主要阶段1之后、主要阶段2之前。在战斗阶段中，玩家可以使用怪兽进行攻击宣言，处理战斗伤害。",
                answer="战斗阶段是回合的第三阶段，位于主要阶段1之后。在此阶段玩家可以进行攻击宣言、计算战斗伤害。若场上没有怪兽或玩家选择不攻击，也可以跳过战斗阶段。",
                intent_type="CONCEPT_QUERY",
                quality_score=0.91,
            ),
            FewShotExample(
                question="场上表侧表示的永续魔法被破坏后怎么处理？",
                context="游戏王规则书：永续魔法卡发动后持续留在场上，直到被破坏或从游戏中除外。被破坏的永续魔法送入墓地，其持续效果不再适用。",
                answer="场上表侧表示的永续魔法被破坏后送入墓地，其持续生效的效果不再适用。",
                intent_type="RULE_QUERY",
                quality_score=0.94,
            ),
            FewShotExample(
                question="如何进行连接召唤？",
                context="游戏王规则书：连接召唤需要将自己场上满足连接标记数量和连接素材要求的怪兽送入墓地，然后从额外卡组特殊召唤对应的连接怪兽。连接素材需要满足怪兽种类和数量要求。",
                answer="连接召唤步骤：1）确认额外卡组中要召唤的连接怪兽及其素材要求；2）将自己场上符合条件的怪兽送入墓地；3）从额外卡组特殊召唤该连接怪兽到额外怪兽区域或连接端。",
                intent_type="OPERATION_QUERY",
                quality_score=0.89,
            ),
            FewShotExample(
                question="什么是优先权？",
                context="游戏王规则书：优先权是指在某个时点谁可以先发动效果或进行行动的权利。回合玩家在各个阶段和步骤开始时拥有优先权，可以选择发动效果或放弃优先权让对手发动。",
                answer="优先权是指决定谁可以在某个时点先发动效果的权利。回合玩家在各阶段开始时拥有优先权，可以发动效果或传递给对方。",
                intent_type="CONCEPT_QUERY",
                quality_score=0.87,
            ),
            FewShotExample(
                question="融合召唤和仪式召唤的区别是什么？",
                context="游戏王规则书：融合召唤需要使用融合魔法卡将素材怪兽从手牌或场上送入墓地，从额外卡组特殊召唤融合怪兽。仪式召唤需要使用仪式魔法卡，将手牌或场上的怪兽解放，从手牌特殊召唤仪式怪兽。",
                answer="融合召唤：用融合魔法将素材送墓，从额外卡组召唤融合怪兽。仪式召唤：用仪式魔法解放怪兽，从手牌召唤仪式怪兽。融合怪兽在额外卡组，仪式怪兽在主卡组。",
                intent_type="COMPARE_QUERY",
                quality_score=0.96,
            ),
            FewShotExample(
                question="主卡组的卡数量限制是多少？",
                context="游戏王规则书：主卡组（Main Deck）必须包含至少40张卡，最多60张卡。额外卡组最多15张。副卡组（Side Deck）最多15张。同名卡在主卡组、额外卡组和副卡组中合计最多3张。",
                answer="主卡组最少40张，最多60张。同名卡最多3张（主+副+额外合计）。",
                intent_type="RULE_QUERY",
                quality_score=0.97,
            ),
            FewShotExample(
                question="如何处理同时发动的多个效果？",
                context="游戏王规则书：当多个效果在同一时点发动时，它们按照连锁的方式处理。回合玩家的强制效果优先构成连锁，然后是回合玩家的任意效果，接着是对方的强制效果，最后是对方的任意效果。",
                answer="同一时点多个效果按以下顺序构成连锁：1）回合玩家强制效果；2）回合玩家任意效果；3）对方强制效果；4）对方任意效果。之后按后发先至顺序处理。",
                intent_type="OPERATION_QUERY",
                quality_score=0.91,
            ),
            FewShotExample(
                question="什么是卡时点？",
                context="游戏王规则书：卡时点（Missing the Timing）是指某些'当...时'发动的效果，在条件满足后如果中间插入了其他效果处理，则可能错过发动时机的现象。只有'可以'发动的选发效果会受到卡时点影响。",
                answer="卡时点是指选发效果（'...时，可以发动'）在条件满足后，若中间有其他效果或操作插入，则可能错过发动时机的规则。必发效果（'...时，必须发动'）不受卡时点影响。",
                intent_type="CONCEPT_QUERY",
                quality_score=0.85,
            ),
            FewShotExample(
                question="反击陷阱和普通陷阱有什么区别？",
                context="游戏王规则书：反击陷阱是陷阱卡的一种，咒速为3，可以对应咒速2及以下的效果发动。普通陷阱咒速为2，只能对应咒速1的效果或在合适时点直接发动。",
                answer="反击陷阱咒速为3，可以连锁咒速2及以下的效果进行无效化。普通陷阱咒速为2，无法连锁其他陷阱或速攻魔法。反击陷阱通常具有无效化效果，但数量较少。",
                intent_type="COMPARE_QUERY",
                quality_score=0.92,
            ),
            FewShotExample(
                question="如何进行融合召唤？",
                context="游戏王规则书：融合召唤需要使用融合魔法卡（如'融合'），将融合素材怪兽从手牌或场上送入墓地，然后从额外卡组特殊召唤指定的融合怪兽。部分怪兽有特殊的融合召唤条件。",
                answer="融合召唤步骤：1）从额外卡组确认要召唤的融合怪兽及素材；2）发动融合魔法卡；3）将素材怪兽从手牌或场上送入墓地；4）从额外卡组特殊召唤融合怪兽到怪兽区域。",
                intent_type="OPERATION_QUERY",
                quality_score=0.93,
            ),
        ]


_default_store: Optional[FewShotExampleStore] = None


def get_default_store() -> FewShotExampleStore:
    """获取默认的 Few-Shot 示例存储"""
    global _default_store
    if _default_store is None:
        _default_store = FewShotExampleStore()
    return _default_store


def reset_default_store():
    """重置默认存储（用于测试）"""
    global _default_store
    _default_store = None
