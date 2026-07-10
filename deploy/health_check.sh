#!/bin/bash
set -euo pipefail

###############################################################################
# health_check.sh - 服务健康检查脚本
# 用法: ./deploy/health_check.sh [OPTIONS]
#   OPTIONS:
#     --url <url>             健康检查URL (默认: http://localhost:5000/api/v1/health)
#     --timeout <seconds>     超时时间 (默认: 30)
#     --retries <count>       重试次数 (默认: 3)
#     --interval <seconds>    重试间隔 (默认: 2)
#     --verbose               显示详细输出
#     --json                  输出JSON格式结果
#     --help                  显示帮助信息
#
# 示例:
#   ./deploy/health_check.sh
#   ./deploy/health_check.sh --verbose --json
#   ./deploy/health_check.sh --timeout 60 --retries 5
###############################################################################

HEALTH_URL="http://localhost:5000/api/v1/health"
TIMEOUT=30
RETRIES=3
RETRY_INTERVAL=2
VERBOSE=false
JSON_OUTPUT=false

while [[ $# -gt 0 ]]; do
  case $1 in
    --url)
      HEALTH_URL="$2"
      shift 2
      ;;
    --timeout)
      TIMEOUT="$2"
      shift 2
      ;;
    --retries)
      RETRIES="$2"
      shift 2
      ;;
    --interval)
      RETRY_INTERVAL="$2"
      shift 2
      ;;
    --verbose)
      VERBOSE=true
      shift
      ;;
    --json)
      JSON_OUTPUT=true
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

START_TIME=$(date +%s)

check_health() {
  local attempt=$1
  local response
  local http_code
  
  response=$(curl -sf -w "\n%{http_code}" --connect-timeout 5 --max-time ${TIMEOUT} ${HEALTH_URL} 2>&1) || {
    if [ "$VERBOSE" = true ]; then
      echo "  Response: $response"
    fi
    return 1
  }
  
  http_code=$(echo "$response" | tail -n 1)
  body=$(echo "$response" | sed '$d')
  
  if [ "$http_code" = "200" ]; then
    if [ "$VERBOSE" = true ]; then
      echo "  HTTP Code: $http_code"
      echo "  Response Body: $body"
    fi
    echo "$body"
    return 0
  else
    if [ "$VERBOSE" = true ]; then
      echo "  HTTP Code: $http_code"
    fi
    return 1
  fi
}

check_container() {
  local container_name="ocg-rulebook-qa"
  
  if ! command -v docker &> /dev/null; then
    return 0
  fi
  
  if docker ps -q --filter name=${container_name} | grep -q .; then
    if [ "$VERBOSE" = true ]; then
      echo "Container Status:"
      docker ps --filter name=${container_name} --format "table {{.Names}}\t{{.Status}}\t{{.Ports}}"
      echo ""
      echo "Container Health:"
      docker inspect --format='{{.State.Health.Status}}' ${container_name} 2>/dev/null || echo "No health check configured"
      echo ""
      echo "Resource Usage:"
      docker stats --no-stream ${container_name} --format "CPU: {{.CPUPerc}}, Memory: {{.MemUsage}}" 2>/dev/null || echo "N/A"
    fi
    return 0
  else
    if [ "$VERBOSE" = true ]; then
      echo "Container '${container_name}' is not running"
    fi
    return 1
  fi
}

check_disk_space() {
  local usage=$(df -h / | awk 'NR==2 {print $5}' | sed 's/%//')
  
  if [ "$VERBOSE" = true ]; then
    echo "Disk Usage: ${usage}%"
  fi
  
  if [ "$usage" -gt 90 ]; then
    return 1
  fi
  return 0
}

check_docker_logs() {
  local container_name="ocg-rulebook-qa"
  local recent_errors
  
  if docker ps -q --filter name=${container_name} | grep -q .; then
    recent_errors=$(docker logs --tail 100 ${container_name} 2>&1 | grep -i "error\|exception\|critical" | tail -n 5)
    
    if [ -n "$recent_errors" ] && [ "$VERBOSE" = true ]; then
      echo "Recent Errors in Logs:"
      echo "$recent_errors"
    fi
  fi
}

main() {
  if [ "$JSON_OUTPUT" = true ]; then
    echo "{"
  fi
  
  overall_status="healthy"
  
  if [ "$JSON_OUTPUT" = true ]; then
    echo "  \"timestamp\": \"$(date -u '+%Y-%m-%dT%H:%M:%SZ')\","
  fi
  
  if ! check_container; then
    overall_status="unhealthy"
    if [ "$JSON_OUTPUT" = true ]; then
      echo "  \"container_status\": \"not_running\","
    else
      echo "Container Status: NOT RUNNING"
    fi
  else
    if [ "$JSON_OUTPUT" = true ]; then
      echo "  \"container_status\": \"running\","
    else
      echo "Container Status: RUNNING"
    fi
  fi
  
  health_passed=false
  for attempt in $(seq 1 $RETRIES); do
    if [ "$VERBOSE" = true ]; then
      echo "Health check attempt $attempt/$RETRIES..."
    fi
    
    if health_response=$(check_health $attempt); then
      health_passed=true
      break
    fi
    
    if [ $attempt -lt $RETRIES ]; then
      sleep $RETRY_INTERVAL
    fi
  done
  
  if [ "$health_passed" = true ]; then
    if [ "$JSON_OUTPUT" = true ]; then
      echo "  \"health_status\": \"healthy\","
      echo "  \"health_response\": ${health_response},"
    else
      echo "Health Status: HEALTHY"
    fi
  else
    overall_status="unhealthy"
    if [ "$JSON_OUTPUT" = true ]; then
      echo "  \"health_status\": \"unhealthy\","
    else
      echo "Health Status: UNHEALTHY"
    fi
  fi
  
  if [ "$JSON_OUTPUT" = true ]; then
    echo "  \"disk_space\": \"$(df -h / | awk 'NR==2 {print $5}')\","
  else
    check_disk_space
    echo "Disk Usage: $(df -h / | awk 'NR==2 {print $5}')"
  fi
  
  if [ "$VERBOSE" = true ] && [ "$JSON_OUTPUT" = false ]; then
    echo ""
    check_docker_logs
  fi
  
  END_TIME=$(date +%s)
  DURATION=$((END_TIME - START_TIME))
  
  if [ "$JSON_OUTPUT" = true ]; then
    echo "  \"overall_status\": \"${overall_status}\","
    echo "  \"check_duration_seconds\": ${DURATION}"
    echo "}"
  else
    echo ""
    echo "Overall Status: ${overall_status^^}"
    echo "Check Duration: ${DURATION}s"
  fi
  
  if [ "$overall_status" = "healthy" ]; then
    exit 0
  else
    exit 1
  fi
}

main
