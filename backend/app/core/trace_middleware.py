from flask import Flask, request, g
import logging
import time

from app.core.trace import generate_trace_id, set_trace_id, clear_trace

logger = logging.getLogger(__name__)


class TraceMiddleware:
    def __init__(self, app: Flask):
        self.app = app
        self._register_hooks()

    def _register_hooks(self):
        @self.app.before_request
        def before_request_trace():
            trace_id = request.headers.get('X-Trace-ID', '').strip()
            if not trace_id:
                trace_id = generate_trace_id()

            token = set_trace_id(trace_id)
            g.trace_id = trace_id
            g._trace_token = token
            g.request_start_time = time.time()

            logger.info(f"[TRACE:{trace_id}] >>> {request.method} {request.path}")

        @self.app.after_request
        def after_request_trace(response):
            trace_id = getattr(g, 'trace_id', None)
            if trace_id:
                response.headers['X-Trace-ID'] = trace_id

                elapsed_ms = 0
                start_time = getattr(g, 'request_start_time', None)
                if start_time is not None:
                    elapsed_ms = int((time.time() - start_time) * 1000)

                logger.info(f"[TRACE:{trace_id}] <<< {response.status_code} {elapsed_ms}ms")

            return response

        @self.app.teardown_request
        def teardown_request_trace(exception=None):
            token = getattr(g, '_trace_token', None)
            if token is not None:
                clear_trace(token)


def init_trace_middleware(app: Flask) -> TraceMiddleware:
    return TraceMiddleware(app)
