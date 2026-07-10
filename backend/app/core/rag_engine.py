from typing import List, Dict, Any, Optional, Generator
from dataclasses import dataclass, field
from app.db.vector_store import VectorStore
from app.services.document_processor import DocumentChunk
from app.core.prompt_templates import get_template, classify_query, DEFAULT_TEMPLATE
from app.services.intent_classifier import classify_query as intent_classify, IntentType
from app.services.retrieval_strategy import get_strategy, get_default_strategy, RetrievalConfig
from app.services.result_filter import RelevanceFilter
import logging

logger = logging.getLogger(__name__)


# 多阶段检索支持配置
@dataclass
class MultiStageConfig:
    enabled: bool = False
    initial_top_k: int = 15
    rerank_threshold: float = 0.75
    final_top_k: int = 5

DEFAULT_MULTI_STAGE_CONFIG = MultiStageConfig()

def _get_trace_id() -> str:
    try:
        from app.core.trace import get_current_trace
        return get_current_trace()
    except Exception:
        return ''

@dataclass
class RetrievalResult:
    content: str
    source: str
    chapter: str
    section: str
    similarity: float

@dataclass
class RAGResponse:
    answer: str
    citations: List[Dict[str, Any]]
    confidence: float
    conversation_id: str

@dataclass
class StreamingRAGResponse:
    citations: List[Dict[str, Any]] = field(default_factory=list)
    confidence: float = 0.0
    conversation_id: str = ""


class RAGEngine:

    SYSTEM_PROMPT = DEFAULT_TEMPLATE

    def __init__(
        self,
        vector_store: VectorStore,
        provider: Any = None,
        api_key: str = None,
        api_base: str = None,
        model_name: str = "MiniMax-M2.5",
        use_multi_stage: bool = True,
        multi_stage_config: Optional[MultiStageConfig] = None,
    ):
        self.vector_store = vector_store
        self.use_multi_stage = use_multi_stage
        self.multi_stage_config = multi_stage_config or DEFAULT_MULTI_STAGE_CONFIG
        
        # 初始化多阶段RAG组件（如果启用）
        self.multi_stage_engine = None
        self.bm25_engine = None
        self.cross_encoder_reranker = None
        
        if self.use_multi_stage:
            try:
                from app.services.bm25_engine import BM25Engine
                self.bm25_engine = BM25Engine()
                logger.info("[多阶段RAG] BM25引擎初始化成功")
            except Exception as e:
                logger.warning(f"[多阶段RAG] BM25引擎初始化失败，将使用向量检索: {e}")
            
            try:
                from app.services.cross_encoder_reranker import CrossEncoderReranker
                self.cross_encoder_reranker = CrossEncoderReranker(top_n=self.multi_stage_config.rerank_top_n if hasattr(self.multi_stage_config, 'rerank_top_n') else 10)
                logger.info("[多阶段RAG] Cross-Encoder精排器初始化成功")
            except Exception as e:
                logger.warning(f"[多阶段RAG] Cross-Encoder精排器初始化失败，将跳过精排: {e}")
            
            if self.bm25_engine is not None:
                from app.services.multi_stage_rag_engine import MultiStageRAGEngine
                self.multi_stage_engine = MultiStageRAGEngine(
                    vector_store=self.vector_store,
                    bm25_engine=self.bm25_engine,
                    cross_encoder_reranker=self.cross_encoder_reranker,
                    top_k=multi_stage_config.final_top_k if hasattr(multi_stage_config, 'final_top_k') else 5,
                    vector_top_k=multi_stage_config.initial_top_k if hasattr(multi_stage_config, 'initial_top_k') else 15,
                    bm25_top_k=multi_stage_config.initial_top_k if hasattr(multi_stage_config, 'initial_top_k') else 15,
                    rerank_top_n=self.multi_stage_config.rerank_top_n if hasattr(self.multi_stage_config, 'rerank_top_n') else 10,
                )
                logger.info(f"[多阶段RAG] 完整Pipeline已启用")

        if provider is not None:
            self.provider = provider
        elif api_key is not None:
            from app.services.llm_provider import OpenAICompatibleProvider
            self.provider = OpenAICompatibleProvider(
                api_key=api_key,
                api_base=api_base,
                model_name=model_name,
            )
        else:
            from app.config import Config
            from app.services.llm_provider import OpenAICompatibleProvider
            self.provider = OpenAICompatibleProvider(
                api_key=Config.MINIMAX_API_KEY,
                api_base=Config.MINIMAX_API_BASE,
                model_name=Config.MODEL_NAME,
            )

    def retrieve(
        self,
        query: str,
        top_k: Optional[int] = None,
        use_intent_strategy: bool = True,
        min_relevance_threshold: float = 0.5,
        use_multi_stage: Optional[bool] = None,
    ) -> List[RetrievalResult]:
        trace_id = _get_trace_id()
        
        # 判断是否使用多阶段检索
        effective_multi_stage = use_multi_stage if use_multi_stage is not None else self.use_multi_stage
        
        if effective_multi_stage and self.multi_stage_engine:
            return self._multi_stage_retrieve(query, top_k, use_intent_strategy, min_relevance_threshold, trace_id)
        else:
            return self._vector_only_retrieve(query, top_k, use_intent_strategy, min_relevance_threshold, trace_id)
    
    def _multi_stage_retrieve(
        self,
        query: str,
        top_k: Optional[int],
        use_intent_strategy: bool,
        min_relevance_threshold: float,
        trace_id: str,
    ) -> List[RetrievalResult]:
        """多阶段检索：意图分类 → BM25+向量 → RRF融合 → Cross-Encoder精排"""
        
        # 1. 意图分类，获取权重配置
        if use_intent_strategy:
            from app.services.rrf_fusion import QueryClassifier
            query_type, weights = QueryClassifier.classify(query)
            vector_weight = weights['vector_weight']
            bm25_weight = weights['bm25_weight']
            
            logger.info(
                f"[意图分类:{trace_id}] query='{query[:30]}...', "
                f"type={query_type}, "
                f"weights=(vector={vector_weight}, bm25={bm25_weight})"
            )
        else:
            vector_weight = 0.7
            bm25_weight = 0.3
        
        # 2. 执行多阶段检索
        multi_stage_results = self.multi_stage_engine.retrieve(
            query=query,
            top_k=top_k or self.multi_stage_config.final_top_k,
            use_multi_stage=True,
            vector_weight=vector_weight,
            bm25_weight=bm25_weight,
        )
        
        # 3. 转换为RetrievalResult格式
        retrieval_results = []
        for result in multi_stage_results:
            retrieval_results.append(RetrievalResult(
                content=result.content,
                source=result.source,
                chapter=result.chapter,
                section=result.section,
                similarity=result.similarity,
            ))
        
        # 4. 相关性过滤
        if retrieval_results:
            before_filter_count = len(retrieval_results)
            filter_instance = RelevanceFilter(threshold=min_relevance_threshold)
            filtered_results = filter_instance.filter(retrieval_results)
            after_filter_count = len(filtered_results)
            
            avg_similarity = (
                sum(r.similarity for r in filtered_results) / len(filtered_results)
                if filtered_results else 0.0
            )
            
            logger.info(
                f"[相关性过滤:{trace_id}] query='{query[:30]}...', "
                f"过滤前={before_filter_count}, "
                f"过滤后={after_filter_count}, "
                f"阈值={min_relevance_threshold}, "
                f"平均similarity={avg_similarity:.3f}"
            )
            
            retrieval_results = filtered_results
        
        logger.info(
            f"[多阶段检索完成:{trace_id}] query='{query[:30]}...', "
            f"最终结果={len(retrieval_results)}"
        )
        
        return retrieval_results
    
    def _vector_only_retrieve(
        self,
        query: str,
        top_k: Optional[int],
        use_intent_strategy: bool,
        min_relevance_threshold: float,
        trace_id: str,
    ) -> List[RetrievalResult]:
        """降级方案：仅使用向量检索"""
        if use_intent_strategy:
            intent_result = intent_classify(query)
            retrieval_config = get_strategy(intent_result.intent_type)

            logger.info(
                f"[意图分类:{trace_id}] query='{query[:30]}...', "
                f"intent={intent_result.intent_type.value}, "
                f"confidence={intent_result.confidence:.2f}, "
                f"top_k={retrieval_config.top_k}, "
                f"weights=(bm25={retrieval_config.bm25_weight}, "
                f"vector={retrieval_config.vector_weight})"
            )

            effective_top_k = retrieval_config.top_k
        else:
            retrieval_config = get_default_strategy()
            effective_top_k = top_k if top_k is not None else 5

        results = self.vector_store.search(query, n_results=effective_top_k)
        logger.info(f"[向量检索:{trace_id}] query='{query[:30]}...', found={len(results)} results")

        retrieval_results = []
        for result in results:
            similarity = 1 - result['distance']
            metadata = result['metadata']
            retrieval_results.append(RetrievalResult(
                content=result['content'],
                source=metadata.get('source', 'unknown'),
                chapter=metadata.get('chapter', ''),
                section=metadata.get('section', ''),
                similarity=similarity
            ))

        if retrieval_results:
            before_filter_count = len(retrieval_results)
            
            filter_instance = RelevanceFilter(threshold=min_relevance_threshold)
            filtered_results = filter_instance.filter(retrieval_results)
            after_filter_count = len(filtered_results)
            
            avg_similarity = (
                sum(r.similarity for r in filtered_results) / len(filtered_results)
                if filtered_results else 0.0
            )
            
            logger.info(
                f"[相关性过滤:{trace_id}] query='{query[:30]}...', "
                f"过滤前={before_filter_count}, "
                f"过滤后={after_filter_count}, "
                f"阈值={min_relevance_threshold}, "
                f"平均similarity={avg_similarity:.3f}"
            )
            
            if after_filter_count < effective_top_k and before_filter_count >= effective_top_k:
                logger.warning(
                    f"[相关性过滤警告:{trace_id}] 过滤后结果不足top_k: "
                    f"query='{query[:30]}...', "
                    f"top_k={effective_top_k}, "
                    f"过滤后={after_filter_count}"
                )
            
            retrieval_results = filtered_results

        return retrieval_results

    def _build_messages(self, question: str, retrieval_results: List[RetrievalResult],
                        conversation_history: Optional[List[Dict]] = None,
                        system_prompt: Optional[str] = None) -> list:
        context = self._build_context(retrieval_results)

        if system_prompt is not None:
            prompt = system_prompt
        else:
            query_type = classify_query(question)
            prompt = get_template(query_type)

        messages = [{"role": "system", "content": prompt}]

        if conversation_history:
            for msg in conversation_history[-10:]:
                messages.append({
                    "role": msg["role"],
                    "content": msg["content"]
                })

        user_message = f"""【上下文信息】
{context}

【用户问题】
{question}"""
        messages.append({"role": "user", "content": user_message})

        return messages

    def generate(
        self,
        question: str,
        retrieval_results: List[RetrievalResult],
        conversation_history: Optional[List[Dict]] = None,
        temperature: float = 0.3,
        max_tokens: int = 1500,
        system_prompt: Optional[str] = None,
    ) -> RAGResponse:
        messages = self._build_messages(question, retrieval_results, conversation_history, system_prompt)

        answer = self.provider.generate(messages, temperature=temperature, max_tokens=max_tokens)

        citations = self._build_citations(retrieval_results)
        avg_similarity = sum(r.similarity for r in retrieval_results) / len(retrieval_results) if retrieval_results else 0
        confidence = min(avg_similarity * 1.2, 1.0)

        return RAGResponse(
            answer=answer,
            citations=citations,
            confidence=confidence,
            conversation_id=""
        )

    def generate_stream(
        self,
        question: str,
        retrieval_results: List[RetrievalResult],
        conversation_history: Optional[List[Dict]] = None,
        temperature: float = 0.3,
        max_tokens: int = 1500,
        system_prompt: Optional[str] = None,
    ) -> Generator[str, None, None]:
        import json

        messages = self._build_messages(question, retrieval_results, conversation_history, system_prompt)

        for chunk in self.provider.generate_stream(messages, temperature=temperature, max_tokens=max_tokens):
            yield f"data: {json.dumps({'content': chunk})}\n\n"

        citations = self._build_citations(retrieval_results)
        avg_similarity = sum(r.similarity for r in retrieval_results) / len(retrieval_results) if retrieval_results else 0
        confidence = min(avg_similarity * 1.2, 1.0)

        yield f"data: {json.dumps({'citations': citations, 'confidence': confidence})}\n\n"
        yield "data: [DONE]\n\n"

    def _build_context(self, retrieval_results: List[RetrievalResult]) -> str:
        context_parts = []

        for i, result in enumerate(retrieval_results, 1):
            source = f"{result.chapter}·{result.section}" if result.section else result.chapter
            context_parts.append(
                f"【参考{i}】来源：{source}\n{result.content}\n"
            )

        return "\n---\n".join(context_parts)

    def _build_citations(self, retrieval_results: List[RetrievalResult]) -> List[Dict]:
        citations = []

        for result in retrieval_results:
            source = f"{result.chapter}·{result.section}" if result.section else result.chapter
            citations.append({
                "source": result.source,
                "title": source,
                "text": result.content[:200] + "..." if len(result.content) > 200 else result.content,
                "relevance": round(result.similarity, 3)
            })

        return citations

    def query(
        self,
        question: str,
        top_k: Optional[int] = None,
        conversation_history: Optional[List[Dict]] = None,
        temperature: float = 0.3,
        max_tokens: int = 1500,
        system_prompt: str = None,
        use_intent_strategy: bool = True,
        min_relevance_threshold: float = 0.5,
        use_multi_stage: Optional[bool] = None,
    ) -> RAGResponse:
        retrieval_results = self.retrieve(
            question, top_k, use_intent_strategy=use_intent_strategy,
            min_relevance_threshold=min_relevance_threshold,
            use_multi_stage=use_multi_stage,
        )

        if not retrieval_results:
            return RAGResponse(
                answer="抱歉，我在知识库中没有找到与您问题相关的信息。请尝试换一种表述方式，或者查看官方规则书获取更多信息。",
                citations=[],
                confidence=0.0,
                conversation_id=""
            )

        return self.generate(question, retrieval_results, conversation_history=conversation_history,
                             temperature=temperature, max_tokens=max_tokens, system_prompt=system_prompt)

    def query_stream(
        self,
        question: str,
        top_k: Optional[int] = None,
        conversation_history: Optional[List[Dict]] = None,
        temperature: float = 0.3,
        max_tokens: int = 1500,
        system_prompt: str = None,
        use_intent_strategy: bool = True,
        min_relevance_threshold: float = 0.5,
        use_multi_stage: Optional[bool] = None,
    ) -> Generator[str, None, None]:
        retrieval_results = self.retrieve(
            question, top_k, use_intent_strategy=use_intent_strategy,
            min_relevance_threshold=min_relevance_threshold,
            use_multi_stage=use_multi_stage,
        )

        if not retrieval_results:
            import json
            yield f"data: {json.dumps({'content': '抱歉，我在知识库中没有找到与您问题相关的信息。请尝试换一种表述方式，或者查看官方规则书获取更多信息。'})}\n\n"
            yield "data: [DONE]\n\n"
            return

        yield from self.generate_stream(question, retrieval_results, conversation_history=conversation_history,
                                        temperature=temperature, max_tokens=max_tokens, system_prompt=system_prompt)

    def query_multimodal(
        self,
        text: str,
        image_base64: str = None,
        top_k: int = 5,
        temperature: float = 0.3,
        max_tokens: int = 1500,
    ) -> RAGResponse:
        """多模态 RAG——文字检索 + 图像理解
        Args:
            text: 用户文字查询
            image_base64: 可选的 base64 编码图片
            top_k: 检索条数
            temperature: 温度
            max_tokens: 最大 token 数
        Returns:
            RAGResponse
        """
        retrieval_results = self.retrieve(text, top_k)

        vision_context = ""
        if image_base64:
            try:
                from app.services.multimodal_provider import MiniMaxVisionProvider
                from app.config import Config
                vision_provider = MiniMaxVisionProvider(api_key=Config.MINIMAX_API_KEY)
                vision_answer = vision_provider.generate_with_image(
                    text="请详细描述这张图片中的游戏王卡牌效果，包括卡名、效果文本、类型等",
                    image_base64=image_base64,
                )
                vision_context = f"\n【图像分析结果】\n{vision_answer}\n"
            except Exception as e:
                logger.warning(f"视觉分析失败: {e}")
                vision_context = "\n【图像分析失败，仅使用文字检索结果】\n"

        context = self._build_context(retrieval_results) + vision_context

        system_prompt = self.SYSTEM_PROMPT + "\n\n请结合图像分析结果和文字检索结果进行回答。"
        messages = [{"role": "system", "content": system_prompt}]
        messages.append({"role": "user", "content": context + f"\n用户问题：{text}"})

        answer = self.provider.generate(messages, temperature=temperature, max_tokens=max_tokens)

        citations = self._build_citations(retrieval_results)
        avg_similarity = sum(r.similarity for r in retrieval_results) / len(retrieval_results) if retrieval_results else 0
        confidence = min(avg_similarity * 1.2, 1.0)

        return RAGResponse(
            answer=answer,
            citations=citations,
            confidence=confidence,
            conversation_id=""
        )