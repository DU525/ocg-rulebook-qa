"""快速构建DM索引 - 分批保存进度"""
import os, json, faiss, numpy as np
from pathlib import Path

os.environ['HF_ENDPOINT'] = 'https://hf-mirror.com'

CHUNKS_FILE = Path(r"C:\Users\1\Downloads\ocg-rulebook-qa\data\chunks\dm_rules_chunks.json")
INDEX_FILE = Path(r"C:\Users\1\Downloads\ocg-rulebook-qa\data\chunks\dm_rules_index.bin")
VECTORS_FILE = Path(r"C:\Users\1\Downloads\ocg-rulebook-qa\data\chunks\dm_vectors.npy")

print("加载分块...")
with open(CHUNKS_FILE, 'r', encoding='utf-8') as f:
    chunks = json.load(f)
print(f"共 {len(chunks)} 个分块")

# 检查已有向量
vectors = None
start_idx = 0
if VECTORS_FILE.exists():
    vectors = np.load(VECTORS_FILE)
    start_idx = len(vectors)
    print(f"已有 {start_idx} 个向量，继续...")

print("加载模型...")
from text2vec import SentenceModel
model = SentenceModel('shibing624/text2vec-base-chinese')

# 剩余需要处理的
remaining = [c['content'] for c in chunks[start_idx:]]
print(f"还需处理 {len(remaining)} 个分块...")

# 分批处理，每批50个
batch_size = 50
new_vectors = []

for i in range(0, len(remaining), batch_size):
    batch = remaining[i:i+batch_size]
    emb = model.encode(batch)
    if len(emb.shape) == 1:
        emb = emb.reshape(1, -1)
    new_vectors.append(emb)
    print(f"进度: {start_idx+i+len(batch)}/{len(chunks)}")
    
    # 每200个保存一次
    if (i + batch_size) % 200 == 0:
        if vectors is not None:
            all_v = np.vstack([vectors, np.vstack(new_vectors)])
        else:
            all_v = np.vstack(new_vectors)
        np.save(VECTORS_FILE, all_v)
        vectors = all_v
        new_vectors = []
        print(f"  已保存进度: {len(vectors)} 个向量")

# 最终保存
if new_vectors:
    if vectors is not None:
        all_v = np.vstack([vectors, np.vstack(new_vectors)])
    else:
        all_v = np.vstack(new_vectors)
    np.save(VECTORS_FILE, all_v)
    vectors = all_v

print(f"\n总共生成 {len(vectors)} 个向量")

# 构建索引
print("构建FAISS索引...")
dimension = vectors.shape[1]
index = faiss.IndexFlatL2(dimension)
index.add(vectors.astype('float32'))
faiss.write_index(index, str(INDEX_FILE))
print(f"完成！索引保存到: {INDEX_FILE}")