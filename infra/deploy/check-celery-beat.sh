#!/usr/bin/env bash
# Celery beat 巡检：U-1 紧急队列对应（docs/19 §二）
# 目标：核验 celery-beat 容器存活、近 30 分钟有派发 expire_stale_pending_orders、阈值生效。
#
# 用法（默认走远端 CVM）：
#   bash infra/deploy/check-celery-beat.sh
#
# 用法（本机 compose 栈，跳过 SSH）：
#   LOCAL=1 bash infra/deploy/check-celery-beat.sh
#
# 环境变量：
#   DEPLOY_HOST     默认 ubuntu@1.13.198.172（与 publish-backend-to-cvm.sh 对齐）
#   DEPLOY_REPO     默认 /home/ubuntu/lingniao-golf
#   BIRDIE_CVM_KEY  默认 $HOME/.ssh/id_ed25519_birdie_golf
#   COMPOSE_FILES   远端拼接，默认 -f docker-compose.yml -f docker-compose.test.yml -f docker-compose.cvm.yml
#   SINCE           日志回溯窗口，默认 30m
#   BEAT_SERVICE    服务名，默认 celery-beat
#   BACKEND_SERVICE 后端服务名，默认 backend
set -euo pipefail

LOCAL="${LOCAL:-0}"
DEPLOY_HOST="${DEPLOY_HOST:-ubuntu@1.13.198.172}"
DEPLOY_REPO="${DEPLOY_REPO:-/home/ubuntu/lingniao-golf}"
BIRDIE_CVM_KEY="${BIRDIE_CVM_KEY:-$HOME/.ssh/id_ed25519_birdie_golf}"
COMPOSE_FILES="${COMPOSE_FILES:--f docker-compose.yml -f docker-compose.test.yml -f docker-compose.cvm.yml}"
SINCE="${SINCE:-30m}"
BEAT_SERVICE="${BEAT_SERVICE:-celery-beat}"
BACKEND_SERVICE="${BACKEND_SERVICE:-backend}"

red()   { printf '\033[31m%s\033[0m\n' "$*" >&2; }
green() { printf '\033[32m%s\033[0m\n' "$*"; }
yellow(){ printf '\033[33m%s\033[0m\n' "$*"; }
section(){ printf '\n\033[1m=== %s ===\033[0m\n' "$*"; }

# 远端执行：透传环境变量 + cd 项目目录
remote_exec() {
  local cmd="$1"
  local ssh_opts=(-o BatchMode=yes -o StrictHostKeyChecking=accept-new)
  if [[ -f "${BIRDIE_CVM_KEY}" ]]; then
    ssh_opts+=(-i "${BIRDIE_CVM_KEY}" -o IdentitiesOnly=yes)
  fi
  # shellcheck disable=SC2029
  ssh "${ssh_opts[@]}" "${DEPLOY_HOST}" "cd '${DEPLOY_REPO}' && ${cmd}"
}

run_compose() {
  local args="$*"
  if [[ "${LOCAL}" == "1" ]]; then
    docker compose ${COMPOSE_FILES} ${args}
  else
    remote_exec "docker compose ${COMPOSE_FILES} ${args}"
  fi
}

errors=0

section "1) ${BEAT_SERVICE} 容器状态"
ps_out=$(run_compose "ps ${BEAT_SERVICE}" 2>&1 || true)
echo "${ps_out}"
if echo "${ps_out}" | grep -E "(Up|running)" >/dev/null 2>&1; then
  green "✓ ${BEAT_SERVICE} 在线"
else
  red "✗ ${BEAT_SERVICE} 未检测到 Up/running 状态"
  errors=$((errors + 1))
fi

section "2) 近 ${SINCE} 内 expire_stale_pending_orders 派发记录"
log_out=$(run_compose "logs --since ${SINCE} --no-color ${BEAT_SERVICE}" 2>&1 || true)
# 同名 task 注册路径：app/celery_app.py::beat_schedule -> xiaoniao.expire_stale_pending_orders
if echo "${log_out}" | grep -E "expire_stale_pending_orders|xiaoniao\.expire_stale_pending_orders" >/dev/null 2>&1; then
  hits=$(echo "${log_out}" | grep -cE "expire_stale_pending_orders|xiaoniao\.expire_stale_pending_orders" || true)
  green "✓ 近 ${SINCE} 内捕获到 ${hits} 条派发记录"
else
  red "✗ 近 ${SINCE} 内未发现 expire_stale_pending_orders 派发；可能 beat 阻塞或频率配置异常"
  echo "  最近 30 行日志预览："
  echo "${log_out}" | tail -n 30 | sed 's/^/    /'
  errors=$((errors + 1))
fi

section "3) PAYMENT_PENDING_ORDER_EXPIRE_MINUTES 阈值"
# 容器内系统 python 无项目依赖；与 release 镜像一致走 /app/.venv
threshold_cmd='/app/.venv/bin/python -c "from app.config import settings; print(settings.PAYMENT_PENDING_ORDER_EXPIRE_MINUTES)"'
threshold_out=$(run_compose "exec -T ${BACKEND_SERVICE} ${threshold_cmd}" 2>&1 || true)
threshold=$(echo "${threshold_out}" | tail -n 1 | tr -d '\r')
if [[ "${threshold}" =~ ^[0-9]+$ ]]; then
  if [[ "${threshold}" -gt 0 ]]; then
    green "✓ PAYMENT_PENDING_ORDER_EXPIRE_MINUTES=${threshold}"
  else
    yellow "! PAYMENT_PENDING_ORDER_EXPIRE_MINUTES=${threshold} （≤0 表示关闭超时回收，仅在确认无需自动取消时允许）"
  fi
else
  red "✗ 无法读取阈值；输出：${threshold_out}"
  errors=$((errors + 1))
fi

section "结论"
if [[ "${errors}" -eq 0 ]]; then
  green "✓ Celery beat 自检通过（U-1）"
  exit 0
else
  red "✗ Celery beat 自检共 ${errors} 项失败；详见上方分段输出"
  echo "  关联文档：docs/19-产品开发迭代计划-当前队列.md §二 U-1"
  exit 1
fi
