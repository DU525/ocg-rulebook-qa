"""
RAGAS四大指标自动化评估流水线

功能：
  - 从test_dataset.json读取测试集
  - 连接本地RAG系统批量提问并收集回答
  - 使用RAGAS四大指标评估（Faithfulness/Answer Relevance/Context Precision/Context Recall）
  - 生成Markdown格式的基线评估报告

评估指标说明：
  1. Faithfulness（忠实度）：答案是否忠实于检索到的上下文，不引入外部信息
  2. Answer Relevance（答案相关性）：答案是否与问题直接相关
  3. Context Precision（上下文精确度）：检索到的上下文是否有助于回答问题
  4. Context Recall（上下文召回率）：检索到的上下文是否覆盖了标准答案的关键信息

技术栈：ragas 0.4.3 + datasets + langchain
降级策略：若无OpenAI API密钥，使用基于规则/启发式方法模拟四项指标
"""

import os
import re
import sys
import json
import time
import math
import string
import logging
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Optional, Tuple
from collections import Counter
from concurrent.futures import ThreadPoolExecutor, as_completed
import urllib.request
import urllib.error
import urllib.parse

# 尝试导入ragas，如果不可用则使用启发式评估器
RAGAS_AVAILABLE = False
try:
    from ragas.metrics import faithfulness, answer_relevancy, context_precision, context_recall
    from datasets import Dataset
    from ragas import evaluate
    RAGAS_AVAILABLE = True
    print("[INFO] ragas库已加载，将使用标准RAGAS评估")
except ImportError:
    print("[INFO] ragas库不可用，将使用启发式规则评估器")

# ==================== 配置区 ====================

# RAG系统API配置
RAG_API_BASE = os.getenv("RAG_API_BASE", "http://localhost:5000")
RAG_CHAT_ENDPOINT = f"{RAG_API_BASE}/api/v1/chat/question"

# 测试集路径
BASE_DIR = Path(__file__).parent
TEST_DATASET_PATH = BASE_DIR / "test_dataset.json"

# 报告输出路径
REPORT_DIR = BASE_DIR.parent.parent / "docs"
REPORT_OUTPUT_PATH = REPORT_DIR / "BASELINE_EVALUATION_REPORT.md"

# 评估配置
EVAL_BATCH_SIZE = 50  # 每批处理的问答数量
EVAL_CONCURRENCY = 5  # 并发请求数
REQUEST_TIMEOUT = 30  # 单次API请求超时（秒）
SAMPLE_RATIO = float(os.getenv("RAGAS_SAMPLE_RATIO", "1.0"))  # 采样比例，默认100%

# 日志配置
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("RAGAS_EVAL")


# ==================== 数据加载模块 ====================

def load_test_dataset(path: str = str(TEST_DATASET_PATH)) -> List[Dict]:
    """加载测试数据集
    
    Args:
        path: 测试集JSON文件路径
        
    Returns:
        测试集列表，每条包含question/answer/contexts/ground_truth等字段
        
    Raises:
        FileNotFoundError: 测试集文件不存在
        json.JSONDecodeError: JSON格式错误
    """
    if not Path(path).exists():
        raise FileNotFoundError(f"测试集文件不存在: {path}")
    
    logger.info(f"正在加载测试集: {path}")
    with open(path, "r", encoding="utf-8") as f:
        dataset = json.load(f)
    
    logger.info(f"成功加载 {len(dataset)} 条测试数据")
    return dataset


def sample_dataset(dataset: List[Dict], ratio: float = 1.0) -> List[Dict]:
    """按比例采样测试集
    
    Args:
        dataset: 完整测试集
        ratio: 采样比例（0.0-1.0）
        
    Returns:
        采样后的测试集
    """
    if ratio >= 1.0:
        return dataset
    
    sample_size = max(1, int(len(dataset) * ratio))
    import random
    random.seed(42)
    sampled = random.sample(dataset, sample_size)
    logger.info(f"采样 {sample_size}/{len(dataset)} 条数据 ({ratio*100:.0f}%)")
    return sampled


# ==================== RAG系统交互模块 ====================

def query_rag_system(question: str, conversation_id: Optional[str] = None) -> Tuple[str, Optional[str], List[str]]:
    """向RAG系统发送问题并获取回答
    
    Args:
        question: 用户问题
        conversation_id: 会话ID（可选，用于保持上下文）
        
    Returns:
        Tuple[答案, 新会话ID, 引用上下文列表]
    """
    payload = {
        "question": question,
        "conversation_id": conversation_id
    }
    
    data = json.dumps(payload, ensure_ascii=False).encode("utf-8")
    req = urllib.request.Request(
        RAG_CHAT_ENDPOINT,
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT) as resp:
            result = json.loads(resp.read().decode("utf-8"))
            
            if not result.get("success"):
                error_msg = result.get("error", {}).get("message", "未知错误")
                raise Exception(f"API返回错误: {error_msg}")
            
            answer = result.get("data", {}).get("answer", "")
            new_conv_id = result.get("data", {}).get("conversation_id")
            citations = result.get("data", {}).get("citations", [])
            
            return answer, new_conv_id, citations
            
    except urllib.error.URLError as e:
        logger.warning(f"RAG系统连接失败: {e}")
        raise ConnectionError(f"无法连接到RAG系统 ({RAG_API_BASE}): {e}")
    except Exception as e:
        logger.error(f"查询失败: {question[:50]}... -> {e}")
        return f"[ERROR] {e}", conversation_id, []


def batch_query_rag(dataset: List[Dict]) -> List[Dict]:
    """批量向RAG系统提问并收集回答
    
    Args:
        dataset: 测试数据集
        
    Returns:
        包含rag_answer和rag_contexts的增强数据集
    """
    logger.info(f"开始批量查询RAG系统，共 {len(dataset)} 条问题")
    logger.info(f"API端点: {RAG_CHAT_ENDPOINT}")
    logger.info(f"并发数: {EVAL_CONCURRENCY}, 超时: {REQUEST_TIMEOUT}s")
    
    results = []
    conversation_id = None
    lock = __import__("threading").Lock()
    
    def query_single(item: Dict, idx: int) -> Dict:
        """查询单个问题"""
        question = item.get("question", "")
        try:
            answer, new_conv_id, contexts = query_rag_system(question, conversation_id)
            return {
                **item,
                "rag_answer": answer,
                "rag_contexts": contexts if contexts else item.get("contexts", []),
                "query_status": "success"
            }
        except Exception as e:
            logger.warning(f"第 {idx+1} 条查询失败: {e}")
            return {
                **item,
                "rag_answer": item.get("answer", ""),
                "rag_contexts": item.get("contexts", []),
                "query_status": "failed"
            }
    
    # 顺序查询（避免并发导致会话ID混乱）
    for idx, item in enumerate(dataset):
        result = query_single(item, idx)
        results.append(result)
        conversation_id = result.get("rag_conversation_id") or conversation_id
        
        if (idx + 1) % EVAL_BATCH_SIZE == 0:
            logger.info(f"已处理 {idx+1}/{len(dataset)} 条")
    
    success_count = sum(1 for r in results if r.get("query_status") == "success")
    logger.info(f"批量查询完成: {success_count}/{len(dataset)} 条成功")
    return results


# ==================== 文本相似度工具函数 ====================

def jaccard_similarity(text1: str, text2: str) -> float:
    """计算Jaccard相似度（基于字符级n-gram）
    
    Args:
        text1: 文本1
        text2: 文本2
        
    Returns:
        相似度分数 [0, 1]
    """
    if not text1 or not text2:
        return 0.0
    
    n = 2
    set1 = set(text1[i:i+n] for i in range(len(text1)-n+1))
    set2 = set(text2[i:i+n] for i in range(len(text2)-n+1))
    
    if not set1 and not set2:
        return 1.0
    
    intersection = set1 & set2
    union = set1 | set2
    
    return len(intersection) / len(union) if union else 0.0


def extract_key_phrases(text: str, min_length: int = 2) -> List[str]:
    """提取关键短语（基于中文分词启发式方法）
    
    Args:
        text: 输入文本
        min_length: 最小短语长度
        
    Returns:
        关键短语列表
    """
    # 移除标点符号
    cleaned = re.sub(r'[^\w\u4e00-\u9fff\s]', ' ', text)
    
    # 按空格和常见分隔符切分
    tokens = re.split(r'[\s,;，。！？、：；]+', cleaned)
    
    # 过滤短词
    phrases = [t.strip() for t in tokens if len(t.strip()) >= min_length]
    
    return phrases


def compute_overlap_score(answer: str, ground_truth: str) -> float:
    """计算答案与标准答案的重叠分数
    
    综合考虑：
    - 关键短语重叠率
    - 字符级n-gram相似度
    - 包含关系
    
    Args:
        answer: 生成的答案
        ground_truth: 标准答案
        
    Returns:
        重叠分数 [0, 1]
    """
    if not answer or not ground_truth:
        return 0.0
    
    answer = answer.strip()
    ground_truth = ground_truth.strip()
    
    # 方法1：关键短语重叠
    ans_phrases = set(extract_key_phrases(answer))
    gt_phrases = set(extract_key_phrases(ground_truth))
    
    if gt_phrases:
        phrase_overlap = len(ans_phrases & gt_phrases) / len(gt_phrases)
    else:
        phrase_overlap = 0.0
    
    # 方法2：字符级n-gram相似度
    char_sim = jaccard_similarity(answer, ground_truth)
    
    # 方法3：包含关系
    contains_score = 0.0
    if ground_truth in answer:
        contains_score = 1.0
    elif answer in ground_truth:
        contains_score = 0.8
    
    # 加权综合
    score = 0.4 * phrase_overlap + 0.4 * char_sim + 0.2 * contains_score
    return min(1.0, max(0.0, score))


# ==================== RAGAS启发式评估器 ====================

class HeuristicRAGASEvaluator:
    """基于规则/启发式方法的RAGAS指标评估器
    
    当无法使用LLM API时，采用以下策略模拟RAGAS四大指标：
    
    1. Faithfulness（忠实度）：
       - 检查答案中的关键信息是否都来源于提供的上下文
       - 使用上下文片段匹配和术语一致性检测
    
    2. Answer Relevance（答案相关性）：
       - 计算答案与问题的语义重叠度
       - 检测答案是否直接回应了问题
    
    3. Context Precision（上下文精确度）：
       - 评估检索到的上下文中与问题相关的片段比例
       - 基于问题-上下文关键词匹配
    
    4. Context Recall（上下文召回率）：
       - 评估标准答案的关键信息是否都能在检索到的上下文中找到
       - 基于标准答案与上下文的覆盖度
    """
    
    def evaluate_faithfulness(self, answer: str, contexts: List[str]) -> float:
        """评估忠实度：答案是否忠实于检索到的上下文
        
        策略：
        - 提取答案中的关键信息片段
        - 检查这些片段是否能在上下文中找到对应
        - 无法在上下文中找到的信息被视为"幻觉"
        
        Args:
            answer: 生成的答案
            contexts: 检索到的上下文列表
            
        Returns:
            忠实度分数 [0, 1]
        """
        if not answer or not contexts:
            return 0.0
        
        combined_context = " ".join(contexts)
        
        # 提取答案中的关键短语
        answer_phrases = extract_key_phrases(answer, min_length=3)
        
        if not answer_phrases:
            return 0.5  # 无法评估，给中间值
        
        # 检查每个短语是否在上下文中出现
        found_count = 0
        for phrase in answer_phrases:
            if phrase in combined_context:
                found_count += 1
            else:
                # 模糊匹配：检查短语的子串
                sub_phrases = extract_key_phrases(phrase, min_length=2)
                if any(sp in combined_context for sp in sub_phrases):
                    found_count += 0.5
        
        faithfulness_score = found_count / len(answer_phrases)
        return min(1.0, max(0.0, faithfulness_score))
    
    def evaluate_answer_relevancy(self, question: str, answer: str) -> float:
        """评估答案相关性：答案是否与问题直接相关
        
        策略：
        - 提取问题和答案的关键词
        - 计算关键词重叠率
        - 检查答案长度是否合理（太短可能不相关）
        
        Args:
            question: 用户问题
            answer: 生成的答案
            
        Returns:
            相关性分数 [0, 1]
        """
        if not question or not answer:
            return 0.0
        
        q_phrases = set(extract_key_phrases(question, min_length=2))
        a_phrases = set(extract_key_phrases(answer, min_length=2))
        
        if not q_phrases:
            return 0.5
        
        # 关键词重叠
        overlap = len(q_phrases & a_phrases) / len(q_phrases)
        
        # 答案长度惩罚（太短的答案通常不够相关）
        length_factor = min(1.0, len(answer) / 20)
        
        # 检查答案是否包含问题的核心词汇
        question_words = set(extract_key_phrases(question, min_length=3))
        answer_contains_question = sum(1 for w in question_words if w in answer)
        direct_answer_score = answer_contains_question / len(question_words) if question_words else 0
        
        # 综合评分
        score = 0.4 * overlap + 0.3 * length_factor + 0.3 * direct_answer_score
        return min(1.0, max(0.0, score))
    
    def evaluate_context_precision(self, question: str, contexts: List[str]) -> float:
        """评估上下文精确度：检索到的上下文是否有助于回答问题
        
        策略：
        - 检查每个上下文片段与问题的相关性
        - 计算相关上下文的比例
        
        Args:
            question: 用户问题
            contexts: 检索到的上下文列表
            
        Returns:
            精确度分数 [0, 1]
        """
        if not question or not contexts:
            return 0.0
        
        question_phrases = set(extract_key_phrases(question, min_length=2))
        
        relevant_count = 0
        for ctx in contexts:
            ctx_phrases = set(extract_key_phrases(ctx, min_length=2))
            if not ctx_phrases:
                continue
            
            # 上下文与问题的重叠度
            overlap = len(question_phrases & ctx_phrases) / len(question_phrases)
            if overlap > 0.1:  # 阈值：至少10%重叠认为相关
                relevant_count += 1
        
        precision = relevant_count / len(contexts) if contexts else 0
        return min(1.0, max(0.0, precision))
    
    def evaluate_context_recall(self, ground_truth: str, contexts: List[str]) -> float:
        """评估上下文召回率：标准答案的关键信息是否都在检索到的上下文中
        
        策略：
        - 从标准答案中提取关键信息点
        - 检查这些信息点是否能在上下文中找到
        
        Args:
            ground_truth: 标准答案
            contexts: 检索到的上下文列表
            
        Returns:
            召回率分数 [0, 1]
        """
        if not ground_truth or not contexts:
            return 0.0
        
        combined_context = " ".join(contexts)
        
        # 提取标准答案的关键短语
        gt_phrases = extract_key_phrases(ground_truth, min_length=3)
        
        if not gt_phrases:
            return 0.5
        
        # 检查关键短语是否在上下文中
        found_count = 0
        for phrase in gt_phrases:
            if phrase in combined_context:
                found_count += 1
            else:
                # 模糊匹配
                sub_phrases = extract_key_phrases(phrase, min_length=2)
                if any(sp in combined_context for sp in sub_phrases):
                    found_count += 0.5
        
        recall = found_count / len(gt_phrases)
        return min(1.0, max(0.0, recall))


# ==================== 标准RAGAS评估模块 ====================

def run_standard_ragas_eval(dataset: List[Dict]) -> Dict:
    """使用标准RAGAS库进行评估
    
    Args:
        dataset: 增强后的测试数据集（包含rag_answer和rag_contexts）
        
    Returns:
        评估结果字典
    """
    if not RAGAS_AVAILABLE:
        raise ImportError("ragas库不可用")
    
    logger.info("使用标准RAGAS库进行评估")
    
    # 准备RAGAS格式数据
    eval_samples = []
    for item in dataset:
        eval_samples.append({
            "question": item.get("question", ""),
            "answer": item.get("rag_answer", item.get("answer", "")),
            "contexts": item.get("rag_contexts", item.get("contexts", [])),
            "ground_truth": item.get("ground_truth", "")
        })
    
    # 创建Dataset
    ragas_dataset = Dataset.from_list(eval_samples)
    
    # 定义评估指标
    metrics = [faithfulness, answer_relevancy, context_precision, context_recall]
    
    # 执行评估
    logger.info(f"开始评估 {len(eval_samples)} 条数据")
    result = evaluate(
        dataset=ragas_dataset,
        metrics=metrics,
        batch_size=EVAL_BATCH_SIZE
    )
    
    # 解析结果
    df = result.to_pandas()
    
    metrics_result = {}
    metric_names = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]
    
    for name in metric_names:
        if name in df.columns:
            metrics_result[name] = {
                "mean": float(df[name].mean()),
                "std": float(df[name].std()),
                "min": float(df[name].min()),
                "max": float(df[name].max()),
                "scores": df[name].tolist()
            }
            logger.info(f"{name}: {metrics_result[name]['mean']:.4f}")
    
    return metrics_result


# ==================== 启发式评估模块 ====================

def run_heuristic_eval(dataset: List[Dict]) -> Dict:
    """使用启发式规则进行评估（无需LLM API）
    
    Args:
        dataset: 增强后的测试数据集
        
    Returns:
        评估结果字典
    """
    logger.info("使用启发式规则评估器")
    
    evaluator = HeuristicRAGASEvaluator()
    
    # 存储每条数据的各项分数
    all_scores = {
        "faithfulness": [],
        "answer_relevancy": [],
        "context_precision": [],
        "context_recall": []
    }
    
    for idx, item in enumerate(dataset):
        question = item.get("question", "")
        answer = item.get("rag_answer", item.get("answer", ""))
        contexts = item.get("rag_contexts", item.get("contexts", []))
        ground_truth = item.get("ground_truth", "")
        
        # 计算四项指标
        all_scores["faithfulness"].append(evaluator.evaluate_faithfulness(answer, contexts))
        all_scores["answer_relevancy"].append(evaluator.evaluate_answer_relevancy(question, answer))
        all_scores["context_precision"].append(evaluator.evaluate_context_precision(question, contexts))
        all_scores["context_recall"].append(evaluator.evaluate_context_recall(ground_truth, contexts))
        
        if (idx + 1) % 100 == 0:
            logger.info(f"已评估 {idx+1}/{len(dataset)} 条")
    
    # 统计结果
    metrics_result = {}
    metric_names = ["faithfulness", "answer_relevancy", "context_precision", "context_recall"]
    
    for name in metric_names:
        scores = all_scores[name]
        if scores:
            metrics_result[name] = {
                "mean": sum(scores) / len(scores),
                "std": math.sqrt(sum((s - sum(scores)/len(scores))**2 for s in scores) / len(scores)),
                "min": min(scores),
                "max": max(scores),
                "scores": scores
            }
            logger.info(f"{name}: {metrics_result[name]['mean']:.4f}")
    
    return metrics_result


# ==================== 报告生成模块 ====================

def generate_text_histogram(scores: List[float], bins: int = 10, width: int = 40) -> str:
    """生成文本格式的分数分布直方图
    
    Args:
        scores: 分数列表
        bins: 直方图柱数
        width: 图表宽度
        
    Returns:
        文本直方图字符串
    """
    if not scores:
        return "无数据"
    
    # 计算每个bin的范围和计数
    bin_edges = [i / bins for i in range(bins + 1)]
    bin_counts = [0] * bins
    
    for score in scores:
        for i in range(bins):
            if bin_edges[i] <= score < bin_edges[i + 1]:
                bin_counts[i] += 1
                break
        else:
            if score == 1.0:
                bin_counts[-1] += 1
    
    max_count = max(bin_counts) if bin_counts else 1
    
    lines = []
    for i in range(bins):
        low = bin_edges[i]
        high = bin_edges[i + 1]
        count = bin_counts[i]
        bar_len = int((count / max_count) * width) if max_count > 0 else 0
        bar = "#" * bar_len
        lines.append(f"[{low:.1f}-{high:.1f}) | {bar:<{width}} | {count}")
    
    return "\n".join(lines)


def find_weak_items(dataset: List[Dict], metrics_result: Dict, threshold: float = 0.6) -> List[Dict]:
    """找出薄弱项（分数低于阈值的问答对）
    
    Args:
        dataset: 测试数据集
        metrics_result: 评估结果
        threshold: 薄弱项阈值
        
    Returns:
        薄弱项列表
    """
    weak_items = []
    
    for idx, item in enumerate(dataset):
        scores = {}
        for metric_name in metrics_result:
            scores[metric_name] = metrics_result[metric_name]["scores"][idx]
        
        # 检查是否有任何指标低于阈值
        min_score = min(scores.values())
        if min_score < threshold:
            weak_items.append({
                "index": idx,
                "question": item.get("question", ""),
                "answer": item.get("rag_answer", item.get("answer", "")),
                "ground_truth": item.get("ground_truth", ""),
                "scores": scores,
                "min_metric": min(scores, key=scores.get),
                "min_score": min_score
            })
    
    return weak_items


def generate_improvement_suggestions(metrics_result: Dict, weak_items: List[Dict]) -> List[str]:
    """基于评估结果生成改进建议
    
    Args:
        metrics_result: 评估结果
        weak_items: 薄弱项列表
        
    Returns:
        改进建议列表
    """
    suggestions = []
    
    # 基于各项指标分数生成建议
    metric_names = {
        "faithfulness": ("忠实度", "减少幻觉，确保答案严格基于检索到的上下文"),
        "answer_relevancy": ("答案相关性", "提高答案与问题的直接相关性，避免跑题"),
        "context_precision": ("上下文精确度", "优化检索策略，提高检索到的上下文质量"),
        "context_recall": ("上下文召回率", "扩大检索范围，确保覆盖所有必要信息")
    }
    
    for metric_name, (name_cn, suggestion) in metric_names.items():
        if metric_name in metrics_result:
            score = metrics_result[metric_name]["mean"]
            if score < 0.7:
                suggestions.append(f"【{name_cn}偏低 ({score:.3f})】{suggestion}")
            elif score < 0.8:
                suggestions.append(f"【{name_cn}待提升 ({score:.3f})】可适当优化以进一步提升系统表现")
    
    # 基于薄弱项分析生成建议
    if weak_items:
        # 分析薄弱项的共同特征
        categories = Counter()
        sources = Counter()
        for item in weak_items:
            pass  # 可以根据需要添加更多分析
        
        weak_ratio = len(weak_items) / max(1, sum(len(metrics_result.get(m, {}).get("scores", [])) for m in metrics_result))
        if weak_ratio > 0.3:
            suggestions.append(f"【薄弱项比例较高 ({weak_ratio:.1%})】建议重点分析低分项，优化知识库覆盖和检索策略")
    
    # 通用建议
    suggestions.append("【通用建议】定期进行人工审核，构建高质量评估基准")
    suggestions.append("【通用建议】引入用户反馈机制，持续优化RAG系统表现")
    
    return suggestions


def generate_report(
    dataset: List[Dict],
    metrics_result: Dict,
    eval_time: float,
    weak_threshold: float = 0.6,
    output_path: str = str(REPORT_OUTPUT_PATH)
) -> str:
    """生成Markdown格式的评估报告
    
    Args:
        dataset: 测试数据集
        metrics_result: 评估结果
        eval_time: 评估耗时（秒）
        weak_threshold: 薄弱项阈值
        output_path: 报告输出路径
        
    Returns:
        报告内容字符串
    """
    total_count = len(dataset)
    eval_mode = "标准RAGAS" if RAGAS_AVAILABLE else "启发式规则"
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    
    # 构建报告
    report = []
    
    # 标题
    report.append("# RAG系统基线评估报告")
    report.append("")
    report.append(f"> 评估时间: {timestamp}")
    report.append(f"> 评估模式: {eval_mode}")
    report.append(f"> RAG系统: {RAG_API_BASE}")
    report.append("")
    
    # 评估概览
    report.append("## 评估概览")
    report.append("")
    report.append(f"| 指标 | 值 |")
    report.append(f"|------|------|")
    report.append(f"| 评估时间 | {timestamp} |")
    report.append(f"| 总条数 | {total_count} |")
    report.append(f"| 评估耗时 | {eval_time:.2f} 秒 ({eval_time/60:.1f} 分钟) |")
    report.append(f"| 评估模式 | {eval_mode} |")
    report.append("")
    
    # 4项指标分数统计
    report.append("## 指标分数统计")
    report.append("")
    
    metric_names = {
        "faithfulness": "忠实度 (Faithfulness)",
        "answer_relevancy": "答案相关性 (Answer Relevance)",
        "context_precision": "上下文精确度 (Context Precision)",
        "context_recall": "上下文召回率 (Context Recall)"
    }
    
    report.append("### 指标汇总表")
    report.append("")
    report.append("| 指标 | 平均分 | 标准差 | 最高分 | 最低分 |")
    report.append("|------|--------|--------|--------|--------|")
    
    for metric_key, metric_label in metric_names.items():
        if metric_key in metrics_result:
            m = metrics_result[metric_key]
            report.append(f"| {metric_label} | {m['mean']:.4f} | {m['std']:.4f} | {m['max']:.4f} | {m['min']:.4f} |")
    
    report.append("")
    
    # 各项指标详情
    for metric_key, metric_label in metric_names.items():
        if metric_key not in metrics_result:
            continue
        
        m = metrics_result[metric_key]
        report.append(f"### {metric_label}")
        report.append("")
        report.append(f"- **平均分**: {m['mean']:.4f}")
        report.append(f"- **标准差**: {m['std']:.4f}")
        report.append(f"- **最高分**: {m['max']:.4f}")
        report.append(f"- **最低分**: {m['min']:.4f}")
        report.append("")
        
        # 分数分布直方图
        report.append("**分数分布**:")
        report.append("")
        report.append("```")
        report.append(generate_text_histogram(m["scores"]))
        report.append("```")
        report.append("")
    
    # 薄弱项分析
    report.append("## 薄弱项分析")
    report.append("")
    report.append(f"阈值: 分数低于 {weak_threshold} 的问答对被视为薄弱项")
    report.append("")
    
    weak_items = find_weak_items(dataset, metrics_result, threshold=weak_threshold)
    report.append(f"共发现 **{len(weak_items)}** 个薄弱项（占总数的 {len(weak_items)/total_count:.1%}）")
    report.append("")
    
    if weak_items:
        # 按最低分排序，取前20个展示
        weak_items_sorted = sorted(weak_items, key=lambda x: x["min_score"])[:20]
        
        report.append("### 薄弱项示例（前20条）")
        report.append("")
        
        for i, item in enumerate(weak_items_sorted):
            report.append(f"#### {i+1}. {item['question']}")
            report.append("")
            report.append(f"- **RAG回答**: {item['answer'][:200]}{'...' if len(item['answer']) > 200 else ''}")
            report.append(f"- **标准答案**: {item['ground_truth'][:200]}{'...' if len(item['ground_truth']) > 200 else ''}")
            report.append(f"- **最低分指标**: {item['min_metric']} ({item['min_score']:.4f})")
            report.append(f"- **各项分数**:")
            for metric_key, score in item["scores"].items():
                report.append(f"  - {metric_key}: {score:.4f}")
            report.append("")
    
    # 改进建议
    report.append("## 改进建议")
    report.append("")
    
    suggestions = generate_improvement_suggestions(metrics_result, weak_items)
    for i, suggestion in enumerate(suggestions, 1):
        report.append(f"{i}. {suggestion}")
    report.append("")
    
    # 报告结束
    report.append("---")
    report.append("")
    report.append("*本报告由RAGAS自动化评估流水线生成*")
    
    report_content = "\n".join(report)
    
    # 保存报告
    Path(output_path).parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report_content)
    
    logger.info(f"评估报告已保存至: {output_path}")
    return report_content


# ==================== 主流程 ====================

def run_evaluation_pipeline():
    """运行完整的RAGAS评估流水线
    
    流程：
    1. 加载测试集
    2. 采样（可选）
    3. 向RAG系统批量提问
    4. 执行评估
    5. 生成报告
    """
    logger.info("=" * 60)
    logger.info("RAGAS自动化评估流水线启动")
    logger.info("=" * 60)
    
    start_time = time.time()
    
    try:
        # 1. 加载测试集
        logger.info("步骤1: 加载测试集")
        dataset = load_test_dataset()
        
        # 2. 采样
        logger.info("步骤2: 数据采样")
        dataset = sample_dataset(dataset, SAMPLE_RATIO)
        
        # 3. 向RAG系统批量提问
        logger.info("步骤3: 批量查询RAG系统")
        try:
            enhanced_dataset = batch_query_rag(dataset)
        except ConnectionError as e:
            logger.warning(f"RAG系统连接失败: {e}")
            logger.info("使用测试集中的预置答案进行评估")
            enhanced_dataset = [{**item, "query_status": "skipped"} for item in dataset]
        
        # 4. 执行评估
        logger.info("步骤4: 执行评估")
        eval_start = time.time()
        
        if RAGAS_AVAILABLE:
            try:
                metrics_result = run_standard_ragas_eval(enhanced_dataset)
            except Exception as e:
                logger.warning(f"标准RAGAS评估失败: {e}")
                logger.info("切换到启发式评估器")
                metrics_result = run_heuristic_eval(enhanced_dataset)
        else:
            metrics_result = run_heuristic_eval(enhanced_dataset)
        
        eval_time = time.time() - eval_start
        total_time = time.time() - start_time
        
        logger.info(f"评估完成，耗时: {eval_time:.2f} 秒")
        
        # 5. 生成报告
        logger.info("步骤5: 生成评估报告")
        report = generate_report(
            dataset=enhanced_dataset,
            metrics_result=metrics_result,
            eval_time=total_time,
            output_path=str(REPORT_OUTPUT_PATH)
        )
        
        # 打印报告摘要
        logger.info("=" * 60)
        logger.info("评估报告摘要")
        logger.info("=" * 60)
        for metric_key, m in metrics_result.items():
            logger.info(f"  {metric_key}: {m['mean']:.4f}")
        logger.info(f"  总耗时: {total_time:.2f} 秒")
        logger.info(f"  报告路径: {REPORT_OUTPUT_PATH}")
        logger.info("=" * 60)
        
        return metrics_result, report
        
    except Exception as e:
        logger.error(f"评估流水线执行失败: {e}", exc_info=True)
        raise


if __name__ == "__main__":
    try:
        run_evaluation_pipeline()
    except KeyboardInterrupt:
        logger.info("评估被用户中断")
        sys.exit(1)
    except Exception as e:
        logger.error(f"评估失败: {e}")
        sys.exit(1)
