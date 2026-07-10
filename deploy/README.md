# Deploy Scripts

部署脚本目录，包含自动化部署、回滚和健康检查脚本。

## 脚本说明

### deploy.sh
自动化部署脚本，支持一键部署新版本。

用法:
```bash
./deploy/deploy.sh [OPTIONS]
```

选项:
- `--image <image:tag>` - 指定要部署的镜像
- `--env <environment>` - 部署环境: production | staging
- `--skip-health-check` - 跳过健康检查
- `--dry-run` - 仅显示将要执行的操作
- `--help` - 显示帮助

示例:
```bash
./deploy/deploy.sh
./deploy/deploy.sh --image ghcr.io/user/ocg-rulebook-qa:abc1234
./deploy/deploy.sh --env staging --dry-run
```

### rollback.sh
一键回滚脚本，支持回滚到任意历史版本。

用法:
```bash
./deploy/rollback.sh [OPTIONS]
```

选项:
- `--version <version>` - 回滚到指定版本
- `--list` - 列出所有可用版本
- `--auto` - 自动回滚模式
- `--dry-run` - 仅显示将要执行的操作
- `--help` - 显示帮助

示例:
```bash
./deploy/rollback.sh
./deploy/rollback.sh --version abc1234
./deploy/rollback.sh --list
./deploy/rollback.sh --dry-run
```

### health_check.sh
服务健康检查脚本，支持多种输出格式。

用法:
```bash
./deploy/health_check.sh [OPTIONS]
```

选项:
- `--url <url>` - 健康检查URL
- `--timeout <seconds>` - 超时时间
- `--retries <count>` - 重试次数
- `--interval <seconds>` - 重试间隔
- `--verbose` - 显示详细输出
- `--json` - 输出JSON格式结果

示例:
```bash
./deploy/health_check.sh
./deploy/health_check.sh --verbose
./deploy/health_check.sh --json
./deploy/health_check.sh --timeout 60 --retries 5
```

## 目录结构

```
deploy/
├── deploy.sh          # 部署脚本
├── rollback.sh        # 回滚脚本
├── health_check.sh    # 健康检查脚本
└── README.md          # 本文件
```

## 部署目录

脚本默认使用以下目录:
- `/opt/ocg-rulebook-qa` - 部署根目录
- `/opt/ocg-rulebook-qa/data` - 数据目录
- `/opt/ocg-rulebook-qa/backups` - 备份目录
- `/opt/ocg-rulebook-qa/deploy-history` - 部署历史

## 前置条件

- Docker 已安装并运行
- curl 已安装
- jq 已安装
- 服务器端口 5000 可用
- 已配置 .env 文件在 /opt/ocg-rulebook-qa/.env

## 安全说明

- 部署脚本需要 root 或 docker 组权限
- 回滚前会自动创建备份
- 部署失败会自动触发回滚
- 所有操作都会记录到历史日志
