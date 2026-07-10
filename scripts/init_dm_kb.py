"""独立脚本：初始化数码宝贝知识库"""
import sys
import os
import json
import faiss
import numpy as np
from pathlib import Path

# 设置HF镜像
os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

# 数据目录
DATA_DIR = Path(__file__).parent.parent.parent / 'data'
CHUNKS_DIR = DATA_DIR / 'chunks'
CHUNKS_DIR.mkdir(parents=True, exist_ok=True)

CHUNKS_FILE = CHUNKS_DIR / 'dm_rules_chunks.json'
INDEX_FILE = CHUNKS_DIR / 'dm_rules_index.bin'

# PDF文件
SOURCE_PDF = r"C:\Users\1\Downloads\数码宝贝卡牌对战综合规则V2.3.pdf"


def extract_pdf_text(pdf_path):
    """提取PDF文本"""
    from pypdf import PdfReader
    
    reader = PdfReader(pdf_path)
    texts = []
    
    for page in reader.pages:
        text = page.extract_text()
        if text:
            texts.append(text)
    
    return texts


def split_text(text, chunk_size=512, overlap=64):
    """智能文本分块"""
    chunks = []
    paragraphs = text.split('\n\n')
    current_chunk = ""
    
    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
            
        if len(para) > chunk_size:
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = ""
            
            # 按句子分割
            sentences = []
            import re
            for sep in re.findall(r'[。！？；\.]', para):
                parts = para.split(sep)
                for i, part in enumerate(parts):
                    if part.strip():
                        suffix = sep if i < len(parts) - 1 else ''
                        sentences.append(part.strip() + suffix)
            
            for sentence in sentences:
                if len(current_chunk) + len(sentence) > chunk_size:
                    if current_chunk:
                        chunks.append(current_chunk)
                    current_chunk = sentence[overlap:] if overlap > 0 else sentence
                else:
                    current_chunk += sentence
        else:
            if len(current_chunk) + len(para) > chunk_size:
                chunks.append(current_chunk)
                current_chunk = para
            else:
                current_chunk += ('\n\n' + para) if current_chunk else para
    
    if current_chunk:
        chunks.append(current_chunk)
    
    return chunks


def build_index(chunks_data):
    """构建FAISS索引"""
    print("\n正在加载 text2vec 模型...")
    from text2vec import SentenceModel
    model = SentenceModel('shibing624/text2vec-base-chinese')
    
    print("正在生成向量...")
    texts = [c['content'] for c in chunks_data]
    embeddings = model.encode(texts)
    
    if len(embeddings.shape) == 1:
        embeddings = embeddings.reshape(1, -1)
    
    print(f"生成了 {len(embeddings)} 个向量")
    print(f"向量维度: {embeddings.shape[1]}")
    
    # 构建索引
    dimension = embeddings.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(embeddings.astype('float32'))
    
    print(f"索引构建完成，包含 {index.ntotal} 个向量")
    
    # 保存
    faiss.write_index(index, str(INDEX_FILE))
    print(f"索引已保存到: {INDEX_FILE}")
    
    return index


def main():
    print("=" * 50)
    print("数码宝贝规则知识库初始化")
    print("=" * 50)
    
    # 检查是否已有索引
    if CHUNKS_FILE.exists() and INDEX_FILE.exists():
        with open(CHUNKS_FILE, 'r', encoding='utf-8') as f:
            chunks = json.load(f)
        print(f"\n检测到已有知识库:")
        print(f"  分块文件: {CHUNKS_FILE}")
        print(f"  索引文件: {INDEX_FILE}")
        print(f"  已加载 {len(chunks)} 个文档块")
        return
    
    # 检查源文件
    if not os.path.exists(SOURCE_PDF):
        print(f"错误: 找不到源PDF文件: {SOURCE_PDF}")
        print("请确保PDF文件存在于此路径")
        return
    
    print(f"\n源文件: {SOURCE_PDF}")
    print("正在提取PDF文本...")
    
    pages_text = extract_pdf_text(SOURCE_PDF)
    print(f"提取了 {len(pages_text)} 页文本")
    
    # 分块
    print("正在进行文档分块...")
    all_chunks = []
    for i, text in enumerate(pages_text):
        chunks = split_text(text, chunk_size=512, overlap=64)
        for j, chunk_text in enumerate(chunks):
            if len(chunk_text) < 50:
                continue
            all_chunks.append({
                'id': f'dm_pdf_{i}_{j}',
                'content': chunk_text,
                'metadata': {
                    'source': SOURCE_PDF,
                    'type': 'pdf',
                    'page': i + 1,
                    'chunk_index': j,
                    'char_count': len(chunk_text)
                }
            })
    
    print(f"生成了 {len(all_chunks)} 个文档块")
    
    # 保存分块
    with open(CHUNKS_FILE, 'w', encoding='utf-8') as f:
        json.dump(all_chunks, f, ensure_ascii=False, indent=2)
    print(f"分块已保存到: {CHUNKS_FILE}")
    
    # 构建索引
    build_index(all_chunks)
    
    print("\n" + "=" * 50)
    print("知识库初始化完成！")
    print("=" * 50)


if __name__ == '__main__':
    main()