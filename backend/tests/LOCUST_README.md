
# OCG Rulebook QA System - Locust 压测文档

## 概述

本文档描述了如何使用 Locust 对 OCG Rulebook QA System 进行全链路压测。包含四个不同负载场景的测试脚本和自动化报告生成工具。

## 📁 文件说明

| 文件 | 说明 |
|------|------|
| `locustfile.py` | 主压测脚本，包含所有用户行为 |
| `locustfile_scene1.py` | 场景1：100并发用户（正常负载） |
| `locustfile_scene2.py` | 场景2：500并发用户（高负载） |
| `locustfile_scene3.py` | 场景3：1000并发用户（极限负载） |
| `locustfile_scene4.py` | 场景4：5000并发用户（压力测试） |
| `generate_report.py` | 报告生成脚本，自动生成 Markdown 报告和图表 |
| `locust_requirements.txt` | 压测工具依赖包 |
| `LOCUST_README.md` | 本文档 |

## 🚀 快速开始

### 1. 安装依赖

```bash
cd backend/tests
pip install -r locust_requirements.txt
```

### 2. 启动后端服务

确保您的 OCG Rulebook QA System 后端服务正在运行：

```bash
# 在 backend 目录下
python run.py
# 或
python run_debug.py
```

默认服务地址: `http://localhost:8000`

### 3. 运行压测（Web UI 模式）

```bash
# 使用场景1（100并发）
locust -f locustfile_scene1.py --host=http://localhost:8000

# 或者使用主脚本
locust -f locustfile.py --host=http://localhost:8000
```

然后在浏览器中打开: `http://localhost:8089`

### 4. 运行压测（Headless 模式）

```bash
# 场景1：100用户，10用户/秒增长，运行5分钟
locust -f locustfile_scene1.py --host=http://localhost:8000 \
    --headless -u 100 -r 10 -t 5m

# 场景2：500用户，10用户/秒增长，运行8分钟
locust -f locustfile_scene2.py --host=http://localhost:8000 \
    --headless -u 500 -r 10 -t 8m

# 导出结果为 CSV
locust -f locustfile_scene1.py --host=http://localhost:8000 \
    --headless -u 100 -r 10 -t 5m --csv=scene1
```

## 📊 压测场景详解

### 场景 1: 正常负载（100 并发）

**配置:**
- 用户数: 100
- 增长速率: 10 用户/秒
- 持续时间: 5 分钟
- 思考时间: 1-2 秒

**适用场景:**
- 日常性能基准测试
- 回归测试
- 开发验证

**运行命令:**
```bash
locust -f locustfile_scene1.py --host=http://localhost:8000
```

### 场景 2: 高负载（500 并发）

**配置:**
- 用户数: 500
- 增长速率: 10 用户/秒
- 持续时间: 8 分钟
- 思考时间: 0.5-1.5 秒

**适用场景:**
- 峰值负载测试
- 容量规划
- 性能瓶颈发现

**运行命令:**
```bash
locust -f locustfile_scene2.py --host=http://localhost:8000
```

### 场景 3: 极限负载（1000 并发）

**配置:**
- 用户数: 1000
- 增长速率: 10 用户/秒
- 持续时间: 10 分钟
- 思考时间: 0.3-1 秒

**适用场景:**
- 系统极限测试
- 高可用验证
- 灾难恢复测试

**运行命令:**
```bash
locust -f locustfile_scene3.py --host=http://localhost:8000
```

### 场景 4: 压力测试（5000 并发）

⚠️ **注意**: 此场景需要强大的服务器资源，建议使用分布式部署

**配置:**
- 用户数: 5000
- 增长速率: 10 用户/秒
- 持续时间: 10 分钟
- 思考时间: 0.1-0.5 秒

**适用场景:**
- 极端压力测试
- 分布式架构验证
- Auto-scaling 测试

**分布式部署运行:**

```bash
# 主控节点
locust -f locustfile_scene4.py --master --host=http://localhost:8000

# 工作节点（在多台机器上运行）
locust -f locustfile_scene4.py --worker --master-host=MASTER_IP --host=http://localhost:8000
```

## 🎯 测试的 API 端点

| 端点 | 方法 | 权重 | 说明 |
|------|------|------|------|
| `/api/v1/chat/question` | POST | 30-70 | 问答查询（主要负载） |
| `/api/v1/chat/question/stream` | POST | 15-25 | 流式问答 |
| `/api/v1/conversations` | GET | 10-15 | 获取对话列表 |
| `/api/v1/documents` | GET | 6-10 | 获取文档列表 |
| `/api/v1/metrics` | GET | 3-5 | 获取系统指标 |
| `/api/v1/health` | GET | 1-3 | 健康检查 |

## 📈 生成报告

### 生成演示报告

```bash
python generate_report.py --demo
```

报告将生成在 `reports/` 目录下，包含：
- 各场景的 Markdown 报告
- RPS、延迟、错误率等图表
- 场景对比报告

### 从测试数据生成报告

```bash
# 1. 运行压测并导出 CSV
locust -f locustfile_scene1.py --host=http://localhost:8000 \
    --headless -u 100 -r 10 -t 5m --csv=scene1

# 2. 生成报告（需要修改 generate_report.py 以支持实际数据加载）
# 目前演示模式可用于查看报告模板
python generate_report.py --demo
```

## 🔍 cProfile 性能分析

要进行更深入的性能分析，可以使用 cProfile：

```bash
# 启动服务时启用性能分析
python -m cProfile -o profile_stats.run run.py

# 分析结果
python -c "import pstats; p = pstats.Stats('profile_stats.run'); p.sort_stats('cumulative').print_stats(20)"
```

## 💡 优化建议

基于压测结果，您可能需要考虑以下优化：

### 1. 缓存层
- 实现 Redis 缓存热点查询
- 添加 L1/L2 多级缓存

### 2. 数据库优化
- 连接池优化
- 查询优化和索引
- 读写分离

### 3. 异步处理
- 使用 Celery 处理后台任务
- 流式响应优化

### 4. 架构扩展
- 负载均衡（Nginx）
- 水平扩展
- 容器化部署（Docker/K8s）

## 📋 压测检查清单

- [ ] 后端服务正常运行
- [ ] 数据库已初始化
- [ ] 向量索引已构建
- [ ] 网络带宽充足
- [ ] 测试机器资源足够
- [ ] 监控已配置（CPU、内存、磁盘、网络）
- [ ] 日志收集已就绪
- [ ] 备份已完成（生产环境）

## 🆘 常见问题

### Q: 压测时出现大量连接错误？
A: 检查服务器的文件描述符限制：
```bash
ulimit -n
ulimit -n 65536  # 增加限制
```

### Q: 如何监控服务器资源？
A: 使用以下工具：
```bash
# 实时监控
htop
iotop
nethogs

# 或使用 Prometheus + Grafana
```

### Q: 压测对生产环境有影响吗？
A: 不要在生产环境直接运行压测！使用独立的测试环境或影子流量测试。

## 📚 参考资源

- [Locust 官方文档](https://docs.locust.io/)
- [性能测试最佳实践](https://martinfowler.com/articles/performance-testing.html)
- [Web 性能优化指南](https://web.dev/fast/)

## 📄 许可证

同主项目许可证。

