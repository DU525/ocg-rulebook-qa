from typing import List, Optional

try:
    from app.core.few_shot_examples import FewShotExample
    HAS_FEW_SHOT = True
except ImportError:
    HAS_FEW_SHOT = False


# 优化点3的细分方向1: Few-Shot示例增强 - 使用更丰富的示例
DEFAULT_TEMPLATE = """你是一个专业的游戏王OCG规则问答助手。请根据提供的上下文信息回答问题。

【思考步骤】（优化点3-2: 链式思考Chain-of-Thought）
1. 首先理解用户的问题意图
2. 在上下文中查找相关规则
3. 分析规则如何应用于该问题
4. 组织答案结构
5. 验证答案准确性（优化点3-5: 自我验证）

回答格式：（优化点3-3: 答案格式严格化）
【答案】
<直接给出准确答案，不包含思考过程>

【引用来源】
[来源：章节标题]

规则：
1. 基于上下文回答，不编造信息
2. 直接给出答案，不使用<think>标签或冗长解释
3. 必须引用相关规则条款
4. 若上下文中无相关信息，直接回复"知识库中未找到相关信息"
5. 保持回答简洁专业
6. 自我验证：确认答案有上下文支持，没有幻觉内容

对话历史：
- 根据对话历史理解指代词（如"它"、"那个"）
- 结合上下文理解用户意图"""


RULE_QUERY_TEMPLATE = """你是一个专业的游戏王OCG规则问答助手。用户正在查询具体规则条款。

回答格式：
【答案】
<直接引用或解释相关规则>

【引用来源】
[来源：章节标题]

规则：
1. 精确引用规则条款，不添加个人解释
2. 直接给出答案，不使用<think>标签
3. 若规则不存在于上下文中，直接回复"知识库中未找到相关信息"
4. 保持回答简洁，仅包含必要信息"""


CONCEPT_QUERY_TEMPLATE = """你是一个专业的游戏王OCG规则问答助手。用户正在查询游戏概念或术语定义。

回答格式：
【答案】
<直接给出概念定义或解释>

【引用来源】
[来源：章节标题]

规则：
1. 准确解释概念，基于上下文信息
2. 直接给出答案，不使用<think>标签
3. 若概念不存在于上下文中，直接回复"知识库中未找到相关信息"
4. 保持解释简洁明了"""


COMPARE_QUERY_TEMPLATE = """你是一个专业的游戏王OCG规则问答助手。用户正在对比两个或多个规则/概念/卡牌效果。

回答格式：
【答案】
<直接对比差异和相同点>

【引用来源】
[来源：章节标题]

规则：
1. 清晰列出对比项的差异
2. 直接给出答案，不使用<think>标签
3. 若信息不足，直接回复"知识库中未找到相关信息"
4. 保持对比简洁，使用条目式表达"""


OPERATION_QUERY_TEMPLATE = """你是一个专业的游戏王OCG规则问答助手。用户正在询问游戏操作流程或步骤。

回答格式：
【答案】
<直接给出操作步骤>

【引用来源】
[来源：章节标题]

规则：
1. 按顺序列出操作步骤
2. 直接给出答案，不使用<think>标签
3. 若操作步骤不存在于上下文中，直接回复"知识库中未找到相关信息"
4. 保持步骤清晰简洁"""


TEMPLATE_MAP = {
    "default": DEFAULT_TEMPLATE,
    "rule": RULE_QUERY_TEMPLATE,
    "concept": CONCEPT_QUERY_TEMPLATE,
    "compare": COMPARE_QUERY_TEMPLATE,
    "operation": OPERATION_QUERY_TEMPLATE,
}


def get_template(template_type: str = "default") -> str:
    return TEMPLATE_MAP.get(template_type.lower(), DEFAULT_TEMPLATE)


INTENT_MAX_TOKENS = {
    "RULE_QUERY": 300,
    "CONCEPT_QUERY": 200,
    "COMPARE_QUERY": 400,
    "OPERATION_QUERY": 150,
    "DEFAULT": 250,
}


def get_max_tokens_by_intent(intent: str) -> int:
    return INTENT_MAX_TOKENS.get(intent.upper(), INTENT_MAX_TOKENS["DEFAULT"])


class PromptConfig:
    def __init__(
        self,
        template_type: str = "default",
        max_tokens: int = 250,
        few_shot_examples: List["FewShotExample"] = None,
    ):
        self.template_type = template_type
        self.max_tokens = max_tokens
        self.few_shot_examples = few_shot_examples or []

    @classmethod
    def from_intent(cls, intent: str, few_shot_examples: List["FewShotExample"] = None) -> "PromptConfig":
        intent_upper = intent.upper()
        template_type_map = {
            "RULE_QUERY": "rule",
            "CONCEPT_QUERY": "concept",
            "COMPARE_QUERY": "compare",
            "OPERATION_QUERY": "operation",
        }
        template_type = template_type_map.get(intent_upper, "default")
        max_tokens = get_max_tokens_by_intent(intent)
        return cls(template_type=template_type, max_tokens=max_tokens, few_shot_examples=few_shot_examples)


def build_few_shot_context(examples: List["FewShotExample"]) -> str:
    if not examples:
        return ""

    lines = ["\n【参考示例】"]
    for i, example in enumerate(examples, 1):
        if isinstance(example, dict):
            q = example.get("question", "")
            a = example.get("answer", "")
            score = example.get("quality_score", 1.0)
        else:
            q = example.question
            a = example.answer
            score = getattr(example, "quality_score", 1.0)

        lines.append(f"\n示例{i}（质量评分: {score:.2f}）：")
        lines.append(f"问：{q}")
        lines.append(f"答：{a}")

    lines.append("")
    return "\n".join(lines)


def classify_query(query: str) -> str:
    query_lower = query.lower()

    compare_keywords = ["对比", "区别", "差异", "比较", "和...有什么不同", "与...相比"]
    for kw in compare_keywords:
        if kw in query_lower:
            return "compare"

    operation_keywords = ["怎么", "如何", "步骤", "流程", "操作", "怎么做", "怎样做", "怎样做"]
    for kw in operation_keywords:
        if kw in query_lower:
            return "operation"

    concept_keywords = ["什么是", "定义", "意思", "含义", "是指", "什么叫", "什么概念"]
    for kw in concept_keywords:
        if kw in query_lower:
            return "concept"

    rule_keywords = ["规则", "条款", "规定", "规则书", "能否", "可以吗", "是不是"]
    for kw in rule_keywords:
        if kw in query_lower:
            return "rule"

    return "default"


# 优化点3的完整实现：增强的Prompt构建器
class EnhancedPromptBuilder:
    """
    增强的Prompt构建器
    实现优化点3的所有5个细分方向
    """
    
    def __init__(self, enable_cot: bool = True, enable_self_verify: bool = True):
        self.enable_cot = enable_cot  # 链式思考
        self.enable_self_verify = enable_self_verify  # 自我验证
    
    def build_prompt(
        self,
        query: str,
        contexts: List[str],
        template_type: str = "default",
        few_shot_examples: Optional[List["FewShotExample"]] = None,
        conversation_history: Optional[List[str]] = None,
    ) -> str:
        """
        构建完整的Prompt
        
        整合：
        1. Few-Shot示例增强
        2. 链式思考
        3. 答案格式严格化
        4. 思维模板（针对不同查询类型）
        5. 自我验证引导
        """
        template = get_template(template_type)
        
        prompt_parts = [template]
        
        # 1. 添加Few-Shot示例（优化点3-1）
        if few_shot_examples and HAS_FEW_SHOT:
            few_shot_context = build_few_shot_context(few_shot_examples)
            if few_shot_context:
                prompt_parts.append(few_shot_context)
        
        # 2. 添加上下文信息
        if contexts:
            prompt_parts.append("\n【参考上下文】")
            for i, ctx in enumerate(contexts, 1):
                prompt_parts.append(f"{i}. {ctx}")
        
        # 3. 添加对话历史
        if conversation_history:
            prompt_parts.append("\n【对话历史】")
            for msg in conversation_history[-3:]:  # 最近3条
                prompt_parts.append(f"- {msg}")
        
        # 4. 添加最终查询
        prompt_parts.append(f"\n【用户问题】{query}")
        
        # 5. 根据查询类型添加思维模板（优化点3-4）
        thought_instruction = self._get_thought_instruction(template_type)
        if thought_instruction:
            prompt_parts.append(thought_instruction)
        
        return "\n".join(prompt_parts)
    
    def _get_thought_instruction(self, template_type: str) -> Optional[str]:
        """
        优化点3-4: 思维模板Thought Templates
        根据查询类型提供针对性的思考引导
        """
        instructions = {
            "rule": """【规则查询思维模板】
请按照以下思路组织回答：
1. 定位到具体的规则条款
2. 提取关键规则内容
3. 确认规则的适用条件
4. 给出明确的规则说明""",
            
            "concept": """【概念查询思维模板】
请按照以下思路组织回答：
1. 明确概念的定义
2. 说明概念的关键特征
3. 指出概念的应用场景
4. 提供简洁明了的解释""",
            
            "compare": """【对比查询思维模板】
请按照以下思路组织回答：
1. 分别理解每个对比项
2. 找出相同点和差异点
3. 按维度列出对比内容
4. 给出清晰的对比结论""",
            
            "operation": """【操作查询思维模板】
请按照以下思路组织回答：
1. 确认操作的目标
2. 按顺序列出步骤
3. 说明每个步骤的要点
4. 注意可能的特殊情况""",
        }
        
        return instructions.get(template_type)
