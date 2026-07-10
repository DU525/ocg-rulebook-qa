"""
Query优化器 - 第1优先级优化点
实现5个细分方向：查询扩展、查询分解、查询改写、查询分类、查询过滤
预计提升：25-35% | 时间成本：1-2小时
"""
import re
import random
from typing import List, Dict, Optional, Tuple
from dataclasses import dataclass


@dataclass
class QueryRewriteResult:
    """查询重写结果"""
    original_query: str
    rewritten_queries: List[str]
    decomposed_queries: List[str]
    expanded_query: str
    filtered_query: str
    query_type: str


class QueryOptimizer:
    """
    综合查询优化器
    实现5个细分优化方向
    """

    # 游戏王OCG领域同义词词典
    SYNONYMS = {
        '怪兽': ['怪物', '怪', '怪兽卡', 'monster'],
        '魔法': ['魔法卡', 'spell', 'spell card'],
        '陷阱': ['陷阱卡', 'trap', 'trap card'],
        '召唤': ['特召', '特殊召唤', '通常召唤', 'summon'],
        '攻击': ['攻击宣言', 'attack', '战斗'],
        '效果': ['effect', '效果处理'],
        '连锁': ['chain', '连锁处理'],
        '墓地': ['grave', 'graveyard'],
        '卡组': ['主卡组', 'deck'],
        '手卡': ['手牌', 'hand'],
        '场上': ['场地区', '场上存在'],
        'OCG': ['游戏王', '游戏王规则', 'Yu-Gi-Oh'],
        'DM': ['数码宝贝', '数码暴龙', 'Digimon']
    }

    # 查询类型定义
    QUERY_TYPES = {
        'simple': '简单查询',
        'concept': '概念查询',
        'compare': '比较查询',
        'operation': '操作查询',
        'complex': '复杂查询'
    }

    # 无意义过滤词
    STOPWORDS = [
        '的', '了', '在', '是', '我', '有', '和', '就', '不', '人',
        '都', '一', '一个', '上', '也', '很', '到', '说', '要', '去',
        '你', '会', '着', '没有', '看', '好', '自己', '这', '请问',
        '您好', '帮忙', '一下', '吗', '呢', '吧', '啊'
    ]

    def __init__(self):
        self.conjunction_patterns = [
            r'(.*)(和|与|及|以及|以及)(.*)',
            r'(.*)(区别|差别|差异|不同)(.*)',
            r'(.*)(和|与)(.*)(哪个|哪一个)(.*)',
            r'(.*)(同时|一起|都)(.*)'
        ]

    def optimize(self, query: str) -> QueryRewriteResult:
        """
        综合查询优化入口
        
        Args:
            query: 原始查询
            
        Returns:
            QueryRewriteResult: 查询优化结果
        """
        # 1. 查询分类
        query_type = self.classify_query(query)
        
        # 2. 查询过滤
        filtered_query = self.filter_query(query)
        
        # 3. 查询扩展
        expanded_query = self.expand_query(filtered_query)
        
        # 4. 查询分解
        decomposed_queries = self.decompose_query(query)
        
        # 5. 查询改写
        rewritten_queries = self.rewrite_query(filtered_query, query_type)
        
        return QueryRewriteResult(
            original_query=query,
            rewritten_queries=rewritten_queries,
            decomposed_queries=decomposed_queries,
            expanded_query=expanded_query,
            filtered_query=filtered_query,
            query_type=query_type
        )

    def expand_query(self, query: str) -> str:
        """
        细分方向1：查询扩展（Query Expansion）
        为原始查询添加相关关键词和同义词
        
        Args:
            query: 原始查询
            
        Returns:
            扩展后的查询
        """
        expanded = query
        
        # 添加同义词扩展
        for term, synonyms in self.SYNONYMS.items():
            if term in query:
                # 添加同义词
                for synonym in synonyms[:2]:  # 每词最多加2个同义词
                    if synonym not in expanded:
                        expanded += f" {synonym}"
        
        # 添加领域相关关键词
        if '游戏王' in query or 'OCG' in query or '规则' in query:
            expanded += ' 规则文档 游戏规则'
        
        if '数码宝贝' in query or 'DM' in query:
            expanded += ' 数码宝贝规则 Digimon规则'
        
        return expanded

    def decompose_query(self, query: str) -> List[str]:
        """
        细分方向2：查询分解（Query Decomposition）
        复杂问题拆解为多个子问题
        
        Args:
            query: 原始查询
            
        Returns:
            分解后的子问题列表
        """
        subqueries = [query]  # 至少包含原始查询
        
        # 基于连接词分解
        for pattern in self.conjunction_patterns:
            match = re.search(pattern, query)
            if match:
                # 尝试提取各个部分
                parts = []
                part1 = match.group(1).strip() if match.group(1) else ''
                part3 = match.group(3).strip() if match.group(3) else ''
                
                if part1 and len(part1) > 3:
                    parts.append(self._make_query(part1))
                if part3 and len(part3) > 3:
                    parts.append(self._make_query(part3))
                
                if parts:
                    subqueries.extend(parts)
        
        # 基于问号分解（多个问题）
        if query.count('?') + query.count('？') > 1:
            question_parts = re.split(r'[?？]', query)
            for part in question_parts:
                part = part.strip()
                if len(part) > 3 and part not in subqueries:
                    subqueries.append(part + '？')
        
        return subqueries

    def rewrite_query(self, query: str, query_type: str) -> List[str]:
        """
        细分方向3：查询改写（Query Rewriting）
        改善问题表述，使其更符合检索语言
        
        Args:
            query: 原始查询
            query_type: 查询类型
            
        Returns:
            改写后的查询列表
        """
        rewrites = [query]
        
        # 改写策略1：规范化术语
        normalized = self._normalize_terms(query)
        if normalized != query:
            rewrites.append(normalized)
        
        # 改写策略2：添加疑问词
        question_forms = self._generate_question_forms(query)
        rewrites.extend(question_forms)
        
        # 改写策略3：简化问题
        simplified = self._simplify_query(query)
        if simplified != query and simplified not in rewrites:
            rewrites.append(simplified)
        
        # 改写策略4：根据类型定制
        type_rewrites = self._rewrite_by_type(query, query_type)
        rewrites.extend(type_rewrites)
        
        return list(set(rewrites))[:5]  # 去重，最多返回5个

    def classify_query(self, query: str) -> str:
        """
        细分方向4：查询分类（Query Classification）
        识别问题类型，匹配最优检索策略
        
        Args:
            query: 原始查询
            
        Returns:
            查询类型字符串
        """
        # 简单查询
        simple_indicators = ['什么是', '如何', '怎么', '怎样', '哪里']
        if any(ind in query for ind in simple_indicators):
            if len(query) < 20:
                return 'simple'
            else:
                return 'concept'
        
        # 比较查询
        compare_indicators = ['区别', '差异', '不同', '对比', '比较', '哪个更好']
        if any(ind in query for ind in compare_indicators):
            return 'compare'
        
        # 操作查询
        operation_indicators = ['如何', '怎样', '怎么操作', '步骤', '方法']
        if any(ind in query for ind in operation_indicators):
            return 'operation'
        
        # 复杂查询
        complex_indicators = ['同时', '一起', '并且', '而且', '和', '与']
        if len(query) > 30 or any(ind in query for ind in complex_indicators):
            return 'complex'
        
        return 'concept'

    def filter_query(self, query: str) -> str:
        """
        细分方向5：查询过滤（Query Filtering）
        去除无意义词汇，提升检索精准度
        
        Args:
            query: 原始查询
            
        Returns:
            过滤后的查询
        """
        # 1. 去除停用词
        filtered_words = []
        words = list(query)
        
        for word in self.STOPWORDS:
            query = query.replace(word, '')
        
        # 2. 修剪空白
        query = re.sub(r'\s+', ' ', query).strip()
        
        # 3. 确保查询不为空
        if not query:
            return ''
        
        return query

    def _normalize_terms(self, query: str) -> str:
        """规范化术语表达"""
        normalized = query
        
        # 常见术语规范化
        term_mappings = {
            '游戏王卡': '游戏王OCG',
            '游戏王': '游戏王OCG',
            '怪兽卡': '怪兽',
            '魔法卡': '魔法',
            '陷阱卡': '陷阱',
            '特召': '特殊召唤'
        }
        
        for old, new in term_mappings.items():
            if old in normalized and new not in normalized:
                normalized = normalized.replace(old, new)
        
        return normalized

    def _generate_question_forms(self, query: str) -> List[str]:
        """生成不同形式的疑问表达"""
        forms = []
        
        # 为陈述句添加疑问词
        if not any(q in query for q in ['?', '？', '什么', '如何', '怎么', '怎样']):
            forms.append(f"什么是{query}？")
            forms.append(f"{query}是什么？")
        
        return forms

    def _simplify_query(self, query: str) -> str:
        """简化查询表达式"""
        # 移除修饰性词语
        simplify_patterns = [
            r'请(问|问一下|告诉我)',
            r'你好[，,]*',
            r'谢谢[，,]*',
            r'麻烦[您]*',
            r'帮我[一]*下'
        ]
        
        simplified = query
        for pattern in simplify_patterns:
            simplified = re.sub(pattern, '', simplified)
        
        return simplified.strip()

    def _make_query(self, part: str) -> str:
        """从片段构造完整查询"""
        if not part:
            return ''
        if not any(q in part for q in ['?', '？', '什么', '如何', '怎么']):
            part = f"什么是{part}？"
        return part

    def _rewrite_by_type(self, query: str, query_type: str) -> List[str]:
        """根据查询类型进行定制改写"""
        rewrites = []
        
        if query_type == 'compare':
            # 比较查询：分离比较对象
            for separator in ['和', '与', '及', '以及']:
                if separator in query:
                    parts = query.split(separator)
                    if len(parts) == 2:
                        rewrites.append(f"{parts[0].strip()}的规则")
                        rewrites.append(f"{parts[1].strip()}的规则")
        
        elif query_type == 'operation':
            # 操作查询：强调操作过程
            if '步骤' not in query:
                rewrites.append(f"{query}的步骤")
            if '方法' not in query:
                rewrites.append(f"{query}的方法")
        
        elif query_type == 'concept':
            # 概念查询：强调定义和解释
            if '定义' not in query:
                rewrites.append(f"{query}的定义")
            if '解释' not in query:
                rewrites.append(f"{query}的解释")
        
        return rewrites

    def get_best_query_for_retrieval(self, query: str) -> str:
        """
        获取最适合检索的查询版本
        
        Args:
            query: 原始查询
            
        Returns:
            优化后的最佳查询
        """
        result = self.optimize(query)
        
        # 策略：使用扩展后的查询
        return result.expanded_query

    def get_retrieval_queries(self, query: str) -> List[str]:
        """
        获取用于检索的查询列表（包括原始查询和各种改写）
        
        Args:
            query: 原始查询
            
        Returns:
            查询列表
        """
        result = self.optimize(query)
        
        # 组合所有查询版本
        all_queries = [result.original_query]
        
        if result.filtered_query != result.original_query:
            all_queries.append(result.filtered_query)
        
        all_queries.extend(result.rewritten_queries)
        all_queries.extend(result.decomposed_queries)
        
        if result.expanded_query != result.original_query:
            all_queries.append(result.expanded_query)
        
        # 去重并过滤掉太短的查询
        unique_queries = list(set([q.strip() for q in all_queries if len(q.strip()) > 3]))
        
        return unique_queries


# 全局实例
_query_optimizer = None

def get_query_optimizer() -> QueryOptimizer:
    """获取查询优化器单例"""
    global _query_optimizer
    if _query_optimizer is None:
        _query_optimizer = QueryOptimizer()
    return _query_optimizer
