#!/usr/bin/env bash
# 在云服务器上一次改掉「穿透域名 + APP_ENV=local」等最常见坑。
# 不修改数据库口令、JWT 等（避免因密码与已有 volume 不一致而连不上库）。
#
# 用法（默认域名 api.birdieai.cn，默认文件 ~/lingniao-golf/.env.local）：
#   bash infra/deploy/patch-wechat-upload-env-quick.sh
# 指定域名与文件：
#   DOMAIN=api.birdieai.cn bash infra/deploy/patch-wechat-upload-env-quick.sh /path/to/.env.local
#
# 然后再（务必在 Compose 目录，且必须用 force-recreate 才读到新变量）：
#   cd /home/ubuntu/lingniao-golf
#   docker compose --env-file .env.local up -d --force-recreate backend celery-worker

set -euo pipefail

DOMAIN="${DOMAIN:-api.birdieai.cn}"
HTTPS_API="https://${DOMAIN}"
MINIO_PUB="${HTTPS_API}/minio"

ENV_FILE="${1:-}"
if [[ -z "$ENV_FILE" ]]; then
  if [[ -f "/home/ubuntu/lingniao-golf/.env.local" ]]; then
    ENV_FILE="/home/ubuntu/lingniao-golf/.env.local"
  elif [[ -f ".env.local" ]]; then
    ENV_FILE="$(pwd)/.env.local"
  else
    echo "✗ 未找到默认 .env.local，请传入路径。"
    echo "  例: DOMAIN=api.birdieai.cn bash $0 /home/ubuntu/lingniao-golf/.env.local"
    exit 1
  fi
fi

[[ -f "$ENV_FILE" ]] || { echo "✗ 未找到: $ENV_FILE"; exit 1; }

bak="${ENV_FILE}.bak.patch.$(date +%s)"
cp "$ENV_FILE" "$bak"
echo "[patch-wechat-upload] 已备份 → $bak"

sed -i \
  -e "s|^MINIO_PUBLIC_ENDPOINT=.*|MINIO_PUBLIC_ENDPOINT=${MINIO_PUB}|" \
  -e "s|^API_PUBLIC_BASE_URL=.*|API_PUBLIC_BASE_URL=${HTTPS_API}|" \
  -e 's/^APP_ENV=local\b/APP_ENV=staging/' \
  -e 's/^APP_DEBUG=true\s*$/APP_DEBUG=false/' \
  -e "s|^BACKEND_CORS_ORIGINS=.*|BACKEND_CORS_ORIGINS=${HTTPS_API}|" \
  "$ENV_FILE"

echo "[patch-wechat-upload] 已写入:"
echo "  MINIO_PUBLIC_ENDPOINT=${MINIO_PUB}"
echo "  API_PUBLIC_BASE_URL=${HTTPS_API}"
echo "  APP_ENV=staging（由原 local 替换） APP_DEBUG=false  BACKEND_CORS_ORIGINS=${HTTPS_API}"
echo "[patch-wechat-upload] 请到 compose 目录执行:"
echo "  docker compose --env-file .env.local up -d --force-recreate backend celery-worker"
