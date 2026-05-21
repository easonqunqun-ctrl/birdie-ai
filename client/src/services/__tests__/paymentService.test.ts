/**
 * paymentService.ts 单测：URL / payload / silent 配置
 *
 * createOrder 必须 silent=true：成功路径里 UI 自己负责弹起微信支付，
 * 失败再让 UI 决定文案（如 40301 配额耗尽 vs 40005 套餐已下架）。
 */

import { paymentService } from '@/services/paymentService'
import Taro from '@tarojs/taro'

const T = Taro as unknown as Record<string, jest.Mock>
const ok = (data: unknown) => ({
  statusCode: 200,
  data: { code: 0, message: 'ok', data },
})

beforeEach(() => {
  ;(Taro as any).clearStorageSync()
  T.request.mockReset()
})

describe('paymentService', () => {
  test('listPlans → GET /payments/plans', async () => {
    T.request.mockResolvedValueOnce(ok([]))
    await paymentService.listPlans()
    const sent = T.request.mock.calls[0][0]
    expect(sent.method).toBe('GET')
    expect(sent.url).toContain('/payments/plans')
  })

  test('createOrder → POST /payments/orders + silent', async () => {
    T.request.mockResolvedValueOnce(ok({ order_id: 'o1', mock_mode: true }))
    await paymentService.createOrder('monthly')
    const sent = T.request.mock.calls[0][0]
    expect(sent.method).toBe('POST')
    expect(sent.url).toContain('/payments/orders')
    expect(sent.data).toEqual({ plan_type: 'monthly' })
    // 业务错误码（40301 等）由 UI 处理，不应该走默认 toast
    // 触发一次 silent 路径
    T.request.mockReset()
    T.request.mockResolvedValueOnce({
      statusCode: 200,
      data: { code: 40301, message: '套餐已下架' },
    })
    await expect(paymentService.createOrder('yearly')).rejects.toThrow()
    expect(T.showToast).not.toHaveBeenCalled()
  })

  test('mockConfirm → POST /payments/orders/:id/mock-confirm', async () => {
    T.request.mockResolvedValueOnce(ok({ id: 'o1', status: 'paid' }))
    await paymentService.mockConfirm('o1')
    expect(T.request.mock.calls[0][0].url).toContain('/payments/orders/o1/mock-confirm')
    expect(T.request.mock.calls[0][0].method).toBe('POST')
  })

  test('syncFromWechat → POST /payments/orders/:id/sync-from-wechat', async () => {
    T.request.mockResolvedValueOnce(ok({ order: { id: 'o1', status: 'paid' } }))
    await paymentService.syncFromWechat('o1')
    expect(T.request.mock.calls[0][0].url).toContain(
      '/payments/orders/o1/sync-from-wechat',
    )
  })

  test('getOrder → GET /payments/orders/:id', async () => {
    T.request.mockResolvedValueOnce(ok({ id: 'o1' }))
    await paymentService.getOrder('o1')
    expect(T.request.mock.calls[0][0].url).toContain('/payments/orders/o1')
  })

  test('listMyOrders → GET /users/me/orders', async () => {
    T.request.mockResolvedValueOnce(ok([]))
    await paymentService.listMyOrders()
    expect(T.request.mock.calls[0][0].url).toContain('/users/me/orders')
  })

  test('getMembership → GET /users/me/membership', async () => {
    T.request.mockResolvedValueOnce(ok({ active: false }))
    await paymentService.getMembership()
    expect(T.request.mock.calls[0][0].url).toContain('/users/me/membership')
  })

  test('postAutoRenew(true/false) → POST /payments/auto-renew', async () => {
    T.request.mockResolvedValueOnce(ok({ enabled: true }))
    await paymentService.postAutoRenew(true)
    let sent = T.request.mock.calls[0][0]
    expect(sent.url).toContain('/payments/auto-renew')
    expect(sent.method).toBe('POST')
    expect(sent.data).toEqual({ enabled: true })

    T.request.mockResolvedValueOnce(ok({ enabled: false }))
    await paymentService.postAutoRenew(false)
    sent = T.request.mock.calls[1][0]
    expect(sent.data).toEqual({ enabled: false })
  })

  test('postCancelAutoRenew → POST /payments/membership/cancel-auto-renew', async () => {
    T.request.mockResolvedValueOnce(
      ok({ auto_renew: false, expires_at: '2027-04-14T10:38:00+08:00' }),
    )
    const res = await paymentService.postCancelAutoRenew()
    const sent = T.request.mock.calls[0][0]
    expect(sent.method).toBe('POST')
    expect(sent.url).toContain('/payments/membership/cancel-auto-renew')
    // 无 payload
    expect(sent.data).toBeUndefined()
    expect(res.auto_renew).toBe(false)
    expect(res.expires_at).toBe('2027-04-14T10:38:00+08:00')
  })
})
