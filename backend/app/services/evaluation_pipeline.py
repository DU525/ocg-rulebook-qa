"""
监控和评估管道 - 量化指标的持续监控与评估

功能：
1. 定期采集指标数据
2. 自动评估指标状态
3. 生成优化建议
4. 触发优化流程
5. 监控告警
"""

import time
import logging
from typing import Dict, List, Optional, Any
from dataclasses import dataclass
from datetime import datetime
from app.core.quantitative_metrics import QuantitativeMetricsFramework, MetricCategory, MetricLevel
from app.services.quantitative_optimizer import QuantitativeOptimizer, get_quantitative_optimizer

logger = logging.getLogger(__name__)


@dataclass
class MetricSnapshot:
    """指标快照"""
    timestamp: float
    metric_name: str
    value: float
    status: str  # 'healthy', 'warning', 'critical'


class EvaluationPipeline:
    """
    评估管道
    
    持续监控和评估系统的多维量化指标
    """

    def __init__(self):
        self.framework = QuantitativeMetricsFramework()
        self.optimizer = get_quantitative_optimizer()
        self.history: List[MetricSnapshot] = []
        self.auto_optimization_enabled = False
        self.evaluation_interval = 3600  # 默认1小时评估一次

    def record_metrics(self, metrics_values: Dict[str, float]) -> None:
        """
        记录指标快照
        
        Args:
            metrics_values: 指标名称到值的映射
        """
        for metric_name, value in metrics_values.items():
            metric = self.framework.get_metric_by_name(metric_name)
            if not metric:
                continue
            
            # 判断状态
            status = self._evaluate_metric_status(metric, value)
            
            snapshot = MetricSnapshot(
                timestamp=time.time(),
                metric_name=metric_name,
                value=value,
                status=status
            )
            self.history.append(snapshot)
            
            # 检查是否触发告警
            if status in ['warning', 'critical']:
                self._trigger_alert(metric, value, status)

    def _evaluate_metric_status(
        self,
        metric: Any,
        value: float
    ) -> str:
        """评估指标状态"""
        # 延迟和错误率（越低越好）
        if metric.name in ['ttfb', 'avg_latency', 'p95_latency', 'p99_latency', 'error_rate', 'follow_up_rate']:
            if value <= metric.target:
                return 'healthy'
            elif value <= metric.warning_threshold:
                return 'warning'
            elif value <= metric.critical_threshold:
                return 'warning'
            else:
                return 'critical'
        else:
            # 质量指标（越高越好）
            if value >= metric.target:
                return 'healthy'
            elif value >= metric.warning_threshold:
                return 'warning'
            elif value >= metric.critical_threshold:
                return 'warning'
            else:
                return 'critical'

    def _trigger_alert(
        self,
        metric: Any,
        value: float,
        status: str
    ) -> None:
        """触发告警"""
        logger.warning(
            f"[ALERT] {metric.display_name} ({metric.name}): {value} "
            f"- Status: {status.upper()}"
        )
        # TODO: 集成飞书/Slack通知

    def run_evaluation(
        self,
        current_metrics: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        运行完整评估流程
        
        Args:
            current_metrics: 当前指标值
            
        Returns:
            评估报告
        """
        # 1. 记录当前指标
        self.record_metrics(current_metrics)
        
        # 2. 生成优化建议
        suggestions = self.framework.generate_optimization_report(current_metrics)
        
        # 3. 执行优化（如启用）
        optimization_results = []
        if self.auto_optimization_enabled and suggestions:
            optimization_results = self.optimizer.optimize_all(current_metrics)
        
        # 4. 计算综合评分
        comprehensive_score, dimension_scores = self.framework.calculate_comprehensive_score(current_metrics)
        
        # 5. 生成报告
        report = {
            'timestamp': datetime.now().isoformat(),
            'comprehensive_score': comprehensive_score,
            'dimension_scores': dimension_scores,
            'current_metrics': current_metrics,
            'optimization_suggestions': suggestions,
            'optimization_results': [
                {
                    'metric': r.metric_name,
                    'improvement': r.improvement,
                    'success': r.success
                }
                for r in optimization_results
            ],
            'auto_optimization_enabled': self.auto_optimization_enabled
        }
        
        return report

    def generate_dashboard_data(
        self,
        metrics_values: Dict[str, float]
    ) -> Dict[str, Any]:
        """
        生成监控看板数据
        
        Args:
            metrics_values: 当前指标值
            
        Returns:
            看板数据
        """
        dashboard = {
            'timestamp': datetime.now().isoformat(),
            'overall_health': 'healthy',
            'metrics': {},
            'trends': {},
            'alerts': []
        }
        
        for metric_name, value in metrics_values.items():
            metric = self.framework.get_metric_by_name(metric_name)
            if not metric:
                continue
            
            status = self._evaluate_metric_status(metric, value)
            
            # 更新overall_health
            if status == 'critical':
                dashboard['overall_health'] = 'critical'
            elif status == 'warning' and dashboard['overall_health'] != 'critical':
                dashboard['overall_health'] = 'warning'
            
            dashboard['metrics'][metric_name] = {
                'display_name': metric.display_name,
                'value': value,
                'target': metric.target,
                'status': status,
                'category': metric.category.value,
                'level': metric.level.value,
                'weight': metric.weight
            }
            
            # 添加告警
            if status in ['warning', 'critical']:
                dashboard['alerts'].append({
                    'metric': metric_name,
                    'display_name': metric.display_name,
                    'value': value,
                    'target': metric.target,
                    'status': status,
                    'suggestions': metric.optimization_suggestions[:2]  # 只显示前2个建议
                })
        
        # 计算综合评分
        comprehensive_score, dimension_scores = self.framework.calculate_comprehensive_score(metrics_values)
        dashboard['comprehensive_score'] = comprehensive_score
        dashboard['dimension_scores'] = dimension_scores
        
        return dashboard

    def enable_auto_optimization(self) -> None:
        """启用自动优化"""
        self.auto_optimization_enabled = True
        logger.info("自动优化已启用")

    def disable_auto_optimization(self) -> None:
        """禁用自动优化"""
        self.auto_optimization_enabled = False
        logger.info("自动优化已禁用")

    def get_metric_trends(
        self,
        metric_name: str,
        hours: int = 24
    ) -> List[Dict[str, Any]]:
        """
        获取指标趋势
        
        Args:
            metric_name: 指标名称
            hours: 时间范围（小时）
            
        Returns:
            趋势数据列表
        """
        cutoff_time = time.time() - (hours * 3600)
        
        trends = [
            {
                'timestamp': s.timestamp,
                'value': s.value,
                'status': s.status
            }
            for s in self.history
            if s.metric_name == metric_name and s.timestamp >= cutoff_time
        ]
        
        return sorted(trends, key=lambda x: x['timestamp'])

    def export_metrics_json(self) -> str:
        """导出指标数据为JSON"""
        import json
        return json.dumps({
            'history': [
                {
                    'timestamp': s.timestamp,
                    'metric_name': s.metric_name,
                    'value': s.value,
                    'status': s.status
                }
                for s in self.history
            ]
        }, indent=2)


# 全局实例
_pipeline = None

def get_evaluation_pipeline() -> EvaluationPipeline:
    """获取评估管道实例"""
    global _pipeline
    if _pipeline is None:
        _pipeline = EvaluationPipeline()
    return _pipeline
