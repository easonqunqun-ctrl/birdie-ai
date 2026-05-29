#!/usr/bin/env bash
# infra/deploy/seed-sample-fixture-to-minio.sh
#
# 幂等地把 `/v1/analyses/sample` 需要的占位视频 + 缩略图 seed 到 MinIO，
# 用于 W15-B 修复："sample fixture URL 默认走 backend 同源代理 → MinIO，
# 但 staging/prod 上 bucket 是空的，导致 sample 入口黑屏 / 404"。
#
# 设计：
#   - 视频：5s 720x1280 mp4（ffmpeg lavfi color + drawtext 合成，靛蓝底 + 金字水印）
#   - 缩略：从合成视频里抽第 1s 一帧 jpg
#   - 上传：用容器名 xiaoniao-ai-engine 跑 ffmpeg（自带 ffmpeg），
#          再 docker cp 转到 xiaoniao-minio 后 mc cp 到 bucket/samples/
#   - 幂等：上传前先 mc stat 检查；存在就跳过（除非 --force）
#
# 用法：
#   bash infra/deploy/seed-sample-fixture-to-minio.sh           # 在本机（localhost）跑
#   ssh ubuntu@cvm 'bash -s' < seed-sample-fixture-to-minio.sh  # 远程注入
#
# 环境变量：
#   MINIO_BUCKET            目标 bucket（默认读 .env.local 里的 MINIO_BUCKET，
#                           读不到时回落 xiaoniao-videos）
#   AI_ENGINE_CONTAINER     ffmpeg 容器（默认 xiaoniao-ai-engine）
#   MINIO_CONTAINER         MinIO 容器（默认 xiaoniao-minio）
#   FORCE                   设为 1 强制覆盖

set -euo pipefail

AI_ENGINE_CONTAINER="${AI_ENGINE_CONTAINER:-xiaoniao-ai-engine}"
MINIO_CONTAINER="${MINIO_CONTAINER:-xiaoniao-minio}"

# 读 bucket 优先级：环境变量 > .env.local > 默认
if [[ -z "${MINIO_BUCKET:-}" ]]; then
  if [[ -f "${BASH_SOURCE%/*}/../../.env.local" ]]; then
    MINIO_BUCKET=$(grep -E '^MINIO_BUCKET=' "${BASH_SOURCE%/*}/../../.env.local" 2>/dev/null | head -1 | cut -d= -f2 || true)
  fi
  MINIO_BUCKET="${MINIO_BUCKET:-xiaoniao-videos}"
fi

VIDEO_KEY="samples/swing_demo.mp4"
THUMB_KEY="samples/swing_demo_thumb.jpg"

echo "==> seed sample fixture to MinIO"
echo "    bucket = ${MINIO_BUCKET}"
echo "    video  = ${VIDEO_KEY}"
echo "    thumb  = ${THUMB_KEY}"
echo "    force  = ${FORCE:-0}"

# 幂等检查
if [[ "${FORCE:-0}" != "1" ]]; then
  if docker exec "$MINIO_CONTAINER" mc stat "local/${MINIO_BUCKET}/${VIDEO_KEY}" >/dev/null 2>&1 \
     && docker exec "$MINIO_CONTAINER" mc stat "local/${MINIO_BUCKET}/${THUMB_KEY}" >/dev/null 2>&1; then
    echo "==> already seeded, skip (set FORCE=1 to overwrite)"
    exit 0
  fi
fi

# 1. 在 ai_engine 容器里合成视频（靛蓝底 + 金字水印 + 5s + 静音）
echo "==> [1/3] ffmpeg synth video + thumb"
docker exec "$AI_ENGINE_CONTAINER" sh -c '
  ffmpeg -y -f lavfi -i "color=c=0x1a237e:s=720x1280:d=5:r=30" \
         -f lavfi -i "sine=f=440:d=5" \
         -vf "drawtext=text=领翼golf 示例:fontcolor=white:fontsize=64:x=(w-text_w)/2:y=(h-text_h)/2-80,drawtext=text=swing demo placeholder:fontcolor=0xc9a227:fontsize=36:x=(w-text_w)/2:y=(h-text_h)/2+20" \
         -c:v libx264 -preset fast -pix_fmt yuv420p -movflags +faststart \
         -c:a aac -shortest /tmp/swing_demo.mp4 >/dev/null 2>&1
  ffmpeg -y -i /tmp/swing_demo.mp4 -ss 1 -frames:v 1 -q:v 3 /tmp/swing_demo_thumb.jpg >/dev/null 2>&1
  ls -lh /tmp/swing_demo.mp4 /tmp/swing_demo_thumb.jpg
'

# 2. 转送到 minio 容器
echo "==> [2/3] copy to minio container"
TMP_DIR=$(mktemp -d)
trap 'rm -rf "$TMP_DIR"' EXIT
docker cp "${AI_ENGINE_CONTAINER}:/tmp/swing_demo.mp4"       "$TMP_DIR/swing_demo.mp4"
docker cp "${AI_ENGINE_CONTAINER}:/tmp/swing_demo_thumb.jpg" "$TMP_DIR/swing_demo_thumb.jpg"
docker cp "$TMP_DIR/swing_demo.mp4"       "${MINIO_CONTAINER}:/tmp/swing_demo.mp4"
docker cp "$TMP_DIR/swing_demo_thumb.jpg" "${MINIO_CONTAINER}:/tmp/swing_demo_thumb.jpg"

# 3. 上传到 bucket（带正确 content-type）
echo "==> [3/3] mc cp to bucket"
docker exec "$MINIO_CONTAINER" mc cp --attr "content-type=video/mp4" \
  /tmp/swing_demo.mp4 "local/${MINIO_BUCKET}/${VIDEO_KEY}"
docker exec "$MINIO_CONTAINER" mc cp --attr "content-type=image/jpeg" \
  /tmp/swing_demo_thumb.jpg "local/${MINIO_BUCKET}/${THUMB_KEY}"

echo "==> verify"
docker exec "$MINIO_CONTAINER" mc ls "local/${MINIO_BUCKET}/samples/"

echo "==> done"
echo "    HEAD: curl -sI \${API_PUBLIC_BASE_URL}/v1/assets/video/${VIDEO_KEY}"
echo "    HEAD: curl -sI \${API_PUBLIC_BASE_URL}/v1/assets/image/${THUMB_KEY}"
