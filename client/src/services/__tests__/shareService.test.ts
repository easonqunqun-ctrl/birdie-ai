/**
 * shareService 单测：埋点 silent + 公开报告 noAuth
 */

import { shareService } from '@/services/shareService'
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

describe('shareService', () => {
  test('logShare → POST /shares/log；业务错误不 toast（silent）', async () => {
    T.request.mockResolvedValueOnce(ok({ id: 's1', share_type: 'report', created_at: '' }))
    await shareService.logShare({ share_type: 'report', target_id: 'a1' })
    const sent = T.request.mock.calls[0][0]
    expect(sent.method).toBe('POST')
    expect(sent.url).toContain('/shares/log')
    expect(sent.data).toEqual({ share_type: 'report', target_id: 'a1' })

    T.request.mockReset()
    T.request.mockResolvedValueOnce({
      statusCode: 200,
      data: { code: 50001, message: '埋点失败' },
    })
    await expect(
      shareService.logShare({ share_type: 'moments' }),
    ).rejects.toThrow()
    expect(T.showToast).not.toHaveBeenCalled()
  })

  test('getPublicReport → GET /analyses/:id/public，无 Authorization（noAuth）', async () => {
    T.request.mockResolvedValueOnce(ok({ id: 'a1', overall_score: 80 }))
    await shareService.getPublicReport('a1')
    const sent = T.request.mock.calls[0][0]
    expect(sent.method).toBe('GET')
    expect(sent.url).toContain('/analyses/a1/public')
    expect(sent.header?.Authorization).toBeUndefined()
  })
})
