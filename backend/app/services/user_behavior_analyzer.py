"""
用户行为分析器 - 用户画像与热点问题分析
功能：
- 用户画像构建（活跃度、偏好、历史记录）
- 热点问题统计
- 趋势分析
- 个性化推荐
"""
import time
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from collections import defaultdict, Counter
from datetime import datetime, timedelta
from app.db.models import Message, Feedback

logger = logging.getLogger(__name__)


@dataclass
class UserProfile:
    """用户画像"""
    user_id: str
    total_questions: int = 0
    total_feedbacks: int = 0
    positive_feedback_rate: float = 0.0
    avg_response_time: float = 0.0
    favorite_topics: List[str] = field(default_factory=list)
    active_hours: List[int] = field(default_factory=list)
    first_seen: float = field(default_factory=time.time)
    last_active: float = field(default_factory=time.time)


class UserBehaviorAnalyzer:
    """用户行为分析器"""

    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        if self._initialized:
            return
        self._initialized = True
        self._user_profiles: Dict[str, UserProfile] = {}
        self._hot_questions: Counter = Counter()
        self._topic_keywords = {
            "召唤": ["召唤", "通常召唤", "反转召唤", "特殊召唤", "同步召唤", "超量召唤", "连接召唤", "融合召唤", "仪式召唤"],
            "魔法陷阱": ["魔法", "陷阱", "速攻", "永续", "装备", "场地", "反击"],
            "战斗": ["战斗", "攻击", "伤害", "防御", "表示形式", "战斗阶段"],
            "效果": ["效果", "发动", "连锁", "无效", "破坏", "除外", "送墓"],
            "规则": ["规则", "裁定", "优先权", "卡时点", "同时发动"],
            "卡组": ["卡组", "主卡组", "额外卡组", "副卡组", "卡数"],
        }
        logger.info("用户行为分析器初始化完成")

    def _extract_topic(self, question: str) -> Optional[str]:
        """从问题中提取主题"""
        question_lower = question.lower()
        for topic, keywords in self._topic_keywords.items():
            for keyword in keywords:
                if keyword.lower() in question_lower:
                    return topic
        return None

    def record_question(self, user_id: str, question: str, response_time: float) -> None:
        """记录用户问题"""
        # 更新用户画像
        if user_id not in self._user_profiles:
            self._user_profiles[user_id] = UserProfile(user_id=user_id)

        profile = self._user_profiles[user_id]
        profile.total_questions += 1
        profile.last_active = time.time()

        # 更新平均响应时间
        total_time = profile.avg_response_time * (profile.total_questions - 1) + response_time
        profile.avg_response_time = total_time / profile.total_questions

        # 更新活跃时段
        hour = datetime.fromtimestamp(time.time()).hour
        if hour not in profile.active_hours:
            profile.active_hours.append(hour)

        # 更新偏好主题
        topic = self._extract_topic(question)
        if topic and topic not in profile.favorite_topics:
            profile.favorite_topics.append(topic)
            if len(profile.favorite_topics) > 5:
                profile.favorite_topics.pop(0)

        # 更新热点问题
        self._hot_questions[question] += 1

        logger.debug(f"记录用户问题: {user_id}, 问题: {question[:30]}...")

    def record_feedback(self, user_id: str, is_positive: bool) -> None:
        """记录用户反馈"""
        if user_id not in self._user_profiles:
            return

        profile = self._user_profiles[user_id]
        profile.total_feedbacks += 1

        # 计算正反馈率
        if profile.total_feedbacks > 0:
            current_positive = int(profile.positive_feedback_rate * (profile.total_feedbacks - 1))
            if is_positive:
                current_positive += 1
            profile.positive_feedback_rate = current_positive / profile.total_feedbacks

    def get_user_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """获取用户画像"""
        profile = self._user_profiles.get(user_id)
        if not profile:
            return None

        return {
            "user_id": profile.user_id,
            "total_questions": profile.total_questions,
            "total_feedbacks": profile.total_feedbacks,
            "positive_feedback_rate": round(profile.positive_feedback_rate, 2),
            "avg_response_time": round(profile.avg_response_time, 2),
            "favorite_topics": profile.favorite_topics,
            "active_hours": profile.active_hours,
            "first_seen": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(profile.first_seen)),
            "last_active": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(profile.last_active)),
        }

    def get_hot_questions(self, limit: int = 10, days: int = 7) -> List[Dict[str, Any]]:
        """获取热点问题"""
        # 简单实现：返回频率最高的问题
        hot_list = self._hot_questions.most_common(limit)

        return [
            {
                "question": question,
                "frequency": count,
                "topic": self._extract_topic(question),
            }
            for question, count in hot_list
        ]

    def get_trending_topics(self, days: int = 7) -> List[Dict[str, Any]]:
        """获取趋势话题"""
        topic_counts: Dict[str, int] = defaultdict(int)

        for question, count in self._hot_questions.items():
            topic = self._extract_topic(question)
            if topic:
                topic_counts[topic] += count

        sorted_topics = sorted(topic_counts.items(), key=lambda x: x[1], reverse=True)

        return [
            {
                "topic": topic,
                "count": count,
            }
            for topic, count in sorted_topics
        ]

    def get_user_suggestions(self, user_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """为用户生成个性化建议"""
        profile = self._user_profiles.get(user_id)
        if not profile or not profile.favorite_topics:
            # 返回通用热点问题
            return self.get_hot_questions(limit=limit)

        # 基于用户偏好筛选
        suggestions = []
        favorite_set = set(profile.favorite_topics)

        for question, count in self._hot_questions.most_common(limit * 2):
            topic = self._extract_topic(question)
            if topic in favorite_set:
                suggestions.append({
                    "question": question,
                    "frequency": count,
                    "topic": topic,
                    "personalized": True,
                })
                if len(suggestions) >= limit:
                    break

        # 补充通用问题
        if len(suggestions) < limit:
            general = self.get_hot_questions(limit=limit)
            for item in general:
                if len(suggestions) >= limit:
                    break
                if item["question"] not in [s["question"] for s in suggestions]:
                    item["personalized"] = False
                    suggestions.append(item)

        return suggestions

    def get_statistics(self, days: int = 7) -> Dict[str, Any]:
        """获取整体统计"""
        total_users = len(self._user_profiles)
        total_questions = sum(p.total_questions for p in self._user_profiles.values())
        avg_questions_per_user = total_questions / max(total_users, 1)

        active_users = sum(
            1 for p in self._user_profiles.values()
            if (time.time() - p.last_active) < days * 86400
        )

        return {
            "period_days": days,
            "total_users": total_users,
            "active_users": active_users,
            "total_questions": total_questions,
            "avg_questions_per_user": round(avg_questions_per_user, 2),
            "hot_topics": self.get_trending_topics(days=days),
            "hot_questions": self.get_hot_questions(limit=5, days=days),
        }


def get_behavior_analyzer() -> UserBehaviorAnalyzer:
    """获取用户行为分析器单例"""
    return UserBehaviorAnalyzer()

