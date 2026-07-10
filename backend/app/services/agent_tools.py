"""Agent Tool 注册系统——标准化工具接口与内置工具集
已重构为与 tool_system 兼容，保持向后兼容
"""
import re
import math
import logging
from typing import Any, Dict, List, Optional, Callable
from datetime import datetime
from .tool_system import (
    BaseTool as NewBaseTool,
    ToolParameter,
    ToolSchema,
    ToolStatus,
    ToolRegistry as NewToolRegistry,
)

logger = logging.getLogger(__name__)


class BaseTool(NewBaseTool):
    """标准 Tool 接口（保持向后兼容）
    继承自新的 tool_system.BaseTool，保持旧接口的同时提供新功能
    """

    @property
    def name(self) -> str:
        """工具名称（向后兼容）"""
        return self.schema.name

    @property
    def description(self) -> str:
        """工具描述（向后兼容）"""
        return self.schema.description

    @property
    def input_schema(self) -> str:
        """输入参数说明（向后兼容）"""
        param_strs = []
        for p in self.schema.parameters:
            ps = f"{p.name}: {p.type}"
            if not p.required:
                ps += f" = {p.default}" if p.default is not None else " = None"
            param_strs.append(ps)
        return ", ".join(param_strs)


class RuleSearchTool(BaseTool):
    """规则搜索工具——复用现有向量检索能力"""

    def __init__(self, rag_engine=None):
        self._rag_engine = rag_engine

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="rule_search",
            description="搜索OCG/DM规则书相关规则条款，支持语义搜索和关键词搜索",
            version="1.0.0",
            category="search",
            parameters=[
                ToolParameter(name="query", type="str", required=True, description="搜索查询"),
                ToolParameter(name="top_k", type="int", required=False, default=5, min_value=1, max_value=50, description="返回结果数"),
                ToolParameter(name="search_type", type="str", required=False, default="hybrid", enum=["hybrid", "vector", "bm25", "rrf"], description="搜索类型"),
            ],
            tags=["search", "rules", "ocg", "dm"],
        )

    def _execute(self, **kwargs) -> Any:
        query = kwargs.get("query", "")
        top_k = kwargs.get("top_k", 5)
        search_type = kwargs.get("search_type", "hybrid")

        if not query or not query.strip():
            return {"error": "查询词不能为空", "results": []}

        if self._rag_engine is None:
            return {
                "error": "RAG引擎未初始化",
                "query": query,
                "results": [],
            }

        try:
            if search_type == "vector":
                results = self._rag_engine.search(query, top_k=top_k)
            elif search_type == "bm25":
                results = self._rag_engine.bm25_search(query, top_k=top_k)
            elif search_type == "rrf":
                results = self._rag_engine.rrf_hybrid_search(query, top_k=top_k)
            else:
                results = self._rag_engine.rrf_hybrid_search(query, top_k=top_k)

            return {
                "query": query,
                "search_type": search_type,
                "result_count": len(results),
                "results": results,
            }
        except Exception as e:
            logger.error(f"RuleSearchTool execution failed: {e}")
            return {"error": str(e), "query": query, "results": []}


class CardDatabaseTool(BaseTool):
    """卡牌数据库查询工具"""

    _MOCK_CARD_DB: Dict[str, Dict[str, Any]] = {
        "青眼白龙": {
            "name": "青眼白龙",
            "type": "效果怪兽",
            "attribute": "光",
            "race": "龙族",
            "level": 8,
            "atk": 3000,
            "def": 2500,
            "effect": "这张卡以高攻击力著称，是非常强力的通常怪兽。",
        },
        "黑魔导": {
            "name": "黑魔导",
            "type": "通常怪兽",
            "attribute": "暗",
            "race": "魔法师族",
            "level": 7,
            "atk": 2500,
            "def": 2100,
            "effect": "作为魔法师，攻击力·守备力都是最高级别的。",
        },
        "真红眼黑龙": {
            "name": "真红眼黑龙",
            "type": "通常怪兽",
            "attribute": "暗",
            "race": "龙族",
            "level": 7,
            "atk": 2400,
            "def": 2000,
            "effect": "拥有真红之眼的黑龙。愤怒的铁锤不会放过敌人。",
        },
    }

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="card_database",
            description="查询OCG/DM卡牌信息，包括卡名、效果、属性、种族等",
            version="1.0.0",
            category="data",
            parameters=[
                ToolParameter(name="card_name", type="str", required=True, description="卡牌名称"),
                ToolParameter(name="field", type="str", required=False, default="all", description="要查询的字段"),
            ],
            tags=["cards", "database", "ocg", "dm"],
        )

    def _execute(self, **kwargs) -> Any:
        card_name = kwargs.get("card_name", "") or kwargs.get("query", "")
        field = kwargs.get("field", "all")

        if not card_name or not card_name.strip():
            return {"error": "卡牌名称不能为空", "card": None}

        card_name = card_name.strip()

        card = self._MOCK_CARD_DB.get(card_name)

        if card is None:
            for key, val in self._MOCK_CARD_DB.items():
                if card_name in key or key in card_name:
                    card = val
                    break

        if card is None:
            return {
                "error": f"未找到卡牌: {card_name}",
                "query": card_name,
                "card": None,
            }

        if field != "all":
            result = card.get(field, None)
            if result is None:
                return {
                    "error": f"卡牌 {card_name} 没有字段 '{field}'",
                    "card_name": card_name,
                    "field": field,
                }
            return {"card_name": card_name, "field": field, "value": result}

        return {"card_name": card_name, "card": card}


class CalculatorTool(BaseTool):
    """数值计算工具"""

    _SAFE_OPS = {
        "add": lambda a, b: a + b,
        "sub": lambda a, b: a - b,
        "mul": lambda a, b: a * b,
        "div": lambda a, b: a / b if b != 0 else float("inf"),
        "pow": lambda a, b: a ** b,
        "sqrt": lambda a, b: math.sqrt(abs(a)),
        "floor": lambda a, b: math.floor(a),
        "ceil": lambda a, b: math.ceil(a),
        "mod": lambda a, b: a % b if b != 0 else 0,
        "abs": lambda a, b: abs(a),
    }

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="calculator",
            description="执行数学计算，支持加减乘除、幂运算、开方、取整等",
            version="1.0.0",
            category="utility",
            parameters=[
                ToolParameter(name="expression", type="str", required=True, description="数学表达式"),
            ],
            tags=["calculator", "math"],
        )

    def _execute(self, **kwargs) -> Any:
        expression = kwargs.get("expression", "") or kwargs.get("query", "")

        if not expression or not expression.strip():
            return {"error": "表达式不能为空", "result": None}

        expression = expression.strip()

        if " " in expression:
            parts = expression.split()
            if len(parts) == 2:
                op_name, operand = parts[0], parts[1]
                try:
                    a = float(operand)
                    if op_name in self._SAFE_OPS:
                        result = self._SAFE_OPS[op_name](a, 0)
                        return {"expression": expression, "result": result}
                except ValueError:
                    pass
            elif len(parts) == 3:
                op_name, a_str, b_str = parts
                try:
                    a, b = float(a_str), float(b_str)
                    if op_name in self._SAFE_OPS:
                        result = self._SAFE_OPS[op_name](a, b)
                        return {"expression": expression, "result": result}
                except ValueError:
                    pass

        match = re.match(r"([\d.]+)\s*([+\-*/^%])\s*([\d.]+)", expression)
        if match:
            try:
                a = float(match.group(1))
                op = match.group(2)
                b = float(match.group(3))

                op_map = {"+": "add", "-": "sub", "*": "mul", "/": "div", "^": "pow", "%": "mod"}
                if op in op_map:
                    result = self._SAFE_OPS[op_map[op]](a, b)
                    return {"expression": expression, "result": result}
            except Exception as e:
                return {"error": f"计算错误: {e}", "expression": expression}

        try:
            allowed = {"__builtins__": {}, "abs": abs, "round": round, "int": int, "float": float}
            result = eval(expression, allowed, {})
            return {"expression": expression, "result": result}
        except Exception as e:
            return {
                "error": f"无法解析表达式: {e}",
                "expression": expression,
                "hint": "支持格式: 'add 3 5', '3 + 5', 'sqrt 16'",
            }


class DateTimeTool(BaseTool):
    """时间相关查询工具"""

    @property
    def schema(self) -> ToolSchema:
        return ToolSchema(
            name="datetime",
            description="获取当前时间、日期、星期，以及进行日期计算和格式转换",
            version="1.0.0",
            category="utility",
            parameters=[
                ToolParameter(name="action", type="str", required=False, default="now", enum=["now", "date", "time", "weekday", "timestamp"], description="执行的操作"),
                ToolParameter(name="format", type="str", required=False, default="%Y-%m-%d %H:%M:%S", description="日期格式"),
            ],
            tags=["datetime", "time", "date"],
        )

    def _execute(self, **kwargs) -> Any:
        action = kwargs.get("action", "now") or kwargs.get("query", "now")
        fmt = kwargs.get("format", "%Y-%m-%d %H:%M:%S")

        now = datetime.now()

        if action == "now":
            return {
                "action": "now",
                "datetime": now.strftime(fmt),
                "timestamp": now.timestamp(),
            }
        elif action == "date":
            return {
                "action": "date",
                "date": now.strftime("%Y-%m-%d"),
                "year": now.year,
                "month": now.month,
                "day": now.day,
            }
        elif action == "time":
            return {
                "action": "time",
                "time": now.strftime("%H:%M:%S"),
                "hour": now.hour,
                "minute": now.minute,
                "second": now.second,
            }
        elif action == "weekday":
            weekdays = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]
            return {
                "action": "weekday",
                "weekday": weekdays[now.weekday()],
                "weekday_index": now.weekday() + 1,
            }
        elif action == "timestamp":
            return {
                "action": "timestamp",
                "timestamp": now.timestamp(),
                "datetime": now.strftime(fmt),
            }
        else:
            return {
                "error": f"未知操作: {action}",
                "supported_actions": ["now", "date", "time", "weekday", "timestamp"],
            }


class ToolRegistry(NewToolRegistry):
    """Tool 注册中心——管理所有可用工具
    保持向后兼容性，同时提供新功能
    """

    def __init__(self):
        super().__init__(enable_tracing=True)
        logger.info("ToolRegistry initialized (standardized with tool_system)")

    def register_function(
        self,
        name: str,
        func: Callable,
        description: str,
        input_schema: str = "query: str",
    ) -> None:
        """通过函数注册工具（保持向后兼容）"""
        params = self._parse_input_schema(input_schema)
        super().register_function(
            func=func,
            name=name,
            description=description,
            parameters=params,
            category="general",
        )
        logger.info(f"Function tool registered: {name}")

    def _parse_input_schema(self, input_schema: str) -> List[ToolParameter]:
        """解析旧的 input_schema 格式为 ToolParameter 列表"""
        params = []
        if not input_schema:
            return params
        parts = input_schema.split(",")
        for part in parts:
            part = part.strip()
            if not part:
                continue
            if ":" in part:
                name_type = part.split(":", 1)
                name = name_type[0].strip()
                type_str = name_type[1].strip() if len(name_type) > 1 else "str"
                default = None
                if "=" in type_str:
                    type_str, default_part = type_str.split("=", 1)
                    type_str = type_str.strip()
                    default = default_part.strip()
            else:
                name = part
                type_str = "str"
                default = None
            params.append(ToolParameter(
                name=name,
                type=type_str,
                required=default is None,
                default=default,
                description="",
            ))
        return params

    def list_tools(self) -> List[Dict[str, str]]:
        """获取所有已注册工具的信息列表（向后兼容）"""
        result = []
        for tool in self._tools.values():
            info = {
                "name": tool.schema.name,
                "description": tool.schema.description,
                "input_schema": "",
            }
            if hasattr(tool, "input_schema"):
                info["input_schema"] = tool.input_schema
            else:
                param_strs = []
                for p in tool.schema.parameters:
                    ps = f"{p.name}: {p.type}"
                    if not p.required:
                        ps += f" = {p.default}" if p.default is not None else " = None"
                    param_strs.append(ps)
                info["input_schema"] = ", ".join(param_strs)
            result.append(info)
        return result

    @property
    def tool_count(self) -> int:
        """已注册工具数量（向后兼容）"""
        return len(self._tools)


def create_builtin_registry(rag_engine=None) -> ToolRegistry:
    """创建包含所有内置工具的注册表

    Args:
        rag_engine: VectorRAG 引擎实例，用于 rule_search 工具

    Returns:
        ToolRegistry: 包含所有内置工具的注册表
    """
    registry = ToolRegistry()

    registry.register(RuleSearchTool(rag_engine=rag_engine))
    registry.register(CardDatabaseTool())
    registry.register(CalculatorTool())
    registry.register(DateTimeTool())

    logger.info(f"Built-in registry created with {registry.tool_count} tools")
    return registry
