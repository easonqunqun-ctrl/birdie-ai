#!/usr/bin/env bash
# 将 Let's Encrypt live 目录下的证书拷入 infra/test/certs（容器挂载目录），并重载 nginx。
#
# 用法（在仓库根目录）：
#   bash infra/deploy/sync-le-certs-from-letsencrypt.sh api.birdieai.cn
# 或通过 Makefile：
#   make sync-le-certs DOMAIN=api.birdieai.cn
#
set -euo pipefail

DOMAIN="${1:-api.birdieai.cn}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
CERTS_DIR="${REPO_ROOT}/infra/test/certs"
LIVE="/etc/letsencrypt/live/${DOMAIN}"

# live/ 常为 root:750，ubuntu 无法遍历；不可用裸 [[ -f ]] 判断（会误判「不存在」）
_le_pair_ok() {
  if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
    [[ -f "${LIVE}/fullchain.pem" && -f "${LIVE}/privkey.pem" ]]
  else
    sudo test -f "${LIVE}/fullchain.pem" && sudo test -f "${LIVE}/privkey.pem"
  fi
}

if ! _le_pair_ok; then
  echo "✗ 未找到 ${LIVE}/fullchain.pem 或 privkey.pem（请先申请证书；或用 sudo ls ${LIVE}/ 核对域名目录名）" >&2
  exit 1
fi

mkdir -p "${CERTS_DIR}"

if [[ "${EUID:-$(id -u)}" -eq 0 ]]; then
  run() { "$@"; }
else
  run() { sudo "$@"; }
fi

run cp "${LIVE}/fullchain.pem" "${CERTS_DIR}/fullchain.pem"
run cp "${LIVE}/privkey.pem" "${CERTS_DIR}/privkey.pem"

owner="$(id -u):$(id -g)"
run chown "${owner}" "${CERTS_DIR}/fullchain.pem" "${CERTS_DIR}/privkey.pem"
chmod 644 "${CERTS_DIR}/fullchain.pem"
chmod 600 "${CERTS_DIR}/privkey.pem"

echo "✓ 已同步 Let's Encrypt → ${CERTS_DIR}/fullchain.pem / privkey.pem"

cd "${REPO_ROOT}"
if [[ -f .env.local ]]; then
  if docker compose -f docker-compose.yml -f docker-compose.test.yml --env-file .env.local exec -T nginx nginx -s reload >/dev/null 2>&1; then
    echo "✓ nginx 已 reload"
  else
    echo "⚠ nginx reload 跳过（容器未启动时可忽略）；起栈后执行："
    echo "  docker compose -f docker-compose.yml -f docker-compose.test.yml --env-file .env.local exec nginx nginx -s reload"
  fi
fi
