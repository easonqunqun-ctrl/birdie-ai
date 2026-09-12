#!/usr/bin/env bash
# CVM 上整包发版（人已登录服务器 shell / 控制台）：
#   git 更新 → docker compose（含 cvm 叠层）build 拉起（不含 nginx）→ alembic → nginx -s reload
#
# 用法（仓库根）：
#   bash infra/deploy/release-cvm-on-server.sh
#
# 环境变量：
#   DEPLOY_REPO              默认 ~/lingniao-golf
#   GIT_BRANCH               默认 main（发版 tag 可：GIT_BRANCH=v0.9.1）
#   若存在 docker-compose.wechat-pay-key.yml 会自动叠加（与 make deploy-cvm-up 一致）。
#   WECHAT_PAY_MOCK_MODE=false 时会先跑 infra/deploy/check-cvm-pay-mount.sh。
#   SKIP_GIT=1                 跳过 git fetch/checkout/pull（服务端无 .git / rsync-only 过渡期）。
#   ALLOW_DIRTY_GIT=1          默认：若 .git 存在且工作区不干净则失败，避免 pull 合并冲突 / 镜像打到脏树。
#                              应急排障可设 1 跳过检查（不推荐日常发版）。
#
# 约定见 docs/release-notes/CVM-canonical-deploy.md
set -euo pipefail

DEPLOY_REPO="${DEPLOY_REPO:-$HOME/lingniao-golf}"
GIT_BRANCH="${GIT_BRANCH:-main}"
DEPLOY_REPO="${DEPLOY_REPO/#\~/$HOME}"

cd "$DEPLOY_REPO" || {
  echo "✗ 无法进入 $DEPLOY_REPO" >&2
  exit 1
}
[[ -f .env.local ]] || {
  echo "✗ 缺少 $DEPLOY_REPO/.env.local" >&2
  exit 1
}

COMPOSE_FILES=( -f docker-compose.yml -f docker-compose.test.yml -f docker-compose.cvm.yml )
if [[ -f docker-compose.wechat-pay-key.yml ]]; then
  COMPOSE_FILES+=( -f docker-compose.wechat-pay-key.yml )
fi

dc() {
  docker compose --project-directory "$DEPLOY_REPO" "${COMPOSE_FILES[@]}" \
    --env-file "$DEPLOY_REPO/.env.local" "$@"
}

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  CVM 发版  repo=$DEPLOY_REPO  branch=$GIT_BRANCH"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [[ -d .git && "${SKIP_GIT:-0}" != "1" && "${ALLOW_DIRTY_GIT:-0}" != "1" ]]; then
  if [[ -n "$(git status --porcelain 2>/dev/null)" ]]; then
    echo "✗ 工作区不干净：继续发版可能导致 git pull 失败或镜像混入未提交改动。" >&2
    git status -sb >&2
    echo "" >&2
    echo "  在确认无未备份内容后，可在仓库根执行（将丢弃本地修改；勿 git clean 其它站点文件）：" >&2
    echo "    git fetch origin && git reset --hard \"origin/$GIT_BRANCH\"" >&2
    echo "  保留 .env.local；保留 thinkfree / 居境 等机上站点文件；勿 checkout infra/test/nginx.conf。" >&2
    echo "  仅应急可：ALLOW_DIRTY_GIT=1 bash infra/deploy/release-cvm-on-server.sh" >&2
    exit 1
  fi
fi

if [[ -d .git && "${SKIP_GIT:-0}" != "1" ]]; then
  git fetch origin
  git checkout "$GIT_BRANCH"
  git pull --ff-only
else
  echo "⚠ 跳过 git fetch/checkout/pull（目录无 .git 或已设 SKIP_GIT=1；过渡期见 CVM 文档 §0）"
fi

bash infra/deploy/check-cvm-pay-mount.sh ".env.local"

# 公网 xiaoniao-nginx 与领翼共用，挂有其它站点（居境等）。禁止 recreate。
UP_SERVICES=()
while IFS= read -r svc; do
  [[ -z "$svc" || "$svc" == "nginx" ]] && continue
  UP_SERVICES+=("$svc")
done < <(dc config --services)
if [[ ${#UP_SERVICES[@]} -eq 0 ]]; then
  echo "✗ compose 服务列表为空" >&2
  exit 1
fi
echo "→ docker compose up -d --build（跳过 nginx：${UP_SERVICES[*]})"
dc up -d --build "${UP_SERVICES[@]}"

echo "→ alembic upgrade head"
dc exec -T backend uv run alembic upgrade head

if docker ps --format '{{.Names}}' | grep -qx xiaoniao-nginx; then
  echo "→ nginx -s reload（禁止 recreate / restart xiaoniao-nginx）"
  docker exec xiaoniao-nginx nginx -s reload \
    || echo "⚠ nginx reload 失败；不要 recreate，只排障"
else
  echo "⚠ xiaoniao-nginx 未在运行；禁止用仓库 compose 拉起（会丢掉其它站点挂载）"
fi

echo "→ curl health"
curl -sS https://api.birdieai.cn/v1/health | head -c 400 || true
echo
echo "✓ release-cvm-on-server 完成"
