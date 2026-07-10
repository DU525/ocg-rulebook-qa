"""独立脚本：初始化数码宝贝知识库 - 优化版"""
import sys
import os
import json
import faiss
import numpy as np
from pathlib import Path

os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

DATA_DIR = Path(__file__).parent.parent / 'data'
CHUNKS_DIR = DATA_DIR / 'chunks'
CHUNKS_DIR.mkdir(parents=True, exist_ok=True)

CHUNKS_FILE = CHUNKS_DIR / 'dm_rules_chunks.json'
INDEX_FILE = CHUNKS_DIR / 'dm_rules_index.bin'
SOURCE_PDF = r"C:\Users\1\Downloads\数码宝贝卡牌对战综合规则V2.3.pdf"


def extract_pdf_text(pdf_path):
    from pypdf import PdfReader
    reader = PdfReader(pdf_path)
    return [page.extract_text() for page in reader.pages if page.extract_text()]


def split_text(text, chunk_size=512, overlap=64):
    chunks, paragraphs = [], text.split('\n\n')
    current_chunk = ""
    
    for para in paragraphs:
        para = para.strip()
        if not para: continue
        
        if len(para) > chunk_size:
            if current_chunk:
                chunks.append(current_chunk)
                current_chunk = ""
            
            import re
            sentences = []
            for sep in re.findall(r'[。！？；\.]', para):
                parts = para.split(sep)
                for i, part in enumerate(parts):
                    if part.strip():
                        suffix = sep if i < len(parts) - 1 else ''
                        sentences.append(part.strip() + suffix)
            
            for sentence in sentences:
                if len(current_chunk) + len(sentence) > chunk_size:
                    if current_chunk: chunks.append(current_chunk)
                    current_chunk = sentence[overlap:] if overlap > 0 else sentence
                else:
                    current_chunk += sentence
        else:
            if len(current_chunk) + len(para) > chunk_size:
                chunks.append(current_chunk)
                current_chunk = para
            else:
                current_chunk += ('\n\n' + para) if current_chunk else para
    
    if current_chunk: chunks.append(current_chunk)
    return chunks


def build_index_optimized(chunks_data, batch_size=500):
    """分批构建索引，避免内存溢出"""
    print("\n正在加载 text2vec 模型...")
    from text2vec import SentenceModel
    model = SentenceModel('shibing624/text2vec-base-chinese')
    
    texts = [c['content'] for c in chunks_data]
    dimension = 768
    
    index = faiss.IndexFlatL2(dimension)
    
    # 分批处理
    for i in range(0, len(texts), batch_size):
        batch_texts = texts[i:i+batch_size]
        print(f"正在生成向量批次 {i//batch_size + 1}/{(len(texts)-1)//batch_size + 1}...")
        embeddings = model.encode(batch_texts)
        if len(embeddings.shape) == 1:
            embeddings = embeddings.reshape(1, -1)
        index.add(embeddings.astype('float32'))
        print(f"  已处理 {min(i+batch_size, len(texts))}/{len(texts)} 个向量")
    
    print(f"索引构建完成，包含 {index.ntotal} 个向量")
    faiss.write_index(index, str(INDEX_FILE))
    print(f"索引已保存到: {INDEX_FILE}")
    return index


def main():
    print("=" * 50)
    print("数码宝贝规则知识库初始化")
    print("=" * 50)
    
    # 强制重建索引
    force_rebuild = True
    
    if not force_rebuild and CHUNKS_FILE.exists() and INDEX_FILE.exists():
        with open(CHUNKS_FILE, 'r', encoding='utf-8') as f:
            chunks = json.load(f)
        print(f"\n检测到已有知识库，跳过初始化")
        print(f"  分块: {len(chunks)} 个")
        return
    
    if not os.path.exists(SOURCE_PDF):
        print(f"错误: 找不到 {SOURCE_PDF}")
        return
    
    if not CHUNKS_FILE.exists():
        print(f"\n源文件: {SOURCE_PDF}")
        print("正在提取PDF文本...")
        pages_text = extract_pdf_text(SOURCE_PDF)
        print(f"提取了 {len(pages_text)} 页")
        
        print("分块中...")
        all_chunks = []
        for i, text in enumerate(pages_text):
            for j, chunk_text in enumerate(split_text(text)):
                if len(chunk_text) < 50: continue
                all_chunks.append({
                    'id': f'dm_pdf_{i}_{j}',
                    'content': chunk_text,
                    'metadata': {'source': SOURCE_PDF, 'page': i+1, 'chunk_index': j}
                })
        
        print(f"生成了 {len(all_chunks)} 个分块")
        with open(CHUNKS_FILE, 'w', encoding='utf-8') as f:
            json.dump(all_chunks, f, ensure_ascii=False, indent=2)
        print(f"已保存到: {CHUNKS_FILE}")
    
    # 构建索引
    if not INDEX_FILE.exists() or force_rebuild:
        with open(CHUNKS_FILE, 'r', encoding='utf-8') as f:
            chunks_data = json.load(f)
        build_index_optimized(chunks_data)
    
    print("\n" + "=" * 50)
    print("知识库初始化完成！")
    print("=" * 50)


if __name__ == '__main__':
    main()