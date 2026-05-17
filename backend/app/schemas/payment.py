"""支付 / 会员相关 Pydantic schema."""

from datetime import datetime
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field

PlanType = Literal["monthly", "yearly"]  # W7 不开 family
OrderStatus = Literal["pending", "paid", "failed", "refunded", "cancelled"]


class PlanOption(BaseModel):
    """套餐选项（前端展示用）."""

    plan_type: PlanType
    name: str
    amount_cents: int  # 分
    amount_yuan_display: str  # "¥39"
    duration_days: int
    badge: str | None = None  # "年付立省 ¥169" 等


class CreateOrderRequest(BaseModel):
    plan_type: PlanType


class PrepayParams(BaseModel):
    """客户端 wx.requestPayment 入参。mock 模式下仅含 `mock=True`."""

    model_config = ConfigDict(extra="allow")

    mock: bool = False
    # 真实模式下（W8 接入后）以下字段会填值：
    time_stamp: str | None = None
    nonce_str: str | None = None
    package: str | None = None
    sign_type: str | None = None
    pay_sign: str | None = None


class OrderResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    plan_type: PlanType
    amount: int  # 分
    currency: str
    status: OrderStatus
    membership_start: datetime | None
    membership_end: datetime | None
    paid_at: datetime | None
    created_at: datetime


class CreateOrderResponse(BaseModel):
    order: OrderResponse
    prepay_params: PrepayParams
    mock_mode: bool = Field(
        description="后端 WECHAT_PAY_MOCK_MODE 值，方便前端决定走 wx.requestPayment 还是直接 confirm",
    )


class ApplyRefundResponse(BaseModel):
    """已提交微信退款单；仍以退款异步通知为最终态（订单先保持 paid）."""

    order: OrderResponse
    wechat: dict[str, Any] = Field(
        default_factory=dict,
        description="`/v3/refund/domestic/refunds` JSON 应答摘要",
    )


class SyncOrderFromWechatResponse(BaseModel):
    """前端在 wx.requestPayment 成功后调用：主动拉微信订单态以补异步回调缺口。"""

    order: OrderResponse
    synced: bool = Field(description="本次请求是否刚从微信侧确认为 SUCCESS 并完成本地到账")
    detail: str = Field(description="人可读说明，如 already_paid、微信侧 trade_state")


class MembershipInfo(BaseModel):
    """当前会员状态（嵌入 UserResponse 的派生视图）."""

    is_member: bool
    membership_type: Literal["free", "monthly", "yearly", "family"]
    expires_at: datetime | None
    days_remaining: int  # 会员剩余天数；非会员为 0
    auto_renew: bool
