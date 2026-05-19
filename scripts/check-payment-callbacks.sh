#!/usr/bin/env bash
# 微信支付 / 退款回调路径自检：U-4 紧急队列对应（docs/19 §二）
#
# 校验 .env 中 WECHAT_PAY_NOTIFY_URL / WECHAT_PAY_REFUND_NOTIFY_URL 与
# backend/app/api/v1/payments.py 的实际路由完全一致：
#   - HTTPS
#   - 路径 /v1/payments/wechat/notify        ← @router.post('/wechat/notify')
#   - 路径 /v1/payments/wechat/refund-notify ← @router.post('/wechat/refund-notify')
#   - host 与同环境 client/.env.production 的 API host 同源（不强制，仅警告）
#
# 用法（仓库根）：
#   make check-pay-callbacks                      # 默认 ENV=.env.local
#   ENV=.env.production make check-pay-callbacks
#   ENV=$HOME/secrets/lingniao-prod.env make check-pay-callbacks
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

ENV_FILE="${ENV:-${ENV_FILE:-.env.local}}"
CLIENT_ENV="${CLIENT_ENV:-client/.env.production}"
CLIENT_ENV_LOCAL="${CLIENT_ENV_LOCAL:-client/.env.production.local}"

# 实际路由（与 backend/app/api/v1/payments.py 一一对应）
EXPECTED_NOTIFY_PATH="/v1/payments/wechat/notify"
EXPECTED_REFUND_PATH="/v1/payments/wechat/refund-notify"

red()   { printf '\033[31m%s\033[0m\n' "$*" >&2; }
green() { printf '\033[32m%s\033[0m\n' "$*"; }
yellow(){ printf '\033[33m%s\033[0m\n' "$*"; }
section(){ printf '\n\033[1m=== %s ===\033[0m\n' "$*"; }

extract_var() {
  local file="$1" key="$2"
  [[ -f "${file}" ]] || return 0
  awk -v k="${key}" -F= '
    /^[[:space:]]*#/ { next }
    $1 ~ "^[[:space:]]*"k"[[:space:]]*$" {
      sub(/^[^=]*=/, "", $0)
      gsub(/\r/, "", $0)
      gsub(/^[[:space:]]+|[[:space:]]+$/, "", $0)
      gsub(/^"|"$/, "", $0)
      print
    }
  ' "${file}" | tail -n 1
}

url_host() {
  local raw="${1:-}"
  [[ -z "${raw}" ]] && return 0
  raw="${raw#http://}"
  raw="${raw#https://}"
  raw="${raw%%/*}"
  raw="${raw%%:*}"
  echo "${raw}"
}

url_path() {
  local raw="${1:-}"
  [[ -z "${raw}" ]] && return 0
  local stripped="${raw#http://}"
  stripped="${stripped#https://}"
  if [[ "${stripped}" == *"/"* ]]; then
    echo "/${stripped#*/}"
  else
    echo "/"
  fi
}

if [[ ! -f "${ENV_FILE}" ]]; then
  red "✗ 找不到 ${ENV_FILE}"
  echo "  用法：ENV=.env.local make check-pay-callbacks"
  exit 1
fi

section "0) 输入"
echo "  ENV_FILE      = ${ENV_FILE}"
echo "  CLIENT_ENV    = ${CLIENT_ENV}"

notify_url=$(extract_var "${ENV_FILE}" WECHAT_PAY_NOTIFY_URL || true)
refund_url=$(extract_var "${ENV_FILE}" WECHAT_PAY_REFUND_NOTIFY_URL || true)
pay_mock=$(extract_var "${ENV_FILE}" WECHAT_PAY_MOCK_MODE || true)
papay_url=$(extract_var "${ENV_FILE}" WECHAT_PAY_PAPAY_NOTIFY_URL || true)
api_pub=$(extract_var "${ENV_FILE}" API_PUBLIC_BASE_URL || true)

# 客户端实际请求域（仅用于交叉提示）
client_api=$(extract_var "${CLIENT_ENV_LOCAL}" TARO_APP_API_BASE_URL || true)
[[ -z "${client_api}" ]] && client_api=$(extract_var "${CLIENT_ENV}" TARO_APP_API_BASE_URL || true)
client_host="$(url_host "${client_api}")"

errors=0
warns=0

check_url() {
  local label="$1" url="$2" expected_path="$3" required="$4"
  echo ""
  echo "  • ${label}"
  echo "    raw   = ${url:-<空>}"
  if [[ -z "${url}" ]]; then
    if [[ "${required}" == "yes" ]]; then
      red "    ✗ ${label} 未配置"
      errors=$((errors + 1))
    else
      yellow "    ! ${label} 未配置（按当前环境/特性可选）"
      warns=$((warns + 1))
    fi
    return
  fi
  if [[ "${url}" != https://* ]]; then
    red "    ✗ 必须为 https://（与微信商户后台一致）"
    errors=$((errors + 1))
  fi
  local host path
  host="$(url_host "${url}")"
  path="$(url_path "${url}")"
  echo "    host  = ${host}"
  echo "    path  = ${path}"
  case "${host}" in
    ""|localhost|127.0.0.1|0.0.0.0|*.local|*.internal|*.lan)
      red "    ✗ host 非公网，微信支付服务器无法回调"
      errors=$((errors + 1)) ;;
  esac
  if [[ -n "${expected_path}" && "${path}" != "${expected_path}" ]]; then
    red "    ✗ path 与后端路由不一致（期望 ${expected_path}）"
    echo "      路由来源：backend/app/api/v1/payments.py"
    errors=$((errors + 1))
  fi
  # 与同环境 client API host 一致更稳；不同源仅警告
  if [[ -n "${client_host}" && "${host}" != "${client_host}" ]]; then
    yellow "    ! host 与 client 实际请求域 ${client_host} 不同源；可正常工作但建议同源避免 nginx 配置漂移"
    warns=$((warns + 1))
  fi
}

section "1) 路径与协议校验"

# mock 模式下不强制要求；非 mock 视为生产必填
required="yes"
pay_mock_lc="$(printf '%s' "${pay_mock:-}" | tr '[:upper:]' '[:lower:]')"
case "${pay_mock_lc}" in
  true|1|yes) required="no" ;;
esac
echo "  WECHAT_PAY_MOCK_MODE=${pay_mock:-<空>}（required=${required}）"

check_url "WECHAT_PAY_NOTIFY_URL"        "${notify_url}" "${EXPECTED_NOTIFY_PATH}" "${required}"

# refund：若空、且 notify 非空，按 config.py 描述「在 notify URL 上推导」，给出推导值
if [[ -z "${refund_url}" && -n "${notify_url}" ]]; then
  derived="${notify_url/${EXPECTED_NOTIFY_PATH}/${EXPECTED_REFUND_PATH}}"
  yellow "  • WECHAT_PAY_REFUND_NOTIFY_URL 留空 → 后端将由 NOTIFY_URL 推导为 ${derived}"
  warns=$((warns + 1))
fi
check_url "WECHAT_PAY_REFUND_NOTIFY_URL" "${refund_url}" "${EXPECTED_REFUND_PATH}" "no"
check_url "WECHAT_PAY_PAPAY_NOTIFY_URL"  "${papay_url}"  ""                         "no"

section "2) 文档与代码一致性快验"
# docs/02 §6.2 应明确登记这两条路径；任何一条缺失即提示
docs_path="docs/02-API接口设计文档.md"
if [[ -f "${docs_path}" ]]; then
  if grep -F "${EXPECTED_NOTIFY_PATH}" "${docs_path}" >/dev/null 2>&1; then
    green "  ✓ docs/02 含 ${EXPECTED_NOTIFY_PATH}"
  else
    red "  ✗ docs/02 未提及 ${EXPECTED_NOTIFY_PATH}"
    errors=$((errors + 1))
  fi
  if grep -F "${EXPECTED_REFUND_PATH}" "${docs_path}" >/dev/null 2>&1; then
    green "  ✓ docs/02 含 ${EXPECTED_REFUND_PATH}"
  else
    red "  ✗ docs/02 未提及 ${EXPECTED_REFUND_PATH}"
    errors=$((errors + 1))
  fi
else
  yellow "  ! 找不到 ${docs_path}（不强制阻塞）"
  warns=$((warns + 1))
fi

# 后端路由声明：payments.py 必须含上述两条字符串
routes_py="backend/app/api/v1/payments.py"
if [[ -f "${routes_py}" ]]; then
  if grep -F '"/wechat/notify"' "${routes_py}" >/dev/null 2>&1; then
    green "  ✓ ${routes_py} 含 /wechat/notify 路由"
  else
    red "  ✗ ${routes_py} 未找到 /wechat/notify 路由声明"
    errors=$((errors + 1))
  fi
  if grep -F '"/wechat/refund-notify"' "${routes_py}" >/dev/null 2>&1; then
    green "  ✓ ${routes_py} 含 /wechat/refund-notify 路由"
  else
    red "  ✗ ${routes_py} 未找到 /wechat/refund-notify 路由声明"
    errors=$((errors + 1))
  fi
fi

section "结论"
if [[ "${errors}" -eq 0 ]]; then
  if [[ "${warns}" -eq 0 ]]; then
    green "✓ 支付/退款回调自检全部通过（U-4）"
  else
    green "✓ 支付/退款回调自检通过（U-4）；${warns} 条警告，按业务确认即可"
  fi
  exit 0
else
  red "✗ 支付/退款回调自检共 ${errors} 项失败（warns=${warns}）"
  echo "  关联文档：docs/19-产品开发迭代计划-当前队列.md §二 U-4"
  echo "  锚点：docs/02-API接口设计文档.md §6.2"
  exit 1
fi
