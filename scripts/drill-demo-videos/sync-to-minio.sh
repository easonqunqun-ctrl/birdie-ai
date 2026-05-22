#!/usr/bin/env bash
# 下载 Mixkit 免版权高尔夫素材 → 转码（720p / faststart / ≤15s）→ 上传 CVM MinIO samples/drills/
#
# 用法：
#   bash scripts/drill-demo-videos/sync-to-minio.sh              # 本地下载 MP4（缓存 .cache/）
#   bash scripts/drill-demo-videos/sync-to-minio.sh --upload     # scp + 远端转码 + mc 写入 MinIO
#   bash scripts/drill-demo-videos/sync-to-minio.sh --remote     # CVM 下载 + 转码 + 写入 MinIO
#   bash scripts/drill-demo-videos/sync-to-minio.sh --recompress # 仅对 MinIO 已有 MP4 重新转码（修卡顿）
#
# 依赖：curl、python3；转码/封面需 CVM 上 xiaoniao-ai-engine（ffmpeg）
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
CACHE="${HERE}/.cache"
MANIFEST="${HERE}/manifest.json"
BUCKET="${MINIO_BUCKET:-xiaoniao-videos-test}"
DEPLOY_HOST="${DEPLOY_HOST:-ubuntu@1.13.198.172}"
SSH_KEY="${DEPLOY_SSH_KEY:-$HOME/.ssh/id_ed25519_birdie_golf}"
ENGINE="${DRILL_FFMPEG_CONTAINER:-xiaoniao-ai-engine}"
MINIO="${DRILL_MINIO_CONTAINER:-xiaoniao-minio}"
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

read_manifest_ids() {
  python3 - "${MANIFEST}" <<'PY'
import json, sys
for item in json.load(open(sys.argv[1], encoding="utf-8"))["items"]:
    print(item["drill_id"])
PY
}

remote_python() {
  scp -i "${SSH_KEY}" -o StrictHostKeyChecking=accept-new \
    "${MANIFEST}" "${DEPLOY_HOST}:/tmp/drill-demo-manifest.json" >/dev/null
  ssh -i "${SSH_KEY}" "${DEPLOY_HOST}" \
    BUCKET="${BUCKET}" ENGINE="${ENGINE}" MINIO="${MINIO}" DRILL_SYNC_MODE="${MODE}" \
    bash -s <<'REMOTE'
set -euo pipefail
WORKDIR="/tmp/drill-demo-sync"
mkdir -p "${WORKDIR}"
MANIFEST="/tmp/drill-demo-manifest.json"

python3 - "${MANIFEST}" <<'PY'
import json, os, subprocess, sys

manifest_path = sys.argv[1]
mode = os.environ["DRILL_SYNC_MODE"]
bucket = os.environ["BUCKET"]
engine = os.environ["ENGINE"]
minio = os.environ["MINIO"]
workdir = "/tmp/drill-demo-sync"
manifest = json.load(open(manifest_path, encoding="utf-8"))

SCALE = "scale='min(720,iw)':-2"
FFMPEG_ARGS = [
    "-t", "15",
    "-vf", SCALE,
    "-c:v", "libx264", "-profile:v", "main", "-pix_fmt", "yuv420p",
    "-crf", "20", "-preset", "fast",
    "-maxrate", "2500k", "-bufsize", "5000k",
    "-movflags", "+faststart",
    "-an",
]


def transcode_on_engine(host_src: str, host_dst: str, tag: str) -> None:
    in_c = f"/tmp/{tag}_in.mp4"
    out_c = f"/tmp/{tag}_out.mp4"
    subprocess.check_call(["docker", "cp", host_src, f"{engine}:{in_c}"])
    subprocess.check_call(["docker", "exec", engine, "ffmpeg", "-y", "-loglevel", "error", "-i", in_c, *FFMPEG_ARGS, out_c])
    subprocess.check_call(["docker", "cp", f"{engine}:{out_c}", host_dst])
    subprocess.check_call(["docker", "exec", engine, "rm", "-f", in_c, out_c])


def thumb_from_video(host_mp4: str, host_jpg: str, tag: str) -> None:
    in_c = f"/tmp/{tag}_v.mp4"
    out_c = f"/tmp/{tag}_t.jpg"
    subprocess.check_call(["docker", "cp", host_mp4, f"{engine}:{in_c}"])
    subprocess.check_call([
        "docker", "exec", engine, "ffmpeg", "-y", "-loglevel", "error",
        "-ss", "0.5", "-i", in_c, "-vframes", "1", "-q:v", "3", out_c,
    ])
    subprocess.check_call(["docker", "cp", f"{engine}:{out_c}", host_jpg])
    subprocess.check_call(["docker", "exec", engine, "rm", "-f", in_c, out_c])


def upload_pair(drill_id: str, host_mp4: str, host_jpg: str) -> None:
    subprocess.check_call(["docker", "cp", host_mp4, f"{minio}:/tmp/{drill_id}.mp4"])
    subprocess.check_call(["docker", "cp", host_jpg, f"{minio}:/tmp/{drill_id}_thumb.jpg"])
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


def process_item(item: dict, source: str) -> None:
    drill_id = item["drill_id"]
    raw_mp4 = f"{workdir}/{drill_id}_raw.mp4"
    out_mp4 = f"{workdir}/{drill_id}.mp4"
    out_jpg = f"{workdir}/{drill_id}_thumb.jpg"

    if source == "mixkit":
        mixkit_id = item["mixkit_id"]
        res = item["resolution"]
        url = f"https://assets.mixkit.co/videos/{mixkit_id}/{mixkit_id}-{res}.mp4"
        subprocess.check_call(["curl", "-fsSL", url, "-o", raw_mp4])
    else:
        subprocess.check_call([
            "docker", "exec", minio, "mc", "cp",
            f"local/{bucket}/samples/drills/{drill_id}.mp4",
            f"/tmp/{drill_id}_pull.mp4",
        ])
        subprocess.check_call(["docker", "cp", f"{minio}:/tmp/{drill_id}_pull.mp4", raw_mp4])
        subprocess.check_call(["docker", "exec", minio, "rm", "-f", f"/tmp/{drill_id}_pull.mp4"])

    transcode_on_engine(raw_mp4, out_mp4, drill_id)
    thumb_from_video(out_mp4, out_jpg, f"{drill_id}_thumb")
    upload_pair(drill_id, out_mp4, out_jpg)
    print(f"ok {drill_id} {os.path.getsize(out_mp4) // 1024}KiB")


source = "minio" if mode == "--recompress" else "mixkit"
for item in manifest["items"]:
    process_item(item, source)
PY
rm -f "${MANIFEST}"
REMOTE
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

  if [[ ! -s "${out_mp4}" ]]; then
    echo "缺少本地文件: ${out_mp4}，请先运行无参下载" >&2
    exit 1
  fi

  say "上传 ${drill_id}（远端转码）→ MinIO ${BUCKET}/samples/drills/"
  scp -i "${SSH_KEY}" -o StrictHostKeyChecking=accept-new \
    "${out_mp4}" "${DEPLOY_HOST}:${remote_mp4}"

  ssh -i "${SSH_KEY}" "${DEPLOY_HOST}" bash -s <<EOF
set -euo pipefail
WORKDIR="/tmp/drill-demo-sync"
mkdir -p "\${WORKDIR}"
cp "${remote_mp4}" "\${WORKDIR}/${drill_id}_raw.mp4"
python3 - <<'PY'
import json, os, subprocess
drill_id = "${drill_id}"
bucket = "${BUCKET}"
engine = "${ENGINE}"
minio = "${MINIO}"
workdir = "/tmp/drill-demo-sync"
raw = f"{workdir}/{drill_id}_raw.mp4"
out = f"{workdir}/{drill_id}.mp4"
jpg = f"{workdir}/{drill_id}_thumb.jpg"
tag = drill_id
scale = "scale='min(720,iw)':-2"
args = ["-t","15","-vf",scale,"-c:v","libx264","-profile:v","main","-pix_fmt","yuv420p","-crf","20","-preset","fast","-maxrate","2500k","-bufsize","5000k","-movflags","+faststart","-an"]
in_c = f"/tmp/{tag}_in.mp4"
out_c = f"/tmp/{tag}_out.mp4"
subprocess.check_call(["docker","cp",raw,f"{engine}:{in_c}"])
subprocess.check_call(["docker","exec",engine,"ffmpeg","-y","-loglevel","error","-i",in_c,*args,out_c])
subprocess.check_call(["docker","cp",f"{engine}:{out_c}",out])
subprocess.check_call(["docker","exec",engine,"rm","-f",in_c,out_c])
in_v = f"/tmp/{tag}_v.mp4"
out_t = f"/tmp/{tag}_t.jpg"
subprocess.check_call(["docker","cp",out,f"{engine}:{in_v}"])
subprocess.check_call(["docker","exec",engine,"ffmpeg","-y","-loglevel","error","-ss","0.5","-i",in_v,"-vframes","1","-q:v","3",out_t])
subprocess.check_call(["docker","cp",f"{engine}:{out_t}",jpg])
subprocess.check_call(["docker","exec",engine,"rm","-f",in_v,out_t])
subprocess.check_call(["docker","cp",out,f"{minio}:/tmp/{drill_id}.mp4"])
subprocess.check_call(["docker","cp",jpg,f"{minio}:/tmp/{drill_id}_thumb.jpg"])
subprocess.check_call(["docker","exec",minio,"mc","cp",f"/tmp/{drill_id}.mp4",f"local/{bucket}/samples/drills/{drill_id}.mp4"])
subprocess.check_call(["docker","exec",minio,"mc","cp",f"/tmp/{drill_id}_thumb.jpg",f"local/{bucket}/samples/drills/{drill_id}_thumb.jpg"])
subprocess.check_call(["docker","exec",minio,"rm","-f",f"/tmp/{drill_id}.mp4",f"/tmp/{drill_id}_thumb.jpg"])
print(f"ok {drill_id} {os.path.getsize(out)//1024}KiB")
PY
rm -f "${remote_mp4}"
EOF
}

case "${MODE}" in
  --upload)
    while IFS=$'\t' read -r drill_id mixkit_id resolution; do
      [[ -z "${drill_id}" ]] && continue
      download_item "${drill_id}" "${mixkit_id}" "${resolution}"
    done < <(read_manifest_rows)
    while IFS= read -r drill_id; do
      [[ -z "${drill_id}" ]] && continue
      upload_item "${drill_id}"
    done < <(read_manifest_ids)
    say "全部上传完成"
    ;;
  --remote | --recompress)
    if [[ "${MODE}" == "--recompress" ]]; then
      say "重新转码 MinIO 已有示范片（720p / faststart / ≤15s）"
    else
      say "在 ${DEPLOY_HOST} 下载 + 转码 + 写入 MinIO"
    fi
    remote_python
    say "远端同步完成"
    ;;
  *)
    while IFS=$'\t' read -r drill_id mixkit_id resolution; do
      [[ -z "${drill_id}" ]] && continue
      download_item "${drill_id}" "${mixkit_id}" "${resolution}"
    done < <(read_manifest_rows)
    say "本地 MP4 缓存于 ${CACHE}；推荐: bash $0 --remote 或 --recompress"
    ;;
esac
