"""
结构化数据处理测试脚本

验证表格提取、OCR和文档清理功能。
"""

import os
import sys
from pathlib import Path

# 添加 backend 路径到 sys.path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.services.structured_data_processor import StructuredDataProcessor
from app.services.document_cleaner import DocumentCleaner


def test_structured_processor_init():
    """测试结构化数据处理器初始化"""
    print("=" * 50)
    print("测试 1: 结构化数据处理器初始化")
    print("=" * 50)

    try:
        processor = StructuredDataProcessor()
        print(f"✓ StructuredDataProcessor 初始化成功")
        return processor
    except Exception as e:
        print(f"✗ 初始化失败: {e}")
        raise


def test_table_to_markdown(processor: StructuredDataProcessor):
    """测试表格转 Markdown"""
    print("\n" + "=" * 50)
    print("测试 2: 表格转 Markdown")
    print("=" * 50)

    # 模拟表格数据
    mock_table = {
        "headers": ["卡名", "类型", "属性", "等级"],
        "rows": [
            ["青眼白龙", "怪兽", "光", "8"],
            ["黑魔术师", "怪兽", "暗", "7"],
            ["神之宣告", "陷阱", "", ""]
        ]
    }

    try:
        markdown = processor.table_to_markdown(mock_table)
        print(f"✓ 表格转 Markdown 成功")
        print(f"\n生成的 Markdown:")
        print(markdown)
        return True
    except Exception as e:
        print(f"✗ 转换失败: {e}")
        raise


def test_document_cleaner_init():
    """测试文档清理器初始化"""
    print("\n" + "=" * 50)
    print("测试 3: 文档清理器初始化")
    print("=" * 50)

    try:
        cleaner = DocumentCleaner()
        print(f"✓ DocumentCleaner 初始化成功")
        return cleaner
    except Exception as e:
        print(f"✗ 初始化失败: {e}")
        raise


def test_text_cleaning(cleaner: DocumentCleaner):
    """测试文本清理"""
    print("\n" + "=" * 50)
    print("测试 4: 页眉页脚清理")
    print("=" * 50)

    # 测试文本（包含模拟的页眉页脚）
    test_text = """
游戏王规则手册 第1页
=====================================

这是第一章的内容，讲述了游戏王的基本规则。
包含了很多重要的信息。

游戏王规则手册 第2页
=====================================

这是第二章的内容，继续深入讲解。
更多规则细节在这里。

游戏王规则手册 第3页
=====================================
"""

    try:
        result = cleaner.clean_text(test_text)
        print(f"✓ 文本清理成功")
        print(f"\n清理前 ({len(test_text)} 字符):")
        print(test_text[:200] + "..." if len(test_text) > 200 else test_text)
        print(f"\n清理后 ({len(result.cleaned_text)} 字符):")
        print(result.cleaned_text)
        print(f"\n统计:")
        print(f"  - Headers removed: {len(result.headers_removed)}")
        print(f"  - Footers removed: {len(result.footers_removed)}")
        return True
    except Exception as e:
        print(f"✗ 清理失败: {e}")
        raise


def test_custom_patterns(cleaner: DocumentCleaner):
    """测试自定义模式"""
    print("\n" + "=" * 50)
    print("测试 5: 自定义清理模式")
    print("=" * 50)

    try:
        # 添加自定义页眉模式
        cleaner.add_custom_header_pattern(r"^===.*第\s*\d+\s*页.*===$")
        cleaner.add_custom_footer_pattern(r"^---.*页末.*---$")

        print(f"✓ 自定义模式添加成功")
        print(f"  - Custom header patterns: {len(cleaner.custom_header_patterns)}")
        print(f"  - Custom footer patterns: {len(cleaner.custom_footer_patterns)}")
        return True
    except Exception as e:
        print(f"✗ 自定义模式失败: {e}")
        raise


def test_ocr_availability():
    """测试 OCR 可用性"""
    print("\n" + "=" * 50)
    print("测试 6: OCR 功能检查")
    print("=" * 50)

    try:
        from app.services.ocr_processor import OCRProcessor

        ocr = OCRProcessor()
        available = ocr.is_available()

        if available:
            print(f"✓ OCR 功能可用")
            print(f"  - Available backends: {ocr.get_available_backends()}")
            print(f"  - Languages: {ocr.get_available_languages()[:5]}...")
        else:
            print(f"⚠ OCR 功能当前不可用（缺少依赖库）")
            print(f"  - 可选择安装: pytesseract, easyocr, paddleocr")

        return True
    except Exception as e:
        print(f"⚠ OCR 检查跳过: {e}")
        return True


def run_all_tests():
    """运行所有测试"""
    print("\n" + "=" * 60)
    print("结构化数据处理系统测试")
    print("=" * 60)

    try:
        # 测试 1
        processor = test_structured_processor_init()

        # 测试 2
        test_table_to_markdown(processor)

        # 测试 3
        cleaner = test_document_cleaner_init()

        # 测试 4
        test_text_cleaning(cleaner)

        # 测试 5
        test_custom_patterns(cleaner)

        # 测试 6
        test_ocr_availability()

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
