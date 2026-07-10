"""提问建议引擎 - 基于历史查询频率、用户反馈、时间衰减推荐热门问题"""
import logging
import math
import re
from collections import Counter
from datetime import datetime, timedelta
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class SuggestionEngine:
    """提问建议引擎，用于生成热门问题建议"""

    CATEGORIES = {
        '规则类': ['召唤', '发动', '效果', '连锁', '处理', '规则', '裁定', '时机', 'cost', '代价', '取对象', '不取对象'],
        '概念类': ['什么是', '意思', '区别', '类型', '种类', '定义', '说明', '介绍', '机制', '原理'],
        '操作类': ['怎么', '如何', '步骤', '流程', '方法', '顺序', '优先权', '回合', '阶段', '流程'],
    }

    def __init__(self, db, Message, Feedback=None):
        self.db = db
        self.Message = Message
        self.Feedback = Feedback

    def get_hot_questions(
        self,
        game_type: str = 'ocg',
        category: Optional[str] = None,
        limit: int = 10,
        days: int = 30
    ) -> List[Dict[str, Any]]:
        """获取热门问题建议

        Args:
            game_type: 游戏类型 (ocg/dm)
            category: 分类过滤（规则类/概念类/操作类）
            limit: 返回数量限制
            days: 统计时间范围（天）

        Returns:
            热门问题建议列表 [{question, category, frequency, relevance_score}]
        """
        session = self.db.get_session()
        try:
            end_date = datetime.utcnow()
            start_date = end_date - timedelta(days=days)

            messages = session.query(self.Message).filter(
                self.Message.role == 'user',
                self.Message.created_at >= start_date,
                self.Message.created_at <= end_date
            ).order_by(self.Message.created_at.desc()).all()

            question_counts = Counter([msg.content for msg in messages])

            question_first_seen = {}
            for msg in reversed(messages):
                if msg.content not in question_first_seen:
                    question_first_seen[msg.content] = msg.created_at

            suggestions = []
            for question, frequency in question_counts.most_common(limit * 3):
                cat = self._categorize_question(question)
                if category and cat != category:
                    continue

                time_decay = self._calculate_time_decay(question_first_seen.get(question, start_date), end_date)
                relevance_score = self._calculate_relevance(frequency, time_decay, question)

                suggestions.append({
                    'question': question,
                    'category': cat,
                    'frequency': frequency,
                    'relevance_score': round(relevance_score, 4),
                    'time_decay': round(time_decay, 4)
                })

            suggestions.sort(key=lambda x: x['relevance_score'], reverse=True)
            return suggestions[:limit]

        finally:
            session.close()

    def get_category_suggestions(
        self,
        game_type: str = 'ocg',
        limit_per_category: int = 5
    ) -> Dict[str, List[Dict[str, Any]]]:
        """获取各分类的热门问题建议

        Args:
            game_type: 游戏类型
            limit_per_category: 每个分类的返回数量

        Returns:
            {category: [suggestions]}
        """
        result = {}
        for category in self.CATEGORIES.keys():
            result[category] = self.get_hot_questions(
                game_type=game_type,
                category=category,
                limit=limit_per_category
            )
        return result

    def get_personalized_suggestions(
        self,
        conversation_id: str,
        game_type: str = 'ocg',
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """基于用户历史生成个性化建议

        Args:
            conversation_id: 用户对话ID
            game_type: 游戏类型
            limit: 返回数量

        Returns:
            个性化建议列表
        """
        session = self.db.get_session()
        try:
            user_history = session.query(self.Message).filter(
                self.Message.role == 'user',
                self.Message.conversation_id == conversation_id
            ).order_by(self.Message.created_at.desc()).limit(10).all()

            if not user_history:
                return self.get_hot_questions(game_type=game_type, limit=limit)

            history_keywords = set()
            for msg in user_history:
                words = re.findall(r'[\u4e00-\u9fa5]{2,}', msg.content)
                history_keywords.update(words)

            all_suggestions = self.get_hot_questions(game_type=game_type, limit=limit * 3)

            personalized = []
            for suggestion in all_suggestions:
                score_boost = 1.0
                question_keywords = set(re.findall(r'[\u4e00-\u9fa5]{2,}', suggestion['question']))
                common_keywords = history_keywords & question_keywords
                if common_keywords:
                    score_boost = 1.0 + len(common_keywords) * 0.2

                suggestion['relevance_score'] = round(
                    suggestion['relevance_score'] * score_boost, 4
                )
                personalized.append(suggestion)

            personalized.sort(key=lambda x: x['relevance_score'], reverse=True)
            return personalized[:limit]

        finally:
            session.close()

    def get_default_suggestions(
        self,
        game_type: str = 'ocg',
        limit: int = 10
    ) -> List[Dict[str, Any]]:
        """获取默认建议（当历史数据不足时使用）

        Args:
            game_type: 游戏类型
            limit: 返回数量

        Returns:
            默认建议列表
        """
        default_ocg = [
            {'question': '什么是通常召唤？', 'category': '概念类'},
            {'question': '连锁的处理顺序是什么？', 'category': '规则类'},
            {'question': '魔法卡和陷阱卡有什么区别？', 'category': '概念类'},
            {'question': '灵摆召唤的规则是什么？', 'category': '规则类'},
            {'question': '效果伤害步骤怎么计算？', 'category': '操作类'},
            {'question': '回合的流程是什么？', 'category': '操作类'},
            {'question': '什么是优先权？', 'category': '概念类'},
            {'question': '取对象效果和不取对象效果有什么区别？', 'category': '规则类'},
            {'question': 'cost和代价有什么区别？', 'category': '概念类'},
            {'question': '融合召唤的步骤是什么？', 'category': '操作类'},
        ]

        default_dm = [
            {'question': '内存指示物的规则是什么？', 'category': '规则类'},
            {'question': '数码宝贝如何进化？', 'category': '操作类'},
            {'question': '安全区攻击的规则是什么？', 'category': '规则类'},
            {'question': '什么是回忆费用？', 'category': '概念类'},
            {'question': '育成区的规则是什么？', 'category': '规则类'},
            {'question': '数码宝贝的类型有哪些？', 'category': '概念类'},
            {'question': '战斗阶段的流程是什么？', 'category': '操作类'},
            {'question': '什么是登场时效果？', 'category': '概念类'},
            {'question': '选项卡的使用规则是什么？', 'category': '规则类'},
            {'question': '如何构建卡组？', 'category': '操作类'},
        ]

        defaults = default_dm if game_type == 'dm' else default_ocg
        suggestions = []
        for item in defaults[:limit]:
            suggestions.append({
                'question': item['question'],
                'category': item['category'],
                'frequency': 0,
                'relevance_score': 0.5,
                'time_decay': 1.0,
                'is_default': True
            })

        return suggestions

    def _categorize_question(self, question: str) -> str:
        """对问题进行分类

        Args:
            question: 问题文本

        Returns:
            分类标签
        """
        question_lower = question.lower()
        scores = {}
        for category, keywords in self.CATEGORIES.items():
            score = sum(1 for kw in keywords if kw.lower() in question_lower)
            scores[category] = score

        max_score = max(scores.values())
        if max_score == 0:
            return '规则类'

        for category, score in scores.items():
            if score == max_score:
                return category

        return '规则类'

    def _calculate_time_decay(self, first_seen: datetime, now: datetime) -> float:
        """计算时间衰减因子

        使用指数衰减：decay = e^(-λ * t)
        t = 天数，λ = 0.05（半衰期约14天）

        Args:
            first_seen: 首次出现时间
            now: 当前时间

        Returns:
            时间衰减值 (0-1)
        """
        days_diff = (now - first_seen).total_seconds() / 86400.0
        decay_rate = 0.05
        return math.exp(-decay_rate * days_diff)

    def _calculate_relevance(
        self,
        frequency: int,
        time_decay: float,
        question: str
    ) -> float:
        """计算综合相关度分数

        relevance = frequency_score * 0.5 + time_decay * 0.3 + length_score * 0.2

        Args:
            frequency: 查询频率
            time_decay: 时间衰减因子
            question: 问题文本

        Returns:
            相关度分数
        """
        freq_score = min(frequency / 10.0, 1.0)

        question_len = len(question)
        if 5 <= question_len <= 30:
            length_score = 1.0
        elif question_len < 5:
            length_score = 0.3
        else:
            length_score = max(0.5, 1.0 - (question_len - 30) * 0.02)

        relevance = freq_score * 0.5 + time_decay * 0.3 + length_score * 0.2
        return relevance
