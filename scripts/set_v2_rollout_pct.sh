#!/usr/bin/env bash
# W24-A · 设置 ai_engine V2 灰度比例（Redis + 进程缓存；降级需 FORCE=1）。
#
# 用法：
#   # CVM 上（推荐，读 .env.local 里的 AI_ENGINE_ADMIN_TOKEN）
#   cd ~/lingniao-golf && PCT=25 bash scripts/set_v2_rollout_pct.sh
#
#   # 本机经 SSH
#   DEPLOY_HOST=ubuntu@1.13.198.172 PCT=25 bash scripts/set_v2_rollout_pct.sh
#
#   # 降级（5→0 等）
#   PCT=5 FORCE=1 bash scripts/set_v2_rollout_pct.sh
#
# 环境变量：
#   PCT          必填，0–100
#   FORCE        设为 1 允许 pct 下调
#   ENGINE_URL   默认 http://127.0.0.1:9100（CVM 宿主机映射 ai_engine）
#   AI_ENGINE_ADMIN_TOKEN  未设则从 .env.local 读取
#   DEPLOY_HOST  非空则经 ssh 在远端执行 curl
set -euo pipefail

PCT="${PCT:-}"
FORCE="${FORCE:-0}"
ENGINE_URL="${ENGINE_URL:-http://127.0.0.1:9100}"
DEPLOY_HOST="${DEPLOY_HOST:-}"
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
ENV_FILE="${ENV_FILE:-${REPO_ROOT}/.env.local}"

if [[ -z "${PCT}" ]]; then
  echo "用法: PCT=25 bash scripts/set_v2_rollout_pct.sh" >&2
  echo "  查看当前: bash scripts/v2_rollout_status.sh" >&2
  exit 1
fi

if ! [[ "${PCT}" =~ ^[0-9]+$ ]] || (( PCT < 0 || PCT > 100 )); then
  echo "✗ PCT 须为 0–100 整数" >&2
  exit 1
fi

if [[ -z "${AI_ENGINE_ADMIN_TOKEN:-}" && -f "${ENV_FILE}" ]]; then
  AI_ENGINE_ADMIN_TOKEN="$(grep -E '^AI_ENGINE_ADMIN_TOKEN=' "${ENV_FILE}" | head -1 | cut -d= -f2- | tr -d '\r"'"'"'' || true)"
  export AI_ENGINE_ADMIN_TOKEN
fi

if [[ -z "${AI_ENGINE_ADMIN_TOKEN:-}" ]]; then
  echo "✗ 请设置 AI_ENGINE_ADMIN_TOKEN 或在 ${ENV_FILE} 配置" >&2
  exit 1
fi

payload=$(printf '{"pct": %s, "force": %s}' "${PCT}" "$( [[ "${FORCE}" == "1" ]] && echo true || echo false )")

run_curl() {
  local url="$1"
  curl -fsS -X POST "${url}/admin/engine-rollout" \
    -H "Content-Type: application/json" \
    -H "X-Admin-Token: ${AI_ENGINE_ADMIN_TOKEN}" \
    -d "${payload}"
}

if [[ -n "${DEPLOY_HOST}" ]]; then
  BIRDIE_CVM_KEY="${BIRDIE_CVM_KEY:-$HOME/.ssh/id_ed25519_birdie_golf}"
  SSH_OPTS=(-o StrictHostKeyChecking=accept-new)
  if [[ -f "${BIRDIE_CVM_KEY}" ]]; then
    SSH_OPTS+=(-i "${BIRDIE_CVM_KEY}" -o IdentitiesOnly=yes)
  fi
  echo "→ 经 SSH ${DEPLOY_HOST} 设置 V2 rollout → ${PCT}%"
  ssh "${SSH_OPTS[@]}" "${DEPLOY_HOST}" \
    "curl -fsS -X POST http://127.0.0.1:9100/admin/engine-rollout \
      -H 'Content-Type: application/json' \
      -H 'X-Admin-Token: ${AI_ENGINE_ADMIN_TOKEN}' \
      -d '${payload}'" | python3 -m json.tool 2>/dev/null || true
else
  echo "→ 设置 V2 rollout → ${PCT}% (${ENGINE_URL})"
  run_curl "${ENGINE_URL}" | python3 -m json.tool 2>/dev/null || run_curl "${ENGINE_URL}"
fi

echo ""
echo "验证: bash scripts/v2_rollout_status.sh"
