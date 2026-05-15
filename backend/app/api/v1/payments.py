"""支付相关 API（W7-T1）.

端点概览：
- `GET  /v1/payments/plans`                    套餐列表（前端开通页用）
- `POST /v1/payments/orders`                   下单
- `POST /v1/payments/orders/{id}/mock-confirm` mock 模式立即支付
- `POST /v1/payments/orders/{id}/sync-from-wechat` 客户端支付成功后主动拉微信查单补账（非 mock）
- `POST /v1/payments/wechat/notify`          微信支付异步通知（无 JWT，验签）
- `GET  /v1/payments/orders/{id}`              订单详情
- `GET  /v1/users/me/orders`                   当前用户订单列表
- `GET  /v1/users/me/membership`               当前会员状态
"""

import structlog
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession

from pydantic import ValidationError
from sqlalchemy.exc import SQLAlchemyError

from app.api.deps import get_current_user
from app.config import settings
from app.core.database import get_db
from app.core.exceptions import AppException, ThirdPartyError
from app.integrations import wechat_pay_v3
from app.models.user import User
from app.schemas.base import APIResponse, ok
from app.schemas.payment import (
    CreateOrderRequest,
    CreateOrderResponse,
    MembershipInfo,
    OrderResponse,
    PlanOption,
    SyncOrderFromWechatResponse,
)
from app.services import payment_service

router = APIRouter()
logger = structlog.get_logger("payments")


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
    try:
        order, prepay = await payment_service.create_order(db, user, payload.plan_type)
        await db.commit()
        await db.refresh(order)
    except AppException:
        await db.rollback()
        raise
    except SQLAlchemyError as e:
        await db.rollback()
        logger.exception(
            "payment_create_order_db_error",
            user_id=user.id,
            plan_type=payload.plan_type,
            error=str(e),
        )
        raise ThirdPartyError(
            message="订单保存失败，请稍后重试",
            detail=str(e),
        ) from e
    except Exception as e:
        await db.rollback()
        logger.exception(
            "payment_create_order_unexpected",
            user_id=user.id,
            plan_type=payload.plan_type,
            error=str(e),
        )
        raise ThirdPartyError(
            message="下单失败，请稍后重试",
            detail=str(e),
        ) from e

    try:
        body = CreateOrderResponse(
            order=OrderResponse.model_validate(order),
            prepay_params=prepay,
            mock_mode=settings.WECHAT_PAY_MOCK_MODE,
        )
    except ValidationError as e:
        logger.exception(
            "payment_create_order_response_validation_failed",
            order_id=getattr(order, "id", None),
            errors=e.errors(),
        )
        raise ThirdPartyError(
            message="订单已生成但响应异常，请刷新订单列表或稍后重试",
            detail=str(e),
        ) from e
    return ok(body)


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


@router.post(
    "/orders/{order_id}/sync-from-wechat",
    summary="支付成功后：按商户订单号向微信查单并完成本地到账（补异步通知缺口，非 mock）",
    response_model=APIResponse[SyncOrderFromWechatResponse],
)
async def sync_order_from_wechat(
    order_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
) -> APIResponse[SyncOrderFromWechatResponse]:
    synced, order, detail = await payment_service.sync_pending_order_from_wechat(
        db, order_id, user
    )
    await db.commit()
    await db.refresh(order)
    return ok(
        SyncOrderFromWechatResponse(
            order=OrderResponse.model_validate(order),
            synced=synced,
            detail=detail,
        )
    )


@router.post(
    "/wechat/notify",
    summary="微信支付结果通知",
    include_in_schema=True,
)
async def wechat_payment_notify(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """V3 回调：验签、解密、幂等置订单已支付。始终 HTTP 200，body 中 code=SUCCESS|FAIL（微信会重试 5xx）。"""
    if settings.WECHAT_PAY_MOCK_MODE:
        return JSONResponse(
            content={"code": "FAIL", "message": "mock 模式不处理"},
            status_code=200,
        )
    body = await request.body()
    headers = {k: v for k, v in request.headers.items()}
    try:
        data = await wechat_pay_v3.handle_payment_notify(raw_body=body, headers=headers)
    except Exception as e:
        logger.warning("wechat_notify_parse_error", error=str(e))
        return JSONResponse(content={"code": "FAIL", "message": "验签或解密失败"}, status_code=200)
    if not data:
        return JSONResponse(content={"code": "FAIL", "message": "验签失败"}, status_code=200)
    try:
        ok_paid, msg = await payment_service.process_wechat_payment_notify(db, data)
        if ok_paid:
            await db.commit()
            return JSONResponse(content={"code": "SUCCESS", "message": "成功"}, status_code=200)
        await db.rollback()
        return JSONResponse(content={"code": "FAIL", "message": msg}, status_code=200)
    except Exception as e:
        await db.rollback()
        logger.exception("wechat_notify_handle_fail", error=str(e))
        return JSONResponse(content={"code": "FAIL", "message": "处理失败"}, status_code=200)


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
