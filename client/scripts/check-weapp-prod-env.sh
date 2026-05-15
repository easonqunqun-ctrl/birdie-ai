#!/usr/bin/env bash
# 打正式小程序包前校验 client/.env.production 中的 API 域名，避免空手误传 localhost。
# CI 无法用本地 .env 时：SKIP_WEAPP_PROD_ENV_CHECK=1
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
CLIENT_DIR="$(cd "${SCRIPT_DIR}/.." && pwd)"
ENV_FILE="${CLIENT_DIR}/.env.production"
LOCAL_FILE="${CLIENT_DIR}/.env.production.local"

pick_api_line() {
  local f="$1"
  [[ -f "$f" ]] || return 0
  grep -E '^[[:space:]]*TARO_APP_API_BASE_URL=' "$f" | tail -1 || true
}

if [[ "${SKIP_WEAPP_PROD_ENV_CHECK:-}" == "1" ]]; then
  echo "[check-weapp-prod-env] SKIP_WEAPP_PROD_ENV_CHECK=1，跳过。"
  exit 0
fi

if [[ ! -f "${ENV_FILE}" ]]; then
  echo "[check-weapp-prod-env] ✗ 未找到 ${ENV_FILE}"
  exit 1
fi

# 先读 .env.production；若存在 .env.production.local 且其中有同名变量则用本地覆盖（不入库，适合本机发版）
raw="$(pick_api_line "${ENV_FILE}")"
if [[ -f "${LOCAL_FILE}" ]]; then
  local_raw="$(pick_api_line "${LOCAL_FILE}")"
  if [[ -n "${local_raw}" ]]; then
    raw="${local_raw}"
  fi
fi
val="${raw#*=}"
val="${val%$'\r'}"
val="${val//\"/}"
val="$(echo "${val}" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"

if [[ -z "${val}" ]]; then
  echo "[check-weapp-prod-env] ✗ TARO_APP_API_BASE_URL 为空。请编辑 client/.env.production（或本机 .env.production.local 覆盖）"
  echo "   参见 docs/release-notes/go-live-weapp-fool-checklist.md"
  exit 1
fi

if [[ "${val}" != https://* ]]; then
  echo "[check-weapp-prod-env] ✗ API 须为 https（当前: ${val}）"
  exit 1
fi

hl="$(echo "${val}" | awk '{print tolower($0)}')"
if [[ "${hl}" == *"localhost"* || "${hl}" == *"127.0.0.1"* ]]; then
  echo "[check-weapp-prod-env] ✗ 正式包禁止使用 localhost（当前: ${val}）"
  exit 1
fi

if [[ ! "${val}" =~ /v1/?$ ]]; then
  echo "[check-weapp-prod-env] ⚠️ 警告：惯例为 URL 以 /v1 结尾（当前: ${val}），请确认与后端路由前缀一致。"
fi

echo "[check-weapp-prod-env] ✓ TARO_APP_API_BASE_URL=${val}"
