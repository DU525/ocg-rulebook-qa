"""Shared domain services for OCG and DM backends."""
from dataclasses import dataclass, field
from typing import Dict, Callable, Any


@dataclass
class DomainConfig:
    """Configuration for a single game domain."""
    name: str
    url_prefix: str
    db_path: str
    vector_store_path: str
    chunks_file: str
    index_file: str
    system_prompt: str
    prompt_templates: Dict[str, str] = field(default_factory=dict)
    default_template: str = "default"
    collection_name: str = "rules"


class SharedProviderFactory:
    """Unified LLM provider factory, shared by OCG and DM."""

    @staticmethod
    def build_provider(provider_name: str, fallback_provider_name: str, config: Any):
        from app.services.llm_provider import LLMProviderFactory, LLMProviderWithFallback

        primary_api_key, primary_api_base, primary_model_name = _resolve_provider_config(provider_name, config)
        primary = LLMProviderFactory.create(
            provider_name,
            api_key=primary_api_key,
            api_base=primary_api_base,
            model_name=primary_model_name,
        )

        fallback_api_key, fallback_api_base, fallback_model_name = _resolve_provider_config(fallback_provider_name, config)
        fallback = LLMProviderFactory.create(
            fallback_provider_name,
            api_key=fallback_api_key,
            api_base=fallback_api_base,
            model_name=fallback_model_name,
        )

        provider = LLMProviderWithFallback(primary, [fallback])
        print(f"[Provider] Main: {provider_name}({primary_model_name}), Fallback: {fallback_provider_name}({fallback_model_name})")
        return provider


def _resolve_provider_config(provider_name: str, config: Any):
    """Resolve provider config from the application Config class."""
    provider_name_lower = provider_name.lower().strip()
    if provider_name_lower == "minimax":
        return config.MINIMAX_API_KEY, config.MINIMAX_API_BASE, config.MODEL_NAME
    elif provider_name_lower == "openai":
        return config.OPENAI_API_KEY, config.OPENAI_API_BASE, config.OPENAI_MODEL_NAME
    else:
        return config.OPENAI_API_KEY, config.OPENAI_API_BASE, config.OPENAI_MODEL_NAME


# Default prompt templates
OCG_PROMPT_TEMPLATES = {
    "default": "你是一个专业的游戏王OCG规则问答助手。\n你的任务是根据提供的上下文信息，准确回答用户关于游戏王OCG规则的问题。\n\n回答要求：\n1. 基于提供的上下文信息进行回答，不要编造信息\n2. 回答必须引用相关的规则条款，格式：[来源：章节标题]\n3. 对于不确定的问题，明确告知用户该信息在知识库中未找到\n4. 回答应该清晰、准确、专业\n\n【对话历史理解】\n- 如果用户的问题涉及\"它\"、\"那个\"等指代词，请根据对话历史确定用户指的是什么\n- 如果用户追问或延续之前的话题，请结合历史上下文理解用户的真实意图\n- 如果用户纠正之前的回答，请承认并给出正确的解释\n\n注意：如果上下文中没有相关信息，请直接说明，不要猜测。",
    "concise": "你是一个游戏王OCG规则专家。请用最简洁的语言回答用户关于OCG规则的问题，直接给出结论和关键引用。不需要展开解释，除非用户明确要求。\n\n回答要求：\n1. 优先简洁直接，一句话讲清楚核心答案\n2. 引用格式：[来源：章节标题]\n3. 不确定时直接说明",
    "detailed": "你是一个游戏王OCG规则详解助手。请尽可能详细地回答用户关于OCG规则的问题，包括规则背景、相关卡牌类型、常见误区等。\n\n回答要求：\n1. 先给出简明结论，再展开详细说明\n2. 引用所有相关的规则条款，格式：[来源：章节标题]\n3. 涉及多种情况时，逐一列举分析\n4. 指出常见的误解和需要注意的细节\n5. 对于不确定的问题，说明不确定的原因和可能的解释方向",
}

DM_PROMPT_TEMPLATES = {
    "default": "你是一个专业的数码宝贝卡牌规则问答助手。\n你的任务是根据提供的上下文信息，准确回答用户关于数码宝贝卡牌规则的问题。\n\n回答要求：\n1. 基于提供的上下文信息进行回答，不要编造信息\n2. 回答必须引用相关的规则条款，格式：[来源：章节标题]\n3. 对于不确定的问题，明确告知用户该信息在知识库中未找到\n4. 回答应该清晰、准确、专业\n\n【对话历史理解】\n- 如果用户的问题涉及\"它\"、\"那个\"等指代词，请根据对话历史确定用户指的是什么\n- 如果用户追问或延续之前的话题，请结合历史上下文理解用户的真实意图\n\n注意：如果上下文中没有相关信息，请直接说明，不要猜测。",
    "concise": "你是一个数码宝贝卡牌规则专家。请用最简洁的语言回答用户关于数码宝贝卡牌规则的问题，直接给出结论和关键引用。\n\n回答要求：\n1. 优先简洁直接\n2. 引用格式：[来源：章节标题]\n3. 不确定时直接说明",
    "detailed": "你是一个数码宝贝卡牌规则详解助手。请尽可能详细地回答用户关于数码宝贝卡牌规则的问题，包括规则背景、相关卡牌类型等。\n\n回答要求：\n1. 先给出简明结论，再展开详细说明\n2. 引用所有相关的规则条款\n3. 涉及多种情况时，逐一列举分析",
}


OCG_RAG_CONFIG = {
    "top_k": 5,
    "temperature": 0.3,
    "max_tokens": 1500,
    "system_prompt_template": "default",
    "streaming_enabled": False,
    "similarity_threshold": 0.5,
}

DM_RAG_CONFIG = {
    "top_k": 5,
    "temperature": 0.3,
    "max_tokens": 1500,
    "system_prompt_template": "default",
    "streaming_enabled": False,
    "similarity_threshold": 0.5,
}
