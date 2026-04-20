#!/usr/bin/env bash
# ai_engine/tests/fixtures/generate_synthetic.sh
# ------------------------------------------------------------------
# 生成 W6-T1 质量门失败分支测试用的合成视频。
# 运行前置：ffmpeg 在 PATH 里（macOS: `brew install ffmpeg`；Linux: `apt install ffmpeg`）。
# ------------------------------------------------------------------
set -euo pipefail

HERE="$(cd "$(dirname "$0")" && pwd)"
OUT_DIR="${HERE}/synthetic"
mkdir -p "${OUT_DIR}"

say() { printf "\n\033[1;36m[synth]\033[0m %s\n" "$*"; }

# ----------------------------------------
# 1. 纯黑视频：3s / 720x1280 / 30fps
#    触发 PoorQualityError (50102)：清晰度拉普拉斯方差接近 0
# ----------------------------------------
say "生成 blackscreen.mp4（纯黑 3 秒）"
ffmpeg -hide_banner -loglevel error -y \
  -f lavfi -i color=c=black:s=720x1280:r=30 \
  -t 3 \
  -c:v libx264 -pix_fmt yuv420p \
  "${OUT_DIR}/blackscreen.mp4"

# ----------------------------------------
# 2. 纯噪声：3s / 720x1280 / 30fps
#    另一种画质异常场景（clarity 偏高但 stability 差）
# ----------------------------------------
say "生成 noise.mp4（随机噪声 3 秒）"
ffmpeg -hide_banner -loglevel error -y \
  -f lavfi -i "nullsrc=s=720x1280:r=30,geq=random(1)*255:128:128" \
  -t 3 \
  -c:v libx264 -pix_fmt yuv420p \
  "${OUT_DIR}/noise.mp4"

# ----------------------------------------
# 3. 风景照静态转视频：3s / 720x1280 / 30fps
#    触发 NoPersonError (50103)：MediaPipe 全帧无检测
#    （用一张 ffmpeg 生成的渐变色色块代替，避免版权图片依赖）
# ----------------------------------------
say "生成 no_person.mp4（静态渐变 3 秒，无人物）"
ffmpeg -hide_banner -loglevel error -y \
  -f lavfi -i "gradients=size=720x1280:rate=30:duration=3:speed=0.01:c0=0x3366cc:c1=0x66aa55" \
  -t 3 \
  -c:v libx264 -pix_fmt yuv420p \
  "${OUT_DIR}/no_person.mp4"

# ----------------------------------------
# 4. 时长过短：1 秒
#    触发 PreprocessError：时长 < MIN_DURATION_SEC
# ----------------------------------------
say "生成 too_short.mp4（仅 1 秒）"
ffmpeg -hide_banner -loglevel error -y \
  -f lavfi -i color=c=gray:s=720x1280:r=30 \
  -t 1 \
  -c:v libx264 -pix_fmt yuv420p \
  "${OUT_DIR}/too_short.mp4"

# ----------------------------------------
# 5. 正常但简短的"活动色块"：3s
#    作为 sanity check 视频：preprocess 质量门通过，MediaPipe 检不到人
#    → 适合验证 pipeline 不会在"画质 OK 但无人物"的场景里崩
# ----------------------------------------
say "生成 bouncing_box.mp4（弹跳色块 3 秒，有动但无人）"
ffmpeg -hide_banner -loglevel error -y \
  -f lavfi -i "testsrc2=size=720x1280:rate=30:duration=3" \
  -t 3 \
  -c:v libx264 -pix_fmt yuv420p \
  "${OUT_DIR}/bouncing_box.mp4"

echo ""
printf "\033[1;32m✅ 合成视频生成完成：\033[0m\n"
ls -lh "${OUT_DIR}/"
