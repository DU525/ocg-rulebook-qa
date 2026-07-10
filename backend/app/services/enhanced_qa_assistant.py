"""
增强QA智能助手 - 优化方向3
实现：规则推理链可视化、场景化问题模板、智能纠错与建议
"""
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from enum import Enum

logger = logging.getLogger(__name__)


class ReasoningStepType(Enum):
    """推理步骤类型"""
    RULE_RETRIEVAL = "rule_retrieval"
    FACT_VERIFICATION = "fact_verification"
    LOGICAL_DEDUCTION = "logical_deduction"
    CONCLUSION = "conclusion"


@dataclass
class ReasoningStep:
    """推理步骤"""
    step_number: int
    step_type: ReasoningStepType
    reasoning_text: str
    source_reference: Optional[str] = None
    source_knowledge_base: Optional[str] = None
    confidence: float = 0.95


@dataclass
class SceneTemplate:
    """场景模板"""
    scene_id: str
    scene_name: str
    category: str
    example_queries: List[str]
    recommended_sources: List[str]


@dataclass
class CorrectionSuggestion:
    """纠错建议"""
    original_query: str
    detected_issue: str
    suggested_query: str
    confidence: float
    additional_suggestions: List[str] = field(default_factory=list)


class EnhancedQAAssistant:
    """增强QA智能助手"""

    def __init__(self):
        self.scene_templates = self._init_scene_templates()
        self.common_errors = self._init_common_errors()
        self.reasoning_history: Dict[str, List[ReasoningStep]] = {}
        logger.info("Enhanced QA Assistant initialized")

    def _init_scene_templates(self) -> List[SceneTemplate]:
        """初始化场景模板库"""
        return [
            SceneTemplate(
                scene_id="summon",
                scene_name="召唤相关问题",
                category="mechanics",
                example_queries=[
                    "如何通常召唤？",
                    "特殊召唤的条件是什么？",
                    "反转召唤有什么效果？",
                    "超量召唤的规则是什么？"
                ],
                recommended_sources=["规则书第3章", "召唤规则FAQ"]
            ),
            SceneTemplate(
                scene_id="battle",
                scene_name="战斗阶段问题",
                category="mechanics",
                example_queries=[
                    "攻击步骤是怎样的？",
                    "伤害计算规则是什么？",
                    "攻击反应有哪些？",
                    "战斗伤害如何处理？"
                ],
                recommended_sources=["规则书第5章", "战斗FAQ"]
            ),
            SceneTemplate(
                scene_id="chain",
                scene_name="连锁相关问题",
                category="mechanics",
                example_queries=[
                    "连锁规则是什么？",
                    "优先权如何处理？",
                    "连锁1发动后如何处理？",
                    "同时发动的效果如何排序？"
                ],
                recommended_sources=["规则书第4章", "连锁FAQ"]
            ),
            SceneTemplate(
                scene_id="card_effect",
                scene_name="卡片效果问题",
                category="card_rules",
                example_queries=[
                    "这个效果在什么时候发动？",
                    "永续效果如何处理？",
                    "速攻魔法能在对方回合发动吗？",
                    "反击陷阱有什么特点？"
                ],
                recommended_sources=["规则书第6章", "效果FAQ"]
            ),
            SceneTemplate(
                scene_id="deck_building",
                scene_name="卡组构建问题",
                category="rules",
                example_queries=[
                    "卡组最多能有多少张卡？",
                    "限制卡和准限制卡有什么区别？",
                    "副卡组如何使用？",
                    "同名卡最多放几张？"
                ],
                recommended_sources=["规则书第1章", "禁限卡表"]
            )
        ]

    def _init_common_errors(self) -> Dict[str, Dict[str, Any]]:
        """初始化常见错误库"""
        return {
            "term_confusion": {
                "patterns": [
                    ("特效", "效果"),
                    ("生物", "怪兽"),
                    ("法术", "魔法"),
                    ("陷阱卡", "陷阱"),
                    ("融合卡", "融合魔法"),
                ],
                "suggestions": "使用正确的游戏王术语可以获得更准确的答案"
            },
            "missing_context": {
                "patterns": [
                    "它",
                    "那个",
                    "这张卡",
                    "这个效果",
                ],
                "suggestions": "请提供更具体的卡片名称或效果描述"
            },
            "typos": {
                "patterns": [
                    ("游戏亡", "游戏王"),
                    ("召唤兽", "召唤的怪兽"),
                    ("连索", "连锁"),
                ],
                "suggestions": "检测到可能的输入错误，已自动修正"
            }
        }

    def build_reasoning_chain(
        self,
        query: str,
        retrieved_contexts: List[Dict[str, Any]],
        kb_router_result: Optional[Dict[str, Any]] = None
    ) -> List[ReasoningStep]:
        """
        细分方向3.1：规则推理链可视化
        构建推理步骤链
        """
        steps = []
        
        # 步骤1：理解并分类问题
        steps.append(ReasoningStep(
            step_number=1,
            step_type=ReasoningStepType.RULE_RETRIEVAL,
            reasoning_text=f"分析用户问题：{query}",
            confidence=0.98
        ))
        
        # 步骤2：检索相关规则
        if retrieved_contexts:
            for i, ctx in enumerate(retrieved_contexts[:3], start=2):
                ctx_content = ctx.get('content', '')[:100] + '...' if len(ctx.get('content', '')) > 100 else ctx.get('content', '')
                steps.append(ReasoningStep(
                    step_number=i,
                    step_type=ReasoningStepType.RULE_RETRIEVAL,
                    reasoning_text=f"检索到相关规则：{ctx_content}",
                    source_reference=ctx.get('source', 'Unknown'),
                    source_knowledge_base=ctx.get('kb', 'OCG'),
                    confidence=ctx.get('score', 0.9)
                ))
        
        # 步骤3：验证事实
        steps.append(ReasoningStep(
            step_number=len(steps) + 1,
            step_type=ReasoningStepType.FACT_VERIFICATION,
            reasoning_text="验证检索到的规则是否适用于该问题",
            confidence=0.92
        ))
        
        # 步骤4：逻辑推导
        steps.append(ReasoningStep(
            step_number=len(steps) + 1,
            step_type=ReasoningStepType.LOGICAL_DEDUCTION,
            reasoning_text="根据规则进行逻辑推导",
            confidence=0.90
        ))
        
        # 步骤5：生成结论
        steps.append(ReasoningStep(
            step_number=len(steps) + 1,
            step_type=ReasoningStepType.CONCLUSION,
            reasoning_text="综合以上规则，生成最终答案",
            confidence=0.85
        ))
        
        return steps

    def format_reasoning_chain(self, steps: List[ReasoningStep]) -> Dict[str, Any]:
        """格式化推理链用于展示"""
        formatted = {
            'total_steps': len(steps),
            'steps': [],
            'confidence_summary': sum(s.confidence for s in steps) / len(steps) if steps else 0
        }
        
        for step in steps:
            formatted['steps'].append({
                'step': step.step_number,
                'type': step.step_type.value,
                'reasoning': step.reasoning_text,
                'source': step.source_reference,
                'kb': step.source_knowledge_base,
                'confidence': step.confidence
            })
        
        return formatted

    def suggest_scene_templates(
        self,
        query: str,
        top_k: int = 3
    ) -> List[SceneTemplate]:
        """
        细分方向3.2：场景化问题模板
        根据查询推荐相关场景
        """
        matched = []
        
        for template in self.scene_templates:
            score = 0
            query_lower = query.lower()
            
            # 简单的匹配评分
            for example in template.example_queries:
                for keyword in example.split(''):
                    if keyword in query_lower:
                        score += 1
            
            if score > 0:
                matched.append((template, score))
        
        # 按分数排序
        matched.sort(key=lambda x: x[1], reverse=True)
        
        return [template for template, score in matched[:top_k]]

    def get_scene_example_queries(self, scene_id: str) -> List[str]:
        """获取场景的示例查询"""
        for template in self.scene_templates:
            if template.scene_id == scene_id:
                return template.example_queries
        return []

    def detect_and_correct_query(
        self,
        query: str
    ) -> Optional[CorrectionSuggestion]:
        """
        细分方向3.3：智能纠错与建议
        检测查询中的问题并提供修正建议
        """
        original = query
        corrected = query
        issues = []
        additional_suggestions = []
        
        # 检测术语错误
        term_fixes = self._fix_terminology(query)
        if term_fixes:
            corrected = term_fixes['corrected']
            issues.append("术语使用可能有误")
            additional_suggestions.append(term_fixes['suggestion'])
        
        # 检测缺少上下文
        if self._missing_context_check(query):
            issues.append("问题可能缺少具体上下文")
            additional_suggestions.append("建议提供具体的卡片名称或规则引用")
        
        # 检测拼写错误
        typo_fixes = self._fix_typos(query)
        if typo_fixes:
            corrected = typo_fixes['corrected']
            issues.append("检测到可能的拼写错误")
            additional_suggestions.append(typo_fixes['suggestion'])
        
        if issues:
            return CorrectionSuggestion(
                original_query=original,
                detected_issue='; '.join(issues),
                suggested_query=corrected,
                confidence=0.8 if issues else 0.5,
                additional_suggestions=additional_suggestions
            )
        
        return None

    def _fix_terminology(self, query: str) -> Optional[Dict[str, str]]:
        """修正术语使用"""
        corrected = query
        needs_fix = False
        
        for wrong, correct in self.common_errors['term_confusion']['patterns']:
            if wrong in query:
                corrected = corrected.replace(wrong, correct)
                needs_fix = True
        
        if needs_fix:
            return {
                'corrected': corrected,
                'suggestion': self.common_errors['term_confusion']['suggestions']
            }
        return None

    def _fix_typos(self, query: str) -> Optional[Dict[str, str]]:
        """修正拼写错误"""
        corrected = query
        needs_fix = False
        
        for wrong, correct in self.common_errors['typos']['patterns']:
            if wrong in query:
                corrected = corrected.replace(wrong, correct)
                needs_fix = True
        
        if needs_fix:
            return {
                'corrected': corrected,
                'suggestion': self.common_errors['typos']['suggestions']
            }
        return None

    def _missing_context_check(self, query: str) -> bool:
        """检查是否缺少上下文"""
        vague_terms = ['它', '那个', '这张卡', '这个效果']
        return any(term in query for term in vague_terms)

    def generate_follow_up_suggestions(
        self,
        query: str,
        answer: str,
        reasoning_chain: List[ReasoningStep]
    ) -> List[str]:
        """生成后续问题建议"""
        suggestions = []
        
        # 基于推理链生成后续问题
        for step in reasoning_chain:
            if step.step_type == ReasoningStepType.RULE_RETRIEVAL:
                if '召唤' in step.reasoning_text:
                    suggestions.append("特殊召唤有哪些类型？")
                    suggestions.append("召唤规则有什么限制？")
                elif '连锁' in step.reasoning_text:
                    suggestions.append("连锁规则的详细说明？")
                    suggestions.append("优先权如何处理？")
                elif '战斗' in step.reasoning_text:
                    suggestions.append("战斗阶段详细说明？")
                    suggestions.append("伤害计算规则？")
        
        # 限制建议数量
        return suggestions[:5]

    def get_assistant_statistics(self) -> Dict[str, Any]:
        """获取助手统计"""
        return {
            'total_scenes': len(self.scene_templates),
            'total_error_patterns': sum(
                len(patterns['patterns']) 
                for patterns in self.common_errors.values()
            ),
            'supported_categories': list(set(t.category for t in self.scene_templates))
        }


# 全局单例
_enhanced_assistant = None

def get_enhanced_qa_assistant() -> EnhancedQAAssistant:
    """获取增强QA助手单例"""
    global _enhanced_assistant
    if _enhanced_assistant is None:
        _enhanced_assistant = EnhancedQAAssistant()
    return _enhanced_assistant
