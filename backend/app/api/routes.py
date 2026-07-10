"""OCG routes - thin wrapper around shared BaseRouteHandler."""
from flask import Blueprint
from app.api.base_routes import BaseRouteHandler

api = Blueprint('api', __name__, url_prefix='/api/v1')

vector_store = None
rag_engine = None
db = None
skill_registry = None
agent_instance = None

PROMPT_TEMPLATES = {
    'default': "你是一个专业的游戏王OCG规则问答助手。\n你的任务是根据提供的上下文信息，准确回答用户关于游戏王OCG规则的问题。\n\n回答要求：\n1. 基于提供的上下文信息进行回答，不要编造信息\n2. 回答必须引用相关的规则条款，格式：[来源：章节标题]\n3. 对于不确定的问题，明确告知用户该信息在知识库中未找到\n4. 回答应该清晰、准确、专业\n\n【对话历史理解】\n- 如果用户的问题涉及\"它\"、\"那个\"等指代词，请根据对话历史确定用户指的是什么\n- 如果用户追问或延续之前的话题，请结合历史上下文理解用户的真实意图\n- 如果用户纠正之前的回答，请承认并给出正确的解释\n\n注意：如果上下文中没有相关信息，请直接说明，不要猜测。",
    'concise': "你是一个游戏王OCG规则专家。请用最简洁的语言回答用户关于OCG规则的问题，直接给出结论和关键引用。不需要展开解释，除非用户明确要求。\n\n回答要求：\n1. 优先简洁直接，一句话讲清楚核心答案\n2. 引用格式：[来源：章节标题]\n3. 不确定时直接说明",
    'detailed': "你是一个游戏王OCG规则详解助手。请尽可能详细地回答用户关于OCG规则的问题，包括规则背景、相关卡牌类型、常见误区等。\n\n回答要求：\n1. 先给出简明结论，再展开详细说明\n2. 引用所有相关的规则条款，格式：[来源：章节标题]\n3. 涉及多种情况时，逐一列举分析\n4. 指出常见的误解和需要注意的细节\n5. 对于不确定的问题，说明不确定的原因和可能的解释方向",
}


def init_services():
    from app.db.vector_store import VectorStore
    from app.db.models import Database
    from app.services.llm_provider import LLMProviderFactory, LLMProviderWithFallback
    from app.config import Config
    from app.services.skill_registry import SkillRegistry
    from app.services.agent import SimpleAgent, FunctionCallingAgent

    global vector_store, rag_engine, db, skill_registry, agent_instance
    from app.core.rag_engine import RAGEngine

    vector_store = VectorStore(Config.OCG_CHROMA_DB_PATH)
    db = Database(Config.OCG_SQLITE_DB_PATH)

    # Build provider
    provider_name_lower = Config.LLM_PROVIDER.lower().strip()
    if provider_name_lower == "minimax":
        primary_api_key, primary_api_base, primary_model_name = Config.MINIMAX_API_KEY, Config.MINIMAX_API_BASE, Config.MODEL_NAME
    else:
        primary_api_key, primary_api_base, primary_model_name = Config.OPENAI_API_KEY, Config.OPENAI_API_BASE, Config.OPENAI_MODEL_NAME
    primary = LLMProviderFactory.create(Config.LLM_PROVIDER, api_key=primary_api_key, api_base=primary_api_base, model_name=primary_model_name)

    fallback_name_lower = Config.FALLBACK_PROVIDER.lower().strip()
    if fallback_name_lower == "minimax":
        fb_api_key, fb_api_base, fb_model_name = Config.MINIMAX_API_KEY, Config.MINIMAX_API_BASE, Config.FALLBACK_MODEL_NAME if hasattr(Config, 'FALLBACK_MODEL_NAME') else Config.MODEL_NAME
    else:
        fb_api_key, fb_api_base, fb_model_name = Config.OPENAI_API_KEY, Config.OPENAI_API_BASE, Config.OPENAI_MODEL_NAME
    fallback = LLMProviderFactory.create(Config.FALLBACK_PROVIDER, api_key=fb_api_key, api_base=fb_api_base, model_name=fb_model_name)

    provider = LLMProviderWithFallback(primary, [fallback])
    print("[Provider] 主: {}({}), 降级: {}({})".format(Config.LLM_PROVIDER, primary_model_name, Config.FALLBACK_PROVIDER, fb_model_name))

    # RAG engine — 默认启用多阶段 RRF 融合
    rag_engine = RAGEngine(
        vector_store=vector_store,
        provider=provider,
        use_multi_stage=bool(getattr(Config, 'RRF_ENABLED', True)),
    )

    # ----- Skill 注册：覆盖 search_rules / calculate / get_card_info -----
    skill_registry = SkillRegistry()

    def _search_rules(query, top_k=5, search_type="hybrid"):
        """搜索 OCG 规则（按 search_type 切换 RRF / vector 路径）"""
        top_k = int(top_k) if top_k else 5
        use_multi_stage = (str(search_type).lower() in ("hybrid", "rrf")) and bool(getattr(Config, 'RRF_ENABLED', True))
        # RAGEngine.query() 现在支持 use_multi_stage 透传（2026-06-02 修复）
        # Agent 调 skill 时, search_type='hybrid' → 走 RRF 完整 pipeline
        #           search_type='vector' → 走纯向量检索
        response = rag_engine.query(
            query,
            top_k=top_k,
            use_multi_stage=use_multi_stage,
        )
        if not response or not getattr(response, "answer", None):
            return "未在知识库中找到相关信息。"
        return response.answer

    def _calculate(expression):
        """安全的数学计算（仅允许数字和基础运算符）"""
        if not expression or not isinstance(expression, str):
            return "无效的数学表达式"
        allowed = set("0123456789+-*/.() ")
        if not all(c in allowed for c in expression):
            return "无效的数学表达式：含不允许的字符"
        try:
            return str(eval(expression, {"__builtins__": {}}, {}))
        except Exception as e:
            return f"计算错误: {e}"

    def _get_card_info(card_name):
        """从知识库查找卡片信息（用 RAG 检索标题相关的内容）"""
        if not card_name or not isinstance(card_name, str):
            return {"error": "card_name 不能为空", "card": None}
        query = f"卡片 {card_name} 的效果/属性/种族/攻击力/守备力"
        response = rag_engine.query(query, top_k=3)
        if not response or not getattr(response, "answer", None):
            return {"card_name": card_name, "card": None, "note": "未在知识库中找到该卡片信息"}
        return {"card_name": card_name, "info": response.answer}

    skill_registry.register(
        name="search_rules",
        func=_search_rules,
        description="搜索游戏王OCG规则知识库（BM25+向量+RRF+Cross-Encoder 融合）",
        input_schema="query: 用户问题, top_k: int = 5, search_type: str = hybrid",
    )
    skill_registry.register(
        name="calculate",
        func=_calculate,
        description="执行数学计算（仅数字与基础运算符，安全 eval）",
        input_schema="query: 数学表达式",
    )
    skill_registry.register(
        name="get_card_info",
        func=_get_card_info,
        description="查询游戏王卡片信息（卡名/属性/种族/效果）",
        input_schema="query: 卡片名称",
    )

    # ----- Agent：按 Config.AGENT_TYPE 选择 SimpleAgent / FunctionCallingAgent -----
    agent_type = (getattr(Config, 'AGENT_TYPE', 'function_calling') or 'function_calling').lower().strip()
    if agent_type == 'simple':
        agent_instance = SimpleAgent(
            provider=provider,
            skill_registry=skill_registry,
            max_iterations=int(getattr(Config, 'AGENT_MAX_ITERATIONS', 5)),
        )
        print("[Agent] SimpleAgent (ReAct 文本解析模式)")
    else:
        agent_instance = FunctionCallingAgent(
            provider=provider,
            skill_registry=skill_registry,
            max_iterations=int(getattr(Config, 'AGENT_MAX_ITERATIONS', 5)),
        )
        print(f"[Agent] FunctionCallingAgent (MiniMax-M2.5 native tool_calls) — model={primary_model_name}, max_iterations={Config.AGENT_MAX_ITERATIONS}")

    # 预热 text2vec 模型（可选，失败不影响主流程）
    try:
        print("[预热] 加载 text2vec 模型...")
        _ = vector_store.search("预热查询", n_results=1)
        print("[预热] 模型加载完成，text2vec 已就绪")
    except Exception as e:
        print(f"[预热] text2vec 加载失败，将使用纯 BM25 检索: {e}")

    from app.db.models import Conversation, Message, Document, Alert, AlertRule, PerformanceLog, Feedback, NegativeSample
    BaseRouteHandler(api, vector_store, db, rag_engine, 'ocg', PROMPT_TEMPLATES, {
        'Conversation': Conversation,
        'Message': Message,
        'Document': Document,
        'Alert': Alert,
        'AlertRule': AlertRule,
        'PerformanceLog': PerformanceLog,
        'Feedback': Feedback,
        'NegativeSample': NegativeSample,
    }, agent_instance, skill_registry)
