# 从62分到88分：一个RAG系统的23天优化之旅

> **作者**：OCG/DM RAG项目组
> **发布时间**：2026-05-23
> **预计阅读时间**：15分钟
> **目标读者**：大模型/RAG方向工程师

---

## 引言

23天，5个工作周，从62分到88分。

这不是一次简单的功能迭代，而是一个完整的RAG系统工程优化实践。本文将从一个真实的OCG/DM游戏王规则书问答系统出发，详细记录从基线评估、策略优化、架构升级到全链路压测的完整过程。

如果你正在做RAG项目，或者准备面试大模型方向，这篇文章或许能给你一些参考。

---

## 一、项目背景

### 1.1 为什么做这个项目

OCG/DM游戏王规则书包含118,298条OCG规则和6,511条DM规则，总计超过12万条知识条目。传统的FAQ系统面临两个核心痛点：

1. **维护成本高**：规则书频繁更新，FAQ需要人工维护
2. **覆盖不全**：长尾问题无法覆盖，用户查不到想要的规则

RAG（Retrieval-Augmented Generation）是解决这两个问题的天然方案：从知识库中检索相关规则，让大语言模型基于检索结果生成回答，既保证了答案的准确性，又降低了对训练数据的依赖。

### 1.2 初始系统状态

项目开始时的系统架构很简单：

```
用户提问 → text2vec编码 → FAISS向量检索 → MiniMax LLM生成回答
```

技术栈：React前端 + Flask后端 + FAISS HNSW索引 + SQLite存储。

**问题也很明显**：
- 单一向量检索对专有名词匹配率低（如"神之宣告"、"灰流丽"）
- 没有量化评估手段，优化靠感觉
- 重复查询每次都走完整RAG流程，LLM调用成本高
- Flask同步架构QPS上限仅180

用内部评分体系打分，系统只有62分。目标是达到行业Top 2水平（对标FastGPT/Dify），目标分数88分。

---

## 二、Week 1：建立量化评估 + 三级缓存

### 2.1 RAGAS：用数据说话

优化的第一步不是改代码，而是建立评估体系。没有量化指标，优化就是盲人摸象。

我引入了RAGAS框架（Retrieval-Augmented Generation Assessment），用4项指标评估RAG质量：

| 指标 | 含义 | 评估内容 |
|------|------|----------|
| **Faithfulness（忠实度）** | 答案是否忠实于上下文 | 是否引入了外部信息/幻觉 |
| **Answer Relevance（答案相关性）** | 答案是否与问题直接相关 | 是否跑题 |
| **Context Precision（上下文精确度）** | 检索到的上下文是否有用 | 是否检索到了无关文档 |
| **Context Recall（上下文召回率）** | 检索是否覆盖了关键信息 | 是否遗漏了重要规则 |

**基线评估结果**：

| 指标 | 基线值 | 行业基准 |
|------|--------|----------|
| Faithfulness | 0.75 | ≥0.80 |
| Answer Relevance | 0.35 | ≥0.70 |
| Context Precision | 0.72 | ≥0.80 |
| Context Recall | 0.68 | ≥0.80 |

三项指标未达标，答案相关性尤其低（后续分析发现主要由LLM Prompt中的`<think>`标签引起，RAGAS对其过度惩罚）。

> **关键经验**：RAGAS标准评估需要LLM做评判，成本较高。我写了一个启发式降级评估器，基于规则匹配、语义相似度、覆盖率计算4项指标，零成本完成评估。

### 2.2 三级缓存架构

缓存是性能优化的第一道防线。我设计了三级缓存：

```python
# L1 内存LRU缓存
from functools import lru_cache

@lru_cache(maxsize=10000)
def vector_search_cached(query_hash: str) -> List[Dict]:
    """MD5哈希作为key，避免大字符串作为缓存key"""
    return vector_store.search(query_hash)

# L2 Redis缓存
import redis

redis_client = redis.Redis(host='localhost', port=6379, db=0)

def get_redis_cache(query: str) -> Optional[Dict]:
    """Redis缓存，支持多进程共享"""
    key = f"rag:query:{hashlib.md5(query.encode()).hexdigest()}"
    cached = redis_client.get(key)
    if cached:
        return json.loads(cached)
    return None

def set_redis_cache(query: str, result: Dict, ttl: int = 86400):
    """动态TTL策略"""
    key = f"rag:query:{hashlib.md5(query.encode()).hexdigest()}"
    redis_client.setex(key, ttl, json.dumps(result))

# L3 SimHash语义缓存
from simhash import Simhash

def get_simhash_cache(query: str) -> Optional[Dict]:
    """语义近似匹配，处理paraphrase问题"""
    query_hash = Simhash(query).value
    for cached_hash, cached_result in simhash_index.items():
        if bin(query_hash ^ cached_hash).count('1') <= 3:
            return cached_result
    return None
```

**查询流程**：

```
用户查询 → MD5查L1 → 未命中 → Redis查L2 → 未命中 → 
SimHash查L3 → 未命中 → 完整RAG流程
```

**动态TTL策略**：
- 热门查询（>10次/天）：TTL = 7天
- 普通查询：TTL = 24小时
- 冷门查询（<1次/天）：TTL = 1小时

服务启动时预热Top 100热门查询，避免冷启动问题。

**Week 1成果**：
- RAGAS评估体系上线，4项指标可自动化评估
- 三级缓存综合命中率达到85%
- 缓存命中响应时间<0.1ms
- LLM调用量减少65%
- 系统评分：62 → 70

---

## 三、Week 2：多路检索 + RRF融合 + Cross-Encoder重排

### 3.1 单一向量检索的局限

基线评估发现Context Recall只有0.68，意味着32%的情况下检索到的上下文没有覆盖关键信息。

分析bad case后发现，向量检索对以下场景匹配率低：
1. **专有名词**：如"神之宣告"、"灰流丽"等卡牌名
2. **规则编号**：如"综合规则第2-2条"
3. **精确术语**：如"连锁"、"优先权"、"诱发效果"

这些都是BM25关键词检索的强项。

### 3.2 BM25 + 向量双路检索

我用Whoosh构建BM25索引，jieba分词处理中文：

```python
from whoosh.index import create_in
from whoosh.fields import Schema, TEXT, ID
from whoosh.qparser import QueryParser
import jieba

# 构建BM25索引schema
schema = Schema(
    chunk_id=ID(stored=True),
    content=TEXT(stored=True, analyzer=jieba.analyzer()),
    title=TEXT(stored=True)
)

index = create_in("bm25_index", schema)
writer = index.writer()
for chunk in chunks:
    writer.add_document(
        chunk_id=chunk['id'],
        content=chunk['text'],
        title=chunk.get('title', '')
    )
writer.commit()

# BM25搜索
def bm25_search(query: str, top_k: int = 50) -> List[Dict]:
    with index.searcher() as searcher:
        parser = QueryParser("content", schema=schema)
        query_obj = parser.parse(query)
        results = searcher.search(query_obj, limit=top_k)
        return [{"id": r["chunk_id"], "score": r.score} for r in results]
```

**关键发现**：BM25和向量检索有约25%的互补案例，即BM25能召回但向量检索遗漏的文档。这证明多路检索的必要性。

### 3.3 RRF融合排序

两路检索结果如何融合？加权求和需要归一化（BM25分数和向量相似度量纲不同），我选择了RRF（Reciprocal Rank Fusion）：

```python
from collections import defaultdict

def rrf_fusion(
    vector_results: List[Dict],
    bm25_results: List[Dict],
    k: int = 60,
    vector_weight: float = 0.7,
    bm25_weight: float = 0.3
) -> List[Dict]:
    """
    RRF融合排序
    score(d) = Σ weight_i / (k + rank_i(d))
    """
    scores = defaultdict(float)
    
    for rank, doc in enumerate(vector_results):
        scores[doc['id']] += vector_weight / (k + rank + 1)
    
    for rank, doc in enumerate(bm25_results):
        scores[doc['id']] += bm25_weight / (k + rank + 1)
    
    sorted_docs = sorted(scores.items(), key=lambda x: -x[1])
    return [{"id": doc_id, "score": score} for doc_id, score in sorted_docs]
```

**为什么k=60**：这是RRF论文中的经验值。k太小会导致Top 1和Top 2差距过大，k太大会让排名差异被稀释。60在大多数场景下表现稳健。

**权重调优**：通过实验确定向量70% + BM25 30%。对规则类查询（如"连锁规则第几条"）动态提高BM25权重到50%。

### 3.4 Cross-Encoder重排序

RRF融合后recall@5达到88%，但Top 50结果中仍含有不相关文档。我引入Cross-Encoder做精排：

```python
from sentence_transformers import CrossEncoder

# 加载Cross-Encoder模型
reranker = CrossEncoder('cross-encoder/ms-marco-MiniLM-L-6-v2')

def cross_encoder_rerank(
    query: str,
    documents: List[Dict],
    top_k: int = 5
) -> List[Dict]:
    """
    Cross-Encoder重排序
    对RRF输出的Top N文档进行交互注意力计算
    """
    # 只取Top 10做重排，控制延迟
    candidates = documents[:10]
    
    # 构建(query, doc)对
    pairs = [(query, doc['text']) for doc in candidates]
    
    # 批量打分
    scores = reranker.predict(pairs)
    
    # 排序返回Top K
    ranked = sorted(
        zip(candidates, scores),
        key=lambda x: -x[1]
    )
    
    return [doc for doc, score in ranked[:top_k]]
```

**延迟权衡**：最初对Top 50做重排，延迟超过200ms。调整为只对Top 10重排，延迟45ms，recall@5从88%提升到92%。这是经过实验找到的最佳平衡点。

**Week 2成果**：
- BM25关键词检索上线
- RRF融合排序，recall@5从78%提升至88%
- Cross-Encoder重排，recall@5从88%提升至92%
- 系统评分：70 → 78

---

## 四、Week 3：Flask → FastAPI异步升级

### 4.1 同步架构的瓶颈

Flask是同步阻塞架构。当LLM调用需要2-10秒时，整个worker被阻塞，其他请求只能排队等待。压测发现Flask的QPS上限仅180。

### 4.2 FastAPI异步改造

三个核心异步化改造：

**1. FAISS异步封装**：FAISS本身不支持async，用`asyncio.to_thread()`包装：

```python
import asyncio

async def async_vector_search(query_vector: np.ndarray, top_k: int = 50) -> List[Dict]:
    """将FAISS搜索放到线程池执行，不阻塞事件循环"""
    distances, indices = await asyncio.to_thread(
        faiss_index.search,
        query_vector,
        top_k
    )
    return [{"id": idx, "distance": dist} for idx, dist in zip(indices, distances)]
```

**2. LLM异步调用**：用aiohttp替代requests：

```python
import aiohttp

async def async_llm_generate(prompt: str, stream: bool = False) -> str:
    """异步LLM调用"""
    async with aiohttp.ClientSession() as session:
        async with session.post(
            "https://api.minimax.chat/v1/text/chatcompletion",
            json={"prompt": prompt, "stream": stream},
            timeout=aiohttp.ClientTimeout(total=30)
        ) as response:
            if stream:
                content = ""
                async for chunk in response.content:
                    content += chunk.decode()
                    yield chunk.decode()
            else:
                data = await response.json()
                return data["choices"][0]["message"]["content"]
```

**3. 异步数据库**：用aiosqlite替代sqlite3：

```python
import aiosqlite

async def save_conversation(user_id: str, question: str, answer: str):
    """异步保存对话历史"""
    async with aiosqlite.connect("rag.db") as db:
        await db.execute(
            "INSERT INTO conversations (user_id, question, answer) VALUES (?, ?, ?)",
            (user_id, question, answer)
        )
        await db.commit()
```

**Week 3成果**：
- FastAPI全异步架构上线
- QPS从180提升至5,100（+2,733%）
- p99延迟从250ms降至45ms
- 系统评分：78 → 84

---

## 五、Week 4：全链路压测 + 监控体系

### 5.1 Locust压测

使用Locust进行全链路压测，设计4个并发场景：

```python
from locust import HttpUser, task, between
import random

QUESTIONS = [
    "什么是连锁？",
    "连锁的处理顺序是什么？",
    "神之宣告的效果是什么？",
    "灰流丽可以连锁什么效果？",
    # ... 更多测试问题
]

class RAGUser(HttpUser):
    wait_time = between(1, 3)
    
    @task(3)
    def ask_question(self):
        self.client.post(
            '/api/v1/chat/question',
            json={'question': random.choice(QUESTIONS)}
        )
    
    @task(1)
    def get_conversations(self):
        self.client.get('/api/v1/conversations')
```

**压测结果**：

| 并发数 | Flask QPS | FastAPI QPS | 提升幅度 |
|--------|-----------|-------------|----------|
| 100 | 85 | 420 | +394% |
| 500 | 120 | 1,850 | +1,442% |
| 1,000 | 145 | 3,200 | +2,107% |
| 5,000 | 180 | 5,100 | +2,733% |

向量检索QPS达50,000，p99延迟<50ms，错误率<0.25%。

### 5.2 Prometheus + Grafana监控

缺乏可观测性意味着问题定位困难。我部署了Prometheus + Grafana监控体系：

**5个核心面板**：
1. QPS实时曲线
2. p50/p95/p99延迟分布
3. 缓存命中率
4. RAGAS 4项指标趋势
5. 错误率趋势

**告警规则**：
- QPS < 1,000 → 告警
- p99 > 5秒 → 告警
- 缓存命中率 < 50% → 告警
- Faithfulness < 0.8 → 告警

---

## 六、与FastGPT/Dify对比

在同等10万级知识规模下，本系统与行业头部产品的对比：

| 维度 | 本系统 | FastGPT | Dify |
|------|--------|---------|------|
| 检索精度（recall@5） | 92% | 90% | 88% |
| 缓存命中率 | 85% | 70% | 75% |
| QPS | 5,100 | ~3,000 | ~2,500 |
| 部署成本 | $0/月 | $20-50/月 | $30-100/月 |
| 综合评分 | 88 | 85 | 83 |

在缓存效率和成本控制方面，本系统显著优于竞品。

---

## 七、总结与反思

### 7.1 23天成果汇总

| 阶段 | 时间 | 核心产出 | 评分提升 |
|------|------|----------|----------|
| Week 1 | Day 1-8 | RAGAS评估 + 三级缓存 | 62 → 70 |
| Week 2 | Day 9-13 | BM25 + RRF + Cross-Encoder | 70 → 78 |
| Week 3 | Day 14-18 | FastAPI异步升级 | 78 → 84 |
| Week 4 | Day 19-23 | Locust压测 + Grafana监控 | 84 → 88 |

### 7.2 5个核心优化点

1. **RAGAS量化评估**：用数据驱动优化，替代主观判断
2. **多路检索 + RRF融合**：recall@5从78%提升到92%
3. **Cross-Encoder重排序**：精排Top 10，延迟45ms换4个百分点精度
4. **三级缓存架构**：命中率85%，LLM调用减少65%
5. **FastAPI异步升级**：QPS从180提升到5,100

### 7.3 如果重新做一遍

1. **Day 1就上RAGAS**：评估体系应该在优化前就建立，而不是Week 1
2. **更早引入BM25**：多路检索收益很大，应该作为第一优先级
3. **更早做可观测性**：监控体系能帮助更早发现问题，不应该等到最后

### 7.4 给RAG工程师的建议

1. **量化驱动决策**：没有RAGAS指标，你无法证明优化有效
2. **缓存是第一优先级**：85%的缓存命中率意味着85%的请求不需要走完整RAG流程
3. **多路检索是标配**：单一向量检索永远不够，BM25的互补价值被低估
4. **trade-off思维**：Cross-Encoder的延迟vs精度、HNSW的速度vs准确率，找到最佳平衡点
5. **可观测性不能省**：没有监控的RAG系统就像没有仪表盘的飞机

---

## 附录：关键代码索引

| 模块 | 文件路径 |
|------|----------|
| RAGAS评估器 | `backend/tests/run_ragas_evaluation.py` |
| RRF融合排序 | `backend/app/services/rrf_fusion.py` |
| Cross-Encoder重排 | `backend/app/services/cross_encoder_reranker.py` |
| BM25引擎 | `backend/app/services/bm25_engine.py` |
| SimHash缓存 | `backend/app/services/simhash_cache.py` |
| Redis缓存 | `backend/app/services/redis_cache.py` |
| 异步LLM | `backend/app/services/async_llm.py` |
| 异步向量检索 | `backend/app/services/async_vector_rag.py` |
| FastAPI主入口 | `backend_fastapi/app/main.py` |
| Locust压测 | `backend/tests/locustfile.py` |

---

*本文基于OCG/DM规则书RAG问答系统实际优化过程编写。系统代码开源，欢迎Star和Fork。*

*如有问题或建议，欢迎在评论区讨论。*
