#!/usr/bin/env bash
# Mac → CVM：同步 infra/monitoring + 可选 docker-compose.yml，重启 monitoring profile。
# 解决 publish-backend-cvm 不 rsync 监控配置、bridge 脚本需手工 scp 的问题。
#
# 用法：
#   make publish-monitoring-cvm
#   REMOTE_RSYNC_COMPOSE=no make publish-monitoring-cvm   # 仅更新 yml/bridge，不动 compose 主文件
#
# 环境变量（与 publish-backend-to-cvm.sh 对齐）：
#   DEPLOY_HOST / DEPLOY_REPO / BIRDIE_CVM_KEY / SSH_BATCH_MODE
#   REMOTE_RSYNC_COMPOSE=yes|no  默认 yes（scp docker-compose.yml 以同步 bridge env）
set -euo pipefail

REMOTE_RSYNC_COMPOSE="${REMOTE_RSYNC_COMPOSE:-yes}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DEPLOY_HOST="${DEPLOY_HOST:-ubuntu@1.13.198.172}"
DEPLOY_REPO="${DEPLOY_REPO:-/home/ubuntu/lingniao-golf}"
BIRDIE_CVM_KEY="${BIRDIE_CVM_KEY:-$HOME/.ssh/id_ed25519_birdie_golf}"
SSH_BATCH_MODE="${SSH_BATCH_MODE:-}"
if [[ -z "${SSH_BATCH_MODE}" ]]; then
  if [[ -f "${BIRDIE_CVM_KEY}" ]]; then
    SSH_BATCH_MODE=yes
  else
    SSH_BATCH_MODE=no
  fi
fi

SSH_OPTS=(
  -o "BatchMode=${SSH_BATCH_MODE}"
  -o StrictHostKeyChecking=accept-new
  -o ServerAliveInterval=30
  -o ServerAliveCountMax=120
)

if [[ -f "${BIRDIE_CVM_KEY}" ]]; then
  SSH_OPTS+=(-i "${BIRDIE_CVM_KEY}" -o IdentitiesOnly=yes)
elif [[ "${SSH_BATCH_MODE}" == yes ]]; then
  echo "✗ 找不到 ${BIRDIE_CVM_KEY} 且 SSH_BATCH_MODE=yes — 请先跑 make setup-cvm-ssh-key" >&2
  exit 1
fi

die() {
  echo "✗ $*" >&2
  exit 1
}

rsync_ssh_rsh() {
  local out=""
  local a
  for a in ssh "${SSH_OPTS[@]}"; do
    out+=$(printf ' %q' "$a")
  done
  echo "${out# }"
}

cd "${REPO_ROOT}"
[[ -d infra/monitoring ]] || die "找不到 infra/monitoring"
[[ -f docker-compose.yml ]] || die "找不到 docker-compose.yml"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  监控发版 → ${DEPLOY_HOST}:${DEPLOY_REPO}"
echo "  REMOTE_RSYNC_COMPOSE=${REMOTE_RSYNC_COMPOSE}"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

ssh "${SSH_OPTS[@]}" "${DEPLOY_HOST}" "mkdir -p '${DEPLOY_REPO}/infra/monitoring'"

RSYNC_CMD=(rsync -avz -e "$(rsync_ssh_rsh)")
echo "→ rsync infra/monitoring/ → ${DEPLOY_HOST}:${DEPLOY_REPO}/infra/monitoring/"
"${RSYNC_CMD[@]}" "${REPO_ROOT}/infra/monitoring/" "${DEPLOY_HOST}:${DEPLOY_REPO}/infra/monitoring/"

if [[ "${REMOTE_RSYNC_COMPOSE}" != "no" ]]; then
  echo "→ scp docker-compose.yml（monitoring profile 服务定义）"
  scp "${SSH_OPTS[@]}" "${REPO_ROOT}/docker-compose.yml" "${DEPLOY_HOST}:${DEPLOY_REPO}/"
fi

ssh "${SSH_OPTS[@]}" "${DEPLOY_HOST}" bash --norc --noprofile <<EOF
set -euo pipefail
cd '${DEPLOY_REPO}' || { echo "✗ 远端目录不存在" >&2; exit 1; }
test -f '.env.local' || { echo "✗ 缺少 .env.local" >&2; exit 1; }

echo "→ docker compose --profile monitoring up -d（prometheus / alertmanager / bridge）"
docker compose --project-directory '${DEPLOY_REPO}' \\
  -f docker-compose.yml -f docker-compose.test.yml -f docker-compose.cvm.yml \\
  --env-file '${DEPLOY_REPO}/.env.local' \\
  --profile monitoring up -d --force-recreate \\
  prometheus alertmanager wechat-webhook-bridge

echo "→ 重载 Prometheus 配置（SIGHUP）"
docker kill -s HUP xiaoniao-prometheus 2>/dev/null || true

echo "→ 监控容器状态"
docker compose --project-directory '${DEPLOY_REPO}' \\
  -f docker-compose.yml -f docker-compose.test.yml -f docker-compose.cvm.yml \\
  --env-file '${DEPLOY_REPO}/.env.local' \\
  --profile monitoring ps
EOF

echo ""
echo "✓ 监控栈已同步并重启。"
echo "  自检（CVM）：curl -s http://127.0.0.1:9100/health | python3 -m json.tool"
echo "  PushPlus 测试见 infra/monitoring/README.md §4"
