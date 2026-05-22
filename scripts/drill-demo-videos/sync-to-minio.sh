#!/usr/bin/env bash
# 下载 Mixkit 免版权高尔夫素材 → 生成封面 → 上传 CVM MinIO samples/drills/
#
# 用法：
#   bash scripts/drill-demo-videos/sync-to-minio.sh              # 本地下载 MP4（缓存 .cache/）
#   bash scripts/drill-demo-videos/sync-to-minio.sh --upload     # scp + 远端 ffmpeg 封面 + mc 写入 MinIO
#   bash scripts/drill-demo-videos/sync-to-minio.sh --remote     # 直接在 CVM 下载并写入 MinIO（推荐）
#
# 依赖：curl、python3；封面需 ffmpeg（--upload 在 CVM 上执行，--remote 亦同）
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
CACHE="${HERE}/.cache"
MANIFEST="${HERE}/manifest.json"
BUCKET="${MINIO_BUCKET:-xiaoniao-videos-test}"
DEPLOY_HOST="${DEPLOY_HOST:-ubuntu@1.13.198.172}"
SSH_KEY="${DEPLOY_SSH_KEY:-$HOME/.ssh/id_ed25519_birdie_golf}"
MODE="${1:-download}"

require() {
  command -v "$1" >/dev/null 2>&1 || {
    echo "缺少依赖: $1" >&2
    exit 2
  }
}

require curl
require python3

mkdir -p "${CACHE}"

mixkit_url() {
  local mixkit_id="$1"
  local resolution="$2"
  printf 'https://assets.mixkit.co/videos/%s/%s-%s.mp4' "${mixkit_id}" "${mixkit_id}" "${resolution}"
}

say() { printf "\033[1;36m[drill-videos]\033[0m %s\n" "$*"; }

read_manifest_rows() {
  python3 - "${MANIFEST}" <<'PY'
import json, sys
for item in json.load(open(sys.argv[1], encoding="utf-8"))["items"]:
    print(f"{item['drill_id']}\t{item['mixkit_id']}\t{item['resolution']}")
PY
}

download_item() {
  local drill_id="$1" mixkit_id="$2" resolution="$3"
  local out_mp4="${CACHE}/${drill_id}.mp4"
  local url
  url="$(mixkit_url "${mixkit_id}" "${resolution}")"

  if [[ -s "${out_mp4}" ]]; then
    say "跳过下载（已缓存）${drill_id}"
    return 0
  fi

  say "下载 ${drill_id} ← Mixkit #${mixkit_id} (${resolution}p)"
  curl -fsSL "${url}" -o "${out_mp4}.part"
  mv "${out_mp4}.part" "${out_mp4}"
}

upload_item() {
  local drill_id="$1"
  local out_mp4="${CACHE}/${drill_id}.mp4"
  local remote_mp4="/tmp/drill-upload-${drill_id}.mp4"
  local remote_jpg="/tmp/drill-upload-${drill_id}_thumb.jpg"

  if [[ ! -s "${out_mp4}" ]]; then
    echo "缺少本地文件: ${out_mp4}，请先运行无参下载" >&2
    exit 1
  fi

  say "上传 ${drill_id} → MinIO ${BUCKET}/samples/drills/"
  scp -i "${SSH_KEY}" -o StrictHostKeyChecking=accept-new \
    "${out_mp4}" "${DEPLOY_HOST}:${remote_mp4}"

  ssh -i "${SSH_KEY}" "${DEPLOY_HOST}" bash -s <<EOF
set -euo pipefail
docker cp "${remote_mp4}" xiaoniao-ai-engine:/tmp/${drill_id}.mp4
docker exec xiaoniao-ai-engine ffmpeg -y -loglevel error -ss 0.5 -i /tmp/${drill_id}.mp4 -vframes 1 -q:v 3 /tmp/${drill_id}_thumb.jpg
docker cp xiaoniao-ai-engine:/tmp/${drill_id}_thumb.jpg "${remote_jpg}"
docker exec xiaoniao-ai-engine rm -f /tmp/${drill_id}.mp4 /tmp/${drill_id}_thumb.jpg
docker cp "${remote_mp4}" xiaoniao-minio:/tmp/${drill_id}.mp4
docker cp "${remote_jpg}" xiaoniao-minio:/tmp/${drill_id}_thumb.jpg
docker exec xiaoniao-minio mc cp /tmp/${drill_id}.mp4 "local/${BUCKET}/samples/drills/${drill_id}.mp4"
docker exec xiaoniao-minio mc cp /tmp/${drill_id}_thumb.jpg "local/${BUCKET}/samples/drills/${drill_id}_thumb.jpg"
docker exec xiaoniao-minio rm -f /tmp/${drill_id}.mp4 /tmp/${drill_id}_thumb.jpg
rm -f "${remote_mp4}" "${remote_jpg}"
EOF
}

remote_sync_all() {
  say "在 ${DEPLOY_HOST} 上直接下载并写入 MinIO"
  scp -i "${SSH_KEY}" -o StrictHostKeyChecking=accept-new \
    "${MANIFEST}" "${DEPLOY_HOST}:/tmp/drill-demo-manifest.json"

  ssh -i "${SSH_KEY}" "${DEPLOY_HOST}" bash -s <<EOF
set -euo pipefail
export BUCKET="${BUCKET}"
MANIFEST="/tmp/drill-demo-manifest.json"
WORKDIR="/tmp/drill-demo-sync"
mkdir -p "\${WORKDIR}"
python3 - "\${MANIFEST}" <<'PY'
import json, subprocess, sys, os
manifest = json.load(open(sys.argv[1], encoding="utf-8"))
bucket = os.environ["BUCKET"]
engine = "xiaoniao-ai-engine"
minio = "xiaoniao-minio"
for item in manifest["items"]:
    drill_id = item["drill_id"]
    mixkit_id = item["mixkit_id"]
    res = item["resolution"]
    url = f"https://assets.mixkit.co/videos/{mixkit_id}/{mixkit_id}-{res}.mp4"
    mp4 = f"/tmp/drill-demo-sync/{drill_id}.mp4"
    jpg = f"/tmp/drill-demo-sync/{drill_id}_thumb.jpg"
    in_mp4 = f"/tmp/{drill_id}.mp4"
    in_jpg = f"/tmp/{drill_id}_thumb.jpg"
    subprocess.check_call(["curl", "-fsSL", url, "-o", mp4])
    subprocess.check_call(["docker", "cp", mp4, f"{engine}:{in_mp4}"])
    subprocess.check_call([
        "docker", "exec", engine, "ffmpeg", "-y", "-loglevel", "error",
        "-ss", "0.5", "-i", in_mp4, "-vframes", "1", "-q:v", "3", in_jpg,
    ])
    subprocess.check_call(["docker", "cp", f"{engine}:{in_jpg}", jpg])
    subprocess.check_call(["docker", "cp", mp4, f"{minio}:/tmp/{drill_id}.mp4"])
    subprocess.check_call(["docker", "cp", jpg, f"{minio}:/tmp/{drill_id}_thumb.jpg"])
    subprocess.check_call([
        "docker", "exec", minio, "mc", "cp", f"/tmp/{drill_id}.mp4",
        f"local/{bucket}/samples/drills/{drill_id}.mp4",
    ])
    subprocess.check_call([
        "docker", "exec", minio, "mc", "cp", f"/tmp/{drill_id}_thumb.jpg",
        f"local/{bucket}/samples/drills/{drill_id}_thumb.jpg",
    ])
    subprocess.check_call([
        "docker", "exec", minio, "rm", "-f",
        f"/tmp/{drill_id}.mp4", f"/tmp/{drill_id}_thumb.jpg",
    ])
    subprocess.check_call(["docker", "exec", engine, "rm", "-f", in_mp4, in_jpg])
    print(f"ok {drill_id}")
PY
rm -f "\${MANIFEST}"
EOF
}

case "${MODE}" in
  --upload)
    while IFS=$'\t' read -r drill_id mixkit_id resolution; do
      [[ -z "${drill_id}" ]] && continue
      download_item "${drill_id}" "${mixkit_id}" "${resolution}"
    done < <(read_manifest_rows)
    while IFS=$'\t' read -r drill_id _ _; do
      [[ -z "${drill_id}" ]] && continue
      upload_item "${drill_id}"
    done < <(read_manifest_rows)
    say "全部上传完成"
    ;;
  --remote)
    remote_sync_all
    say "远端同步完成"
    ;;
  *)
    while IFS=$'\t' read -r drill_id mixkit_id resolution; do
      [[ -z "${drill_id}" ]] && continue
      download_item "${drill_id}" "${mixkit_id}" "${resolution}"
    done < <(read_manifest_rows)
    say "本地 MP4 缓存于 ${CACHE}；推荐: bash $0 --remote"
    ;;
esac
