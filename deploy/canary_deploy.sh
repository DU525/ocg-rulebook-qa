#!/bin/bash
set -euo pipefail

###############################################################################
# canary_deploy.sh - 金丝雀部署脚本
# 用法: ./deploy/canary_deploy.sh [OPTIONS]
#   OPTIONS:
#     --image <image:tag>          金丝雀版本镜像 (默认: 自动检测)
#     --canary-percent <10|25|50|100>  金丝雀流量百分比 (默认: 10)
#     --rollback                   快速回滚到稳定版本
#     --promote                    提升金丝雀版本为稳定版本
#     --env <environment>          部署环境: production | staging (默认: production)
#     --skip-health-check          跳过健康检查
#     --dry-run                    仅显示操作，不实际执行
#     --help                       显示帮助信息
#
# 示例:
#   ./deploy/canary_deploy.sh --image ghcr.io/user/ocg-rulebook-qa:abc1234 --canary-percent 10
#   ./deploy/canary_deploy.sh --rollback
#   ./deploy/canary_deploy.sh --promote
###############################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DEPLOY_DIR="/opt/ocg-rulebook-qa"
STABLE_CONTAINER="ocg-rulebook-qa-stable"
CANARY_CONTAINER="ocg-rulebook-qa-canary"
NGINX_CONTAINER="ocg-rulebook-qa-nginx"
REGISTRY="ghcr.io"
IMAGE_NAME="ocg-rulebook-qa"
DEPLOY_ENV="production"
CANARY_PERCENT=10
SKIP_HEALTH_CHECK=false
DRY_RUN=false
CUSTOM_IMAGE=""
ACTION="deploy"

log() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] $*"
}

log_warn() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] WARNING: $*"
}

log_error() {
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] ERROR: $*" >&2
}

check_dependencies() {
  local deps=("docker" "curl" "jq" "nginx")
  local missing=()
  for dep in "${deps[@]}"; do
    if ! command -v "$dep" &> /dev/null; then
      missing+=("$dep")
    fi
  done
  if [ ${#missing[@]} -gt 0 ]; then
    log_error "Missing dependencies: ${missing[*]}"
    log_error "Please install missing dependencies and try again"
    exit 1
  fi
  log "All dependencies satisfied"
}

validate_canary_percent() {
  case $CANARY_PERCENT in
    10|25|50|100)
      log "Canary percentage: ${CANARY_PERCENT}%"
      ;;
    *)
      log_error "Invalid canary percentage: ${CANARY_PERCENT}"
      log_error "Supported values: 10, 25, 50, 100"
      exit 1
      ;;
  esac
}

get_latest_image() {
  log "Fetching latest image from registry..."
  LATEST_SHA=$(git rev-parse HEAD 2>/dev/null || echo "latest")
  IMAGE_TAG="${REGISTRY}/${IMAGE_NAME}:${LATEST_SHA}"
  echo "$IMAGE_TAG"
}

generate_nginx_canary_config() {
  local stable_weight=$1
  local canary_weight=$2
  local canary_image="$3"
  local config_file="${DEPLOY_DIR}/nginx_canary.conf"

  log "Generating Nginx canary configuration..."
  log "  Stable weight: ${stable_weight}"
  log "  Canary weight: ${canary_weight}"

  cat > "${config_file}" << NGINX_EOF
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

    log_format  main  '\$remote_addr - \$remote_user [\$time_local] "\$request" '
                      '\$status \$body_bytes_sent "\$http_referer" '
                      '"\$http_user_agent" "\$http_x_forwarded_for" '
                      'rt=\$request_time upstream=\$upstream_addr';

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

    map \$cookie_canary \$canary_backend {
        default     "stable";
        canary      "canary";
    }

    map \$http_x_canary \$header_canary_backend {
        default     "stable";
        canary      "canary";
    }

    upstream stable_backend {
        server 127.0.0.1:5001;
        keepalive 32;
    }

    upstream canary_backend {
        server 127.0.0.1:5002;
        keepalive 32;
    }

    split_clients "\$remote_addr\$http_user_agent" \%canary {
        ${canary_weight}    canary;
        *                   stable;
    }

    upstream backend_pool {
        server 127.0.0.1:5001 weight=${stable_weight};
        server 127.0.0.1:5002 weight=${canary_weight};
    }

    server {
        listen 80;
        server_name _;

        root /usr/share/nginx/html;
        index index.html;

        location / {
            try_files \$uri \$uri/ /index.html;
            add_header Cache-Control "no-cache, no-store, must-revalidate";
            add_header Pragma "no-cache";
            add_header Expires 0;
        }

        location /assets/ {
            expires 30d;
            add_header Cache-Control "public, immutable";
            try_files \$uri =404;
        }

        location /api/ {
            set \$backend "backend_pool";

            if (\$canary_backend = "canary") {
                set \$backend "canary_backend";
            }

            if (\$header_canary_backend = "canary") {
                set \$backend "canary_backend";
            }

            if (\%canary = "canary") {
                set \$backend "canary_backend";
            }

            proxy_pass http://\$backend/api/;
            proxy_http_version 1.1;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \$scheme;
            proxy_set_header Connection "";
            proxy_buffering off;
            proxy_cache off;
            proxy_read_timeout 120s;
            proxy_connect_timeout 10s;
            proxy_send_timeout 120s;

            add_header X-Upstream-Backend \$backend;
            add_header X-Canary-Routing "percent=\%canary";
        }

        location /metrics {
            proxy_pass http://stable_backend/metrics;
            proxy_http_version 1.1;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \$scheme;
        }

        location /health {
            proxy_pass http://backend_pool/api/v1/health;
            proxy_http_version 1.1;
            proxy_set_header Host \$host;
        }

        error_page 500 502 503 504 /50x.html;
        location = /50x.html {
            root /usr/share/nginx/html;
        }
    }
}
NGINX_EOF

  log "Nginx canary configuration generated at ${config_file}"
}

deploy_stable() {
  local image="$1"
  log "Deploying stable container..."

  if docker ps -q --filter name=${STABLE_CONTAINER} | grep -q .; then
    log "Stopping existing stable container..."
    docker stop ${STABLE_CONTAINER} --time 30
    docker rm ${STABLE_CONTAINER}
  fi

  docker run -d \
    --name ${STABLE_CONTAINER} \
    --restart unless-stopped \
    -p 5001:5000 \
    -v ${DEPLOY_DIR}/data:/app/backend/data \
    -v ${DEPLOY_DIR}/.env:/app/backend/.env \
    -e FLASK_ENV=${DEPLOY_ENV} \
    -e DEPLOY_VERSION=$(echo "$image" | cut -d: -f2) \
    -e DEPLOY_TYPE="stable" \
    -e DEPLOY_TIME=$(date -u '+%Y-%m-%d %H:%M:%S UTC') \
    --health-cmd "curl -f http://localhost:5000/api/v1/health || exit 1" \
    --health-interval=30s \
    --health-timeout=10s \
    --health-retries=3 \
    --health-start-period=60s \
    "$image"

  log "Stable container deployed successfully"
}

deploy_canary() {
  local image="$1"
  log "Deploying canary container..."

  if docker ps -q --filter name=${CANARY_CONTAINER} | grep -q .; then
    log "Stopping existing canary container..."
    docker stop ${CANARY_CONTAINER} --time 30
    docker rm ${CANARY_CONTAINER}
  fi

  docker run -d \
    --name ${CANARY_CONTAINER} \
    --restart unless-stopped \
    -p 5002:5000 \
    -v ${DEPLOY_DIR}/data:/app/backend/data \
    -v ${DEPLOY_DIR}/.env:/app/backend/.env \
    -e FLASK_ENV=${DEPLOY_ENV} \
    -e DEPLOY_VERSION=$(echo "$image" | cut -d: -f2) \
    -e DEPLOY_TYPE="canary" \
    -e DEPLOY_TIME=$(date -u '+%Y-%m-%d %H:%M:%S UTC') \
    --health-cmd "curl -f http://localhost:5000/api/v1/health || exit 1" \
    --health-interval=30s \
    --health-timeout=10s \
    --health-retries=3 \
    --health-start-period=60s \
    "$image"

  log "Canary container deployed successfully"
}

deploy_nginx() {
  local stable_weight=$1
  local canary_weight=$2

  log "Deploying Nginx canary router..."

  if docker ps -q --filter name=${NGINX_CONTAINER} | grep -q .; then
    log "Stopping existing Nginx container..."
    docker stop ${NGINX_CONTAINER} --time 10
    docker rm ${NGINX_CONTAINER}
  fi

  docker run -d \
    --name ${NGINX_CONTAINER} \
    --restart unless-stopped \
    -p 80:80 \
    -p 443:443 \
    -v ${DEPLOY_DIR}/nginx_canary.conf:/etc/nginx/nginx.conf:ro \
    -v ${DEPLOY_DIR}/nginx_logs:/var/log/nginx \
    nginx:latest

  log "Nginx canary router deployed successfully"
}

check_container_health() {
  local container_name="$1"
  local max_retries=30
  local retry_interval=2

  log "Checking health of ${container_name}..."

  for i in $(seq 1 $max_retries); do
    local port
    if [ "$container_name" = "${STABLE_CONTAINER}" ]; then
      port=5001
    else
      port=5002
    fi

    if curl -sf http://localhost:${port}/api/v1/health > /dev/null 2>&1; then
      log "Health check passed for ${container_name} on attempt $i"
      return 0
    fi
    log "Health check attempt $i/$max_retries for ${container_name}, retrying in ${retry_interval}s..."
    sleep $retry_interval
  done

  log_error "Health check failed for ${container_name} after $max_retries attempts"
  return 1
}

monitor_canary_metrics() {
  local canary_port=5002
  local stable_port=5001
  local duration=${1:-300}
  local interval=${2:-30}

  log "Monitoring canary metrics for ${duration}s (interval: ${interval}s)..."

  local start_time=$(date +%s)
  local canary_errors=0
  local canary_requests=0
  local stable_errors=0
  local stable_requests=0

  while true; do
    local current_time=$(date +%s)
    local elapsed=$((current_time - start_time))

    if [ $elapsed -ge $duration ]; then
      break
    fi

    if curl -sf http://localhost:${canary_port}/api/v1/health > /dev/null 2>&1; then
      ((canary_requests++))
    else
      ((canary_errors++))
      log_warn "Canary health check failed"
    fi

    if curl -sf http://localhost:${stable_port}/api/v1/health > /dev/null 2>&1; then
      ((stable_requests++))
    else
      ((stable_errors++))
    fi

    local canary_error_rate=0
    if [ $canary_requests -gt 0 ]; then
      canary_error_rate=$((canary_errors * 100 / canary_requests))
    fi

    log "Canary metrics: requests=${canary_requests}, errors=${canary_errors}, error_rate=${canary_error_rate}%"

    if [ $canary_error_rate -gt 10 ]; then
      log_error "Canary error rate exceeded threshold (10%)"
      return 1
    fi

    sleep $interval
  done

  log "Canary monitoring completed successfully"
  return 0
}

increase_canary_traffic() {
  local current_percent=$1
  local next_percent

  case $current_percent in
    10) next_percent=25 ;;
    25) next_percent=50 ;;
    50) next_percent=100 ;;
    100)
      log "Canary traffic at 100%, ready for promotion"
      return 0
      ;;
    *)
      log_error "Invalid canary percentage: ${current_percent}"
      return 1
      ;;
  esac

  log "Increasing canary traffic from ${current_percent}% to ${next_percent}%"

  local stable_weight=$((100 - next_percent))
  local canary_weight=$next_percent

  generate_nginx_canary_config $stable_weight $canary_weight ""

  docker exec ${NGINX_CONTAINER} nginx -s reload

  log "Traffic increased to ${next_percent}% canary"
  return 0
}

do_rollback() {
  log "========================================="
  log "Starting canary rollback"
  log "========================================="

  log "Stopping canary container..."
  if docker ps -q --filter name=${CANARY_CONTAINER} | grep -q .; then
    docker stop ${CANARY_CONTAINER} --time 30
    docker rm ${CANARY_CONTAINER}
    log "Canary container removed"
  else
    log_warn "No canary container found"
  fi

  log "Restoring stable-only Nginx configuration..."
  cat > "${DEPLOY_DIR}/nginx_canary.conf" << 'NGINX_EOF'
user  nginx;
worker_processes  auto;

error_log  /var/log/nginx/error.log warn;
pid        /var/run/nginx.pid;

events {
    worker_connections  1024;
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;

    log_format  main  '\$remote_addr - \$remote_user [\$time_local] "\$request" '
                      '\$status \$body_bytes_sent "\$http_referer" '
                      '"\$http_user_agent" "\$http_x_forwarded_for"';

    access_log  /var/log/nginx/access.log  main;

    sendfile        on;
    tcp_nopush      on;
    tcp_nodelay     on;
    keepalive_timeout  65;

    upstream backend_api {
        server 127.0.0.1:5001;
        keepalive 32;
    }

    server {
        listen 80;
        server_name _;

        location / {
            proxy_pass http://backend_api;
            proxy_http_version 1.1;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \$scheme;
        }
    }
}
NGINX_EOF

  if docker ps -q --filter name=${NGINX_CONTAINER} | grep -q .; then
    docker exec ${NGINX_CONTAINER} nginx -s reload
  fi

  log "========================================="
  log "Canary rollback completed"
  log "All traffic routed to stable version"
  log "========================================="
}

do_promote() {
  log "========================================="
  log "Promoting canary to stable"
  log "========================================="

  local canary_image=$(docker inspect --format='{{.Config.Image}}' ${CANARY_CONTAINER} 2>/dev/null || echo "")

  if [ -z "$canary_image" ]; then
    log_error "No canary container found for promotion"
    exit 1
  fi

  log "Promoting canary image: ${canary_image}"

  docker stop ${STABLE_CONTAINER} --time 30
  docker rm ${STABLE_CONTAINER}

  docker run -d \
    --name ${STABLE_CONTAINER} \
    --restart unless-stopped \
    -p 5001:5000 \
    -v ${DEPLOY_DIR}/data:/app/backend/data \
    -v ${DEPLOY_DIR}/.env:/app/backend/.env \
    -e FLASK_ENV=${DEPLOY_ENV} \
    -e DEPLOY_VERSION=$(echo "$canary_image" | cut -d: -f2) \
    -e DEPLOY_TYPE="stable" \
    -e PROMOTED_FROM="canary" \
    -e PROMOTION_TIME=$(date -u '+%Y-%m-%d %H:%M:%S UTC') \
    --health-cmd "curl -f http://localhost:5000/api/v1/health || exit 1" \
    --health-interval=30s \
    --health-timeout=10s \
    --health-retries=3 \
    --health-start-period=60s \
    "$canary_image"

  docker stop ${CANARY_CONTAINER} --time 30
  docker rm ${CANARY_CONTAINER}

  cat > "${DEPLOY_DIR}/nginx_canary.conf" << NGINX_EOF
user  nginx;
worker_processes  auto;

error_log  /var/log/nginx/error.log warn;
pid        /var/run/nginx.pid;

events {
    worker_connections  1024;
}

http {
    include       /etc/nginx/mime.types;
    default_type  application/octet-stream;

    upstream backend_api {
        server 127.0.0.1:5001;
        keepalive 32;
    }

    server {
        listen 80;
        server_name _;

        location / {
            proxy_pass http://backend_api;
            proxy_http_version 1.1;
            proxy_set_header Host \$host;
            proxy_set_header X-Real-IP \$remote_addr;
            proxy_set_header X-Forwarded-For \$proxy_add_x_forwarded_for;
            proxy_set_header X-Forwarded-Proto \$scheme;
        }
    }
}
NGINX_EOF

  if docker ps -q --filter name=${NGINX_CONTAINER} | grep -q .; then
    docker exec ${NGINX_CONTAINER} nginx -s reload
  fi

  log "========================================="
  log "Canary promoted to stable successfully"
  log "Image: ${canary_image}"
  log "========================================="
}

update_deployment_history() {
  local canary_image="$1"
  local canary_percent="$2"

  log "Updating deployment history..."
  mkdir -p "${DEPLOY_DIR}/deploy-history"

  cat >> "${DEPLOY_DIR}/deploy-history/canary.log" << EOF
[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] CANARY_DEPLOY
Image: ${canary_image}
Canary Percent: ${canary_percent}%
Environment: ${DEPLOY_ENV}
Deployed by: $(whoami)
---
EOF

  log "Deployment history updated"
}

main() {
  log "========================================="
  log "Starting canary deployment"
  log "Action: ${ACTION}"
  log "Environment: ${DEPLOY_ENV}"
  log "Canary Percent: ${CANARY_PERCENT}%"
  log "========================================="

  if [ "$ACTION" = "rollback" ]; then
    do_rollback
    exit 0
  fi

  if [ "$ACTION" = "promote" ]; then
    do_promote
    exit 0
  fi

  check_dependencies
  validate_canary_percent

  if [ -n "$CUSTOM_IMAGE" ]; then
    CANARY_IMAGE="$CUSTOM_IMAGE"
  else
    CANARY_IMAGE=$(get_latest_image)
  fi

  log "Canary image: ${CANARY_IMAGE}"

  if [ "$DRY_RUN" = true ]; then
    log "[DRY RUN] Would execute the following steps:"
    log "  1. Pull canary image: ${CANARY_IMAGE}"
    log "  2. Deploy stable container on port 5001"
    log "  3. Deploy canary container on port 5002"
    log "  4. Generate Nginx config (${CANARY_PERCENT}% canary traffic)"
    log "  5. Deploy Nginx canary router"
    log "  6. Run health checks"
    log "  7. Monitor canary metrics"
    log "[DRY RUN] No changes were made"
    exit 0
  fi

  docker pull "$CANARY_IMAGE" || {
    log_error "Failed to pull canary image: ${CANARY_IMAGE}"
    exit 1
  }

  deploy_stable "$CANARY_IMAGE"

  deploy_canary "$CANARY_IMAGE"

  if ! check_container_health ${STABLE_CONTAINER}; then
    log_error "Stable container health check failed"
    exit 1
  fi

  if ! check_container_health ${CANARY_CONTAINER}; then
    log_error "Canary container health check failed"
    do_rollback
    exit 1
  fi

  local stable_weight=$((100 - CANARY_PERCENT))
  local canary_weight=$CANARY_PERCENT

  generate_nginx_canary_config $stable_weight $canary_weight "$CANARY_IMAGE"

  deploy_nginx $stable_weight $canary_weight

  if ! check_container_health ${NGINX_CONTAINER}; then
    log_error "Nginx container health check failed"
    do_rollback
    exit 1
  fi

  update_deployment_history "$CANARY_IMAGE" "$CANARY_PERCENT"

  log "========================================="
  log "Canary deployment completed!"
  log "Stable: ${CANARY_PERCENT}% traffic"
  log "Canary: ${CANARY_PERCENT}% traffic"
  log "Canary image: ${CANARY_IMAGE}"
  log ""
  log "Next steps:"
  log "  - Monitor: ./deploy/canary_deploy.sh --monitor"
  log "  - Increase traffic: ./deploy/canary_deploy.sh --increase"
  log "  - Promote: ./deploy/canary_deploy.sh --promote"
  log "  - Rollback: ./deploy/canary_deploy.sh --rollback"
  log "========================================="
}

while [[ $# -gt 0 ]]; do
  case $1 in
    --image)
      CUSTOM_IMAGE="$2"
      shift 2
      ;;
    --canary-percent)
      CANARY_PERCENT="$2"
      shift 2
      ;;
    --rollback)
      ACTION="rollback"
      shift
      ;;
    --promote)
      ACTION="promote"
      shift
      ;;
    --env)
      DEPLOY_ENV="$2"
      shift 2
      ;;
    --skip-health-check)
      SKIP_HEALTH_CHECK=true
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
