"""
分层 RAG 系统测试脚本

验证 HierarchicalVectorStore 和相关功能。
"""

import os
import sys
import tempfile
from pathlib import Path

# 添加 backend 路径到 sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.hierarchical_vector_store import HierarchicalVectorStore
from app.services.hierarchical_rag import HierarchicalChunk


def test_hierarchical_store_init():
    """测试分层向量存储初始化"""
    print("=" * 50)
    print("测试 1: HierarchicalVectorStore 初始化")
    print("=" * 50)

    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            store = HierarchicalVectorStore(
                persist_directory=temp_dir,
                collection_name="test_hierarchical"
            )
            print(f"✓ HierarchicalVectorStore 初始化成功")
            print(f"  - Collection Name: {store.collection_name}")
            stats = store.get_collection_stats()
            print(f"  - Stats: {stats}")
            return store
        except Exception as e:
            print(f"✗ 初始化失败: {e}")
            raise


def test_add_document(store: HierarchicalVectorStore):
    """测试添加文档"""
    print("\n" + "=" * 50)
    print("测试 2: 添加文档")
    print("=" * 50)

    test_content = """# 游戏王OCG规则

## 第一章 基本规则

### 1.1 游戏目标
游戏王OCG的目标是通过使用怪兽卡、魔法卡和陷阱卡，将对方的生命值从8000降低至0。

### 1.2 卡牌类型
游戏王OCG包含三种主要卡牌类型：
- 怪兽卡：用于攻击和防御
- 魔法卡：提供各种辅助效果
- 陷阱卡：在对方回合发动的效果

## 第二章 怪兽卡规则

### 2.1 召唤规则
怪兽卡有多种召唤方式：
- 通常召唤：每回合一次
- 特殊召唤：通过卡片效果
- 融合召唤：使用融合魔法卡
- 同步召唤：使用协调怪兽
- 超量召唤：使用同等级怪兽叠放
"""

    try:
        store.add_document(
            content=test_content,
            metadata={"source": "test_rules.md", "category": "rule"},
            document_id="test_doc_001"
        )
        print(f"✓ 成功添加文档")
        stats = store.get_collection_stats()
        print(f"  - Total Parent Chunks: {stats['parent_count']}")
        print(f"  - Total Child Chunks: {stats['child_count']}")
        return True
    except Exception as e:
        print(f"✗ 添加文档失败: {e}")
        raise


def test_hierarchical_search(store: HierarchicalVectorStore):
    """测试分层检索"""
    print("\n" + "=" * 50)
    print("测试 3: 分层检索")
    print("=" * 50)

    test_queries = [
        "游戏王的游戏目标是什么",
        "怪兽卡有哪些召唤方式",
        "陷阱卡如何使用"
    ]

    for query in test_queries:
        print(f"\n查询: {query}")
        try:
            results = store.search(
                query=query,
                top_k=3,
                parent_top_k=5,
                enable_rerank=False
            )
            print(f"  ✓ 找到 {len(results)} 个结果")
            for i, result in enumerate(results[:2], 1):
                print(f"    [{i}] Score: {result.score:.3f}")
                print(f"        Content: {result.content[:80]}...")
        except Exception as e:
            print(f"  ✗ 检索失败: {e}")
            raise

    return True


def test_clear_collection(store: HierarchicalVectorStore):
    """测试清空集合"""
    print("\n" + "=" * 50)
    print("测试 4: 清空集合")
    print("=" * 50)

    try:
        stats_before = store.get_collection_stats()
        print(f"  - 清空之前: {stats_before}")

        store.clear()

        stats_after = store.get_collection_stats()
        print(f"  - 清空之后: {stats_after}")
        print(f"✓ 集合清空成功")
        return True
    except Exception as e:
        print(f"✗ 清空失败: {e}")
        raise


def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("分层 RAG 系统测试")
    print("=" * 60)

    try:
        # 测试 1
        store = test_hierarchical_store_init()

        # 测试 2
        test_add_document(store)

        # 测试 3
        test_hierarchical_search(store)

        # 测试 4
        test_clear_collection(store)

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
