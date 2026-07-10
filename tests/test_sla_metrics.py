"""
SLA 监控系统 - 单元测试

测试内容:
- Prometheus 指标定义和采集
- SLOCalculator 各项计算逻辑
- SLAMetricsCollector 单例模式
- SLAMiddleware Flask 集成
"""
import sys
import os
import time
import pytest
from unittest.mock import MagicMock, patch

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))


class TestSLAMetricsCollector:
    @pytest.fixture(autouse=True)
    def reset_singleton(self):
        from app.core.sla_metrics import SLAMetricsCollector
        SLAMetricsCollector._instance = None
        yield
        SLAMetricsCollector._instance = None

    def test_singleton_pattern(self):
        from app.core.sla_metrics import SLAMetricsCollector
        c1 = SLAMetricsCollector()
        c2 = SLAMetricsCollector()
        assert c1 is c2

    def test_record_request(self):
        from app.core.sla_metrics import SLAMetricsCollector, sla_request_total
        collector = SLAMetricsCollector()
        collector.record_request('GET', '/api/query', 200)
        collector.record_request('POST', '/api/query', 201)
        collector.record_request('GET', '/api/query', 500)

        metrics = sla_request_total._metrics
        total = sum(m._value.get() for m in metrics.values())
        assert total == 3

    def test_record_latency(self):
        from app.core.sla_metrics import SLAMetricsCollector, sla_latency_seconds
        collector = SLAMetricsCollector()
        collector.record_latency('GET', '/api/query', 0.5)
        collector.record_latency('GET', '/api/query', 1.2)
        collector.record_latency('GET', '/api/query', 0.1)

        assert len(collector._latency_history) == 3

    def test_record_error(self):
        from app.core.sla_metrics import SLAMetricsCollector, sla_error_total
        collector = SLAMetricsCollector()
        collector.record_error('server_error', '/api/query')
        collector.record_error('client_error', '/api/query')

        assert len(collector._error_history) == 2

