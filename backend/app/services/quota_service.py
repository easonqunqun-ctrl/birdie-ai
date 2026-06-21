"""配额服务：分析配额（月）+ 对话配额（日）."""

from datetime import UTC, datetime, timedelta

from redis.asyncio import Redis
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.logging import get_logger
from app.core.security import new_id
from app.models.analysis import AnalysisQuota
from app.models.chat import ChatQuota
from app.models.user import User

logger = get_logger("quota")

# W8-T3：「无限」对外 sentinel。前端约定 < 0 即无限，避免每个调用方
#   各自记 9999 等魔法数。会员（quota.total = -1）和 QUOTA_MODE=unlimited
#   都通过该 sentinel 透出。
UNLIMITED_REMAINING: int = -1


def _is_unlimited_mode() -> bool:
    """W8-T3：QUOTA_MODE=unlimited 或公测 PROMO_FREE_UNTIL 时跳过配额限制."""
    if settings.QUOTA_MODE == "unlimited":
        return True
    from app.services import promo_service

    return promo_service.is_promo_free_active()


def _now_month_str() -> str:
    """当前月份字符串：2026-04（按 UTC+8）."""
    now = datetime.now(UTC) + timedelta(hours=8)
    return now.strftime("%Y-%m")


def _next_month_reset_at() -> datetime:
    """下个自然月 1 号 0 点（UTC+8 的时区）."""
    now = datetime.now(UTC) + timedelta(hours=8)
    if now.month == 12:
        nxt = now.replace(year=now.year + 1, month=1, day=1, hour=0, minute=0, second=0, microsecond=0)
    else:
        nxt = now.replace(month=now.month + 1, day=1, hour=0, minute=0, second=0, microsecond=0)
    return nxt - timedelta(hours=8)  # 转回 UTC


def _is_member(user: User) -> bool:
    """判断当前是否为有效会员。W7-T1 起统一委托给 payment_service.is_member."""
    # 循环导入规避：在函数内 import（payment_service 依赖本模块）
    from app.services.payment_service import is_member

    return is_member(user)


def _is_unlimited_user(user: User) -> bool:
    """该用户是否享有无限配额（会员 / QUOTA_MODE=unlimited）."""
    return _is_unlimited_mode() or _is_member(user)


async def _coach_quota_bypass_eligible(
    db: AsyncSession,
    user: User,
    *,
    request_role: str | None,
) -> bool:
    if not settings.COACH_QUOTA_BYPASS_ENABLED:
        return False
    role = (request_role or "user").strip().lower()
    if role != "coach":
        return False
    from app.services.coach_profile_service import is_active_coach

    return await is_active_coach(db, user_id=user.id)


async def _coach_quota_bypass_applies(
    db: AsyncSession,
    user: User,
    *,
    request_role: str | None,
    quota_type: str,
    redis: Redis | None = None,
    track_abuse: bool = True,
) -> bool:
    if not await _coach_quota_bypass_eligible(db, user, request_role=request_role):
        return False
    if track_abuse:
        if redis is None:
            from app.core.redis import get_redis

            redis = await get_redis()
        from app.services.coach_abuse_service import track_coach_quota_usage

        await track_coach_quota_usage(redis, user_id=user.id, quota_type=quota_type)
    logger.info(
        "quota_skipped",
        extra={"user_id": user.id, "role": "coach", "quota_type": quota_type},
    )
    return True


# ==================== 分析配额 ====================
async def get_or_create_analysis_quota(
    db: AsyncSession,
    user: User,
    *,
    create: bool = True,
) -> AnalysisQuota | None:
    """获取当月分析配额，不存在时创建."""
    month_str = _now_month_str()
    stmt = select(AnalysisQuota).where(
        AnalysisQuota.user_id == user.id,
        AnalysisQuota.quota_month == month_str,
    )
    quota = (await db.execute(stmt)).scalar_one_or_none()
    if quota is not None:
        return quota
    if not create:
        return None

    total = -1 if _is_unlimited_user(user) else settings.FREE_USER_MONTHLY_ANALYSES
    quota = AnalysisQuota(
        id=new_id("aq"),
        user_id=user.id,
        quota_month=month_str,
        used=0,
        total=total,
        bonus=0,
    )
    db.add(quota)
    # 并发首次写入会触发 (user_id, quota_month) UNIQUE 冲突；
    # 用 SAVEPOINT 包裹 flush，冲突时只回滚 SAVEPOINT、保留外层事务，
    # 然后把别人写好的行 SELECT 回来返回给调用方。
    try:
        async with db.begin_nested():
            await db.flush()
    except IntegrityError:
        existing = (await db.execute(stmt)).scalar_one()
        return existing
    return quota


def analysis_remaining(quota: AnalysisQuota) -> int:
    """剩余次数。-1 = 无限（前端约定 < 0 即无限）."""
    if quota.total < 0:
        return UNLIMITED_REMAINING
    return max(0, quota.total + quota.bonus - quota.used)


async def check_analysis_quota(
    db: AsyncSession,
    user: User,
    *,
    request_role: str | None = None,
    redis: Redis | None = None,
) -> AnalysisQuota:
    """配额预检：返回当月 quota；无剩余次数时抛 QuotaExceededError。

    注意：此方法**不扣减**配额，仅校验 + 初始化记录（写入当月空记录以便后续 consume）。
    供 `POST /v1/analyses/upload-token` 在签发凭证前使用。
    """
    from app.core.exceptions import QuotaExceededError

    quota = await get_or_create_analysis_quota(db, user)
    assert quota is not None  # create=True 时不会返回 None
    if await _coach_quota_bypass_applies(
        db,
        user,
        request_role=request_role,
        quota_type="analysis",
        redis=redis,
        track_abuse=False,
    ):
        return quota
    # W8-T3：剩余 = -1（unlimited / 会员）或 > 0 都放行；
    #   "==0" 才算耗尽。原 `<= 0` 会把 -1 误判为耗尽。
    remaining = analysis_remaining(quota)
    if remaining == 0:
        raise QuotaExceededError(
            code=40006,
            message="本月分析次数已用完",
        )
    return quota


async def consume_analysis_quota(
    db: AsyncSession,
    user: User,
    *,
    request_role: str | None = None,
    redis: Redis | None = None,
) -> AnalysisQuota:
    """扣减一次分析配额（创建 SwingAnalysis 记录时调用）。

    并发保护（P0-4）：
        1. 先 ``get_or_create`` 确保当月行存在（首次写入会持有插入锁，
           插入冲突由 `uq_analysis_quota` 保证唯一）。
        2. 再用 ``SELECT ... FOR UPDATE`` 把该行排它锁回来，重新读取最新
           ``used`` 值，避免两个并发请求同时读到 ``used=N``、各 +1 → ``N+1``，
           导致一次配额被扣两次（原实现的"双花"风险）。
        3. 锁在事务提交后释放；上层 API 处于同一个事务里，commit 之后才
           对其它请求可见。

    依赖：调用方运行在 ``AsyncSession`` 的事务中（FastAPI 默认 ``get_db``
    会在 yield 内开启一个事务）。SQLite 无视 ``FOR UPDATE``，因此这条
    保护只在 PostgreSQL 上真正生效；测试若用 SQLite 不影响功能。
    """
    from app.core.exceptions import QuotaExceededError

    quota = await get_or_create_analysis_quota(db, user)
    assert quota is not None
    if await _coach_quota_bypass_applies(
        db, user, request_role=request_role, quota_type="analysis", redis=redis
    ):
        return quota
    # 关键：行锁定 + 重新读取，避免并发双扣
    locked_stmt = (
        select(AnalysisQuota)
        .where(AnalysisQuota.id == quota.id)
        .with_for_update()
    )
    quota = (await db.execute(locked_stmt)).scalar_one()

    if analysis_remaining(quota) == 0:
        raise QuotaExceededError(code=40006, message="本月分析次数已用完")
    # total=-1 表示无限（会员 / QUOTA_MODE=unlimited），不计数（避免 used 无意义累加）
    if quota.total >= 0:
        quota.used += 1
        await db.flush()
    return quota


async def refund_analysis_quota(db: AsyncSession, quota: AnalysisQuota) -> None:
    """退回一次分析配额（分析失败且 quota_refunded=False 时调用）。

    幂等性由调用方（`SwingAnalysis.quota_refunded` 字段）保证，本函数不查不校验；
    只要 total >= 0 且 used > 0，就执行 used -= 1。
    """
    if quota.total >= 0 and quota.used > 0:
        quota.used -= 1
        await db.flush()


async def refund_analysis_quota_by_user_month(
    db: AsyncSession, *, user_id: str, quota_month: str
) -> bool:
    """根据 user_id + 月份字符串（如 '2026-04'）查找配额记录并退回 1 次。

    供 Celery task 里不持有 User / AnalysisQuota 实例的场景用。
    返回 True 表示确实退成功（或无需退），False 表示找不到对应记录。
    """
    stmt = select(AnalysisQuota).where(
        AnalysisQuota.user_id == user_id,
        AnalysisQuota.quota_month == quota_month,
    )
    quota = (await db.execute(stmt)).scalar_one_or_none()
    if quota is None:
        return False
    await refund_analysis_quota(db, quota)
    return True


# ==================== 对话配额 ====================
async def get_or_create_chat_quota(
    db: AsyncSession,
    user: User,
    *,
    create: bool = True,
) -> ChatQuota | None:
    """获取当日对话配额，不存在时创建."""
    today = (datetime.now(UTC) + timedelta(hours=8)).date()
    stmt = select(ChatQuota).where(
        ChatQuota.user_id == user.id,
        ChatQuota.quota_date == today,
    )
    quota = (await db.execute(stmt)).scalar_one_or_none()
    if quota is not None:
        return quota
    if not create:
        return None

    total = -1 if _is_unlimited_user(user) else settings.FREE_USER_DAILY_CHATS
    quota = ChatQuota(
        id=new_id("cq"),
        user_id=user.id,
        quota_date=today,
        used=0,
        total=total,
    )
    db.add(quota)
    # SAVEPOINT 同上：并发首次写入冲突时只回滚 nested，把已存在行返回
    try:
        async with db.begin_nested():
            await db.flush()
    except IntegrityError:
        existing = (await db.execute(stmt)).scalar_one()
        return existing
    return quota


def chat_remaining(quota: ChatQuota) -> int:
    if quota.total < 0:
        return UNLIMITED_REMAINING
    return max(0, quota.total - quota.used)


async def check_chat_quota(
    db: AsyncSession,
    user: User,
    *,
    request_role: str | None = None,
    redis: Redis | None = None,
) -> ChatQuota:
    """消息发送前的配额预检。不足抛 ChatQuotaExhaustedError(40007)."""
    from app.core.exceptions import ChatQuotaExhaustedError

    quota = await get_or_create_chat_quota(db, user)
    assert quota is not None
    if await _coach_quota_bypass_applies(
        db,
        user,
        request_role=request_role,
        quota_type="chat",
        redis=redis,
        track_abuse=False,
    ):
        return quota
    if chat_remaining(quota) == 0:
        raise ChatQuotaExhaustedError()
    return quota


async def consume_chat_quota(
    db: AsyncSession,
    user: User,
    *,
    request_role: str | None = None,
    redis: Redis | None = None,
) -> ChatQuota:
    """扣减一次对话配额。

    约定：一"轮" = 1 条 user message（无论 AI 回复是否成功）。
    但如果 AI 回复因服务端错误（超时 / LLM 5xx）失败，调用方应负责调
    `refund_chat_quota` 退回。用户主动中断不退（已经消耗了 LLM 预算）。

    并发保护（P0-4）：与 ``consume_analysis_quota`` 同思路，
    用 ``SELECT ... FOR UPDATE`` 锁住当日行后再 +1，避免并发双扣。
    """
    from app.core.exceptions import ChatQuotaExhaustedError

    quota = await get_or_create_chat_quota(db, user)
    assert quota is not None
    if await _coach_quota_bypass_applies(
        db, user, request_role=request_role, quota_type="chat", redis=redis
    ):
        return quota
    locked_stmt = (
        select(ChatQuota)
        .where(ChatQuota.id == quota.id)
        .with_for_update()
    )
    quota = (await db.execute(locked_stmt)).scalar_one()

    if chat_remaining(quota) == 0:
        raise ChatQuotaExhaustedError()
    if quota.total >= 0:
        quota.used += 1
        await db.flush()
    return quota


async def refund_chat_quota(db: AsyncSession, quota: ChatQuota) -> None:
    """退回一次对话配额（LLM 服务端失败时调用）。

    幂等性：只要 total >= 0 且 used > 0 就 -1；重复调用会持续递减，
    调用方应保证每条 user message 最多调用一次。
    """
    if quota.total >= 0 and quota.used > 0:
        quota.used -= 1
        await db.flush()


def next_month_reset_iso() -> datetime:
    """下个月配额重置时间（UTC）."""
    return _next_month_reset_at()
