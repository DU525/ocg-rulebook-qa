"""反馈分析器 - 分析反馈统计和生成报告"""
import logging
from datetime import datetime, timedelta
from collections import Counter
from typing import Dict, List, Any, Optional

logger = logging.getLogger(__name__)


class FeedbackAnalyzer:
    """反馈分析器，用于分析用户反馈数据"""

    REASON_CATEGORIES = [
        "answer_inaccurate",
        "answer_irrelevant",
        "citation_missing",
        "format_issue",
        "outdated_info",
        "other"
    ]

    REASON_LABELS = {
        "answer_inaccurate": "答案不准确",
        "answer_irrelevant": "答案不相关",
        "citation_missing": "引用缺失",
        "format_issue": "格式问题",
        "outdated_info": "信息过时",
        "other": "其他"
    }

    def __init__(self, db, Feedback, NegativeSample=None):
        self.db = db
        self.Feedback = Feedback
        self.NegativeSample = NegativeSample

    def analyze_feedback(self, game_type: str = 'ocg', days: int = 30) -> Dict[str, Any]:
        """分析反馈统计"""
        session = self.db.get_session()
        try:
            end_date = datetime.utcnow().replace(hour=23, minute=59, second=59, microsecond=999999)
            start_date = (end_date - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)

            total = session.query(self.Feedback).filter(
                self.Feedback.game_type == game_type,
                self.Feedback.created_at >= start_date,
                self.Feedback.created_at <= end_date
            ).count()

            positive = session.query(self.Feedback).filter(
                self.Feedback.game_type == game_type,
                self.Feedback.rating == 'positive',
                self.Feedback.created_at >= start_date,
                self.Feedback.created_at <= end_date
            ).count()

            negative = session.query(self.Feedback).filter(
                self.Feedback.game_type == game_type,
                self.Feedback.rating == 'negative',
                self.Feedback.created_at >= start_date,
                self.Feedback.created_at <= end_date
            ).count()

            positive_rate = round(positive / total, 4) if total > 0 else 0.0

            daily_trend = []
            current_date = start_date
            while current_date <= end_date:
                day_start = current_date.replace(hour=0, minute=0, second=0, microsecond=0)
                day_end = current_date.replace(hour=23, minute=59, second=59, microsecond=999999)
                dp = session.query(self.Feedback).filter(
                    self.Feedback.game_type == game_type,
                    self.Feedback.rating == 'positive',
                    self.Feedback.created_at >= day_start,
                    self.Feedback.created_at <= day_end
                ).count()
                dn = session.query(self.Feedback).filter(
                    self.Feedback.game_type == game_type,
                    self.Feedback.rating == 'negative',
                    self.Feedback.created_at >= day_start,
                    self.Feedback.created_at <= day_end
                ).count()
                daily_trend.append({
                    'date': day_start.strftime('%Y-%m-%d'),
                    'positive': dp,
                    'negative': dn,
                    'rate': round(dp / (dp + dn), 2) if (dp + dn) > 0 else None
                })
                current_date += timedelta(days=1)

            return {
                'total_feedbacks': total,
                'positive_count': positive,
                'negative_count': negative,
                'positive_rate': positive_rate,
                'daily_trend': daily_trend,
                'period_days': days
            }
        finally:
            session.close()

    def get_top_negative_reasons(self, game_type: str = 'ocg', limit: int = 10) -> List[Dict[str, Any]]:
        """获取差评原因TOP N"""
        session = self.db.get_session()
        try:
            neg_feedbacks = session.query(self.Feedback).filter(
                self.Feedback.game_type == game_type,
                self.Feedback.rating == 'negative',
                self.Feedback.reason.isnot(None),
                self.Feedback.reason != ''
            ).all()

            reason_counts = Counter([f.reason for f in neg_feedbacks])
            top_reasons = []
            for reason, count in reason_counts.most_common(limit):
                label = self.REASON_LABELS.get(reason, reason)
                top_reasons.append({
                    'reason': reason,
                    'label': label,
                    'count': count
                })

            return top_reasons
        finally:
            session.close()

    def get_negative_samples(self, game_type: str = 'ocg', page: int = 1, 
                            limit: int = 20, reason_filter: str = '') -> Dict[str, Any]:
        """获取负样本列表"""
        if not self.NegativeSample:
            return {'samples': [], 'total': 0, 'page': page, 'limit': limit}

        session = self.db.get_session()
        try:
            query = session.query(self.NegativeSample)
            if reason_filter:
                query = query.filter(self.NegativeSample.reason == reason_filter)

            total = query.count()
            samples = query.order_by(self.NegativeSample.created_at.desc()).offset((page - 1) * limit).limit(limit).all()

            result = [{
                'id': s.id,
                'question': s.question,
                'answer': s.answer,
                'reason': s.reason,
                'reason_label': self.REASON_LABELS.get(s.reason, s.reason),
                'feedback_id': s.feedback_id,
                'created_at': s.created_at.isoformat()
            } for s in samples]

            return {
                'samples': result,
                'total': total,
                'page': page,
                'limit': limit
            }
        finally:
            session.close()

    def generate_feedback_report(self, game_type: str = 'ocg', days: int = 30) -> Dict[str, Any]:
        """生成反馈报告"""
        session = self.db.get_session()
        try:
            analysis = self.analyze_feedback(game_type, days)
            top_reasons = self.get_top_negative_reasons(game_type, 10)
            
            negative_sample_count = 0
            if self.NegativeSample:
                negative_sample_count = session.query(self.NegativeSample).count()

            end_date = datetime.utcnow().replace(hour=23, minute=59, second=59, microsecond=999999)
            start_date = (end_date - timedelta(days=days - 1)).replace(hour=0, minute=0, second=0, microsecond=0)

            neg_feedbacks = session.query(self.Feedback).filter(
                self.Feedback.game_type == game_type,
                self.Feedback.rating == 'negative',
                self.Feedback.created_at >= start_date,
                self.Feedback.created_at <= end_date
            ).all()

            custom_reasons = []
            for f in neg_feedbacks:
                if f.reason and f.reason.startswith('other:'):
                    custom_reasons.append({
                        'reason_text': f.reason[6:],
                        'message_id': f.message_id,
                        'created_at': f.created_at.isoformat()
                    })

            report = {
                'report_generated_at': datetime.utcnow().isoformat(),
                'period_days': days,
                'summary': {
                    'total_feedbacks': analysis['total_feedbacks'],
                    'positive_count': analysis['positive_count'],
                    'negative_count': analysis['negative_count'],
                    'positive_rate': analysis['positive_rate'],
                    'negative_sample_count': negative_sample_count
                },
                'top_negative_reasons': top_reasons,
                'daily_trend': analysis['daily_trend'],
                'custom_reasons': custom_reasons[:20]
            }

            logger.info(f"[FeedbackReport] Report generated: {analysis['total_feedbacks']} feedbacks, "
                       f"positive_rate={analysis['positive_rate']}")

            return report
        finally:
            session.close()
