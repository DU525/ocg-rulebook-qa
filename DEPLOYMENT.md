# 部署文档

本文档描述 OCG Rulebook QA 系统的完整部署流程、回滚机制和常见问题排查。

## 目录

- [架构概览](#架构概览)
- [CI/CD 流水线](#cicd-流水线)
- [环境配置](#环境配置)
- [自动部署流程](#自动部署流程)
- [手动部署流程](#手动部署流程)
- [回滚流程](#回滚流程)
- [健康检查](#健康检查)
- [发布检查清单](#发布检查清单)
- [监控与告警](#监控与告警)
- [常见问题排查](#常见问题排查)

## 架构概览

### 部署架构

```
GitHub Actions CI/CD
       │
       ├── RAGAS Evaluation (质量评估)
       ├── Code Quality (代码质量)
       ├── Performance Test (性能测试)
       │
       └── Auto Deploy (自动部署)
              │
              ├── Build Docker Image
              ├── Push to GHCR
              ├── Deploy to Server
              ├── Health Check
              └── Auto Rollback (on failure)
```

### 容器配置

- 容器名称: `ocg-rulebook-qa`
- 端口映射: `5000:5000`
- 数据卷: `/opt/ocg-rulebook-qa/data:/app/backend/data`
- 环境变量: `/opt/ocg-rulebook-qa/.env:/app/backend/.env`
- 重启策略: `unless-stopped`
- 健康检查: 每30秒检查 `/api/v1/health` 端点

## CI/CD 流水线

### 工作流文件

| 文件 | 触发条件 | 功能 |
|------|---------|------|
| `ragas-evaluation.yml` | push到main分支 | RAG质量评估 + 自动部署 + 自动回滚 |
| `auto-deploy.yml` | push到main分支 / 手动触发 | 完整测试 + Docker构建 + 部署 |
| `rollback.yml` | 手动触发 | 手动回滚到指定版本 |
| `code-quality.yml` | PR到main分支 | Python和前端代码质量检查 |
| `performance-test.yml` | push到main分支 / 定时 | 性能负载测试 |

### 部署流程

1. 代码推送到 main 分支
2. 触发 RAGAS 评估和质量检查
3. 所有测试通过后构建 Docker 镜像
4. 推送镜像到 GitHub Container Registry
5. SSH到服务器拉取并运行新镜像
6. 运行健康检查验证部署
7. 发送通知（Slack/DingTalk）
8. 如果任何步骤失败，自动回滚到上一版本

### 质量门禁

- RAGAS Faithfulness >= 0.80
- RAGAS Answer Relevance >= 0.70
- 代码质量检查通过
- 前端构建成功
- 健康检查通过

## 环境配置

### 服务器要求

- Ubuntu 20.04+ / CentOS 8+
- Docker 20.10+
- 4GB+ RAM
- 20GB+ 可用磁盘空间
- 端口 5000 可用

### GitHub Secrets 配置

在 GitHub 仓库 Settings -> Secrets and variables -> Actions 中配置以下密钥:

| Secret | 说明 | 示例 |
|--------|------|------|
| `DEPLOY_SERVER` | 部署服务器地址 | `192.168.1.100` |
| `DEPLOY_USER` | SSH登录用户 | `deploy` |
| `DEPLOY_SSH_KEY` | SSH私钥 | `-----BEGIN OPENSSH PRIVATE KEY-----...` |
| `DINGTALK_WEBHOOK` | 钉钉通知Webhook URL | `https://oapi.dingtalk.com/robot/send?access_token=...` |
| `SLACK_WEBHOOK_URL` | Slack通知Webhook URL | `https://hooks.slack.com/services/...` |

### 服务器初始化

在部署服务器上执行以下命令初始化环境:

```bash
sudo mkdir -p /opt/ocg-rulebook-qa/data
sudo mkdir -p /opt/ocg-rulebook-qa/backups
sudo mkdir -p /opt/ocg-rulebook-qa/deploy-history

sudo cp .env /opt/ocg-rulebook-qa/.env
sudo chmod 600 /opt/ocg-rulebook-qa/.env

sudo usermod -aG docker $USER
```

## 自动部署流程

### 触发方式

自动部署在以下情况触发:

1. 代码推送到 main 分支
2. RAGAS 评估通过
3. 所有测试通过

### 部署步骤

```bash
# 开发者推送代码
git push origin main

# CI/CD 自动执行:
# 1. RAGAS Evaluation
# 2. Run All Tests
# 3. Build Docker Image
# 4. Push to GHCR
# 5. Deploy to Server
# 6. Health Check
# 7. Send Notification
```

### 部署验证

部署完成后，通过以下方式验证:

```bash
curl -s http://<server>:5000/api/v1/health | jq

docker ps --filter name=ocg-rulebook-qa

docker logs ocg-rulebook-qa --tail 50
```

## 手动部署流程

### 使用部署脚本

```bash
cd /opt/ocg-rulebook-qa

bash deploy/deploy.sh
bash deploy/deploy.sh --dry-run
bash deploy/deploy.sh --env staging
bash deploy/deploy.sh --image ghcr.io/user/ocg-rulebook-qa:abc1234
```

### 使用 GitHub Actions 手动触发

1. 进入 GitHub 仓库 -> Actions
2. 选择 "Auto Deploy" 工作流
3. 点击 "Run workflow"
4. 选择环境和是否强制部署
5. 点击 "Run workflow" 执行

## 回滚流程

### 自动回滚

当以下情况发生时，系统会自动回滚:

1. 部署后健康检查失败
2. 烟雾测试失败
3. 服务启动超时

### 手动回滚

#### 方式1: 使用 GitHub Actions

1. 进入 GitHub 仓库 -> Actions
2. 选择 "Manual Rollback" 工作流
3. 点击 "Run workflow"
4. 填写回滚原因和目标版本（可选）
5. 点击 "Run workflow" 执行

#### 方式2: 使用回滚脚本

```bash
cd /opt/ocg-rulebook-qa

bash deploy/rollback.sh
bash deploy/rollback.sh --version abc1234
bash deploy/rollback.sh --list
bash deploy/rollback.sh --dry-run
```

### 回滚验证

```bash
curl -s http://<server>:5000/api/v1/health | jq

cat /opt/ocg-rulebook-qa/deploy-history/rollback.log

docker logs ocg-rulebook-qa --tail 50
```

## 健康检查

### 自动健康检查

部署脚本会自动执行健康检查:

- 默认重试30次，每次间隔2秒
- 检查 `/api/v1/health` 端点
- 验证HTTP状态码为200
- 可选验证响应内容

### 手动健康检查

```bash
bash deploy/health_check.sh
bash deploy/health_check.sh --verbose
bash deploy/health_check.sh --json
bash deploy/health_check.sh --timeout 60 --retries 5
```

### 健康检查端点

```
GET /api/v1/health

Response (200 OK):
{
  "status": "healthy",
  "version": "1.0.0",
  "timestamp": "2024-01-01T00:00:00Z",
  "checks": {
    "database": "ok",
    "cache": "ok",
    "model": "ok"
  }
}
```

## 发布检查清单

### 发布前检查

- [ ] 所有代码已提交并推送到 main 分支
- [ ] CI/CD 流水线全部通过
- [ ] RAGAS 评估分数达标
- [ ] 性能测试无回归
- [ ] 代码质量检查通过
- [ ] 已通知团队成员即将发布
- [ ] 已确认回滚方案

### 发布中检查

- [ ] 部署脚本执行成功
- [ ] Docker 镜像构建成功
- [ ] 镜像推送到仓库成功
- [ ] 容器启动成功
- [ ] 健康检查通过
- [ ] 烟雾测试通过

### 发布后检查

- [ ] 服务响应正常
- [ ] API 端点可访问
- [ ] 搜索功能正常
- [ ] 对话功能正常
- [ ] 监控指标正常
- [ ] 无错误日志
- [ ] 已发送发布通知
- [ ] 已更新发布文档

### 紧急回滚触发条件

- [ ] 健康检查失败超过5分钟
- [ ] 核心API返回错误率 > 5%
- [ ] 响应时间 P95 > 5秒
- [ ] 数据库连接失败
- [ ] 内存使用率 > 90%
- [ ] 磁盘使用率 > 90%

## 监控与告警

### Docker 监控

```bash
docker stats ocg-rulebook-qa

docker logs ocg-rulebook-qa --tail 100 -f

docker inspect ocg-rulebook-qa | jq '.[0].State.Health'
```

### 日志查看

```bash
docker logs ocg-rulebook-qa
docker logs ocg-rulebook-qa --tail 100
docker logs ocg-rulebook-qa --tail 100 -f
docker logs ocg-rulebook-qa --since 1h
```

### 部署历史

```bash
cat /opt/ocg-rulebook-qa/deploy-history/history.log
cat /opt/ocg-rulebook-qa/deploy-history/rollback.log
cat /opt/ocg-rulebook-qa/deploy-history/latest_version.txt
```

### 备份管理

```bash
ls -lt /opt/ocg-rulebook-qa/backups/
ls -lt /opt/ocg-rulebook-qa/rollback-backups/
```

## 常见问题排查

### Q: 部署失败，健康检查不通过

**症状**: 部署脚本输出 "Health check failed"

**排查步骤**:

1. 检查容器状态
```bash
docker ps -a --filter name=ocg-rulebook-qa
```

2. 查看容器日志
```bash
docker logs ocg-rulebook-qa --tail 100
```

3. 检查端口占用
```bash
sudo lsof -i :5000
```

4. 检查数据卷权限
```bash
ls -la /opt/ocg-rulebook-qa/data/
```

5. 检查 .env 文件
```bash
cat /opt/ocg-rulebook-qa/.env
```

**解决方案**:

```bash
bash deploy/rollback.sh
```

### Q: Docker 镜像拉取失败

**症状**: 部署输出 "Failed to pull image"

**排查步骤**:

1. 检查网络连接
```bash
curl -I https://ghcr.io
```

2. 检查 Docker 登录状态
```bash
docker login ghcr.io
```

3. 验证镜像是否存在
```bash
docker manifest inspect ghcr.io/<user>/ocg-rulebook-qa:<tag>
```

**解决方案**:

```bash
docker logout ghcr.io
echo $GITHUB_TOKEN | docker login ghcr.io -u $GITHUB_ACTOR --password-stdin
bash deploy/deploy.sh
```

### Q: 容器频繁重启

**症状**: `docker ps` 显示容器状态为 "Restarting"

**排查步骤**:

1. 查看容器退出码
```bash
docker inspect ocg-rulebook-qa --format='{{.State.ExitCode}}'
```

2. 查看重启次数
```bash
docker inspect ocg-rulebook-qa --format='{{.RestartCount}}'
```

3. 查看完整日志
```bash
docker logs ocg-rulebook-qa --tail 500
```

**解决方案**:

```bash
docker stop ocg-rulebook-qa
docker rm ocg-rulebook-qa

docker run -d \
  --name ocg-rulebook-qa \
  -p 5000:5000 \
  -v /opt/ocg-rulebook-qa/data:/app/backend/data \
  -v /opt/ocg-rulebook-qa/.env:/app/backend/.env \
  -e FLASK_ENV=production \
  --restart unless-stopped \
  ghcr.io/<user>/ocg-rulebook-qa:<tag>
```

### Q: 磁盘空间不足

**症状**: 部署失败，日志显示 "no space left on device"

**解决方案**:

```bash
df -h

docker system df

docker system prune -a

docker images | grep "<none>" | awk '{print $3}' | xargs docker rmi

rm -rf /opt/ocg-rulebook-qa/backups/*
```

### Q: 回滚失败

**症状**: 执行 rollback.sh 后服务仍不正常

**排查步骤**:

1. 检查目标版本是否存在
```bash
bash deploy/rollback.sh --list
```

2. 检查备份文件
```bash
ls -lt /opt/ocg-rulebook-qa/backups/
ls -lt /opt/ocg-rulebook-qa/rollback-backups/
```

3. 手动恢复
```bash
docker stop ocg-rulebook-qa
docker rm ocg-rulebook-qa

docker run -d \
  --name ocg-rulebook-qa \
  -p 5000:5000 \
  -v /opt/ocg-rulebook-qa/data:/app/backend/data \
  -v /opt/ocg-rulebook-qa/.env:/app/backend/.env \
  -e FLASK_ENV=production \
  ghcr.io/<user>/ocg-rulebook-qa:<previous-version>
```

### Q: SSH 连接失败

**症状**: 部署输出 "Permission denied" 或 "Connection refused"

**解决方案**:

1. 验证 SSH 密钥
```bash
ssh -i ~/.ssh/id_ed25519 ${DEPLOY_USER}@${DEPLOY_SERVER}
```

2. 检查 SSH 服务
```bash
sudo systemctl status sshd
```

3. 更新 GitHub Secrets
```bash
cat ~/.ssh/id_ed25519 | pbcopy
# 更新 GitHub Secrets -> DEPLOY_SSH_KEY
```

## 附录

### 环境变量说明

| 变量 | 说明 | 默认值 |
|------|------|--------|
| `FLASK_ENV` | Flask运行环境 | `production` |
| `DEPLOY_VERSION` | 部署版本 | - |
| `DEPLOY_TIME` | 部署时间 | - |
| `ROLLBACK_TIME` | 回滚时间 | - |

### 端口说明

| 端口 | 协议 | 说明 |
|------|------|------|
| 5000 | HTTP | 主服务端口 |

### 目录结构

```
/opt/ocg-rulebook-qa/
├── data/                    # 数据目录
│   ├── vector_db/          # 向量数据库
│   └── conversations/      # 对话记录
├── backups/                 # 部署备份
├── rollback-backups/        # 回滚备份
├── deploy-history/          # 部署历史
│   ├── history.log         # 部署日志
│   ├── rollback.log        # 回滚日志
│   └── latest_version.txt  # 当前版本
├── .env                     # 环境变量文件
└── deploy/                  # 部署脚本
    ├── deploy.sh
    ├── rollback.sh
    ├── health_check.sh
    └── README.md
```

### 版本管理

版本格式: `<git-commit-sha>`

示例: `abc1234def567890`

查看当前版本:
```bash
cat /opt/ocg-rulebook-qa/deploy-history/latest_version.txt

docker inspect ocg-rulebook-qa --format='{{.Config.Image}}'
```
