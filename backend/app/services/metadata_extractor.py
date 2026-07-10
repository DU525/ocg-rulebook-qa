import os
import re
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple
from dataclasses import dataclass, field
from enum import Enum


class DocumentType(Enum):
    """文档类型枚举"""
    RST = "rst"
    MARKDOWN = "markdown"
    PDF = "pdf"
    DOCX = "docx"
    TXT = "txt"
    HTML = "html"
    UNKNOWN = "unknown"


@dataclass
class DocumentMetadata:
    """文档元数据 dataclass"""
    doc_type: DocumentType
    title: str = ""
    author: str = ""
    date: str = ""
    version: str = ""
    language: str = "zh"
    page_count: int = 0
    sections: List[str] = field(default_factory=list)
    chapters: List[str] = field(default_factory=list)
    keywords: List[str] = field(default_factory=list)
    extra: Dict[str, Any] = field(default_factory=dict)


@dataclass
class ChunkMetadata:
    """块元数据 dataclass，支持父子关系"""
    parent_id: Optional[str] = None
    chunk_index: int = 0
    page_number: Optional[int] = None
    chapter: str = ""
    section: str = ""
    subsection: str = ""
    level: int = 0
    heading: str = ""
    extra: Dict[str, Any] = field(default_factory=dict)


class MetadataExtractor:
    """元数据提取器"""

    def __init__(self):
        self.supported_extensions = {
            '.rst': DocumentType.RST,
            '.md': DocumentType.MARKDOWN,
            '.markdown': DocumentType.MARKDOWN,
            '.pdf': DocumentType.PDF,
            '.docx': DocumentType.DOCX,
            '.doc': DocumentType.DOCX,
            '.txt': DocumentType.TXT,
            '.html': DocumentType.HTML,
            '.htm': DocumentType.HTML
        }

    def identify_document_type(self, file_path: str) -> DocumentType:
        """
        识别文档类型
        
        Args:
            file_path: 文档文件路径
            
        Returns:
            DocumentType 枚举值
        """
        ext = Path(file_path).suffix.lower()
        return self.supported_extensions.get(ext, DocumentType.UNKNOWN)

    def extract_document_metadata(self, file_path: str) -> DocumentMetadata:
        """
        提取文档级元数据
        
        Args:
            file_path: 文档文件路径
            
        Returns:
            DocumentMetadata 对象
        """
        doc_type = self.identify_document_type(file_path)
        metadata = DocumentMetadata(doc_type=doc_type)
        
        # 提取文件名作为默认标题
        metadata.title = Path(file_path).stem
        
        try:
            if doc_type == DocumentType.RST:
                self._extract_rst_metadata(file_path, metadata)
            elif doc_type == DocumentType.MARKDOWN:
                self._extract_markdown_metadata(file_path, metadata)
            elif doc_type == DocumentType.PDF:
                self._extract_pdf_metadata(file_path, metadata)
            elif doc_type == DocumentType.DOCX:
                self._extract_docx_metadata(file_path, metadata)
            elif doc_type == DocumentType.TXT:
                self._extract_txt_metadata(file_path, metadata)
            elif doc_type == DocumentType.HTML:
                self._extract_html_metadata(file_path, metadata)
        except Exception as e:
            metadata.extra['extraction_error'] = str(e)
        
        return metadata

    def _extract_rst_metadata(self, file_path: str, metadata: DocumentMetadata) -> None:
        """提取 RST 文档元数据"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 提取标题
        title_match = re.search(r'^(.+?)\n[=]+', content, re.MULTILINE)
        if title_match:
            metadata.title = title_match.group(1).strip()
        
        # 提取章节
        sections = re.findall(r'^(.+?)\n[-]+\s*$', content, re.MULTILINE)
        metadata.sections = [s.strip() for s in sections if s.strip()]
        
        chapters = re.findall(r'^(.+?)\n[=]+\s*$', content, re.MULTILINE)
        metadata.chapters = [c.strip() for c in chapters if c.strip()]
        
        # 提取版本信息
        version_match = re.search(r':Version:\s*(.+)', content)
        if version_match:
            metadata.version = version_match.group(1).strip()
        
        # 提取作者
        author_match = re.search(r':Author:\s*(.+)', content)
        if author_match:
            metadata.author = author_match.group(1).strip()
        
        # 提取日期
        date_match = re.search(r':Date:\s*(.+)', content)
        if date_match:
            metadata.date = date_match.group(1).strip()

    def _extract_markdown_metadata(self, file_path: str, metadata: DocumentMetadata) -> None:
        """提取 Markdown 文档元数据"""
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()
        
        # 提取 frontmatter
        frontmatter_match = re.match(r'^---\s*\n(.*?)\n---\s*\n', content, re.DOTALL)
        if frontmatter_match:
            frontmatter = frontmatter_match.group(1)
            title_match = re.search(r'title:\s*(.+)', frontmatter, re.IGNORECASE)
            if title_match:
                metadata.title = title_match.group(1).strip().strip('"\'')
            
            author_match = re.search(r'author:\s*(.+)', frontmatter, re.IGNORECASE)
            if author_match:
                metadata.author = author_match.group(1).strip().strip('"\'')
            
            date_match = re.search(r'date:\s*(.+)', frontmatter, re.IGNORECASE)
            if date_match:
                metadata.date = date_match.group(1).strip().strip('"\'')
            
            version_match = re.search(r'version:\s*(.+)', frontmatter, re.IGNORECASE)
            if version_match:
                metadata.version = version_match.group(1).strip().strip('"\'')
        
        # 提取一级标题
        h1_match = re.search(r'^#\s+(.+)', content, re.MULTILINE)
        if h1_match and not metadata.title:
            metadata.title = h1_match.group(1).strip()
        
        # 提取章节
        h2_sections = re.findall(r'^##\s+(.+)', content, re.MULTILINE)
        metadata.sections = [s.strip() for s in h2_sections]
        
        h1_chapters = re.findall(r'^#\s+(.+)', content, re.MULTILINE)
        metadata.chapters = [c.strip() for c in h1_chapters]

    def _extract_pdf_metadata(self, file_path: str, metadata: DocumentMetadata) -> None:
        """提取 PDF 文档元数据"""
        try:
            from pypdf import PdfReader
            reader = PdfReader(file_path)
            
            if reader.metadata:
                if reader.metadata.title:
                    metadata.title = reader.metadata.title
                if reader.metadata.author:
                    metadata.author = reader.metadata.author
                if reader.metadata.subject:
                    metadata.extra['subject'] = reader.metadata.subject
                if reader.metadata.producer:
                    metadata.extra['producer'] = reader.metadata.producer
            
            metadata.page_count = len(reader.pages)
        except ImportError:
            metadata.extra['warning'] = 'pypdf not available'

    def _extract_docx_metadata(self, file_path: str, metadata: DocumentMetadata) -> None:
        """提取 DOCX 文档元数据"""
        try:
            from docx import Document
            doc = Document(file_path)
            
            core_props = doc.core_properties
            if core_props.title:
                metadata.title = core_props.title
            if core_props.author:
                metadata.author = core_props.author
            if core_props.subject:
                metadata.extra['subject'] = core_props.subject
            if core_props.created:
                metadata.date = str(core_props.created)
            if core_props.version:
                metadata.version = core_props.version
            
            # 提取标题
            for para in doc.paragraphs:
                if para.style.name.startswith('Heading 1') and para.text.strip():
                    if not metadata.title:
                        metadata.title = para.text.strip()
                    metadata.chapters.append(para.text.strip())
                elif para.style.name.startswith('Heading 2') and para.text.strip():
                    metadata.sections.append(para.text.strip())
        except ImportError:
            metadata.extra['warning'] = 'python-docx not available'

    def _extract_txt_metadata(self, file_path: str, metadata: DocumentMetadata) -> None:
        """提取 TXT 文档元数据"""
        with open(file_path, 'r', encoding='utf-8') as f:
            lines = f.readlines()
        
        # 尝试从第一行提取标题
        for line in lines[:10]:
            line = line.strip()
            if line and len(line) < 100:
                if not metadata.title:
                    metadata.title = line
                break
        
        # 提取可能的章节标题
        for line in lines:
            line = line.strip()
            if line and len(line) < 200:
                # 检查是否是章节标题模式
                if re.match(r'^第[一二三四五六七八九十百]+[章节条]', line) or \
                   re.match(r'^\d+(\.\d+)*\s+', line):
                    metadata.sections.append(line)

    def _extract_html_metadata(self, file_path: str, metadata: DocumentMetadata) -> None:
        """提取 HTML 文档元数据"""
        try:
            from bs4 import BeautifulSoup
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            soup = BeautifulSoup(content, 'html.parser')
            
            title_tag = soup.find('title')
            if title_tag:
                metadata.title = title_tag.string.strip()
            
            # 提取 meta 标签
            for meta in soup.find_all('meta'):
                if meta.get('name') == 'author':
                    metadata.author = meta.get('content', '').strip()
                elif meta.get('name') == 'keywords':
                    keywords = meta.get('content', '').split(',')
                    metadata.keywords = [k.strip() for k in keywords if k.strip()]
                elif meta.get('name') == 'description':
                    metadata.extra['description'] = meta.get('content', '').strip()
            
            # 提取标题
            for h1 in soup.find_all('h1'):
                if h1.text.strip():
                    metadata.chapters.append(h1.text.strip())
            
            for h2 in soup.find_all('h2'):
                if h2.text.strip():
                    metadata.sections.append(h2.text.strip())
        except ImportError:
            metadata.extra['warning'] = 'beautifulsoup4 not available'

    def extract_heading_info(self, text: str, doc_type: DocumentType) -> Tuple[str, int]:
        """
        从文本中提取标题信息
        
        Args:
            text: 文本内容
            doc_type: 文档类型
            
        Returns:
            (标题文本, 标题级别) 元组
        """
        if doc_type == DocumentType.RST:
            return self._extract_rst_heading(text)
        elif doc_type == DocumentType.MARKDOWN:
            return self._extract_markdown_heading(text)
        elif doc_type in [DocumentType.TXT, DocumentType.HTML]:
            return self._extract_generic_heading(text)
        return ("", 0)

    def _extract_rst_heading(self, text: str) -> Tuple[str, int]:
        """提取 RST 标题"""
        lines = text.strip().split('\n')
        if len(lines) >= 2:
            heading_line = lines[0]
            underline = lines[1]
            
            if set(underline) in [set('='), set('-'), set('^'), set('"'), set("'")]:
                level_map = {'=': 1, '-': 2, '^': 3, '"': 4, "'": 5}
                level = level_map.get(underline[0], 1)
                return (heading_line.strip(), level)
        return ("", 0)

    def _extract_markdown_heading(self, text: str) -> Tuple[str, int]:
        """提取 Markdown 标题"""
        match = re.match(r'^(#{1,6})\s+(.+)', text.strip())
        if match:
            level = len(match.group(1))
            heading = match.group(2).strip()
            return (heading, level)
        return ("", 0)

    def _extract_generic_heading(self, text: str) -> Tuple[str, int]:
        """提取通用标题"""
        lines = text.strip().split('\n')
        if lines:
            first_line = lines[0].strip()
            # 检查中文章节模式
            if re.match(r'^第[一二三四五六七八九十百]+[章节条]', first_line):
                return (first_line, 1)
            # 检查数字章节模式
            if re.match(r'^\d+(\.\d+)*\s+', first_line):
                level = first_line.count('.') + 1
                return (first_line, min(level, 6))
        return ("", 0)
