"""OpenAI Function Calling 格式工具定义

将内部 ToolSchema 转换为 OpenAI Function Calling 格式，供 LLM 的 tools 参数使用。
"""
from typing import List, Dict, Any, Optional
from app.services.tool_system import ToolSchema, ToolParameter, ToolStatus


def _type_mapping(python_type: str) -> str:
    """将内部类型映射到 JSON Schema 类型。"""
    mapping = {
        "str": "string",
        "string": "string",
        "int": "integer",
        "integer": "integer",
        "float": "number",
        "number": "number",
        "bool": "boolean",
        "boolean": "boolean",
        "list": "array",
        "array": "array",
        "dict": "object",
        "object": "object",
    }
    return mapping.get(python_type.lower(), "string")


def tool_parameter_to_json_schema(param: ToolParameter) -> Dict[str, Any]:
    """将单个 ToolParameter 转换为 JSON Schema property 条目。"""
    prop: Dict[str, Any] = {
        "type": _type_mapping(param.type),
        "description": param.description,
    }
    if param.enum is not None:
        prop["enum"] = param.enum
    if param.min_value is not None:
        prop["minimum"] = param.min_value
    if param.max_value is not None:
        prop["maximum"] = param.max_value
    if param.default is not None:
        prop["default"] = param.default
    return prop


def tool_schema_to_function_calling(schema: ToolSchema) -> Dict[str, Any]:
    """将单个 ToolSchema 转换为 OpenAI Function Calling 格式。"""
    properties: Dict[str, Any] = {}
    required: List[str] = []

    for param in schema.parameters:
        properties[param.name] = tool_parameter_to_json_schema(param)
        if param.required:
            required.append(param.name)

    return {
        "type": "function",
        "function": {
            "name": schema.name,
            "description": schema.description,
            "parameters": {
                "type": "object",
                "properties": properties,
                "required": required,
            },
        },
    }


def schemas_to_tools(schemas: List[ToolSchema], filter_active: bool = True) -> List[Dict[str, Any]]:
    """将 ToolSchema 列表批量转换为 OpenAI tools 列表。

    Args:
        schemas: 内部 ToolSchema 列表
        filter_active: 是否只返回状态为 ACTIVE 的工具
    Returns:
        OpenAI Function Calling 格式的工具定义列表
    """
    result = []
    for schema in schemas:
        if filter_active and schema.status != ToolStatus.ACTIVE:
            continue
        result.append(tool_schema_to_function_calling(schema))
    return result


# ---------------------------------------------------------------------------
# 预定义的 OCG 规则问答系统工具
# ---------------------------------------------------------------------------

TOOLS_SEARCH_RULES: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "search_rules",
        "description": "在游戏王 OCG 规则知识库中搜索相关规则、卡牌效果或机制说明。支持 BM25+向量+RRF+Cross-Encoder 多阶段融合检索。",
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "用户的搜索关键词或问题，例：'通常召唤的限制'、'禁止召唤的怪兽'",
                },
                "top_k": {
                    "type": "integer",
                    "description": "返回结果条数，默认 5，范围 1-20",
                    "default": 5,
                    "minimum": 1,
                    "maximum": 20,
                },
                "search_type": {
                    "type": "string",
                    "enum": ["hybrid", "vector"],
                    "description": "检索类型：hybrid=BM25+向量+RRF+Cross-Encoder 融合；vector=纯 FAISS 向量检索",
                    "default": "hybrid",
                },
            },
            "required": ["query"],
        },
    },
}

TOOLS_CALCULATE: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "calculate",
        "description": "执行数学计算（仅支持基础运算符 +、-、*、/ 和括号），用于攻击力合计、连锁伤害计算等场景。",
        "parameters": {
            "type": "object",
            "properties": {
                "expression": {
                    "type": "string",
                    "description": "数学表达式，例：'3000 + 2500'、'(2 * 1000) / 2'",
                },
            },
            "required": ["expression"],
        },
    },
}

TOOLS_GET_CARD_INFO: Dict[str, Any] = {
    "type": "function",
    "function": {
        "name": "get_card_info",
        "description": "查询游戏王卡牌信息：卡名、属性、种族、攻击力、守备力、效果文本等。",
        "parameters": {
            "type": "object",
            "properties": {
                "card_name": {
                    "type": "string",
                    "description": "卡牌名称，例：'黑魔导'、'青眼白龙'、'元素英雄 天空侠'",
                },
            },
            "required": ["card_name"],
        },
    },
}

ALL_PREDEFINED_TOOLS: List[Dict[str, Any]] = [
    TOOLS_SEARCH_RULES,
    TOOLS_CALCULATE,
    TOOLS_GET_CARD_INFO,
]
