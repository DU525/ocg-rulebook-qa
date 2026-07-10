"""DM routes - thin wrapper around shared BaseRouteHandler."""
from flask import Blueprint
from app.api.base_routes import BaseRouteHandler

api = Blueprint('dm_api', __name__, url_prefix='/api/v1/dm')

vector_store = None
rag_engine = None
db = None
skill_registry = None
agent_instance = None

PROMPT_TEMPLATES = {
    'default': "你是一个专业的数码宝贝卡牌规则问答助手。\n你的任务是根据提供的上下文信息，准确回答用户关于数码宝贝卡牌规则的问题。\n\n回答要求：\n1. 基于提供的上下文信息进行回答，不要编造信息\n2. 回答必须引用相关的规则条款，格式：[来源：章节标题]\n3. 对于不确定的问题，明确告知用户该信息在知识库中未找到\n4. 回答应该清晰、准确、专业\n\n【对话历史理解】\n- 如果用户的问题涉及\"它\"、\"那个\"等指代词，请根据对话历史确定用户指的是什么\n- 如果用户追问或延续之前的话题，请结合历史上下文理解用户的真实意图\n\n注意：如果上下文中没有相关信息，请直接说明，不要猜测。",
    'concise': "你是一个数码宝贝卡牌规则专家。请用最简洁的语言回答用户关于数码宝贝卡牌规则的问题，直接给出结论和关键引用。\n\n回答要求：\n1. 优先简洁直接\n2. 引用格式：[来源：章节标题]\n3. 不确定时直接说明",
    'detailed': "你是一个数码宝贝卡牌规则详解助手。请尽可能详细地回答用户关于数码宝贝卡牌规则的问题，包括规则背景、相关卡牌类型等。\n\n回答要求：\n1. 先给出简明结论，再展开详细说明\n2. 引用所有相关的规则条款\n3. 涉及多种情况时，逐一列举分析",
}


def init_dm_services():
    return init_services()


def init_services():
    from app.db.dm_vector_store import DMVectorStore
    from app.db.dm_models import DMDatabase
    from app.services.llm_provider import LLMProviderFactory, LLMProviderWithFallback
    from app.config import Config
    from app.core.rag_engine import RAGEngine

    global vector_store, rag_engine, db
    vector_store = DMVectorStore(Config.DM_CHROMA_DB_PATH)
    db = DMDatabase(Config.DM_SQLITE_DB_PATH)

    provider_name_lower = Config.LLM_PROVIDER.lower().strip()
    if provider_name_lower == "minimax":
        primary_api_key, primary_api_base, primary_model_name = Config.MINIMAX_API_KEY, Config.MINIMAX_API_BASE, Config.MODEL_NAME
    else:
        primary_api_key, primary_api_base, primary_model_name = Config.OPENAI_API_KEY, Config.OPENAI_API_BASE, Config.OPENAI_MODEL_NAME
    primary = LLMProviderFactory.create(Config.LLM_PROVIDER, api_key=primary_api_key, api_base=primary_api_base, model_name=primary_model_name)

    fallback_name_lower = Config.DM_FALLBACK_PROVIDER.lower().strip() if hasattr(Config, 'DM_FALLBACK_PROVIDER') else Config.FALLBACK_PROVIDER.lower().strip()
    if fallback_name_lower == "minimax":
        fb_api_key, fb_api_base, fb_model_name = Config.MINIMAX_API_KEY, Config.MINIMAX_API_BASE, Config.DM_FALLBACK_MODEL_NAME if hasattr(Config, 'DM_FALLBACK_MODEL_NAME') else Config.MODEL_NAME
    else:
        fb_api_key, fb_api_base, fb_model_name = Config.OPENAI_API_KEY, Config.OPENAI_API_BASE, Config.OPENAI_MODEL_NAME
    fallback = LLMProviderFactory.create(fallback_name_lower, api_key=fb_api_key, api_base=fb_api_base, model_name=fb_model_name)

    provider = LLMProviderWithFallback(primary, [fallback])
    print("[DM-Provider] 主: {}({}), 降级: {}({})".format(Config.LLM_PROVIDER, primary_model_name, fallback_name_lower, fb_model_name))

    rag_engine = RAGEngine(vector_store=vector_store, provider=provider)

    # 预热 text2vec 模型（可选，失败不影响主流程）
    try:
        print("[DM预热] 加载 text2vec 模型...")
        _ = vector_store.search("预热查询", n_results=1)
        print("[DM预热] 模型加载完成")
    except Exception as e:
        print("[DM预热] text2vec 加载失败: {}".format(e))

    from app.db.dm_models import DMConversation, DMMessage, DMDocument
    from app.db.models import Feedback, Alert, AlertRule, PerformanceLog, NegativeSample

    BaseRouteHandler(api, vector_store, db, rag_engine, 'dm', PROMPT_TEMPLATES, {
        'Conversation': DMConversation,
        'Message': DMMessage,
        'Document': DMDocument,
        'Alert': Alert,
        'AlertRule': AlertRule,
        'PerformanceLog': PerformanceLog,
        'Feedback': Feedback,
        'NegativeSample': NegativeSample,
    })


dm_vector_store = vector_store
dm_rag_engine = rag_engine
dm_db = db
