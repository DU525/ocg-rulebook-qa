"""BM25关键词检索引擎 - 基于Whoosh构建，支持降级方案

功能：
- 使用Whoosh库构建BM25索引（轻量级，适合12万文档）
- 降级方案：jieba.analyse.extract_tags（Whoosh不可用时）
- 文档分词使用jieba分词器
- 支持关键词搜索、短语搜索（带引号）、布尔搜索（AND/OR）
- BM25参数优化：k1=1.5, b=0.75
- 增量更新机制（支持新文档添加而不重建索引）
- 索引重建功能

数据源：
- data/chunks/ocg_rules_chunks.json
- data/chunks/dm_rules_chunks.json

索引路径：
- data/indexes/bm25_index/
"""
import os
import re
import json
import shutil
import logging
import importlib
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

logger = logging.getLogger(__name__)


class JiebaAnalyzer:
    """jieba自定义分析器，适配Whoosh

    使用jieba进行中文分词，支持停用词过滤。
    Whoosh默认不支持中文分词，需要自定义Analyzer。
    """

    def __init__(self, stopwords: Optional[set] = None):
        """初始化jieba分析器

        Args:
            stopwords: 停用词集合，如果为None则使用默认停用词
        """
        try:
            import jieba
            self.jieba = jieba
        except ImportError:
            raise ImportError("jieba库未安装，请运行: pip install jieba")

        self.stopwords = stopwords or self._default_stopwords()

    @staticmethod
    def _default_stopwords() -> set:
        """返回默认中文停用词集合"""
        return {
            '的', '了', '在', '是', '我', '有', '和', '就', '不', '人', '都',
            '一', '一个', '上', '也', '很', '到', '说', '要', '去', '你',
            '会', '着', '没有', '看', '好', '自己', '这', '那', '么', '吗',
            '呢', '啊', '哦', '吧', '呀', '吧', '嗯', '唉', '之', '与',
            '及', '等', '其', '而', '但', '如果', '这个', '那个', '什么',
        }

    def __call__(self, text: str):
        """分词生成器，供Whoosh调用

        Args:
            text: 待分词的文本

        Yields:
            str: 分词后的token
        """
        if not text:
            return

        words = self.jieba.cut(text)
        for word in words:
            word = word.strip().lower()
            if word and word not in self.stopwords and len(word) > 0:
                yield word


class BM25Engine:
    """BM25关键词检索引擎

    基于Whoosh实现，支持：
    - 关键词搜索：直接搜索关键词
    - 短语搜索：使用双引号包裹，如 "连锁处理"
    - 布尔搜索：使用AND/OR连接，如 连锁 AND 效果

    BM25参数：
    - k1=1.5: 控制词频饱和点
    - b=0.75: 控制文档长度归一化
    """

    BM25_K1 = 1.5
    BM25_B = 0.75
    PROGRESS_INTERVAL = 10000

    def __init__(
        self,
        index_dir: Optional[str] = None,
        chunks_files: Optional[List[str]] = None,
        use_fallback: bool = False,
    ):
        """初始化BM25引擎

        Args:
            index_dir: 索引存储目录，默认为 data/indexes/bm25_index/
            chunks_files: 文档分块JSON文件路径列表
            use_fallback: 是否强制使用降级方案
        """
        self.project_root = self._find_project_root()
        self.index_dir = index_dir or os.path.join(
            self.project_root, 'data', 'indexes', 'bm25_index'
        )
        self.chunks_files = chunks_files or self._default_chunks_files()
        self.use_fallback = use_fallback
        self.index = None
        self.schema = None
        self.analyzer = None
        self._whoosh_available = False

        self._load_or_build_index()

    def _find_project_root(self) -> str:
        """查找项目根目录

        Returns:
            str: 项目根目录路径
        """
        current = os.path.dirname(os.path.abspath(__file__))
        for _ in range(5):
            if os.path.exists(os.path.join(current, 'data')):
                return current
            parent = os.path.dirname(current)
            if parent == current:
                break
            current = parent
        return os.path.dirname(os.path.abspath(__file__))

    def _default_chunks_files(self) -> List[str]:
        """返回默认的数据源文件列表

        Returns:
            List[str]: JSON文件路径列表
        """
        data_dir = os.path.join(self.project_root, 'data', 'chunks')
        return [
            os.path.join(data_dir, 'ocg_rules_chunks.json'),
            os.path.join(data_dir, 'dm_rules_chunks.json'),
        ]

    def _check_whoosh_available(self) -> bool:
        """检查Whoosh是否可用

        Returns:
            bool: True表示Whoosh可用，False表示不可用
        """
        if self.use_fallback:
            return False

        try:
            import whoosh
            from whoosh.index import create_in, open_dir
            from whoosh.fields import Schema, TEXT, ID
            from whoosh.qparser import QueryParser, MultifieldParser
            from whoosh.analysis import StemmingAnalyzer
            from whoosh.scoring import BM25F
            from whoosh.searching import Results
            self._whoosh_available = True
            return True
        except ImportError:
            logger.warning("Whoosh库未安装，将使用jieba降级方案")
            self._whoosh_available = False
            return False

    def _load_or_build_index(self):
        """加载已有索引或构建新索引

        优先尝试加载Whoosh索引，如果失败则使用降级方案。
        """
        if not self._check_whoosh_available():
            logger.info("使用jieba降级方案进行关键词检索")
            self._init_fallback()
            return

        try:
            if os.path.exists(self.index_dir):
                from whoosh.index import open_dir
                self.index = open_dir(self.index_dir)
                self.schema = self.index.schema
                logger.info(f"已加载BM25索引: {self.index_dir}")
                print(f"Loaded BM25 index from {self.index_dir} "
                      f"(文档数: {self.index.doc_count()})")
                return
        except Exception as e:
            logger.warning(f"加载BM25索引失败: {e}，将重建索引")
            self.index = None

        self._build_index()

    def _build_index(self):
        """构建BM25索引

        从数据源读取文档分块，分词后构建Whoosh BM25索引。
        每10000条文档打印一次进度。
        """
        if not self._whoosh_available:
            self._build_fallback_index()
            return

        try:
            from whoosh.index import create_in
            from whoosh.fields import Schema, TEXT, ID, KEYWORD
            from whoosh.scoring import BM25F
            from whoosh.analysis import RegexAnalyzer
        except ImportError:
            logger.error("Whoosh导入失败")
            self._init_fallback()
            return

        all_chunks = self._load_chunks()
        if not all_chunks:
            logger.warning("没有找到文档数据，跳过索引构建")
            return

        print(f"开始构建BM25索引，共 {len(all_chunks)} 个文档...")

        schema = Schema(
            id=ID(stored=True, unique=True),
            content=TEXT(
                stored=True,
                analyzer=self._get_jieba_analyzer(),
                field_boost=1.0,
            ),
            title=TEXT(stored=True, analyzer=self._get_jieba_analyzer()),
            source=TEXT(stored=True, analyzer=self._get_jieba_analyzer()),
            chapter=TEXT(stored=True, analyzer=self._get_jieba_analyzer()),
            section=TEXT(stored=True, analyzer=self._get_jieba_analyzer()),
        )
        self.schema = schema

        os.makedirs(self.index_dir, exist_ok=True)
        self.index = create_in(self.index_dir, schema)

        writer = self.index.writer()

        for i, chunk in enumerate(all_chunks):
            metadata = chunk.get('metadata', {})
            writer.add_document(
                id=str(chunk.get('id', f'doc_{i}')),
                content=chunk.get('content', ''),
                title=metadata.get('title', ''),
                source=metadata.get('source', ''),
                chapter=metadata.get('chapter', ''),
                section=metadata.get('section', ''),
            )

            if (i + 1) % self.PROGRESS_INTERVAL == 0:
                progress = (i + 1) / len(all_chunks) * 100
                print(f"  索引进度: {i + 1}/{len(all_chunks)} ({progress:.1f}%)")

        writer.commit()

        print(f"BM25索引构建完成，共 {len(all_chunks)} 个文档")
        self._print_index_stats()

    def _get_jieba_analyzer(self):
        """获取或创建jieba分析器

        Returns:
            JiebaAnalyzer: jieba分词器实例
        """
        if self.analyzer is None:
            self.analyzer = JiebaAnalyzer()
        return self.analyzer

    def _load_chunks(self) -> List[Dict]:
        """从所有数据源加载文档分块

        Returns:
            List[Dict]: 文档分块列表
        """
        all_chunks = []
        seen_ids = set()

        for file_path in self.chunks_files:
            if not os.path.exists(file_path):
                logger.warning(f"数据文件不存在: {file_path}")
                continue

            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    chunks = json.load(f)

                for chunk in chunks:
                    chunk_id = chunk.get('id')
                    if chunk_id and chunk_id not in seen_ids:
                        all_chunks.append(chunk)
                        seen_ids.add(chunk_id)

                print(f"  加载 {file_path}: {len(chunks)} 个文档")
            except Exception as e:
                logger.error(f"加载文件 {file_path} 失败: {e}")

        print(f"共加载 {len(all_chunks)} 个唯一文档")
        return all_chunks

    def _print_index_stats(self):
        """打印索引统计信息"""
        if self.index is None:
            return

        try:
            doc_count = self.index.doc_count()
            index_size = self._get_index_size()
            print(f"  索引文档数: {doc_count}")
            print(f"  索引大小: {index_size:.2f} MB")

            if index_size > 200:
                logger.warning(f"索引大小 ({index_size:.2f} MB) 超过200MB限制")
        except Exception as e:
            logger.warning(f"获取索引统计信息失败: {e}")

    def _get_index_size(self) -> float:
        """获取索引目录大小（MB）

        Returns:
            float: 索引大小（MB）
        """
        total_size = 0
        if os.path.exists(self.index_dir):
            for dirpath, dirnames, filenames in os.walk(self.index_dir):
                for filename in filenames:
                    file_path = os.path.join(dirpath, filename)
                    try:
                        total_size += os.path.getsize(file_path)
                    except OSError:
                        pass
        return total_size / (1024 * 1024)

    def search(
        self,
        query: str,
        top_k: int = 5,
        search_type: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """BM25关键词搜索

        支持三种搜索模式：
        1. 关键词搜索：直接搜索关键词，如 "连锁"
        2. 短语搜索：使用双引号包裹，如 "连锁处理"
        3. 布尔搜索：使用AND/OR连接，如 "连锁 AND 效果"

        Args:
            query: 搜索查询字符串
            top_k: 返回结果数量
            search_type: 搜索类型 ('keyword', 'phrase', 'boolean')，
                         如果为None则自动检测

        Returns:
            List[Dict]: 搜索结果列表，每个结果包含:
                - id: 文档ID
                - content: 文档内容
                - metadata: 文档元数据
                - score: BM25相关性分数
        """
        if not query or not query.strip():
            return []

        if self._whoosh_available and not self.use_fallback:
            return self._whoosh_search(query, top_k, search_type)
        else:
            return self._fallback_search(query, top_k)

    def _whoosh_search(
        self,
        query: str,
        top_k: int,
        search_type: Optional[str],
    ) -> List[Dict[str, Any]]:
        """使用Whoosh执行BM25搜索

        Args:
            query: 搜索查询
            top_k: 返回结果数量
            search_type: 搜索类型

        Returns:
            List[Dict]: 搜索结果
        """
        try:
            from whoosh.qparser import QueryParser, MultifieldParser
            from whoosh.scoring import BM25F
            from whoosh.analysis import RegexAnalyzer
        except ImportError:
            return self._fallback_search(query, top_k)

        if self.index is None:
            logger.warning("BM25索引未初始化")
            return []

        try:
            with self.index.searcher(
                weighting=BM25F(k1=self.BM25_K1, b=self.BM25_B)
            ) as searcher:
                detected_type = search_type or self._detect_query_type(query)
                query_obj = self._parse_query(query, detected_type)

                if query_obj is None:
                    return []

                results = searcher.search(
                    query_obj,
                    limit=top_k,
                )

                return self._format_results(results)
        except Exception as e:
            logger.error(f"BM25搜索失败: {e}")
            return self._fallback_search(query, top_k)

    def _detect_query_type(self, query: str) -> str:
        """自动检测查询类型

        Args:
            query: 搜索查询

        Returns:
            str: 'phrase', 'boolean', 或 'keyword'
        """
        if query.startswith('"') and query.endswith('"'):
            return 'phrase'

        if re.search(r'\bAND\b|\bOR\b|\bNOT\b', query, re.IGNORECASE):
            return 'boolean'

        return 'keyword'

    def _parse_query(self, query: str, query_type: str):
        """解析搜索查询为Whoosh查询对象

        Args:
            query: 搜索查询
            query_type: 查询类型

        Returns:
            Whoosh Query对象
        """
        try:
            from whoosh.qparser import QueryParser, MultifieldParser
            from whoosh.analysis import RegexAnalyzer
        except ImportError:
            return None

        search_fields = ['content', 'title', 'source', 'chapter', 'section']

        try:
            if query_type == 'phrase':
                phrase = query.strip('"')
                parser = MultifieldParser(
                    ['content'],
                    schema=self.schema,
                )
                return parser.parse(f'"{phrase}"')

            elif query_type == 'boolean':
                parser = MultifieldParser(
                    search_fields,
                    schema=self.schema,
                )
                return parser.parse(query)

            else:
                parser = MultifieldParser(
                    search_fields,
                    schema=self.schema,
                )
                return parser.parse(query)
        except Exception as e:
            logger.warning(f"查询解析失败: {e}，尝试简单解析")
            try:
                parser = QueryParser(
                    'content',
                    schema=self.schema,
                )
                return parser.parse(query)
            except Exception:
                return None

    def _format_results(self, results) -> List[Dict[str, Any]]:
        """格式化Whoosh搜索结果

        Args:
            results: Whoosh搜索结果对象

        Returns:
            List[Dict]: 格式化后的结果
        """
        formatted = []
        for hit in results:
            metadata = {}
            for field in ['title', 'source', 'chapter', 'section']:
                value = hit.get(field)
                if value:
                    metadata[field] = value

            formatted.append({
                'id': hit.get('id', ''),
                'content': hit.get('content', ''),
                'metadata': metadata,
                'score': float(hit.score),
            })

        return formatted

    def add_document(self, document: Dict):
        """增量添加单个文档到索引

        支持在不重建索引的情况下添加新文档。

        Args:
            document: 文档字典，包含:
                - id: 文档唯一标识
                - content: 文档内容
                - metadata: 元数据字典（可选包含title, source, chapter, section）
        """
        if self._whoosh_available and not self.use_fallback:
            self._whoosh_add_document(document)
        else:
            self._fallback_add_document(document)

    def _whoosh_add_document(self, document: Dict):
        """使用Whoosh增量添加文档"""
        if self.index is None:
            logger.warning("索引未初始化，无法添加文档")
            return

        try:
            metadata = document.get('metadata', {})
            with self.index.writer() as writer:
                writer.update_document(
                    id=str(document.get('id', '')),
                    content=document.get('content', ''),
                    title=metadata.get('title', ''),
                    source=metadata.get('source', ''),
                    chapter=metadata.get('chapter', ''),
                    section=metadata.get('section', ''),
                )
            logger.debug(f"文档已添加: {document.get('id')}")
        except Exception as e:
            logger.error(f"添加文档失败: {e}")

    def add_documents(self, documents: List[Dict]):
        """批量增量添加文档

        Args:
            documents: 文档列表
        """
        if self._whoosh_available and not self.use_fallback:
            if self.index is None:
                logger.warning("索引未初始化，无法添加文档")
                return

            try:
                with self.index.writer() as writer:
                    for doc in documents:
                        metadata = doc.get('metadata', {})
                        writer.update_document(
                            id=str(doc.get('id', '')),
                            content=doc.get('content', ''),
                            title=metadata.get('title', ''),
                            source=metadata.get('source', ''),
                            chapter=metadata.get('chapter', ''),
                            section=metadata.get('section', ''),
                        )
                logger.info(f"批量添加 {len(documents)} 个文档完成")
            except Exception as e:
                logger.error(f"批量添加文档失败: {e}")
        else:
            for doc in documents:
                self._fallback_add_document(doc)

    def rebuild_index(self):
        """重建BM25索引

        删除现有索引并从头构建。
        适用于索引损坏或需要完全更新的情况。
        """
        print("开始重建BM25索引...")

        if os.path.exists(self.index_dir):
            try:
                shutil.rmtree(self.index_dir)
                print(f"已删除旧索引: {self.index_dir}")
            except Exception as e:
                logger.error(f"删除旧索引失败: {e}")

        self.index = None
        self.analyzer = None
        self._build_index()

    def get_stats(self) -> Dict[str, Any]:
        """获取索引统计信息

        Returns:
            Dict: 统计信息字典
        """
        stats = {
            'engine': 'BM25',
            'whoosh_available': self._whoosh_available,
            'use_fallback': self.use_fallback,
        }

        if self._whoosh_available and self.index is not None:
            try:
                stats['doc_count'] = self.index.doc_count()
                stats['index_size_mb'] = round(self._get_index_size(), 2)
                stats['index_dir'] = self.index_dir
            except Exception as e:
                stats['error'] = str(e)
        elif self.use_fallback:
            stats['doc_count'] = len(getattr(self, '_fallback_docs', []))
            stats['mode'] = 'fallback (jieba)'

        return stats

    def _init_fallback(self):
        """初始化降级方案（基于jieba）"""
        try:
            import jieba.analyse
            self._fallback_docs = []
            self._fallback_index = {}
            self._load_fallback_data()
            print(f"降级方案初始化完成，共 {len(self._fallback_docs)} 个文档")
        except ImportError:
            logger.error("jieba库未安装，无法使用降级方案")
            self._fallback_docs = []
            self._fallback_index = {}

    def _build_fallback_index(self):
        """构建降级方案索引"""
        self._init_fallback()

    def _load_fallback_data(self):
        """加载数据到降级方案"""
        self._fallback_docs = self._load_chunks()
        self._build_fallback_search_index()

    def _build_fallback_search_index(self):
        """构建基于TF-IDF的降级搜索索引"""
        try:
            import jieba.analyse
        except ImportError:
            return

        for i, doc in enumerate(self._fallback_docs):
            content = doc.get('content', '')
            try:
                keywords = jieba.analyse.extract_tags(content, topK=20)
                self._fallback_index[i] = {
                    'doc_id': doc.get('id', ''),
                    'keywords': keywords,
                    'content': content,
                    'metadata': doc.get('metadata', {}),
                }
            except Exception:
                pass

    def _fallback_search(
        self,
        query: str,
        top_k: int,
    ) -> List[Dict[str, Any]]:
        """使用降级方案进行搜索

        Args:
            query: 搜索查询
            top_k: 返回结果数量

        Returns:
            List[Dict]: 搜索结果
        """
        try:
            import jieba.analyse
        except ImportError:
            return []

        query_keywords = set()
        try:
            query_keywords = set(
                jieba.analyse.extract_tags(query, topK=20)
            )
        except Exception:
            query_keywords = set(jieba.cut(query))

        if not query_keywords:
            return []

        scored_docs = []
        for idx, doc_info in self._fallback_index.items():
            doc_keywords = set(doc_info.get('keywords', []))
            overlap = query_keywords & doc_keywords

            if overlap:
                score = len(overlap) / len(query_keywords)

                content = doc_info.get('content', '')
                content_lower = content.lower()
                for kw in query_keywords:
                    if kw in content_lower:
                        score += 0.5

                scored_docs.append({
                    'id': doc_info.get('doc_id', ''),
                    'content': content,
                    'metadata': doc_info.get('metadata', {}),
                    'score': round(score, 4),
                })

        scored_docs.sort(key=lambda x: x['score'], reverse=True)
        return scored_docs[:top_k]

    def _fallback_add_document(self, document: Dict):
        """降级方案：添加文档"""
        try:
            import jieba.analyse
        except ImportError:
            return

        doc_index = len(self._fallback_docs)
        self._fallback_docs.append(document)

        content = document.get('content', '')
        try:
            keywords = jieba.analyse.extract_tags(content, topK=20)
            self._fallback_index[doc_index] = {
                'doc_id': document.get('id', ''),
                'keywords': keywords,
                'content': content,
                'metadata': document.get('metadata', {}),
            }
        except Exception:
            pass
