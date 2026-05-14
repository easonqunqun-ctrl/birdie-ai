#!/usr/bin/env bash
# 在无 Git/CD 时用：本机拷贝后端关键源码 → CVM → docker compose rebuild（backend + celery）。
#
# 【推荐先发】路径 B 免密：bash infra/deploy/setup-cvm-ssh-key.sh
# （一次输入服务器密码后，本会话自动用 ~/.ssh/id_ed25519_birdie_golf）
#
# 默认主机 ubuntu@1.13.198.172；覆盖示例：
#   DEPLOY_HOST=ubuntu@… DEPLOY_REPO=/home/ubuntu/xxx bash infra/deploy/publish-backend-to-cvm.sh
#
# compose 叠加商户 PEM：
#   REMOTE_EXTRA_COMPOSE_FLAGS="-f docker-compose.wechat-pay-key.yml" …
#
# 非交互 / CI：`SSH_BATCH_MODE=yes`（须已 ssh-copy-id 成功，否则会立刻失败）。
#
# REMOTE_BUILD_CMD 覆盖远端整段命令（非标编排）。
set -euo pipefail

REMOTE_BUILD_CMD="${REMOTE_BUILD_CMD:-}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DEPLOY_HOST="${DEPLOY_HOST:-ubuntu@1.13.198.172}"
DEPLOY_REPO="${DEPLOY_REPO:-/home/ubuntu/lingniao-golf}"
REMOTE_EXTRA_COMPOSE_FLAGS="${REMOTE_EXTRA_COMPOSE_FLAGS:-}"
BIRDIE_CVM_KEY="${BIRDIE_CVM_KEY:-$HOME/.ssh/id_ed25519_birdie_golf}"
# 未显式设置时：有专用密钥则默认 BatchMode=yes（免密 / 非交互）；否则允许回退密码
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

need_file() {
  [[ -f "$1" ]] || die "找不到 $1 （请在仓库根目录执行）"
}

cd "${REPO_ROOT}"
need_file backend/app/config.py
need_file backend/app/integrations/llm.py
need_file backend/app/api/v1/chat.py

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  远端: ${DEPLOY_HOST}"
echo "  目录: ${DEPLOY_REPO}"
if [[ -f "${BIRDIE_CVM_KEY}" ]]; then
  echo "  认证: ${BIRDIE_CVM_KEY} （BatchMode=${SSH_BATCH_MODE}）"
else
  echo "  认证: 未找到本项目密钥 → 可用密码；一次性免密请先：make setup-cvm-ssh-key"
fi
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

scp "${SSH_OPTS[@]}" backend/app/config.py \
  "${DEPLOY_HOST}:${DEPLOY_REPO}/backend/app/config.py"

scp "${SSH_OPTS[@]}" backend/app/integrations/llm.py \
  "${DEPLOY_HOST}:${DEPLOY_REPO}/backend/app/integrations/llm.py"

scp "${SSH_OPTS[@]}" backend/app/api/v1/chat.py \
  "${DEPLOY_HOST}:${DEPLOY_REPO}/backend/app/api/v1/chat.py"

# 须用「仓库内」.env.local 的绝对路径 + --project-directory；否则部分 compose 版本会把
# --env-file .env.local 解析成 $HOME/.env.local（出现 couldn't find env file: /home/ubuntu/.env.local）。
REMOTE_RUN_DEFAULT="set -e; cd '${DEPLOY_REPO}' || { echo \"✗ 远端目录不存在: ${DEPLOY_REPO}\" >&2; exit 1; }; test -f '.env.local' || { echo \"✗ 缺少 ${DEPLOY_REPO}/.env.local — 请按 docs/release-notes/CVM-canonical-deploy.md 在服务器维护密钥文件（勿用本机误盖）\" >&2; exit 1; }; docker compose --project-directory '${DEPLOY_REPO}' -f docker-compose.yml -f docker-compose.test.yml -f docker-compose.cvm.yml ${REMOTE_EXTRA_COMPOSE_FLAGS} --env-file '${DEPLOY_REPO}/.env.local' up -d --build backend celery-worker"

if [[ -n "${REMOTE_BUILD_CMD}" ]]; then
  ssh "${SSH_OPTS[@]}" "${DEPLOY_HOST}" bash -lc "${REMOTE_BUILD_CMD}"
else
  ssh "${SSH_OPTS[@]}" "${DEPLOY_HOST}" bash -lc "${REMOTE_RUN_DEFAULT}"
fi

echo ""
echo "✓ 已上传并完成 backend/celery 重建。"
echo "  自检：curl -sS https://api.birdieai.cn/v1/health"
