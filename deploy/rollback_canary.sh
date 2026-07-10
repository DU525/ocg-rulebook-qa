#!/bin/bash
set -euo pipefail

###############################################################################
# rollback_canary.sh - 金丝雀回滚脚本
# 用法: ./deploy/rollback_canary.sh [OPTIONS]
#   OPTIONS:
#     --version <version>     回滚到指定版本 (默认: 上一个稳定版本)
#     --force                 强制回滚，跳过确认
#     --dry-run               仅显示操作，不实际执行
#     --help                  显示帮助信息
#
# 示例:
#   ./deploy/rollback_canary.sh
#   ./deploy/rollback_canary.sh --force
#   ./deploy/rollback_canary.sh --version abc1234
###############################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="/opt/ocg-rulebook-qa"
STABLE_CONTAINER="ocg-rulebook-qa-stable"
CANARY_CONTAINER="ocg-rulebook-qa-canary"
NGINX_CONTAINER="ocg-rulebook-qa-nginx"
REGISTRY="ghcr.io"
IMAGE_NAME="ocg-rulebook-qa"
TARGET_VERSION=""
FORCE=false
DRY_RUN=false

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

log_warn() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: $*"
}

log_error() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $*" >&2
}

get_current_stable_version() {
  if docker ps -q --filter name=${STABLE_CONTAINER} | grep -q .; then
    docker inspect --format='{{.Config.Image}}' ${STABLE_CONTAINER} 2>/dev/null | cut -d: -f2
  else
    echo "none"
  fi
}

get_current_canary_version() {
  if docker ps -q --filter name=${CANARY_CONTAINER} | grep -q .; then
    docker inspect --format='{{.Config.Image}}' ${CANARY_CONTAINER} 2>/dev/null | cut -d: -f2
  else
    echo "none"
  fi
}

find_previous_stable_version() {
  if [ -f "${DEPLOY_DIR}/deploy-history/canary.log" ]; then
    local prev_version
    prev_version=$(grep "Image:" "${DEPLOY_DIR}/deploy-history/canary.log" | tail -n 2 | head -n 1 | cut -d: -f3)
    if [ -n "$prev_version" ]; then
      echo "$prev_version"
      return 0
    fi
  fi

  local prev_image
  prev_image=$(docker images --format "{{.Repository}}:{{.Tag}}" | grep "${IMAGE_NAME}" | grep -v "latest" | head -n 1)
  if [ -n "$prev_image" ]; then
    echo "$prev_image" | cut -d: -f2
    return 0
  fi

  log_error "No previous stable version found"
  return 1
}

backup_canary_state() {
  log "Creating backup before rollback..."
  mkdir -p "${DEPLOY_DIR}/rollback-backups"

  local backup_time
  backup_time=$(date +%Y%m%d_%H%M%S)

  if docker ps -q --filter name=${CANARY_CONTAINER} | grep -q .; then
    docker inspect ${CANARY_CONTAINER} > "${DEPLOY_DIR}/rollback-backups/canary_config_${backup_time}.json" 2>/dev/null || true
    docker logs --tail 2000 ${CANARY_CONTAINER} > "${DEPLOY_DIR}/rollback-backups/canary_logs_${backup_time}.txt" 2>/dev/null || true
    get_current_canary_version > "${DEPLOY_DIR}/rollback-backups/canary_version_${backup_time}.txt"
  fi

  if docker ps -q --filter name=${STABLE_CONTAINER} | grep -q .; then
    docker inspect ${STABLE_CONTAINER} > "${DEPLOY_DIR}/rollback-backups/stable_config_${backup_time}.json" 2>/dev/null || true
    docker logs --tail 2000 ${STABLE_CONTAINER} > "${DEPLOY_DIR}/rollback-backups/stable_logs_${backup_time}.txt" 2>/dev/null || true
    get_current_stable_version > "${DEPLOY_DIR}/rollback-backups/stable_version_${backup_time}.txt"
  fi

  log "Backup saved to ${DEPLOY_DIR}/rollback-backups/"
}

stop_canary() {
  log "Stopping canary container..."
  if docker ps -q --filter name=${CANARY_CONTAINER} | grep -q .; then
    docker stop ${CANARY_CONTAINER} --time 30
    docker rm ${CANARY_CONTAINER}
    log "Canary container stopped and removed"
  else
    log_warn "No canary container found"
  fi
}

restore_stable_only_config() {
  log "Restoring stable-only Nginx configuration..."

  cat > "${DEPLOY_DIR}/nginx_canary.conf" << 'NGINX_EOF'
user  nginx;
worker_processes  auto;

error_log  /var/log/nginx/error.log warn;
pid        /var/run/nginx.pid;

events {
    worker_connections  1024;
    use epoll;
    multi_accept on;
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;

    log_format  main  '$remote_addr - $remote_user [$time_local] "$request" '
                      '$status $body_bytes_sent "$http_referer" '
                      '"$http_user_agent" "$http_x_forwarded_for" '
                      'rt=$request_time';

    access_log  /var/log/nginx/access.log  main;

    sendfile        on;
    tcp_nopush      on;
    tcp_nodelay     on;
    keepalive_timeout  65;
    types_hash_max_size 2048;
    client_max_body_size 50m;

    gzip  on;
    gzip_vary on;
    gzip_proxied any;
    gzip_comp_level 6;
    gzip_min_length 1000;
    gzip_types
        text/plain
        text/css
        text/xml
        text/javascript
        application/json
        application/javascript
        application/xml
        application/xml+rss
        application/x-javascript
        image/svg+xml;

    upstream backend_api {
        server 127.0.0.1:5001;
        keepalive 32;
    }

    server {
        listen 80;
        server_name _;

        root /usr/share/nginx/html;
        index index.html;

        location / {
            try_files $uri $uri/ /index.html;
            add_header Cache-Control "no-cache, no-store, must-revalidate";
            add_header Pragma "no-cache";
            add_header Expires 0;
        }

        location /assets/ {
            expires 30d;
            add_header Cache-Control "public, immutable";
            try_files $uri =404;
        }

        location /api/ {
            proxy_pass http://backend_api/api/;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
            proxy_set_header Connection "";
            proxy_buffering off;
            proxy_cache off;
            proxy_read_timeout 120s;
            proxy_connect_timeout 10s;
            proxy_send_timeout 120s;
        }

        location /metrics {
            proxy_pass http://backend_api/metrics;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
            proxy_set_header X-Real-IP $remote_addr;
            proxy_set_header X-Forwarded-For $proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto $scheme;
        }

        location /health {
            proxy_pass http://backend_api/api/v1/health;
            proxy_http_version 1.1;
            proxy_set_header Host $host;
        }

        error_page 500 502 503 504 /50x.html;
        location = /50x.html {
            root /usr/share/nginx/html;
        }
    }
}
NGINX_EOF

  if docker ps -q --filter name=${NGINX_CONTAINER} | grep -q .; then
    docker exec ${NGINX_CONTAINER} nginx -s reload
    log "Nginx configuration reloaded"
  else
    log_warn "Nginx container not running, configuration will be applied on next start"
  fi
}

check_stable_health() {
  log "Checking stable container health..."

  local max_retries=30
  local retry_interval=2

  for i in $(seq 1 $max_retries); do
    if curl -sf http://localhost:5001/api/v1/health > /dev/null 2>&1; then
      log "Health check passed on attempt $i"
      return 0
    fi
    log "Health check attempt $i/$max_retries, retrying in ${retry_interval}s..."
    sleep $retry_interval
  done

  log_error "Health check failed after $max_retries attempts"
  return 1
}

update_rollback_history() {
  local from_version="$1"
  local to_version="$2"

  log "Updating rollback history..."
  mkdir -p "${DEPLOY_DIR}/deploy-history"

  cat >> "${DEPLOY_DIR}/deploy-history/canary_rollback.log" << EOF
[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] CANARY_ROLLBACK
From: ${from_version}
To: ${to_version}
Initiated by: $(whoami)
---
EOF

  log "Rollback history updated"
}

main() {
  log "========================================="
  log "Starting canary rollback"
  log "========================================="

  local canary_version
  canary_version=$(get_current_canary_version)
  local stable_version
  stable_version=$(get_current_stable_version)

  log "Current canary version: ${canary_version}"
  log "Current stable version: ${stable_version}"

  if [ "$canary_version" = "none" ]; then
    log_warn "No canary deployment found"
    log "If you want to rollback to a previous stable version, use:"
    log "  ./deploy/rollback.sh --version <version>"
    exit 0
  fi

  if [ -z "$TARGET_VERSION" ]; then
    TARGET_VERSION="$stable_version"
    if [ "$TARGET_VERSION" = "none" ]; then
      TARGET_VERSION=$(find_previous_stable_version)
    fi
  fi

  log "Target version: ${TARGET_VERSION}"

  if [ "$TARGET_VERSION" = "$canary_version" ]; then
    log_error "Target version is the same as canary version"
    exit 1
  fi

  if [ "$DRY_RUN" = true ]; then
    log "[DRY RUN] Would execute the following steps:"
    log "  1. Backup current canary state"
    log "  2. Stop canary container: ${CANARY_CONTAINER}"
    log "  3. Restore stable-only Nginx configuration"
    log "  4. Reload Nginx"
    log "  5. Run health check"
    log "  6. Update rollback history"
    log "[DRY RUN] No changes were made"
    exit 0
  fi

  backup_canary_state

  stop_canary

  restore_stable_only_config

  if check_stable_health; then
    update_rollback_history "$canary_version" "$TARGET_VERSION"

    log "========================================="
    log "Canary rollback completed successfully!"
    log "Rolled back from: ${canary_version}"
    log "Rolled back to: ${TARGET_VERSION}"
    log "All traffic now routed to stable version"
    log "========================================="
  else
    log_error "Rollback failed - stable health check did not pass"
    log_error "Manual intervention required!"
    exit 1
  fi
}

while [[ $# -gt 0 ]]; do
  case $1 in
    --version)
      TARGET_VERSION="$2"
      shift 2
      ;;
    --force)
      FORCE=true
      shift
      ;;
    --dry-run)
      DRY_RUN=true
      shift
      ;;
    --help)
      head -n 15 "$0" | tail -n 13
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

main "$@"
