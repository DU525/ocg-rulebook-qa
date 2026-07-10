# OCG Rulebook QA 监控方案

本文档描述了 OCG Rulebook QA 系统的 Prometheus + Grafana 监控集成方案。

## 目录

1. [部署指南](#部署指南)
2. [指标说明](#指标说明)
3. [看板使用说明](#看板使用说明)
4. [移动端访问配置](#移动端访问配置)

---

## 部署指南

### 前置要求

- Docker 和 Docker Compose 已安装
- Backend FastAPI 应用正在运行（默认端口 8000）

### 快速启动

1. 进入 monitoring 目录：
   ```bash
   cd monitoring
   ```

2. 启动 Prometheus 和 Grafana：
   ```bash
   docker-compose up -d
   ```

3. 访问服务：
   - Prometheus UI: http://localhost:9090
   - Grafana UI: http://localhost:3000
   - 应用指标: http://localhost:8000/metrics

4. 登录 Grafana：
   - 用户名: `admin`
   - 密码: `admin123`（首次登录会提示修改）

### 服务说明

| 服务 | 端口 | 说明 |
|------|------|------|
| Prometheus | 9090 | 时序数据库和监控服务器 |
| Grafana | 3000 | 可视化仪表盘 |

---

## 指标说明

### HTTP 指标

| 指标名称 | 类型 | 说明 |
|----------|------|------|
| `http_requests_total` | Counter | HTTP 请求总数，标签：method, endpoint, status_code |
| `http_request_duration_seconds` | Histogram | HTTP 请求耗时（秒），标签：method, endpoint |

### 缓存指标

| 指标名称 | 类型 | 说明 |
|----------|------|------|
| `cache_hit_rate` | Gauge | 缓存命中率（0.0 - 1.0） |

### RAGAS 指标

| 指标名称 | 类型 | 说明 |
|----------|------|------|
| `ragas_faithfulness` | Gauge | RAGAS Faithfulness 评分（0.0 - 1.0） |
| `ragas_answer_relevance` | Gauge | RAGAS Answer Relevance 评分（0.0 - 1.0） |

### 搜索和 LLM 指标

| 指标名称 | 类型 | 说明 |
|----------|------|------|
| `vector_search_latency_ms` | Histogram | 向量搜索耗时（毫秒） |
| `llm_call_total` | Counter | LLM 调用总数，标签：model, status |

---

## 看板使用说明

### 面板说明

1. **QPS 实时曲线**：每秒请求数的实时变化趋势
2. **P50/P95/P99 延迟**：不同分位的请求延迟（P50: 中位数，P99: 99%的请求在此时间内完成）
3. **缓存命中率**：当前缓存命中百分比，绿色表示良好
4. **RAGAS 指标**：Faithfulness 和 Answer Relevance 评分变化趋势
5. **错误率**：5xx 错误占总请求的百分比

### 常用操作

- **调整时间范围**：右上角选择查看过去 15 分钟、1 小时、6 小时、24 小时等
- **刷新频率**：右上角设置自动刷新（默认 5 秒）
- **查看详细数据**：鼠标悬停在图表上查看具体数值

---

## 移动端访问配置

### 方案一：内网穿透（推荐）

使用工具如 ngrok 或 frp 将本地端口暴露到公网：

1. 安装 ngrok
2. 运行：
   ```bash
   ngrok http 3000
   ```
3. 使用 ngrok 提供的公网地址在手机上访问

### 方案二：局域网访问

确保手机和电脑在同一局域网：

1. 查看电脑 IP 地址（Windows: `ipconfig`，Mac/Linux: `ifconfig`）
2. 在手机浏览器访问 `http://[电脑IP]:3000`

### Grafana 移动端优化

Grafana 默认支持响应式布局，移动端会自动适配。

---

## 告警规则

| 告警名称 | 触发条件 | 严重程度 |
|----------|----------|----------|
| LowQPS | QPS < 1000 | warning |
| HighP99Latency | P99 > 5ms | critical |
| LowCacheHitRate | 缓存命中率 < 50% | warning |
| LowFaithfulness | Faithfulness < 0.8 | critical |

---

## 停止服务

```bash
cd monitoring
docker-compose down
```

保留数据卷（下次启动数据会保留）：
```bash
docker-compose down --volumes
```
