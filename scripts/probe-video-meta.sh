#!/usr/bin/env bash
# APP-SP-1：用 ffprobe 读取视频分辨率 / 帧率 / 时长 / 体积，便于填 kickoff 结果表。
# 依赖：ffmpeg 套件中的 ffprobe（macOS: brew install ffmpeg）
#
# 用法：
#   bash scripts/probe-video-meta.sh /path/to/swing.mov
#   bash scripts/probe-video-meta.sh a.mp4 b.mov
set -euo pipefail

if ! command -v ffprobe >/dev/null 2>&1; then
  echo "✗ 未找到 ffprobe。请先安装：brew install ffmpeg" >&2
  exit 1
fi

if [[ $# -lt 1 ]]; then
  echo "用法: $0 <video> [video...]" >&2
  exit 1
fi

probe_one() {
  local f="$1"
  if [[ ! -f "$f" ]]; then
    echo "✗ 文件不存在: $f" >&2
    return 1
  fi

  local json
  json="$(ffprobe -v error -select_streams v:0 \
    -show_entries stream=width,height,r_frame_rate,avg_frame_rate,duration,codec_name,nb_frames \
    -show_entries format=size,duration \
    -of json "$f")"

  PATH_ARG="$f" JSON_ARG="$json" python3 - <<'PY'
import json, os, fractions

path = os.environ["PATH_ARG"]
data = json.loads(os.environ["JSON_ARG"])
stream = (data.get("streams") or [{}])[0]
fmt = data.get("format") or {}

def fps_of(rate: str) -> str:
    if not rate or rate in ("0/0", "N/A"):
        return "?"
    try:
        return f"{float(fractions.Fraction(rate)):.3f}".rstrip("0").rstrip(".")
    except Exception:
        return rate

w = stream.get("width") or "?"
h = stream.get("height") or "?"
r_fps = fps_of(str(stream.get("r_frame_rate") or ""))
a_fps = fps_of(str(stream.get("avg_frame_rate") or ""))
dur = stream.get("duration") or fmt.get("duration") or "?"
try:
    dur_s = f"{float(dur):.2f}s"
except Exception:
    dur_s = str(dur)
size = fmt.get("size")
try:
    size_mb = f"{int(size) / (1024 * 1024):.2f}MB" if size is not None else "?"
except Exception:
    size_mb = "?"
codec = stream.get("codec_name") or "?"
nb = stream.get("nb_frames") or "?"

print("──", path)
print(f"  分辨率     {w}×{h}")
print(f"  r_frame    {r_fps} fps  (容器标称)")
print(f"  avg_frame  {a_fps} fps  (平均，优先记入结果表「实测」)")
print(f"  时长       {dur_s}")
print(f"  体积       {size_mb}")
print(f"  编码       {codec}  frames={nb}")
print()
print("结果表粘贴建议：")
print(f"  | … | {w}×{h} | 标称 {r_fps} / 实测 {a_fps} | {size_mb}（{dur_s}） |  |  |")
print()
PY
}

echo "APP-SP-1 video probe"
echo
for f in "$@"; do
  probe_one "$f" || true
done
