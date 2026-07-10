"""RRF (Reciprocal Rank Fusion) 融合排序算法

RRF算法原理：
-----------
RRF是一种简单而有效的多路检索结果融合方法，由Cormack等人在2009年提出。
核心思想：对每个文档，将其在各路检索结果中的排名转换为倒数得分，然后累加。

公式：score(d) = Σ 1/(k + rank_i(d))

其中：
- d: 文档
- k: 平滑常数，经验值为60
- rank_i(d): 文档d在第i路检索结果中的排名（从1开始）

为什么k=60？
- k值决定了排名对得分的影响程度
- k=60是经过大量实验验证的经验值，能产生稳定且平滑的得分分布
- k太小：排名第一的文档得分过高，后续文档区分度不足
- k太大：所有文档得分趋同，排名差异被过度平滑
- k=60时：rank=1得分≈0.0164，rank=10得分≈0.0143，区分度适中

RRF的优势：
1. 无需对原始分数进行归一化（不同检索器的分数尺度可能不同）
2. 算法简单，时间复杂度O(N log N)，N为候选文档总数
3. 在实践中表现优异，广泛用于混合检索场景
"""
import logging
import re
from typing import List, Dict, Any, Optional, Tuple

logger = logging.getLogger(__name__)

# RRF平滑常数，经验值60
RRF_K = 60

# 查询分类规则术语
RULE_TERMS = {
    "连锁", "反击陷阱", "反击", "陷阱", "效果", "咒语速度",
    "连锁处理", "连锁块", "逆顺处理", "优先权", "时点",
    "强制效果", "选发效果", "任意发动", "必发效果",
    " COST", "代价", "支付", "宣言", "无效", "破坏",
    "除外", "返回卡组", "返回手牌", "特殊召唤", "通常召唤",
    "上级召唤", "仪式召唤", "融合召唤", "同步召唤", "超量召唤",
    "灵摆召唤", "连接召唤", "游戏规则", "规则书", "裁定",
    "调整", "官方", "裁定", "处理", "发动", "响应",
    "连锁点", "连锁顺序", "效果处理", "发动时机",
}

# 语义查询特征词（抽象概念）
SEMANTIC_TERMS = {
    "为什么", "如何", "怎么", "什么", "区别", "原理",
    "策略", "技巧", "建议", "推荐", "解释", "说明",
    "理解", "概念", "机制", "流程", "步骤",
}


class QueryClassifier:
    """查询分类器：根据查询内容判断查询类型，推荐合适的权重配置
    
    查询类型：
    - 'rule': 规则查询，包含精确规则术语，需要提高BM25权重
    - 'semantic': 语义查询，包含抽象概念词，需要提高向量权重  
    - 'default': 默认查询，使用标准权重配置
    
    权重配置：
    - rule: vector_weight=0.5, bm25_weight=0.5
    - semantic: vector_weight=0.9, bm25_weight=0.1
    - default: vector_weight=0.7, bm25_weight=0.3
    """

    @staticmethod
    def classify(query: str) -> Tuple[str, Dict[str, float]]:
        """对查询进行分类并返回推荐权重
        
        Args:
            query: 用户查询字符串
            
        Returns:
            Tuple[str, Dict[str, float]]: (查询类型, 权重配置)
            权重配置包含 'vector_weight' 和 'bm25_weight'
        """
        if not query or not query.strip():
            return 'default', {'vector_weight': 0.7, 'bm25_weight': 0.3}
        
        query_lower = query.lower().strip()
        
        # 检测是否包含精确规则术语
        rule_match_count = 0
        for term in RULE_TERMS:
            if term.lower() in query_lower:
                rule_match_count += 1
        
        # 检测是否包含语义查询特征词
        semantic_match_count = 0
        for term in SEMANTIC_TERMS:
            if term.lower() in query_lower:
                semantic_match_count += 1
        
        # 判断查询类型
        if rule_match_count >= 1 and rule_match_count > semantic_match_count:
            # 规则查询：包含精确规则术语
            return 'rule', {'vector_weight': 0.5, 'bm25_weight': 0.5}
        elif semantic_match_count > rule_match_count:
            # 语义查询：包含抽象概念词
            return 'semantic', {'vector_weight': 0.9, 'bm25_weight': 0.1}
        else:
            # 默认查询
            return 'default', {'vector_weight': 0.7, 'bm25_weight': 0.3}

    @staticmethod
    def get_weights(query: str, 
                   vector_weight: Optional[float] = None,
                   bm25_weight: Optional[float] = None) -> Dict[str, float]:
        """获取查询权重配置
        
        如果提供了自定义权重，则使用自定义权重；
        否则根据查询类型自动推荐权重。
        
        Args:
            query: 用户查询字符串
            vector_weight: 自定义向量权重（可选）
            bm25_weight: 自定义BM25权重（可选）
            
        Returns:
            Dict[str, float]: {'vector_weight': float, 'bm25_weight': float}
        """
        if vector_weight is not None and bm25_weight is not None:
            return {'vector_weight': vector_weight, 'bm25_weight': bm25_weight}
        
        _, weights = QueryClassifier.classify(query)
        return weights


def reciprocal_rank_fusion(
    vector_results: List[Dict[str, Any]],
    bm25_results: List[Dict[str, Any]],
    top_k: int = 5,
    vector_weight: float = 0.7,
    bm25_weight: float = 0.3,
    k: int = RRF_K,
) -> List[Dict[str, Any]]:
    """RRF融合排序：将向量检索和BM25检索结果进行融合
    
    算法步骤：
    1. 对每路检索结果，按排名计算RRF得分：1/(k + rank)
    2. 对每个文档，加权累加各路RRF得分
    3. 按融合得分降序排序，返回Top K结果
    
    Args:
        vector_results: 向量检索结果列表，每项需包含'id'和原始结果信息
        bm25_results: BM25检索结果列表，每项需包含'id'和原始结果信息
        top_k: 返回结果数量
        vector_weight: 向量检索RRF得分权重
        bm25_weight: BM25检索RRF得分权重
        k: RRF平滑常数，默认60
        
    Returns:
        List[Dict[str, Any]]: 融合排序后的结果，每项包含:
            - id: 文档ID
            - content: 文档内容
            - metadata: 文档元数据
            - rrf_score: RRF融合得分
            - vector_rrf: 向量RRF贡献得分
            - bm25_rrf: BM25 RRF贡献得分
            - vector_rank: 向量检索排名（0表示未出现）
            - bm25_rank: BM25检索排名（0表示未出现）
            - source: 结果来源 ('vector', 'bm25', 'both')
    """
    # 使用字典合并相同文档的得分，避免重复计算
    doc_scores: Dict[str, Dict] = {}
    
    # 处理向量检索结果：计算RRF得分
    for rank, result in enumerate(vector_results, start=1):
        doc_id = result.get('id', '')
        if not doc_id:
            continue
        
        # RRF核心公式：1/(k + rank)
        rrf_score = 1.0 / (k + rank)
        
        doc_scores[doc_id] = {
            'result': result,
            'vector_rrf': rrf_score * vector_weight,
            'bm25_rrf': 0.0,
            'vector_rank': rank,
            'bm25_rank': 0,
        }
    
    # 处理BM25检索结果：累加RRF得分
    for rank, result in enumerate(bm25_results, start=1):
        doc_id = result.get('id', '')
        if not doc_id:
            continue
        
        # RRF核心公式：1/(k + rank)
        rrf_score = 1.0 / (k + rank)
        
        if doc_id in doc_scores:
            # 文档已存在于向量结果中，累加BM25的RRF得分
            doc_scores[doc_id]['bm25_rrf'] = rrf_score * bm25_weight
            doc_scores[doc_id]['bm25_rank'] = rank
        else:
            # 文档仅出现在BM25结果中
            doc_scores[doc_id] = {
                'result': result,
                'vector_rrf': 0.0,
                'bm25_rrf': rrf_score * bm25_weight,
                'vector_rank': 0,
                'bm25_rank': rank,
            }
    
    # 计算最终RRF融合得分并排序
    fusion_results = []
    for doc_id, scores in doc_scores.items():
        final_rrf_score = scores['vector_rrf'] + scores['bm25_rrf']
        
        result = scores['result'].copy()
        result['rrf_score'] = final_rrf_score
        result['vector_rrf'] = scores['vector_rrf']
        result['bm25_rrf'] = scores['bm25_rrf']
        result['vector_rank'] = scores['vector_rank']
        result['bm25_rank'] = scores['bm25_rank']
        
        # 标记结果来源
        if scores['vector_rank'] > 0 and scores['bm25_rank'] > 0:
            result['source'] = 'both'
        elif scores['vector_rank'] > 0:
            result['source'] = 'vector'
        else:
            result['source'] = 'bm25'
        
        fusion_results.append(result)
    
    # 按RRF融合得分降序排序（O(N log N)）
    fusion_results.sort(key=lambda x: x['rrf_score'], reverse=True)
    
    return fusion_results[:top_k]


def compute_rrf_scores(
    results_lists: List[List[Dict[str, Any]]],
    weights: Optional[List[float]] = None,
    top_k: int = 5,
    k: int = RRF_K,
) -> List[Dict[str, Any]]:
    """通用RRF融合：支持多路检索结果融合（扩展版）
    
    适用于需要融合超过两路检索结果的场景，例如：
    - 向量检索（不同模型）
    - BM25检索
    - 关键词匹配
    - 知识图谱检索
    
    Args:
        results_lists: 多路检索结果列表的列表，每路结果按排名排序
        weights: 各路检索的权重列表，默认等权重
        top_k: 返回结果数量
        k: RRF平滑常数
        
    Returns:
        List[Dict[str, Any]]: 融合排序后的结果
    """
    num_lists = len(results_lists)
    if num_lists == 0:
        return []
    
    if weights is None:
        weights = [1.0 / num_lists] * num_lists
    elif len(weights) != num_lists:
        raise ValueError(f"权重数量({len(weights)})与结果路数({num_lists})不匹配")
    
    doc_scores: Dict[str, Dict] = {}
    
    for list_idx, results in enumerate(results_lists):
        weight = weights[list_idx]
        for rank, result in enumerate(results, start=1):
            doc_id = result.get('id', '')
            if not doc_id:
                continue
            
            rrf_score = weight / (k + rank)
            
            if doc_id in doc_scores:
                doc_scores[doc_id]['rrf_score'] += rrf_score
                doc_scores[doc_id]['ranks'].append((list_idx, rank))
            else:
                doc_scores[doc_id] = {
                    'result': result,
                    'rrf_score': rrf_score,
                    'ranks': [(list_idx, rank)],
                }
    
    fusion_results = []
    for doc_id, scores in doc_scores.items():
        result = scores['result'].copy()
        result['rrf_score'] = scores['rrf_score']
        result['ranks'] = scores['ranks']
        fusion_results.append(result)
    
    fusion_results.sort(key=lambda x: x['rrf_score'], reverse=True)
    return fusion_results[:top_k]
