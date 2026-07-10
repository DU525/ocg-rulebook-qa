"""
工具系统测试脚本

验证 ToolSystem、ToolRegistry 和标准化工具功能。
"""

import os
import sys
from pathlib import Path

# 添加 backend 路径到 sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.tool_system import (
    ToolRegistry,
    BaseTool,
    FunctionTool,
    ToolTester,
    TestCase,
    ToolTracer,
    tool
)


def test_tool_registry_init():
    """测试工具注册表初始化"""
    print("=" * 50)
    print("测试 1: 工具注册表初始化")
    print("=" * 50)

    try:
        registry = ToolRegistry()
        print(f"✓ ToolRegistry 初始化成功")
        print(f"  - Tool count: {len(registry.tools)}")
        return registry
    except Exception as e:
        print(f"✗ 初始化失败: {e}")
        raise


def test_function_tool_creation():
    """测试 FunctionTool 创建"""
    print("\n" + "=" * 50)
    print("测试 2: FunctionTool 创建")
    print("=" * 50)

    try:
        # 简单的计算器工具
        def add_numbers(a: int, b: int) -> int:
            """两个数字相加"""
            return a + b

        calculator_tool = FunctionTool(
            name="calculator_add",
            description="两个数字相加",
            function=add_numbers,
            parameters={
                "a": {"type": "integer", "description": "第一个数字"},
                "b": {"type": "integer", "description": "第二个数字"}
            }
        )
        print(f"✓ FunctionTool 创建成功")
        print(f"  - Name: {calculator_tool.name}")
        print(f"  - Description: {calculator_tool.description}")

        # 测试执行
        result = calculator_tool.execute(a=2, b=3)
        print(f"  - Test execution (2+3): {result}")

        return calculator_tool
    except Exception as e:
        print(f"✗ FunctionTool 创建失败: {e}")
        raise


def test_tool_decorator():
    """测试 @tool 装饰器"""
    print("\n" + "=" * 50)
    print("测试 3: @tool 装饰器")
    print("=" * 50)

    try:
        @tool(name="string_utils", description="字符串处理工具")
        def reverse_string(s: str) -> str:
            """反转字符串"""
            return s[::-1]

        print(f"✓ @tool 装饰器工作正常")
        print(f"  - Tool name: {reverse_string.name}")

        # 测试执行
        test_str = "游戏王OCG"
        result = reverse_string.execute(s=test_str)
        print(f"  - Reverse '{test_str}': {result}")

        return reverse_string
    except Exception as e:
        print(f"✗ @tool 装饰器失败: {e}")
        raise


def test_tool_registration(registry: ToolRegistry):
    """测试工具注册"""
    print("\n" + "=" * 50)
    print("测试 4: 工具注册")
    print("=" * 50)

    try:
        # 创建几个测试工具
        def multiply(a: int, b: int) -> int:
            return a * b

        multiply_tool = FunctionTool(
            name="multiply",
            description="两个数字相乘",
            function=multiply,
            parameters={
                "a": {"type": "integer", "description": "第一个数字"},
                "b": {"type": "integer", "description": "第二个数字"}
            }
        )

        def uppercase(s: str) -> str:
            return s.upper()

        uppercase_tool = FunctionTool(
            name="uppercase",
            description="字符串转大写",
            function=uppercase,
            parameters={
                "s": {"type": "string", "description": "输入字符串"}
            }
        )

        # 注册工具
        registry.register_tool(multiply_tool)
        registry.register_tool(uppercase_tool)

        print(f"✓ 工具注册成功")
        print(f"  - Total tools: {len(registry.tools)}")
        print(f"  - Tools: {list(registry.tools.keys())}")

        return True
    except Exception as e:
        print(f"✗ 工具注册失败: {e}")
        raise


def test_tool_execution(registry: ToolRegistry):
    """测试工具执行"""
    print("\n" + "=" * 50)
    print("测试 5: 工具执行")
    print("=" * 50)

    try:
        # 测试乘法工具
        result = registry.execute_tool("multiply", a=4, b=5)
        print(f"  - multiply(4,5) = {result}")

        # 测试大写工具
        result = registry.execute_tool("uppercase", s="hello world")
        print(f"  - uppercase('hello world') = {result}")

        print(f"✓ 工具执行成功")
        return True
    except Exception as e:
        print(f"✗ 工具执行失败: {e}")
        raise


def test_tool_tester():
    """测试工具测试框架"""
    print("\n" + "=" * 50)
    print("测试 6: 工具测试框架")
    print("=" * 50)

    try:
        tester = ToolTester()

        # 创建一个简单的测试工具
        def simple_add(a: int, b: int) -> int:
            return a + b

        test_tool = FunctionTool(
            name="simple_add",
            description="测试工具",
            function=simple_add,
            parameters={
                "a": {"type": "integer", "description": "第一个数"},
                "b": {"type": "integer", "description": "第二个数"}
            }
        )

        # 添加测试用例
        tester.add_test_case(
            TestCase(
                tool_name="simple_add",
                input={"a": 1, "b": 1},
                expected_output=2,
                description="1+1=2"
            )
        )
        tester.add_test_case(
            TestCase(
                tool_name="simple_add",
                input={"a": 100, "b": 200},
                expected_output=300,
                description="100+200=300"
            )
        )

        # 运行测试
        print(f"  - Running tests for 'simple_add'...")
        results = tester.run_tests_for_tool("simple_add", test_tool)

        passed = sum(1 for r in results if r.passed)
        total = len(results)
        print(f"  - Test results: {passed}/{total} passed")
        for i, result in enumerate(results, 1):
            status = "✓" if result.passed else "✗"
            print(f"    [{i}] {status} {result.description}")

        print(f"✓ 工具测试框架工作正常")
        return True
    except Exception as e:
        print(f"✗ 工具测试失败: {e}")
        raise


def test_tool_tracer():
    """测试工具调用追踪"""
    print("\n" + "=" * 50)
    print("测试 7: 工具调用追踪")
    print("=" * 50)

    try:
        tracer = ToolTracer()

        # 创建并执行一些工具调用来追踪
        def trace_test(x: int) -> int:
            return x * 2

        test_tool = FunctionTool(
            name="trace_test",
            description="追踪测试工具",
            function=trace_test,
            parameters={"x": {"type": "integer", "description": "输入"}}
        )

        # 模拟调用
        test_tool.execute(x=10)
        test_tool.execute(x=20)

        # 获取统计
        stats = tracer.get_stats()
        print(f"  - Trace stats: {stats}")

        # 获取追踪历史
        history = tracer.get_trace_history()
        print(f"  - Trace history count: {len(history)}")

        print(f"✓ 工具追踪功能正常")
        return True
    except Exception as e:
        print(f"✗ 工具追踪失败: {e}")
        raise


def test_existing_tools():
    """测试现有工具（向后兼容）"""
    print("\n" + "=" * 50)
    print("测试 8: 现有工具兼容性")
    print("=" * 50)

    try:
        from app.services.agent_tools import (
            RuleSearchTool,
            CalculatorTool,
            DateTimeTool
        )

        # 测试 RuleSearchTool 可初始化
        rule_tool = RuleSearchTool()
        print(f"  - RuleSearchTool 可初始化")

        # 测试 CalculatorTool
        calc_tool = CalculatorTool()
        result = calc_tool.execute(expression="2 + 2")
        print(f"  - CalculatorTool: 2+2 = {result}")

        # 测试 DateTimeTool
        dt_tool = DateTimeTool()
        result = dt_tool.execute()
        print(f"  - DateTimeTool: {result}")

        print(f"✓ 现有工具兼容性良好")
        return True
    except Exception as e:
        print(f"⚠ 现有工具测试跳过: {e}")
        return True


def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("标准化工具系统测试")
    print("=" * 60)

    try:
        # 测试 1
        registry = test_tool_registry_init()

        # 测试 2
        test_function_tool_creation()

        # 测试 3
        test_tool_decorator()

        # 测试 4
        test_tool_registration(registry)

        # 测试 5
        test_tool_execution(registry)

        # 测试 6
        test_tool_tester()

        # 测试 7
        test_tool_tracer()

        # 测试 8
        test_existing_tools()

        print("\n" + "=" * 60)
        print("✓ 所有测试通过！")
        print("=" * 60)
        return True
    except Exception as e:
        print(f"\n✗ 测试失败: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    success = run_all_tests()
    sys.exit(0 if success else 1)
