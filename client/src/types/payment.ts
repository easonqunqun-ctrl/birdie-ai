/**
 * 支付 / 会员相关类型（对齐 backend/app/schemas/payment.py）.
 *
 * W7 通通走 mock-pay：create_order 返回 `prepay_params.mock=true`，客户端
 * 立即调 `/orders/{id}/mock-confirm` 模拟支付成功。真实 `wx.requestPayment`
 * 分支保留在 `paymentService.payOrder` 里，W8 接商户号后启用。
 */

export type PlanType = 'monthly' | 'yearly'
export type OrderStatus = 'pending' | 'paid' | 'failed' | 'refunded' | 'cancelled'

export interface PlanOption {
  plan_type: PlanType
  name: string
  amount_cents: number
  amount_yuan_display: string
  duration_days: number
  badge: string | null
}

export interface PrepayParams {
  mock: boolean
  payment_method?: 'mock' | 'jsapi' | 'virtual'
  time_stamp?: string
  nonce_str?: string
  package?: string
  sign_type?: string
  pay_sign?: string
  sign_data?: string
  pay_sig?: string
  signature?: string
  mode?: string
}

export interface Order {
  id: string
  user_id: string
  plan_type: PlanType
  amount: number
  currency: string
  status: OrderStatus
  membership_start: string | null
  membership_end: string | null
  paid_at: string | null
  created_at: string
}

export interface CreateOrderResponse {
  order: Order
  prepay_params: PrepayParams
  mock_mode: boolean
  virtual_pay_enabled?: boolean
}

/** POST /payments/orders/{id}/sync-from-wechat */
export interface SyncOrderFromWechatResponse {
  order: Order
  synced: boolean
  detail: string
}

export interface MembershipInfo {
  is_member: boolean
  membership_type: 'free' | 'monthly' | 'yearly' | 'family'
  expires_at: string | null
  days_remaining: number
  auto_renew: boolean
  virtual_pay_enabled?: boolean
  papay_contract_id?: string | null
}

export interface PapayMiniProgramSignPayload {
  pre_entrustweb_id: string
  redirect_appid: string
  redirect_path: string
}

export interface AutoRenewResponse {
  auto_renew: boolean
  papay_sign: PapayMiniProgramSignPayload | null
}

/** POST /payments/membership/cancel-auto-renew （docs/02 §6.5） */
export interface CancelAutoRenewResponse {
  auto_renew: boolean
  expires_at: string | null
}
