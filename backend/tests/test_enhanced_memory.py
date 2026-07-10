"""
记忆系统测试脚本

验证 EnhancedMemorySystem 和 MemoryRetriever 功能。
"""

import os
import sys
import tempfile
from pathlib import Path

# 添加 backend 路径到 sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.enhanced_memory import (
    get_enhanced_memory,
    EnhancedMemorySystem,
    MemoryType,
    MemoryItem
)
from app.services.memory_retriever import (
    get_memory_retriever,
    MemoryRetriever,
    RetrievalStrategy
)


def test_memory_system_init():
    """测试记忆系统初始化"""
    print("=" * 50)
    print("测试 1: 记忆系统初始化")
    print("=" * 50)

    try:
        memory = get_enhanced_memory()
        print(f"✓ EnhancedMemorySystem 初始化成功")
        print(f"  - Short-term count: {len(memory.short_term.memories)}")
        print(f"  - Long-term count: {len(memory.long_term.memories)}")
        print(f"  - Working count: {len(memory.working_memory.memories)}")
        return memory
    except Exception as e:
        print(f"✗ 初始化失败: {e}")
        raise


def test_add_memory(memory: EnhancedMemorySystem):
    """测试添加记忆"""
    print("\n" + "=" * 50)
    print("测试 2: 添加记忆")
    print("=" * 50)

    test_memories = [
        {
            "content": "用户A喜欢使用游戏王中的龙族卡组",
            "memory_type": MemoryType.EPISODIC,
            "importance": 0.8,
            "tags": {"用户偏好", "龙族", "卡组"}
        },
        {
            "content": "用户B询问了超量召唤的规则",
            "memory_type": MemoryType.FACTUAL,
            "importance": 0.6,
            "tags": {"超量召唤", "规则", "用户B"}
        },
        {
            "content": "OCG规则中，通常召唤每回合只能进行一次",
            "memory_type": MemoryType.FACTUAL,
            "importance": 0.9,
            "tags": {"OCG", "规则", "通常召唤"}
        },
        {
            "content": "2024年3月，游戏王OCG发布了新的禁止卡表",
            "memory_type": MemoryType.SEMANTIC,
            "importance": 0.7,
            "tags": {"禁止卡表", "2024", "OCG"}
        }
    ]

    memory_ids = []
    for i, mem_data in enumerate(test_memories, 1):
        try:
            memory_id = memory.add_memory(**mem_data)
            memory_ids.append(memory_id)
            print(f"  ✓ 添加记忆 {i}: {mem_data['content'][:50]}...")
            print(f"    - ID: {memory_id}")
        except Exception as e:
            print(f"  ✗ 添加记忆 {i} 失败: {e}")
            raise

    print(f"\n✓ 成功添加 {len(memory_ids)} 个记忆")
    return memory_ids


def test_memory_retrieval(memory: EnhancedMemorySystem):
    """测试记忆检索"""
    print("\n" + "=" * 50)
    print("测试 3: 记忆检索")
    print("=" * 50)

    try:
        retriever = get_memory_retriever()
        retriever.index_all_memories()
        print(f"✓ MemoryRetriever 初始化和索引成功")
    except Exception as e:
        print(f"✗ 检索器初始化失败: {e}")
        raise

    test_queries = [
        ("用户喜欢什么卡组", RetrievalStrategy.HYBRID),
        ("超量召唤规则", RetrievalStrategy.SEMANTIC),
        ("通常召唤", RetrievalStrategy.BM25),
        ("2024年", RetrievalStrategy.TIME_BASED)
    ]

    for query, strategy in test_queries:
        print(f"\n查询: {query} (策略: {strategy.value})")
        try:
            results = retriever.retrieve(
                query=query,
                limit=3,
                strategy=strategy
            )
            print(f"  ✓ 找到 {len(results)} 个结果")
            for i, result in enumerate(results, 1):
                print(f"    [{i}] Score: {result.score:.3f}")
                print(f"        Content: {result.memory.content[:60]}...")
        except Exception as e:
            print(f"  ✗ 检索失败: {e}")
            raise

    return True


def test_memory_operations(memory: EnhancedMemorySystem):
    """测试记忆操作"""
    print("\n" + "=" * 50)
    print("测试 4: 记忆操作")
    print("=" * 50)

    try:
        # 测试获取记忆
        all_memories = memory.get_all_memories()
        print(f"✓ 获取所有记忆: {len(all_memories)} 个")

        # 测试按类型获取
        factual_memories = memory.get_memories_by_type(MemoryType.FACTUAL)
        print(f"✓ FACTUAL 类型记忆: {len(factual_memories)} 个")

        # 测试按标签获取
        tag_memories = memory.get_memories_by_tag("OCG")
        print(f"✓ 含 'OCG' 标签记忆: {len(tag_memories)} 个")

        # 测试重要性过滤
        important_memories = memory.get_important_memories(threshold=0.7)
        print(f"✓ 重要性 >=0.7 的记忆: {len(important_memories)} 个")

        return True
    except Exception as e:
        print(f"✗ 记忆操作失败: {e}")
        raise


def test_memory_clearing(memory: EnhancedMemorySystem):
    """测试清空记忆"""
    print("\n" + "=" * 50)
    print("测试 5: 清空记忆")
    print("=" * 50)

    try:
        # 统计清空之前
        before_count = len(memory.get_all_memories())
        print(f"  - 清空之前: {before_count} 个记忆")

        # 清空短期记忆
        memory.clear_short_term()
        print(f"  - 清空短期记忆完成")

        # 清空全部
        memory.clear_all()
        after_count = len(memory.get_all_memories())
        print(f"  - 清空全部之后: {after_count} 个记忆")
        print(f"✓ 记忆清空成功")
        return True
    except Exception as e:
        print(f"✗ 清空失败: {e}")
        raise


def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("增强记忆系统测试")
    print("=" * 60)

    try:
        # 测试 1
        memory = test_memory_system_init()

        # 测试 2
        test_add_memory(memory)

        # 测试 3
        test_memory_retrieval(memory)

        # 测试 4
        test_memory_operations(memory)

        # 测试 5
        test_memory_clearing(memory)

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
