"""Skill 技能注册中心——让 Agent 可以动态加载能力
已重构为与 tool_system 兼容，保持向后兼容
"""
from typing import Dict, Any, Callable, List
import logging
from .tool_system import (
    ToolRegistry as BaseToolRegistry,
    BaseTool,
    FunctionTool,
    ToolParameter,
    ToolSchema,
    ToolStatus,
)

logger = logging.getLogger(__name__)


class SkillRegistry:
    """技能注册中心——让 Agent 可以动态加载能力
    已重构为与 tool_system 兼容，保持向后兼容
    """

    def __init__(self):
        self._registry = BaseToolRegistry(enable_tracing=True)
        logger.info("SkillRegistry initialized (standardized with tool_system)")

    def register(
        self,
        name: str,
        func: Callable,
        description: str,
        input_schema: str = "query: str",
    ) -> None:
        """注册技能
        Args:
            name: 技能名称（Agent 用这个名称调用）
            func: 技能执行函数
            description: 技能描述（告诉 Agent 这个技能能做什么）
            input_schema: 输入参数说明
        """
        params = self._parse_input_schema(input_schema)
        self._registry.register_function(
            func=func,
            name=name,
            description=description,
            parameters=params,
            category="skill",
            tags=["skill"],
        )
        logger.info(f"Skill registered: {name}")

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
                if "=" in type_str:
                    type_str, _ = type_str.split("=", 1)
                    type_str = type_str.strip()
            else:
                name = part
                type_str = "str"
            params.append(ToolParameter(
                name=name,
                type=type_str,
                required=True,
                description="",
            ))
        return params

    def execute(self, name: str, **kwargs) -> Any:
        """执行技能"""
        return self._registry.execute(name, **kwargs)

    def get_available_skills(self) -> List[Dict[str, str]]:
        """获取可用技能列表"""
        return [
            {"name": tool.schema.name, "description": tool.schema.description}
            for tool in self._registry.list_tools_by_category("skill")
        ]

    def get_skill_descriptions(self) -> str:
        """获取技能描述文本（用于 Prompt）"""
        lines = []
        for tool in self._registry.list_tools_by_category("skill"):
            param_str = ", ".join([p.name for p in tool.schema.parameters])
            lines.append(f"- {tool.schema.name}: {tool.schema.description} (输入: {param_str})")
        return "\n".join(lines)

    @property
    def base_registry(self) -> BaseToolRegistry:
        """获取底层工具注册表，用于高级功能"""
        return self._registry
