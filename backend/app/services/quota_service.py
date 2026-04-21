"""配额服务：分析配额（月）+ 对话配额（日）."""

from datetime import UTC, datetime, timedelta

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.core.security import new_id
from app.models.analysis import AnalysisQuota
from app.models.chat import ChatQuota
from app.models.user import User


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

    total = -1 if _is_member(user) else settings.FREE_USER_MONTHLY_ANALYSES
    quota = AnalysisQuota(
        id=new_id("aq"),
        user_id=user.id,
        quota_month=month_str,
        used=0,
        total=total,
        bonus=0,
    )
    db.add(quota)
    await db.flush()
    return quota


def analysis_remaining(quota: AnalysisQuota) -> int:
    """剩余次数。-1 = 无限."""
    if quota.total < 0:
        return 9999
    return max(0, quota.total + quota.bonus - quota.used)


async def check_analysis_quota(db: AsyncSession, user: User) -> AnalysisQuota:
    """配额预检：返回当月 quota；无剩余次数时抛 QuotaExceededError。

    注意：此方法**不扣减**配额，仅校验 + 初始化记录（写入当月空记录以便后续 consume）。
    供 `POST /v1/analyses/upload-token` 在签发凭证前使用。
    """
    from app.core.exceptions import QuotaExceededError

    quota = await get_or_create_analysis_quota(db, user)
    assert quota is not None  # create=True 时不会返回 None
    if analysis_remaining(quota) <= 0:
        raise QuotaExceededError(
            code=40006,
            message="本月分析次数已用完",
        )
    return quota


async def consume_analysis_quota(db: AsyncSession, user: User) -> AnalysisQuota:
    """扣减一次分析配额（创建 SwingAnalysis 记录时调用）。

    并发保护：依赖 SQLAlchemy 事务 + 同会话内的 flush；
    实际并发场景下若要严格防双扣，应在更上层使用 Redis 分布式锁或数据库行锁。
    MVP 阶段保持简单。
    """
    from app.core.exceptions import QuotaExceededError

    quota = await get_or_create_analysis_quota(db, user)
    assert quota is not None
    if analysis_remaining(quota) <= 0:
        raise QuotaExceededError(code=40006, message="本月分析次数已用完")
    # total=-1 表示无限，不计数（避免 used 无意义累加）
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

    total = -1 if _is_member(user) else settings.FREE_USER_DAILY_CHATS
    quota = ChatQuota(
        id=new_id("cq"),
        user_id=user.id,
        quota_date=today,
        used=0,
        total=total,
    )
    db.add(quota)
    await db.flush()
    return quota


def chat_remaining(quota: ChatQuota) -> int:
    if quota.total < 0:
        return 9999
    return max(0, quota.total - quota.used)


async def check_chat_quota(db: AsyncSession, user: User) -> ChatQuota:
    """消息发送前的配额预检。不足抛 ChatQuotaExhaustedError(40007)."""
    from app.core.exceptions import ChatQuotaExhaustedError

    quota = await get_or_create_chat_quota(db, user)
    assert quota is not None
    if chat_remaining(quota) <= 0:
        raise ChatQuotaExhaustedError()
    return quota


async def consume_chat_quota(db: AsyncSession, user: User) -> ChatQuota:
    """扣减一次对话配额。

    约定：一"轮" = 1 条 user message（无论 AI 回复是否成功）。
    但如果 AI 回复因服务端错误（超时 / LLM 5xx）失败，调用方应负责调
    `refund_chat_quota` 退回。用户主动中断不退（已经消耗了 LLM 预算）。
    """
    from app.core.exceptions import ChatQuotaExhaustedError

    quota = await get_or_create_chat_quota(db, user)
    assert quota is not None
    if chat_remaining(quota) <= 0:
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
