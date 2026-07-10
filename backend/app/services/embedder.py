"""
[DEPRECATED] 文本搜索 - 使用关键词匹配作为向量搜索的后备

VectorStore 已迁移至纯 FAISS 后端，不再依赖 TextSearcher 作为后备方案。
此模块保留供其他脚本（如 test_search.py）使用，新代码请使用 VectorRAG 系统。
"""
import os
import re
from typing import List, Dict, Any
import json

class TextSearcher:
    """基于关键词的文本搜索器 - 作为向量搜索的后备方案"""

    def __init__(self, chunks_file: str = None):
        self.chunks_file = chunks_file
        self.chunks = []
        self._load_chunks()

    def _load_chunks(self):
        """加载文档块"""
        if self.chunks_file and os.path.exists(self.chunks_file):
            with open(self.chunks_file, 'r', encoding='utf-8') as f:
                self.chunks = json.load(f)

    def search(self, query: str, top_k: int = 5) -> List[Dict[str, Any]]:
        """关键词搜索相关文档"""
        if not self.chunks:
            return []

        query_words = self._tokenize(query)
        if not query_words:
            return self.chunks[:top_k]

        results = []
        for chunk in self.chunks:
            content = chunk.get('content', '')
            chunk_words = self._tokenize(content)

            # 计算匹配分数
            score = sum(1 for w in query_words if w in chunk_words)

            if score > 0:
                results.append({
                    'content': content,
                    'metadata': chunk.get('metadata', {}),
                    'score': score
                })

        # 按分数排序
        results.sort(key=lambda x: x['score'], reverse=True)
        return results[:top_k]

    def _tokenize(self, text: str) -> set:
        """简单分词 - 支持中英文"""
        text = text.lower()
        # Match Chinese characters and English words
        chinese_chars = re.findall(r'[\u4e00-\u9fff]+', text)
        english_words = re.findall(r'[a-zA-Z]+', text)
        # Also get individual Chinese characters for better matching
        all_chars = re.findall(r'[\u4e00-\u9fff]|[a-zA-Z]+', text)
        return set(all_chars)

    def add_chunks(self, chunks: List[Dict]):
        """添加文档块"""
        self.chunks.extend(chunks)


# ============================================================
# Embedding 模型 - 支持 LoRA 领域适配微调
# ============================================================

class GameYuEmbedder:
    """游戏王OCG领域适配Embedding模型。

    支持加载基础text2vec模型和可选的LoRA adapter。
    当adapter_path未指定时使用基础模型。

    用法：
        # 基础模型
        embedder = GameYuEmbedder()

        # 加载微调adapter
        embedder = GameYuEmbedder(adapter_path="models/adapter/final")

        # 通过环境变量配置
        export EMBEDDER_ADAPTER_PATH=models/adapter/final
    """

    def __init__(self, model_name: str = "shibing624/text2vec-base-chinese", adapter_path: str = None):
        self.model_name = model_name
        self.adapter_path = adapter_path or os.environ.get("EMBEDDER_ADAPTER_PATH")
        self.model = self._load_model()

    def _load_model(self):
        """加载模型（支持LoRA adapter）。"""
        try:
            from sentence_transformers import SentenceTransformer
            base_model = SentenceTransformer(self.model_name)

            if self.adapter_path:
                try:
                    from peft import PeftModel
                    base_model.model = PeftModel.from_pretrained(
                        base_model.model,
                        self.adapter_path,
                    )
                    print(f"[GameYuEmbedder] 加载LoRA adapter: {self.adapter_path}")
                except ImportError:
                    print("[GameYuEmbedder] peft未安装，使用基础模型")
            else:
                print("[GameYuEmbedder] 使用基础模型（无adapter）")

            return base_model
        except ImportError:
            raise ImportError(
                "sentence-transformers未安装，请运行: pip install sentence-transformers peft"
            )

    def encode(self, texts: List[str], **kwargs) -> Any:
        """将文本编码为向量。"""
        return self.model.encode(texts, **kwargs)

    def similarity(self, text1: str, text2: str) -> float:
        """计算两个文本的余弦相似度。"""
        import numpy as np
        emb1 = self.encode([text1])[0]
        emb2 = self.encode([text2])[0]
        return float(np.dot(emb1, emb2) / (np.linalg.norm(emb1) * np.linalg.norm(emb2)))

    def search(self, query: str, documents: List[str], top_k: int = 5) -> List[Dict[str, Any]]:
        """在文档列表中搜索最相关的top_k条。"""
        import numpy as np
        if not documents:
            return []
        query_emb = self.encode([query])[0]
        doc_embs = self.encode(documents)
        similarities = np.dot(doc_embs, query_emb)
        top_indices = np.argsort(-similarities)[:top_k]
        results = []
        for idx in top_indices:
            results.append({
                "content": documents[int(idx)],
                "score": float(similarities[int(idx)]),
            })
        return results