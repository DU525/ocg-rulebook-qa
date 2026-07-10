"""
分块策略系统测试脚本

验证 ChunkingStrategySystem 功能。
"""

import os
import sys
from pathlib import Path

# 添加 backend 路径到 sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.chunking_strategy import (
    ChunkingStrategySystem,
    ChunkingStrategy
)


def test_chunker_init():
    """测试分块系统初始化"""
    print("=" * 50)
    print("测试 1: 分块策略系统初始化")
    print("=" * 50)

    try:
        chunker = ChunkingStrategySystem()
        print(f"✓ ChunkingStrategySystem 初始化成功")
        return chunker
    except Exception as e:
        print(f"✗ 初始化失败: {e}")
        raise


def test_sentence_chunking(chunker: ChunkingStrategySystem):
    """测试句子分块"""
    print("\n" + "=" * 50)
    print("测试 2: 句子分块策略")
    print("=" * 50)

    test_text = """
    游戏王OCG是一款集换式卡牌游戏。玩家通过使用怪兽卡、魔法卡和陷阱卡进行对战。
    游戏的目标是将对方的生命值从8000降低到0。每张卡牌都有独特的效果。
    合理的卡组构建和战术运用是获胜的关键。
    """

    try:
        chunks = chunker.chunk_text(
            text=test_text,
            strategy=ChunkingStrategy.SENTENCE
        )
        print(f"✓ 句子分块成功")
        print(f"  - 分块数量: {len(chunks)}")
        for i, chunk in enumerate(chunks[:3], 1):
            print(f"    [{i}] {chunk.content[:50]}...")
        return True
    except Exception as e:
        print(f"✗ 句子分块失败: {e}")
        raise


def test_paragraph_chunking(chunker: ChunkingStrategySystem):
    """测试段落分块"""
    print("\n" + "=" * 50)
    print("测试 3: 段落分块策略")
    print("=" * 50)

    test_text = """
# 第一章 游戏王OCG简介

游戏王OCG是由KONAMI开发的集换式卡牌游戏，于1999年首次发布。
玩家通过构建卡组，使用怪兽卡、魔法卡和陷阱卡进行对战。

## 1.1 游戏目标

游戏的基本目标是通过各种手段，将对方的生命值从初始的8000点降低至0点。
每张卡牌都有独特的效果，玩家需要巧妙地组合使用这些卡牌。

## 1.2 卡牌类型

游戏王OCG包含三种主要卡牌类型：
1. 怪兽卡：用于攻击和防御
2. 魔法卡：提供各种辅助效果
3. 陷阱卡：在对方回合发动的效果
"""

    try:
        chunks = chunker.chunk_text(
            text=test_text,
            strategy=ChunkingStrategy.PARAGRAPH
        )
        print(f"✓ 段落分块成功")
        print(f"  - 分块数量: {len(chunks)}")
        for i, chunk in enumerate(chunks, 1):
            print(f"    [{i}] {chunk.content[:60]}...")
        return True
    except Exception as e:
        print(f"✗ 段落分块失败: {e}")
        raise


def test_semantic_chunking(chunker: ChunkingStrategySystem):
    """测试语义分块"""
    print("\n" + "=" * 50)
    print("测试 4: 语义分块策略")
    print("=" * 50)

    test_text = """
# 游戏王OCG规则

## 怪兽卡规则
### 召唤方式
- 通常召唤：每回合一次
- 特殊召唤：通过卡片效果
- 融合召唤：使用融合魔法卡

## 魔法卡规则
### 魔法卡类型
- 通常魔法
- 永续魔法
- 装备魔法
- 场地魔法
- 速攻魔法
- 仪式魔法

## 陷阱卡规则
### 陷阱卡类型
- 通常陷阱
- 永续陷阱
- 反击陷阱
"""

    try:
        chunks = chunker.chunk_text(
            text=test_text,
            strategy=ChunkingStrategy.SEMANTIC
        )
        print(f"✓ 语义分块成功")
        print(f"  - 分块数量: {len(chunks)}")
        for i, chunk in enumerate(chunks, 1):
            print(f"    [{i}] {chunk.content[:50]}...")
        return True
    except Exception as e:
        print(f"✗ 语义分块失败: {e}")
        raise


def test_adaptive_chunking(chunker: ChunkingStrategySystem):
    """测试自适应分块"""
    print("\n" + "=" * 50)
    print("测试 5: 自适应分块策略")
    print("=" * 50)

    test_text = """
游戏王OCG包含很多复杂的规则。

首先，让我们了解一下基本的游戏流程：
1. 抽卡阶段
2. 准备阶段
3. 主要阶段1
4. 战斗阶段
5. 主要阶段2
6. 结束阶段

每个阶段都有特定的操作规则。
比如，在战斗阶段可以进行攻击宣言，
在主要阶段可以召唤怪兽和发动魔法。
"""

    try:
        chunks = chunker.chunk_text(
            text=test_text,
            strategy=ChunkingStrategy.ADAPTIVE
        )
        print(f"✓ 自适应分块成功")
        print(f"  - 分块数量: {len(chunks)}")
        for i, chunk in enumerate(chunks, 1):
            print(f"    [{i}] {chunk.content[:60]}...")
        return True
    except Exception as e:
        print(f"✗ 自适应分块失败: {e}")
        raise


def test_auto_strategy_selection(chunker: ChunkingStrategySystem):
    """测试自动策略选择"""
    print("\n" + "=" * 50)
    print("测试 6: 自动策略选择")
    print("=" * 50)

    test_texts = [
        "这是一段简单的文本，包含几个句子。它应该用句子分块。",
        """
# 有标题的文档

## 第一节
这是第一节的内容。

## 第二节
这是第二节的内容，应该用语义分块。
        """
    ]

    for i, text in enumerate(test_texts, 1):
        try:
            strategy = chunker.auto_select_strategy(text)
            print(f"  文本 {i}:")
            print(f"    - 自动选择策略: {strategy.value}")
        except Exception as e:
            print(f"  ✗ 策略选择失败: {e}")
            raise

    print(f"✓ 自动策略选择功能正常")
    return True


def test_chunk_evaluation(chunker: ChunkingStrategySystem):
    """测试分块质量评估"""
    print("\n" + "=" * 50)
    print("测试 7: 分块质量评估")
    print("=" * 50)

    test_text = """
    这是测试文本。第一部分。第二部分。第三部分。
    第四部分稍微长一点，用来测试不同的分块效果。
    """

    try:
        chunks = chunker.chunk_text(test_text, ChunkingStrategy.SENTENCE)
        evaluation = chunker.evaluate_chunking(chunks, test_text)

        print(f"✓ 分块质量评估完成")
        print(f"  - 总体评分: {evaluation.overall_score:.3f}")
        print(f"  - 完整性: {evaluation.completeness:.3f}")
        print(f"  - 连贯性: {evaluation.coherence:.3f}")
        print(f"  - 覆盖率: {evaluation.coverage:.3f}")
        print(f"  - 分块数: {evaluation.chunk_count}")
        return True
    except Exception as e:
        print(f"✗ 评估失败: {e}")
        raise


def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("智能分块策略系统测试")
    print("=" * 60)

    try:
        # 测试 1
        chunker = test_chunker_init()

        # 测试 2
        test_sentence_chunking(chunker)

        # 测试 3
        test_paragraph_chunking(chunker)

        # 测试 4
        test_semantic_chunking(chunker)

        # 测试 5
        test_adaptive_chunking(chunker)

        # 测试 6
        test_auto_strategy_selection(chunker)

        # 测试 7
        test_chunk_evaluation(chunker)

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
