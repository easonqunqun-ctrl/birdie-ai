/**
 * feedbackService.ts 单测：URL / payload / 失败码穿透
 */

import { feedbackService } from '@/services/feedbackService'
import Taro from '@tarojs/taro'

const T = Taro as unknown as Record<string, jest.Mock>
const ok = (data: unknown) => ({
  statusCode: 200,
  data: { code: 0, message: '感谢你的反馈', data },
})

beforeEach(() => {
  ;(Taro as any).clearStorageSync()
  T.request.mockReset()
})

describe('feedbackService', () => {
  test('submit → POST /feedback with content+contact', async () => {
    T.request.mockResolvedValueOnce(ok({ feedback_id: 'fb_abc' }))
    const res = await feedbackService.submit({
      content: '希望加夜间模式',
      contact: 'wechat:hi',
    })
    const sent = T.request.mock.calls[0][0]
    expect(sent.method).toBe('POST')
    expect(sent.url).toContain('/feedback')
    expect(sent.data).toEqual({
      content: '希望加夜间模式',
      contact: 'wechat:hi',
    })
    expect(res.feedback_id).toBe('fb_abc')
  })

  test('submit 不传 contact 时 payload.contact 为 undefined', async () => {
    T.request.mockResolvedValueOnce(ok({ feedback_id: 'fb_xyz' }))
    await feedbackService.submit({ content: 'bug 报告' })
    const sent = T.request.mock.calls[0][0]
    expect(sent.data).toEqual({ content: 'bug 报告', contact: undefined })
  })

  test('429 业务码穿透为 RequestError，UI 自决', async () => {
    T.request.mockResolvedValueOnce({
      statusCode: 200,
      data: { code: 42901, message: '反馈太频繁' },
    })
    await expect(feedbackService.submit({ content: 'x' })).rejects.toThrow()
  })
})
