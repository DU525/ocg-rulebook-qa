"""
结构化数据处理系统使用示例
================================

本示例展示了如何使用三个新创建的模块：
1. structured_data_processor - 表格提取和处理
2. ocr_processor - 图片OCR识别
3. document_cleaner - 页眉页脚清理
"""

from pathlib import Path


def example_structured_data_processor():
    """示例：使用 StructuredDataProcessor 提取和处理表格"""
    print("=== 表格提取和处理示例 ===\n")

    try:
        from structured_data_processor import StructuredDataProcessor

        processor = StructuredDataProcessor()

        # 示例1：从PDF提取表格
        # pdf_path = "your_document.pdf"
        # pdf_tables = processor.extract_pdf_tables(pdf_path)
        # print(f"从PDF提取到 {len(pdf_tables)} 个表格")

        # 示例2：从Word文档提取表格
        # docx_path = "your_document.docx"
        # docx_tables = processor.extract_docx_tables(docx_path)
        # print(f"从Word提取到 {len(docx_tables)} 个表格")

        # 示例3：转换表格为Markdown
        # if docx_tables:
        #     for i, table in enumerate(docx_tables):
        #         markdown = processor.table_to_markdown(table)
        #         print(f"\n表格 {i+1}:\n{markdown}")

        # 示例4：批量处理并获取Markdown
        # markdown_tables = processor.process_tables_to_markdown("your_file.pdf")
        # print(f"\n转换了 {len(markdown_tables)} 个表格为Markdown")

        print("✓ StructuredDataProcessor 已就绪")
        print("  - 支持PDF和Word文档表格提取")
        print("  - 支持表格转Markdown格式")
        print("  - 智能识别表格结构\n")

    except Exception as e:
        print(f"示例运行失败: {e}")


def example_ocr_processor():
    """示例：使用 OCRProcessor 进行图片文字识别"""
    print("=== 图片OCR识别示例 ===\n")

    try:
        from ocr_processor import OCRProcessor

        processor = OCRProcessor()

        # 检查OCR功能是否可用
        if processor.is_available():
            print("✓ OCR功能可用")
        else:
            print("⚠ OCR库未安装。请安装以下库之一：")
            print("  - pytesseract (需要Tesseract OCR引擎)")
            print("  - easyocr")
            print("  - paddleocr")

        # 显示可用语言
        languages = processor.get_available_languages()
        print(f"\n支持的语言: {', '.join(languages)}")

        # 示例1：处理单张图片
        # image_path = "your_image.png"
        # result = processor.process_image(image_path, language='chi_sim+eng')
        # print(f"\n识别文本:\n{result.text}")
        # print(f"置信度: {result.confidence:.2f}")

        # 示例2：批量处理图片
        # images = ["image1.png", "image2.png"]
        # results = processor.process_images_batch(images)
        # for path, result in results.items():
        #     print(f"{path}: {len(result.text)} 字符")

        # 示例3：从PDF提取图片并OCR
        # pdf_path = "your_document.pdf"
        # pdf_results = processor.process_pdf_images(pdf_path)
        # print(f"从PDF识别了 {len(pdf_results)} 张图片")

        print("\n✓ OCRProcessor 已就绪")
        print("  - 支持多种OCR库（Tesseract、EasyOCR、PaddleOCR）")
        print("  - 支持中英文识别")
        print("  - 支持从PDF提取图片识别\n")

    except Exception as e:
        print(f"示例运行失败: {e}")


def example_document_cleaner():
    """示例：使用 DocumentCleaner 清理页眉页脚"""
    print("=== 文档清理示例 ===\n")

    try:
        from document_cleaner import DocumentCleaner

        cleaner = DocumentCleaner()

        # 示例1：清理纯文本
        sample_text = """文档标题
        机密
        这是正文内容...
        第一段落...
        第二段落...
        第 1 页
        """

        result = cleaner.clean_text(sample_text, source="示例文档")
        print(f"原始文本:\n{result.original_text}")
        print(f"\n清理后文本:\n{result.cleaned_text}")
        if result.removed_header:
            print(f"\n移除的页眉: {result.removed_header}")
        if result.removed_footer:
            print(f"移除的页脚: {result.removed_footer}")
        print(f"移除行数: {len(result.removed_lines)}")

        # 示例2：清理PDF文档
        # pdf_path = "your_document.pdf"
        # clean_result = cleaner.clean_file(pdf_path)
        # if clean_result['success']:
        #     print(f"清理完成，移除了 {clean_result['total_removed_lines']} 行")

        # 示例3：添加自定义模式
        # cleaner.add_custom_header_pattern(r'^公司内部文档.*$')
        # cleaner.add_custom_footer_pattern(r'^内部使用.*$')

        print("\n✓ DocumentCleaner 已就绪")
        print("  - 智能检测页眉页脚")
        print("  - 识别重复出现的模式")
        print("  - 支持自定义模式")
        print("  - 支持PDF、DOCX、TXT格式\n")

    except Exception as e:
        print(f"示例运行失败: {e}")


def example_combined_usage():
    """示例：综合使用所有模块"""
    print("=== 综合使用示例 ===\n")

    try:
        from structured_data_processor import StructuredDataProcessor
        from ocr_processor import OCRProcessor
        from document_cleaner import DocumentCleaner

        # 初始化所有处理器
        table_processor = StructuredDataProcessor()
        ocr_processor = OCRProcessor()
        doc_cleaner = DocumentCleaner()

        print("""
综合处理流程示例：
-------------------

1. 清理文档（移除页眉页脚）
   result = doc_cleaner.clean_file("document.pdf")

2. 提取表格
   tables = table_processor.extract_pdf_tables("document.pdf")
   for table in tables:
       markdown = table_processor.table_to_markdown(table)

3. OCR识别图片（如果需要）
   if ocr_processor.is_available():
       ocr_results = ocr_processor.process_pdf_images("document.pdf")

4. 整合处理后的数据用于RAG系统
""")

        print("✓ 所有模块已就绪，可配合使用！")

    except Exception as e:
        print(f"示例运行失败: {e}")


if __name__ == "__main__":
    print("=" * 60)
    print("结构化数据处理系统 - 使用示例")
    print("=" * 60 + "\n")

    example_structured_data_processor()
    example_ocr_processor()
    example_document_cleaner()
    example_combined_usage()

    print("=" * 60)
    print("提示：请取消注释相关代码并传入真实文件路径进行测试")
    print("=" * 60)
