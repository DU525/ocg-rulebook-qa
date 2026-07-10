# OCG 规则问答系统 - 向量存储测试

## 环境要求

```bash
pip install -r requirements.txt
```

## 运行测试

```bash
cd backend
python tests/test_vector_store.py
```

## 测试项目

1. **VectorStore 初始化** - 验证 BAAI/bge-m3 模型加载
2. **add_chunks** - 验证批量添加文档块功能
3. **search** - 验证语义检索功能
4. **向量维度** - 验证 BGE-m3 生成 1024 维向量

## 预期结果

- VectorStore 正常初始化
- ChromaDB 集合名为 `ocg_rules`
- search() 方法返回相关结果
- add_chunks() 正确添加文档到向量库