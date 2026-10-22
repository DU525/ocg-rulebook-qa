"""Regression tests for the production evidence-grounding contract."""

from __future__ import annotations

import inspect
import sys
from pathlib import Path


BACKEND = Path(__file__).resolve().parents[1] / "backend"
sys.path.insert(0, str(BACKEND))

TEMPLATE_TYPES = ("default", "rule", "concept", "compare", "operation")
REQUIRED_CONSTRAINTS = (
    "只能使用【上下文信息】直接支持的事实",
    "卡名、数值、例子、条款号不得新增",
    "每个独立结论末尾必须标注 [参考N]",
    "禁止将多条参考拼接成上下文未直接陈述的新结论",
    "逐项回答所有显式子问题",
    "区分发动合法性与处理结果",
    "效果与代价/召唤手续",
    "时间点/连锁",
    "区域/控制者变化",
    "知识库中未找到相关信息",
)


def test_all_five_templates_contain_the_shared_hard_constraints():
    from app.core.prompt_templates import get_template

    for template_type in TEMPLATE_TYPES:
        template = get_template(template_type)
        for constraint in REQUIRED_CONSTRAINTS:
            assert constraint in template, f"{template_type} missing: {constraint}"


def test_generation_defaults_are_deterministic():
    from app.core.rag_engine import RAGEngine

    for method_name in ("generate", "generate_stream", "query", "query_stream", "query_multimodal"):
        parameter = inspect.signature(getattr(RAGEngine, method_name)).parameters["temperature"]
        assert parameter.default == 0.0, f"{method_name} defaults to {parameter.default}"
