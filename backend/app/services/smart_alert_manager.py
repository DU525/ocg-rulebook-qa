"""
智能告警管理器 - Prometheus 指标告警 + 飞书通知
功能：
- 阈值告警（延迟过高、错误率异常、缓存命中率低）
- 告警去重（避免重复告警）
- 告警级别自动升级
- 自动恢复通知
"""
import time
import logging
from typing import Dict, Any, List, Optional
from dataclasses import dataclass, field
from collections import defaultdict
from app.core.sla_metrics import SLAMetricsCollector, SLOCalculator
from app.services.feishu_notifier import send_alert

logger = logging.getLogger(__name__)


@dataclass
class AlertRule:
    """告警规则配置"""
    name: str
    metric: str
    threshold: float
    operator: str  # 'gt', 'lt', 'ge', 'le'
    level: str  # 'info', 'warning', 'error', 'critical'
    cooldown_seconds: int = 300  # 5分钟冷却
    description: str = ""


@dataclass
class ActiveAlert:
    """活跃告警记录"""
    rule: AlertRule
    value: float
    first_triggered: float
    last_triggered: float
    trigger_count: int = 1
    acknowledged: bool = False
    resolved: bool = False


class SmartAlertManager:
    """智能告警管理器"""

    DEFAULT_RULES = [
        AlertRule(
            name="高延迟告警",
            metric="p99_latency",
            threshold=5000,
            operator="gt",
            level="warning",
            cooldown_seconds=600,
            description="P99 延迟超过 5 秒",
        ),
        AlertRule(
            name="严重延迟告警",
            metric="p99_latency",
            threshold=10000,
            operator="gt",
            level="critical",
            cooldown_seconds=300,
            description="P99 延迟超过 10 秒",
        ),
        AlertRule(
            name="高错误率告警",
            metric="error_rate",
            threshold=0.01,
            operator="gt",
            level="warning",
            cooldown_seconds=600,
            description="错误率超过 1%",
        ),
        AlertRule(
            name="严重错误率告警",
            metric="error_rate",
            threshold=0.05,
            operator="gt",
            level="critical",
            cooldown_seconds=300,
            description="错误率超过 5%",
        ),
        AlertRule(
            name="低缓存命中率告警",
            metric="cache_hit_rate",
            threshold=0.5,
            operator="lt",
            level="warning",
            cooldown_seconds=1800,
            description="缓存命中率低于 50%",
        ),
        AlertRule(
            name="低可用性告警",
            metric="availability",
            threshold=0.99,
            operator="lt",
            level="error",
            cooldown_seconds=600,
            description="可用性低于 99%",
        ),
    ]

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
        self.rules: List[AlertRule] = self.DEFAULT_RULES.copy()
        self.active_alerts: Dict[str, ActiveAlert] = {}
        self.last_alert_time: Dict[str, float] = {}
        self.slo_collector = SLAMetricsCollector()
        self.slo_calculator = SLOCalculator()
        logger.info("智能告警管理器初始化完成")

    def add_rule(self, rule: AlertRule) -> None:
        """添加自定义告警规则"""
        self.rules.append(rule)
        logger.info(f"添加告警规则: {rule.name}")

    def check_alerts(self) -> List[ActiveAlert]:
        """检查所有告警规则，返回当前触发的告警"""
        triggered = []
        current_time = time.time()

        # 获取当前指标
        slo_data = self.slo_calculator.get_slo_dashboard_data()
        metrics = {
            "p99_latency": slo_data["latency"]["p99_ms"],
            "error_rate": slo_data["error_rate"]["error_rate"],
            "availability": slo_data["availability"]["availability"],
            "cache_hit_rate": slo_data["cache_hit_rate"],
        }

        for rule in self.rules:
            value = metrics.get(rule.metric)
            if value is None:
                continue

            if self._evaluate_rule(rule, value):
                alert_key = f"{rule.name}_{rule.metric}"
                last_time = self.last_alert_time.get(alert_key, 0)

                # 检查冷却时间
                if current_time - last_time >= rule.cooldown_seconds:
                    alert = self._record_alert(rule, value, current_time)
                    triggered.append(alert)
                    self.last_alert_time[alert_key] = current_time

                    # 发送通知
                    self._send_alert_notification(alert)

        # 检查恢复的告警
        self._check_resolved(metrics, current_time)

        return triggered

    def _evaluate_rule(self, rule: AlertRule, value: float) -> bool:
        """评估告警规则是否触发"""
        if rule.operator == "gt":
            return value > rule.threshold
        elif rule.operator == "lt":
            return value < rule.threshold
        elif rule.operator == "ge":
            return value >= rule.threshold
        elif rule.operator == "le":
            return value <= rule.threshold
        return False

    def _record_alert(self, rule: AlertRule, value: float, timestamp: float) -> ActiveAlert:
        """记录告警事件"""
        alert_key = f"{rule.name}_{rule.metric}"

        if alert_key in self.active_alerts:
            alert = self.active_alerts[alert_key]
            alert.last_triggered = timestamp
            alert.trigger_count += 1
            alert.value = value
        else:
            alert = ActiveAlert(
                rule=rule,
                value=value,
                first_triggered=timestamp,
                last_triggered=timestamp,
            )
            self.active_alerts[alert_key] = alert

        logger.warning(f"告警触发: {rule.name}, 当前值: {value}, 阈值: {rule.threshold}")
        return alert

    def _check_resolved(self, metrics: Dict[str, float], timestamp: float) -> None:
        """检查是否有告警恢复"""
        resolved_keys = []

        for alert_key, alert in self.active_alerts.items():
            if alert.resolved:
                continue

            value = metrics.get(alert.rule.metric)
            if value is None:
                continue

            # 检查是否恢复（不再满足触发条件）
            if not self._evaluate_rule(alert.rule, value):
                alert.resolved = True
                resolved_keys.append(alert_key)
                self._send_resolved_notification(alert)
                logger.info(f"告警恢复: {alert.rule.name}")

        # 清理已恢复的告警（保留 24 小时）
        for key in list(self.active_alerts.keys()):
            alert = self.active_alerts[key]
            if alert.resolved and (timestamp - alert.last_triggered) > 86400:
                del self.active_alerts[key]

    def _send_alert_notification(self, alert: ActiveAlert) -> None:
        """发送告警通知到飞书"""
        level_emoji = {
            "info": "ℹ️",
            "warning": "⚠️",
            "error": "❌",
            "critical": "🔥",
        }

        level_label = {
            "info": "信息",
            "warning": "警告",
            "error": "错误",
            "critical": "严重",
        }

        emoji = level_emoji.get(alert.rule.level, "ℹ️")
        level_name = level_label.get(alert.rule.level, "未知")

        title = f"{emoji} {level_name}: {alert.rule.name}"
        content = f"""
**告警类型**: {alert.rule.description}
**当前值**: {alert.value:.4f}
**阈值**: {alert.rule.operator} {alert.rule.threshold}
**触发次数**: {alert.trigger_count}
**首次触发**: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(alert.first_triggered))}
**最后触发**: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(alert.last_triggered))}
"""
        try:
            send_alert(title, content, priority=alert.rule.level)
        except Exception as e:
            logger.error(f"发送告警通知失败: {e}")

    def _send_resolved_notification(self, alert: ActiveAlert) -> None:
        """发送恢复通知到飞书"""
        title = f"✅ 恢复: {alert.rule.name}"
        content = f"""
**告警已恢复**: {alert.rule.description}
**持续时间**: {(alert.last_triggered - alert.first_triggered) / 60:.1f} 分钟
**触发次数**: {alert.trigger_count}
**恢复时间**: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(time.time()))}
"""
        try:
            send_alert(title, content, priority="info")
        except Exception as e:
            logger.error(f"发送恢复通知失败: {e}")

    def get_active_alerts(self) -> List[Dict[str, Any]]:
        """获取所有活跃告警"""
        return [
            {
                "name": a.rule.name,
                "level": a.rule.level,
                "value": a.value,
                "threshold": a.rule.threshold,
                "trigger_count": a.trigger_count,
                "first_triggered": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(a.first_triggered)),
                "last_triggered": time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(a.last_triggered)),
                "acknowledged": a.acknowledged,
                "resolved": a.resolved,
            }
            for a in self.active_alerts.values()
        ]

    def acknowledge_alert(self, alert_name: str) -> bool:
        """确认告警"""
        for alert in self.active_alerts.values():
            if alert.rule.name == alert_name and not alert.resolved:
                alert.acknowledged = True
                logger.info(f"告警已确认: {alert_name}")
                return True
        return False


def get_alert_manager() -> SmartAlertManager:
    """获取告警管理器单例"""
    return SmartAlertManager()

