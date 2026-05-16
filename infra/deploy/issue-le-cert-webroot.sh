#!/usr/bin/env bash
# 使用 HTTP-01 webroot 申请 Let's Encrypt（须 nginx 已在 80 暴露 /.well-known/acme-challenge/）。
#
# 用法（仓库根目录）：
#   bash infra/deploy/issue-le-cert-webroot.sh your@email.com api.birdieai.cn
# 或：
#   make issue-le-cert EMAIL=your@email.com DOMAIN=api.birdieai.cn
#
# 前置：
#   1. 域名 A 记录指向本机公网 IP；安全组放行 80/443
#   2. 已 make deploy-test（nginx 容器挂载 infra/test/acme-webroot → /var/www/html）
#
set -euo pipefail

EMAIL="${1:-}"
DOMAIN="${2:-api.birdieai.cn}"

if [[ -z "${EMAIL}" ]]; then
  echo "用法：$0 <certbot-email> [domain]" >&2
  echo "  例：$0 ops@yourcompany.com api.birdieai.cn" >&2
  exit 1
fi

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
WEBROOT="${REPO_ROOT}/infra/test/acme-webroot"

mkdir -p "${WEBROOT}/.well-known/acme-challenge"

CERTBOT_IMG="${CERTBOT_IMG:-certbot/certbot:v3.1.0}"

extra_args=()
if [[ "${CERTBOT_STAGING:-}" == "1" ]]; then
  extra_args+=(--staging)
  echo "⚠ 使用 Let's Encrypt STAGING（仅调试），浏览器会提示不受信任"
fi

echo "→ 申请域名：${DOMAIN}（email=${EMAIL}）"
echo "→ webroot：${WEBROOT}"

docker run --rm \
  -v "${WEBROOT}:/var/www/html" \
  -v /etc/letsencrypt:/etc/letsencrypt \
  "${CERTBOT_IMG}" certonly \
  --webroot \
  --webroot-path=/var/www/html \
  -d "${DOMAIN}" \
  --email "${EMAIL}" \
  --agree-tos \
  --non-interactive \
  "${extra_args[@]}"

bash "${REPO_ROOT}/infra/deploy/sync-le-certs-from-letsencrypt.sh" "${DOMAIN}"
