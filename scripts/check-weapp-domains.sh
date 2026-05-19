#!/usr/bin/env bash
# 微信小程序合法域名 + HTTPS 链路自检：U-3 紧急队列对应（docs/19 §二）
#
# 与 infra/deploy/verify-weapp-https-readiness.sh 互补：
#   - verify-weapp-https-readiness.sh：单 host 深度 TLS / 业务自检
#   - 本脚本：从 client/.env.production(.local) + 服务端 env 中汇总
#     所有需登记到微信公众平台「服务器域名」(request/upload/socket)
#     的主机集合，逐个调用上面的脚本并最终输出登记清单。
#
# 用法（仓库根）：
#   make check-weapp-domains
#
# 环境变量：
#   STRICT_HEALTH=1       任意一个 host 的 /v1/health 非 2xx 即整体失败
#   EXTRA_HOSTS="a.com b.com"  追加要核验的 host（如 CDN、socket）
#   CLIENT_ENV=client/.env.production  覆盖默认前端 env
#   BACKEND_ENV=.env.local             覆盖默认后端 env（仅用作可选补充）
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "${REPO_ROOT}"

CLIENT_ENV="${CLIENT_ENV:-client/.env.production}"
CLIENT_ENV_LOCAL="${CLIENT_ENV_LOCAL:-client/.env.production.local}"
BACKEND_ENV="${BACKEND_ENV:-.env.local}"

red()    { printf '\033[31m%s\033[0m\n' "$*" >&2; }
green()  { printf '\033[32m%s\033[0m\n' "$*"; }
yellow() { printf '\033[33m%s\033[0m\n' "$*"; }
section(){ printf '\n\033[1m=== %s ===\033[0m\n' "$*"; }

# 从 KEY=VALUE 文件抽取变量值（兼容 # 注释、引号、CRLF）
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

# 把 URL 规整成 host（去 schema/path/port）
url_to_host() {
  local raw="${1:-}"
  [[ -z "${raw}" ]] && return 0
  raw="${raw#http://}"
  raw="${raw#https://}"
  raw="${raw%%/*}"
  raw="${raw%%:*}"
  echo "${raw}"
}

# .local 覆盖 .env.production
read_client_var() {
  local k="$1"
  local v
  v="$(extract_var "${CLIENT_ENV_LOCAL}" "${k}" || true)"
  if [[ -z "${v}" ]]; then
    v="$(extract_var "${CLIENT_ENV}" "${k}" || true)"
  fi
  echo "${v}"
}

section "0) 输入"
echo "  CLIENT_ENV       = ${CLIENT_ENV}"
echo "  CLIENT_ENV_LOCAL = ${CLIENT_ENV_LOCAL}"
echo "  BACKEND_ENV      = ${BACKEND_ENV}"

api_url="$(read_client_var TARO_APP_API_BASE_URL)"
storage_pub_url="$(read_client_var TARO_APP_STORAGE_BASE_URL)"
if [[ -z "${storage_pub_url}" ]]; then
  storage_pub_url="$(read_client_var TARO_APP_MINIO_PUBLIC_ENDPOINT)"
fi
ai_engine_url="$(read_client_var TARO_APP_AI_ENGINE_URL)"

backend_api_pub="$(extract_var "${BACKEND_ENV}" API_PUBLIC_BASE_URL || true)"
backend_minio_pub="$(extract_var "${BACKEND_ENV}" MINIO_PUBLIC_ENDPOINT || true)"
backend_cos_pub="$(extract_var "${BACKEND_ENV}" COS_PUBLIC_BASE || true)"

# 用 sentinel 文件存数组，避免 macOS 默认 bash 3.2 + set -u 下的间接数组展开问题
WORKDIR="$(mktemp -d -t check-weapp-domains.XXXXXX)"
trap 'rm -rf "${WORKDIR}"' EXIT
: > "${WORKDIR}/request" ; : > "${WORKDIR}/upload" ; : > "${WORKDIR}/socket"

add_unique() {
  local kind="$1" v="$2"
  [[ -z "${v}" ]] && return 0
  local f="${WORKDIR}/${kind}"
  if ! grep -Fxq "${v}" "${f}" 2>/dev/null; then
    echo "${v}" >> "${f}"
  fi
}

list_kind() {
  local kind="$1"
  cat "${WORKDIR}/${kind}" 2>/dev/null | grep -v '^$' || true
}

count_kind() {
  list_kind "$1" | wc -l | tr -d ' '
}

add_unique request "$(url_to_host "${api_url}")"
add_unique request "$(url_to_host "${ai_engine_url}")"
add_unique request "$(url_to_host "${backend_api_pub}")"

# upload 域名：通常与下载共用（COS / MinIO 公网）
add_unique upload  "$(url_to_host "${storage_pub_url}")"
add_unique upload  "$(url_to_host "${backend_minio_pub}")"
add_unique upload  "$(url_to_host "${backend_cos_pub}")"

# 追加用户指定
if [[ -n "${EXTRA_HOSTS:-}" ]]; then
  for h in ${EXTRA_HOSTS}; do
    add_unique request "$(url_to_host "${h}")"
  done
fi

# 合法性：必须有 request host
if [[ "$(count_kind request)" == "0" ]]; then
  red "✗ 无法从 ${CLIENT_ENV} 中提取 TARO_APP_API_BASE_URL"
  exit 1
fi

section "1) 解析到的 host 集合"
echo "  request (https): $(list_kind request | tr '\n' ' ')"
upload_list="$(list_kind upload | tr '\n' ' ')"
echo "  upload  (https): ${upload_list:-<无>}"
socket_list="$(list_kind socket | tr '\n' ' ')"
echo "  socket  (wss)  : ${socket_list:-<无，按需经 EXTRA_HOSTS 指定>}"

errors=0
: > "${WORKDIR}/checked"

run_one() {
  local host="$1"
  [[ -z "${host}" ]] && return 0
  case "${host}" in
    localhost|127.0.0.1|0.0.0.0|*.local|*.internal|*.lan)
      yellow "! 跳过非公网 host：${host}"
      return 0 ;;
  esac

  if grep -Fxq "${host}" "${WORKDIR}/checked" 2>/dev/null; then
    return 0
  fi
  echo "${host}" >> "${WORKDIR}/checked"

  section "2) 核验 ${host}"
  if bash infra/deploy/verify-weapp-https-readiness.sh "${host}"; then
    green "✓ ${host} 通过"
  else
    red "✗ ${host} 失败"
    errors=$((errors + 1))
  fi
}

while IFS= read -r h; do [[ -n "${h}" ]] && run_one "${h}"; done < "${WORKDIR}/request"
while IFS= read -r h; do [[ -n "${h}" ]] && run_one "${h}"; done < "${WORKDIR}/upload"
while IFS= read -r h; do [[ -n "${h}" ]] && run_one "${h}"; done < "${WORKDIR}/socket"

print_registry() {
  local kind="$1" prefix="$2" title="$3"
  if [[ "$(count_kind "${kind}")" != "0" ]]; then
    echo ""
    echo "  ${title}："
    while IFS= read -r h; do
      [[ -z "${h}" ]] && continue
      case "${h}" in localhost|127.0.0.1|0.0.0.0|*.local|*.internal|*.lan) continue ;; esac
      echo "    ${prefix}${h}"
    done < "${WORKDIR}/${kind}"
  fi
}

section "3) 微信公众平台「服务器域名」登记清单"
echo "  ← 复制到「开发管理 → 开发设置 → 服务器域名」（仅含主机名，不含路径 /v1）"
print_registry request "https://" "request 合法域名"
print_registry upload  "https://" "uploadFile / downloadFile 合法域名"
print_registry socket  "wss://"   "socket 合法域名"

section "结论"
if [[ "${errors}" -eq 0 ]]; then
  green "✓ 全部 host TLS/业务自检通过（U-3）"
  exit 0
else
  red "✗ 共 ${errors} 个 host 自检失败；详见上方分段输出"
  echo "  关联文档：docs/19-产品开发迭代计划-当前队列.md §二 U-3"
  echo "  关联说明：docs/release-notes/W9-code-vs-plan-status.md「小程序侧此前踩坑」"
  exit 1
fi
