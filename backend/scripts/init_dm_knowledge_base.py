"""初始化数码宝贝规则知识库"""
import sys
import os
from pathlib import Path
import json

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.db.dm_vector_store import DMVectorRAG
from app.services.document_processor import DocumentProcessor
from app.config import Config
import faiss
import numpy as np


def init_dm_knowledge_base():
    """初始化数码宝贝知识库"""
    print("=" * 50)
    print("开始初始化数码宝贝规则知识库...")
    print("=" * 50)

    # 确保数据目录存在
    os.makedirs(Config.DM_DOCS_PATH, exist_ok=True)
    os.makedirs(os.path.join(os.path.dirname(__file__), '../../data/chunks'), exist_ok=True)

    processor = DocumentProcessor(chunk_size=512, chunk_overlap=64)

    # 检查源PDF是否存在
    source_pdf = r"C:\Users\1\Downloads\数码宝贝卡牌对战综合规则V2.3.pdf"
    
    if not os.path.exists(source_pdf):
        print(f"错误: 找不到源PDF文件 {source_pdf}")
        print("请确保PDF文件存在于上述路径")
        return

    chunks_file = os.path.join(
        os.path.dirname(__file__), '../../data/chunks/dm_rules_chunks.json'
    )
    index_file = os.path.join(
        os.path.dirname(__file__), '../../data/chunks/dm_rules_index.bin'
    )

    # 如果已有索引，先检查
    if os.path.exists(chunks_file) and os.path.exists(index_file):
        print(f"检测到已有知识库，跳过初始化")
        print(f"  分块文件: {chunks_file}")
        print(f"  索引文件: {index_file}")
        
        # 显示统计信息
        with open(chunks_file, 'r', encoding='utf-8') as f:
            chunks = json.load(f)
        print(f"  已加载 {len(chunks)} 个文档块")
        return

    print(f"\n处理PDF文件: {source_pdf}")
    
    try:
        chunks = processor.process_pdf(source_pdf)
        print(f"生成了 {len(chunks)} 个文档块")
    except Exception as e:
        print(f"处理PDF失败: {e}")
        return

    if not chunks:
        print("未能生成分块")
        return

    # 保存分块
    chunks_data = []
    for i, chunk in enumerate(chunks):
        chunks_data.append({
            'id': f'dm_chunk_{i}',
            'content': chunk.content if hasattr(chunk, 'content') else chunk.get('content', ''),
            'metadata': {
                'source': '数码宝贝卡牌对战综合规则V2.3.pdf',
                'chunk_index': i,
                'char_count': len(chunk.content if hasattr(chunk, 'content') else '')
            }
        })

    with open(chunks_file, 'w', encoding='utf-8') as f:
        json.dump(chunks_data, f, ensure_ascii=False, indent=2)
    print(f"分块已保存到: {chunks_file}")

    # 构建向量索引
    print("\n正在构建向量索引...")
    dm_rag = DMVectorRAG(chunks_file=chunks_file, index_file=index_file)
    
    stats = dm_rag.get_stats()
    print(f"\n知识库统计:")
    print(f"  文档块数量: {stats['chunk_count']}")
    print(f"  索引向量数: {stats['index_size']}")
    print(f"  向量维度: {stats['dimension']}")
    
    print("\n" + "=" * 50)
    print("数码宝贝知识库初始化完成！")
    print("=" * 50)


if __name__ == '__main__':
    init_dm_knowledge_base()