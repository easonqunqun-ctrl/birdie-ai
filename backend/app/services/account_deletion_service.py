"""账号注销：冷静期 + 到期硬删（MVP §3.4）."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.exceptions import BadRequestError
from app.models.payment import Order
from app.models.user import User

DELETION_COOLDOWN = timedelta(days=7)
CONFIRM_PHRASE = "DELETE"


def has_pending_payments_block_deletion(orders: list[Order]) -> bool:
    """未支付/待处理订单阻注销（MVP：pending 单阻）。"""
    return any(o.status == "pending" for o in orders)


async def _list_recent_orders(db: AsyncSession, user_id: str) -> list[Order]:
    r = await db.execute(select(Order).where(Order.user_id == user_id).limit(50))
    return list(r.scalars().all())


async def request_account_deletion(
    db: AsyncSession,
    user: User,
    *,
    confirm_text: str,
) -> User:
    if (confirm_text or "").strip() != CONFIRM_PHRASE:
        raise BadRequestError(code=40001, message='请输入大写 "DELETE" 以确认')
    if user.account_deletion_scheduled_at is not None:
        raise BadRequestError(code=40015, message="已提交注销申请，冷静期内可取消")
    orders = await _list_recent_orders(db, user.id)
    if has_pending_payments_block_deletion(orders):
        raise BadRequestError(
            code=40016,
            message="你有未完成的会员订单，请处理或等待关闭后再申请注销",
        )
    user.account_deletion_scheduled_at = datetime.now(UTC) + DELETION_COOLDOWN
    await db.flush()
    return user


async def cancel_account_deletion(db: AsyncSession, user: User) -> User:
    if user.account_deletion_scheduled_at is None:
        raise BadRequestError(code=40001, message="未处于注销申请状态")
    user.account_deletion_scheduled_at = None
    await db.flush()
    return user


async def purge_user_if_due(
    db: AsyncSession, user: User
) -> bool:
    """若已超过冷静期执行时间，硬删 user 行（子表 CASCADE）。"""
    if user.account_deletion_scheduled_at is None:
        return False
    if user.account_deletion_scheduled_at > datetime.now(UTC):
        return False
    uid = user.id
    await db.execute(delete(User).where(User.id == uid))
    await db.commit()
    return True
