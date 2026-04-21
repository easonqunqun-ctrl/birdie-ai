import type {
  CreateOrderResponse,
  MembershipInfo,
  Order,
  PlanOption,
  PlanType
} from '@/types/payment'
import { http } from './request'

/**
 * 会员 + 支付相关 API。
 *
 * W7 期间后端默认 `WECHAT_PAY_MOCK_MODE=true`，`createOrder` 返回的
 * `mock_mode=true`；调用方（`pages/profile/membership.tsx`）需要按此分支：
 *  - mock：展示模拟弹窗 → 调 `mockConfirm(orderId)`
 *  - real（W8 上线）：调 `wx.requestPayment(prepay_params)` → 后端回调处理
 */
export const paymentService = {
  listPlans() {
    return http.get<PlanOption[]>('/payments/plans')
  },
  createOrder(planType: PlanType) {
    return http.post<CreateOrderResponse>('/payments/orders', { plan_type: planType })
  },
  mockConfirm(orderId: string) {
    return http.post<Order>(`/payments/orders/${orderId}/mock-confirm`)
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
