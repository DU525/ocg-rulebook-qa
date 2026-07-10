# OCG/DM规则书RAG问答系统 - 架构图

> 格式：Mermaid（支持Markdown渲染）
> 生成日期：2026-05-23

---

## 一、系统整体架构图

```mermaid
graph TB
    subgraph 前端层
        UI[React UI<br/>Vite + TypeScript]
        Chat[ChatWindow组件]
        Render[Markdown渲染<br/>react-markdown]
        Stream[打字机效果<br/>Typewriter Buffer]
    end

    subgraph 网关层
        LB[负载均衡<br/>Nginx/反向代理]
        CORS[CORS中间件]
        RateLimit[请求限流]
    end

    subgraph 后端服务层
        subgraph Flask生产环境
            F_API[Flask API路由<br/>routes.py / dm_routes.py]
            RAG[RAG引擎<br/>rag_engine.py]
            SVC[领域服务<br/>domain_services.py]
        end

        subgraph FastAPI异步环境
            FA_API[FastAPI路由<br/>main.py]
            FA_SVC[异步服务<br/>service_manager.py]
            FA_MET[指标采集<br/>metrics.py]
        end
    end

    subgraph 检索层
        VC[向量检索<br/>FAISS HNSW]
        BM[BM25检索<br/>Whoosh + jieba]
        RRF[RRF融合排序<br/>rrf_fusion.py]
        CE[Cross-Encoder重排<br/>cross_encoder_reranker.py]
    end

    subgraph 缓存层
        L1[L1 内存LRU缓存<br/>functools.lru_cache]
        L2[L2 Redis缓存<br/>redis-cache]
        L3[L3 SimHash语义缓存<br/>simhash_cache.py]
    end

    subgraph 存储层
        FAISS_OCG[FAISS索引<br/>ocg_rules_index.bin<br/>355.67MB / 118,298条]
        FAISS_DM[FAISS索引<br/>dm_rules_index.bin<br/>6,511条]
        SQLITE[(SQLite<br/>对话历史+文档)]
        REDIS[(Redis<br/>L2缓存)]
    end

    subgraph LLM层
        LLM_MAIN[MiniMax M2.7<br/>主模型]
        LLM_FALLBACK[OpenAI<br/>降级模型]
    end

    subgraph 监控层
        PROM[Prometheus<br/>指标采集]
        GRAF[Grafana<br/>5面板看板]
        ALERT[告警规则<br/>alert_rules.yml]
    end

    UI --> Chat
    Chat --> Render
    Chat --> Stream
    UI -->|HTTP API| LB
    LB --> CORS
    CORS --> RateLimit
    RateLimit --> F_API
    RateLimit --> FA_API
    F_API --> RAG
    FA_API --> FA_SVC
    RAG --> SVC
    FA_SVC --> FA_MET

    SVC --> L1
    FA_SVC --> L1
    L1 -.未命中.-> L2
    L2 -.未命中.-> L3
    L3 -.未命中.-> VC
    L3 -.未命中.-> BM

    VC --> RRF
    BM --> RRF
    RRF --> CE

    CE --> RAG
    CE --> FA_SVC

    VC --> FAISS_OCG
    VC --> FAISS_DM
    F_API --> SQLITE
    FA_API --> SQLITE
    L2 --> REDIS

    RAG --> LLM_MAIN
    FA_SVC --> LLM_MAIN
    LLM_MAIN -.超时/失败.-> LLM_FALLBACK

    FA_MET --> PROM
    PROM --> GRAF
    PROM --> ALERT
```

---

## 二、检索流程时序图

```mermaid
sequenceDiagram
    participant U as 用户
    participant FE as 前端React
    participant GW as 网关/限流
    participant API as API路由
    participant C as 缓存层<br/>L1+L2+L3
    participant E as Embedding<br/>text2vec
    participant V as 向量检索<br/>FAISS HNSW
    participant B as BM25检索<br/>Whoosh
    participant R as RRF融合
    participant CE as Cross-Encoder
    participant LLM as LLM<br/>MiniMax M2.7

    U->>FE: 输入问题
    FE->>GW: POST /api/v1/chat/question
    GW->>API: 限流检查通过
    API->>C: 查询缓存 MD5(question)
    
    alt 缓存命中
        C-->>API: 返回缓存结果
        API-->>FE: 返回答案
        FE-->>U: 打字机效果展示
    else 缓存未命中
        API->>E: 编码query → 768维向量
        E-->>API: 返回向量
        
        par 并行检索
            API->>V: FAISS搜索 Top 50
            V-->>API: 向量检索结果
        and
            API->>B: BM25搜索 Top 50
            B-->>API: BM25检索结果
        end
        
        API->>R: RRF融合排序
        Note over R: score(d) = Σ 1/(k+rank(d))<br/>向量70% + BM25 30%
        R-->>API: 融合后 Top 10
        
        API->>CE: Cross-Encoder精排
        Note over CE: ms-marco-MiniLM-L-6-v2<br/>交互注意力计算
        CE-->>API: 重排后 Top 5
        
        API->>LLM: 构建Prompt + Top 5上下文
        LLM-->>API: 生成答案 + 引用来源
        
        API->>C: 写入缓存 TLL=24h
        API-->>FE: SSE流式返回
        FE-->>U: 打字机效果逐字展示
    end
```

---

## 三、多级缓存架构图

```mermaid
graph TB
    subgraph 查询入口
        Q[用户查询]
    end

    subgraph L1_内存层["L1 内存LRU缓存"]
        MD5[MD5哈希计算]
        LRU[LRU缓存<br/>maxsize=10,000]
        HIT1{命中?}
        T1[延迟 < 0.1ms]
    end

    subgraph L2_Redis层["L2 Redis分布式缓存"]
        REDIS_CLIENT[Redis客户端]
        REDIS_STORE[(Redis Store<br/>maxmemory=1GB<br/>allkeys-lru)]
        TTL[动态TTL<br/>热门7d/普通24h/冷门1h]
        HIT2{命中?}
        T2[延迟 < 1ms]
    end

    subgraph L3_语义层["L3 SimHash语义缓存"]
        SIMHASH[SimHash指纹计算<br/>64位]
        HAMMING[汉明距离计算<br/>threshold ≤ 3]
        SIM_STORE[(语义缓存索引)]
        HIT3{命中?}
        T3[延迟 < 2ms]
    end

    subgraph 完整RAG流程
        RAG[向量检索 + BM25<br/>+ RRF + Cross-Encoder<br/>+ LLM生成]
        TRAG[延迟 2,000-12,000ms]
    end

    subgraph 缓存管理
        PREHEAT[服务启动预热<br/>Top 100热门查询]
        STATS[缓存统计监控<br/>命中率/大小/淘汰率]
        EVICT[淘汰策略<br/>LRU + TTL过期]
    end

    Q --> MD5
    MD5 --> LRU
    LRU --> HIT1
    
    HIT1 -->|是| T1
    HIT1 -->|否| REDIS_CLIENT
    
    REDIS_CLIENT --> REDIS_STORE
    REDIS_STORE --> TTL
    TTL --> HIT2
    
    HIT2 -->|是| T2
    HIT2 -->|否| SIMHASH
    
    SIMHASH --> HAMMING
    HAMMING --> SIM_STORE
    SIM_STORE --> HIT3
    
    HIT3 -->|是| T3
    HIT3 -->|否| RAG
    
    RAG --> TRAG
    
    T1 --> Q_OUT[返回结果]
    T2 --> Q_OUT
    T3 --> Q_OUT
    TRAG --> Q_OUT
    
    Q_OUT -.写入.-> REDIS_STORE
    Q_OUT -.写入.-> LRU
    Q_OUT -.写入.-> SIM_STORE
    
    PREHEAT -.启动时.-> LRU
    PREHEAT -.启动时.-> REDIS_STORE
    
    LRU -.监控.-> STATS
    REDIS_STORE -.监控.-> STATS
    SIM_STORE -.监控.-> STATS
    
    STATS --> EVICT
    TTL -.触发.-> EVICT
    LRU -.满时.-> EVICT
```

---

## 四、数据流向图

```mermaid
flowchart LR
    subgraph 数据采集
        RAW1[OCG规则书PDF<br/>规则+判例+Wiki]
        RAW2[DM规则书PDF<br/>数码宝贝对战规则]
    end

    subgraph 数据处理
        PARSE[文档解析<br/>Markdown分割]
        CHUNK[分块处理<br/>chunk_size=512<br/>overlap=128]
        CLEAN[数据清洗<br/>去重+格式标准化]
    end

    subgraph 向量化
        EMBED[Embedding编码<br/>text2vec-base-chinese<br/>768维]
        FAISS_BUILD[FAISS索引构建<br/>IndexHNSWFlat<br/>M=8, ef=64]
    end

    subgraph 索引存储
        IDX_OCG[OCG索引<br/>ocg_rules_index.bin<br/>355.67MB / 118,298条]
        IDX_DM[DM索引<br/>dm_rules_index.bin<br/>6,511条]
        CHUNKS_OCG[分块数据<br/>ocg_rules_chunks.json]
        CHUNKS_DM[分块数据<br/>dm_rules_chunks.json]
    end

    subgraph 在线检索
        QUERY[用户查询]
        Q_EMBED[Query编码]
        V_SEARCH[FAISS搜索<br/>ef_search=64]
        BM_SEARCH[BM25搜索]
        FUSION[RRF融合]
        RERANK[Cross-Encoder重排]
    end

    subgraph 答案生成
        PROMPT[Prompt构建<br/>SYSTEM_PROMPT + 上下文]
        GEN[LLM生成<br/>MiniMax M2.7]
        ANSWER[答案 + 引用来源]
    end

    subgraph 缓存写入
        CACHE_W[多级缓存写入<br/>L1+L2+L3]
    end

    RAW1 --> PARSE
    RAW2 --> PARSE
    PARSE --> CHUNK
    CHUNK --> CLEAN
    CLEAN --> EMBED
    EMBED --> FAISS_BUILD
    
    FAISS_BUILD --> IDX_OCG
    FAISS_BUILD --> IDX_DM
    CHUNK --> CHUNKS_OCG
    CHUNK --> CHUNKS_DM
    
    QUERY --> Q_EMBED
    Q_EMBED --> V_SEARCH
    Q_EMBED --> BM_SEARCH
    IDX_OCG --> V_SEARCH
    IDX_DM --> V_SEARCH
    CHUNKS_OCG --> BM_SEARCH
    
    V_SEARCH --> FUSION
    BM_SEARCH --> FUSION
    FUSION --> RERANK
    RERANK --> PROMPT
    
    PROMPT --> GEN
    GEN --> ANSWER
    ANSWER --> CACHE_W
    
    CACHE_W -.加速后续查询.-> QUERY
```

---

## 五、监控数据流图

```mermaid
graph TB
    subgraph 数据采集
        M1[HTTP请求计数器<br/>http_requests_total]
        M2[请求延迟直方图<br/>http_request_duration_seconds]
        M3[缓存命中率<br/>cache_hit_rate]
        M4[RAGAS指标<br/>faithfulness / precision / recall]
        M5[错误计数器<br/>http_errors_total]
    end

    subgraph 指标导出
        METRICS[/metrics 端点<br/>Prometheus格式]
    end

    subgraph Prometheus
        SCRAPE[定时采集<br/>interval=15s]
        TSDB[(时序数据库<br/>TSDB)]
    end

    subgraph Grafana
        DASH[Dashboard<br/>5个面板]
        P1[QPS实时曲线]
        P2[p50/p95/p99延迟]
        P3[缓存命中率]
        P4[RAGAS 4项指标]
        P5[错误率趋势]
    end

    subgraph 告警
        RULES[告警规则<br/>alert_rules.yml]
        R1[QPS < 1000]
        R2[p99 > 5s]
        R3[缓存命中率 < 50%]
        R4[Faithfulness < 0.8]
        NOTIFY[通知渠道<br/>飞书/邮件]
    end

    M1 --> METRICS
    M2 --> METRICS
    M3 --> METRICS
    M4 --> METRICS
    M5 --> METRICS
    
    METRICS --> SCRAPE
    SCRAPE --> TSDB
    TSDB --> DASH
    
    DASH --> P1
    DASH --> P2
    DASH --> P3
    DASH --> P4
    DASH --> P5
    
    TSDB --> RULES
    RULES --> R1
    RULES --> R2
    RULES --> R3
    RULES --> R4
    
    R1 --> NOTIFY
    R2 --> NOTIFY
    R3 --> NOTIFY
    R4 --> NOTIFY
```

---

## 六、FastAPI异步架构对比图

```mermaid
graph TB
    subgraph Flask同步架构
        F1[请求A到达]
        F2[同步向量检索<br/>阻塞worker]
        F3[同步LLM调用<br/>阻塞worker 2-10s]
        F4[返回响应]
        F5[请求B到达<br/>等待worker空闲]
        F6[请求C到达<br/>排队等待]
        
        F1 --> F2 --> F3 --> F4
        F5 -.等待.-> F2
        F6 -.等待.-> F3
    end

    subgraph FastAPI异步架构
        A1[请求A到达]
        A2[asyncio.to_thread<br/>FAISS搜索]
        A3[aiohttp异步LLM<br/>await响应]
        A4[返回响应]
        A5[请求B到达<br/>不阻塞，并行处理]
        A6[请求C到达<br/>不阻塞，并行处理]
        A7[请求D到达<br/>不阻塞，并行处理]
        
        A1 --> A2 --> A3 --> A4
        A5 --> A2
        A6 --> A2
        A7 --> A2
    end

    subgraph 性能对比
        C1[Flask QPS: 180<br/>p99延迟: 250ms]
        C2[FastAPI QPS: 5,100<br/>p99延迟: 45ms]
        C3[提升: +2,733%<br/>延迟降低: 82%]
    end

    C1 --> C2 --> C3
```

---

*本架构图使用Mermaid语法，可在支持Mermaid的Markdown编辑器中渲染*
*推荐工具：Obsidian、GitHub、Notion、VS Code + Mermaid插件*
