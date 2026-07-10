import os

class Config:
    SECRET_KEY = os.environ.get('SECRET_KEY', 'dev-secret-key-change-in-production')

    # ==================== OCG 配置 ====================
    OCG_CHROMA_DB_PATH = os.path.join(
        os.path.dirname(__file__), '../../data/ocg_chroma_db'
    )

    OCG_SQLITE_DB_PATH = os.path.join(
        os.path.dirname(__file__), '../../data/ocg_qa.db'
    )

    OCG_DOCS_PATH = os.path.join(
        os.path.dirname(__file__), '../../data/ocg_rules'
    )

    # ==================== 数码宝贝 (DM) 配置 ====================
    DM_CHROMA_DB_PATH = os.path.join(
        os.path.dirname(__file__), '../../data/dm_chroma_db'
    )

    DM_SQLITE_DB_PATH = os.path.join(
        os.path.dirname(__file__), '../../data/dm_qa.db'
    )

    DM_DOCS_PATH = os.path.join(
        os.path.dirname(__file__), '../../data/dm_rules'
    )

    # ==================== 共享配置 ====================
    UPLOAD_PATH = os.path.join(
        os.path.dirname(__file__), '../../data/uploads'
    )

    # ==================== 飞书 (Feishu) 配置 ====================
    FEISHU_ENABLED = os.environ.get('FEISHU_ENABLED', 'false').lower() == 'true'
    FEISHU_BOT_TOKEN = os.environ.get('FEISHU_BOT_TOKEN', '')
    FEISHU_CHAT_ID = os.environ.get('FEISHU_CHAT_ID', '')
    FEISHU_USER_ID = os.environ.get('FEISHU_USER_ID', 'your-feishu-user-id-here')
    FEISHU_CLI_PATH = os.environ.get('FEISHU_CLI_PATH', 'lark-cli')

    # ==================== LLM Provider 配置 ====================
    LLM_PROVIDER = os.environ.get('LLM_PROVIDER', 'minimax')
    OPENAI_API_KEY = os.environ.get('OPENAI_API_KEY', '')
    OPENAI_API_BASE = os.environ.get('OPENAI_API_BASE', 'https://api.openai.com/v1')
    OPENAI_MODEL_NAME = os.environ.get('OPENAI_MODEL_NAME', 'gpt-4')

    QWEN_API_KEY = os.environ.get('QWEN_API_KEY', '')
    QWEN_API_BASE = os.environ.get('QWEN_API_BASE', 'https://dashscope.aliyuncs.com/compatible-mode/v1')
    QWEN_MODEL_NAME = os.environ.get('QWEN_MODEL_NAME', 'qwen-plus')

    FALLBACK_PROVIDER = os.environ.get('FALLBACK_PROVIDER', 'minimax')
    FALLBACK_API_KEY = os.environ.get('FALLBACK_API_KEY', '')
    FALLBACK_API_BASE = os.environ.get('FALLBACK_API_BASE', '')
    FALLBACK_MODEL_NAME = os.environ.get('FALLBACK_MODEL_NAME', '')

    STREAMING_ENABLED = os.environ.get('STREAMING_ENABLED', 'false').lower() == 'true'
    TEMPERATURE = float(os.environ.get('TEMPERATURE', '0.3'))
    MAX_TOKENS = int(os.environ.get('MAX_TOKENS', '1500'))
    RETRIEVAL_TOP_K = int(os.environ.get('RETRIEVAL_TOP_K', '5'))

    # ==================== MiniMax API 配置（向后兼容） ====================
    MINIMAX_API_KEY = os.environ.get('MINIMAX_API_KEY', '')
    MINIMAX_API_BASE = os.environ.get('MINIMAX_API_BASE', 'https://api.minimax.chat/v1')
    MODEL_NAME = os.environ.get('MODEL_NAME', 'MiniMax-M2.5')

    # ==================== 嵌入模型配置 ====================
    EMBEDDING_MODEL = os.environ.get('EMBEDDING_MODEL', 'BAAI/bge-m3')

    # ==================== 混合检索 / RRF 融合开关 ====================
    # RRF_ENABLED: True=走 BM25+向量+RRF+Cross-Encoder 多阶段融合；False=回退纯向量（FAISS）检索
    RRF_ENABLED = os.environ.get('RRF_ENABLED', 'true').lower() == 'true'

    # 多阶段检索参数（仅在 RRF_ENABLED=True 时生效）
    RRF_VECTOR_TOP_K = int(os.environ.get('RRF_VECTOR_TOP_K', '15'))   # 向量粗排 TopK
    RRF_BM25_TOP_K = int(os.environ.get('RRF_BM25_TOP_K', '15'))       # BM25 粗排 TopK
    RRF_RERANK_TOP_N = int(os.environ.get('RRF_RERANK_TOP_N', '10'))   # RRF 融合后送 Cross-Encoder 精排的 TopN
    RRF_FINAL_TOP_K = int(os.environ.get('RRF_FINAL_TOP_K', '5'))      # 最终返回 TopK
    RRF_K = int(os.environ.get('RRF_K', '60'))                          # RRF 平滑常数（经验值 60）
    RRF_VECTOR_WEIGHT = float(os.environ.get('RRF_VECTOR_WEIGHT', '0.7'))
    RRF_BM25_WEIGHT = float(os.environ.get('RRF_BM25_WEIGHT', '0.3'))

    # ==================== Agent 开关 ====================
    # AGENT_TYPE: 'function_calling'（默认，使用 MiniMax-M2.5 原生 tool_calls）
    #             'simple'（回退到 ReAct 文本解析模式，兼容老逻辑）
    AGENT_TYPE = os.environ.get('AGENT_TYPE', 'function_calling').lower().strip()
    AGENT_MAX_ITERATIONS = int(os.environ.get('AGENT_MAX_ITERATIONS', '5'))

    # ==================== 兼容性别名 ====================
    CHROMA_DB_PATH = OCG_CHROMA_DB_PATH
    SQLITE_DB_PATH = OCG_SQLITE_DB_PATH
    DOCS_PATH = OCG_DOCS_PATH