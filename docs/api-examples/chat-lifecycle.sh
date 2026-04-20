#!/usr/bin/env bash
# =============================================================================
# M3 AI 对话 API · 端到端联调脚本（T1-T5 累进，T6 收官核对）
# =============================================================================
# 覆盖：
#   0. GET  /chat/quick-questions              免登快捷问题
#   1. mock 微信登录
#   2. POST /chat/sessions                     创建会话
#   3. POST /chat/sessions/{id}/messages?stream=false   JSON 降级（T1）
#   4. GET  /chat/sessions                     会话列表（T1）
#   5. GET  /chat/sessions/{id}/messages       历史消息分页（T1）
#   6. POST /chat/sessions/{id}/messages       SSE 流式（T2；curl -N 看逐块输出）
#   7. POST /chat/sessions (context_analysis_id=xxx)  期望 404/40401
#   8. DELETE /chat/sessions/{id}              删除会话 → 再读 404
#
# 依赖：curl、jq、uuidgen
# 前置：`make up` 起全套服务
# 注意：
#   - 后端默认未配 LLM_API_KEY 时自动启用 FakeLLMClient，响应是固定模板文本；
#     如要打真实 LLM，先 `export LLM_API_KEY=...` 并重启 backend。
#   - SSE 步骤用 `curl -N`（禁用输出缓冲）+ `-H "Accept: text/event-stream"`。
#   - 非流式降级既认 `Accept: application/json` 也认 `?stream=false`，二者任一即生效（见 backend/app/api/v1/chat.py:181）
# =============================================================================

set -euo pipefail

API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
CODE="pytest_$(uuidgen | tr -d '-' | head -c 16)"

say() { printf "\n\033[1;36m==> %s\033[0m\n" "$*"; }
fail() { printf "\n\033[1;31mFAIL: %s\033[0m\n" "$*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || fail "缺少命令：$1"; }

need curl
need jq
need uuidgen

# ============================================================================
# 0. 匿名调用快捷问题（不需要 Token）
# ============================================================================
say "0) 获取快捷问题（免登）"
QQ=$(curl -fsS "${API_BASE_URL}/v1/chat/quick-questions")
QQ_COUNT=$(echo "$QQ" | jq '.data.questions | length')
echo "$QQ" | jq '.data.questions[] | {id, text, requires_analysis}'
[[ "$QQ_COUNT" -ge 4 ]] || fail "快捷问题至少 4 条，实际 $QQ_COUNT"

# ============================================================================
# 1. mock 登录
# ============================================================================
say "1) mock 微信登录，code=${CODE}"
TOKEN=$(curl -fsS -X POST "${API_BASE_URL}/v1/auth/wechat-login" \
  -H "Content-Type: application/json" \
  -d "{\"code\":\"${CODE}\"}" | jq -r '.data.token')
[[ -n "$TOKEN" && "$TOKEN" != "null" ]] || fail "登录失败，未拿到 token"
AUTH=(-H "Authorization: Bearer ${TOKEN}")

# ============================================================================
# 2. 创建会话（无 context_analysis_id）
# ============================================================================
say "2) 创建/获取活跃会话"
RESP=$(curl -fsS -X POST "${API_BASE_URL}/v1/chat/sessions" \
  "${AUTH[@]}" -H "Content-Type: application/json" \
  -d '{}')
SID=$(echo "$RESP" | jq -r '.data.session_id')
[[ -n "$SID" && "$SID" != "null" ]] || fail "未拿到 session_id"
echo "session_id=${SID}"

# ============================================================================
# 3. 发送 3 条消息，观察 quota_remaining 递减（免费用户 total=5 → 4,3,2）
# ============================================================================
for i in 1 2 3; do
  say "3.${i}) 发送消息 #${i}（JSON 降级：?stream=false + Accept: application/json 双保险）"
  MSG=$(curl -fsS -X POST "${API_BASE_URL}/v1/chat/sessions/${SID}/messages?stream=false" \
    "${AUTH[@]}" -H "Content-Type: application/json" -H "Accept: application/json" \
    -d "{\"content\":\"测试消息 ${i}\"}")
  echo "$MSG" | jq '{user: .data.user_message.content, ai: .data.assistant_message.content, remaining: .data.quota_remaining, attachments: .data.assistant_message.attachments}'
  REM=$(echo "$MSG" | jq -r '.data.quota_remaining')
  EXPECTED=$((5 - i))
  [[ "$REM" == "$EXPECTED" ]] || fail "quota_remaining 应为 $EXPECTED，实际 $REM"
done

# ============================================================================
# 4. 会话列表
# ============================================================================
say "4) 获取会话列表"
curl -fsS "${API_BASE_URL}/v1/chat/sessions?page=1&page_size=10" "${AUTH[@]}" \
  | jq '.data.items[] | {id, message_count, last_message_preview, last_message_at}'

# ============================================================================
# 5. 历史消息分页
# ============================================================================
say "5) 获取历史消息（第 1 页，page_size=2）"
curl -fsS "${API_BASE_URL}/v1/chat/sessions/${SID}/messages?page=1&page_size=2" "${AUTH[@]}" \
  | jq '{total: .data.total, has_more: .data.has_more, roles: [.data.items[].role]}'

# ============================================================================
# 6. SSE 流式发消息（T2 新增；用 curl -N 可看到逐块输出）
# ============================================================================
say "6) SSE 流式发消息（Accept: text/event-stream）"
curl -sS -N -X POST "${API_BASE_URL}/v1/chat/sessions/${SID}/messages" \
  "${AUTH[@]}" -H "Content-Type: application/json" -H "Accept: text/event-stream" \
  -d '{"content":"帮我推荐一个髋部旋转的练习"}' | sed -u 's/^/  [SSE] /' | head -n 40
printf "\n  （上面应包含：event: message_start → 多条 event: content_delta → event: attachment → event: message_end）\n"

# ============================================================================
# 7. 带 context_analysis_id 的创建（期望 404：当前用户没有这个分析）
# ============================================================================
say "7) 带不存在的 context_analysis_id → 期望 404/40401"
HTTP_CODE=$(curl -s -o /tmp/chat_404.json -w "%{http_code}" -X POST \
  "${API_BASE_URL}/v1/chat/sessions" \
  "${AUTH[@]}" -H "Content-Type: application/json" \
  -d '{"context_analysis_id":"ana_fake"}')
CODE=$(jq -r '.code' /tmp/chat_404.json)
echo "http=${HTTP_CODE} code=${CODE}"
[[ "$HTTP_CODE" == "404" && "$CODE" == "40401" ]] || fail "期望 404/40401"

# ============================================================================
# 8. 删除会话
# ============================================================================
say "8) 删除会话 ${SID}"
curl -fsS -X DELETE "${API_BASE_URL}/v1/chat/sessions/${SID}" "${AUTH[@]}" | jq
# 再读消息应 404
HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" \
  "${API_BASE_URL}/v1/chat/sessions/${SID}/messages" "${AUTH[@]}")
[[ "$HTTP_CODE" == "404" ]] || fail "删除后读消息应 404，实际 $HTTP_CODE"

printf "\n\033[1;32m✅ M3 AI 对话 API 联调全部通过（T1 骨架 + T2 SSE + T5 context_analysis_id 路径）\033[0m\n"
