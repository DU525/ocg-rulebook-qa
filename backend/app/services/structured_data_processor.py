import os
import re
from typing import List, Dict, Any, Optional
from dataclasses import dataclass
from pathlib import Path


@dataclass
class TableData:
    """表格数据类"""
    table_index: int
    headers: List[str]
    rows: List[List[str]]
    source: str
    page_number: Optional[int] = None


class StructuredDataProcessor:
    """结构化数据处理器：提取和处理表格数据"""

    def __init__(self):
        pass

    def extract_pdf_tables(self, file_path: str) -> List[TableData]:
        """
        从PDF文档中提取表格
        
        Args:
            file_path: PDF文件路径
            
        Returns:
            TableData列表
        """
        try:
            from pypdf import PdfReader
            tables = []
            reader = PdfReader(file_path)

            for page_num, page in enumerate(reader.pages):
                page_tables = self._extract_tables_from_pdf_page(page)
                for table_data in page_tables:
                    table_data.source = str(file_path)
                    table_data.page_number = page_num + 1
                    tables.append(table_data)

            return tables
        except ImportError:
            print("警告: 需要安装表格提取库，将使用基础方法")
            return []
        except Exception as e:
            print(f"PDF表格提取失败: {str(e)}")
            return []

    def _extract_tables_from_pdf_page(self, page) -> List[TableData]:
        """
        从PDF页面提取表格（基础实现）
        
        Args:
            page: PDF页面对象
            
        Returns:
            TableData列表
        """
        tables = []
        text = page.extract_text()
        lines = text.split('\n')

        # 尝试识别表格模式
        potential_tables = self._find_table_candidates(lines)

        for idx, table_candidate in enumerate(potential_tables):
            table_data = self._parse_table_candidate(table_candidate)
            if table_data:
                tables.append(TableData(
                    table_index=idx,
                    headers=table_data.get('headers', []),
                    rows=table_data.get('rows', []),
                    source="",
                    page_number=None
                ))

        return tables

    def _find_table_candidates(self, lines: List[str]) -> List[List[str]]:
        """
        查找可能的表格候选
        
        Args:
            lines: 文本行列表
            
        Returns:
            表格候选列表
        """
        candidates = []
        current_candidate = []

        for line in lines:
            # 检查是否有多个制表符或空格分隔符（表格特征）
            if self._has_multiple_separators(line):
                current_candidate.append(line)
            else:
                if len(current_candidate) >= 2:
                    candidates.append(current_candidate.copy())
                current_candidate = []

        if len(current_candidate) >= 2:
            candidates.append(current_candidate)

        return candidates

    def _has_multiple_separators(self, line: str) -> bool:
        """检查行是否有多个分隔符"""
        # 检查多个制表符
        if line.count('\t') >= 2:
            return True

        # 检查多个连续空格
        if len(re.findall(r'\s{3,}', line)) >= 2:
            return True

        # 检查竖线分隔符
        if line.count('|') >= 2:
            return True

        return False

    def _parse_table_candidate(self, lines: List[str]) -> Optional[Dict[str, Any]]:
        """
        解析表格候选
        
        Args:
            lines: 表格行列表
            
        Returns:
            包含headers和rows的字典
        """
        if not lines:
            return None

        headers = []
        rows = []

        # 尝试解析每一行
        for line in lines:
            cells = self._split_table_line(line)
            if len(cells) >= 2:
                if not headers:
                    headers = cells
                else:
                    rows.append(cells)

        if headers and len(rows) > 0:
            return {
                'headers': headers,
                'rows': rows
            }

        return None

    def _split_table_line(self, line: str) -> List[str]:
        """
        分割表格行中的单元格
        
        Args:
            line: 表格行文本
            
        Returns:
            单元格内容列表
        """
        # 尝试按竖线分割
        if '|' in line:
            cells = [cell.strip() for cell in line.split('|')]
            return [cell for cell in cells if cell]

        # 尝试按制表符分割
        if '\t' in line:
            return [cell.strip() for cell in line.split('\t')]

        # 尝试按多个空格分割
        cells = re.split(r'\s{3,}', line.strip())
        return [cell.strip() for cell in cells if cell.strip()]

    def extract_docx_tables(self, file_path: str) -> List[TableData]:
        """
        从Word文档中提取表格
        
        Args:
            file_path: DOCX文件路径
            
        Returns:
            TableData列表
        """
        try:
            from docx import Document
            tables = []
            doc = Document(file_path)

            for table_idx, table in enumerate(doc.tables):
                headers = []
                rows = []

                for row_idx, row in enumerate(table.rows):
                    cells = [cell.text.strip() for cell in row.cells]

                    if row_idx == 0:
                        headers = cells
                    else:
                        rows.append(cells)

                tables.append(TableData(
                    table_index=table_idx,
                    headers=headers,
                    rows=rows,
                    source=str(file_path),
                    page_number=None
                ))

            return tables
        except ImportError:
            print("警告: 需要安装python-docx库")
            return []
        except Exception as e:
            print(f"Word表格提取失败: {str(e)}")
            return []

    def table_to_markdown(self, table_data: TableData) -> str:
        """
        将表格数据转换为Markdown格式
        
        Args:
            table_data: 表格数据对象
            
        Returns:
            Markdown表格字符串
        """
        if not table_data.headers or not table_data.rows:
            return ""

        # 创建Markdown表格
        md_lines = []

        # 表头行
        header_line = "| " + " | ".join(table_data.headers) + " |"
        md_lines.append(header_line)

        # 分隔线
        separator_line = "| " + " | ".join(["---" for _ in table_data.headers]) + " |"
        md_lines.append(separator_line)

        # 数据行
        for row in table_data.rows:
            # 确保每行单元格数量与表头一致
            padded_row = row + [""] * (len(table_data.headers) - len(row))
            row_line = "| " + " | ".join(padded_row) + " |"
            md_lines.append(row_line)

        return "\n".join(md_lines)

    def extract_all_tables(self, file_path: str) -> Dict[str, List[TableData]]:
        """
        根据文件类型提取所有表格
        
        Args:
            file_path: 文件路径
            
        Returns:
            包含表格数据的字典
        """
        file_ext = Path(file_path).suffix.lower()

        if file_ext == '.pdf':
            return {
                'success': True,
                'tables': self.extract_pdf_tables(file_path),
                'type': 'pdf'
            }
        elif file_ext in ['.docx', '.doc']:
            return {
                'success': True,
                'tables': self.extract_docx_tables(file_path),
                'type': 'docx'
            }
        else:
            return {
                'success': False,
                'error': f'不支持的文件格式: {file_ext}',
                'tables': [],
                'type': 'unknown'
            }

    def process_tables_to_markdown(self, file_path: str) -> List[str]:
        """
        提取表格并转换为Markdown
        
        Args:
            file_path: 文件路径
            
        Returns:
            Markdown表格字符串列表
        """
        result = self.extract_all_tables(file_path)

        if not result['success']:
            return []

        markdown_tables = []
        for table_data in result['tables']:
            md_table = self.table_to_markdown(table_data)
            if md_table:
                markdown_tables.append(md_table)

        return markdown_tables
