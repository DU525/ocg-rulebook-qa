"""Tool System - 标准化工具系统
提供统一工具Schema定义、工具自动发现与注册、工具调用链路追踪、工具测试框架
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import (
    Dict,
    Any,
    Callable,
    List,
    Optional,
    Type,
    TypeVar,
    Generic,
    Union,
    Literal,
    Set,
)
from enum import Enum
import logging
import time
import uuid
import inspect
from datetime import datetime
from collections import deque
import json

logger = logging.getLogger(__name__)


class ToolStatus(str, Enum):
    """工具状态枚举"""
    ACTIVE = "active"
    DISABLED = "disabled"
    DEPRECATED = "deprecated"
    ERROR = "error"


@dataclass
class ToolParameter:
    """工具参数定义"""
    name: str
    type: str = "str"
    required: bool = False
    default: Any = None
    description: str = ""
    enum: Optional[List[Any]] = None
    min_value: Optional[float] = None
    max_value: Optional[float] = None


@dataclass
class ToolSchema:
    """统一工具Schema定义"""
    name: str
    description: str
    version: str = "1.0.0"
    category: str = "general"
    parameters: List[ToolParameter] = field(default_factory=list)
    output_description: str = "工具执行结果"
    tags: List[str] = field(default_factory=list)
    status: ToolStatus = ToolStatus.ACTIVE
    author: str = ""
    created_at: str = field(default_factory=lambda: datetime.now().isoformat())
    deprecated_reason: str = ""
    examples: List[Dict[str, Any]] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典"""
        return {
            "name": self.name,
            "description": self.description,
            "version": self.version,
            "category": self.category,
            "parameters": [
                {
                    "name": p.name,
                    "type": p.type,
                    "required": p.required,
                    "default": p.default,
                    "description": p.description,
                    "enum": p.enum,
                    "min_value": p.min_value,
                    "max_value": p.max_value,
                }
                for p in self.parameters
            ],
            "output_description": self.output_description,
            "tags": self.tags,
            "status": self.status.value,
            "author": self.author,
            "created_at": self.created_at,
            "examples": self.examples,
        }

    def validate_input(self, kwargs: Dict[str, Any]) -> List[str]:
        """验证输入参数
        Returns:
            错误信息列表，如果为空表示验证通过
        """
        errors = []
        for param in self.parameters:
            if param.required and param.name not in kwargs:
                errors.append(f"Missing required parameter: {param.name}")
            elif param.name in kwargs:
                value = kwargs[param.name]
                if param.enum is not None and value not in param.enum:
                    errors.append(f"Parameter {param.name} must be one of {param.enum}")
                if param.min_value is not None and isinstance(value, (int, float)):
                    if value < param.min_value:
                        errors.append(f"Parameter {param.name} must be >= {param.min_value}")
                if param.max_value is not None and isinstance(value, (int, float)):
                    if value > param.max_value:
                        errors.append(f"Parameter {param.name} must be <= {param.max_value}")
        return errors


@dataclass
class CallTrace:
    """调用追踪记录"""
    trace_id: str
    tool_name: str
    start_time: float
    end_time: Optional[float] = None
    duration: Optional[float] = None
    success: bool = False
    input_args: Dict[str, Any] = field(default_factory=dict)
    output: Any = None
    error: Optional[str] = None
    timestamp: str = field(default_factory=lambda: datetime.now().isoformat())


T = TypeVar('T')


class BaseTool(ABC, Generic[T]):
    """标准工具基类（新）"""

    @property
    @abstractmethod
    def schema(self) -> ToolSchema:
        """工具Schema定义"""
        pass

    @abstractmethod
    def _execute(self, **kwargs) -> T:
        """实际执行逻辑，子类必须实现"""
        pass

    def execute(self, **kwargs) -> T:
        """执行工具（包含验证）"""
        errors = self.schema.validate_input(kwargs)
        if errors:
            raise ValueError(f"Input validation failed: {', '.join(errors)}")
        if self.schema.status != ToolStatus.ACTIVE:
            raise RuntimeError(f"Tool {self.schema.name} is {self.schema.status.value}")
        return self._execute(**kwargs)

    def to_dict(self) -> Dict[str, Any]:
        """转换为字典表示"""
        return self.schema.to_dict()


class FunctionTool(BaseTool[T]):
    """函数包装工具"""

    def __init__(
        self,
        func: Callable,
        name: str,
        description: str,
        parameters: Optional[List[ToolParameter]] = None,
        version: str = "1.0.0",
        category: str = "general",
        tags: Optional[List[str]] = None,
    ):
        self._func = func
        self._schema = ToolSchema(
            name=name,
            description=description,
            version=version,
            category=category,
            parameters=parameters or [ToolParameter(name="query", type="str", required=True)],
            tags=tags or [],
        )

    @property
    def schema(self) -> ToolSchema:
        return self._schema

    def _execute(self, **kwargs) -> T:
        return self._func(**kwargs)


class ToolTracer:
    """工具调用链路追踪器"""

    def __init__(self, max_history: int = 1000):
        self._traces: deque[CallTrace] = deque(maxlen=max_history)
        self._active_traces: Dict[str, CallTrace] = {}

    def start_trace(self, tool_name: str, input_args: Dict[str, Any]) -> str:
        """开始追踪"""
        trace_id = str(uuid.uuid4())
        trace = CallTrace(
            trace_id=trace_id,
            tool_name=tool_name,
            start_time=time.time(),
            input_args=input_args.copy(),
        )
        self._active_traces[trace_id] = trace
        return trace_id

    def end_trace(self, trace_id: str, output: Any = None, error: Optional[str] = None) -> Optional[CallTrace]:
        """结束追踪"""
        trace = self._active_traces.pop(trace_id, None)
        if not trace:
            return None
        trace.end_time = time.time()
        trace.duration = trace.end_time - trace.start_time
        trace.success = error is None
        trace.output = output
        trace.error = error
        self._traces.append(trace)
        return trace

    def get_traces(
        self,
        tool_name: Optional[str] = None,
        success: Optional[bool] = None,
        limit: int = 100,
    ) -> List[CallTrace]:
        """获取追踪记录"""
        traces = list(self._traces)
        if tool_name:
            traces = [t for t in traces if t.tool_name == tool_name]
        if success is not None:
            traces = [t for t in traces if t.success == success]
        return traces[-limit:]

    def get_statistics(self, tool_name: Optional[str] = None) -> Dict[str, Any]:
        """获取统计信息"""
        traces = list(self._traces)
        if tool_name:
            traces = [t for t in traces if t.tool_name == tool_name]
        if not traces:
            return {"total_calls": 0}
        durations = [t.duration for t in traces if t.duration is not None]
        successful = [t for t in traces if t.success]
        return {
            "total_calls": len(traces),
            "successful_calls": len(successful),
            "failed_calls": len(traces) - len(successful),
            "success_rate": len(successful) / len(traces) if traces else 0,
            "avg_duration": sum(durations) / len(durations) if durations else 0,
            "min_duration": min(durations) if durations else 0,
            "max_duration": max(durations) if durations else 0,
        }


@dataclass
class TestCase:
    """工具测试用例"""
    name: str
    input_args: Dict[str, Any]
    expected_output: Optional[Any] = None
    should_fail: bool = False
    description: str = ""


@dataclass
class TestResult:
    """工具测试结果"""
    case_name: str
    passed: bool
    error: Optional[str] = None
    actual_output: Any = None
    duration: float = 0.0


class ToolTester:
    """工具测试框架"""

    def __init__(self):
        self._test_cases: Dict[str, List[TestCase]] = {}

    def register_test_cases(self, tool_name: str, cases: List[TestCase]) -> None:
        """注册测试用例"""
        self._test_cases[tool_name] = cases

    def test_tool(self, tool: BaseTool, cases: Optional[List[TestCase]] = None) -> List[TestResult]:
        """测试单个工具"""
        test_cases = cases or self._test_cases.get(tool.schema.name, [])
        if not test_cases:
            return []
        results = []
        for case in test_cases:
            start = time.time()
            error = None
            actual_output = None
            try:
                actual_output = tool.execute(**case.input_args)
                if case.should_fail:
                    error = f"Expected to fail but succeeded"
            except Exception as e:
                if not case.should_fail:
                    error = str(e)
            duration = time.time() - start
            passed = error is None
            results.append(TestResult(
                case_name=case.name,
                passed=passed,
                error=error,
                actual_output=actual_output,
                duration=duration,
            ))
        return results

    def run_all_tests(self, registry: 'ToolRegistry') -> Dict[str, List[TestResult]]:
        """运行所有工具的测试"""
        all_results = {}
        for tool_name in registry.list_tool_names():
            tool = registry.get_tool(tool_name)
            if tool:
                all_results[tool_name] = self.test_tool(tool)
        return all_results


class ToolRegistry:
    """标准工具注册中心"""

    def __init__(self, enable_tracing: bool = True):
        self._tools: Dict[str, BaseTool] = {}
        self._categories: Set[str] = set()
        self._tracer = ToolTracer() if enable_tracing else None
        self._tester = ToolTester()
        logger.info("ToolRegistry initialized")

    @property
    def tracer(self) -> Optional[ToolTracer]:
        """获取追踪器"""
        return self._tracer

    @property
    def tester(self) -> ToolTester:
        """获取测试器"""
        return self._tester

    def register(self, tool: BaseTool) -> None:
        """注册工具"""
        if not isinstance(tool, BaseTool):
            raise TypeError(f"Tool must be an instance of BaseTool, got {type(tool)}")
        if tool.schema.name in self._tools:
            logger.warning(f"Tool {tool.schema.name} already registered, overwriting")
        self._tools[tool.schema.name] = tool
        self._categories.add(tool.schema.category)
        logger.info(f"Tool registered: {tool.schema.name} (v{tool.schema.version})")

    def register_function(
        self,
        func: Callable,
        name: str,
        description: str,
        parameters: Optional[List[ToolParameter]] = None,
        version: str = "1.0.0",
        category: str = "general",
        tags: Optional[List[str]] = None,
    ) -> None:
        """通过函数注册工具"""
        tool = FunctionTool(
            func=func,
            name=name,
            description=description,
            parameters=parameters,
            version=version,
            category=category,
            tags=tags,
        )
        self.register(tool)

    def get_tool(self, name: str) -> Optional[BaseTool]:
        """获取工具"""
        return self._tools.get(name)

    def list_tool_names(self) -> List[str]:
        """列出所有工具名称"""
        return list(self._tools.keys())

    def list_tools_by_category(self, category: str) -> List[BaseTool]:
        """按分类列出工具"""
        return [
            tool for tool in self._tools.values()
            if tool.schema.category == category
        ]

    def get_categories(self) -> List[str]:
        """获取所有分类"""
        return sorted(list(self._categories))

    def execute(self, tool_name: str, **kwargs) -> Any:
        """执行工具"""
        tool = self.get_tool(tool_name)
        if not tool:
            raise ValueError(f"Tool not found: {tool_name}. Available: {list(self._tools.keys())}")
        trace_id = None
        if self._tracer:
            trace_id = self._tracer.start_trace(tool_name, kwargs)
        try:
            result = tool.execute(**kwargs)
            if self._tracer and trace_id:
                self._tracer.end_trace(trace_id, output=result)
            return result
        except Exception as e:
            if self._tracer and trace_id:
                self._tracer.end_trace(trace_id, error=str(e))
            logger.error(f"Tool '{tool_name}' execution failed: {e}")
            raise

    def unregister(self, name: str) -> bool:
        """注销工具"""
        if name in self._tools:
            del self._tools[name]
            logger.info(f"Tool unregistered: {name}")
            return True
        return False

    def get_tool_schemas(self) -> List[Dict[str, Any]]:
        """获取所有工具Schema"""
        return [tool.to_dict() for tool in self._tools.values()]

    def get_tool_descriptions(self) -> str:
        """获取工具描述文本（用于Prompt）"""
        lines = []
        for tool in self._tools.values():
            if tool.schema.status == ToolStatus.ACTIVE:
                param_str = ", ".join([
                    f"{p.name}: {p.type}" + ("" if p.required else " = None")
                    for p in tool.schema.parameters
                ])
                lines.append(f"- {tool.schema.name}: {tool.schema.description} ({param_str})")
        return "\n".join(lines)

    def get_statistics(self) -> Dict[str, Any]:
        """获取统计信息"""
        stats = {
            "total_tools": len(self._tools),
            "categories": list(self._categories),
            "tools_by_category": {
                cat: len(self.list_tools_by_category(cat))
                for cat in self._categories
            },
        }
        if self._tracer:
            stats["traces"] = self._tracer.get_statistics()
        return stats


def tool(
    name: Optional[str] = None,
    description: Optional[str] = None,
    parameters: Optional[List[ToolParameter]] = None,
    version: str = "1.0.0",
    category: str = "general",
    tags: Optional[List[str]] = None,
):
    """工具装饰器，用于快速注册函数为工具"""
    def decorator(func: Callable):
        func._tool_info = {
            "name": name or func.__name__,
            "description": description or func.__doc__ or "",
            "parameters": parameters,
            "version": version,
            "category": category,
            "tags": tags or [],
        }
        return func
    return decorator


def discover_tools(module) -> List[BaseTool]:
    """自动发现模块中的工具"""
    tools = []
    for name, obj in inspect.getmembers(module):
        if inspect.isfunction(obj) and hasattr(obj, "_tool_info"):
            info = obj._tool_info
            tool = FunctionTool(
                func=obj,
                name=info["name"],
                description=info["description"],
                parameters=info["parameters"],
                version=info["version"],
                category=info["category"],
                tags=info["tags"],
            )
            tools.append(tool)
        elif (
            inspect.isclass(obj)
            and issubclass(obj, BaseTool)
            and obj != BaseTool
            and obj != FunctionTool
        ):
            try:
                tools.append(obj())
            except Exception as e:
                logger.warning(f"Failed to instantiate tool {name}: {e}")
    return tools
