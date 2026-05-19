/**
 * invitationService 单测：邀请码信息与邀请列表
 */

import { invitationService } from '@/services/invitationService'
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

describe('invitationService', () => {
  test('getInfo → GET /users/me/invite-info', async () => {
    T.request.mockResolvedValueOnce(
      ok({ invite_code: 'ABC', total_invited: 0, valid_count: 0 }),
    )
    await invitationService.getInfo()
    const sent = T.request.mock.calls[0][0]
    expect(sent.method).toBe('GET')
    expect(sent.url).toContain('/users/me/invite-info')
  })

  test('listInvitations → GET /users/me/invitations', async () => {
    T.request.mockResolvedValueOnce(ok([]))
    await invitationService.listInvitations()
    const sent = T.request.mock.calls[0][0]
    expect(sent.method).toBe('GET')
    expect(sent.url).toContain('/users/me/invitations')
  })
})
