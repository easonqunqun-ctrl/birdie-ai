"""支付相关 API（W7-T1）.

端点概览：
- `GET  /v1/payments/plans`                    套餐列表（前端开通页用）
- `POST /v1/payments/orders`                   下单
- `POST /v1/payments/auto-renew`              自动续费（mock 落库；真实开通返回 papay 跳转参数）
- `POST /v1/payments/orders/{id}/mock-confirm` mock 模式立即支付
- `POST /v1/payments/orders/{id}/mock-refund`  mock 模式退款演练
- `POST /v1/payments/orders/{id}/apply-refund` 生产：微信「申请退款」，非 mock
- `POST /v1/payments/orders/{id}/sync-from-wechat` 客户端支付成功后主动拉微信查单补账（非 mock）
- `POST /v1/payments/wechat/notify`          微信支付异步通知（无 JWT，验签）
- `POST /v1/payments/wechat/refund-notify`   微信退款结果异步通知
- `POST /v1/payments/wechat/papay-notify`    委托代扣签约结果（平文/加密兼容尝试）
- `GET  /v1/payments/orders/{id}`              订单详情
- `GET  /v1/users/me/orders`                   当前用户订单列表
- `GET  /v1/users/me/membership`               当前会员状态
"""

import json

import structlog
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError
from redis.asyncio import Redis
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import get_current_user
from app.config import settings
from app.core.database import get_db
from app.core.exceptions import AppException, ThirdPartyError
from app.core.redis import get_redis
from app.integrations import wechat_pay_v3
from app.models.user import User
from app.schemas.base import APIResponse, ok
from app.schemas.payment import (
    ApplyRefundResponse,
    AutoRenewRequest,
    AutoRenewResponse,
    CancelAutoRenewResponse,
    CreateOrderRequest,
    CreateOrderResponse,
    MembershipInfo,
    OrderResponse,
    PapayMiniProgramSignPayload,
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
    "/auto-renew",
    summary="开通/关闭自动续费（mock 直接落库；真实模式开通时返回跳转签约参数）",
    response_model=APIResponse[AutoRenewResponse],
)
async def post_auto_renew(
    payload: AutoRenewRequest,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> APIResponse[AutoRenewResponse]:
    try:
        extra = await payment_service.apply_auto_renew(
            db, user, enabled=payload.enabled, redis=redis
        )
        await db.commit()
        await db.refresh(user)
    except AppException:
        await db.rollback()
        raise
    papay = None
    if extra:
        papay = PapayMiniProgramSignPayload(
            pre_entrustweb_id=extra["pre_entrustweb_id"],
            redirect_appid=extra["redirect_appid"],
            redirect_path=extra["redirect_path"],
        )
    return ok(AutoRenewResponse(auto_renew=user.auto_renew, papay_sign=papay))


@router.post(
    "/membership/cancel-auto-renew",
    summary="关闭会员自动续费（docs/02 §6.5）",
    response_model=APIResponse[CancelAutoRenewResponse],
)
async def cancel_auto_renew(
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    redis: Redis = Depends(get_redis),
) -> APIResponse[CancelAutoRenewResponse]:
    """关闭自动续费。语义与 ``POST /v1/payments/auto-renew {enabled:false}`` 等价，
    单独提供独立端点是为了客户端 UI 调用清晰（"关闭自动续费"按钮 vs 通用 toggle）。
    """
    try:
        await payment_service.apply_auto_renew(db, user, enabled=False, redis=redis)
        await db.commit()
        await db.refresh(user)
    except AppException:
        await db.rollback()
        raise
    return ok(
        CancelAutoRenewResponse(
            auto_renew=user.auto_renew,
            expires_at=user.membership_expires_at,
        ),
        message=(
            "已关闭自动续费"
            if not user.membership_expires_at
            else "已关闭自动续费，当前会员有效期至 "
            f"{user.membership_expires_at.strftime('%Y-%m-%d')}"
        ),
    )


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
    "/orders/{order_id}/mock-refund",
    summary="Mock 模式：对已支付订单记账退款并降级会员（仅 WECHAT_PAY_MOCK_MODE=true 可用）",
    response_model=APIResponse[OrderResponse],
)
async def mock_refund(
    order_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    reason: str | None = None,
) -> APIResponse[OrderResponse]:
    """生产退款走 `apply-refund` + `refund-notify`；本路由仅 mock 演练。"""
    order = await payment_service.get_order(db, order_id, user)
    await payment_service.mock_refund_paid_order(db, order, user, reason=reason)
    await db.commit()
    await db.refresh(order)
    await db.refresh(user)
    return ok(OrderResponse.model_validate(order))


@router.post(
    "/orders/{order_id}/apply-refund",
    summary="生产：对已支付订单向微信发起全额退款申请（非 mock）；结果以异步 refund-notify 为准",
    response_model=APIResponse[ApplyRefundResponse],
)
async def apply_wechat_refund_route(
    order_id: str,
    user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
    reason: str | None = None,
) -> APIResponse[ApplyRefundResponse]:
    order = await payment_service.get_order(db, order_id, user)
    wx, ord2 = await payment_service.apply_wechat_refund_for_order(db, order, user, reason=reason)
    await db.commit()
    await db.refresh(ord2)
    return ok(ApplyRefundResponse(order=OrderResponse.model_validate(ord2), wechat=wx))


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


@router.post(
    "/wechat/refund-notify",
    summary="微信退款结果异步通知",
    include_in_schema=True,
)
async def wechat_refund_notify(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """V3：验签解密 → `refunded` + 会员降级。始终 HTTP 200 + body code（与支付 notify 一致语义）。"""
    if settings.WECHAT_PAY_MOCK_MODE:
        return JSONResponse(
            content={"code": "FAIL", "message": "mock 模式不处理"},
            status_code=200,
        )
    body = await request.body()
    headers = {k: v for k, v in request.headers.items()}
    try:
        payload = await wechat_pay_v3.decrypt_wechat_pay_notify_resource(raw_body=body, headers=headers)
    except Exception as e:
        logger.warning("wechat_refund_notify_parse_error", error=str(e))
        return JSONResponse(content={"code": "FAIL", "message": "验签或解密失败"}, status_code=200)
    if not payload:
        return JSONResponse(content={"code": "FAIL", "message": "验签失败"}, status_code=200)
    try:
        ok_rf, msg = await payment_service.process_wechat_refund_notify(db, payload)
        if ok_rf:
            await db.commit()
            return JSONResponse(content={"code": "SUCCESS", "message": "成功"}, status_code=200)
        await db.rollback()
        return JSONResponse(content={"code": "FAIL", "message": msg}, status_code=200)
    except Exception as e:
        await db.rollback()
        logger.exception("wechat_refund_notify_handle_fail", error=str(e))
        return JSONResponse(content={"code": "FAIL", "message": "处理失败"}, status_code=200)


@router.post(
    "/wechat/papay-notify",
    summary="微信委托代扣签约结果通知（HTTPS POST JSON）",
    include_in_schema=True,
)
async def wechat_papay_contract_notify(
    request: Request,
    db: AsyncSession = Depends(get_db),
) -> JSONResponse:
    """MVP：优先按平文 JSON；若外层带 `resource`，再尝试按 V3 AEAD 解密。"""
    if settings.WECHAT_PAY_MOCK_MODE:
        return JSONResponse(
            content={"code": "FAIL", "message": "mock 模式不处理"},
            status_code=200,
        )
    body = await request.body()
    headers = {k: v for k, v in request.headers.items()}
    payload: dict
    try:
        outer = json.loads(body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return JSONResponse(content={"code": "FAIL", "message": "bad json"}, status_code=200)
    if not isinstance(outer, dict):
        return JSONResponse(content={"code": "FAIL", "message": "bad json"}, status_code=200)
    payload = outer
    if "resource" in outer:
        dec = await wechat_pay_v3.decrypt_wechat_pay_notify_resource(
            raw_body=body, headers=headers
        )
        if isinstance(dec, dict):
            payload = dec
    try:
        ok_n, msg = await payment_service.process_papay_contract_notify(db, payload)
        if ok_n:
            await db.commit()
            return JSONResponse(content={"code": "SUCCESS", "message": "成功"}, status_code=200)
        await db.rollback()
        return JSONResponse(content={"code": "FAIL", "message": msg}, status_code=200)
    except Exception as e:
        await db.rollback()
        logger.exception("papay_notify_handle_fail", error=str(e))
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
            papay_contract_id=user.papay_contract_id,
        )
    )
