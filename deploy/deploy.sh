#!/bin/bash
set -euo pipefail

###############################################################################
# deploy.sh - 自动化部署脚本
# 用法: ./deploy/deploy.sh [OPTIONS]
#   OPTIONS:
#     --image <image:tag>     指定要部署的镜像 (默认: 自动检测最新版本)
#     --env <environment>     部署环境: production | staging (默认: production)
#     --skip-health-check     跳过健康检查
#     --dry-run               仅显示将要执行的操作，不实际部署
#     --help                  显示帮助信息
#
# 示例:
#   ./deploy/deploy.sh
#   ./deploy/deploy.sh --image ghcr.io/user/ocg-rulebook-qa:abc1234
#   ./deploy/deploy.sh --env staging --dry-run
###############################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
DEPLOY_DIR="/opt/ocg-rulebook-qa"
CONTAINER_NAME="ocg-rulebook-qa"
REGISTRY="ghcr.io"
IMAGE_NAME="ocg-rulebook-qa"
DEPLOY_ENV="production"
SKIP_HEALTH_CHECK=false
DRY_RUN=false
CUSTOM_IMAGE=""

REGISTRY="${REGISTRY}"
IMAGE_NAME="${IMAGE_NAME}"

while [[ $# -gt 0 ]]; do
  case $1 in
    --image)
      CUSTOM_IMAGE="$2"
      shift 2
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
      head -n 17 "$0" | tail -n 15
      exit 0
      ;;
    *)
      echo "Unknown option: $1"
      exit 1
      ;;
  esac
done

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
  local deps=("docker" "curl" "jq")
  for dep in "${deps[@]}"; do
    if ! command -v "$dep" &> /dev/null; then
      log_error "Required dependency '$dep' is not installed"
      exit 1
    fi
  done
  log "All dependencies satisfied"
}

get_latest_image() {
  log "Fetching latest image from registry..."
  
  LATEST_SHA=$(git rev-parse HEAD)
  IMAGE_TAG="${REGISTRY}/${IMAGE_NAME}:${LATEST_SHA}"
  
  if ! docker manifest inspect "$IMAGE_TAG" > /dev/null 2>&1; then
    log_warn "Image ${IMAGE_TAG} not found in registry"
    log "Trying to find latest available image..."
    
    IMAGE_TAG=$(docker images --format "{{.Repository}}:{{.Tag}}" | grep "${IMAGE_NAME}" | grep -v "latest" | head -n 1)
    
    if [ -z "$IMAGE_TAG" ]; then
      log_error "No available image found for deployment"
      exit 1
    fi
  fi
  
  echo "$IMAGE_TAG"
}

backup_current_deployment() {
  log "Backing up current deployment..."
  
  mkdir -p "${DEPLOY_DIR}/backups"
  BACKUP_TIME=$(date +%Y%m%d_%H%M%S)
  
  if docker ps -q --filter name=${CONTAINER_NAME} | grep -q .; then
    CURRENT_IMAGE=$(docker inspect --format='{{.Config.Image}}' ${CONTAINER_NAME})
    echo "$CURRENT_IMAGE" > "${DEPLOY_DIR}/backups/version_${BACKUP_TIME}.txt"
    
    docker inspect ${CONTAINER_NAME} > "${DEPLOY_DIR}/backups/config_${BACKUP_TIME}.json"
    docker logs --tail 1000 ${CONTAINER_NAME} > "${DEPLOY_DIR}/backups/logs_${BACKUP_TIME}.txt" 2>/dev/null || true
    
    log "Backup created at ${DEPLOY_DIR}/backups/"
  else
    log_warn "No running container found, skipping backup"
  fi
}

stop_current_container() {
  log "Stopping current container..."
  
  if docker ps -q --filter name=${CONTAINER_NAME} | grep -q .; then
    docker stop ${CONTAINER_NAME} --time 30
    docker rm ${CONTAINER_NAME}
    log "Container stopped and removed"
  else
    log_warn "No running container to stop"
  fi
}

pull_image() {
  local image="$1"
  log "Pulling image: $image"
  
  if docker pull "$image"; then
    log "Image pulled successfully"
  else
    log_error "Failed to pull image: $image"
    exit 1
  fi
}

start_container() {
  local image="$1"
  log "Starting container with image: $image"
  
  docker run -d \
    --name ${CONTAINER_NAME} \
    --restart unless-stopped \
    -p 5000:5000 \
    -v ${DEPLOY_DIR}/data:/app/backend/data \
    -v ${DEPLOY_DIR}/.env:/app/backend/.env \
    -e FLASK_ENV=${DEPLOY_ENV} \
    -e DEPLOY_VERSION=$(echo "$image" | cut -d: -f2) \
    -e DEPLOY_TIME=$(date -u '+%Y-%m-%d %H:%M:%S UTC') \
    --health-cmd "curl -f http://localhost:5000/api/v1/health || exit 1" \
    --health-interval=30s \
    --health-timeout=10s \
    --health-retries=3 \
    --health-start-period=60s \
    "$image"
  
  log "Container started"
}

run_health_check() {
  if [ "$SKIP_HEALTH_CHECK" = true ]; then
    log "Skipping health check (--skip-health-check specified)"
    return 0
  fi
  
  log "Running health check..."
  
  MAX_RETRIES=30
  RETRY_INTERVAL=2
  
  for i in $(seq 1 $MAX_RETRIES); do
    if curl -sf http://localhost:5000/api/v1/health > /dev/null 2>&1; then
      log "Health check passed on attempt $i"
      
      HEALTH_RESPONSE=$(curl -sf http://localhost:5000/api/v1/health)
      log "Health response: $HEALTH_RESPONSE"
      return 0
    fi
    log "Health check attempt $i/$MAX_RETRIES failed, retrying in ${RETRY_INTERVAL}s..."
    sleep $RETRY_INTERVAL
  done
  
  log_error "Health check failed after $MAX_RETRIES attempts"
  return 1
}

run_smoke_tests() {
  log "Running smoke tests..."
  
  local passed=0
  local failed=0
  
  if curl -sf http://localhost:5000/api/v1/health > /dev/null 2>&1; then
    log "  [PASS] Health endpoint"
    ((passed++))
  else
    log_error "  [FAIL] Health endpoint"
    ((failed++))
  fi
  
  if curl -sf http://localhost:5000/api/v1/search?q=test > /dev/null 2>&1; then
    log "  [PASS] Search endpoint"
    ((passed++))
  else
    log_warn "  [WARN] Search endpoint (may require data initialization)"
  fi
  
  log "Smoke tests: $passed passed, $failed failed"
  
  if [ $failed -gt 0 ]; then
    return 1
  fi
  return 0
}

update_deployment_history() {
  local image="$1"
  local version=$(echo "$image" | cut -d: -f2)
  
  log "Updating deployment history..."
  
  mkdir -p "${DEPLOY_DIR}/deploy-history"
  
  cat >> "${DEPLOY_DIR}/deploy-history/history.log" << EOF
[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] DEPLOY
Image: ${image}
Version: ${version}
Environment: ${DEPLOY_ENV}
Deployed by: $(whoami)
---
EOF
  
  echo "$version" > "${DEPLOY_DIR}/deploy-history/latest_version.txt"
  log "Deployment history updated"
}

main() {
  log "========================================="
  log "Starting deployment"
  log "Environment: ${DEPLOY_ENV}"
  log "========================================="
  
  check_dependencies
  
  if [ -n "$CUSTOM_IMAGE" ]; then
    IMAGE_TAG="$CUSTOM_IMAGE"
  else
    IMAGE_TAG=$(get_latest_image)
  fi
  
  log "Deploying image: $IMAGE_TAG"
  
  if [ "$DRY_RUN" = true ]; then
    log "[DRY RUN] Would execute the following steps:"
    log "  1. Backup current deployment"
    log "  2. Stop current container: ${CONTAINER_NAME}"
    log "  3. Pull image: ${IMAGE_TAG}"
    log "  4. Start new container"
    log "  5. Run health check"
    log "  6. Run smoke tests"
    log "  7. Update deployment history"
    log "[DRY RUN] No changes were made"
    exit 0
  fi
  
  backup_current_deployment
  
  stop_current_container
  
  pull_image "$IMAGE_TAG"
  
  start_container "$IMAGE_TAG"
  
  if run_health_check; then
    run_smoke_tests
    update_deployment_history "$IMAGE_TAG"
    
    log "========================================="
    log "Deployment completed successfully!"
    log "Image: ${IMAGE_TAG}"
    log "========================================="
  else
    log_error "Deployment failed - health check did not pass"
    log "Container logs:"
    docker logs ${CONTAINER_NAME} --tail 50
    
    log "Initiating automatic rollback..."
    if [ -f "${SCRIPT_DIR}/rollback.sh" ]; then
      bash "${SCRIPT_DIR}/rollback.sh" --auto
    else
      log_error "Rollback script not found. Manual intervention required."
      exit 1
    fi
  fi
}

main "$@"
