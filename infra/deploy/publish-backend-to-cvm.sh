#!/usr/bin/env bash
# Mac → CVM：先发 optional git pull，再 rsync backend/（可选 ai_engine/），最后重建容器并 alembic。
# 解决「散装 scp」漏文件、以及「未跑迁移」导致训练/分析等仍 500。
# ai_engine：分析推理与 preprocess；与 backend 分叉时需一并 rsync + --build ai_engine。
#
# 【推荐先发】路径 B 免密：bash infra/deploy/setup-cvm-ssh-key.sh
#
# 默认 ubuntu@1.13.198.172、/home/ubuntu/lingniao-golf。覆盖示例：
#   DEPLOY_HOST=ubuntu@… DEPLOY_REPO=/home/ubuntu/xxx bash infra/deploy/publish-backend-to-cvm.sh
#
# 环境变量：
#   REMOTE_RSYNC_BACKEND=no   跳过 rsync backend/
#   REMOTE_RSYNC_AI_ENGINE=no 跳过 rsync ai_engine/
#   REMOTE_RSYNC_COMPOSE=no   跳过 scp docker-compose*.yml（默认同步三件套，勿漏 ai_engine/test 叠层）
#   REMOTE_GIT_PULL=no        不发版前 git pull（默认 yes）
#   GIT_BRANCH=main
#   REMOTE_ALEMBIC=no         跳过 alembic upgrade head（默认 yes）
#   REMOTE_EXTRA_COMPOSE_FLAGS   例：-f docker-compose.extra.yml
#   REMOTE_BUILD_CMD=...      非空则完全替代远端 compose/alembic 段（高级）
#
# 非交互：SSH_BATCH_MODE=yes（须已配置免密密钥）
set -euo pipefail

REMOTE_BUILD_CMD="${REMOTE_BUILD_CMD:-}"
REMOTE_RSYNC_BACKEND="${REMOTE_RSYNC_BACKEND:-yes}"
REMOTE_RSYNC_AI_ENGINE="${REMOTE_RSYNC_AI_ENGINE:-yes}"
REMOTE_RSYNC_COMPOSE="${REMOTE_RSYNC_COMPOSE:-yes}"
REMOTE_GIT_PULL="${REMOTE_GIT_PULL:-yes}"
REMOTE_ALEMBIC="${REMOTE_ALEMBIC:-yes}"
GIT_BRANCH="${GIT_BRANCH:-main}"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
DEPLOY_HOST="${DEPLOY_HOST:-ubuntu@1.13.198.172}"
DEPLOY_REPO="${DEPLOY_REPO:-/home/ubuntu/lingniao-golf}"
REMOTE_EXTRA_COMPOSE_FLAGS="${REMOTE_EXTRA_COMPOSE_FLAGS:-}"
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
  # 远端 compose build（尤其 uv sync）耗时很长；无 keepalive 时 NAT/防火墙易 idle 掐断 SSH
  -o ServerAliveInterval=30
  -o ServerAliveCountMax=240
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

# rsync -e 用：把 ssh 及其参数拼成一条命令
rsync_ssh_rsh() {
  local out=""
  local a
  for a in ssh "${SSH_OPTS[@]}"; do
    out+=$(printf ' %q' "$a")
  done
  echo "${out# }"
}

cd "${REPO_ROOT}"
need_file infra/deploy/check-cvm-pay-mount.sh
need_file docker-compose.yml
need_file docker-compose.test.yml
need_file docker-compose.cvm.yml
need_file backend/Dockerfile
need_file backend/app/main.py
need_file ai_engine/Dockerfile
need_file ai_engine/app/main.py

ssh "${SSH_OPTS[@]}" "${DEPLOY_HOST}" "mkdir -p '${DEPLOY_REPO}/infra/deploy'"
scp "${SSH_OPTS[@]}" infra/deploy/check-cvm-pay-mount.sh \
  "${DEPLOY_HOST}:${DEPLOY_REPO}/infra/deploy/check-cvm-pay-mount.sh"
chmod +x infra/deploy/release-cvm-on-server.sh 2>/dev/null || true
scp "${SSH_OPTS[@]}" infra/deploy/release-cvm-on-server.sh \
  "${DEPLOY_HOST}:${DEPLOY_REPO}/infra/deploy/release-cvm-on-server.sh"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  远端: ${DEPLOY_HOST}"
echo "  目录: ${DEPLOY_REPO}"
echo "  git:  REMOTE_GIT_PULL=${REMOTE_GIT_PULL}  branch=${GIT_BRANCH}"
echo "  同步: REMOTE_RSYNC_BACKEND=${REMOTE_RSYNC_BACKEND}"
echo "  同步: REMOTE_RSYNC_AI_ENGINE=${REMOTE_RSYNC_AI_ENGINE}"
echo "  同步: REMOTE_RSYNC_COMPOSE=${REMOTE_RSYNC_COMPOSE} (docker-compose + test + cvm)"
echo "  db:   REMOTE_ALEMBIC=${REMOTE_ALEMBIC}"
if [[ -f "${BIRDIE_CVM_KEY}" ]]; then
  echo "  认证: ${BIRDIE_CVM_KEY} （BatchMode=${SSH_BATCH_MODE}）"
else
  echo "  认证: 密码或默认 ssh-agent"
fi
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [[ "${REMOTE_GIT_PULL}" != "no" ]]; then
  echo "→ 远端 git（仅当 \$DEPLOY_REPO 为克隆仓库时执行）"
  ssh "${SSH_OPTS[@]}" "${DEPLOY_HOST}" bash --norc --noprofile <<EOF
set -euo pipefail
cd '${DEPLOY_REPO}' || { echo "✗ 远端目录不存在" >&2; exit 1; }
if [[ ! -d .git ]]; then
  echo "⚠ 跳过 git pull：${DEPLOY_REPO} 无 .git。编排文件请依赖本脚本默认 scp docker-compose.yml / .test / .cvm。"
  exit 0
fi
git fetch origin
git checkout '${GIT_BRANCH}'
git pull --ff-only origin '${GIT_BRANCH}'
EOF
fi

RSYNC_CMD=(rsync -avz)
RSYNC_CMD+=(
  --exclude '.venv/'
  --exclude '__pycache__/'
  --exclude '.pytest_cache/'
  --exclude '*.pyc'
  --exclude '*.egg-info/'
  --exclude '.ruff_cache/'
  --exclude '.secrets/'
)
RSYNC_CMD+=(-e "$(rsync_ssh_rsh)")

if [[ "${REMOTE_RSYNC_COMPOSE}" != "no" ]]; then
  echo "→ scp docker-compose.yml / docker-compose.test.yml / docker-compose.cvm.yml → ${DEPLOY_REPO}/"
  scp "${SSH_OPTS[@]}" \
    "${REPO_ROOT}/docker-compose.yml" \
    "${REPO_ROOT}/docker-compose.test.yml" \
    "${REPO_ROOT}/docker-compose.cvm.yml" \
    "${DEPLOY_HOST}:${DEPLOY_REPO}/"
else
  echo "⚠ 已跳过 REMOTE_RSYNC_COMPOSE（慎用：云上 compose 可能与仓库不一致）"
fi

if [[ "${REMOTE_RSYNC_BACKEND}" != "no" ]]; then
  echo "→ rsync ${REPO_ROOT}/backend/ → ${DEPLOY_HOST}:${DEPLOY_REPO}/backend/"
  "${RSYNC_CMD[@]}" "${REPO_ROOT}/backend/" "${DEPLOY_HOST}:${DEPLOY_REPO}/backend/"
else
  echo "⚠ 已跳过 REMOTE_RSYNC_BACKEND"
fi

if [[ "${REMOTE_RSYNC_AI_ENGINE}" != "no" ]]; then
  echo "→ rsync ${REPO_ROOT}/ai_engine/ → ${DEPLOY_HOST}:${DEPLOY_REPO}/ai_engine/"
  "${RSYNC_CMD[@]}" "${REPO_ROOT}/ai_engine/" "${DEPLOY_HOST}:${DEPLOY_REPO}/ai_engine/"
else
  echo "⚠ 已跳过 REMOTE_RSYNC_AI_ENGINE"
fi

if [[ -n "${REMOTE_BUILD_CMD}" ]]; then
  ssh "${SSH_OPTS[@]}" "${DEPLOY_HOST}" bash --norc --noprofile -c "${REMOTE_BUILD_CMD}"
else
  # 此处 heredoc 无引号：`DEPLOY_REPO` / `REMOTE_ALEMBIC` / REMOTE_EXTRA_COMPOSE_FLAGS 由本机展开一次。
  ssh "${SSH_OPTS[@]}" "${DEPLOY_HOST}" bash --norc --noprofile <<EOF
set -euo pipefail
cd '${DEPLOY_REPO}' || { echo "✗ 远端目录不存在: ${DEPLOY_REPO}" >&2; exit 1; }
test -f '.env.local' || { echo "✗ 缺少 ${DEPLOY_REPO}/.env.local" >&2; exit 1; }

bash infra/deploy/check-cvm-pay-mount.sh '.env.local' || exit 1

PAY_KEY_FLAGS=""
if [[ -f docker-compose.wechat-pay-key.yml ]]; then
  PAY_KEY_FLAGS="-f docker-compose.wechat-pay-key.yml"
fi

# shellcheck disable=SC2086
docker compose --project-directory '${DEPLOY_REPO}' \\
  -f docker-compose.yml -f docker-compose.test.yml -f docker-compose.cvm.yml \\
  \${PAY_KEY_FLAGS} ${REMOTE_EXTRA_COMPOSE_FLAGS} \\
  --env-file '${DEPLOY_REPO}/.env.local' up -d --build backend celery-worker ai_engine

if [[ '${REMOTE_ALEMBIC}' != 'no' ]]; then
  echo "→ alembic upgrade head"
  # shellcheck disable=SC2086
  docker compose --project-directory '${DEPLOY_REPO}' \\
    -f docker-compose.yml -f docker-compose.test.yml -f docker-compose.cvm.yml \\
    \${PAY_KEY_FLAGS} ${REMOTE_EXTRA_COMPOSE_FLAGS} \\
    --env-file '${DEPLOY_REPO}/.env.local' exec -T backend uv run alembic upgrade head
fi

docker restart xiaoniao-nginx 2>/dev/null || true
EOF
fi

echo ""
echo "✓ 发版流程结束（git pull（若有）→ compose yml → rsync backend+ai_engine → rebuild → alembic）。"
echo "  自检：curl -sS https://api.birdieai.cn/v1/health && echo"
echo "  若改过 infra/test/nginx.conf 而未用 git pull，请自行 scp 该文件以保持与 compose 挂载一致。"
