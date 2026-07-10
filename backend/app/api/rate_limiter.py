"""API 限流中间件——防止恶意调用"""
from functools import wraps
import time
from flask import request, jsonify
import logging

logger = logging.getLogger(__name__)


class RateLimiter:
    """基于 IP 的滑动窗口限流"""

    def __init__(self, max_requests: int = 10, window: int = 60):
        """
        Args:
            max_requests: 时间窗口内最大请求数
            window: 时间窗口（秒）
        """
        self.max_requests = max_requests
        self.window = window
        self._requests: dict[str, list[float]] = {}

    def _cleanup(self, ip: str) -> None:
        """清理过期的请求记录"""
        now = time.time()
        if ip in self._requests:
            self._requests[ip] = [
                t for t in self._requests[ip] if now - t < self.window
            ]

    def is_rate_limited(self, ip: str) -> bool:
        """检查是否触发限流"""
        self._cleanup(ip)
        return len(self._requests.get(ip, [])) >= self.max_requests

    def record_request(self, ip: str) -> None:
        """记录一次请求"""
        if ip not in self._requests:
            self._requests[ip] = []
        self._requests[ip].append(time.time())

    def __call__(self, f):
        """装饰器使用"""
        @wraps(f)
        def decorated(*args, **kwargs):
            ip = request.remote_addr or 'unknown'

            if self.is_rate_limited(ip):
                logger.warning(f"Rate limit triggered for IP: {ip}")
                return jsonify({
                    'success': False,
                    'error': {
                        'code': 'RATE_LIMITED',
                        'message': '请求过于频繁，请稍后再试'
                    }
                }), 429

            self.record_request(ip)
            return f(*args, **kwargs)

        return decorated


# 预设的限流策略
rate_limit_question = RateLimiter(max_requests=5, window=60)    # 问答：5次/分钟
rate_limit_upload = RateLimiter(max_requests=3, window=60)      # 上传：3次/分钟
rate_limit_general = RateLimiter(max_requests=30, window=60)    # 其他：30次/分钟
