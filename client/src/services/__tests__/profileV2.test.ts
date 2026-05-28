/**
 * P2-M9-03 · profileV2 service 单测：URL / method / payload 透传 + 错误码 passthrough。
 */

import { profileV2Service } from '@/services/profileV2'
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

const stubRead = {
  user_id: 'u_test',
  handicap_official: null,
  handicap_self: null,
  handicap_source: null,
  height_cm: null,
  weight_kg: null,
  handedness: null,
  known_injuries: [],
  mid_long_goals: [],
  training_preference: null,
  weekly_target_sessions: null,
  favorite_course_ids: [],
  privacy_payload: {
    handicap_consent: false,
    body_consent: false,
    injury_consent: false,
    location_consent: false,
    coach_visible_consent: false,
  },
  coach_visible_fields: [],
}

describe('profileV2Service', () => {
  test('get → GET /users/me/profile-v2', async () => {
    T.request.mockResolvedValueOnce(ok(stubRead))
    const res = await profileV2Service.get()
    const sent = T.request.mock.calls[0][0]
    expect(sent.method).toBe('GET')
    expect(sent.url).toContain('/users/me/profile-v2')
    expect(res.user_id).toBe('u_test')
  })

  test('update → PUT with patch payload', async () => {
    T.request.mockResolvedValueOnce(
      ok({ ...stubRead, handicap_self: 18.5, handedness: 'right' }),
    )
    const res = await profileV2Service.update({
      handicap_self: 18.5,
      handedness: 'right',
    })
    const sent = T.request.mock.calls[0][0]
    expect(sent.method).toBe('PUT')
    expect(sent.url).toContain('/users/me/profile-v2')
    expect(sent.data).toEqual({ handicap_self: 18.5, handedness: 'right' })
    expect(res.handicap_self).toBe(18.5)
  })

  test('update 显式 null 触发清空（PATCH 语义）', async () => {
    T.request.mockResolvedValueOnce(ok(stubRead))
    await profileV2Service.update({ handicap_self: null, handicap_source: null })
    const sent = T.request.mock.calls[0][0]
    // null 必须保留在 payload 中（不能被 stringify 吃掉）；让后端识别"清空"意图
    expect(JSON.stringify(sent.data)).toContain('"handicap_self":null')
  })

  test('update 已知伤病字段透传', async () => {
    T.request.mockResolvedValueOnce(
      ok({ ...stubRead, known_injuries: ['lower_back'] }),
    )
    const res = await profileV2Service.update({ known_injuries: ['lower_back'] })
    expect(res.known_injuries).toEqual(['lower_back'])
  })

  test('404 未启用 flag → RequestError 透传，UI 自决', async () => {
    T.request.mockResolvedValueOnce({
      statusCode: 404,
      data: { code: 40404, message: '二期画像功能未开放' },
    })
    await expect(profileV2Service.get()).rejects.toThrow()
  })

  test('listFavoriteVenues → GET /users/me/profile-v2/favorite-venues', async () => {
    T.request.mockResolvedValueOnce(
      ok({
        items: [
          {
            id: 'ven_1',
            city: '上海',
            name: '测试练习场',
            venue_type: 'indoor_range',
            source: 'verified',
          },
        ],
        missing_ids: [],
        total: 1,
      }),
    )
    const res = await profileV2Service.listFavoriteVenues()
    const sent = T.request.mock.calls[0][0]
    expect(sent.method).toBe('GET')
    expect(sent.url).toContain('/users/me/profile-v2/favorite-venues')
    expect(res.total).toBe(1)
    expect(res.items[0].name).toBe('测试练习场')
  })
})
