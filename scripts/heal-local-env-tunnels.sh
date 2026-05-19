#!/usr/bin/env bash
# 将 .env.local 里过期的 cloudflared / trycloudflare 隧道 URL 自动改回 CVM 同源地址。
# 无需人工记隧道域名；发版前 preflight 会默认调用（见 make check-preflight）。
#
# 用法：
#   bash scripts/heal-local-env-tunnels.sh
#   ENV_FILE=~/secrets/lingniao-prod.env bash scripts/heal-local-env-tunnels.sh
#
# 仅当检测到 *.trycloudflare.com / *.ngrok* 时才改写；其它值不动。
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-${ENV:-${REPO_ROOT}/.env.local}}"
API_HOST="${HEAL_API_HOST:-api.birdieai.cn}"
API_BASE="https://${API_HOST}"
MINIO_PUB="${HEAL_MINIO_PUBLIC:-${API_BASE}/minio}"

yellow() { printf '\033[33m%s\033[0m\n' "$*"; }
green()  { printf '\033[32m%s\033[0m\n' "$*"; }

if [[ ! -f "${ENV_FILE}" ]]; then
  yellow "! 跳过 heal：未找到 ${ENV_FILE}"
  exit 0
fi

if ! grep -E 'trycloudflare\.com|ngrok-free\.app|ngrok\.io' "${ENV_FILE}" >/dev/null 2>&1; then
  green "✓ ${ENV_FILE} 无穿透隧道占位，无需 heal"
  exit 0
fi

bak="${ENV_FILE}.bak.$(date +%Y%m%d-%H%M%S)"
cp "${ENV_FILE}" "${bak}"
yellow "! 已备份 → ${bak}"

# macOS sed -i '' 兼容
sed_inplace() {
  if sed --version >/dev/null 2>&1; then
    sed -i "$@"
  else
    sed -i '' "$@"
  fi
}

replace_key() {
  local key="$1" val="$2"
  if grep -q "^${key}=" "${ENV_FILE}" 2>/dev/null; then
    sed_inplace "s|^${key}=.*|${key}=${val}|" "${ENV_FILE}"
  fi
}

replace_key API_PUBLIC_BASE_URL "${API_BASE}"
replace_key MINIO_PUBLIC_ENDPOINT "${MINIO_PUB}"
replace_key SAMPLE_VIDEO_URL "${MINIO_PUB}/xiaoniao-videos/samples/swing_demo.mp4"
replace_key SAMPLE_THUMBNAIL_URL "${MINIO_PUB}/xiaoniao-videos/samples/swing_demo_thumb.jpg"

green "✓ 已将 ${ENV_FILE} 中隧道 URL 对齐为 ${API_BASE}（MinIO 公网 ${MINIO_PUB}）"
