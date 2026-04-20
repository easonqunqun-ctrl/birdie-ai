#!/usr/bin/env bash
# =============================================================================
# M1 用户体系·端到端联调脚本
# =============================================================================
# 覆盖：
#   1. 微信登录（mock）→ 新用户建档，拿 token
#   2. GET /v1/users/me（带 stats / quota）
#   3. POST /v1/users/me/onboarding（正常写档）—— 分支 A
#   4. PATCH /v1/users/me { onboarding_completed: true } —— 分支 B（"跳过"入口）
#   5. PATCH /v1/users/me { onboarding_completed: false } —— 预期 400 + code=40010
#   6. PATCH /v1/users/me { nickname / golf_level / ... } —— 档案编辑
#   7. POST /v1/auth/refresh-token —— 刷新 token
#
# 依赖：curl、jq
# =============================================================================

set -euo pipefail

API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
CODE="pytest_$(uuidgen | tr -d '-' | head -c 16)"

say() { printf "\n\033[1;36m==> %s\033[0m\n" "$*"; }
fail() { printf "\n\033[1;31mFAIL: %s\033[0m\n" "$*" >&2; exit 1; }

need() { command -v "$1" >/dev/null 2>&1 || fail "缺少命令：$1"; }
need curl
need jq

# ----------------------------------------------------------------------------
# 1. 登录
# ----------------------------------------------------------------------------
say "1. 微信登录（mock code=${CODE}）"
LOGIN_JSON=$(curl -sS -X POST "${API_BASE_URL}/v1/auth/wechat-login" \
  -H "Content-Type: application/json" \
  -d "{\"code\":\"${CODE}\"}")
echo "$LOGIN_JSON" | jq .

TOKEN=$(echo "$LOGIN_JSON" | jq -r '.data.token // empty')
IS_NEW=$(echo "$LOGIN_JSON" | jq -r '.data.is_new_user')
[[ -n "$TOKEN" ]] || fail "没拿到 token"
[[ "$IS_NEW" == "true" ]] || fail "首次 code 应视为新用户，实际 is_new_user=$IS_NEW"

AUTH=(-H "Authorization: Bearer $TOKEN")

# ----------------------------------------------------------------------------
# 2. GET /me
# ----------------------------------------------------------------------------
say "2. GET /v1/users/me"
curl -sS "${AUTH[@]}" "$API_BASE_URL/v1/users/me" | jq .

# ----------------------------------------------------------------------------
# 3. POST /me/onboarding
# ----------------------------------------------------------------------------
say "3. POST /v1/users/me/onboarding（正常写档）"
curl -sS -X POST "$API_BASE_URL/v1/users/me/onboarding" \
  "${AUTH[@]}" -H "Content-Type: application/json" \
  -d '{
    "golf_level": "beginner",
    "primary_goals": ["distance", "accuracy"],
    "weekly_practice_frequency": "frequent"
  }' | jq .

# ----------------------------------------------------------------------------
# 4. "跳过"入口：PATCH onboarding_completed=true
# ----------------------------------------------------------------------------
say "4. PATCH /v1/users/me { onboarding_completed: true } —— 跳过入口"
curl -sS -X PATCH "$API_BASE_URL/v1/users/me" \
  "${AUTH[@]}" -H "Content-Type: application/json" \
  -d '{"onboarding_completed": true}' | jq '.code, .data.onboarding_completed'

# ----------------------------------------------------------------------------
# 5. 拒绝反向置 false（业务守门）
# ----------------------------------------------------------------------------
say "5. PATCH /v1/users/me { onboarding_completed: false } —— 预期 400 + code=40010"
HTTP_CODE=$(curl -sS -o /tmp/m1_patch_reject.json -w '%{http_code}' \
  -X PATCH "$API_BASE_URL/v1/users/me" \
  "${AUTH[@]}" -H "Content-Type: application/json" \
  -d '{"onboarding_completed": false}')
cat /tmp/m1_patch_reject.json | jq .
[[ "$HTTP_CODE" == "400" ]] || fail "应当返回 400，实际 $HTTP_CODE"
CODE_FIELD=$(jq -r '.code' /tmp/m1_patch_reject.json)
[[ "$CODE_FIELD" == "40010" ]] || fail "应当返回 code=40010，实际 $CODE_FIELD"

# ----------------------------------------------------------------------------
# 6. 编辑档案
# ----------------------------------------------------------------------------
say "6. PATCH /v1/users/me（编辑昵称/等级/目标/频率）"
curl -sS -X PATCH "$API_BASE_URL/v1/users/me" \
  "${AUTH[@]}" -H "Content-Type: application/json" \
  -d '{
    "nickname": "果岭老王",
    "golf_level": "intermediate",
    "primary_goals": ["putting", "consistency"],
    "weekly_practice_frequency": "daily"
  }' | jq '.data | {nickname, golf_level, primary_goals, weekly_practice_frequency, onboarding_completed}'

# ----------------------------------------------------------------------------
# 7. refresh-token
# ----------------------------------------------------------------------------
say "7. POST /v1/auth/refresh-token"
curl -sS -X POST "$API_BASE_URL/v1/auth/refresh-token" \
  "${AUTH[@]}" | jq '.data | {expires_in, token_len: (.token | length)}'

say "✅ 全链路通过"
