import uuid
import contextvars
import asyncio

trace_id_var: contextvars.ContextVar[str] = contextvars.ContextVar('trace_id', default='')


def generate_trace_id() -> str:
    return str(uuid.uuid4())


def get_current_trace() -> str:
    return trace_id_var.get()


def set_trace_id(trace_id: str) -> contextvars.Token:
    return trace_id_var.set(trace_id)


def clear_trace(token: contextvars.Token | None = None) -> None:
    if token is not None:
        trace_id_var.reset(token)
    else:
        trace_id_var.set('')


class TraceContext:
    def __init__(self, trace_id: str | None = None):
        self.trace_id = trace_id or generate_trace_id()
        self._token: contextvars.Token | None = None

    def __enter__(self) -> str:
        self._token = set_trace_id(self.trace_id)
        return self.trace_id

    def __exit__(self, exc_type, exc_val, exc_tb):
        clear_trace(self._token)
        return False

    def __str__(self) -> str:
        return self.trace_id


async def propagate_trace_to_async(trace_id: str, coro):
    token = set_trace_id(trace_id)
    try:
        return await coro
    finally:
        clear_trace(token)
