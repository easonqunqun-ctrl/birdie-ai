import type {
  CreateOrderResponse,
  MembershipInfo,
  Order,
  PlanOption,
  PlanType,
  SyncOrderFromWechatResponse
} from '@/types/payment'
import { http } from './request'

/**
 * 会员 + 支付相关 API。
 *
 * W7 期间后端默认 `WECHAT_PAY_MOCK_MODE=true`，`createOrder` 返回的
 * `mock_mode=true`；调用方（`pages/profile/membership.tsx`）需要按此分支：
 *  - mock：展示模拟弹窗 → 调 `mockConfirm(orderId)`
 *  - real：`mock_mode=false`，必须调 `wx.requestPayment(prepay_params)`（分支只看该字段，
 *    勿再用编译期 PAYMENT_MOCK 覆盖）
 */
export const paymentService = {
  listPlans() {
    return http.get<PlanOption[]>('/payments/plans')
  },
  createOrder(planType: PlanType) {
    return http.post<CreateOrderResponse>(
      '/payments/orders',
      { plan_type: planType },
      { silent: true },
    )
  },
  mockConfirm(orderId: string) {
    return http.post<Order>(`/payments/orders/${orderId}/mock-confirm`)
  },
  /** 真实微信支付：`requestPayment` 成功后调用，弥补 notify 未及时到达的情况 */
  syncFromWechat(orderId: string) {
    return http.post<SyncOrderFromWechatResponse>(
      `/payments/orders/${orderId}/sync-from-wechat`
    )
  },
  getOrder(orderId: string) {
    return http.get<Order>(`/payments/orders/${orderId}`)
  },
  listMyOrders() {
    return http.get<Order[]>('/users/me/orders')
  },
  getMembership() {
    return http.get<MembershipInfo>('/users/me/membership')
  }
}
