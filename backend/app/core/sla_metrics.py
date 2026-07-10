"""
SLA 监控系统 - Prometheus 指标和 SLO 计算器

提供 SLO 指标定义、采集和计算功能，支持:
- 请求量、延迟、错误率、RAGAS评分、缓存命中率等核心指标
- SLO 达标率计算（可用性、延迟、错误率）
- SLO 看板数据聚合
"""
import time
import math
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, field
from collections import defaultdict
from prometheus_client import Counter, Histogram, Gauge, CollectorRegistry


SLO_REGISTRY = CollectorRegistry()

sla_request_total = Counter(
    'sla_request_total',
    'Total number of requests',
    ['method', 'endpoint', 'status'],
    registry=SLO_REGISTRY,
)

sla_latency_seconds = Histogram(
    'sla_latency_seconds',
    'Request latency in seconds',
    ['method', 'endpoint'],
    buckets=[0.1, 0.5, 1, 2, 5, 10],
    registry=SLO_REGISTRY,
)

sla_error_total = Counter(
    'sla_error_total',
    'Total number of errors',
    ['error_type', 'endpoint'],
    registry=SLO_REGISTRY,
)

sla_ragas_score = Gauge(
    'sla_ragas_score',
    'RAGAS evaluation score',
    ['metric_name'],
    registry=SLO_REGISTRY,
)

sla_cache_hit_total = Counter(
    'sla_cache_hit_total',
    'Total number of cache hits/misses',
    ['result'],
    registry=SLO_REGISTRY,
)


@dataclass
class SLOMetricPoint:
    timestamp: float
    value: float
    labels: Dict[str, str] = field(default_factory=dict)


class SLAMetricsCollector:
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
        self._latency_history: List[SLOMetricPoint] = []
        self._error_history: List[SLOMetricPoint] = []
        self._availability_window: Dict[float, bool] = {}
        self._max_history_size = 100000

    def record_request(self, method: str, endpoint: str, status: int):
        status_str = str(status)
        sla_request_total.labels(method=method, endpoint=endpoint, status=status_str).inc()
        is_success = 200 <= status < 500
        self._availability_window[time.time()] = is_success
        self._cleanup_old_records(window_hours=24)

    def record_latency(self, method: str, endpoint: str, duration_seconds: float):
        sla_latency_seconds.labels(method=method, endpoint=endpoint).observe(duration_seconds)
        self._latency_history.append(SLOMetricPoint(
            timestamp=time.time(),
            value=duration_seconds,
            labels={'method': method, 'endpoint': endpoint},
        ))
        if len(self._latency_history) > self._max_history_size:
            self._latency_history = self._latency_history[-self._max_history_size:]

    def record_error(self, error_type: str, endpoint: str):
        sla_error_total.labels(error_type=error_type, endpoint=endpoint).inc()
        self._error_history.append(SLOMetricPoint(
            timestamp=time.time(),
            value=1.0,
            labels={'error_type': error_type, 'endpoint': endpoint},
        ))
        if len(self._error_history) > self._max_history_size:
            self._error_history = self._error_history[-self._max_history_size:]

    def record_ragas_score(self, metric_name: str, score: float):
        sla_ragas_score.labels(metric_name=metric_name).set(score)

    def record_cache_result(self, hit: bool):
        result_label = 'hit' if hit else 'miss'
        sla_cache_hit_total.labels(result=result_label).inc()

    def get_latency_samples(self, window_hours: float = 24) -> List[float]:
        cutoff = time.time() - (window_hours * 3600)
        return [p.value for p in self._latency_history if p.timestamp >= cutoff]

    def get_error_count(self, window_hours: float = 24) -> int:
        cutoff = time.time() - (window_hours * 3600)
        return sum(1 for p in self._error_history if p.timestamp >= cutoff)

    def get_request_count(self, window_hours: float = 24) -> int:
        cutoff = time.time() - (window_hours * 3600)
        return sum(1 for v in self._availability_window.values() if v is not None)

    def _cleanup_old_records(self, window_hours: float = 24):
        cutoff = time.time() - (window_hours * 3600)
        self._availability_window = {
            ts: val for ts, val in self._availability_window.items() if ts >= cutoff
        }

    def get_cache_hit_rate(self) -> float:
        samples = sla_cache_hit_total._metrics
        hit_count = 0
        miss_count = 0
        for labels, metric in samples.items():
            result_label = labels.get('result', '')
            value = metric._value.get()
            if result_label == 'hit':
                hit_count = value
            elif result_label == 'miss':
                miss_count = value
        total = hit_count + miss_count
        if total == 0:
            return 0.0
        return hit_count / total


class SLOCalculator:
    DEFAULT_AVAILABILITY_TARGET = 0.999
    DEFAULT_P99_THRESHOLD_MS = 2000

    def __init__(self, collector: Optional[SLAMetricsCollector] = None):
        self.collector = collector or SLAMetricsCollector()

    def calculate_availability(self, window_hours: float = 24) -> Dict[str, Any]:
        total_requests = 0
        successful_requests = 0
        cutoff = time.time() - (window_hours * 3600)

        samples = sla_request_total._metrics
        for labels, metric in samples.items():
            status_str = labels.get('status', '0')
            try:
                status_code = int(status_str)
            except ValueError:
                continue
            count = metric._value.get()
            total_requests += count
            if 200 <= status_code < 500:
                successful_requests += count

        if total_requests == 0:
            availability = 1.0
        else:
            availability = successful_requests / total_requests

        target = self.DEFAULT_AVAILABILITY_TARGET
        met = availability >= target

        return {
            'availability': round(availability, 6),
            'target': target,
            'met': met,
            'total_requests': total_requests,
            'successful_requests': successful_requests,
            'failed_requests': total_requests - successful_requests,
            'window_hours': window_hours,
        }

    def calculate_latency_slo(self, p99_threshold_ms: float = 2000) -> Dict[str, Any]:
        samples = self.collector.get_latency_samples(window_hours=24)

        if not samples:
            return {
                'p50_ms': 0,
                'p95_ms': 0,
                'p99_ms': 0,
                'threshold_ms': p99_threshold_ms,
                'compliance_rate': 1.0,
                'met': True,
                'total_samples': 0,
            }

        sorted_samples = sorted(samples)
        n = len(sorted_samples)

        p50 = sorted_samples[int(n * 0.50)] * 1000
        p95 = sorted_samples[int(n * 0.95)] * 1000
        p99 = sorted_samples[int(n * 0.99)] * 1000

        threshold_seconds = p99_threshold_ms / 1000.0
        compliant = sum(1 for s in sorted_samples if s <= threshold_seconds)
        compliance_rate = compliant / n if n > 0 else 1.0

        met = p99 <= p99_threshold_ms

        return {
            'p50_ms': round(p50, 2),
            'p95_ms': round(p95, 2),
            'p99_ms': round(p99, 2),
            'threshold_ms': p99_threshold_ms,
            'compliance_rate': round(compliance_rate, 4),
            'met': met,
            'total_samples': n,
        }

    def calculate_error_rate(self, window_hours: float = 24) -> Dict[str, Any]:
        total_requests = 0
        samples = sla_request_total._metrics
        for labels, metric in samples.items():
            total_requests += metric._value.get()

        error_count = self.collector.get_error_count(window_hours=window_hours)

        if total_requests == 0:
            error_rate = 0.0
        else:
            error_rate = error_count / total_requests

        error_rate_target = 0.001
        met = error_rate <= error_rate_target

        error_by_type: Dict[str, int] = defaultdict(int)
        for point in self.collector._error_history:
            cutoff = time.time() - (window_hours * 3600)
            if point.timestamp >= cutoff:
                error_type = point.labels.get('error_type', 'unknown')
                error_by_type[error_type] += 1

        return {
            'error_rate': round(error_rate, 6),
            'target': error_rate_target,
            'met': met,
            'total_errors': error_count,
            'total_requests': total_requests,
            'errors_by_type': dict(error_by_type),
            'window_hours': window_hours,
        }

    def get_slo_dashboard_data(self) -> Dict[str, Any]:
        availability = self.calculate_availability()
        latency = self.calculate_latency_slo()
        error_rate = self.calculate_error_rate()
        cache_hit_rate = self.collector.get_cache_hit_rate()

        ragas_metrics = {}
        ragas_samples = sla_ragas_score._metrics
        for labels, metric in ragas_samples.items():
            metric_name = labels.get('metric_name', 'unknown')
            ragas_metrics[metric_name] = metric._value.get()

        overall_slo_met = (
            availability['met']
            and latency['met']
            and error_rate['met']
        )

        slo_score = self._calculate_slo_score(
            availability['availability'],
            latency['compliance_rate'],
            1 - error_rate['error_rate'],
        )

        return {
            'overall_met': overall_slo_met,
            'slo_score': round(slo_score, 4),
            'availability': availability,
            'latency': latency,
            'error_rate': error_rate,
            'cache_hit_rate': round(cache_hit_rate, 4),
            'ragas_scores': ragas_metrics,
            'timestamp': time.time(),
        }

    @staticmethod
    def _calculate_slo_score(
        availability: float,
        latency_compliance: float,
        success_rate: float,
    ) -> float:
        weights = {
            'availability': 0.4,
            'latency': 0.3,
            'success_rate': 0.3,
        }
        score = (
            weights['availability'] * availability
            + weights['latency'] * latency_compliance
            + weights['success_rate'] * success_rate
        )
        return min(max(score, 0.0), 1.0)


class SLAMiddleware:
    def __init__(self, app=None):
        self.collector = SLAMetricsCollector()
        if app is not None:
            self.init_app(app)

    def init_app(self, app):
        @app.before_request
        def _before_request():
            from flask import request
            request._sla_start_time = time.time()

        @app.after_request
        def _after_request(response):
            from flask import request
            duration = time.time() - getattr(request, '_sla_start_time', time.time())
            method = request.method
            endpoint = request.path
            status = response.status_code

            self.collector.record_request(method, endpoint, status)
            self.collector.record_latency(method, endpoint, duration)

            if status >= 400:
                error_type = 'client_error' if status < 500 else 'server_error'
                self.collector.record_error(error_type, endpoint)

            return response
