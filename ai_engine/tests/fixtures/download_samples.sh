#!/usr/bin/env bash
# ai_engine/tests/fixtures/download_samples.sh
# ------------------------------------------------------------------
# 下载真实挥杆视频到 fixtures/real/ 供 T1-T3 集成测试使用。
# 用法：
#   bash download_samples.sh golfdb     # 从 GolfDB 下载 1-2 段样本（推荐）
#   bash download_samples.sh pexels     # 从 Pexels 下载（CC0，1 段）
#   bash download_samples.sh manual     # 打印手动下载指引
# ------------------------------------------------------------------
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
REAL_DIR="${HERE}/real"
mkdir -p "${REAL_DIR}"

SOURCE="${1:-manual}"

say() { printf "\n\033[1;36m[download]\033[0m %s\n" "$*"; }
warn() { printf "\n\033[1;33m[warn]\033[0m %s\n" "$*" >&2; }

require() {
  if ! command -v "$1" >/dev/null 2>&1; then
    warn "缺少工具：$1，请先安装"
    exit 2
  fi
}

case "${SOURCE}" in
  golfdb)
    # GolfDB: CVPR 2019 Workshop 公开数据集
    # https://github.com/wmcnally/golfdb
    #
    # 注意：
    # - GolfDB 的完整视频包（videos_160.tar.gz）约 700MB，通过 Google Drive 分发
    # - 本脚本只拉几段样本，完整数据集请手动去 GitHub Release 下载
    # - 样本视频版权归原 YouTube 频道所有，GolfDB 仅做学术研究分发
    say "GolfDB 样本视频需要手动从 Google Drive 下载"
    cat <<'EOF'

      1) 访问 https://github.com/wmcnally/golfdb
      2) 点击 "Download Video Database" → Google Drive 链接
      3) 下载 videos_160.tar.gz 或 videos_160_samples.tar.gz（样本包）
      4) 解压后把 1-3 段 *.mp4 放到 fixtures/real/，重命名为：
         - face_on_iron_01.mp4
         - face_on_driver_01.mp4
         - dtl_iron_01.mp4（down-the-line 视角）

    由于 Google Drive 的反爬限制，脚本化下载不稳定；建议手动 3 分钟搞定。

EOF
    ;;

  pexels)
    # Pexels CC0 视频（免版权）；这里用一段高尔夫相关视频作为占位
    # 注意：脚本里的 URL 是示例，真实使用时需要去 pexels.com 搜 "golf swing" 挑一段
    require curl
    warn "Pexels 默认无直接挥杆素材；请访问 https://www.pexels.com/search/videos/golf%20swing/ 手动挑 1-2 段"
    warn "下载后重命名为 real/face_on_iron_01.mp4 即可"
    ;;

  manual|*)
    cat <<'EOF'

      获取 fixture 视频的 3 种路径：

      [A] GolfDB 公开数据集（推荐）
          https://github.com/wmcnally/golfdb
          - 390 段 160×160 挥杆 + 8 关键事件帧标注
          - Google Drive 手动下载，5 分钟搞定

      [B] YouTube 教学视频（yt-dlp + ffmpeg 剪辑）
          yt-dlp -f "best[height<=1080]" "https://www.youtube.com/watch?v=XXX" -o tmp.mp4
          ffmpeg -ss 00:01:23 -t 3 -i tmp.mp4 -c copy real/face_on_iron_01.mp4
          推荐频道：Me and My Golf / Rick Shiels / TXG

      [C] 自录（iPhone / Android）
          练习场 1080p 60fps 录 3-5 秒挥杆，face-on 视角

      下载/录制后放到：fixtures/real/
      建议文件名：
        - face_on_iron_01.mp4
        - face_on_driver_01.mp4
        - dtl_iron_01.mp4

      注意：real/*.mp4 已在根目录 .gitignore 里屏蔽，不会被 git 误 track。

EOF
    ;;
esac

if [[ -n "$(ls -A "${REAL_DIR}" 2>/dev/null)" ]]; then
  printf "\n\033[1;32m现有 real/ 视频：\033[0m\n"
  ls -lh "${REAL_DIR}/"
else
  warn "real/ 目录仍为空；按上面指引手动 drop 视频后再跑集成测试"
fi
