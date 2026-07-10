# 测试清单 - 完整系统测试

**版本**: 2.0  
**更新日期**: 2026-05-25  
**覆盖范围**: T0 + T1 所有新功能

---

## 新增测试文件列表

### 1. 分层 RAG 系统测试
- **文件**: `test_hierarchical_rag.py`
- **覆盖功能**:
  - ✅ HierarchicalVectorStore 初始化
  - ✅ 添加文档（父子分块）
  - ✅ 分层检索（父块召回 + 子块精排）
  - ✅ 集合统计信息
  - ✅ 清空集合

### 2. 增强记忆系统测试
- **文件**: `test_enhanced_memory.py`
- **覆盖功能**:
  - ✅ EnhancedMemorySystem 初始化
  - ✅ 添加记忆（各种类型和标签）
  - ✅ MemoryRetriever 语义检索
  - ✅ 多种检索策略（Hybrid, Semantic, BM25, Time-based）
  - ✅ 记忆操作（按类型、标签、重要性查询）
  - ✅ 记忆清空

### 3. 高级路由系统测试
- **文件**: `test_routing_system.py`
- **覆盖功能**:
  - ✅ SemanticRouter 初始化
  - ✅ 添加路由（示例、关键词、阈值）
  - ✅ 语义路由决策
  - ✅ AdvancedRouter 混合路由
  - ✅ 路由反馈学习
  - ✅ 路由可视化数据

### 4. 结构化数据处理测试
- **文件**: `test_structured_data.py`
- **覆盖功能**:
  - ✅ StructuredDataProcessor 初始化
  - ✅ 表格转 Markdown
  - ✅ DocumentCleaner 初始化
  - ✅ 页眉页脚清理
  - ✅ 自定义清理模式
  - ✅ OCR 可用性检查

### 5. 智能分块策略测试
- **文件**: `test_chunking_strategy.py`
- **覆盖功能**:
  - ✅ ChunkingStrategySystem 初始化
  - ✅ 句子分块策略
  - ✅ 段落分块策略
  - ✅ 语义分块策略（识别标题）
  - ✅ 自适应分块策略
  - ✅ 自动策略选择
  - ✅ 分块质量评估

### 6. 标准化工具系统测试
- **文件**: `test_tool_system.py`
- **覆盖功能**:
  - ✅ ToolRegistry 初始化
  - ✅ FunctionTool 创建和执行
  - ✅ @tool 装饰器
  - ✅ 工具注册和执行
  - ✅ ToolTester 测试框架
  - ✅ ToolTracer 调用追踪
  - ✅ 现有工具兼容性检查

---

## 原有测试文件（保持不变）

| 文件名 | 测试内容 |
|--------|----------|
| `test_vector_store.py` | 向量存储功能 |
| `test_conversation_memory.py` | 对话记忆 |
| `test_agent.py` | Agent 系统 |
| `test_agent_tools.py` | Agent 工具 |
| `test_intent_classifier.py` | 意图分类 |
| `test_ragas_evaluation.py` | RAGAS 评估 |
| `test_performance.py` | 性能测试 |
| `test_health_routes.py` | 健康检查路由 |
| ... | ... |

---

## 运行测试指南

### 运行单个新功能测试

```bash
# 进入 backend 目录
cd ocg-rulebook-qa/backend

# 运行分层 RAG 测试
python tests/test_hierarchical_rag.py

# 运行记忆系统测试
python tests/test_enhanced_memory.py

# 运行路由系统测试
python tests/test_routing_system.py

# 运行结构化数据测试
python tests/test_structured_data.py

# 运行分块策略测试
python tests/test_chunking_strategy.py

# 运行工具系统测试
python tests/test_tool_system.py
```

### 运行所有新功能测试

```bash
# 批量运行所有新测试
for test_file in test_hierarchical_rag.py test_enhanced_memory.py test_routing_system.py test_structured_data.py test_chunking_strategy.py test_tool_system.py; do
    echo "Running: $test_file"
    python tests/$test_file
    echo "----------------------------------------"
done
```

### 完整测试套件

```bash
# 运行所有测试（原有 + 新增）
# 注意：某些测试可能需要环境变量或外部依赖
python -m pytest tests/ -v
```

---

## 测试覆盖统计

### T0 功能测试覆盖
| 功能模块 | 测试文件 | 测试用例数 | 状态 |
|---------|---------|----------|------|
| 分层 RAG 系统 | `test_hierarchical_rag.py` | 4 | ✅ |
| 元数据提取系统 | （集成在其他测试中） | - | ✅ |
| 增强记忆系统 | `test_enhanced_memory.py` | 5 | ✅ |
| 高级路由系统 | `test_routing_system.py` | 6 | ✅ |

### T1 功能测试覆盖
| 功能模块 | 测试文件 | 测试用例数 | 状态 |
|---------|---------|----------|------|
| 结构化数据处理 | `test_structured_data.py` | 6 | ✅ |
| 智能分块策略 | `test_chunking_strategy.py` | 7 | ✅ |
| 工具标准化 | `test_tool_system.py` | 8 | ✅ |

### 总计
- **新增测试文件**: 6 个
- **新增测试用例**: 36+ 个
- **代码覆盖**: T0 + T1 所有核心功能

---

## 测试数据说明

### 测试用示例数据
- 使用游戏王OCG规则相关文本
- 包含Markdown格式的标题、列表等结构
- 涵盖不同场景的查询

### 模拟数据
- 模拟表格数据（用于表格提取测试）
- 模拟页眉页脚（用于文档清理测试）
- 各种场景的用户查询（用于路由测试）

---

## 依赖检查

### 新功能可能需要的依赖
```bash
# 核心依赖（已有）
# - langchain (部分功能)
# - numpy, faiss (已有)

# 可选依赖
# - pymupdf (PDF表格提取)
# - python-docx (Word文档处理)
# - pytesseract/easyocr/paddleocr (OCR)
```

### 测试前检查
```python
# 检查新模块是否可导入
from app.db.hierarchical_vector_store import HierarchicalVectorStore
from app.services.enhanced_memory import get_enhanced_memory
from app.services.semantic_router import get_semantic_router
from app.services.chunking_strategy import ChunkingStrategySystem
from app.services.tool_system import ToolRegistry
```

---

## 集成测试建议

### 1. 完整对话流程集成
```
用户查询
  ↓
[高级路由] → 确定问题类型
  ↓
[记忆检索] → 查找相关历史
  ↓
[分层RAG] → 检索文档
  ↓
[工具执行] → 调用工具（如需要）
  ↓
LLM 生成回答
```

### 2. 文档处理流水线
```
文档上传
  ↓
[文档清理] → 去除页眉页脚
  ↓
[元数据提取] → 提取标题、类型
  ↓
[智能分块] → 生成父子块
  ↓
[分层存储] → 存入向量数据库
```

---

## 更新历史

| 版本 | 日期 | 更新内容 |
|------|------|---------|
| 2.0 | 2026-05-25 | 新增 T0+T1 功能完整测试套件 |
| 1.0 | 2026-05-24 | 初始版本 |

---

## 备注

- ✅ 所有测试文件已创建完成
- ✅ 测试覆盖所有 T0 + T1 新功能
- ✅ 保持与现有测试框架兼容
- ⚠️ 某些功能（如 OCR）需要可选依赖，测试时会优雅降级
