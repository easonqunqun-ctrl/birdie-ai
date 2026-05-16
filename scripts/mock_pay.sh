#!/usr/bin/env bash
# =====================================================
# W8-T6：白名单账号一键开通会员
# -----------------------------------------------------
# 用途：测试环境里，让一个真实微信登录过的账号立刻变会员，
#       好让团队内测验证"会员分支"（无限配额 / 入口徽章 / 专属文案 等）。
#
# 设计选型：
#   - 测试环境 `WECHAT_MOCK_LOGIN=false`，不能再凭 code 在 curl 里登录拿 token
#     → 直接绕开 HTTP 层，在 docker 容器里 psql 改 users 表字段
#   - 同时把 analysis_quotas / chat_quotas 当月/当日行的 total 设成 -1（无限），
#     与真实 mock-pay 路径 `activate_membership` 的行为对齐
#   - 幂等：重复执行会把到期时间延后 +N 天（不是从今天重新算，避免丢天数）
#
# 用法：
#   scripts/mock_pay.sh <openid | user_id | invite_code> [monthly|yearly]
#
# 示例：
#   scripts/mock_pay.sh o_mock_abc123           # 默认 monthly（30 天）
#   scripts/mock_pay.sh usr_a1b2c3d4e5f6 yearly # 用 user_id 开 365 天
#   scripts/mock_pay.sh A3X7KM                   # 用邀请码定位用户
#
# 执行环境：在 CVM 上、compose 栈已 up 的前提下跑（本脚本内部 docker compose exec）
# =====================================================

set -euo pipefail

IDENT="${1:-}"
PLAN="${2:-monthly}"

usage() {
    cat <<EOF
用法：$0 <openid|user_id|invite_code> [monthly|yearly]

示例：
  $0 o_mock_abc123
  $0 usr_a1b2c3d4e5f6 yearly
  $0 A3X7KM monthly

注意：
  - 必须在已部署 compose 栈的 CVM 上执行
  - 脚本会按先 openid → 再 user_id → 再 invite_code 的顺序匹配第一个命中的用户
  - monthly = +30 天，yearly = +365 天；重复执行会叠加
EOF
    exit 1
}

[[ -z "$IDENT" ]] && usage

case "$PLAN" in
    monthly) DAYS=30 ;;
    yearly)  DAYS=365 ;;
    *) echo "unknown plan: $PLAN (expected monthly|yearly)"; exit 1 ;;
esac

# 选择 compose 文件集：优先 docker-compose.test.yml（T4 测试栈），否则走 base
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
cd "$REPO_ROOT"

COMPOSE_FLAGS="-f docker-compose.yml"
if [[ -f docker-compose.test.yml ]]; then
    COMPOSE_FLAGS="$COMPOSE_FLAGS -f docker-compose.test.yml"
fi
if [[ -f .env.local ]]; then
    COMPOSE_FLAGS="$COMPOSE_FLAGS --env-file .env.local"
fi

PG_DB="${POSTGRES_DB:-xiaoniao}"
PG_USER="${POSTGRES_USER:-xiaoniao}"

echo "[mock_pay] 目标: $IDENT → +${DAYS}d ($PLAN)"

# SQL：
#   - 先定位 user.id（三选一匹配，取第一个非空）
#   - UPDATE users 设 membership_type / started_at(首次) / expires_at(累加)
#   - UPDATE analysis_quotas / chat_quotas 当月/当日行（如果存在），total=-1
# 用 DO 块 + RAISE NOTICE 让输出清晰
read -r -d '' SQL <<SQL || true
DO \$\$
DECLARE
    v_user_id TEXT;
    v_plan TEXT := '${PLAN}';
    v_days INT := ${DAYS};
    v_now TIMESTAMPTZ := NOW();
    v_ident TEXT := '${IDENT}';
    v_current_expires TIMESTAMPTZ;
BEGIN
    SELECT id INTO v_user_id FROM users
     WHERE wechat_openid = v_ident OR id = v_ident OR invite_code = v_ident
     LIMIT 1;

    IF v_user_id IS NULL THEN
        RAISE EXCEPTION '未找到用户: %', v_ident;
    END IF;

    SELECT membership_expires_at INTO v_current_expires
      FROM users WHERE id = v_user_id;

    UPDATE users SET
        membership_type      = v_plan,
        membership_started_at = COALESCE(membership_started_at, v_now),
        membership_expires_at = GREATEST(COALESCE(v_current_expires, v_now), v_now)
                                + (v_days || ' days')::INTERVAL
    WHERE id = v_user_id;

    UPDATE analysis_quotas
       SET total = -1
     WHERE user_id = v_user_id
       AND quota_month = TO_CHAR(v_now AT TIME ZONE 'Asia/Shanghai', 'YYYY-MM');

    UPDATE chat_quotas
       SET total = -1
     WHERE user_id = v_user_id
       AND quota_date = (v_now AT TIME ZONE 'Asia/Shanghai')::date;

    RAISE NOTICE '✅ 开通成功: user_id=%, plan=%, +%d days, new_expires=%',
        v_user_id, v_plan, v_days,
        (SELECT membership_expires_at FROM users WHERE id = v_user_id);
END\$\$;
SQL

docker compose $COMPOSE_FLAGS exec -T postgres \
    psql -U "$PG_USER" -d "$PG_DB" -v ON_ERROR_STOP=1 <<< "$SQL"

echo "[mock_pay] 完成。可调 /v1/users/me/membership 检查是否生效："
echo "  curl -k https://\$HOST/v1/users/me/membership -H 'Authorization: Bearer \$TOKEN'"
