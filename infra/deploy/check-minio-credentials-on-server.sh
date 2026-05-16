#!/usr/bin/env bash
# 在云服务器核对：MinIO 容器 ROOT 凭证 vs 后端进程里的 MINIO_ACCESS_KEY（403 InvalidAccessKeyId 时用）。
# 用法：在任意目录执行：
#   bash infra/deploy/check-minio-credentials-on-server.sh
# 或复制本脚本内容到服务器后：
#   bash check-minio-credentials-on-server.sh

set -euo pipefail

M="${MINIO_CONTAINER:-xiaoniao-minio}"
B="${BACKEND_CONTAINER:-xiaoniao-backend}"

die() {
  echo "✗ $*" >&2
  exit 1
}

docker inspect "$M" >/dev/null 2>&1 || die "未找到容器: $M"
docker inspect "$B" >/dev/null 2>&1 || die "未找到容器: $B"

echo "=== MinIO 容器 (${M}) ROOT 账号（Compose 写入的 MINIO_ROOT_*） ==="
ROOT_USER=$(docker inspect "$M" --format '{{range .Config.Env}}{{println .}}{{end}}' | grep -E '^MINIO_ROOT_USER=' | tail -1 | cut -d= -f2-)
ROOT_PASS=$(docker inspect "$M" --format '{{range .Config.Env}}{{println .}}{{end}}' | grep -E '^MINIO_ROOT_PASSWORD=' | tail -1 | cut -d= -f2-)
echo "MINIO_ROOT_USER=${ROOT_USER}"
if [[ -n "$ROOT_PASS" ]]; then
  echo "MINIO_ROOT_PASSWORD=<已设置，长度 ${#ROOT_PASS}，不在此打印>"
else
  echo "MINIO_ROOT_PASSWORD=<空>"
fi

echo ""
echo "=== 后端容器 (${B}) 当前 MINIO_* 环境变量 ==="
docker exec "$B" printenv MINIO_ACCESS_KEY MINIO_SECRET_KEY MINIO_BUCKET 2>/dev/null || true

AK=$(docker exec "$B" printenv MINIO_ACCESS_KEY 2>/dev/null || true)
SK=$(docker exec "$B" printenv MINIO_SECRET_KEY 2>/dev/null || true)

echo ""
if [[ -z "$ROOT_USER" || -z "$AK" ]]; then
  echo "✗ 无法读取完整对比项，请手动 docker inspect / printenv。"
  exit 2
fi

if [[ "$ROOT_USER" == "$AK" && "$ROOT_PASS" == "$SK" ]]; then
  echo "✓ MinIO ROOT_USER 与后端 MINIO_ACCESS_KEY 一致；ROOT_PASSWORD 与 MINIO_SECRET_KEY 一致。"
  echo "  若仍有 403，请考虑签名 URL 与 nginx /minio 路径、bucket 是否存在等问题。"
else
  echo "✗ 不一致：预签名会使用后端 MINIO_ACCESS_KEY，MinIO 只认 ROOT_USER。"
  echo "  请在 ~/lingniao-golf/.env.local 中把 MINIO_ACCESS_KEY / MINIO_SECRET_KEY"
  echo "  改成与 MinIO ROOT 完全相同，然后："
  echo "    docker compose --env-file .env.local up -d --force-recreate backend celery-worker"
  echo "    docker restart xiaoniao-nginx"
fi
