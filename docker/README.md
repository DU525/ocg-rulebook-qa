# OCG 规则书问答系统 - Docker 部署指南

## 架构概述

```
                    ┌─────────────────────────────────────────────┐
                    │              Nginx (:80)                     │
                    │        反向代理 + 静态文件服务                │
                    └────┬──────────────┬──────────────┬───────────┘
                         │              │              │
          ┌──────────────┘              │              └──────────────┐
          │                             │                             │
   ┌──────▼──────┐              ┌───────▼───────┐             ┌───────▼───────┐
   │   前端 SPA   │              │  后端 Flask    │             │   Grafana     │
   │   (Nginx)    │              │   API (:5000)  │             │   (:3000)     │
   │             │              │               │             │               │
   │ React+Vite   │              │  RAG + RRF    │             │  Dashboards   │
   └─────────────┘              └───────┬───────┘             └───────▲───────┘
                                        │                             │
                               ┌────────┴────────┐                    │
                               │                 │                    │
                        ┌──────▼──────┐   ┌──────▼──────┐      ┌──────▼──────┐
                        │    Redis     │   │ Prometheus   │      │ Prometheus  │
                        │   (:6379)    │   │   (:9090)    │      │  Scrape     │
                        │   缓存层      │   │   指标采集    │      └─────────────┘
                        └─────────────┘   └─────────────┘
```

## 服务列表

| 服务        | 镜像                           | 端口（内部） | 说明                       |
|------------|-------------------------------|-------------|---------------------------|
| nginx      | nginx:1.25-alpine             | 80          | 反向代理 + 统一入口         |
| frontend   | 自定义构建 (Node.js + Nginx)   | 80          | 前端静态文件服务             |
| backend    | 自定义构建 (Python 3.11)       | 5000        | Flask API + RAG 引擎        |
| redis      | redis:7-alpine                | 6379        | 查询缓存                    |
| prometheus | prom/prometheus:v2.48.0       | 9090        | 指标采集与存储               |
| grafana    | grafana/grafana:10.2.2        | 3000        | 监控可视化面板               |

## 端口映射

| 外部端口 | 内部服务        | 访问地址                   |
|---------|----------------|---------------------------|
| 80      | Nginx          | http://localhost          |
| 80      | Grafana        | http://localhost/grafana  |
| 80      | Prometheus     | http://localhost/prometheus |

## 快速开始

### 前置条件

- Docker 20.10+
- Docker Compose v2.0+
- 至少 4GB 可用内存
- 至少 10GB 可用磁盘空间

### 1. 克隆项目

```bash
cd C:\Users\1\Downloads\ocg-rulebook-qa\ocg-rulebook-qa\
```

### 2. 配置环境变量

复制环境变量模板：

```bash
cp backend/.env.example .env
```

编辑 `.env` 文件，设置必要的环境变量：

```bash
# LLM API 密钥（必需）
MINIMAX_API_KEY=your-api-key-here

# Grafana 登录凭据（可选）
GRAFANA_ADMIN_USER=admin
GRAFANA_ADMIN_PASSWORD=admin

# 应用密钥（可选，建议在生产环境修改）
SECRET_KEY=your-secret-key
```

### 3. 一键启动

```bash
docker compose up -d
```

### 4. 验证部署

```bash
# 检查所有服务状态
docker compose ps

# 查看日志
docker compose logs -f

# 健康检查
curl http://localhost/api/v1/health
```

## 常用命令

### 启动服务

```bash
# 启动所有服务
docker compose up -d

# 启动单个服务
docker compose up -d backend

# 重建并启动（代码修改后）
docker compose up -d --build
```

### 查看状态

```bash
# 查看所有服务状态
docker compose ps

# 查看实时日志
docker compose logs -f backend

# 查看某个服务的日志
docker compose logs -f frontend

# 查看资源使用情况
docker stats
```

### 停止与清理

```bash
# 停止所有服务
docker compose stop

# 停止并删除容器（保留数据卷）
docker compose down

# 停止并删除容器 + 数据卷（危险操作！）
docker compose down -v

# 停止并删除容器 + 数据卷 + 镜像
docker compose down -v --rmi all
```

### 数据库与知识初始化

```bash
# 进入后端容器
docker compose exec backend bash

# 在容器内初始化知识库
python scripts/init_knowledge_base.py

# 导入知识数据
python scripts/import_knowledge_base.py
```

## 数据持久化

以下数据通过 Docker Volume 持久化：

| 卷名            | 挂载路径                    | 说明             |
|----------------|---------------------------|-----------------|
| redis-data     | /data                     | Redis 缓存数据    |
| prometheus-data| /prometheus               | Prometheus 指标   |
| grafana-data   | /var/lib/grafana          | Grafana 配置      |
| ./data         | /app/data                 | 知识库数据文件     |

## 监控

### Grafana

- 访问地址：http://localhost/grafana
- 默认用户：admin
- 默认密码：admin（在 `.env` 中修改）
- 数据源：Prometheus 已自动配置

### Prometheus

- 访问地址：http://localhost/prometheus
- 指标采集间隔：15 秒（后端 5 秒）
- 数据保留：15 天

### 后端指标

- `/metrics` - Prometheus 指标端点
- `/api/v1/health` - 健康检查端点

## 故障排除

### 服务启动失败

```bash
# 查看具体服务日志
docker compose logs backend

# 检查端口占用
netstat -tulpn | grep :80

# 检查 Docker 资源
docker system df
```

### 后端无法连接 Redis

```bash
# 检查 Redis 是否就绪
docker compose exec redis redis-cli ping

# 重启后端
docker compose restart backend
```

### 前端无法访问后端 API

Nginx 已配置代理转发，检查：
- Nginx 配置是否正确：`docker compose exec nginx nginx -t`
- 后端是否健康：`curl http://localhost/api/v1/health`

### 知识库数据丢失

数据挂载在 `./data` 目录，确保：
- 该目录在宿主机上存在
- 有正确的读写权限

## 生产部署建议

1. **HTTPS**：在 Nginx 前添加 Let's Encrypt 证书
2. **密钥管理**：使用 Docker Secrets 或外部密钥管理服务
3. **日志轮转**：配置 Docker 日志驱动
4. **资源限制**：在 docker-compose.yml 中添加 `deploy.resources`
5. **备份策略**：定期备份 Docker Volume 数据
6. **健康检查**：配合编排系统（K8s/Swarm）使用

## 文件结构

```
ocg-rulebook-qa/
├── docker-compose.yml          # 主编排文件
├── Dockerfile.backend          # 后端多阶段构建
├── Dockerfile.frontend         # 前端多阶段构建
├── .dockerignore               # Docker 构建排除规则
├── .env                        # 环境变量（需自行创建）
├── docker/
│   ├── nginx.conf              # Nginx 反向代理配置
│   └── README.md               # 本文档
├── backend/
│   ├── requirements.txt        # Python 依赖
│   ├── run.py                  # 启动入口
│   └── ...
├── frontend/
│   ├── package.json            # Node.js 依赖
│   └── ...
├── monitoring/
│   ├── prometheus.yml          # Prometheus 配置
│   ├── alert_rules.yml         # 告警规则
│   └── grafana/
│       └── provisioning/       # Grafana 自动配置
└── data/                       # 知识库数据（持久化）
```

## 更新镜像

```bash
# 拉取最新代码
git pull

# 重新构建并启动
docker compose up -d --build

# 清理未使用的镜像
docker image prune -f
```
