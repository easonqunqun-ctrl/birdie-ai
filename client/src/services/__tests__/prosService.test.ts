/**
 * P2-M12-03 · prosService 客户端单测：URL / method / 过滤参数。
 */

import { prosService } from '@/services/prosService'
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

describe('prosService', () => {
  test('list → GET /pros', async () => {
    T.request.mockResolvedValueOnce(ok([]))
    await prosService.list()
    const sent = T.request.mock.calls[0][0]
    expect(sent.method).toBe('GET')
    expect(sent.url).toMatch(/\/pros$/)
  })

  test('detail → GET /pros/{id}', async () => {
    T.request.mockResolvedValueOnce(
      ok({
        id: 'pp_abc',
        name: '示范',
        name_en: 'Demo',
        nationality: 'CHN',
        handedness: 'right',
        height_cm: 180,
        avatar_url: null,
        short_bio: null,
        license_status: 'public_clip',
        is_active: true,
        sort_order: 0,
      }),
    )
    const res = await prosService.detail('pp_abc')
    expect(res.name).toBe('示范')
    expect(T.request.mock.calls[0][0].url).toMatch(/\/pros\/pp_abc$/)
  })

  test('clips without filter → GET /pros/{id}/clips', async () => {
    T.request.mockResolvedValueOnce(ok([]))
    await prosService.clips('pp_x')
    expect(T.request.mock.calls[0][0].url).toMatch(/\/pros\/pp_x\/clips$/)
  })

  test('clips with camera_angle → query string', async () => {
    T.request.mockResolvedValueOnce(ok([]))
    await prosService.clips('pp_x', { camera_angle: 'face_on' })
    expect(T.request.mock.calls[0][0].url).toContain('camera_angle=face_on')
  })

  test('clips with both filters → combined query', async () => {
    T.request.mockResolvedValueOnce(ok([]))
    await prosService.clips('pp_x', {
      camera_angle: 'down_the_line',
      club_type: 'iron_7',
    })
    const url: string = T.request.mock.calls[0][0].url
    expect(url).toContain('camera_angle=down_the_line')
    expect(url).toContain('club_type=iron_7')
  })

  test('club_type with special chars → encodeURIComponent', async () => {
    T.request.mockResolvedValueOnce(ok([]))
    await prosService.clips('pp_x', { club_type: 'iron 7' })
    expect(T.request.mock.calls[0][0].url).toContain('club_type=iron%207')
  })
})
