"""高效构建DM索引 - 分批保存"""
import os, json, faiss, numpy as np
from pathlib import Path

os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

CHUNKS_FILE = Path(r"C:\Users\1\Downloads\ocg-rulebook-qa\data\chunks\dm_rules_chunks.json")
INDEX_FILE = Path(r"C:\Users\1\Downloads\ocg-rulebook-qa\data\chunks\dm_rules_index.bin")
PROGRESS_FILE = Path(r"C:\Users\1\Downloads\ocg-rulebook-qa\data\chunks\dm_vectors.npy")

def main():
    print("=" * 50)
    print("DM索引构建 (分批保存进度)")
    print("=" * 50)
    
    # 加载分块
    with open(CHUNKS_FILE, 'r', encoding='utf-8') as f:
        chunks = json.load(f)
    total = len(chunks)
    print(f"分块总数: {total}")
    
    # 检查已有进度
    all_vectors = []
    start_idx = 0
    if PROGRESS_FILE.exists():
        all_vectors = [np.load(PROGRESS_FILE)]
        start_idx = len(all_vectors[0])
        print(f"已有 {start_idx} 个向量，从第 {start_idx} 个继续...")
    
    if start_idx >= total:
        print("已完成向量编码，跳过到索引构建")
    else:
        # 加载模型
        print("加载 text2vec 模型...")
        from text2vec import SentenceModel
        model = SentenceModel('shibing624/text2vec-base-chinese')
        
        # 分批处理
        batch_size = 100
        batch_vectors = []
        
        for i in range(start_idx, total, batch_size):
            batch = chunks[i:i+batch_size]
            texts = [c['content'] for c in batch]
            emb = model.encode(texts)
            if len(emb.shape) == 1:
                emb = emb.reshape(1, -1)
            batch_vectors.append(emb)
            
            # 每500个保存一次
            processed = i + len(batch)
            if (i + batch_size) % 500 == 0 or processed == total:
                all_vectors.extend(batch_vectors)
                combined = np.vstack(all_vectors)
                np.save(PROGRESS_FILE, combined)
                print(f"进度: {processed}/{total} ({100*processed/total:.1f}%)")
                all_vectors = [combined]
                batch_vectors = []
    
    # 构建索引
    print("\n构建FAISS索引...")
    vectors = np.load(PROGRESS_FILE).astype('float32')
    dimension = vectors.shape[1]
    index = faiss.IndexFlatL2(dimension)
    index.add(vectors)
    faiss.write_index(index, str(INDEX_FILE))
    
    print(f"\n完成！")
    print(f"  向量数: {len(vectors)}")
    print(f"  索引: {INDEX_FILE}")

if __name__ == '__main__':
    main()