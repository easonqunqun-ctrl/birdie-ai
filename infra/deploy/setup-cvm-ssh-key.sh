#!/usr/bin/env bash
# 路径 B：为本机生成 **仅用于本项目 CVM 部署** 的 SSH 密钥，并把公钥装进服务器 authorized_keys，
# 后续 `make publish-backend-cvm` 免输密码。（密钥不带口令，若要更高安全可：`ssh-keygen -p -f KEY`）
#
# 用法（仓库根）：
#   bash infra/deploy/setup-cvm-ssh-key.sh
#   或：make setup-cvm-ssh-key
#
# 环境变量：
#   DEPLOY_HOST             默认 ubuntu@1.13.198.172
#   BIRDIE_CVM_KEY          默认 ~/.ssh/id_ed25519_birdie_golf
#
# 本会话里 **仍会提示输入一次服务器开机密码**，完成后再无密码上传。
set -euo pipefail

DEPLOY_HOST="${DEPLOY_HOST:-ubuntu@1.13.198.172}"
# 从 IM/文档复制时偶发全角字符、CR、首尾空白 → ssh-copy-id 报「hostname contains invalid characters」
DEPLOY_HOST="$(printf '%s' "${DEPLOY_HOST}" | tr -d '\r' | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
if [[ ! "${DEPLOY_HOST}" =~ ^[A-Za-z0-9._-]+@[A-Za-z0-9.:_-]+$ ]]; then
  echo "✗ DEPLOY_HOST 异常（勿含中文引号/换行）：${DEPLOY_HOST}" >&2
  exit 1
fi
BIRDIE_CVM_KEY="${BIRDIE_CVM_KEY:-$HOME/.ssh/id_ed25519_birdie_golf}"

mkdir -p "$(dirname "${BIRDIE_CVM_KEY}")"
chmod 700 "${HOME}/.ssh" 2>/dev/null || true

if [[ ! -f "${BIRDIE_CVM_KEY}" ]]; then
  echo "→ 生成部署专用密钥 ${BIRDIE_CVM_KEY} （无口令，仅限本仓库约定路径）…"
  ssh-keygen -t ed25519 -f "${BIRDIE_CVM_KEY}" -N "" -C "lingniao-golf-cvm-publish"
fi
chmod 600 "${BIRDIE_CVM_KEY}"

echo ""
echo "→ 将把公钥写入 ${DEPLOY_HOST} （此处输入 **最后一次** 服务器密码）："
ssh-copy-id -i "${BIRDIE_CVM_KEY}.pub" -o StrictHostKeyChecking=accept-new "${DEPLOY_HOST}"

echo ""
echo "→ 校验免密："
ssh -i "${BIRDIE_CVM_KEY}" -o IdentitiesOnly=yes -o StrictHostKeyChecking=accept-new -o BatchMode=yes \
  "${DEPLOY_HOST}" bash -lc 'echo "✓ OK: $(hostname)"'

echo ""
echo "✓ 路径 B 已就绪；以后发布：`make publish-backend-cvm`（不再需要密码）。"
echo "  如需换机器或换 IP：`DEPLOY_HOST=… BIRDIE_CVM_KEY=… bash infra/deploy/setup-cvm-ssh-key.sh`"
