#!/usr/bin/env bash
# W24-A · 查看 ai_engine 当前 V2 灰度比例与健康状态。
#
#   bash scripts/v2_rollout_status.sh
#   DEPLOY_HOST=ubuntu@1.13.198.172 bash scripts/v2_rollout_status.sh
set -euo pipefail

ENGINE_URL="${ENGINE_URL:-http://127.0.0.1:9100}"
DEPLOY_HOST="${DEPLOY_HOST:-}"
BIRDIE_CVM_KEY="${BIRDIE_CVM_KEY:-$HOME/.ssh/id_ed25519_birdie_golf}"

fetch_health() {
  curl -fsS "${ENGINE_URL}/health"
}

if [[ -n "${DEPLOY_HOST}" ]]; then
  SSH_OPTS=(-o StrictHostKeyChecking=accept-new)
  if [[ -f "${BIRDIE_CVM_KEY}" ]]; then
    SSH_OPTS+=(-i "${BIRDIE_CVM_KEY}" -o IdentitiesOnly=yes)
  fi
  echo "→ ${DEPLOY_HOST} ai_engine /health"
  ssh "${SSH_OPTS[@]}" "${DEPLOY_HOST}" "curl -fsS http://127.0.0.1:9100/health" | python3 -m json.tool
else
  fetch_health | python3 -m json.tool
fi
