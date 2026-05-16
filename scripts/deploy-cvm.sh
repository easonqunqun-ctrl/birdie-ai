#!/usr/bin/env bash
# CVM / 生产发版：**统一入口文档化** + 可选本机预检（不替你 SSH）。
#
# 真实执行顺序仍以 docs/release-notes/CVM-canonical-deploy.md 为准。
#
# 用法（仓库根）：
#   bash scripts/deploy-cvm.sh                     # 打印阶段说明（默认）
#   bash scripts/deploy-cvm.sh --dry-run           # 打印建议在 CVM 上执行的 compose 片段
#   bash scripts/deploy-cvm.sh --local-preflight   # env 占位 + 真实支付 compose 自检
#
# 环境变量：
#   ENV_FILE   默认 .env.local（仅 --local-preflight）

set -euo pipefail

REPO_ROOT="$(cd "$(dirname "$0")/.." && pwd)"

dry_run=false
preflight=false
preflight_file=""
for arg in "$@"; do
  case "$arg" in
    --dry-run) dry_run=true ;;
    --local-preflight) preflight=true ;;
    --env-file=*)
      preflight_file="${arg#*=}"
      preflight=true
      ;;
    *)
      echo "未知参数: $arg（可选：--dry-run | --local-preflight [--env-file=路径]）" >&2
      exit 1
      ;;
  esac
done

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  部署入口说明（deploy-cvm.sh）  repo=$REPO_ROOT"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

if [[ "$preflight" == true ]]; then
  f="${preflight_file:-${ENV_FILE:-$REPO_ROOT/.env.local}}"
  echo "→ 占位符自检: $f"
  bash "$REPO_ROOT/infra/deploy/quick-check-env-local.sh" "$f"
  echo "→ 真实支付 compose（若 WECHAT_PAY_MOCK_MODE=false）：$f"
  bash "$REPO_ROOT/infra/deploy/check-cvm-pay-mount.sh" "$f"
fi

echo ""
echo "## Phase 1  前置条件（须在公网网关 / TLS 就绪后）"
echo "  - 先发版 env：make cvm-preflight（可加 ENV_FILE=~/secrets/xxx.env）"
echo "  - 再测 HTTPS：make cvm-preflight-tls DOMAIN=api.birdieai.cn"
echo "  - 单项 TLS：make verify-weapp-https DOMAIN=api.birdieai.cn"
echo "  - 首次证书：make issue-le-cert / renew-le-cert / sync-le-certs"

echo ""
echo "## Phase 2  密钥与镜像"
echo "  - Mac 真源 ~/secrets → scp … :\\\$DEPLOY_REPO/.env.local（见 CVM 文档 §1）"

echo ""
echo "## Phase 3  上栈 / 迁移（CVM 仓库根）"
echo "  日常最爱：先 git push → make release-cvm（本机不配 ENV_FILE）"
echo "  SKIP_GIT=1 bash infra/deploy/release-cvm-on-server.sh   # 无 .git 过渡期"
echo "  或默认：bash infra/deploy/release-cvm-on-server.sh"
echo "  本机：make cvm-remote-release｜DEPLOY_HOST / SKIP_GIT / GIT_BRANCH（同 release-cvm）"
echo "  Mac rsync + 远端重建：make publish-backend-cvm"

echo ""
echo "## Phase 4  冒烟"
echo "  make cvm-smoke DOMAIN=api.birdieai.cn TOKEN=…"

echo ""
echo "## Phase 5  观测"
echo "  本机 compose 与 CVM 对齐时：make deploy-cvm-logs；否则 SSH 上 docker compose … logs"

echo ""
echo "## Phase 6  回滚"
echo "  git checkout <上一标签> → 同上 compose rebuild；备份库见运维规范（勿 down -v）"

if [[ "$dry_run" == true ]]; then
  echo ""
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  echo "  --dry-run：建议在 CVM 上使用的 compose（按实际 PEM 叠加调整）"
  echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
  cat << 'EOF'
cd ~/lingniao-golf

COMPOSE_STACK="docker compose -f docker-compose.yml -f docker-compose.test.yml -f docker-compose.cvm.yml"

# 若有商户私钥挂载：
[[ -f docker-compose.wechat-pay-key.yml ]] && COMPOSE_STACK="$COMPOSE_STACK -f docker-compose.wechat-pay-key.yml"

$COMPOSE_STACK --env-file .env.local up -d --build
$COMPOSE_STACK --env-file .env.local exec -T backend uv run alembic upgrade head

docker restart xiaoniao-nginx 2>/dev/null || true

curl -sfS "https://api.birdieai.cn/v1/health" | head -c 300
EOF
fi
