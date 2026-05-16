#!/usr/bin/env bash
# 使用与「首次申请」相同的 Docker certbot 镜像执行 renew（无需宿主机安装 certbot）。
# renew 沿用 issuance 时写入 /etc/letsencrypt/renewal/*.conf 的 authenticator（webroot）。
#
# 用法（仓库根目录）：
#   bash infra/deploy/renew-le-cert-docker.sh api.birdieai.cn
# 或：
#   make renew-le-cert DOMAIN=api.birdieai.cn
#
# 成功后会把最新 PEM sync 进 infra/test/certs 并重载 nginx（与 sync-le-certs 脚本一致）。
#
set -euo pipefail

DOMAIN="${1:-api.birdieai.cn}"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../.." && pwd)"
WEBROOT="${REPO_ROOT}/infra/test/acme-webroot"

CERTBOT_IMG="${CERTBOT_IMG:-certbot/certbot:v3.1.0}"

mkdir -p "${WEBROOT}/.well-known/acme-challenge"

echo "→ certbot renew（镜像 ${CERTBOT_IMG}），域名配置：${DOMAIN}"

docker run --rm \
  -v "${WEBROOT}:/var/www/html" \
  -v /etc/letsencrypt:/etc/letsencrypt \
  "${CERTBOT_IMG}" renew --non-interactive

bash "${REPO_ROOT}/infra/deploy/sync-le-certs-from-letsencrypt.sh" "${DOMAIN}"
