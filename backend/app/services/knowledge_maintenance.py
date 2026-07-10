"""
智能知识库维护助手 - 优化方向1
实现：数据质量自动检测、AI辅助内容更新、智能冲突检测
"""
import json
import hashlib
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from datetime import datetime, timedelta
from collections import defaultdict

logger = logging.getLogger(__name__)


@dataclass
class QualityIssue:
    """数据质量问题"""
    issue_type: str  # 'duplicate', 'outdated', 'conflict', 'incomplete'
    severity: str  # 'low', 'medium', 'high'
    description: str
    affected_items: List[str] = field(default_factory=list)
    suggested_fix: Optional[str] = None


@dataclass
class QualityScore:
    """质量评分"""
    overall_score: float = 0.0
    duplicate_rate: float = 0.0
    timeliness_score: float = 0.0
    completeness_score: float = 0.0
    conflict_count: int = 0
    issues: List[QualityIssue] = field(default_factory=list)


@dataclass
class RuleVersion:
    """规则版本"""
    rule_id: str
    version: str
    content: str
    change_type: str  # 'add', 'modify', 'delete'
    changed_by: str
    change_reason: str
    impact_scope: Dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=datetime.now)
    status: str = 'draft'  # 'draft', 'reviewing', 'published', 'rolled_back'


class KnowledgeMaintenanceAssistant:
    """智能知识库维护助手"""

    def __init__(self):
        self.quality_history: Dict[str, List[QualityScore]] = defaultdict(list)
        self.rule_versions: Dict[str, List[RuleVersion]] = defaultdict(list)
        self.knowledge_bases = ['OCG', 'DM']
        self.similarity_threshold = 0.9
        self.outdated_threshold = timedelta(days=90)
        logger.info("Knowledge Maintenance Assistant initialized")

    def check_data_quality(
        self,
        knowledge_base: str,
        chunks: List[Dict[str, Any]]
    ) -> QualityScore:
        """
        细分方向1.1：数据质量自动检测
        检测重复、过时、冲突、不完整的内容
        """
        logger.info(f"Checking data quality for {knowledge_base}")
        
        score = QualityScore()
        score.issues = []
        
        # 检测重复内容
        duplicates = self._detect_duplicates(chunks)
        score.duplicate_rate = len(duplicates) / max(1, len(chunks))
        if duplicates:
            score.issues.append(
                QualityIssue(
                    issue_type='duplicate',
                    severity='medium' if len(duplicates) > len(chunks)*0.1 else 'low',
                    description=f'Found {len(duplicates)} duplicate chunks',
                    affected_items=duplicates,
                    suggested_fix='Merge or remove duplicate entries'
                )
            )
        
        # 检测过时内容
        outdated = self._detect_outdated(chunks)
        score.timeliness_score = 1.0 - len(outdated) / max(1, len(chunks))
        if outdated:
            score.issues.append(
                QualityIssue(
                    issue_type='outdated',
                    severity='high' if len(outdated) > len(chunks)*0.2 else 'medium',
                    description=f'Found {len(outdated)} outdated chunks',
                    affected_items=outdated,
                    suggested_fix='Review and update outdated rules'
                )
            )
        
        # 检测冲突内容
        conflicts = self._detect_conflicts(chunks)
        score.conflict_count = len(conflicts)
        if conflicts:
            score.issues.append(
                QualityIssue(
                    issue_type='conflict',
                    severity='high',
                    description=f'Found {len(conflicts)} conflicting rules',
                    affected_items=conflicts,
                    suggested_fix='Resolve rule conflicts and update documentation'
                )
            )
        
        # 检测不完整内容
        incomplete = self._detect_incomplete(chunks)
        score.completeness_score = 1.0 - len(incomplete) / max(1, len(chunks))
        if incomplete:
            score.issues.append(
                QualityIssue(
                    issue_type='incomplete',
                    severity='medium',
                    description=f'Found {len(incomplete)} incomplete entries',
                    affected_items=incomplete,
                    suggested_fix='Add missing information to incomplete chunks'
                )
            )
        
        # 计算综合评分
        score.overall_score = (
            (1.0 - score.duplicate_rate) * 0.3 +
            score.timeliness_score * 0.25 +
            score.completeness_score * 0.25 +
            max(0.0, 1.0 - min(1.0, score.conflict_count / max(1, len(chunks)))) * 0.2
        )
        
        # 记录历史
        self.quality_history[knowledge_base].append(score)
        
        logger.info(f"Quality check completed. Score: {score.overall_score:.2f}")
        return score

    def _detect_duplicates(self, chunks: List[Dict[str, Any]]) -> List[str]:
        """检测重复内容（使用SimHash思想）"""
        duplicates = []
        content_hash_map = {}
        
        for chunk in chunks:
            content = chunk.get('content', '')
            if content:
                content_hash = self._compute_content_hash(content)
                if content_hash in content_hash_map:
                    duplicates.append(chunk.get('id', ''))
                else:
                    content_hash_map[content_hash] = chunk.get('id', '')
        
        return duplicates

    def _compute_content_hash(self, content: str) -> str:
        """计算内容指纹"""
        return hashlib.md5(content.lower().replace(' ', '').encode()).hexdigest()

    def _detect_outdated(self, chunks: List[Dict[str, Any]]) -> List[str]:
        """检测过时内容"""
        outdated = []
        now = datetime.now()
        
        for chunk in chunks:
            updated_at = chunk.get('updated_at')
            if updated_at:
                try:
                    if isinstance(updated_at, str):
                        updated_at = datetime.fromisoformat(updated_at)
                    if now - updated_at > self.outdated_threshold:
                        outdated.append(chunk.get('id', ''))
                except:
                    pass
        
        return outdated

    def _detect_conflicts(self, chunks: List[Dict[str, Any]]) -> List[str]:
        """检测冲突内容"""
        conflicts = []
        
        # 简单的关键词冲突检测
        conflict_keywords = [
            ('可以', '不可以'),
            ('允许', '禁止'),
            ('必须', '不必'),
            ('适用', '不适用'),
            ('有效', '无效'),
        ]
        
        content_map = {chunk.get('id', ''): chunk.get('content', '') for chunk in chunks}
        
        for chunk_id1, content1 in content_map.items():
            for chunk_id2, content2 in content_map.items():
                if chunk_id1 >= chunk_id2:
                    continue
                for keyword1, keyword2 in conflict_keywords:
                    if keyword1 in content1 and keyword2 in content2:
                        if chunk_id1 not in conflicts:
                            conflicts.append(chunk_id1)
                        if chunk_id2 not in conflicts:
                            conflicts.append(chunk_id2)
        
        return conflicts

    def _detect_incomplete(self, chunks: List[Dict[str, Any]]) -> List[str]:
        """检测不完整内容"""
        incomplete = []
        
        for chunk in chunks:
            content = chunk.get('content', '')
            # 简单的完整性检测：太短、缺少必要字段等
            if len(content) < 50:
                incomplete.append(chunk.get('id', ''))
            elif '待补充' in content or 'TODO' in content or '占位' in content:
                incomplete.append(chunk.get('id', ''))
        
        return incomplete

    def suggest_rule_update(
        self,
        rule_id: str,
        current_content: str,
        new_information: str
    ) -> Dict[str, Any]:
        """
        细分方向1.2：AI辅助内容更新
        根据新信息生成更新建议
        """
        logger.info(f"Suggesting update for rule {rule_id}")
        
        # 分析变更影响
        impact_scope = self._analyze_impact(rule_id, new_information)
        
        # 生成新版本号
        current_version = self._get_latest_version(rule_id)
        new_version = self._bump_version(current_version)
        
        suggestion = {
            'rule_id': rule_id,
            'current_content': current_content,
            'suggested_content': self._generate_updated_content(current_content, new_information),
            'change_type': 'modify',
            'new_version': new_version,
            'impact_scope': impact_scope,
            'suggested_reason': 'New information available',
            'review_required': True
        }
        
        # 创建版本记录
        rule_version = RuleVersion(
            rule_id=rule_id,
            version=new_version,
            content=suggestion['suggested_content'],
            change_type='modify',
            changed_by='system',
            change_reason=suggestion['suggested_reason'],
            impact_scope=impact_scope,
            status='draft'
        )
        self.rule_versions[rule_id].append(rule_version)
        
        return suggestion

    def _analyze_impact(self, rule_id: str, new_info: str) -> Dict[str, Any]:
        """分析规则变更影响范围"""
        impact = {
            'affected_rules': [],
            'affected_cards': [],
            'related_topics': [],
            'severity': 'medium'
        }
        
        # 简单的影响分析：根据关键词判断
        keywords = ['召唤', '连锁', '战斗', '效果', '特殊']
        for keyword in keywords:
            if keyword in new_info:
                impact['related_topics'].append(keyword)
        
        if len(impact['related_topics']) > 2:
            impact['severity'] = 'high'
        
        return impact

    def _get_latest_version(self, rule_id: str) -> str:
        """获取最新版本号"""
        if rule_id in self.rule_versions and self.rule_versions[rule_id]:
            return self.rule_versions[rule_id][-1].version
        return '1.0.0'

    def _bump_version(self, version: str) -> str:
        """版本号递增"""
        parts = version.split('.')
        parts[-1] = str(int(parts[-1]) + 1)
        return '.'.join(parts)

    def _generate_updated_content(self, current: str, new_info: str) -> str:
        """生成更新后的内容（简单合并示例）"""
        return f"{current}\n\n更新补充：{new_info}"

    def detect_conflicts_and_suggest_merge(
        self,
        chunks: List[Dict[str, Any]]
    ) -> List[Dict[str, Any]]:
        """
        细分方向1.3：智能冲突检测
        检测冲突并提供合并建议
        """
        logger.info("Detecting conflicts and suggesting merges")
        
        conflicts = self._detect_conflicts(chunks)
        suggestions = []
        
        if not conflicts:
            return suggestions
        
        # 分析冲突关系
        conflict_groups = self._group_conflicting_chunks(chunks, conflicts)
        
        for group in conflict_groups:
            suggestion = {
                'conflict_group': group,
                'suggested_action': 'review_and_merge',
                'priority': 'high' if len(group) > 2 else 'medium',
                'suggested_primary': group[0] if group else None,
                'suggested_merges': group[1:] if len(group) > 1 else []
            }
            suggestions.append(suggestion)
        
        return suggestions

    def _group_conflicting_chunks(
        self,
        chunks: List[Dict[str, Any]],
        conflict_ids: List[str]
    ) -> List[List[str]]:
        """将冲突的chunks分组"""
        # 简单实现：将所有冲突的放在一组
        if conflict_ids:
            return [conflict_ids]
        return []

    def get_quality_trend(
        self,
        knowledge_base: str,
        days: int = 30
    ) -> Dict[str, Any]:
        """获取质量趋势"""
        if knowledge_base not in self.quality_history:
            return {'message': 'No quality history available'}
        
        history = self.quality_history[knowledge_base]
        cutoff = datetime.now() - timedelta(days=days)
        
        relevant = [s for s in history if hasattr(s, 'timestamp') and s.timestamp > cutoff]
        
        if not relevant:
            return {'message': 'No recent quality data available'}
        
        scores = [s.overall_score for s in relevant]
        trend = {
            'latest_score': scores[-1] if scores else 0,
            'score_change': scores[-1] - scores[0] if len(scores) > 1 else 0,
            'improving': scores[-1] > scores[0] if len(scores) > 1 else False,
            'total_checks': len(relevant)
        }
        
        return trend

    def get_maintenance_statistics(self) -> Dict[str, Any]:
        """获取维护统计"""
        stats = {
            'total_rules': sum(len(versions) for versions in self.rule_versions.values()),
            'kb_quality_stats': {},
            'total_versions': sum(len(v) for v in self.rule_versions.values()),
            'pending_reviews': sum(1 for vlist in self.rule_versions.values() for v in vlist if v.status == 'draft')
        }
        
        for kb in self.knowledge_bases:
            if kb in self.quality_history and self.quality_history[kb]:
                latest = self.quality_history[kb][-1]
                stats['kb_quality_stats'][kb] = {
                    'latest_score': latest.overall_score,
                    'issues_count': len(latest.issues)
                }
        
        return stats


# 全局单例
_maintenance_assistant = None

def get_maintenance_assistant() -> KnowledgeMaintenanceAssistant:
    """获取维护助手单例"""
    global _maintenance_assistant
    if _maintenance_assistant is None:
        _maintenance_assistant = KnowledgeMaintenanceAssistant()
    return _maintenance_assistant
