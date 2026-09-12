#!/usr/bin/env bash
# PP-08：上传「已对齐」示范片到 CVM MinIO（不走 Mixkit）。
#
# 用法：
#   bash scripts/drill-demo-videos/upload-aligned.sh /path/to/clips
#
# 目录内文件名必须是：
#   drill_weight_shift.mp4
#   drill_hip_rotation.mp4
#   drill_towel_arm.mp4
#   （可选）drill_alignment_stick.mp4 / drill_half_swing.mp4
#   （可选）同名 _thumb.jpg；缺省则远端 ffmpeg 截第 0.5s
#
# 上传后**不会**自动改 DRILL_VIDEO_ALIGNED_IDS。产品看过画面与步骤一致后，
# 再把对应 id 写入 client/src/constants/drillVideoLibrary.ts。
#
# 禁止：对本脚本喂 Mixkit 旧缓存；禁止把未对齐 id 上传后加白名单。
set -euo pipefail

SRC_DIR="${1:-}"
if [[ -z "${SRC_DIR}" || ! -d "${SRC_DIR}" ]]; then
  echo "用法: $0 <本地成片目录>" >&2
  exit 2
fi

BUCKET="${MINIO_BUCKET:-xiaoniao-videos-test}"
DEPLOY_HOST="${DEPLOY_HOST:-ubuntu@1.13.198.172}"
SSH_KEY="${DEPLOY_SSH_KEY:-$HOME/.ssh/id_ed25519_birdie_golf}"
ENGINE="${DRILL_FFMPEG_CONTAINER:-xiaoniao-ai-engine}"
MINIO="${DRILL_MINIO_CONTAINER:-xiaoniao-minio}"

ALLOWED=(
  drill_weight_shift
  drill_hip_rotation
  drill_towel_arm
  drill_alignment_stick
  drill_half_swing
)

is_allowed() {
  local id="$1"
  local x
  for x in "${ALLOWED[@]}"; do
    [[ "${x}" == "${id}" ]] && return 0
  done
  return 1
}

say() { printf "\033[1;36m[pp08-upload]\033[0m %s\n" "$*"; }

uploaded=()
shopt -s nullglob
for mp4 in "${SRC_DIR}"/drill_*.mp4; do
  drill_id="$(basename "${mp4}" .mp4)"
  if ! is_allowed "${drill_id}"; then
    echo "拒绝非 PP-08 清单: ${drill_id}" >&2
    exit 1
  fi

  remote_mp4="/tmp/pp08-${drill_id}.mp4"
  remote_jpg="/tmp/pp08-${drill_id}_thumb.jpg"
  local_jpg="${SRC_DIR}/${drill_id}_thumb.jpg"

  say "上传 ${drill_id} → MinIO ${BUCKET}/samples/drills/"
  scp -i "${SSH_KEY}" -o StrictHostKeyChecking=accept-new \
    "${mp4}" "${DEPLOY_HOST}:${remote_mp4}"

  if [[ -s "${local_jpg}" ]]; then
    scp -i "${SSH_KEY}" -o StrictHostKeyChecking=accept-new \
      "${local_jpg}" "${DEPLOY_HOST}:${remote_jpg}"
  fi

  ssh -i "${SSH_KEY}" "${DEPLOY_HOST}" bash -s <<EOF
set -euo pipefail
drill_id="${drill_id}"
bucket="${BUCKET}"
engine="${ENGINE}"
minio="${MINIO}"
src_mp4="${remote_mp4}"
src_jpg="${remote_jpg}"
if [[ ! -s "\${src_jpg}" ]]; then
  docker cp "\${src_mp4}" "\${engine}:/tmp/\${drill_id}_v.mp4"
  docker exec "\${engine}" ffmpeg -y -loglevel error -ss 0.5 -i "/tmp/\${drill_id}_v.mp4" -vframes 1 -q:v 3 "/tmp/\${drill_id}_t.jpg"
  docker cp "\${engine}:/tmp/\${drill_id}_t.jpg" "\${src_jpg}"
  docker exec "\${engine}" rm -f "/tmp/\${drill_id}_v.mp4" "/tmp/\${drill_id}_t.jpg"
fi
docker cp "\${src_mp4}" "\${minio}:/tmp/\${drill_id}.mp4"
docker cp "\${src_jpg}" "\${minio}:/tmp/\${drill_id}_thumb.jpg"
docker exec "\${minio}" mc cp "/tmp/\${drill_id}.mp4" "local/\${bucket}/samples/drills/\${drill_id}.mp4"
docker exec "\${minio}" mc cp "/tmp/\${drill_id}_thumb.jpg" "local/\${bucket}/samples/drills/\${drill_id}_thumb.jpg"
docker exec "\${minio}" rm -f "/tmp/\${drill_id}.mp4" "/tmp/\${drill_id}_thumb.jpg"
rm -f "\${src_mp4}" "\${src_jpg}"
echo "ok \${drill_id}"
EOF
  uploaded+=("${drill_id}")
done

if [[ ${#uploaded[@]} -eq 0 ]]; then
  echo "目录里没有 drill_*.mp4" >&2
  exit 1
fi

say "已上传: ${uploaded[*]}"
say "下一步：产品确认画面后，把这些 id 写入 DRILL_VIDEO_ALIGNED_IDS（当前必须保持为空）"
