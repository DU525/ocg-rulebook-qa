#!/bin/bash
set -euo pipefail

###############################################################################
# rollback.sh - 一键回滚脚本
# 用法: ./deploy/rollback.sh [OPTIONS]
#   OPTIONS:
#     --version <version>     回滚到指定版本 (默认: 上一个版本)
#     --list                  列出所有可用版本
#     --auto                  自动回滚模式（用于部署失败时自动调用）
#     --dry-run               仅显示将要执行的操作，不实际回滚
#     --help                  显示帮助信息
#
# 示例:
#   ./deploy/rollback.sh
#   ./deploy/rollback.sh --version abc1234
#   ./deploy/rollback.sh --list
###############################################################################

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
DEPLOY_DIR="/opt/ocg-rulebook-qa"
CONTAINER_NAME="ocg-rulebook-qa"
REGISTRY="ghcr.io"
IMAGE_NAME="ocg-rulebook-qa"
TARGET_VERSION=""
LIST_VERSIONS=false
AUTO_MODE=false
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

get_current_version() {
  if docker ps -q --filter name=${CONTAINER_NAME} | grep -q .; then
    CURRENT_IMAGE=$(docker inspect --format='{{.Config.Image}}' ${CONTAINER_NAME})
    echo "$CURRENT_IMAGE" | cut -d: -f2
  else
    echo "none"
  fi
}

list_available_versions() {
  log "Available versions:"
  echo ""
  
  if [ -d "${DEPLOY_DIR}/deploy-history" ] && [ -f "${DEPLOY_DIR}/deploy-history/history.log" ]; then
    log "Deployment history:"
    grep "Version:" "${DEPLOY_DIR}/deploy-history/history.log" | tail -n 20
    echo ""
  fi
  
  log "Local Docker images:"
  docker images --format "table {{.Repository}}\t{{.Tag}}\t{{.CreatedAt}}\t{{.Size}}" | grep "${IMAGE_NAME}" || echo "No local images found"
  echo ""
  
  if [ -f "${DEPLOY_DIR}/backups" ] && [ "$(ls -A ${DEPLOY_DIR}/backups/ 2>/dev/null)" ]; then
    log "Available backups:"
    ls -lt ${DEPLOY_DIR}/backups/ | head -n 10
  fi
}

find_previous_version() {
  CURRENT_VERSION=$(get_current_version)
  
  if [ "$CURRENT_VERSION" = "none" ]; then
    log_error "No running container found"
    exit 1
  fi
  
  log "Current version: $CURRENT_VERSION"
  
  PREVIOUS_VERSION=$(docker images --format "{{.Tag}}" | grep -v "latest" | grep -v "^${CURRENT_VERSION}$" | head -n 1)
  
  if [ -z "$PREVIOUS_VERSION" ]; then
    log_error "No previous version found for rollback"
    exit 1
  fi
  
  echo "$PREVIOUS_VERSION"
}

validate_target_version() {
  local version="$1"
  
  log "Validating target version: $version"
  
  if ! docker image inspect "${REGISTRY}/${IMAGE_NAME}:${version}" > /dev/null 2>&1; then
    log_warn "Version not found locally, pulling from registry..."
    if ! docker pull "${REGISTRY}/${IMAGE_NAME}:${version}"; then
      log_error "Version ${version} not found in registry"
      exit 1
    fi
  fi
  
  log "Version ${version} is valid"
}

backup_current_state() {
  log "Creating backup before rollback..."
  
  mkdir -p "${DEPLOY_DIR}/rollback-backups"
  BACKUP_TIME=$(date +%Y%m%d_%H%M%S)
  
  docker inspect ${CONTAINER_NAME} > "${DEPLOY_DIR}/rollback-backups/config_before_${BACKUP_TIME}.json" 2>/dev/null || true
  docker logs --tail 2000 ${CONTAINER_NAME} > "${DEPLOY_DIR}/rollback-backups/logs_before_${BACKUP_TIME}.txt" 2>/dev/null || true
  get_current_version > "${DEPLOY_DIR}/rollback-backups/version_before_${BACKUP_TIME}.txt"
  
  log "Backup saved to ${DEPLOY_DIR}/rollback-backups/"
}

stop_container() {
  log "Stopping current container..."
  
  if docker ps -q --filter name=${CONTAINER_NAME} | grep -q .; then
    docker stop ${CONTAINER_NAME} --time 30
    docker rm ${CONTAINER_NAME}
    log "Container stopped and removed"
  else
    log_warn "No running container to stop"
  fi
}

start_container() {
  local version="$1"
  local image="${REGISTRY}/${IMAGE_NAME}:${version}"
  
  log "Starting container with version: $version"
  
  docker run -d \
    --name ${CONTAINER_NAME} \
    --restart unless-stopped \
    -p 5000:5000 \
    -v ${DEPLOY_DIR}/data:/app/backend/data \
    -v ${DEPLOY_DIR}/.env:/app/backend/.env \
    -e FLASK_ENV=production \
    -e DEPLOY_VERSION=${version} \
    -e ROLLBACK_TIME=$(date -u '+%Y-%m-%d %H:%M:%S UTC') \
    --health-cmd "curl -f http://localhost:5000/api/v1/health || exit 1" \
    --health-interval=30s \
    --health-timeout=10s \
    --health-retries=3 \
    --health-start-period=60s \
    "$image"
  
  log "Container started"
}

run_health_check() {
  log "Running health check..."
  
  MAX_RETRIES=30
  RETRY_INTERVAL=2
  
  for i in $(seq 1 $MAX_RETRIES); do
    if curl -sf http://localhost:5000/api/v1/health > /dev/null 2>&1; then
      log "Health check passed on attempt $i"
      return 0
    fi
    log "Health check attempt $i/$MAX_RETRIES failed, retrying..."
    sleep $RETRY_INTERVAL
  done
  
  log_error "Health check failed after $MAX_RETRIES attempts"
  return 1
}

update_rollback_history() {
  local from_version="$1"
  local to_version="$2"
  
  log "Updating rollback history..."
  
  mkdir -p "${DEPLOY_DIR}/deploy-history"
  
  cat >> "${DEPLOY_DIR}/deploy-history/rollback.log" << EOF
[$(date -u '+%Y-%m-%d %H:%M:%S UTC')] ROLLBACK
From: ${from_version}
To: ${to_version}
Mode: ${AUTO_MODE:+auto}${AUTO_MODE:-manual}
Initiated by: $(whoami)
---
EOF
  
  echo "$to_version" > "${DEPLOY_DIR}/deploy-history/latest_version.txt"
  log "Rollback history updated"
}

main() {
  log "========================================="
  log "Starting rollback"
  log "========================================="
  
  if [ "$LIST_VERSIONS" = true ]; then
    list_available_versions
    exit 0
  fi
  
  CURRENT_VERSION=$(get_current_version)
  log "Current version: $CURRENT_VERSION"
  
  if [ -z "$TARGET_VERSION" ]; then
    TARGET_VERSION=$(find_previous_version)
    log "Target version (auto-detected): $TARGET_VERSION"
  fi
  
  if [ "$CURRENT_VERSION" = "$TARGET_VERSION" ]; then
    log_error "Target version is the same as current version"
    exit 1
  fi
  
  validate_target_version "$TARGET_VERSION"
  
  if [ "$DRY_RUN" = true ]; then
    log "[DRY RUN] Would execute the following steps:"
    log "  1. Backup current state"
    log "  2. Stop container: ${CONTAINER_NAME}"
    log "  3. Start container with version: ${TARGET_VERSION}"
    log "  4. Run health check"
    log "  5. Update rollback history"
    log "[DRY RUN] No changes were made"
    exit 0
  fi
  
  backup_current_state
  
  stop_container
  
  start_container "$TARGET_VERSION"
  
  if run_health_check; then
    update_rollback_history "$CURRENT_VERSION" "$TARGET_VERSION"
    
    log "========================================="
    log "Rollback completed successfully!"
    log "Rolled back to version: ${TARGET_VERSION}"
    log "========================================="
    
    if [ "$AUTO_MODE" = true ]; then
      log "Auto rollback completed - sending notification..."
    fi
  else
    log_error "Rollback failed - health check did not pass"
    log "Attempting to restore previous version..."
    
    start_container "$CURRENT_VERSION"
    if run_health_check; then
      log "Previous version restored successfully"
    else
      log_error "CRITICAL: Failed to restore previous version"
      log_error "Manual intervention required!"
    fi
    exit 1
  fi
}

while [[ $# -gt 0 ]]; do
  case $1 in
    --version)
      TARGET_VERSION="$2"
      shift 2
      ;;
    --list)
      LIST_VERSIONS=true
      shift
      ;;
    --auto)
      AUTO_MODE=true
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

main
