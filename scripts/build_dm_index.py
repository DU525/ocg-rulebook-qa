"""独立脚本：初始化数码宝贝知识库 - 增量版"""
import sys, os, json, faiss, numpy as np
from pathlib import Path

os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

CHUNKS_FILE = Path(r"C:\Users\1\Downloads\ocg-rulebook-qa\data\chunks\dm_rules_chunks.json")
INDEX_FILE = Path(r"C:\Users\1\Downloads\ocg-rulebook-qa\data\chunks\dm_rules_index.bin")
SOURCE_PDF = r"C:\Users\1\Downloads\数码宝贝卡牌对战综合规则V2.3.pdf"

def main():
    print("=" * 50)
    print("数码宝贝规则知识库 - 向量索引构建")
    print("=" * 50)
    
    # 检查分块文件
    if not CHUNKS_FILE.exists():
        print(f"错误: 找不到分块文件 {CHUNKS_FILE}")
        print("请先运行 init_dm_kb_v2.py 生成初始分块")
        return
    
    # 检查索引是否已存在
    if INDEX_FILE.exists():
        print(f"索引已存在: {INDEX_FILE}")
        return
    
    print("\n加载分块数据...")
    with open(CHUNKS_FILE, 'r', encoding='utf-8') as f:
        chunks_data = json.load(f)
    print(f"加载了 {len(chunks_data)} 个分块")
    
    print("\n加载 text2vec 模型...")
    from text2vec import SentenceModel
    model = SentenceModel('shibing624/text2vec-base-chinese')
    
    dimension = 768
    index = faiss.IndexFlatL2(dimension)
    
    # 分批编码，每批100个
    batch_size = 100
    all_vectors = []
    
    for i in range(0, len(chunks_data), batch_size):
        batch = chunks_data[i:i+batch_size]
        texts = [c['content'] for c in batch]
        vectors = model.encode(texts)
        if len(vectors.shape) == 1:
            vectors = vectors.reshape(1, -1)
        all_vectors.append(vectors)
        print(f"已处理 {min(i+batch_size, len(chunks_data))}/{len(chunks_data)}")
    
    # 合并所有向量
    all_vectors = np.vstack(all_vectors).astype('float32')
    index.add(all_vectors)
    
    print(f"\n索引构建完成: {index.ntotal} 个向量")
    faiss.write_index(index, str(INDEX_FILE))
    print(f"已保存到: {INDEX_FILE}")
    
    print("\n完成！")

if __name__ == '__main__':
    main()