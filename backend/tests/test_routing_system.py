"""
路由系统测试脚本

验证 SemanticRouter 和 AdvancedRouter 功能。
"""

import os
import sys
from pathlib import Path

# 添加 backend 路径到 sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.semantic_router import (
    get_semantic_router,
    SemanticRouter,
    RouteType
)
from app.services.advanced_router import (
    get_advanced_router,
    AdvancedRouter,
    StrategyType
)


def test_semantic_router_init():
    """测试语义路由初始化"""
    print("=" * 50)
    print("测试 1: 语义路由初始化")
    print("=" * 50)

    try:
        router = get_semantic_router()
        print(f"✓ SemanticRouter 初始化成功")
        print(f"  - Route count: {len(router.routes)}")
        return router
    except Exception as e:
        print(f"✗ 初始化失败: {e}")
        raise


def test_add_routes(router: SemanticRouter):
    """测试添加路由"""
    print("\n" + "=" * 50)
    print("测试 2: 添加路由")
    print("=" * 50)

    test_routes = [
        {
            "name": "ocg_rules",
            "description": "OCG规则相关问题",
            "examples": [
                "游戏王规则是什么",
                "怎么召唤怪兽",
                "陷阱卡怎么用",
                "禁止卡表"
            ],
            "keywords": ["规则", "OCG", "游戏王", "召唤", "陷阱"],
            "route_type": RouteType.SEMANTIC,
            "threshold": 0.7
        },
        {
            "name": "card_database",
            "description": "卡片查询相关问题",
            "examples": [
                "查一张卡",
                "青眼白龙的效果",
                "有哪些龙族卡"
            ],
            "keywords": ["卡片", "卡", "查卡", "效果"],
            "route_type": RouteType.KEYWORD,
            "threshold": 0.8
        },
        {
            "name": "game_advice",
            "description": "游戏建议和策略",
            "examples": [
                "怎么组卡组",
                "有什么战术",
                "这个卡怎么用"
            ],
            "keywords": ["卡组", "战术", "建议", "策略"],
            "route_type": RouteType.SEMANTIC,
            "threshold": 0.65
        }
    ]

    for i, route_data in enumerate(test_routes, 1):
        try:
            router.add_route(**route_data)
            print(f"  ✓ 添加路由 {i}: {route_data['name']}")
            print(f"    - Examples: {len(route_data['examples'])}")
        except Exception as e:
            print(f"  ✗ 添加路由 {i} 失败: {e}")
            raise

    print(f"\n✓ 成功添加 {len(test_routes)} 个路由")
    return True


def test_semantic_routing(router: SemanticRouter):
    """测试语义路由"""
    print("\n" + "=" * 50)
    print("测试 3: 语义路由决策")
    print("=" * 50)

    test_queries = [
        "游戏王的召唤规则是什么",
        "帮我查一下青眼白龙",
        "怎么组一副龙族卡组",
        "这个问题不太清楚"
    ]

    for query in test_queries:
        print(f"\n查询: {query}")
        try:
            decision = router.route(query)
            print(f"  ✓ 路由决策: {decision.route_name}")
            print(f"    - Type: {decision.route_type.value}")
            print(f"    - Confidence: {decision.confidence:.3f}")
        except Exception as e:
            print(f"  ✗ 路由失败: {e}")
            raise

    return True


def test_advanced_router():
    """测试高级路由"""
    print("\n" + "=" * 50)
    print("测试 4: 高级混合路由")
    print("=" * 50)

    try:
        advanced_router = get_advanced_router()
        print(f"✓ AdvancedRouter 初始化成功")
    except Exception as e:
        print(f"✗ 高级路由初始化失败: {e}")
        raise

    test_query = "游戏王OCG的规则是什么"
    print(f"\n查询: {test_query}")
    try:
        result = advanced_router.route(test_query)
        print(f"  ✓ 高级路由决策")
        print(f"    - Selected: {result.selected_route}")
        print(f"    - Strategy: {result.strategy_used.value}")
        print(f"    - Scores: {result.scores}")
    except Exception as e:
        print(f"  ✗ 高级路由失败: {e}")
        raise

    return True


def test_router_feedback(router: SemanticRouter):
    """测试路由反馈"""
    print("\n" + "=" * 50)
    print("测试 5: 路由反馈学习")
    print("=" * 50)

    test_query = "游戏王规则"
    try:
        # 初始决策
        decision = router.route(test_query)
        print(f"  - 初始决策: {decision.route_name}")

        # 添加反馈
        router.add_feedback(
            query=test_query,
            correct_route="ocg_rules",
            selected_route=decision.route_name
        )
        print(f"  ✓ 反馈添加成功")

        # 查看反馈历史
        print(f"  - Feedback count: {len(router.feedback_history)}")
        return True
    except Exception as e:
        print(f"✗ 反馈测试失败: {e}")
        raise


def test_router_visualization(router: SemanticRouter):
    """测试路由可视化数据"""
    print("\n" + "=" * 50)
    print("测试 6: 路由可视化")
    print("=" * 50)

    try:
        viz_data = router.get_visualization_data()
        print(f"✓ 可视化数据获取成功")
        print(f"  - Route count: {len(viz_data['routes'])}")
        print(f"  - Decision count: {len(viz_data['decisions'])}")
        return True
    except Exception as e:
        print(f"✗ 可视化失败: {e}")
        raise


def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("高级路由系统测试")
    print("=" * 60)

    try:
        # 测试 1
        router = test_semantic_router_init()

        # 测试 2
        test_add_routes(router)

        # 测试 3
        test_semantic_routing(router)

        # 测试 4
        test_advanced_router()

        # 测试 5
        test_router_feedback(router)

        # 测试 6
        test_router_visualization(router)

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
