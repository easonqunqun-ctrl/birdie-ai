#!/usr/bin/env bash
# 最简单「一条发版」：先在你的分支上 git push，再在仓库根执行（本机不拷生产 .env）：
#   make release-cvm
# （等同 bash scripts/cvm-remote-release.sh；云上读 ~/lingniao-golf/.env.local 并完成 compose + alembic + nginx）
#
# 依赖：本机已对 DEPLOY_HOST 配置免密密钥（或 BatchMode=no 时能交互输密码）。
# 勿把密钥写入仓库。
#
# 用法（仓库根）：
#   bash scripts/cvm-remote-release.sh
#   SKIP_GIT=1 GIT_BRANCH=v0.1.0 DEPLOY_HOST=ubuntu@x.x.x.x bash scripts/cvm-remote-release.sh
#   SSH 前先跑与本机一致的 env / 微信支付 compose 自检（须生产用 ENV_FILE）：
#   CVM_LOCAL_PREFLIGHT=1 ENV_FILE=~/secrets/birdie-prod.env bash scripts/cvm-remote-release.sh
#
# 环境变量（与 infra/deploy/publish-backend-to-cvm.sh 对齐）：
#   DEPLOY_HOST           默认 ubuntu@1.13.198.172
#   DEPLOY_REPO           远端仓库绝对路径，默认 /home/ubuntu/lingniao-golf
#   SKIP_GIT              默认 0；设 1 则远端 SKIP_GIT=1（见 release-cvm-on-server.sh）
#   GIT_BRANCH            默认 main
#   SSH_BATCH_MODE        默认 yes（有专用密钥时常用）；no 允许密码交互
#   CVM_LOCAL_PREFLIGHT   设 1 时在 SSH 前执行 quick-check-env-local + check-cvm-pay-mount（与 deploy-cvm --local-preflight 对齐）
#   ENV_FILE              同上预检时使用；默认 <repo>/.env.local（开发 env 易被占位符自检拦下）
#

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"
CVM_LOCAL_PREFLIGHT="${CVM_LOCAL_PREFLIGHT:-0}"

DEPLOY_HOST="${DEPLOY_HOST:-ubuntu@1.13.198.172}"
DEPLOY_REPO="${DEPLOY_REPO:-/home/ubuntu/lingniao-golf}"
GIT_BRANCH="${GIT_BRANCH:-main}"
SKIP_GIT="${SKIP_GIT:-0}"

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
  -o ServerAliveCountMax=240
)

if [[ "${SSH_BATCH_MODE}" == yes ]] && [[ -f "${BIRDIE_CVM_KEY}" ]]; then
  SSH_OPTS+=( -o "IdentityFile=${BIRDIE_CVM_KEY}" )
fi

if [[ "${CVM_LOCAL_PREFLIGHT}" =~ ^(1|true|yes)$ ]]; then
  f="${ENV_FILE:-$REPO_ROOT/.env.local}"
  echo "→ SSH 前本地预检: $f"
  bash "$REPO_ROOT/infra/deploy/quick-check-env-local.sh" "$f"
  bash "$REPO_ROOT/infra/deploy/check-cvm-pay-mount.sh" "$f"
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  cvm-remote-release  host=$DEPLOY_HOST  repo=$DEPLOY_REPO  branch=$GIT_BRANCH  SKIP_GIT=$SKIP_GIT"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

ssh "${SSH_OPTS[@]}" "$DEPLOY_HOST" bash -s -- "$DEPLOY_REPO" "$GIT_BRANCH" "$SKIP_GIT" << 'EOS'
set -euo pipefail
export DEPLOY_REPO="$1"
export GIT_BRANCH="$2"
export SKIP_GIT="$3"
cd "$DEPLOY_REPO" || {
  echo "✗ cd $DEPLOY_REPO 失败" >&2
  exit 1
}
exec bash infra/deploy/release-cvm-on-server.sh
EOS
