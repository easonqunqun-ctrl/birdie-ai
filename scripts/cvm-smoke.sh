#!/usr/bin/env bash
# 生产 / 测试 HTTPS 冒烟：TLS + /v1/health（可选 Bearer 拉 /users/me·/analyses）
#
# 用法（仓库根或任意目录）：
#   DOMAIN=api.birdieai.cn bash scripts/cvm-smoke.sh
#   CVM_DOMAIN=api.birdieai.cn TOKEN='eyJ…' bash scripts/cvm-smoke.sh
#
# 环境变量：
#   DOMAIN 或 CVM_DOMAIN   API 主机名（不含 https://），默认 api.birdieai.cn
#   TOKEN                     可选；有则校验 /users/me 与分页 /analyses
#   LOGIN_CODE                可选；若设置则 POST /v1/auth/wechat-login（须服务端 mock 或可用的 code）
#   CURL_EXTRA                附加 curl 参数（例如自签调试： CURL_EXTRA=-k）
#   HEALTH_PATH               默认 /v1/health
#
# 文档：docs/release-notes/CVM-canonical-deploy.md §「冒烟脚本」

set -euo pipefail

DOMAIN="${DOMAIN:-${CVM_DOMAIN:-api.birdieai.cn}}"
BASE="https://${DOMAIN}"
HEALTH_PATH="${HEALTH_PATH:-/v1/health}"

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "  CVM smoke  DOMAIN=$DOMAIN"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"

run_curl() {
  # shellcheck disable=SC2086
  curl -sfS "${CURL_EXTRA:-}" --connect-timeout 8 --max-time 25 "$@"
}

echo "→ GET $BASE$HEALTH_PATH"
resp="$(run_curl -H 'Accept: application/json' "$BASE$HEALTH_PATH")"
echo "$resp" | python3 -c 'import sys,json; json.load(sys.stdin); print("  ✓ JSON 解析 OK（/v1/health）")'

if [[ -n "${TOKEN:-}" ]]; then
  echo "→ GET $BASE/v1/users/me （Bearer）"
  me="$(run_curl -H 'Accept: application/json' -H "Authorization: Bearer $TOKEN" "$BASE/v1/users/me")"
  echo "$me" | python3 -c 'import sys,json; json.load(sys.stdin); print("  ✓ JSON 解析 OK（/users/me）")'
  echo "→ GET $BASE/v1/analyses?page=1&page_size=3"
  list="$(run_curl -H 'Accept: application/json' -H "Authorization: Bearer $TOKEN" "$BASE/v1/analyses?page=1&page_size=3")"
  echo "$list" | python3 -c '
import sys, json
d = json.load(sys.stdin)
payload = d.get("data") if isinstance(d.get("data"), dict) else d
items = (payload or {}).get("items")
if isinstance(items, list):
    print("  ✓ analyses items 条数=", len(items))
else:
    print("  ⚠ 未读到 data.items（仍视为 HTTP 成功）")
'

if [[ -n "${LOGIN_CODE:-}" ]]; then
  echo "→ POST /v1/auth/wechat-login"
  body="$(python3 -c "import json,os; print(json.dumps({'code': os.environ.get('LOGIN_CODE','')}))")"
  run_curl -H 'Content-Type: application/json' -H 'Accept: application/json' \
    -X POST -d "$body" "$BASE/v1/auth/wechat-login" | head -c 200
  echo
  echo "✓ 登录请求已送达（核对返回 code/message）"
fi

echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "✓ cvm-smoke 完成"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
