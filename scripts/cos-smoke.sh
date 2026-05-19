#!/usr/bin/env bash
# COS / CDN 真桶冒烟：U-2 紧急队列对应（docs/19 §二）
# 与 backend/tests/test_storage_presign_contract.py 互补：契约 + 真桶。
#
# 用 awscli（COS 兼容 S3 协议）跑 PUT → HEAD → GET → DELETE；附带 CORS
# 抽样与可选 CDN 缓存头核查。
#
# 用法：
#   COS_BUCKET=foo-1250000000 COS_REGION=ap-shanghai \
#     COS_SECRET_ID=AKID... COS_SECRET_KEY=... \
#     bash scripts/cos-smoke.sh
#
# 可选：
#   COS_ENDPOINT          覆盖默认 https://cos.${COS_REGION}.myqcloud.com
#   CDN_HOST              形如 cdn.birdieai.cn；不设则跳过 CDN 检查
#   ORIGIN                CORS 预检 Origin，默认 https://servicewechat.com
#   TEST_KEY              测试对象 Key，默认 _preflight/cos-smoke-$ts
#   KEEP=1                跑完不删除测试对象（人对桶时调试用）
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

red()   { printf '\033[31m%s\033[0m\n' "$*" >&2; }
green() { printf '\033[32m%s\033[0m\n' "$*"; }
yellow(){ printf '\033[33m%s\033[0m\n' "$*"; }
section(){ printf '\n\033[1m=== %s ===\033[0m\n' "$*"; }

# 从 .env.local / ENV_FILE 自动加载 COS_*（与 check-payment-callbacks 一致）
load_env_file() {
  local f="$1"
  [[ -f "${f}" ]] || return 0
  while IFS= read -r line || [[ -n "${line}" ]]; do
    line="${line%%#*}"
    line="$(echo "${line}" | sed 's/^[[:space:]]*//;s/[[:space:]]*$//')"
    [[ -z "${line}" || "${line}" != *=* ]] && continue
    local k="${line%%=*}"
    local v="${line#*=}"
    v="${v%\"}"; v="${v#\"}"
    v="${v%\'}"; v="${v#\'}"
    case "${k}" in
      COS_BUCKET|COS_REGION|COS_SECRET_ID|COS_SECRET_KEY|COS_ENDPOINT|CDN_HOST)
        if [[ -z "${!k:-}" ]]; then
          export "${k}=${v}"
        fi
        ;;
    esac
  done < "${f}"
}

ENV_FILE="${ENV_FILE:-${ENV:-${REPO_ROOT}/.env.local}}"
load_env_file "${ENV_FILE}"

require() {
  if [[ -z "${!1:-}" ]]; then
    return 1
  fi
  return 0
}

if ! require COS_BUCKET || ! require COS_REGION || ! require COS_SECRET_ID || ! require COS_SECRET_KEY; then
  yellow "! U-2 跳过：COS 四元组未配置（可在 ${ENV_FILE} 填写 COS_BUCKET/REGION/SECRET_*）"
  yellow "  契约测试仍由 backend pytest test_storage_presign_contract 覆盖；真桶冒烟待密钥就绪后再跑。"
  exit 0
fi

COS_ENDPOINT="${COS_ENDPOINT:-https://cos.${COS_REGION}.myqcloud.com}"
ORIGIN="${ORIGIN:-https://servicewechat.com}"
ts="$(date +%Y%m%d-%H%M%S)"
TEST_KEY="${TEST_KEY:-_preflight/cos-smoke-${ts}.txt}"
KEEP="${KEEP:-0}"
CDN_HOST="${CDN_HOST:-}"

if ! command -v aws >/dev/null 2>&1; then
  red "✗ 未找到 aws CLI；macOS 安装：brew install awscli"
  exit 127
fi
if ! command -v curl >/dev/null 2>&1; then
  red "✗ 未找到 curl"
  exit 127
fi

errors=0
tmp_payload="$(mktemp -t cos-smoke.XXXXXX)"
tmp_get="$(mktemp -t cos-smoke-get.XXXXXX)"
trap 'rm -f "${tmp_payload}" "${tmp_get}"' EXIT
echo "birdie-cos-smoke ${ts}" > "${tmp_payload}"
expected_sha="$(shasum -a 256 "${tmp_payload}" | awk '{print $1}')"

export AWS_ACCESS_KEY_ID="${COS_SECRET_ID}"
export AWS_SECRET_ACCESS_KEY="${COS_SECRET_KEY}"
AWS_S3=(aws s3api --endpoint-url "${COS_ENDPOINT}" --region "${COS_REGION}")

section "0) 配置回显"
echo "  bucket   = ${COS_BUCKET}"
echo "  region   = ${COS_REGION}"
echo "  endpoint = ${COS_ENDPOINT}"
echo "  key      = ${TEST_KEY}"
echo "  origin   = ${ORIGIN}"
echo "  cdn      = ${CDN_HOST:-<未设置，跳过>}"

section "1) PUT object"
if "${AWS_S3[@]}" put-object \
    --bucket "${COS_BUCKET}" \
    --key "${TEST_KEY}" \
    --body "${tmp_payload}" \
    --content-type "text/plain" \
    >/dev/null; then
  green "✓ put-object 成功"
else
  red "✗ put-object 失败"
  errors=$((errors + 1))
fi

section "2) HEAD object"
if "${AWS_S3[@]}" head-object \
    --bucket "${COS_BUCKET}" \
    --key "${TEST_KEY}" \
    --output json 2>/dev/null | tee /tmp/cos-smoke-head.json >/dev/null; then
  size=$(python3 -c "import json,sys;d=json.load(open('/tmp/cos-smoke-head.json'));print(d.get('ContentLength','?'))")
  green "✓ head-object 成功 (Content-Length=${size})"
else
  red "✗ head-object 失败"
  errors=$((errors + 1))
fi

section "3) GET object + 校验内容"
if "${AWS_S3[@]}" get-object \
    --bucket "${COS_BUCKET}" \
    --key "${TEST_KEY}" \
    "${tmp_get}" >/dev/null 2>&1; then
  got_sha="$(shasum -a 256 "${tmp_get}" | awk '{print $1}')"
  if [[ "${got_sha}" == "${expected_sha}" ]]; then
    green "✓ get-object 成功且内容一致 (sha256=${got_sha:0:12}…)"
  else
    red "✗ get-object 内容不一致：期望 ${expected_sha}，实际 ${got_sha}"
    errors=$((errors + 1))
  fi
else
  red "✗ get-object 失败"
  errors=$((errors + 1))
fi

section "4) CORS 预检 (OPTIONS)"
public_url="${COS_ENDPOINT%/}/${TEST_KEY}"
# 若 endpoint 是 https://cos.<region>.myqcloud.com，COS path-style 需要 bucket 在 path 里；
# 用 vhost-style 更接近真实小程序请求路径。
vhost_url="https://${COS_BUCKET}.cos.${COS_REGION}.myqcloud.com/${TEST_KEY}"
cors_status=$(curl -s -o /tmp/cos-smoke-cors.txt -w '%{http_code}' \
  -X OPTIONS \
  -H "Origin: ${ORIGIN}" \
  -H "Access-Control-Request-Method: GET" \
  -H "Access-Control-Request-Headers: content-type,authorization" \
  "${vhost_url}" || true)
echo "  OPTIONS ${vhost_url} → ${cors_status}"
if [[ "${cors_status}" =~ ^2 ]]; then
  acao=$(curl -sI -X OPTIONS -H "Origin: ${ORIGIN}" -H "Access-Control-Request-Method: GET" \
    "${vhost_url}" | awk -F': ' 'tolower($1)=="access-control-allow-origin"{print $2}' | tr -d '\r')
  if [[ -n "${acao}" ]]; then
    green "✓ CORS 通过 (Access-Control-Allow-Origin: ${acao})"
  else
    yellow "! 2xx 但未返回 Access-Control-Allow-Origin；检查 COS 控制台「跨域访问 CORS」规则中 AllowOrigin"
  fi
else
  red "✗ CORS 预检 ${cors_status}：在 COS 控制台「跨域访问 CORS」配置 AllowOrigin=${ORIGIN}（或 *），AllowMethods=GET/HEAD/PUT/POST/DELETE/OPTIONS"
  errors=$((errors + 1))
fi

if [[ -n "${CDN_HOST}" ]]; then
  section "5) CDN 缓存头"
  cdn_url="https://${CDN_HOST}/${TEST_KEY}"
  cdn_headers=$(curl -sI "${cdn_url}" || true)
  echo "${cdn_headers}" | sed 's/^/    /'
  if echo "${cdn_headers}" | grep -iE '^(x-cache|x-cdn|via|x-edge)' >/dev/null 2>&1; then
    green "✓ CDN 节点响应（建议同时核对回源策略）"
  else
    yellow "! 未识别 CDN 节点头；若 CDN 仍在配置中可跳过"
  fi
else
  section "5) CDN 缓存头 (跳过)"
  echo "  未设置 CDN_HOST；如启用 CDN，重跑加 CDN_HOST=cdn.example.com"
fi

if [[ "${KEEP}" != "1" ]]; then
  section "6) DELETE object"
  if "${AWS_S3[@]}" delete-object \
      --bucket "${COS_BUCKET}" \
      --key "${TEST_KEY}" \
      >/dev/null; then
    green "✓ delete-object 成功"
  else
    yellow "! delete-object 失败；请人工到 COS 控制台清理 ${TEST_KEY}"
  fi
else
  section "6) DELETE object (KEEP=1，保留以便人工查看)"
  echo "  对象仍在桶内：${TEST_KEY}"
fi

section "结论"
if [[ "${errors}" -eq 0 ]]; then
  green "✓ COS 真桶冒烟通过（U-2）"
  exit 0
else
  red "✗ COS 真桶冒烟共 ${errors} 项失败"
  echo "  关联文档：docs/19-产品开发迭代计划-当前队列.md §二 U-2"
  echo "  契约级测试：backend/tests/test_storage_presign_contract.py"
  exit 1
fi
