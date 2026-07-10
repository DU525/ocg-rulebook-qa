"""Tool Executor——统一工具调用、超时控制、错误处理与重试"""
import time
import logging
import threading
from typing import Any, Dict, Optional, Callable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 5.0
DEFAULT_MAX_RETRIES = 2


@dataclass
class ToolCallResult:
    """工具调用结果"""
    tool_name: str
    success: bool
    result: Any = None
    error: Optional[str] = None
    execution_time: float = 0.0
    retries: int = 0
    timed_out: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "tool_name": self.tool_name,
            "success": self.success,
            "result": self.result,
            "error": self.error,
            "execution_time": round(self.execution_time, 4),
            "retries": self.retries,
            "timed_out": self.timed_out,
        }


class TimeoutError(Exception):
    """工具执行超时异常"""
    pass


def _run_with_timeout(func: Callable, timeout: float, **kwargs) -> Any:
    """在超时限制内执行函数

    使用 threading 实现超时控制。
    """
    result_container = {"done": False, "result": None, "exception": None}

    def target():
        try:
            result_container["result"] = func(**kwargs)
            result_container["done"] = True
        except Exception as e:
            result_container["exception"] = e
            result_container["done"] = True

    thread = threading.Thread(target=target, daemon=True)
    thread.start()
    thread.join(timeout=timeout)

    if not result_container["done"]:
        raise TimeoutError(f"Tool execution timed out after {timeout} seconds")

    if result_container["exception"] is not None:
        raise result_container["exception"]

    return result_container["result"]


class ToolExecutor:
    """统一工具调用执行器

    特性：
    - 超时控制（默认 5 秒）
    - 错误处理与自动重试
    - 执行时间统计
    """

    def __init__(
        self,
        tool_registry=None,
        timeout: float = DEFAULT_TIMEOUT,
        max_retries: int = DEFAULT_MAX_RETRIES,
    ):
        self._tool_registry = tool_registry
        self._timeout = timeout
        self._max_retries = max_retries

    @property
    def timeout(self) -> float:
        return self._timeout

    @timeout.setter
    def timeout(self, value: float):
        self._timeout = max(0.1, value)

    @property
    def max_retries(self) -> int:
        return self._max_retries

    @max_retries.setter
    def max_retries(self, value: int):
        self._max_retries = max(0, value)

    def execute(self, tool_name: str, **kwargs) -> ToolCallResult:
        """执行指定工具，带超时控制和重试

        Args:
            tool_name: 工具名称
            **kwargs: 传递给工具的参数

        Returns:
            ToolCallResult: 执行结果
        """
        if self._tool_registry is None:
            return ToolCallResult(
                tool_name=tool_name,
                success=False,
                error="ToolRegistry is not initialized",
            )

        if not self._tool_registry.has_tool(tool_name):
            available = list(self._tool_registry._tools.keys())
            return ToolCallResult(
                tool_name=tool_name,
                success=False,
                error=f"Tool not found: {tool_name}. Available: {available}",
            )

        last_error = None
        total_retries = 0

        for attempt in range(self._max_retries + 1):
            start_time = time.time()
            try:
                result = _run_with_timeout(
                    self._tool_registry.execute,
                    self._timeout,
                    tool_name=tool_name,
                    **kwargs,
                )
                execution_time = time.time() - start_time

                logger.info(
                    f"Tool '{tool_name}' executed successfully "
                    f"in {execution_time:.3f}s (attempt {attempt + 1})"
                )

                return ToolCallResult(
                    tool_name=tool_name,
                    success=True,
                    result=result,
                    execution_time=execution_time,
                    retries=total_retries,
                )

            except TimeoutError as e:
                execution_time = time.time() - start_time
                total_retries = attempt
                last_error = str(e)

                logger.warning(
                    f"Tool '{tool_name}' timed out after {execution_time:.3f}s "
                    f"(attempt {attempt + 1}/{self._max_retries + 1})"
                )

                if attempt < self._max_retries:
                    continue

                return ToolCallResult(
                    tool_name=tool_name,
                    success=False,
                    error=last_error,
                    execution_time=execution_time,
                    retries=total_retries,
                    timed_out=True,
                )

            except Exception as e:
                execution_time = time.time() - start_time
                total_retries = attempt
                last_error = str(e)

                logger.warning(
                    f"Tool '{tool_name}' failed: {e} "
                    f"(attempt {attempt + 1}/{self._max_retries + 1})"
                )

                if attempt < self._max_retries:
                    continue

                return ToolCallResult(
                    tool_name=tool_name,
                    success=False,
                    error=last_error,
                    execution_time=execution_time,
                    retries=total_retries,
                )

        return ToolCallResult(
            tool_name=tool_name,
            success=False,
            error=last_error or "Unknown error",
            retries=total_retries,
        )

    def execute_batch(self, calls: list) -> list:
        """批量执行工具调用

        Args:
            calls: 列表，每项为 {"tool_name": str, **kwargs}

        Returns:
            list[ToolCallResult]: 执行结果列表
        """
        results = []
        for call in calls:
            tool_name = call.pop("tool_name", "")
            result = self.execute(tool_name, **call)
            results.append(result)
        return results

    def get_stats(self) -> Dict[str, Any]:
        """获取执行器配置信息"""
        return {
            "timeout": self._timeout,
            "max_retries": self._max_retries,
            "tool_count": self._tool_registry.tool_count if self._tool_registry else 0,
        }


def create_executor(tool_registry=None, timeout: float = DEFAULT_TIMEOUT, max_retries: int = DEFAULT_MAX_RETRIES) -> ToolExecutor:
    """创建 ToolExecutor 实例"""
    return ToolExecutor(
        tool_registry=tool_registry,
        timeout=timeout,
        max_retries=max_retries,
    )
