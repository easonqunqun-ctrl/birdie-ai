#!/usr/bin/env bash
# 在无 Git/CD 时用：本机拷贝后端关键源码 → CVM → docker compose rebuild（backend + celery）。
#
# 默认主机：ubuntu@1.13.198.172（可被环境变量覆盖）
#   DEPLOY_HOST=ubuntu@别的IP DEPLOY_REPO=/home/ubuntu/别的目录 bash infra/deploy/publish-backend-to-cvm.sh
#
# 若远端 compose 还须叠微信商户 PEM：
#   REMOTE_EXTRA_COMPOSE_FLAGS="-f docker-compose.wechat-pay-key.yml" bash infra/deploy/publish-backend-to-cvm.sh
#
# 密码登录：必须在「你自己的终端」（有 TTY）；Agent 等非交互会话无法替你输入密码。
# 配置免密后可在任意环境一键跑：ssh-copy-id "$DEPLOY_HOST"
#
# 若远端不是 CVM 三文件编排，可自行覆盖远端命令：
#   REMOTE_BUILD_CMD='cd /home/ubuntu/foo && docker compose --env-file .env.local up -d --build backend' bash ...
set -euo pipefail

REMOTE_BUILD_CMD="${REMOTE_BUILD_CMD:-}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DEPLOY_HOST="${DEPLOY_HOST:-ubuntu@1.13.198.172}"
DEPLOY_REPO="${DEPLOY_REPO:-/home/ubuntu/lingniao-golf}"
REMOTE_EXTRA_COMPOSE_FLAGS="${REMOTE_EXTRA_COMPOSE_FLAGS:-}"

SSH_OPTS=(
  -o BatchMode=no
  -o StrictHostKeyChecking=accept-new
)

die() {
  echo "✗ $*" >&2
  exit 1
}

need_file() {
  [[ -f "$1" ]] || die "找不到 $1 （请在仓库根目录执行）"
}

cd "${REPO_ROOT}"
need_file backend/app/config.py
need_file backend/app/integrations/llm.py

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  远端: ${DEPLOY_HOST}"
echo "  目录: ${DEPLOY_REPO}"
echo "  ssh/scp 会提示输入服务器密码。"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

scp "${SSH_OPTS[@]}" backend/app/config.py \
  "${DEPLOY_HOST}:${DEPLOY_REPO}/backend/app/config.py"

scp "${SSH_OPTS[@]}" backend/app/integrations/llm.py \
  "${DEPLOY_HOST}:${DEPLOY_REPO}/backend/app/integrations/llm.py"

REMOTE_RUN_DEFAULT="cd '${DEPLOY_REPO}' && docker compose -f docker-compose.yml -f docker-compose.test.yml -f docker-compose.cvm.yml ${REMOTE_EXTRA_COMPOSE_FLAGS} --env-file .env.local up -d --build backend celery-worker"

if [[ -n "${REMOTE_BUILD_CMD}" ]]; then
  ssh "${SSH_OPTS[@]}" "${DEPLOY_HOST}" bash -lc "${REMOTE_BUILD_CMD}"
else
  ssh "${SSH_OPTS[@]}" "${DEPLOY_HOST}" bash -lc "${REMOTE_RUN_DEFAULT}"
fi

echo ""
echo "✓ 已上传并完成 backend/celery 重建。"
echo "  自检：curl -sS https://api.birdieai.cn/v1/health"
