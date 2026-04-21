"""支付相关 API（W7-T1）.

端点概览：
- `GET  /v1/payments/plans`                    套餐列表（前端开通页用）
- `POST /v1/payments/orders`                   下单
- `POST /v1/payments/orders/{id}/mock-confirm` mock 模式立即支付（W8 真实化后会用 feature flag 屏蔽）
- `GET  /v1/payments/orders/{id}`              订单详情
- `GET  /v1/users/me/orders`                   当前用户订单列表
- `GET  /v1/users/me/membership`               当前会员状态
"""

from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.config import settings
from app.core.database import get_db
from app.models.user import User
from app.schemas.base import APIResponse, ok
from app.schemas.payment import (
    CreateOrderRequest,
    CreateOrderResponse,
    MembershipInfo,
    OrderResponse,
    PlanOption,
)
from app.services import payment_service

router = APIRouter()


@router.get(
    "/plans",
    summary="获取套餐列表",
    response_model=APIResponse[list[PlanOption]],
)
async def list_plans() -> APIResponse[list[PlanOption]]:
    return ok(payment_service.list_plans())


@router.post(
    "/orders",
    summary="创建会员订单",
    response_model=APIResponse[CreateOrderResponse],
)
async def create_order(
    payload: CreateOrderRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[CreateOrderResponse]:
    order, prepay = await payment_service.create_order(db, user, payload.plan_type)
    await db.commit()
    await db.refresh(order)
    return ok(
        CreateOrderResponse(
            order=OrderResponse.model_validate(order),
            prepay_params=prepay,
            mock_mode=settings.WECHAT_PAY_MOCK_MODE,
        )
    )


@router.post(
    "/orders/{order_id}/mock-confirm",
    summary="Mock 模式：立即标记订单已支付并激活会员（仅 WECHAT_PAY_MOCK_MODE=true 可用）",
    response_model=APIResponse[OrderResponse],
)
async def mock_confirm(
    order_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[OrderResponse]:
    order = await payment_service.get_order(db, order_id, user)
    await payment_service.mock_confirm_payment(db, order, user)
    await db.commit()
    await db.refresh(order)
    return ok(OrderResponse.model_validate(order))


@router.get(
    "/orders/{order_id}",
    summary="订单详情",
    response_model=APIResponse[OrderResponse],
)
async def get_order(
    order_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[OrderResponse]:
    order = await payment_service.get_order(db, order_id, user)
    return ok(OrderResponse.model_validate(order))


# ==================== 挂在 /me 下面的路由 ====================
me_router = APIRouter()


@me_router.get(
    "/orders",
    summary="当前用户订单列表",
    response_model=APIResponse[list[OrderResponse]],
)
async def list_my_orders(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[list[OrderResponse]]:
    orders = await payment_service.list_user_orders(db, user)
    return ok([OrderResponse.model_validate(o) for o in orders])


@me_router.get(
    "/membership",
    summary="当前会员状态",
    response_model=APIResponse[MembershipInfo],
)
async def get_membership(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[MembershipInfo]:
    # 读之前先做一次懒降级（过期的话立即降）
    downgraded = await payment_service.ensure_membership_valid(db, user)
    if downgraded:
        await db.commit()
        await db.refresh(user)

    return ok(
        MembershipInfo(
            is_member=payment_service.is_member(user),
            membership_type=user.membership_type,  # type: ignore[arg-type]
            expires_at=user.membership_expires_at,
            days_remaining=payment_service.days_remaining(user),
            auto_renew=user.auto_renew,
        )
    )
