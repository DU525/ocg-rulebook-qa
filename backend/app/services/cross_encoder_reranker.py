"""Cross-Encoder 重排序模块

Cross-Encoder 原理说明：
-------------------------
Cross-Encoder 是一种深度学习模型，用于精确评估 query-document 对的相关性。
与 Bi-Encoder（如 text2vec）分别编码 query 和 document 不同，Cross-Encoder 
将 query 和 document 同时输入 Transformer 模型，通过 self-attention 机制
捕获 query 与 document 之间的细粒度交互关系，从而得到更准确的相关性评分。

优势：
1. 精度高：query 和 document 的每个 token 都能互相 attention，捕获深层语义关联
2. 适合重排序：计算成本高但精度极高，适合对粗排后的少量候选文档精细排序
3. MS-MARCO 模型：针对检索场景优化，在 MS-MARCO 数据集上训练，适合问答场景

工作流程：
----------
1. 粗排阶段：使用 Bi-Encoder（向量检索）+ BM25 快速筛选 Top 50 候选文档
2. RRF 融合：多路检索结果融合，得到 Top 50 有序列表
3. 重排阶段：Cross-Encoder 对 Top 50 文档逐一评分（query-doc pair）
4. 精细排序：按 Cross-Encoder 分数降序，输出最终 Top K

性能特点：
- 模型加载：首次加载约 2-5s（取决于 CPU/GPU）
- 单次推理：每条 query-doc pair 约 1-3ms
- Top 50 重排：总耗时约 50-150ms（GPU 加速可达 < 50ms）
"""
import os
import time
import logging
import threading
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

# 模块级单例：确保模型实例全局复用，避免重复加载
_cross_encoder_model = None
_model_lock = threading.Lock()
_model_load_time = None


class CrossEncoderReranker:
    """Cross-Encoder 重排序器

    使用 sentence-transformers 的 CrossEncoder 对检索结果进行精细重排序。
    支持 CPU/GPU 自动检测，线程安全的模型单例模式。

    Attributes:
        model_name: Cross-Encoder 模型名称
        device: 计算设备 ('cpu' 或 'cuda')
        model: 加载的 CrossEncoder 模型实例
    """

    # 默认模型：MS-MARCO MiniLM，体积小、速度快、精度高
    DEFAULT_MODEL = "cross-encoder/ms-marco-MiniLM-L-6-v2"

    def __init__(self, model_name: Optional[str] = None, force_cpu: bool = False, top_n: int = 10):
        """初始化 Cross-Encoder 重排序器

        Args:
            model_name: 模型名称，默认使用 MS-MARCO MiniLM-L-6-v2
            force_cpu: 是否强制使用 CPU（默认自动检测 GPU）
            top_n: 默认精排保留的 TopN（2026-06-02 增加，让 RAGEngine 显式控制）
        """
        self.model_name = model_name or self.DEFAULT_MODEL
        self.device = self._detect_device(force_cpu)
        self.model = None
        self.top_n = top_n
        self._load_model()

    def _detect_device(self, force_cpu: bool = False) -> str:
        """自动检测可用的计算设备

        Args:
            force_cpu: 是否强制使用 CPU

        Returns:
            str: 'cuda' 或 'cpu'
        """
        if force_cpu:
            logger.info("[CrossEncoder] 强制使用 CPU 设备")
            return "cpu"

        try:
            import torch
            if torch.cuda.is_available():
                device_name = torch.cuda.get_device_name(0)
                logger.info(
                    f"[CrossEncoder] 检测到 GPU: {device_name}, "
                    f"将使用 CUDA 加速"
                )
                return "cuda"
        except ImportError:
            logger.debug("[CrossEncoder] torch 未安装，使用 CPU")

        logger.info("[CrossEncoder] 使用 CPU 设备")
        return "cpu"

    def _load_model(self):
        """加载 Cross-Encoder 模型（线程安全）"""
        global _cross_encoder_model, _model_load_time

        # 线程安全：避免多线程同时加载模型
        with _model_lock:
            if _cross_encoder_model is not None:
                self.model = _cross_encoder_model
                logger.info("[CrossEncoder] 复用已加载的模型实例")
                return

            load_start = time.time()
            try:
                # 设置 HuggingFace 镜像（加速国内下载）
                os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

                from sentence_transformers import CrossEncoder

                logger.info(
                    f"[CrossEncoder] 开始加载模型: {self.model_name}"
                )

                # 加载模型并指定设备
                self.model = CrossEncoder(
                    self.model_name,
                    device=self.device,
                )

                _cross_encoder_model = self.model
                _model_load_time = time.time() - load_start

                logger.info(
                    f"[CrossEncoder] 模型加载完成, "
                    f"设备: {self.device}, "
                    f"耗时: {_model_load_time:.2f}秒"
                )

            except Exception as e:
                logger.error(
                    f"[CrossEncoder] 模型加载失败: {e}, "
                    f"将使用降级策略（跳过重排）"
                )
                self.model = None
                raise

    @property
    def is_loaded(self) -> bool:
        """检查模型是否已成功加载"""
        return self.model is not None

    def rerank(
        self,
        query: str,
        documents: List[Dict[str, Any]],
        top_k: int = 5,
    ) -> List[Dict[str, Any]]:
        """对文档列表进行 Cross-Encoder 重排序

        将 query 与每个 document 组成 pair，批量输入 Cross-Encoder 模型
        进行相关性评分，然后按分数降序返回 Top K 文档。

        Args:
            query: 用户查询字符串
            documents: 候选文档列表（来自 RRF 粗排结果）
            top_k: 返回的重排后文档数量

        Returns:
            List[Dict]: 重排后的文档列表，每项新增 'rerank_score' 字段

        示例：
            >>> reranker = CrossEncoderReranker()
            >>> docs = [{'content': 'xxx', 'metadata': {...}}, ...]
            >>> results = reranker.rerank("连锁处理规则", docs, top_k=5)
        """
        if not self.is_loaded:
            logger.warning(
                "[CrossEncoder] 模型未加载，跳过重排，返回原始文档"
            )
            return documents[:top_k]

        if not documents:
            return []

        # 提取文档内容，构建 query-doc pairs
        doc_contents = [doc.get('content', '') for doc in documents]

        # 批量评分：CrossEncoder 支持同时处理多个 pairs
        # 内部实现：将 (query, doc1), (query, doc2), ... 批量输入模型
        scores = self._score_pairs(query, doc_contents)

        # 将分数附加到文档中
        scored_docs = []
        for doc, score in zip(documents, scores):
            doc_with_score = doc.copy()
            doc_with_score['rerank_score'] = float(score)
            scored_docs.append(doc_with_score)

        # 按 Cross-Encoder 分数降序排序
        scored_docs.sort(key=lambda x: x['rerank_score'], reverse=True)

        # 返回 Top K
        return scored_docs[:top_k]

    def _score_pairs(
        self,
        query: str,
        documents: List[str],
    ) -> List[float]:
        """批量计算 query-document pairs 的相关性分数

        Args:
            query: 查询字符串
            documents: 文档内容列表

        Returns:
            List[float]: 相关性分数列表（MS-MARCO 模型输出 logit 值）
        """
        if not documents:
            return []

        # 构建 pairs: [(query, doc1), (query, doc2), ...]
        pairs = [(query, doc) for doc in documents]

        # 批量预测：sentence-transformers 内部自动 batch 处理
        scores = self.model.predict(pairs, show_progress_bar=False)

        return scores.tolist() if hasattr(scores, 'tolist') else list(scores)

    def get_stats(self) -> Dict[str, Any]:
        """获取重排序器统计信息

        Returns:
            Dict: 包含模型状态、设备信息等统计信息
        """
        return {
            'model_name': self.model_name,
            'device': self.device,
            'is_loaded': self.is_loaded,
            'model_load_time': _model_load_time,
        }


def get_cross_encoder_reranker(
    model_name: Optional[str] = None,
    force_cpu: bool = False,
) -> Optional[CrossEncoderReranker]:
    """获取全局共享的 Cross-Encoder 重排序器实例（单例工厂）

    使用全局缓存，确保模型只加载一次，避免重复加载带来的性能开销。

    Args:
        model_name: 模型名称（可选）
        force_cpu: 是否强制使用 CPU（可选）

    Returns:
        CrossEncoderReranker: 重排序器实例，如果加载失败返回 None
    """
    global _cross_encoder_model

    if _cross_encoder_model is not None:
        # 模型已加载，直接返回包装实例
        reranker = CrossEncoderReranker.__new__(CrossEncoderReranker)
        reranker.model_name = model_name or CrossEncoderReranker.DEFAULT_MODEL
        reranker.device = reranker._detect_device(force_cpu)
        reranker.model = _cross_encoder_model
        return reranker

    try:
        return CrossEncoderReranker(
            model_name=model_name,
            force_cpu=force_cpu,
        )
    except Exception as e:
        logger.error(
            f"[CrossEncoder] 重排序器初始化失败: {e}, "
            f"检索流程将降级为 RRF 粗排结果"
        )
        return None
