/**
 * P2-M9-02 · userClubsService 客户端单测：URL / method / payload 透传。
 */

import { userClubsService } from '@/services/userClubs'
import Taro from '@tarojs/taro'

const T = Taro as unknown as Record<string, jest.Mock>
const ok = (data: unknown) => ({
  statusCode: 200,
  data: { code: 0, message: '', data },
})

beforeEach(() => {
  ;(Taro as any).clearStorageSync()
  T.request.mockReset()
})

describe('userClubsService', () => {
  test('list → GET /users/me/clubs', async () => {
    T.request.mockResolvedValueOnce(
      ok({ items: [], total: 0, max_clubs: 14, remaining: 14 }),
    )
    const res = await userClubsService.list()
    const sent = T.request.mock.calls[0][0]
    expect(sent.method).toBe('GET')
    expect(sent.url).toContain('/users/me/clubs')
    expect(res.max_clubs).toBe(14)
  })

  test('create → POST /users/me/clubs with payload', async () => {
    T.request.mockResolvedValueOnce(
      ok({
        id: 'ucb_abc',
        club_type: 'iron_7',
        nickname: 'A',
        self_yardage_m: 140,
        is_active: true,
        sort_order: 0,
        created_at: '2026-05-25T00:00:00Z',
        updated_at: '2026-05-25T00:00:00Z',
      }),
    )
    const res = await userClubsService.create({
      club_type: 'iron_7',
      nickname: 'A',
      self_yardage_m: 140,
    })
    const sent = T.request.mock.calls[0][0]
    expect(sent.method).toBe('POST')
    expect(sent.url).toContain('/users/me/clubs')
    expect(sent.data).toEqual({
      club_type: 'iron_7',
      nickname: 'A',
      self_yardage_m: 140,
    })
    expect(res.id).toBe('ucb_abc')
  })

  test('update → PUT /users/me/clubs/{id}', async () => {
    T.request.mockResolvedValueOnce(
      ok({
        id: 'ucb_abc',
        club_type: 'iron_7',
        nickname: 'B',
        self_yardage_m: 140,
        is_active: true,
        sort_order: 0,
        created_at: '2026-05-25T00:00:00Z',
        updated_at: '2026-05-25T00:00:00Z',
      }),
    )
    await userClubsService.update('ucb_abc', { nickname: 'B' })
    const sent = T.request.mock.calls[0][0]
    expect(sent.method).toBe('PUT')
    expect(sent.url).toContain('/users/me/clubs/ucb_abc')
    expect(sent.data).toEqual({ nickname: 'B' })
  })

  test('remove → DELETE /users/me/clubs/{id}', async () => {
    T.request.mockResolvedValueOnce(ok({ id: 'ucb_abc', deleted: true }))
    const res = await userClubsService.remove('ucb_abc')
    const sent = T.request.mock.calls[0][0]
    expect(sent.method).toBe('DELETE')
    expect(sent.url).toContain('/users/me/clubs/ucb_abc')
    expect(res.deleted).toBe(true)
  })

  test('40020 上限错误码透传为 RequestError，UI 自决', async () => {
    T.request.mockResolvedValueOnce({
      statusCode: 200,
      data: { code: 40020, message: '装备清单最多 14 支' },
    })
    await expect(
      userClubsService.create({ club_type: 'driver' }),
    ).rejects.toThrow()
  })
})
