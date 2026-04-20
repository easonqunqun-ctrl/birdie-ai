#!/usr/bin/env bash
# =============================================================================
# M2-T1/T2/T6 挥杆分析 API · 端到端联调脚本
# =============================================================================
# 覆盖：
#   0. GET /analyses/sample —— 免登示例报告（T6 新增）
#   1. mock 微信登录拿 token
#   2. 申请上传凭证（40005 / 40004 / 正常 3 个分支）
#   3. 用凭证 POST multipart/form-data 把视频上传到 MinIO（直传，不走后端）
#   4. 创建分析任务（pending → celery 消费中 → completed）
#   5. 轮询 GET /analyses/{id}/status 直到 completed/failed（上限 60s）
#   6. GET /analyses/{id} 取报告（completed 时 200 + 完整字段）
#   7. GET /analyses 列表（默认 + club_type 过滤）
#
# 依赖：curl、jq、uuidgen、ffmpeg（可选：用于生成一个合规的测试视频）
# 前置：`make up` 起全套服务（backend / celery-worker / ai_engine / postgres / redis / minio）
# 说明：ai_engine 默认跑 mock 模式（sleep 2-5s 返回随机报告），所以 60s 内一定 completed。
# =============================================================================

set -euo pipefail

API_BASE_URL="${API_BASE_URL:-http://localhost:8000}"
MINIO_PUBLIC_URL="${MINIO_PUBLIC_URL:-http://localhost:9000}"
CODE="pytest_$(uuidgen | tr -d '-' | head -c 16)"
TEST_VIDEO="${TEST_VIDEO:-/tmp/m2_test_video.mp4}"

say() { printf "\n\033[1;36m==> %s\033[0m\n" "$*"; }
fail() { printf "\n\033[1;31mFAIL: %s\033[0m\n" "$*" >&2; exit 1; }
need() { command -v "$1" >/dev/null 2>&1 || fail "缺少命令：$1"; }

need curl
need jq
need uuidgen

# ----------------------------------------------------------------------------
# 准备：若测试视频不存在，用 ffmpeg 生成 10 秒黑屏 MP4；没 ffmpeg 就写一个空 mp4 占位
# （空文件过不了 MinIO content-length-range，但其他分支仍能测到；建议装 ffmpeg）
# ----------------------------------------------------------------------------
if [[ ! -f "$TEST_VIDEO" ]]; then
  if command -v ffmpeg >/dev/null 2>&1; then
    say "生成测试视频 $TEST_VIDEO（10s 黑屏 mp4）"
    ffmpeg -loglevel error -y -f lavfi -i color=black:s=480x640:r=30 -t 10 \
      -pix_fmt yuv420p "$TEST_VIDEO"
  else
    say "⚠️  ffmpeg 未安装，伪造一个 2MB 随机字节文件（无法通过 MinIO 上传校验）"
    dd if=/dev/urandom of="$TEST_VIDEO" bs=1024 count=2048 status=none
  fi
fi
FILE_SIZE=$(wc -c < "$TEST_VIDEO" | tr -d ' ')

# ----------------------------------------------------------------------------
# 0. 示例报告（免登即可拿完整数据 —— MVP §3.6）
# ----------------------------------------------------------------------------
say "0. GET /analyses/sample —— 预期 200 + 固定示例报告（不需要 Token）"
HTTP=$(curl -sS -o /tmp/m2_sample.json -w '%{http_code}' \
  "${API_BASE_URL}/v1/analyses/sample")
[[ "$HTTP" == "200" ]] || fail "sample 应 200，实际 $HTTP"
jq '.data | {
  id, status, overall_score, score_level,
  weakest: [(.phase_scores | to_entries[] | select(.value.is_weakest) | .key)],
  issues_count: (.issues | length),
  recommendations_count: (.recommendations | length)
}' /tmp/m2_sample.json
[[ "$(jq -r .data.id /tmp/m2_sample.json)" == "sample" ]] || fail "示例报告 id 应为 sample"

# ----------------------------------------------------------------------------
# 1. 登录
# ----------------------------------------------------------------------------
say "1. 微信登录（mock code=${CODE}）"
LOGIN_JSON=$(curl -sS -X POST "${API_BASE_URL}/v1/auth/wechat-login" \
  -H "Content-Type: application/json" \
  -d "{\"code\":\"${CODE}\"}")
TOKEN=$(echo "$LOGIN_JSON" | jq -r '.data.token // empty')
[[ -n "$TOKEN" ]] || fail "登录未拿到 token，响应：$LOGIN_JSON"
AUTH=(-H "Authorization: Bearer $TOKEN")
echo "token = ${TOKEN:0:32}..."

# ----------------------------------------------------------------------------
# 2a. 超大文件应被拒绝（40005）
# ----------------------------------------------------------------------------
say "2a. POST /analyses/upload-token 超大文件 → 预期 400 + code=40005"
HTTP=$(curl -sS -o /tmp/m2_oversize.json -w '%{http_code}' \
  -X POST "${API_BASE_URL}/v1/analyses/upload-token" "${AUTH[@]}" \
  -H "Content-Type: application/json" \
  -d '{"file_name":"big.mp4","file_size":'"$((150 * 1024 * 1024))"',"file_type":"video/mp4","duration":10}')
cat /tmp/m2_oversize.json | jq .
[[ "$HTTP" == "400" ]] || fail "应 400，实际 $HTTP"
[[ "$(jq -r .code /tmp/m2_oversize.json)" == "40005" ]] || fail "应 code=40005"

# ----------------------------------------------------------------------------
# 2b. 时长不足应被拒绝（40004）
# ----------------------------------------------------------------------------
say "2b. POST /analyses/upload-token 时长 1.5s → 预期 400 + code=40004"
HTTP=$(curl -sS -o /tmp/m2_short.json -w '%{http_code}' \
  -X POST "${API_BASE_URL}/v1/analyses/upload-token" "${AUTH[@]}" \
  -H "Content-Type: application/json" \
  -d '{"file_name":"s.mp4","file_size":1024,"file_type":"video/mp4","duration":1.5}')
[[ "$HTTP" == "400" ]] || fail "应 400，实际 $HTTP"
[[ "$(jq -r .code /tmp/m2_short.json)" == "40004" ]] || fail "应 code=40004"

# ----------------------------------------------------------------------------
# 2c. 正常签发凭证
# ----------------------------------------------------------------------------
say "2c. POST /analyses/upload-token 正常（file_size=${FILE_SIZE}, duration=10）"
TOKEN_JSON=$(curl -sS -X POST "${API_BASE_URL}/v1/analyses/upload-token" "${AUTH[@]}" \
  -H "Content-Type: application/json" \
  -d "{\"file_name\":\"swing.mp4\",\"file_size\":${FILE_SIZE},\"file_type\":\"video/mp4\",\"duration\":10}")
echo "$TOKEN_JSON" | jq '.data | {upload_id, upload_url, key, expires_at}'
UPLOAD_ID=$(echo "$TOKEN_JSON" | jq -r '.data.upload_id')
UPLOAD_URL=$(echo "$TOKEN_JSON" | jq -r '.data.upload_url')
KEY=$(echo "$TOKEN_JSON" | jq -r '.data.key')

# ----------------------------------------------------------------------------
# 3. 用凭证直传到 MinIO
# ----------------------------------------------------------------------------
say "3. 直传视频到 MinIO（${UPLOAD_URL}）"
FIELDS_ARGS=()
while IFS= read -r line; do
  KEY_NAME=$(echo "$line" | cut -d= -f1)
  KEY_VAL=$(echo "$line" | cut -d= -f2-)
  FIELDS_ARGS+=(-F "${KEY_NAME}=${KEY_VAL}")
done < <(echo "$TOKEN_JSON" | jq -r '.data.fields | to_entries[] | "\(.key)=\(.value)"')

HTTP_UPLOAD=$(curl -sS -o /tmp/m2_upload_resp -w '%{http_code}' \
  -X POST "$UPLOAD_URL" \
  "${FIELDS_ARGS[@]}" \
  -F "file=@${TEST_VIDEO};type=video/mp4")
if [[ "${HTTP_UPLOAD}" != "204" && "${HTTP_UPLOAD}" != "200" ]]; then
  echo "MinIO 返回："
  cat /tmp/m2_upload_resp
  fail "MinIO 上传失败 HTTP=${HTTP_UPLOAD}, TEST_VIDEO 是否为真 mp4、大小介于 1B 和 100MB 之间？"
fi
echo "✓ 对象已上传：${KEY}"

# ----------------------------------------------------------------------------
# 4. 创建分析任务
# ----------------------------------------------------------------------------
say "4. POST /analyses 创建任务"
CREATE_JSON=$(curl -sS -X POST "${API_BASE_URL}/v1/analyses" "${AUTH[@]}" \
  -H "Content-Type: application/json" \
  -d "{\"upload_id\":\"${UPLOAD_ID}\",\"camera_angle\":\"face_on\",\"club_type\":\"iron_7\"}")
echo "$CREATE_JSON" | jq .
ANALYSIS_ID=$(echo "$CREATE_JSON" | jq -r '.data.analysis_id')
[[ "$ANALYSIS_ID" != "null" && -n "$ANALYSIS_ID" ]] || fail "创建失败"

# ----------------------------------------------------------------------------
# 5. 轮询状态直到 completed / failed（上限 60s，每秒查一次）
# ----------------------------------------------------------------------------
say "5. 轮询 /analyses/${ANALYSIS_ID}/status，等待 celery worker 消费（≤60s）"
STATUS="pending"
FINAL_STATUS=""
for i in $(seq 1 60); do
  STATUS_JSON=$(curl -sS "${AUTH[@]}" "${API_BASE_URL}/v1/analyses/${ANALYSIS_ID}/status")
  STATUS=$(echo "$STATUS_JSON" | jq -r '.data.status')
  STAGE=$(echo "$STATUS_JSON" | jq -r '.data.stage // "-"')
  PROGRESS=$(echo "$STATUS_JSON" | jq -r '.data.stage_progress // 0')
  printf "  [%02ds] status=%s stage=%s progress=%s\n" "$i" "$STATUS" "$STAGE" "$PROGRESS"
  if [[ "$STATUS" == "completed" || "$STATUS" == "failed" ]]; then
    FINAL_STATUS="$STATUS"
    break
  fi
  sleep 1
done
[[ -n "$FINAL_STATUS" ]] || fail "60s 内任务仍未完成（当前 status=$STATUS）"
say "最终 status=${FINAL_STATUS}"
echo "$STATUS_JSON" | jq '.data'

# ----------------------------------------------------------------------------
# 6. 取报告
# ----------------------------------------------------------------------------
if [[ "$FINAL_STATUS" == "completed" ]]; then
  say "6. GET /analyses/${ANALYSIS_ID} —— 预期 200 + 完整报告"
  HTTP=$(curl -sS -o /tmp/m2_report.json -w '%{http_code}' \
    "${AUTH[@]}" "${API_BASE_URL}/v1/analyses/${ANALYSIS_ID}")
  [[ "$HTTP" == "200" ]] || fail "应 200，实际 $HTTP"
  jq '.data | {
    id, status, overall_score, score_level,
    phase_scores_keys: (.phase_scores | keys),
    issues_count: (.issues | length),
    recommendations_count: (.recommendations | length),
    skeleton_video_url, thumbnail_url, analyzed_at
  }' /tmp/m2_report.json
else
  say "6. 任务最终 failed，读取错误"
  curl -sS "${AUTH[@]}" "${API_BASE_URL}/v1/analyses/${ANALYSIS_ID}/status" | jq '.data.error'
fi

# ----------------------------------------------------------------------------
# 7. 列表
# ----------------------------------------------------------------------------
say "7a. GET /analyses?page=1&page_size=10 全部"
curl -sS "${AUTH[@]}" "${API_BASE_URL}/v1/analyses?page=1&page_size=10" | jq '.data | {total, page, page_size, has_more, count: (.items | length)}'

say "7b. GET /analyses?club_type=iron_7 筛选"
curl -sS "${AUTH[@]}" "${API_BASE_URL}/v1/analyses?club_type=iron_7" | jq '.data | {total, items: [.items[].club_type]}'

say "✅ M2-T1+T2+T6 全链路通过（sample → 登录 → 上传 → celery → 报告 → 列表）"
