#!/usr/bin/env bash
# 在云服务器上使用：必须先 cd 到本仓库根目录（与 docker-compose.yml 同级），那里有 .env.local。
# 作用：备份 .env.local，删除指向 Cloudflare/ngrok 等穿透的 MINIO_PUBLIC_ENDPOINT，
#       并为 Docker Compose 写入占位值 http://minio:9000，使 staging/prod 下签发 upload_url
#       回落到「API_PUBLIC_BASE_URL/minio」（须 nginx 已反代该路径）。
#
# 用法：
#   cd /你在服务器上的仓库路径
#   bash infra/deploy/server-fix-minio-public.sh
#   docker compose --env-file .env.local restart backend

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
ENV_REL="${1:-.env.local}"
ENV_FILE="$REPO_ROOT/$ENV_REL"

if [[ ! -f "$ENV_FILE" ]]; then
  echo "[fix-minio-public] ✗ 未找到环境文件：$ENV_FILE"
  echo "    请先：cd $REPO_ROOT"
  echo "    并把第一个参数设为相对路径（默认 .env.local）。"
  exit 1
fi

if [[ ! -f "$REPO_ROOT/docker-compose.yml" ]]; then
  echo "[fix-minio-public] ⚠ 警告：在 $REPO_ROOT 未发现 docker-compose.yml，仍会继续改 $ENV_REL"
fi

bak="${ENV_FILE}.bak.uploadfix.$(date +%s)"
cp "$ENV_FILE" "$bak"
echo "[fix-minio-public] 已备份 → $bak"

tmp="$(mktemp)"
removed=0
while IFS= read -r line || [[ -n "$line" ]]; do
  if [[ "$line" =~ ^MINIO_PUBLIC_ENDPOINT= ]]; then
    val="${line#MINIO_PUBLIC_ENDPOINT=}"
    lval=$(printf '%s' "$val" | tr '[:upper:]' '[:lower:]')
    if [[ "$lval" == *"trycloudflare"* || "$lval" == *"ngrok"* || "$lval" == *"loca.lt"* || "$lval" == *"localtunnel"* || "$lval" == *"serveo.net"* ]]; then
      echo "[fix-minio-public]   移除穿透项：${line:0:80}…"
      removed=$((removed + 1))
      continue
    fi
  fi
  printf '%s\n' "$line"
done <"$ENV_FILE" >"$tmp"
mv "$tmp" "$ENV_FILE"

if grep -q '^MINIO_PUBLIC_ENDPOINT=' "$ENV_FILE" 2>/dev/null; then
  echo "[fix-minio-public] 已保留现有非穿透的 MINIO_PUBLIC_ENDPOINT。"
else
  {
    echo ""
    echo "# ↓ infra/deploy/server-fix-minio-public.sh 追加（Docker 内占位，触发 API/minio 公网签发）"
    echo "MINIO_PUBLIC_ENDPOINT=http://minio:9000"
  } >>"$ENV_FILE"
  echo "[fix-minio-public] 已追加 MINIO_PUBLIC_ENDPOINT=http://minio:9000"
fi

echo "[fix-minio-public] ✓ 完成。请在仓库根目录执行："
echo "    docker compose --env-file ${ENV_REL} restart backend"
