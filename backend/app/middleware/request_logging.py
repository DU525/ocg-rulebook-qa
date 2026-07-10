"""
Request logging middleware for structured HTTP request logging.

Features:
- Logs method, path, query_params, status_code, latency, trace_id for each request
- Slow request detection (>1000ms marked as WARNING)
- Integration with trace_id from existing trace system
- JSON structured output
- Slow query recording to SlowQueryAnalyzer for analysis
"""

import logging
import time
from flask import Flask, request, g

from app.core.logging_config import get_logger, filter_sensitive
from app.services.slow_query_analyzer import SlowQueryAnalyzer

logger = get_logger("app.middleware.request_logging")

SLOW_REQUEST_THRESHOLD_MS = 1000

_slow_query_analyzer = None


def get_slow_query_analyzer() -> SlowQueryAnalyzer:
    global _slow_query_analyzer
    if _slow_query_analyzer is None:
        _slow_query_analyzer = SlowQueryAnalyzer()
    return _slow_query_analyzer


class RequestLoggingMiddleware:
    """Middleware that logs every HTTP request with structured JSON format."""

    def __init__(self, app: Flask, slow_threshold_ms: int = SLOW_REQUEST_THRESHOLD_MS):
        self.app = app
        self.slow_threshold_ms = slow_threshold_ms
        self._register_hooks()

    def _register_hooks(self):
        @self.app.before_request
        def before_request_log():
            g.request_start_time = time.time()

        @self.app.after_request
        def after_request_log(response):
            elapsed_ms = 0
            start_time = getattr(g, "request_start_time", None)
            if start_time is not None:
                elapsed_ms = int((time.time() - start_time) * 1000)

            trace_id = getattr(g, "trace_id", "") or ""

            query_params = request.query_string.decode("utf-8", errors="replace")
            if query_params:
                query_params = filter_sensitive(query_params)

            log_data = {
                "method": request.method,
                "path": request.path,
                "query_params": query_params,
                "status_code": response.status_code,
                "latency": elapsed_ms,
                "trace_id": trace_id,
                "remote_addr": request.remote_addr,
                "user_agent": request.headers.get("User-Agent", ""),
            }

            is_slow = elapsed_ms > self.slow_threshold_ms
            if is_slow:
                logger.warning(
                    f"Slow request: {request.method} {request.path} took {elapsed_ms}ms",
                    extra={
                        "extra_fields": log_data,
                        "latency": elapsed_ms,
                        "trace_id": trace_id,
                    },
                )
                analyzer = get_slow_query_analyzer()
                params_dict = {}
                if request.args:
                    params_dict["query_params"] = dict(request.args)
                if request.is_json:
                    params_dict["json_body"] = request.get_json(silent=True)
                analyzer.record_slow_query(
                    trace_id=trace_id,
                    method=request.method,
                    path=request.path,
                    latency=elapsed_ms,
                    params=params_dict,
                )
            else:
                logger.info(
                    f"{request.method} {request.path} {response.status_code} {elapsed_ms}ms",
                    extra={
                        "extra_fields": log_data,
                        "latency": elapsed_ms,
                        "trace_id": trace_id,
                    },
                )

            return response


def init_request_logging(app: Flask, slow_threshold_ms: int = SLOW_REQUEST_THRESHOLD_MS) -> RequestLoggingMiddleware:
    """Initialize request logging middleware on the Flask app."""
    return RequestLoggingMiddleware(app, slow_threshold_ms)
